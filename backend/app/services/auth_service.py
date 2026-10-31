import secrets
from dataclasses import dataclass
from datetime import timedelta

from beanie import PydanticObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.time import utc_now
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_csrf_token,
    create_refresh_token,
    decode_token,
    hash_session_secret,
)
from app.core.config import settings
from app.core.lab_demo import LAB_DEMO_REHEARSAL_TAG

from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.auth_session import AuthSession

from app.repositories.user_repository import UserRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.session_repository import SessionRepository

from app.schemas.auth import StaffCreate, UserRegister


@dataclass
class SessionBundle:
    access_token: str
    refresh_token: str
    csrf_token: str
    user: User


class AuthService:

    @staticmethod
    async def register(
        schema: UserRegister,
        *,
        demo_rehearsal_tag: str | None = None,
    ) -> User:
        AuthService._validate_demo_tag(demo_rehearsal_tag)
        return await AuthService._create_user(
            email=schema.email,
            password=schema.password,
            full_name=schema.full_name,
            role="patient",
            demo_rehearsal_tag=demo_rehearsal_tag,
        )

    @staticmethod
    async def register_staff(
        schema: StaffCreate,
        *,
        demo_rehearsal_tag: str | None = None,
    ) -> User:
        tag = demo_rehearsal_tag or schema.demo_rehearsal_tag
        AuthService._validate_demo_tag(tag)
        return await AuthService._create_user(
            email=schema.email,
            password=schema.password,
            full_name=schema.full_name,
            role=schema.role,
            demo_rehearsal_tag=tag,
        )

    @staticmethod
    def _validate_demo_tag(tag: str | None) -> None:
        if tag is not None and (
            not settings.LAB_DEMO_MODE or tag != LAB_DEMO_REHEARSAL_TAG
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Demo tagging is available only in the isolated laboratory demo",
            )

    @staticmethod
    async def _create_user(
        email: str,
        password: str,
        full_name: str,
        role: str,
        demo_rehearsal_tag: str | None = None,
    ) -> User:

        existing = await UserRepository.get_by_email(email)

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        hashed = get_password_hash(password)

        user = User(
            email=email,
            hashed_password=hashed,
            role=role,
            full_name=full_name,
            demo_rehearsal_tag=demo_rehearsal_tag,
        )

        try:
            saved_user = await UserRepository.create(user)
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            ) from exc

        if role == "patient":

            patient = Patient(
                user_id=saved_user.id,
                demo_rehearsal_tag=demo_rehearsal_tag,
            )

            await ProfileRepository.create_patient(patient)

        elif role == "doctor":

            doctor = Doctor(
                user_id=saved_user.id,
                specialization="General Physiotherapy",
            )

            await ProfileRepository.create_doctor(doctor)

        return saved_user

    @staticmethod
    async def login(email: str, password: str) -> SessionBundle:

        user = await UserRepository.get_by_email(email)

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        session_id = PydanticObjectId()
        now = utc_now()
        bundle = AuthService._create_session_bundle(user, str(session_id))
        session = AuthSession.model_construct(
            id=session_id,
            user_id=user.id,
            refresh_token_hash=hash_session_secret(bundle.refresh_token),
            csrf_token_hash=hash_session_secret(bundle.csrf_token),
            demo_rehearsal_tag=getattr(user, "demo_rehearsal_tag", None),
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            created_at=now,
            rotated_at=now,
        )
        try:
            await SessionRepository.create(session)
        except Exception as exc:
            raise AuthService._authentication_unavailable() from exc
        return bundle

    @staticmethod
    async def refresh_tokens(refresh_token: str, csrf_token: str) -> SessionBundle:
        payload = decode_token(
            refresh_token,
            secret=settings.JWT_REFRESH_SECRET,
        )
        session, user = await AuthService._validate_refresh_session(
            payload,
            refresh_token,
            csrf_token,
        )
        bundle = AuthService._create_session_bundle(user, str(session.id))
        now = utc_now()
        try:
            rotated = await SessionRepository.rotate_for_refresh(
                session_id=str(session.id),
                user_id=session.user_id,
                current_refresh_token_hash=hash_session_secret(refresh_token),
                csrf_token_hash=hash_session_secret(csrf_token),
                new_refresh_token_hash=hash_session_secret(bundle.refresh_token),
                new_expires_at=(
                    now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
                ),
                now=now,
            )
        except Exception as exc:
            raise AuthService._authentication_unavailable() from exc

        if not rotated:
            await AuthService._revoke_session_id(
                str(session.id),
                reason="refresh_token_reuse_detected",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token revoked or already used",
            )
        return bundle

    @staticmethod
    async def issue_csrf_token(refresh_token: str) -> str:
        payload = decode_token(refresh_token, secret=settings.JWT_REFRESH_SECRET)
        session, _user = await AuthService._validate_refresh_session(
            payload,
            refresh_token,
            csrf_token=None,
            require_csrf=False,
        )
        return create_csrf_token(str(session.id))

    @staticmethod
    async def validate_refresh_session(refresh_token: str, csrf_token: str) -> None:
        payload = decode_token(refresh_token, secret=settings.JWT_REFRESH_SECRET)
        await AuthService._validate_refresh_session(payload, refresh_token, csrf_token)

    @staticmethod
    async def revoke_session(access_token: str | None, refresh_token: str | None) -> None:
        for token, secret in (
            (access_token, settings.JWT_SECRET),
            (refresh_token, settings.JWT_REFRESH_SECRET),
        ):
            if not token:
                continue
            payload = decode_token(token, secret=secret)
            session_id = payload.get("sid") if payload else None
            if not session_id:
                continue
            await AuthService._revoke_session_id(session_id, reason="logout")
            return

    @staticmethod
    async def _validate_refresh_session(
        payload: dict,
        refresh_token: str,
        csrf_token: str | None,
        require_csrf: bool = True,
    ) -> tuple[AuthSession, User]:
        if not payload or payload.get("type") != "refresh" or not payload.get("sid"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session",
            )

        try:
            session = await SessionRepository.get_by_id(payload["sid"])
        except Exception as exc:
            raise AuthService._authentication_unavailable() from exc
        if (
            not session
            or session.revoked_at is not None
            or session.expires_at <= utc_now()
            or str(session.user_id) != payload.get("sub")
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

        if not secrets.compare_digest(
            session.refresh_token_hash,
            hash_session_secret(refresh_token),
        ):
            await AuthService._revoke_session_id(
                str(session.id),
                reason="refresh_token_reuse_detected",
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

        if require_csrf and (
            not csrf_token
            or not secrets.compare_digest(
                session.csrf_token_hash,
                hash_session_secret(csrf_token),
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed",
            )

        try:
            user = await UserRepository.get_by_id(payload["sub"])
        except Exception as exc:
            raise AuthService._authentication_unavailable() from exc
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session",
            )
        return session, user

    @staticmethod
    def _create_session_bundle(user: User, session_id: str) -> SessionBundle:
        try:
            access_token = create_access_token(user.id, user.role, session_id)
            refresh_token = create_refresh_token(user.id, user.role, session_id)
            csrf_token = create_csrf_token(session_id)
        except Exception as exc:
            raise AuthService._authentication_unavailable() from exc
        return SessionBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            user=user,
        )

    @staticmethod
    async def _revoke_session_id(session_id: str, *, reason: str) -> None:
        try:
            await SessionRepository.revoke_by_id(
                session_id,
                reason=reason,
                now=utc_now(),
            )
        except Exception as exc:
            raise AuthService._authentication_unavailable() from exc

    @staticmethod
    def _authentication_unavailable() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )
