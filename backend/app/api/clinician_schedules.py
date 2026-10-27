from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends

from app.middleware.auth import RoleChecker
from app.models.user import User
from app.schemas.appointment import AppointmentAvailabilityOut
from app.schemas.clinician_schedule import ClinicianScheduleOut, ScheduleDraftUpdate, SchedulePublish
from app.services.clinician_schedule_service import ClinicianScheduleService


router = APIRouter(prefix="/clinician-schedules", tags=["clinician schedules"])


@router.get("/admin/{doctor_id}", response_model=ClinicianScheduleOut)
async def get_admin_schedule(doctor_id: str, current_user: User = Depends(RoleChecker(["admin"]))):
    return await ClinicianScheduleService.get_admin(doctor_id)


@router.put("/admin/{doctor_id}/draft", response_model=ClinicianScheduleOut)
async def save_admin_schedule_draft(
    doctor_id: str,
    schema: ScheduleDraftUpdate,
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await ClinicianScheduleService.save_draft(doctor_id, str(current_user.id), schema)


@router.get("/admin/{doctor_id}/preview", response_model=AppointmentAvailabilityOut)
async def preview_admin_schedule(
    doctor_id: str,
    appointment_date: date,
    service_mode: Literal["clinic", "home_visit"],
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await ClinicianScheduleService.preview(doctor_id, appointment_date, service_mode)


@router.post("/admin/{doctor_id}/publish", response_model=ClinicianScheduleOut)
async def publish_admin_schedule(
    doctor_id: str,
    schema: SchedulePublish,
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await ClinicianScheduleService.publish(doctor_id, str(current_user.id), schema.expected_revision)
