from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from jose import JWTError, ExpiredSignatureError, JWTError, jwt
from app.core.security import ALGORITHM
from app.core.config import settings
from app.models.user import User
from app.repositories.user_repository import UserRepository

security_scheme = HTTPBearer(auto_error=False)
print("######## AUTH.PY LOADED ########")

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> User:
    print(f"\n[DIAGNOSTIC] === START AUTHENTICATION TRACE ===")
    
    # 1. Received Authorization header
    auth_header = None
    if credentials:
        auth_header = f"Bearer {credentials.credentials}"
        print(f"[DIAGNOSTIC] Received Authorization Header: {auth_header}")
    else:
        print(f"[DIAGNOSTIC] No Authorization header received (credentials is None)")
        print(f"[DIAGNOSTIC] 401 Exception: Not authenticated")
        print(f"[DIAGNOSTIC] === END AUTHENTICATION TRACE ===\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    print(f"[DIAGNOSTIC] Extracted Token: {token[:25]}... (length: {len(token)} chars)" if token else "[DIAGNOSTIC] Token is empty/None")

    # 2. Decode JWT payload with detailed error handling
    payload = None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        print(f"[DIAGNOSTIC] JWT verification succeeded")
        print(f"[DIAGNOSTIC] Decoded JWT payload: {payload}")
    except ExpiredSignatureError as e:
        print(f"[DIAGNOSTIC] JWT verification failed - Reason: expired token")
        print(f"[DIAGNOSTIC] Exact exception: {type(e).__name__} ({str(e)})")
        print(f"[DIAGNOSTIC] 401 Exception: Token has expired")
        print(f"[DIAGNOSTIC] === END AUTHENTICATION TRACE ===\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        error_msg = str(e).lower()
        reason = "invalid signature, wrong secret, or malformed token"
        
        # Try to identify exact reason from error message
        if "signature" in error_msg:
            reason = "invalid signature (possibly wrong secret or altered signature)"
        elif "expired" in error_msg:
            reason = "expired token"
        elif "format" in error_msg or "malformed" in error_msg:
            reason = "malformed token"
        
        print(f"[DIAGNOSTIC] JWT verification failed - Reason: {reason}")
        print(f"[DIAGNOSTIC] Exact exception: {type(e).__name__} ({str(e)})")
        
        detail_msg = f"Invalid token: {str(e)}"
        if "signature" in error_msg:
            detail_msg = f"Invalid signature: {str(e)}"
        elif "malformed" in error_msg or "format" in error_msg:
            detail_msg = f"Malformed token: {str(e)}"

        print(f"[DIAGNOSTIC] 401 Exception: {detail_msg}")
        print(f"[DIAGNOSTIC] === END AUTHENTICATION TRACE ===\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail_msg,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"[DIAGNOSTIC] Unexpected verification failure - Reason: {str(e)}")
        print(f"[DIAGNOSTIC] Exact exception: {type(e).__name__} ({str(e)})")
        print(f"[DIAGNOSTIC] 401 Exception: Invalid token: {str(e)}")
        print(f"[DIAGNOSTIC] === END AUTHENTICATION TRACE ===\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check token type
    if not payload or payload.get("type") != "access":
        print(f"[DIAGNOSTIC] Verification failed: JWT type is not 'access' (got: '{payload.get('type')}')")
        print(f"[DIAGNOSTIC] 401 Exception: Invalid or expired access token")
        print(f"[DIAGNOSTIC] === END AUTHENTICATION TRACE ===\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. User lookup
    user_id = payload.get("sub")
    print(f"[DIAGNOSTIC] Decoded sub (User ID): {user_id}")
    print(f"[DIAGNOSTIC] Querying MongoDB via UserRepository.get_by_id for ID: {user_id}")
    
    try:
        user = await UserRepository.get_by_id(user_id)
        print(f"[DIAGNOSTIC] MongoDB query result: {user}")
    except Exception as e:
        print(f"[DIAGNOSTIC] MongoDB query failed with exception: {type(e).__name__} ({str(e)})")
        print(f"[DIAGNOSTIC] 401 Exception: Database lookup error")
        print(f"[DIAGNOSTIC] === END AUTHENTICATION TRACE ===\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database lookup error during authentication"
        )

    if not user:
        print(f"[DIAGNOSTIC] User lookup failed - User not found in DB for sub: {user_id}")
        print(f"[DIAGNOSTIC] 401 Exception: User not found")
        print(f"[DIAGNOSTIC] === END AUTHENTICATION TRACE ===\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active:
        print(f"[DIAGNOSTIC] User found but is_active is False")
        print(f"[DIAGNOSTIC] 400 Exception: Inactive user")
        print(f"[DIAGNOSTIC] === END AUTHENTICATION TRACE ===\n")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # 5. Success trace
    print(f"[DIAGNOSTIC] User authentication succeeded!")
    print(f"[DIAGNOSTIC] Authenticated User ID: {user.id}, Role: {user.role}, Name: {user.full_name}")
    print(f"[DIAGNOSTIC] === END AUTHENTICATION TRACE ===\n")
    return user

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        print(f"\n[DIAGNOSTIC] === RoleChecker Checking User: {current_user.id} ===")
        print(f"[DIAGNOSTIC] User Role: '{current_user.role}'")
        print(f"[DIAGNOSTIC] Allowed Roles: {self.allowed_roles}")
        
        if current_user.role not in self.allowed_roles:
            print(f"[DIAGNOSTIC] RoleChecker FAILED: User role '{current_user.role}' not in allowed roles {self.allowed_roles}")
            print(f"[DIAGNOSTIC] 403 Exception: Operation not permitted for this role")
            print(f"[DIAGNOSTIC] === END RoleChecker Trace ===\n")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this role"
            )
            
        print(f"[DIAGNOSTIC] RoleChecker PASSED")
        print(f"[DIAGNOSTIC] === END RoleChecker Trace ===\n")
        return current_user