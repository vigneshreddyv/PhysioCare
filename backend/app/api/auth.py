from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from app.models.user import User
from app.middleware.auth import get_current_user
from app.core.config import settings
from app.core.security import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFRESH_COOKIE_NAME,
)
from app.schemas.auth import CsrfResponse, SessionResponse, UserRegister, UserLogin
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(schema: UserRegister):
    user = await AuthService.register(schema)
    return {"message": "Registration successful", "email": user.email}

def set_session_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    secure = settings.cookie_secure
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api",
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/auth",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    secure = settings.cookie_secure
    for name, path, httponly in (
        (ACCESS_COOKIE_NAME, "/api", True),
        (REFRESH_COOKIE_NAME, "/api/auth", True),
        (CSRF_COOKIE_NAME, "/", False),
    ):
        response.delete_cookie(
            name,
            path=path,
            httponly=httponly,
            secure=secure,
            samesite="lax",
        )


def session_response(bundle) -> SessionResponse:
    return SessionResponse(
        role=bundle.user.role,
        full_name=bundle.user.full_name,
        email=bundle.user.email,
        csrf_token=bundle.csrf_token,
    )


@router.post("/login", response_model=SessionResponse)
async def login(schema: UserLogin, response: Response):
    bundle = await AuthService.login(schema.email, schema.password)
    set_session_cookies(response, bundle.access_token, bundle.refresh_token, bundle.csrf_token)
    return session_response(bundle)


@router.post("/refresh", response_model=SessionResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    csrf_token: str | None = Header(default=None, alias=CSRF_HEADER_NAME),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    bundle = await AuthService.refresh_tokens(refresh_token, csrf_token or "")
    set_session_cookies(response, bundle.access_token, bundle.refresh_token, bundle.csrf_token)
    return session_response(bundle)


@router.get("/csrf", response_model=CsrfResponse)
async def csrf(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    csrf_token = await AuthService.issue_csrf_token(refresh_token)
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return CsrfResponse(csrf_token=csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER_NAME),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
):
    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    if refresh_token:
        await AuthService.validate_refresh_session(refresh_token, csrf_header)
    await AuthService.revoke_session(access_token, refresh_token)
    clear_session_cookies(response)

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    profile = None
    if current_user.role == "patient":
        profile = await UserService.get_patient_profile(str(current_user.id))
    elif current_user.role == "doctor":
        profile = await UserService.get_doctor_profile(str(current_user.id))
        
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "profile": profile
    }
