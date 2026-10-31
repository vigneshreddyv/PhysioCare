from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any, Dict, Optional, Union

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

ACCESS_COOKIE_NAME = "physiocare_access"
REFRESH_COOKIE_NAME = "physiocare_refresh"
CSRF_COOKIE_NAME = "physiocare_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


def create_access_token(
    subject: Union[str, Any],
    role: str,
    session_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "sid": session_id,
        "type": "access",
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(
    subject: Union[str, Any],
    role: str,
    session_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "sid": session_id,
        "jti": secrets.token_urlsafe(24),
        "type": "refresh",
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_REFRESH_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str, secret: str = settings.JWT_SECRET) -> Dict[str, Any]:
    try:
        decoded = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return decoded
    except jwt.InvalidTokenError:
        return {}


def hash_session_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_csrf_token(session_id: str) -> str:
    return hmac.new(
        settings.JWT_REFRESH_SECRET.encode("utf-8"),
        f"physiocare-csrf:{session_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
