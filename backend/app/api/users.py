from fastapi import APIRouter, Depends, status
from typing import List, Union
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

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/public/doctors", response_model=List[PublicDoctorOut])
async def list_public_doctors():
    return await UserService.list_public_doctors()


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
):
    return await UserService.list_staff()


@router.get("/laboratorians", response_model=List[LaboratorianSummary])
async def list_laboratorians(
    current_user = Depends(RoleChecker(["admin"])),
):
    return await UserService.list_laboratorians()

@router.get("/doctors", response_model=List[DoctorOut])
async def list_doctors(
    current_user = Depends(RoleChecker(["admin"]))
):
    return await UserService.list_doctors()


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
):
    return await UserService.list_public_doctors()

@router.get("/reception/patients", response_model=List[ReceptionPatientOut])
async def list_reception_patients(
    current_user = Depends(RoleChecker(["receptionist"])),
):
    return await UserService.list_reception_patients()


@router.patch("/reception/patients/{patient_id}", response_model=ReceptionPatientOut)
async def update_reception_patient(
    patient_id: str,
    schema: ReceptionPatientUpdate,
    current_user = Depends(RoleChecker(["receptionist"])),
):
    return await UserService.update_reception_patient(patient_id, schema)


@router.get("/patients", response_model=List[Union[PatientOut, DoctorPatientOut]])
async def list_patients(
    current_user = Depends(RoleChecker(["admin", "doctor"]))
):
    if current_user.role == "admin":
        return await UserService.list_patients()
    return await UserService.list_assigned_patients(str(current_user.id))


@router.get("/patients/{patient_id}", response_model=PatientOut)
async def get_admin_patient(
    patient_id: str,
    current_user = Depends(RoleChecker(["admin"])),
):
    return await UserService.get_admin_patient(patient_id)


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
):
    return await AdminPatientHistoryService.get_patient_history(patient_id)


@router.get(
    "/doctor/patients/{patient_id}/history",
    response_model=DoctorPatientHistoryOut,
)
async def get_doctor_patient_history(
    patient_id: str,
    current_user = Depends(RoleChecker(["doctor"])),
):
    return await DoctorHistoryService.get_assigned_patient_history(
        str(current_user.id),
        patient_id,
    )
