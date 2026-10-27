from datetime import datetime
import secrets

from fastapi import Cookie, Depends, HTTPException, Request, status
from typing import List
from jose import ExpiredSignatureError, JWTError, jwt
from app.core.security import (
    ACCESS_COOKIE_NAME,
    ALGORITHM,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    hash_session_secret,
)
from app.core.config import settings
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository

async def get_current_user(
    request: Request,
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(access_token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    session = await SessionRepository.get_by_id(session_id)
    if (
        not session
        or session.revoked_at is not None
        or session.expires_at <= datetime.utcnow()
        or str(session.user_id) != user_id
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        csrf_header = request.headers.get(CSRF_HEADER_NAME)
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        if (
            not csrf_header
            or not csrf_cookie
            or not secrets.compare_digest(csrf_header, csrf_cookie)
            or not secrets.compare_digest(
                session.csrf_token_hash,
                hash_session_secret(csrf_header),
            )
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")

    try:
        user = await UserRepository.get_by_id(user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this role"
            )
        return current_user
