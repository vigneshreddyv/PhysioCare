import asyncio
import json
import logging
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
from app.core.time import utc_now
from app.models.report import Report
from app.services.report_service import (
    ReportBookingConflict,
    ReportService,
    ReportTargetUnavailable,
)
from app.repositories.report_repository import ReportRepository
from app.repositories.report_repository import BookingClaimFailed
from app.core.config import settings
from app.services.clinical_report_storage import ClinicalReportStorage
from app.services.pdf_malware_scanner import (
    DeterministicTestPdfScanner,
    ScanResult,
    ScanVerdict,
    UnavailablePdfMalwareScanner,
)


VALID_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def approved_test_scanner(monkeypatch, tmp_path):
    monkeypatch.setattr(
        settings,
        "CLINICAL_REPORT_QUARANTINE_DIR",
        str(tmp_path.parent / f"{tmp_path.name}-quarantine"),
    )
    monkeypatch.setattr(
        ClinicalReportStorage,
        "scanner",
        DeterministicTestPdfScanner(ScanVerdict.CLEAN),
    )


@pytest.mark.asyncio
async def test_report_model_creation():
    report_data = {
        "patient_id": "000000000000000000000000",
        "booking_id": "111111111111111111111111",
        "title": "Lab Fluid Diagnostic Panel",
        "category": "diagnostic",
        "date": utc_now(),
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
    booking = SimpleNamespace(
        patient_id=PydanticObjectId("000000000000000000000000"),
        status="confirmed",
    )
    with patch("app.services.report_service.ReportRepository.create_for_confirmed_booking") as mock_create, \
         patch("app.models.patient.Patient.get") as mock_patient_get, \
         patch("app.services.report_service.LaboratoryBookingRepository.get_by_id", new=AsyncMock(return_value=booking)), \
         patch("app.services.laboratory_service.LaboratoryService.notify_booking_status", new=AsyncMock()) as mock_notify:

        mock_create.return_value = mock_report
        mock_patient_get.return_value = MagicMock()

        res = await ReportService.create_report(
            patient_id="000000000000000000000000",
            booking_id="111111111111111111111111",
            title="Lab Fluid Diagnostic Panel",
            category="diagnostic",
            date=utc_now(),
            description="Diagnostic panel",
            therapist="PhysioCare Labs",
            content={"symptoms": "Swelling", "findings": "Normal", "recommendations": "None"},
            file_path="/static/reports/rpt_1.pdf",
            actor_user_id="admin-user",
            actor_role="admin",
        )

        assert res.id == "report123"
        # Verify lab booking status was auto-transitioned to completed on diagnostic upload
        mock_create.assert_awaited_once()
        assert str(mock_create.await_args.args[0].booking_id) == "111111111111111111111111"
        mock_notify.assert_awaited_once()


def _diagnostic_service_values(**overrides):
    values = {
        "patient_id": "000000000000000000000000",
        "booking_id": "111111111111111111111111",
        "title": "Diagnostic report",
        "category": "diagnostic",
        "date": utc_now(),
        "description": "Fictional diagnostic result",
        "therapist": "Assigned clinician",
        "content": {"symptoms": "None", "findings": "Normal", "recommendations": "None"},
        "actor_user_id": "doctor-user",
        "actor_role": "doctor",
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_doctor_cannot_link_another_patients_booking():
    authorize = AsyncMock(return_value=MagicMock())
    booking = SimpleNamespace(
        patient_id=PydanticObjectId("222222222222222222222222"),
        status="confirmed",
    )
    create = AsyncMock()
    create_booked = AsyncMock()
    with patch("app.services.report_service.require_doctor_patient_access", authorize), \
         patch("app.services.report_service.LaboratoryBookingRepository.get_by_id", AsyncMock(return_value=booking)), \
         patch("app.services.report_service.ReportRepository.create_for_confirmed_booking", create_booked), \
         patch("app.services.report_service.ReportRepository.create", create):
        with pytest.raises(ReportTargetUnavailable):
            await ReportService.create_report(**_diagnostic_service_values())

    create.assert_not_awaited()
    create_booked.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_rejects_missing_patient_before_booking_lookup():
    booking_lookup = AsyncMock()
    with patch("app.services.report_service.Patient.get", AsyncMock(return_value=None)), \
         patch("app.services.report_service.LaboratoryBookingRepository.get_by_id", booking_lookup):
        with pytest.raises(ReportTargetUnavailable):
            await ReportService.create_report(
                **_diagnostic_service_values(actor_user_id="admin-user", actor_role="admin")
            )

    booking_lookup.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("booking_id", ["333333333333333333333333", "not-an-object-id"])
async def test_report_rejects_nonexistent_or_malformed_booking(booking_id):
    create = AsyncMock()
    booking_lookup = (
        AsyncMock(return_value=None)
        if booking_id.startswith("3")
        else AsyncMock(side_effect=ValueError("malformed object id"))
    )
    with patch("app.services.report_service.Patient.get", AsyncMock(return_value=MagicMock())), \
         patch("app.services.report_service.LaboratoryBookingRepository.get_by_id", booking_lookup), \
         patch("app.services.report_service.ReportRepository.create", create):
        with pytest.raises(ReportTargetUnavailable):
            await ReportService.create_report(
                **_diagnostic_service_values(
                    booking_id=booking_id,
                    actor_user_id="admin-user",
                    actor_role="admin",
                )
            )

    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_unauthorized_doctor_cannot_create_report_or_touch_booking():
    booking_lookup = AsyncMock()
    create_booked = AsyncMock()
    create = AsyncMock()
    with patch(
        "app.services.report_service.require_doctor_patient_access",
        AsyncMock(side_effect=PermissionError("not assigned")),
    ), patch(
        "app.services.report_service.LaboratoryBookingRepository.get_by_id",
        booking_lookup,
    ), patch(
        "app.services.report_service.ReportRepository.create_for_confirmed_booking",
        create_booked,
    ), patch("app.services.report_service.ReportRepository.create", create):
        with pytest.raises(ReportTargetUnavailable):
            await ReportService.create_report(**_diagnostic_service_values())

    booking_lookup.assert_not_awaited()
    create_booked.assert_not_awaited()
    create.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("booking_status", ["pending_payment", "completed", "cancelled", "failed"])
async def test_report_rejects_booking_in_invalid_state(booking_status):
    booking = SimpleNamespace(
        patient_id=PydanticObjectId("000000000000000000000000"),
        status=booking_status,
    )
    create_booked = AsyncMock()
    create = AsyncMock()
    with patch("app.services.report_service.Patient.get", AsyncMock(return_value=MagicMock())), \
         patch("app.services.report_service.LaboratoryBookingRepository.get_by_id", AsyncMock(return_value=booking)), \
         patch("app.services.report_service.ReportRepository.create_for_confirmed_booking", create_booked), \
         patch("app.services.report_service.ReportRepository.create", create):
        with pytest.raises(ReportBookingConflict):
            await ReportService.create_report(
                **_diagnostic_service_values(actor_user_id="admin-user", actor_role="admin")
            )

    create_booked.assert_not_awaited()
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_booking_transition_prevents_report_insert():
    booking = SimpleNamespace(
        patient_id=PydanticObjectId("000000000000000000000000"),
        status="confirmed",
    )
    create = AsyncMock()
    with patch("app.services.report_service.Patient.get", AsyncMock(return_value=MagicMock())), \
         patch("app.services.report_service.LaboratoryBookingRepository.get_by_id", AsyncMock(return_value=booking)), \
         patch("app.services.report_service.ReportRepository.create_for_confirmed_booking", AsyncMock(side_effect=BookingClaimFailed)), \
         patch("app.services.report_service.ReportRepository.create", create):
        with pytest.raises(ReportBookingConflict):
            await ReportService.create_report(
                **_diagnostic_service_values(actor_user_id="admin-user", actor_role="admin")
            )

    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_transaction_failure_does_not_emit_completion():
    booking = SimpleNamespace(
        patient_id=PydanticObjectId("000000000000000000000000"),
        status="confirmed",
    )
    notify = AsyncMock()
    with patch("app.services.report_service.Patient.get", AsyncMock(return_value=MagicMock())), \
         patch("app.services.report_service.LaboratoryBookingRepository.get_by_id", AsyncMock(return_value=booking)), \
         patch("app.services.report_service.ReportRepository.create_for_confirmed_booking", AsyncMock(side_effect=RuntimeError("write failed"))), \
         patch("app.services.laboratory_service.LaboratoryService.notify_booking_status", notify):
        with pytest.raises(RuntimeError, match="write failed"):
            await ReportService.create_report(
                **_diagnostic_service_values(actor_user_id="admin-user", actor_role="admin")
            )

    assert booking.status == "confirmed"
    notify.assert_not_awaited()


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
    with patch("app.api.reports.ReportService.validate_create_request", new=AsyncMock(side_effect=ReportTargetUnavailable)), \
         patch("app.api.reports.ReportService.create_report", new=AsyncMock()) as mock_create:
        with pytest.raises(HTTPException) as error:
            await create_report_by_admin(
                report_data_str=json.dumps(_report_payload()),
                file=None,
                current_user=doctor,
            )

    assert error.value.status_code == 404
    mock_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_doctor_report_creation_does_not_hide_authorization_infrastructure_errors():
    doctor = SimpleNamespace(role="doctor", id="doctor-user")
    with patch(
        "app.api.reports.ReportService.validate_create_request",
        new=AsyncMock(side_effect=RuntimeError("authorization database unavailable")),
    ):
        with pytest.raises(RuntimeError, match="authorization database unavailable"):
            await create_report_by_admin(
                report_data_str=json.dumps(_report_payload()),
                file=None,
                current_user=doctor,
            )


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
            file=_upload(VALID_PDF),
            current_user=admin,
        )

    storage_key = mock_create.await_args.kwargs["file_path"]
    stored_path = tmp_path / storage_key
    assert response.has_file is True
    assert "file_path" not in response.model_dump()
    assert storage_key == os.path.basename(storage_key)
    assert stored_path.read_bytes() == VALID_PDF
    assert os.stat(stored_path).st_mode & 0o777 == 0o600
    assert os.stat(tmp_path).st_mode & 0o777 == 0o700


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("upload", "expected_status"),
    [
        (_upload(b"not a pdf"), 422),
        (_upload(VALID_PDF, content_type="text/plain"), 415),
        (_upload(VALID_PDF, name="report.txt"), 415),
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
async def test_report_database_failure_defers_attachment_cleanup_until_reference_check(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)
    monkeypatch.setattr(
        "app.api.reports.ReportService.create_report",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await create_report_by_admin(
            report_data_str=json.dumps(_report_payload()),
            file=_upload(VALID_PDF),
            current_user=SimpleNamespace(role="admin", id="admin-user"),
        )

    retained_files = list(tmp_path.glob("*.pdf"))
    assert len(retained_files) == 1
    assert os.stat(retained_files[0]).st_mode & 0o777 == 0o600
    assert ClinicalReportStorage.pending_cleanup_inventory()[0][0] == retained_files[0].name

    unreferenced = AsyncMock(return_value=False)
    counts = await ClinicalReportStorage.reconcile_pending_cleanup(
        unreferenced, min_age_seconds=0
    )
    assert counts["removed"] == 1
    unreferenced.assert_awaited_once_with(retained_files[0].name)
    assert list(tmp_path.glob("*.pdf")) == []


@pytest.mark.asyncio
async def test_clinical_report_quarantine_fails_closed_without_scanner(
    monkeypatch,
    tmp_path,
):
    approved = tmp_path / "approved"
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(approved))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_QUARANTINE_DIR", str(quarantine))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)
    monkeypatch.setattr(
        ClinicalReportStorage,
        "scanner",
        UnavailablePdfMalwareScanner(),
    )

    with pytest.raises(HTTPException) as error:
        await ClinicalReportStorage.store_pdf(
            _upload(VALID_PDF),
            uploaded_by_user_id="fictional-uploader",
        )

    assert error.value.status_code == 503
    assert list(approved.glob("*.pdf")) == []
    assert list(quarantine.glob("*.pdf")) == []
    audits = list(quarantine.glob("*.audit.json"))
    assert len(audits) == 1
    audit = json.loads(audits[0].read_text(encoding="utf-8"))
    assert audit["state"] == "Rejected"
    assert [event["state"] for event in audit["events"]] == [
        "Uploaded",
        "Quarantined",
        "Scanning",
        "Rejected",
    ]
    assert audit["events"][-1]["reason_code"] == "scanner_unavailable"


@pytest.mark.asyncio
async def test_clinical_report_quarantine_times_out_and_removes_content(
    monkeypatch,
    tmp_path,
):
    approved = tmp_path / "approved"
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(approved))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_QUARANTINE_DIR", str(quarantine))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)
    monkeypatch.setattr(settings, "PDF_SCAN_TIMEOUT_SECONDS", 0.01)

    class SlowScanner:
        async def scan(self, _path):
            await asyncio.sleep(1)
            return ScanResult(ScanVerdict.CLEAN, "slow-test", "clean")

    monkeypatch.setattr(ClinicalReportStorage, "scanner", SlowScanner())

    with pytest.raises(HTTPException) as error:
        await ClinicalReportStorage.store_pdf(
            _upload(VALID_PDF),
            uploaded_by_user_id="fictional-uploader",
        )

    assert error.value.status_code == 503
    assert list(approved.glob("*.pdf")) == []
    assert list(quarantine.glob("*.pdf")) == []
    audit = json.loads(next(quarantine.glob("*.audit.json")).read_text(encoding="utf-8"))
    assert audit["events"][-1]["reason_code"] == "scanner_timeout"


@pytest.mark.asyncio
async def test_clinical_report_quarantine_rejects_invalid_scanner_result(
    monkeypatch,
    tmp_path,
):
    approved = tmp_path / "approved"
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(approved))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_QUARANTINE_DIR", str(quarantine))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)

    class InvalidScanner:
        async def scan(self, _path):
            return {"verdict": "clean"}

    monkeypatch.setattr(ClinicalReportStorage, "scanner", InvalidScanner())

    with pytest.raises(HTTPException) as error:
        await ClinicalReportStorage.store_pdf(
            _upload(VALID_PDF),
            uploaded_by_user_id="fictional-uploader",
        )

    assert error.value.status_code == 503
    assert list(approved.glob("*.pdf")) == []
    assert list(quarantine.glob("*.pdf")) == []
    audit = json.loads(next(quarantine.glob("*.audit.json")).read_text(encoding="utf-8"))
    assert audit["events"][-1]["reason_code"] == "invalid_scanner_result"


def test_approved_and_quarantine_roots_must_not_overlap(monkeypatch, tmp_path):
    approved = tmp_path / "approved"
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(approved))

    for unsafe_quarantine in (approved, approved / "nested-quarantine"):
        monkeypatch.setattr(
            settings,
            "CLINICAL_REPORT_QUARANTINE_DIR",
            str(unsafe_quarantine),
        )
        with pytest.raises(RuntimeError, match="separate from approved storage"):
            ClinicalReportStorage._quarantine_root()


@pytest.mark.asyncio
async def test_malicious_pdf_is_rejected_and_never_promoted(monkeypatch, tmp_path):
    approved = tmp_path / "approved"
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(approved))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_QUARANTINE_DIR", str(quarantine))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)
    monkeypatch.setattr(
        ClinicalReportStorage,
        "scanner",
        DeterministicTestPdfScanner(ScanVerdict.MALICIOUS),
    )

    with pytest.raises(HTTPException) as error:
        await ClinicalReportStorage.store_pdf(
            _upload(VALID_PDF),
            uploaded_by_user_id="fictional-uploader",
        )

    assert error.value.status_code == 422
    assert list(approved.glob("*.pdf")) == []
    assert list(quarantine.glob("*.pdf")) == []


@pytest.mark.asyncio
async def test_quarantined_pdf_is_inaccessible_until_scanner_approval(
    monkeypatch,
    tmp_path,
):
    approved = tmp_path / "approved"
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(approved))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_QUARANTINE_DIR", str(quarantine))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)

    class InspectingScanner:
        async def scan(self, path):
            assert path.parent == quarantine.resolve()
            assert path.is_file()
            assert not (approved.resolve() / path.name).is_file()
            return ScanResult(ScanVerdict.CLEAN, "test-inspector", "clean")

    monkeypatch.setattr(ClinicalReportStorage, "scanner", InspectingScanner())
    storage_key = await ClinicalReportStorage.store_pdf(
        _upload(VALID_PDF),
        uploaded_by_user_id="fictional-uploader",
    )

    assert ClinicalReportStorage.resolve(storage_key).is_file()
    audit = json.loads(
        (quarantine / f"{storage_key}.audit.json").read_text(encoding="utf-8")
    )
    assert [event["state"] for event in audit["events"]] == [
        "Uploaded",
        "Quarantined",
        "Scanning",
        "Approved",
    ]
    assert audit["uploaded_by_user_id"] == "fictional-uploader"


@pytest.mark.asyncio
async def test_approved_file_is_removed_when_final_audit_write_fails(
    monkeypatch,
    tmp_path,
):
    approved = tmp_path / "approved"
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(approved))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_QUARANTINE_DIR", str(quarantine))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_MAX_BYTES", 1024)
    original_audit = ClinicalReportStorage._audit

    def failing_final_audit(storage_key, state, **values):
        if state == "Approved":
            raise OSError("audit storage unavailable")
        return original_audit(storage_key, state, **values)

    monkeypatch.setattr(ClinicalReportStorage, "_audit", failing_final_audit)

    with pytest.raises(OSError, match="audit storage unavailable"):
        await ClinicalReportStorage.store_pdf(
            _upload(VALID_PDF),
            uploaded_by_user_id="fictional-uploader",
        )

    assert list(approved.glob("*.pdf")) == []
    assert list(quarantine.glob("*.pdf")) == []


@pytest.mark.asyncio
async def test_scanner_audit_metadata_is_bounded_and_normalized(monkeypatch, tmp_path):
    approved = tmp_path / "approved"
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "CLINICAL_REPORT_STORAGE_DIR", str(approved))
    monkeypatch.setattr(settings, "CLINICAL_REPORT_QUARANTINE_DIR", str(quarantine))

    class UnsafeMetadataScanner:
        async def scan(self, _path):
            return ScanResult(
                ScanVerdict.CLEAN,
                "engine\n/raw/private/path patient@example.test",
                "x" * 500,
            )

    monkeypatch.setattr(ClinicalReportStorage, "scanner", UnsafeMetadataScanner())
    storage_key = await ClinicalReportStorage.store_pdf(
        _upload(VALID_PDF),
        uploaded_by_user_id="fictional-uploader",
    )

    audit = json.loads(
        (quarantine / f"{storage_key}.audit.json").read_text(encoding="utf-8")
    )
    approved_event = audit["events"][-1]
    assert approved_event["scanner_engine"] == "scanner_engine_unavailable"
    assert approved_event["reason_code"] == "scanner_reason_unavailable"
    assert "patient@example.test" not in json.dumps(audit)


def test_cleanup_failure_is_logged_without_storage_key_or_path(caplog):
    secret_key = "secret-patient-identifier.pdf"
    with patch.object(
        ClinicalReportStorage,
        "resolve",
        side_effect=OSError("/private/clinical/path"),
    ), caplog.at_level(logging.WARNING):
        ClinicalReportStorage.delete(secret_key)

    assert "Report attachment cleanup failed" in caplog.text
    assert secret_key not in caplog.text
    assert "/private/clinical/path" not in caplog.text
