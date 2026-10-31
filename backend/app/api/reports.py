import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from app.models.user import User
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.report import ReportResponse, ReportCreate, ReportContentSchema
from app.services.report_service import ReportService
from app.services.clinical_authorization import require_doctor_patient_access
from app.services.clinical_report_storage import ClinicalReportStorage

router = APIRouter(prefix="/reports", tags=["reports"])


def report_response(report) -> ReportResponse:
    return ReportResponse(
        id=str(report.id),
        patient_id=str(report.patient_id),
        booking_id=str(report.booking_id) if report.booking_id else None,
        title=report.title,
        category=report.category,
        date=report.date,
        description=report.description,
        therapist=report.therapist,
        content=ReportContentSchema(**report.content),
        has_file=bool(report.file_path),
        created_at=report.created_at,
    )

@router.get("", response_model=List[ReportResponse])
async def list_reports(
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """List all reports for the authenticated patient."""
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )
    reports = await ReportService.get_reports_by_patient_id(str(patient.id))
    return [report_response(report) for report in reports]

@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_details(
    report_id: str,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """Retrieve details for a single report (owner patient only)."""
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )
    report = await ReportService.get_report_by_id(report_id, str(patient.id))
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or access denied"
        )
    return report_response(report)

@router.get("/{report_id}/download")
async def download_report_file(
    report_id: str,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """Securely stream PDF report file (owner patient only)."""
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )
    report = await ReportService.get_report_by_id(report_id, str(patient.id))
    if not report or not report.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found or access denied"
        )
    try:
        storage_path = ClinicalReportStorage.resolve(report.file_path)
    except (OSError, RuntimeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found or access denied",
        ) from None
    if not storage_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found or access denied",
        )
    return FileResponse(
        path=storage_path,
        media_type="application/pdf",
        filename="clinical-report.pdf",
    )

@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report_by_admin(
    report_data_str: str = Form(...),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Create a new report and optionally upload a PDF file. Admin/doctor only."""
    try:
        report_dict = json.loads(report_data_str)
        report_create = ReportCreate(**report_dict)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report data payload",
        ) from None

    if current_user.role == "doctor":
        try:
            await require_doctor_patient_access(str(current_user.id), report_create.patient_id)
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctor is not authorized to create a report for this patient.",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            ) from exc

    storage_key = None
    if file:
        storage_key = await ClinicalReportStorage.store_pdf(file)

    try:
        report = await ReportService.create_report(
            patient_id=report_create.patient_id,
            booking_id=report_create.booking_id,
            title=report_create.title,
            category=report_create.category,
            date=report_create.date,
            description=report_create.description,
            therapist=report_create.therapist,
            content=report_create.content.model_dump(),
            file_path=storage_key,
        )
    except Exception:
        ClinicalReportStorage.delete(storage_key)
        raise

    return report_response(report)
