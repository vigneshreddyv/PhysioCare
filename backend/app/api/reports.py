import os
import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from app.models.user import User
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.report import ReportResponse, ReportCreate, ReportContentSchema
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

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
    return [
        ReportResponse(
            id=str(r.id),
            patient_id=str(r.patient_id),
            booking_id=str(r.booking_id) if r.booking_id else None,
            title=r.title,
            category=r.category,
            date=r.date,
            description=r.description,
            therapist=r.therapist,
            content=ReportContentSchema(**r.content),
            file_path=r.file_path,
            created_at=r.created_at
        ) for r in reports
    ]

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
        file_path=report.file_path,
        created_at=report.created_at
    )

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
    if not os.path.exists(report.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical report file not found on disk"
        )
    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        filename=os.path.basename(report.file_path)
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON data payload: {e}"
        )

    file_path = None
    if file:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF attachments are allowed"
            )
        filename = f"rpt_{os.urandom(8).hex()}.pdf"
        file_path = os.path.join(REPORTS_DIR, filename)
        try:
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to write file to storage: {e}"
            )

    report = await ReportService.create_report(
        patient_id=report_create.patient_id,
        booking_id=report_create.booking_id,
        title=report_create.title,
        category=report_create.category,
        date=report_create.date,
        description=report_create.description,
        therapist=report_create.therapist,
        content=report_create.content.model_dump(),
        file_path=file_path
    )

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
        file_path=report.file_path,
        created_at=report.created_at
    )
