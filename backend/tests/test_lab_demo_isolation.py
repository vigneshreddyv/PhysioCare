import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.core.config import (
    LAB_DEMO_DATABASE_NAME,
    LAB_DEMO_MONGODB_URL,
    Settings,
    lab_demo_home,
    settings,
)
from app.lab_demo import _is_known_sample_pdf, _legacy_sample_pdf_bytes, sample_pdf_bytes
from app.core.lab_demo import LAB_DEMO_REHEARSAL_TAG
from app.core.lab_demo_storage import report_file_path
from app.database import init_db
from app.main import app
from app.repositories.profile_repository import ProfileRepository
from app.schemas.lab_request import LabRequestCreate
from app.services.auth_service import AuthService
from app.services.lab_request_service import LabRequestService


def _demo_settings(monkeypatch, tmp_path, **overrides):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    values = {
        "MONGODB_URL": LAB_DEMO_MONGODB_URL,
        "DATABASE_NAME": LAB_DEMO_DATABASE_NAME,
        "LAB_DEMO_MODE": True,
        "JWT_SECRET": "access-secret-" + "a" * 40,
        "JWT_REFRESH_SECRET": "refresh-secret-" + "b" * 40,
        "ENVIRONMENT": "development",
        "HOST": "127.0.0.1",
        "PORT": 8001,
        "RAZORPAY_MODE": "disabled",
        "PAYMENT_RECONCILIATION_ENABLED": False,
        "LAB_REPORT_STORAGE_DIR": str(tmp_path / "PhysioCareLabDemo" / "lab-reports"),
        "CORS_ORIGINS": ["http://127.0.0.1:5175"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_demo_settings_accept_only_the_dedicated_loopback_configuration(monkeypatch, tmp_path):
    configured = _demo_settings(monkeypatch, tmp_path)

    assert configured.DATABASE_NAME == "physiocare_lab_demo"
    assert configured.MONGODB_URL == "mongodb://127.0.0.1:27018"
    configured.validate_lab_demo_isolation()


@pytest.mark.parametrize(
    "override",
    [
        {"DATABASE_NAME": "physiocare"},
        {"MONGODB_URL": "mongodb://localhost:27017"},
        {"HOST": "0.0.0.0"},
        {"PORT": 8000},
        {"ENVIRONMENT": "production"},
        {"RAZORPAY_MODE": "live"},
        {"RAZORPAY_KEY_SECRET": "not-allowed"},
        {"PAYMENT_RECONCILIATION_ENABLED": True},
        {"CORS_ORIGINS": ["http://localhost:5173"]},
        {"LAB_REPORT_STORAGE_DIR": "uploads/lab-reports"},
    ],
)
def test_demo_settings_reject_database_network_payment_or_storage_drift(
    monkeypatch, tmp_path, override
):
    with pytest.raises(ValidationError):
        _demo_settings(monkeypatch, tmp_path, **override)


def test_selected_demo_environment_file_requires_demo_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv(
        "PHYSIOCARE_ENV_FILE",
        str(lab_demo_home() / ".env"),
    )
    with pytest.raises(ValidationError, match="requires LAB_DEMO_MODE=true"):
        Settings(
            _env_file=None,
            JWT_SECRET="access-secret-" + "a" * 40,
            JWT_REFRESH_SECRET="refresh-secret-" + "b" * 40,
        )


def test_database_guard_runs_before_constructing_a_mongo_client(monkeypatch):
    guard = Mock()
    guard.validate_lab_demo_isolation.side_effect = ValueError("unsafe target")
    client_constructor = Mock()
    monkeypatch.setattr("app.database.settings", guard)
    monkeypatch.setattr("app.database.BeanieCompatibleMotorClient", client_constructor)

    with pytest.raises(ValueError, match="unsafe target"):
        asyncio.run(init_db())

    client_constructor.assert_not_called()


def test_storage_key_rejects_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "LAB_REPORT_STORAGE_DIR", str(tmp_path))

    for key in ("../outside.pdf", "..\\outside.pdf", "folder/report.pdf", ""):
        with pytest.raises(ValueError):
            report_file_path(key)


def test_generated_sample_is_a_self_contained_pdf():
    sample = sample_pdf_bytes()
    pdf_text = sample.replace(b"\\(", b"(").replace(b"\\)", b")")

    assert _is_known_sample_pdf(sample)
    assert _is_known_sample_pdf(_legacy_sample_pdf_bytes())
    assert not _is_known_sample_pdf(sample + b"unexpected")
    assert sample.startswith(b"%PDF-1.4")
    assert sample.rstrip().endswith(b"%%EOF")
    assert b"DEMO ONLY - FICTIONAL DATA - NOT A CLINICAL REPORT" in pdf_text
    assert b"Fictional Demonstration Patient (not real)" in pdf_text
    assert b"Report ID: DEMO-LAB-0001" in pdf_text
    assert b"Generated: " in pdf_text
    assert b"TEST RESULTS (FABRICATED EXAMPLES ONLY)" in pdf_text
    assert b"Sodium | 140 | mmol/L | 135-145" in pdf_text
    assert b"Glucose, fasting | 5.2 | mmol/L | 3.9-5.5" in pdf_text
    assert b"Hemoglobin | 13.5 | g/dL | 12.0-16.0" in pdf_text
    assert b"All values and intervals are invented for interface testing." in pdf_text
    assert b"PHYSIOCARE FICTIONAL LABORATORY" in pdf_text
    assert b"DEMO ONLY - NO CLINICAL RESULT - NO MEDICAL DECISION" in pdf_text
    xref = sample.rfind(b"xref\n")
    offsets = [
        int(line[:10])
        for line in sample[xref:].splitlines()[3:8]
    ]
    for object_number, offset in enumerate(offsets, start=1):
        assert sample[offset:].startswith(f"{object_number} 0 obj\n".encode("ascii"))


def test_api_cors_allows_the_lab_request_idempotency_header():
    cors = next(
        middleware for middleware in app.user_middleware
        if middleware.cls is CORSMiddleware
    )

    assert "Idempotency-Key" in cors.kwargs["allow_headers"]


def test_auth_service_rejects_demo_tags_outside_demo_mode(monkeypatch):
    monkeypatch.setattr(settings, "LAB_DEMO_MODE", False)

    with pytest.raises(HTTPException) as error:
        AuthService._validate_demo_tag(LAB_DEMO_REHEARSAL_TAG)

    assert error.value.status_code == 400


def test_lab_request_service_rejects_demo_tags_outside_demo_mode(monkeypatch):
    monkeypatch.setattr(settings, "LAB_DEMO_MODE", False)
    patient_lookup = AsyncMock()
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", patient_lookup)
    schema = LabRequestCreate(
        mode="clinic_visit",
        selected_tests=["cbc"],
        demo_rehearsal_tag=LAB_DEMO_REHEARSAL_TAG,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.create("patient-id", schema))

    assert error.value.status_code == 400
    patient_lookup.assert_not_awaited()


def test_only_tagged_demo_patient_can_create_tagged_request(monkeypatch):
    monkeypatch.setattr(settings, "LAB_DEMO_MODE", True)
    patient_lookup = AsyncMock(return_value=SimpleNamespace(demo_rehearsal_tag=None))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", patient_lookup)
    schema = LabRequestCreate(
        mode="clinic_visit",
        selected_tests=["cbc"],
        demo_rehearsal_tag=LAB_DEMO_REHEARSAL_TAG,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.create("patient-id", schema))

    assert error.value.status_code == 403
