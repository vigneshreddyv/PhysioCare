"""Offline patient-owned appointment lookup used for payment resume."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from beanie import PydanticObjectId
from fastapi import HTTPException
import httpx
import pytest

from app.main import app
from app.middleware.auth import get_current_user
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.appointment import AppointmentOut
from app.services.appointment_service import AppointmentService


PATIENT = PydanticObjectId("507f1f77bcf86cd799439011")
OTHER = PydanticObjectId("507f1f77bcf86cd799439012")
APPOINTMENT = PydanticObjectId("507f1f77bcf86cd799439013")


def appointment_output():
    now = datetime(2026, 11, 2, 9)
    return AppointmentOut(
        id=str(APPOINTMENT), patient_id=str(PATIENT), patient_name="Fictional patient",
        doctor_id=str(OTHER), doctor_name="Fictional doctor", appointment_date=now,
        clinic_timezone="Asia/Kolkata", time_slot="09:00 AM", reason="Fictional visit",
        status="scheduled", billing_status="pending", billing_amount=0,
        can_patient_cancel=True, cancellation_message="Fictional cancellation policy",
        created_at=now,
    )


@pytest.mark.asyncio
async def test_patient_lookup_returns_only_own_appointment(monkeypatch):
    own = SimpleNamespace(id=APPOINTMENT, patient_id=PATIENT)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id=PATIENT),
    ))
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=own))
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(
        return_value=appointment_output(),
    ))
    result = await AppointmentService.get_patient_appointment(str(APPOINTMENT), "fictional-user")
    assert result.id == str(APPOINTMENT)
    AppointmentService._format_appointment.assert_awaited_once_with(own)


@pytest.mark.asyncio
@pytest.mark.parametrize("appointment", [None, SimpleNamespace(id=APPOINTMENT, patient_id=OTHER)])
async def test_patient_lookup_missing_and_foreign_are_identical(monkeypatch, appointment):
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id=PATIENT),
    ))
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    formatter = AsyncMock()
    monkeypatch.setattr(AppointmentService, "_format_appointment", formatter)
    with pytest.raises(HTTPException) as error:
        await AppointmentService.get_patient_appointment(str(APPOINTMENT), "fictional-user")
    assert error.value.status_code == 404
    assert error.value.detail == "Appointment not found"
    formatter.assert_not_awaited()


@pytest.mark.asyncio
async def test_http_lookup_patient_only_and_private(monkeypatch):
    for role, expected_status in (("patient", 200), ("doctor", 403), ("admin", 403)):
        monkeypatch.setitem(app.dependency_overrides, get_current_user,
                            lambda role=role: SimpleNamespace(id=PATIENT, role=role, is_active=True))
        getter = AsyncMock(return_value=appointment_output())
        monkeypatch.setattr(AppointmentService, "get_patient_appointment", getter)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            response = await client.get(f"/api/appointments/{APPOINTMENT}")
        assert response.status_code == expected_status
        if role == "patient":
            assert response.json()["id"] == str(APPOINTMENT)
            assert response.headers["cache-control"] == "private, no-store"
            getter.assert_awaited_once_with(str(APPOINTMENT), str(PATIENT))
        else:
            getter.assert_not_awaited()
    app.dependency_overrides.pop(get_current_user, None)
