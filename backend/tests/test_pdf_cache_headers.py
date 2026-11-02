"""HTTP-level cache and access contracts for private clinical PDF delivery."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import httpx
import pytest

from app.main import app
from app.middleware.auth import get_current_user
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.report_repository import ReportRepository
from app.services.clinical_report_storage import ClinicalReportStorage, LabReportStorage
from app.services.lab_request_service import LabRequestService
from app.services.report_service import ReportService


PATIENT_A = PydanticObjectId("507f1f77bcf86cd799439011")
PATIENT_B = PydanticObjectId("507f1f77bcf86cd799439012")
REPORT_ID = "507f1f77bcf86cd799439013"
LAB_REQUEST_ID = "507f1f77bcf86cd799439014"
PDF_BYTES = b"%PDF-1.4\nfictional clinical content\n%%EOF\n"
CACHE_CONTROL = "private, no-store, no-cache, must-revalidate"


@pytest.fixture
def pdf_path(tmp_path):
    path = tmp_path / ("a" * 32 + ".pdf")
    path.write_bytes(PDF_BYTES)
    return path


def _as_user(monkeypatch, role="patient"):
    user = SimpleNamespace(id=PATIENT_A, role=role, is_active=True)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: user)
    return user


async def _get(path, **kwargs):
    # ASGITransport does not start the application lifespan or contact MongoDB.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, **kwargs)


def _assert_private_pdf(response, filename):
    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == f'attachment; filename="{filename}"'
    assert response.headers["cache-control"] == CACHE_CONTROL
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    assert response.headers["content-length"] == str(len(PDF_BYTES))
    assert response.headers["accept-ranges"] == "bytes"


def _assert_private_range(response):
    assert response.status_code == 206
    assert response.content == b"%PDF"
    assert response.headers["cache-control"] == CACHE_CONTROL
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"


@pytest.mark.asyncio
async def test_patient_report_download_and_range_are_private(monkeypatch, pdf_path):
    _as_user(monkeypatch)
    monkeypatch.setattr(
        ProfileRepository, "get_patient_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=PATIENT_A)),
    )
    monkeypatch.setattr(
        ReportService, "get_report_by_id",
        AsyncMock(return_value=SimpleNamespace(file_path=pdf_path.name)),
    )
    monkeypatch.setattr(ClinicalReportStorage, "resolve", Mock(return_value=pdf_path))

    url = f"/api/reports/{REPORT_ID}/download"
    _assert_private_pdf(await _get(url), "clinical-report.pdf")
    _assert_private_range(await _get(url, headers={"Range": "bytes=0-3"}))


@pytest.mark.asyncio
async def test_laboratory_pdf_used_by_browser_preview_and_range_is_private(
    monkeypatch, pdf_path,
):
    _as_user(monkeypatch)
    monkeypatch.setattr(
        LabRequestService, "get_report_file",
        AsyncMock(return_value=(pdf_path, "final-lab-report.pdf")),
    )

    url = f"/api/lab-requests/{LAB_REQUEST_ID}/report-file"
    _assert_private_pdf(await _get(url), "final-lab-report.pdf")
    _assert_private_range(await _get(url, headers={"Range": "bytes=0-3"}))


@pytest.mark.asyncio
async def test_admin_laboratory_download_keeps_private_headers(monkeypatch, pdf_path):
    _as_user(monkeypatch, "admin")
    request = SimpleNamespace(
        patient_id=PATIENT_B,
        report_status="released",
        report_storage_key=pdf_path.name,
        report_file_name="admin-reviewed.pdf",
        assigned_laboratorian_user_id=None,
    )
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(LabReportStorage, "resolve", Mock(return_value=pdf_path))

    response = await _get(f"/api/lab-requests/{LAB_REQUEST_ID}/report-file")

    _assert_private_pdf(response, "admin-reviewed.pdf")


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    f"/api/reports/{REPORT_ID}/download",
    f"/api/lab-requests/{LAB_REQUEST_ID}/report-file",
])
async def test_unauthenticated_pdf_requests_return_no_document(monkeypatch, url):
    monkeypatch.delitem(app.dependency_overrides, get_current_user, raising=False)

    response = await _get(url)

    assert response.status_code == 401
    assert PDF_BYTES not in response.content
    assert "content-disposition" not in response.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("url, role", [
    (f"/api/reports/{REPORT_ID}/download", "doctor"),
    (f"/api/lab-requests/{LAB_REQUEST_ID}/report-file", "receptionist"),
])
async def test_wrong_role_cannot_download_pdf(monkeypatch, url, role):
    _as_user(monkeypatch, role)

    response = await _get(url)

    assert response.status_code == 403
    assert PDF_BYTES not in response.content
    assert "content-disposition" not in response.headers


@pytest.mark.asyncio
async def test_patient_cannot_download_other_patients_clinical_report(
    monkeypatch, pdf_path,
):
    _as_user(monkeypatch)
    monkeypatch.setattr(
        ProfileRepository, "get_patient_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=PATIENT_A)),
    )
    monkeypatch.setattr(
        ReportRepository, "get_by_id",
        AsyncMock(return_value=SimpleNamespace(patient_id=PATIENT_B, file_path=pdf_path.name)),
    )
    resolve = Mock()
    monkeypatch.setattr(ClinicalReportStorage, "resolve", resolve)

    response = await _get(f"/api/reports/{REPORT_ID}/download")

    assert response.status_code == 404
    assert PDF_BYTES not in response.content
    assert str(pdf_path) not in response.text
    resolve.assert_not_called()


@pytest.mark.asyncio
async def test_patient_cannot_download_other_patients_laboratory_report(
    monkeypatch, pdf_path,
):
    _as_user(monkeypatch)
    request = SimpleNamespace(
        patient_id=PATIENT_B,
        report_status="released",
        report_storage_key=pdf_path.name,
        assigned_laboratorian_user_id=None,
    )
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(
        ProfileRepository, "get_patient_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=PATIENT_A)),
    )
    resolve = Mock()
    monkeypatch.setattr(LabReportStorage, "resolve", resolve)

    response = await _get(f"/api/lab-requests/{LAB_REQUEST_ID}/report-file")

    assert response.status_code == 404
    assert PDF_BYTES not in response.content
    assert str(pdf_path) not in response.text
    resolve.assert_not_called()


@pytest.mark.asyncio
async def test_unassigned_doctor_cannot_download_laboratory_report(
    monkeypatch, pdf_path,
):
    _as_user(monkeypatch, "doctor")
    request = SimpleNamespace(
        patient_id=PATIENT_B,
        report_status="released",
        report_storage_key=pdf_path.name,
        assigned_laboratorian_user_id=None,
    )
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(
        ProfileRepository, "get_doctor_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=PATIENT_A)),
    )
    monkeypatch.setattr(AppointmentRepository, "has_assigned_patient", AsyncMock(return_value=False))
    resolve = Mock()
    monkeypatch.setattr(LabReportStorage, "resolve", resolve)

    response = await _get(f"/api/lab-requests/{LAB_REQUEST_ID}/report-file")

    assert response.status_code == 404
    assert PDF_BYTES not in response.content
    resolve.assert_not_called()
    AppointmentRepository.has_assigned_patient.assert_awaited_once_with(
        str(PATIENT_A), str(PATIENT_B),
    )
