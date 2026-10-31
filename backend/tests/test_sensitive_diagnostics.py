import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import SECRET_SETTINGS_FIELDS, Settings
from app.services.laboratory_service import LaboratoryService
from app.services.report_service import ReportService


FAKE_SECRETS = {
    "MONGODB_URL": "mongodb://fake-user:fake-password@fake.example/physiocare",
    "JWT_SECRET": "fake-access-secret-" + "a" * 32,
    "JWT_REFRESH_SECRET": "fake-refresh-secret-" + "b" * 32,
    "RAZORPAY_KEY_SECRET": "fake-razorpay-secret",
    "RAZORPAY_WEBHOOK_SECRET": "fake-webhook-secret",
}


def make_settings() -> Settings:
    return Settings(_env_file=None, **FAKE_SECRETS)


def test_secret_settings_inventory_is_explicit():
    assert SECRET_SETTINGS_FIELDS == {
        "MONGODB_URL",
        "JWT_SECRET",
        "JWT_REFRESH_SECRET",
        "RAZORPAY_KEY_SECRET",
        "RAZORPAY_WEBHOOK_SECRET",
    }


def test_settings_repr_and_str_redact_all_secrets():
    isolated = make_settings()

    for rendered in (repr(isolated), str(isolated)):
        for value in FAKE_SECRETS.values():
            assert value not in rendered
        for name in SECRET_SETTINGS_FIELDS:
            assert f"{name}=SecretStr('**********')" in rendered


def test_settings_dump_and_json_redact_all_secrets():
    isolated = make_settings()
    dumped = isolated.model_dump()
    dumped_json = isolated.model_dump_json()

    for name in SECRET_SETTINGS_FIELDS:
        assert dumped[name] == "**********"
        assert json.loads(dumped_json)[name] == "**********"
    for value in FAKE_SECRETS.values():
        assert value not in dumped_json


@pytest.mark.asyncio
async def test_report_follow_up_failure_logs_category_without_exception_secret(caplog):
    secret = "patient@example.test bearer-secret"
    report = MagicMock(id="report-id")

    with (
        patch(
            "app.services.report_service.ReportRepository.create",
            new=AsyncMock(return_value=report),
        ),
        patch(
            "app.services.laboratory_service.LaboratoryService.update_booking_status",
            new=AsyncMock(side_effect=RuntimeError(secret)),
        ),
        patch("app.models.patient.Patient.get", new=AsyncMock(return_value=None)),
        caplog.at_level(logging.WARNING),
    ):
        result = await ReportService.create_report(
            patient_id="111111111111111111111111",
            booking_id="222222222222222222222222",
            title="Diagnostic result",
            category="diagnostic",
            date=MagicMock(),
            description="Ready",
            therapist="Clinician",
            content={},
        )

    assert result is report
    assert "operation=lab_status_transition" in caplog.text
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_laboratory_notification_failure_logs_category_without_exception_secret(caplog):
    secret = "patient@example.test cookie-secret"
    booking = MagicMock()
    booking.patient_id = "111111111111111111111111"
    booking.status = "confirmed"
    booking.save = AsyncMock()

    with (
        patch(
            "app.services.laboratory_service.LaboratoryBookingRepository.get_by_id",
            new=AsyncMock(return_value=booking),
        ),
        patch("app.services.laboratory_service.Patient.get", new=AsyncMock(side_effect=RuntimeError(secret))),
        caplog.at_level(logging.WARNING),
    ):
        result = await LaboratoryService.update_booking_status("booking-id", "completed")

    assert result is booking
    assert "operation=status_notification" in caplog.text
    assert secret not in caplog.text
