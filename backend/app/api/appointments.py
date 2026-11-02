from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import date
from typing import List, Union, Literal
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
from app.core.pagination import DEFAULT_PAGE_SIZE, page_window

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
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Invalid schedule date range")
    if start_date or end_date:
        return await AppointmentService.list_reception_schedule(page_window(page, page_size), start_date, end_date)
    return await AppointmentService.list_reception_schedule(page_window(page, page_size))


@router.get("/reception/summary", response_model=dict[str, int])
async def reception_schedule_summary(
    current_user: User = Depends(RoleChecker(["receptionist"])),
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Invalid schedule date range")
    return await AppointmentService.reception_schedule_summary(start_date, end_date)


@router.get("/doctor/summary", response_model=dict[str, int])
async def doctor_dashboard_summary(
    current_user: User = Depends(RoleChecker(["doctor"])),
):
    return await AppointmentService.doctor_dashboard_summary(str(current_user.id))


@router.get("/availability", response_model=AppointmentAvailabilityOut)
async def get_appointment_availability(
    doctor_id: str,
    appointment_date: date,
    current_user: User = Depends(get_current_user),
):
    return await AppointmentService.get_availability(doctor_id, appointment_date)

@router.get("", response_model=List[Union[AppointmentOut, DoctorAppointmentOut]])
async def list_appointments(
    current_user: User = Depends(RoleChecker(["admin", "doctor", "patient"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    status_group: Literal["all", "active", "completed", "closed"] = "all",
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Invalid appointment date range")
    if current_user.role != "doctor" and (status_group != "all" or start_date or end_date):
        raise HTTPException(status_code=422, detail="Doctor filters are not available for this role")
    groups = {"all": None, "active": ["scheduled", "in_progress"],
              "completed": ["completed"], "closed": ["cancelled", "no_show"]}
    if current_user.role == "doctor" and (status_group != "all" or start_date or end_date):
        appointments = await AppointmentService.list_appointments(
            str(current_user.id), current_user.role, page_window(page, page_size),
            statuses=groups[status_group], start_date=start_date, end_date=end_date,
        )
    else:
        appointments = await AppointmentService.list_appointments(
            str(current_user.id), current_user.role, page_window(page, page_size),
        )
    if current_user.role == "doctor":
        return [DoctorAppointmentOut(**appointment.model_dump()) for appointment in appointments]
    return appointments


@router.get("/admin/billing", response_model=List[AppointmentOut])
async def list_admin_billing(
    current_user: User = Depends(RoleChecker(["admin"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    billing_status: str | None = Query(default=None, pattern=r"^[a-z_]{1,32}$"),
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Invalid billing date range")
    return await AppointmentService.list_admin_billing(
        page_window(page, page_size), billing_status, start_date, end_date,
    )


@router.get("/me/home-visits", response_model=List[AppointmentOut])
async def list_patient_home_visits(
    current_user: User = Depends(RoleChecker(["patient"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    return await AppointmentService.list_patient_home_visits(
        str(current_user.id), page_window(page, page_size),
    )


@router.get("/me/history", response_model=List[AppointmentOut])
async def list_patient_appointment_history(
    status_group: Literal["upcoming", "completed", "cancelled"] = "upcoming",
    current_user: User = Depends(RoleChecker(["patient"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    future_only: bool = False,
):
    window = page_window(page, page_size)
    if future_only:
        return await AppointmentService.list_patient_appointment_history(
            str(current_user.id), status_group, window, future_only=True,
        )
    return await AppointmentService.list_patient_appointment_history(
        str(current_user.id), status_group, window,
    )


@router.get("/{appointment_id}", response_model=AppointmentOut)
async def get_patient_appointment(
    appointment_id: str,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await AppointmentService.get_patient_appointment(
        appointment_id, str(current_user.id),
    )


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
