from fastapi import APIRouter, Depends
from typing import List
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.doctor import DoctorOut
from app.schemas.patient import PatientOut, SavedAddressUpdate
from app.services.user_service import UserService
from app.models.user import User

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
    if current_user.role == "doctor":
        return await UserService.list_patients_by_doctor(str(current_user.id))
    return await UserService.list_patients()

@router.put("/me/address", response_model=PatientOut)
async def update_my_address(
    address: SavedAddressUpdate,
    current_user=Depends(RoleChecker(["patient"]))
):
    result = await UserService.update_patient_address(
        str(current_user.id),
        address,
    )

    if not result:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )

    return result

@router.get("/me/address")
async def get_my_address(
    current_user=Depends(RoleChecker(["patient"]))
):
    result = await UserService.get_patient_address(
        str(current_user.id)
    )

    if not result:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved address not found",
        )

    return result


from app.schemas.patient import PatientMonitoringOut

@router.get("/patients/monitoring", response_model=List[PatientMonitoringOut])
async def list_patients_monitoring(
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Retrieve recovery activity and statistics for all caseload patients."""
    return await UserService.list_patients_monitoring(current_user)


from app.schemas.patient import PatientSnapshotOut
from fastapi import HTTPException

@router.get("/patients/{patient_id}/snapshot", response_model=PatientSnapshotOut)
async def get_patient_snapshot(
    patient_id: str,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Retrieve clinical recovery snapshot for a patient. Restricted to doctor caseload."""
    from app.middleware.auth import verify_caseload
    await verify_caseload(patient_id, current_user)
    snapshot = await UserService.get_patient_snapshot(patient_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found or profile incomplete"
        )
    return PatientSnapshotOut(**snapshot)