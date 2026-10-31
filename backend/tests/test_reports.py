import json
import os
from io import BytesIO
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from beanie import PydanticObjectId
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from types import SimpleNamespace
from app.api.reports import create_report_by_admin
from app.models.report import Report
from app.services.report_service import ReportService
from app.repositories.report_repository import ReportRepository
from app.core.config import settings


@pytest.mark.asyncio
async def test_report_model_creation():
    report_data = {
        "patient_id": "000000000000000000000000",
        "booking_id": "111111111111111111111111",
        "title": "Lab Fluid Diagnostic Panel",
        "category": "diagnostic",
        "date": datetime.utcnow(),
        "description": "Diagnostic serum panel.",
        "therapist": "PhysioCare Diagnostic Labs",
        "content": {"symptoms": "Swelling", "findings": "Uric acid 5.4", "recommendations": "None"},
        "file_path": "/static/reports/rpt_1.pdf"
    }
    report = Report.model_validate(report_data)
    assert report.title == "Lab Fluid Diagnostic Panel"
    assert report.category == "diagnostic"
    assert report.file_path == "/static/reports/rpt_1.pdf"
    assert report.content["symptoms"] == "Swelling"


@pytest.mark.asyncio
async def test_create_report_service():
    mock_report = MagicMock()
    mock_report.id = "report123"
    mock_report.patient_id = "000000000000000000000000"
    with patch("app.services.report_service.ReportRepository.create") as mock_create, \
         patch("app.models.patient.Patient.get") as mock_patient_get, \
         patch("app.services.laboratory_service.LaboratoryService.update_booking_status") as mock_update_status:

        mock_create.return_value = mock_report
        mock_patient_get.return_value = None
        mock_update_status.return_value = MagicMock()

        res = await ReportService.create_report(
            patient_id="000000000000000000000000",
            booking_id="111111111111111111111111",
            title="Lab Fluid Diagnostic Panel",
            category="diagnostic",
            date=datetime.utcnow(),
            description="Diagnostic panel",
            therapist="PhysioCare Labs",
            content={"symptoms": "Swelling", "findings": "Normal", "recommendations": "None"},
            file_path="/static/reports/rpt_1.pdf"
        )

        assert res.id == "report123"
        # Verify lab booking status was auto-transitioned to completed on diagnostic upload
        mock_update_status.assert_called_once_with("111111111111111111111111", "completed")


@pytest.mark.asyncio
async def test_get_reports_by_patient_id():
    mock_reports = [MagicMock(), MagicMock()]
    with patch("app.services.report_service.ReportRepository.get_by_patient_id") as mock_get_patient:
        mock_get_patient.return_value = mock_reports
        res = await ReportService.get_reports_by_patient_id("patient123")
        assert len(res) == 2


@pytest.mark.asyncio
async def test_get_report_by_id_owner_success():
    mock_report = MagicMock()
    mock_report.patient_id = "000000000000000000000000"
    with patch("app.services.report_service.ReportRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_report
        res = await ReportService.get_report_by_id("report123", "000000000000000000000000")
        assert res is not None


@pytest.mark.asyncio
async def test_get_report_by_id_idor_failure():
    mock_report = MagicMock()
    mock_report.patient_id = "000000000000000000000000"
    with patch("app.services.report_service.ReportRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_report
        res = await ReportService.get_report_by_id("report123", "999999999999999999999999")
        assert res is None


def _report_payload():
    return {
        "patient_id": "000000000000000000000000",
        "title": "Initial mobility assessment",
        "category": "assessment",
        "date": "2026-11-01T12:00:00Z",
        "description": "Initial clinical assessment.",
        "therapist": "Dr. Assigned",
        "content": {
            "symptoms": "Knee pain",
            "findings": "Reduced flexion",
            "recommendations": "Continue guided mobility exercises",
        },
    }


def _upload(content, *, content_type="application/pdf", name="report.pdf"):
    return UploadFile(
        BytesIO(content),
        size=len(content),
        filename=name,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_doctor_report_creation_requires_assigned_patient_access():
    doctor = SimpleNamespace(role="doctor", id="doctor-user")
    with patch("app.api.reports.require_doctor_patient_access", new=AsyncMock(side_effect=PermissionError)), \
         patch("app.api.reports.ReportService.create_report", new=AsyncMock()) as mock_create:
        with pytest.raises(HTTPException) as error:
            await create_report_by_admin(
                report_data_str=json.dumps(_report_payload()),
                file=None,
                current_user=doctor,
            )

    assert error.value.status_code == 403
    mock_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_report_creation_returns_created_report():
    patient_id = PydanticObjectId("000000000000000000000000")
    created = SimpleNamespace(
        id="report123",
        patient_id=patient_id,
        booking_id=None,
        title="Initial mobility assessment",
        category="assessment",
        date=datetime(2026, 11, 1, 12, 0),
        description="Initial clinical assessment.",
        therapist="Dr. Assigned",
        content={
            "symptoms": "Knee pain",
            "findings": "Reduced flexion",
            "recommendations": "Continue guided mobility exercises",
        },
        file_path=None,
        created_at=datetime(2026, 11, 1, 12, 1),
    )
    admin = SimpleNamespace(role="admin", id="admin-user")
    with patch("app.api.reports.ReportService.create_report", new=AsyncMock(return_value=created)) as mock_create:
        response = await create_report_by_admin(
            report_data_str=json.dumps(_report_payload()),
            file=None,
            current_user=admin,
        )

    assert response.id == "report123"
    assert response.patient_id == str(patient_id)
    assert response.has_file is False
    assert "file_path" not in response.model_dump()
    mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_clinical_report_upload_is_private_bounded_and_opaque(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)
    patient_id = PydanticObjectId("000000000000000000000000")

    async def create_report(**values):
        return SimpleNamespace(
            id="report123",
            patient_id=patient_id,
            booking_id=None,
            title=values["title"],
            category=values["category"],
            date=values["date"],
            description=values["description"],
            therapist=values["therapist"],
            content=values["content"],
            file_path=values["file_path"],
            created_at=datetime(2026, 11, 1, 12, 1),
        )

    admin = SimpleNamespace(role="admin", id="admin-user")
    with patch(
        "app.api.reports.ReportService.create_report",
        new=AsyncMock(side_effect=create_report),
    ) as mock_create:
        response = await create_report_by_admin(
            report_data_str=json.dumps(_report_payload()),
            file=_upload(b"%PDF-1.4 fictional report"),
            current_user=admin,
        )

    storage_key = mock_create.await_args.kwargs["file_path"]
    stored_path = tmp_path / storage_key
    assert response.has_file is True
    assert "file_path" not in response.model_dump()
    assert storage_key == os.path.basename(storage_key)
    assert stored_path.read_bytes() == b"%PDF-1.4 fictional report"
    assert os.stat(stored_path).st_mode & 0o777 == 0o600
    assert os.stat(tmp_path).st_mode & 0o777 == 0o700


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("upload", "expected_status"),
    [
        (_upload(b"not a pdf"), 422),
        (_upload(b"%PDF-1.4", content_type="text/plain"), 415),
        (_upload(b"%PDF-1.4", name="report.txt"), 415),
    ],
)
async def test_clinical_report_upload_rejects_invalid_files_before_database(
    monkeypatch,
    tmp_path,
    upload,
    expected_status,
):
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)
    create = AsyncMock()
    monkeypatch.setattr("app.api.reports.ReportService.create_report", create)

    with pytest.raises(HTTPException) as error:
        await create_report_by_admin(
            report_data_str=json.dumps(_report_payload()),
            file=upload,
            current_user=SimpleNamespace(role="admin", id="admin-user"),
        )

    assert error.value.status_code == expected_status
    create.assert_not_awaited()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_clinical_report_upload_enforces_stream_size_and_removes_partial_file(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 16)
    upload = _upload(b"%PDF-" + b"x" * 20)
    upload.size = None

    with pytest.raises(HTTPException) as error:
        await create_report_by_admin(
            report_data_str=json.dumps(_report_payload()),
            file=upload,
            current_user=SimpleNamespace(role="admin", id="admin-user"),
        )

    assert error.value.status_code == 413
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_report_database_failure_removes_new_attachment(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)
    monkeypatch.setattr(
        "app.api.reports.ReportService.create_report",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await create_report_by_admin(
            report_data_str=json.dumps(_report_payload()),
            file=_upload(b"%PDF-1.4 fictional report"),
            current_user=SimpleNamespace(role="admin", id="admin-user"),
        )

    assert list(tmp_path.iterdir()) == []
