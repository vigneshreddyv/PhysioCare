from fastapi import APIRouter, Depends
from typing import List
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.doctor import DoctorOut
from app.schemas.patient import PatientOut, SavedAddressUpdate
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