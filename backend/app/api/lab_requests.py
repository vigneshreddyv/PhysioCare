from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.middleware.auth import RoleChecker
from app.models.user import User
from app.core.config import settings
from app.schemas.lab_request import (
    LabReportOut,
    LabRequestAssignment,
    LabRequestCreate,
    LabRequestOut,
    LabRequestStatusUpdate,
    LaboratorianLabRequestOut,
)
from app.services.lab_request_service import LabRequestService


router = APIRouter(prefix="/lab-requests", tags=["laboratory requests"])


@router.post("", response_model=LabRequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(
    schema: LabRequestCreate,
    current_user: User = Depends(RoleChecker(["patient"])),
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ] = None,
):
    return await LabRequestService.create(str(current_user.id), schema, idempotency_key)


@router.get("/me", response_model=list[LabRequestOut])
async def list_own(current_user: User = Depends(RoleChecker(["patient"]))):
    return await LabRequestService.list_own(str(current_user.id))


@router.post("/{request_id}/withdraw", response_model=LabRequestOut)
async def withdraw(request_id: str, current_user: User = Depends(RoleChecker(["patient"]))):
    return await LabRequestService.withdraw(request_id, str(current_user.id))


@router.get("/admin", response_model=list[LabRequestOut])
async def list_admin(current_user: User = Depends(RoleChecker(["admin"]))):
    return await LabRequestService.list_admin()


@router.patch("/admin/{request_id}", response_model=LabRequestOut)
async def review(request_id: str, schema: LabRequestStatusUpdate, current_user: User = Depends(RoleChecker(["admin"]))):
    return await LabRequestService.review(request_id, str(current_user.id), schema.status)


@router.patch("/admin/{request_id}/assignment", response_model=LabRequestOut)
async def assign_laboratorian(
    request_id: str,
    schema: LabRequestAssignment,
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await LabRequestService.assign_laboratorian(
        request_id,
        schema.laboratorian_user_id,
        str(current_user.id),
    )


@router.post("/admin/{request_id}/publish-report", response_model=LabRequestOut)
async def publish_report(
    request_id: str,
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await LabRequestService.publish_report(request_id, str(current_user.id))


@router.get("/laboratory/assigned", response_model=list[LaboratorianLabRequestOut])
async def list_assigned_orders(
    current_user: User = Depends(RoleChecker(["laboratorian"])),
):
    return await LabRequestService.list_assigned(str(current_user.id))


@router.put("/laboratory/{request_id}/report", response_model=LaboratorianLabRequestOut)
async def upload_finalized_report(
    request_id: str,
    request: Request,
    report_file_name: Annotated[
        str,
        Header(alias="X-Report-Filename", min_length=5, max_length=160),
    ],
    current_user: User = Depends(RoleChecker(["laboratorian"])),
):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF laboratory reports are accepted")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid report size header") from exc
        if declared_size < 0:
            raise HTTPException(status_code=400, detail="Invalid report size header")
        if declared_size > settings.LAB_REPORT_MAX_BYTES:
            raise HTTPException(status_code=413, detail="The laboratory report is larger than the configured limit")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > settings.LAB_REPORT_MAX_BYTES:
            raise HTTPException(status_code=413, detail="The laboratory report is larger than the configured limit")
        chunks.append(chunk)
    return await LabRequestService.upload_finalized_report(
        request_id,
        str(current_user.id),
        b"".join(chunks),
        report_file_name,
    )


@router.get("/me/reports", response_model=list[LabReportOut])
async def list_released_reports(
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await LabRequestService.list_patient_released_reports(str(current_user.id))


@router.get("/doctor/reports", response_model=list[LabReportOut])
async def list_assigned_patient_reports(
    current_user: User = Depends(RoleChecker(["doctor"])),
):
    return await LabRequestService.list_doctor_released_reports(str(current_user.id))


@router.get("/{request_id}/report-file")
async def download_report(
    request_id: str,
    current_user: User = Depends(RoleChecker(["patient", "doctor", "laboratorian", "admin"])),
):
    path, file_name = await LabRequestService.get_report_file(
        request_id,
        str(current_user.id),
        current_user.role,
    )
    return FileResponse(path, media_type="application/pdf", filename=file_name)
