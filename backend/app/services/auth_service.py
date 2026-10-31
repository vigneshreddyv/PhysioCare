import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.auth_session import AuthSession

from app.repositories.user_repository import UserRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.auth_session_repository import AuthSessionRepository

from app.schemas.auth import UserRegister, Token


class AuthService:

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    async def _create_refresh_session(user: User, refresh_token: str) -> None:
        from app.core.config import settings

        payload = decode_token(refresh_token, secret=settings.JWT_REFRESH_SECRET)
        now = datetime.now(timezone.utc)
        session = AuthSession.model_construct(
            user_id=str(user.id),
            family_id=payload["family_id"],
            jti=payload["jti"],
            token_hash=AuthService._token_hash(refresh_token),
            issued_at=now,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
        await AuthSessionRepository.create(session)

    @staticmethod
    async def register(schema: UserRegister) -> User:

        existing = await UserRepository.get_by_email(schema.email)

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        hashed = get_password_hash(schema.password)

        user = User(
            email=schema.email,
            hashed_password=hashed,
            role="patient",
            full_name=schema.full_name,
        )

        saved_user = await UserRepository.create(user)

        patient = Patient(
            user_id=saved_user.id,
        )

        await ProfileRepository.create_patient(patient)

        return saved_user

    @staticmethod
    async def login(email: str, password: str) -> Token:

        user = await UserRepository.get_by_email(email)

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        access = create_access_token(user.id, user.role)
        refresh = create_refresh_token(user.id, user.role)

        try:
            await AuthService._create_refresh_session(user, refresh)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            )

        return Token(
            access_token=access,
            refresh_token=refresh,
            role=user.role,
            full_name=user.full_name,
            email=user.email,
        )

    @staticmethod
    async def refresh_tokens(refresh_token: str) -> Token:

        from app.core.config import settings

        payload = decode_token(
            refresh_token,
            secret=settings.JWT_REFRESH_SECRET,
        )

        if (
            not payload
            or payload.get("type") != "refresh"
            or not payload.get("sub")
            or not payload.get("jti")
            or not payload.get("family_id")
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user = await UserRepository.get_by_id(payload["sub"])

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
            )

        new_jti = uuid4().hex
        try:
            access = create_access_token(user.id, user.role)
            new_refresh_token = create_refresh_token(
                user.id,
                user.role,
                jti=new_jti,
                family_id=payload["family_id"],
            )
            new_payload = decode_token(
                new_refresh_token,
                secret=settings.JWT_REFRESH_SECRET,
            )
            new_expires_at = datetime.fromtimestamp(
                new_payload["exp"],
                tz=timezone.utc,
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            )

        now = datetime.now(timezone.utc)
        try:
            rotated = await AuthSessionRepository.rotate_for_refresh(
                user_id=str(user.id),
                family_id=payload["family_id"],
                jti=payload["jti"],
                token_hash=AuthService._token_hash(refresh_token),
                new_jti=new_jti,
                new_token_hash=AuthService._token_hash(new_refresh_token),
                new_expires_at=new_expires_at,
                now=now,
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            )

        if not rotated:
            try:
                await AuthSessionRepository.revoke_family(
                    str(user.id),
                    payload["family_id"],
                    reason="refresh_token_reuse_detected",
                    now=now,
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable",
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token revoked or already used",
            )

        return Token(
            access_token=access,
            refresh_token=new_refresh_token,
            role=user.role,
            full_name=user.full_name,
            email=user.email,
        )

    @staticmethod
    async def logout(user: User) -> None:
        try:
            await AuthSessionRepository.revoke_all_for_user(
                str(user.id),
                reason="logout",
                now=datetime.now(timezone.utc),
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            )
