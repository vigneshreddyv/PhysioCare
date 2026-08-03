from fastapi import APIRouter, Depends, status
from app.models.user import User
from app.middleware.auth import get_current_user
from app.schemas.auth import UserRegister, UserLogin, Token, TokenRefreshRequest
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(schema: UserRegister):
    user = await AuthService.register(schema)
    return {"message": "Registration successful", "email": user.email}

@router.post("/login", response_model=Token)
async def login(schema: UserLogin):
    return await AuthService.login(schema.email, schema.password)

@router.post("/refresh", response_model=Token)
async def refresh(schema: TokenRefreshRequest):
    return await AuthService.refresh_tokens(schema.refresh_token)

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
