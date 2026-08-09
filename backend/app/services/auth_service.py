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

from app.repositories.user_repository import UserRepository
from app.repositories.profile_repository import ProfileRepository

from app.schemas.auth import UserRegister, Token


class AuthService:

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

        if not payload or payload.get("type") != "refresh":
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

        access = create_access_token(user.id, user.role)
        refresh = create_refresh_token(user.id, user.role)

        return Token(
            access_token=access,
            refresh_token=refresh,
            role=user.role,
            full_name=user.full_name,
            email=user.email,
        )