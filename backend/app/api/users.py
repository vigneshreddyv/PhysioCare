from fastapi import APIRouter, Depends
from typing import List
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.doctor import DoctorOut
from app.schemas.patient import PatientOut
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/doctors", response_model=List[DoctorOut])
async def list_doctors(
    current_user = Depends(get_current_user)
):
    return await UserService.list_doctors()

@router.get("/patients", response_model=List[PatientOut])
async def list_patients(
    current_user = Depends(RoleChecker(["admin", "doctor"]))
):
    return await UserService.list_patients()
