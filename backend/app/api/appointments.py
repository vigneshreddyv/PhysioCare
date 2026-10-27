from fastapi import APIRouter, Depends, status
from datetime import date
from typing import List, Union
from app.models.user import User
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.appointment import (
    AdminAppointmentCreate,
    AppointmentAvailabilityOut,
    BookingWindowOut,
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentOut,
    DoctorAppointmentOut,
    ReceptionAppointmentCreate,
    ReceptionAppointmentOut,
)
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("/booking-window", response_model=BookingWindowOut)
async def get_booking_window(
    current_user: User = Depends(get_current_user),
):
    return AppointmentService.get_booking_window()

@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    schema: AppointmentCreate,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    return await AppointmentService.create_appointment(str(current_user.id), schema)


@router.post("/admin", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_admin_appointment(
    schema: AdminAppointmentCreate,
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await AppointmentService.create_admin_appointment(schema)


@router.post("/reception", response_model=ReceptionAppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_reception_appointment(
    schema: ReceptionAppointmentCreate,
    current_user: User = Depends(RoleChecker(["receptionist"])),
):
    return await AppointmentService.create_reception_appointment(schema)


@router.get("/reception", response_model=List[ReceptionAppointmentOut])
async def list_reception_schedule(
    current_user: User = Depends(RoleChecker(["receptionist"])),
):
    return await AppointmentService.list_reception_schedule()


@router.get("/availability", response_model=AppointmentAvailabilityOut)
async def get_appointment_availability(
    doctor_id: str,
    appointment_date: date,
    current_user: User = Depends(get_current_user),
):
    return await AppointmentService.get_availability(doctor_id, appointment_date)

@router.get("", response_model=List[Union[AppointmentOut, DoctorAppointmentOut]])
async def list_appointments(
    current_user: User = Depends(RoleChecker(["admin", "doctor", "patient"]))
):
    appointments = await AppointmentService.list_appointments(str(current_user.id), current_user.role)
    if current_user.role == "doctor":
        return [DoctorAppointmentOut(**appointment.model_dump()) for appointment in appointments]
    return appointments


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
async def cancel_appointment(
    appointment_id: str,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await AppointmentService.cancel_patient_appointment(
        appointment_id,
        user_id=str(current_user.id),
    )


@router.post("/reception/{appointment_id}/cancel", response_model=ReceptionAppointmentOut)
async def cancel_reception_appointment(
    appointment_id: str,
    current_user: User = Depends(RoleChecker(["receptionist"])),
):
    return await AppointmentService.cancel_reception_appointment(appointment_id)

@router.patch("/{appointment_id}", response_model=Union[AppointmentOut, DoctorAppointmentOut])
async def update_appointment(
    appointment_id: str,
    schema: AppointmentUpdate,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    appointment = await AppointmentService.update_appointment(
        appointment_id,
        schema,
        actor_user_id=str(current_user.id),
        actor_role=current_user.role,
    )
    if current_user.role == "doctor":
        return DoctorAppointmentOut(**appointment.model_dump())
    return appointment
