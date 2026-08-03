from fastapi import APIRouter, Depends, status
from typing import List
from app.models.user import User
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentOut
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["appointments"])

@router.post("/", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    schema: AppointmentCreate,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    return await AppointmentService.create_appointment(str(current_user.id), schema)

@router.get("/", response_model=List[AppointmentOut])
async def list_appointments(
    current_user: User = Depends(get_current_user)
):
    return await AppointmentService.list_appointments(str(current_user.id), current_user.role)

@router.patch("/{appointment_id}", response_model=AppointmentOut)
async def update_appointment(
    appointment_id: str,
    schema: AppointmentUpdate,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    return await AppointmentService.update_appointment(appointment_id, schema)
