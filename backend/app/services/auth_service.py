from dataclasses import dataclass
from datetime import datetime, timedelta
import secrets

from beanie import PydanticObjectId
from fastapi import HTTPException, status

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
    async def register(schema: UserRegister) -> User:
        return await AuthService._create_user(
            email=schema.email,
            password=schema.password,
            full_name=schema.full_name,
            role="patient",
        )

    @staticmethod
    async def register_staff(schema: StaffCreate) -> User:
        return await AuthService._create_user(
            email=schema.email,
            password=schema.password,
            full_name=schema.full_name,
            role=schema.role,
        )

    @staticmethod
    async def _create_user(email: str, password: str, full_name: str, role: str) -> User:

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
        )

        saved_user = await UserRepository.create(user)

        if role == "patient":

            patient = Patient(
                user_id=saved_user.id,
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

        now = datetime.utcnow()
        session = await SessionRepository.create(
            AuthSession(
                id=PydanticObjectId(),
                user_id=user.id,
                refresh_token_hash="pending",
                csrf_token_hash="pending",
                expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                created_at=now,
                rotated_at=now,
            )
        )
        return await AuthService._rotate_session(session, user)

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
        return await AuthService._rotate_session(session, user)

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
            session = await SessionRepository.get_by_id(session_id)
            if session and session.revoked_at is None:
                session.revoked_at = datetime.utcnow()
                await SessionRepository.save(session)
            return

    @staticmethod
    async def _validate_refresh_session(
        payload: dict,
        refresh_token: str,
        csrf_token: str | None,
        require_csrf: bool = True,
    ) -> tuple[AuthSession, User]:
        if not payload or payload.get("type") != "refresh" or not payload.get("sid"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

        session = await SessionRepository.get_by_id(payload["sid"])
        if (
            not session
            or session.revoked_at is not None
            or session.expires_at <= datetime.utcnow()
            or str(session.user_id) != payload.get("sub")
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

        if not secrets.compare_digest(
            session.refresh_token_hash,
            hash_session_secret(refresh_token),
        ):
            session.revoked_at = datetime.utcnow()
            await SessionRepository.save(session)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

        if require_csrf and (
            not csrf_token
            or not secrets.compare_digest(
                session.csrf_token_hash,
                hash_session_secret(csrf_token),
            )
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")

        user = await UserRepository.get_by_id(payload["sub"])
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
        return session, user

    @staticmethod
    async def _rotate_session(session: AuthSession, user: User) -> SessionBundle:
        now = datetime.utcnow()
        session.expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session.rotated_at = now
        access_token = create_access_token(user.id, user.role, str(session.id))
        refresh_token = create_refresh_token(user.id, user.role, str(session.id))
        csrf_token = create_csrf_token(str(session.id))
        session.refresh_token_hash = hash_session_secret(refresh_token)
        session.csrf_token_hash = hash_session_secret(csrf_token)
        await SessionRepository.save(session)
        return SessionBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            user=user,
        )
