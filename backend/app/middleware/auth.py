from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
import logging

from jose import JWTError, ExpiredSignatureError, jwt

from app.core.security import ALGORITHM
from app.core.config import settings
from app.models.user import User
from app.repositories.user_repository import UserRepository

security_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Diagnostic logging (Phase 4, Task 11).
#
# The previous implementation printed full Authorization headers, token
# prefixes, and decoded JWT payloads. That is prohibited: authentication
# credentials, tokens, and claims are NEVER logged here. Failure logging is
# kept, but restricted to safe reason categories — no submitted token, no
# decoded token, no exception text that could embed credential material.
#
# Authentication semantics are UNCHANGED: valid tokens authenticate exactly
# as before, invalid tokens fail exactly as before (same status codes and
# the same fixed detail messages).
# ---------------------------------------------------------------------------
logger = logging.getLogger("physiocare.auth")


def _log_auth_failure(reason: str) -> None:
    """Log an authentication failure without any credential material."""
    logger.warning("Authentication failed: reason=%s", reason)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> User:
    # 1. Received Authorization header (presence only — never its value).
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 2. Decode JWT payload. No token/payload logging.
    payload = None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        _log_auth_failure("expired_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        # Reason CATEGORY only — the raw exception text is deliberately not
        # logged or returned (it can echo submitted token material).
        _log_auth_failure("invalid_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check token type
    if not payload or payload.get("type") != "access":
        _log_auth_failure("wrong_token_type")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. User lookup (subject id is not logged).
    user_id = payload.get("sub")
    if not user_id:
        _log_auth_failure("missing_subject")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = await UserRepository.get_by_id(user_id)
    except Exception:
        logger.error("Authentication failed: database error during user lookup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database lookup error during authentication"
        )

    if not user:
        _log_auth_failure("user_not_found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active:
        _log_auth_failure("inactive_user")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return user

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            # Safe log: role names only — never user identity or credentials.
            logger.warning(
                "Authorization failed: role=%s not in allowed_roles=%s",
                current_user.role,
                self.allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this role"
            )

        return current_user


async def verify_caseload(patient_id: str, current_user: User):
    if current_user.role == "doctor":
        from app.repositories.profile_repository import ProfileRepository
        doctor = await ProfileRepository.get_doctor_by_user_id(str(current_user.id))
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Clinician profile not found."
            )
        patient = await ProfileRepository.get_patient_by_id(patient_id)
        if not patient or not patient.primary_doctor_id or str(patient.primary_doctor_id) != str(doctor.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found or access denied."
            )
    elif current_user.role == "patient":
        # Patients cannot access clinician monitoring or other patients' datasets
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted."
        )