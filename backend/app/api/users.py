from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Literal, Union
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.doctor import DoctorOut, DoctorProfileUpdate, PublicDoctorOut
from app.schemas.patient import (
    AdminPatientUpdate,
    DoctorPatientOut,
    PatientOut,
    PatientProfileUpdate,
    ReceptionPatientOut,
    ReceptionPatientUpdate,
)
from app.services.user_service import UserService
from app.schemas.auth import StaffCreate, StaffOut
from app.schemas.lab_request import LaboratorianSummary
from app.schemas.doctor_history import AdminPatientHistoryOut, DoctorPatientHistoryOut
from app.services.admin_patient_history_service import AdminPatientHistoryService
from app.services.auth_service import AuthService
from app.services.doctor_history_service import DoctorHistoryService
from app.core.pagination import DEFAULT_PAGE_SIZE, page_window

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/public/doctors", response_model=List[PublicDoctorOut])
async def list_public_doctors(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = Query(default=None, max_length=100),
    home_visits_only: bool = False,
):
    return await UserService.search_public_doctors(
        (search or "").strip(),
        page_window(page, page_size),
        home_visits_only=home_visits_only,
    )


@router.patch("/me/patient-profile", response_model=PatientOut)
async def update_own_patient_profile(
    schema: PatientProfileUpdate,
    current_user = Depends(RoleChecker(["patient"])),
):
    return await UserService.update_patient_profile(str(current_user.id), schema)

@router.post("/staff", status_code=status.HTTP_201_CREATED)
async def create_staff(
    schema: StaffCreate,
    current_user = Depends(RoleChecker(["admin"])),
):
    user = await AuthService.register_staff(schema)
    return {
        "message": "Staff account created",
        "email": user.email,
        "role": user.role,
    }


@router.get("/staff", response_model=List[StaffOut])
async def list_staff(
    current_user = Depends(RoleChecker(["admin"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = Query(default=None, max_length=100),
    role: Literal["doctor", "admin", "receptionist", "laboratorian"] | None = None,
    account_status: Literal["active", "inactive"] | None = None,
):
    return await UserService.list_staff(
        page_window(page, page_size),
        search=(search or "").strip(),
        role=role,
        is_active=(account_status == "active") if account_status else None,
    )


@router.get("/laboratorians", response_model=List[LaboratorianSummary])
async def list_laboratorians(
    current_user = Depends(RoleChecker(["admin"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = Query(default=None, max_length=100),
):
    return await UserService.search_laboratorians(
        (search or "").strip(), page_window(page, page_size),
    )

@router.get("/doctors", response_model=List[DoctorOut])
async def list_doctors(
    current_user = Depends(RoleChecker(["admin"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = Query(default=None, max_length=100),
    home_visits_only: bool = False,
):
    return await UserService.search_doctors(
        (search or "").strip(),
        page_window(page, page_size),
        home_visits_only=home_visits_only,
    )


@router.patch("/doctors/{doctor_id}", response_model=DoctorOut)
async def update_doctor_profile(
    doctor_id: str,
    schema: DoctorProfileUpdate,
    current_user = Depends(RoleChecker(["admin"])),
):
    return await UserService.update_doctor_profile(doctor_id, schema)


@router.get("/reception/doctors", response_model=List[PublicDoctorOut])
async def list_reception_doctors(
    current_user = Depends(RoleChecker(["receptionist"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = Query(default=None, max_length=100),
):
    return await UserService.search_doctors(
        (search or "").strip(), page_window(page, page_size), reception=True,
    )

@router.get("/reception/patients", response_model=List[ReceptionPatientOut])
async def list_reception_patients(
    current_user = Depends(RoleChecker(["receptionist"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = Query(default=None, max_length=100),
):
    return await UserService.search_patients(
        search.strip() if isinstance(search, str) else "",
        page_window(page, page_size),
        reception=True,
    )


@router.patch("/reception/patients/{patient_id}", response_model=ReceptionPatientOut)
async def update_reception_patient(
    patient_id: str,
    schema: ReceptionPatientUpdate,
    current_user = Depends(RoleChecker(["receptionist"])),
):
    return await UserService.update_reception_patient(patient_id, schema)


@router.get("/patients", response_model=List[Union[PatientOut, DoctorPatientOut]])
async def list_patients(
    current_user = Depends(RoleChecker(["admin", "doctor"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    search: str | None = Query(default=None, max_length=100),
):
    window = page_window(page, page_size)
    return await UserService.search_patients(
        search.strip() if isinstance(search, str) else "",
        window,
        doctor_user_id=str(current_user.id) if current_user.role == "doctor" else None,
    )


@router.get("/patients/{patient_id}", response_model=PatientOut)
async def get_admin_patient(
    patient_id: str,
    current_user = Depends(RoleChecker(["admin"])),
):
    return await UserService.get_admin_patient(patient_id)


@router.get("/doctor/patients/{patient_id}", response_model=DoctorPatientOut)
async def get_doctor_patient(
    patient_id: str,
    current_user = Depends(RoleChecker(["doctor"])),
):
    return await UserService.get_doctor_patient(str(current_user.id), patient_id)


@router.patch("/patients/{patient_id}", response_model=PatientOut)
async def update_admin_patient(
    patient_id: str,
    schema: AdminPatientUpdate,
    current_user = Depends(RoleChecker(["admin"])),
):
    return await UserService.update_admin_patient(
        patient_id,
        schema,
        str(current_user.id),
    )


@router.get("/patients/{patient_id}/history", response_model=AdminPatientHistoryOut)
async def get_admin_patient_history(
    patient_id: str,
    current_user = Depends(RoleChecker(["admin"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Invalid history date range")
    window = page_window(page, page_size)
    if start_date or end_date:
        return await AdminPatientHistoryService.get_patient_history(
            patient_id, window, start_date, end_date,
        )
    return await AdminPatientHistoryService.get_patient_history(patient_id, window)


@router.get(
    "/doctor/patients/{patient_id}/history",
    response_model=DoctorPatientHistoryOut,
)
async def get_doctor_patient_history(
    patient_id: str,
    current_user = Depends(RoleChecker(["doctor"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    status_group: str = Query(default="all", pattern="^(all|active|completed|closed)$"),
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Invalid history date range")
    if status_group != "all" or start_date or end_date:
        return await DoctorHistoryService.get_assigned_patient_history(
            str(current_user.id), patient_id, page_window(page, page_size),
            status_group=status_group, start_date=start_date, end_date=end_date,
        )
    return await DoctorHistoryService.get_assigned_patient_history(
        str(current_user.id),
        patient_id,
        page_window(page, page_size),
    )
