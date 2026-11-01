from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from app.services.appointment_service import AppointmentService


def appointment_double(*, patient_id: str, status: str = "scheduled"):
    return type("AppointmentDouble", (), {
        "id": PydanticObjectId("222222222222222222222222"),
        "patient_id": PydanticObjectId(patient_id),
        "doctor_id": PydanticObjectId("999999999999999999999999"),
        "status": status,
        "starts_at": datetime.now(timezone.utc) + timedelta(days=3),
        "appointment_date": datetime.now(timezone.utc) + timedelta(days=3),
        "time_slot": "09:00 AM",
        "billing_status": "pending",
        "payment_status": "pending",
    })()


@pytest.mark.asyncio
async def test_patient_cancels_own_appointment_through_atomic_repository(monkeypatch):
    patient_id = "111111111111111111111111"
    patient_user_id = "000000000000000000000000"
    appointment = appointment_double(patient_id=patient_id)
    cancelled = appointment_double(patient_id=patient_id, status="cancelled")
    from app.repositories.appointment_repository import AppointmentRepository
    from app.repositories.profile_repository import ProfileRepository

    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=type("PatientDouble", (), {"id": PydanticObjectId(patient_id)})()
    ))
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(side_effect=[appointment, cancelled]))
    monkeypatch.setattr(AppointmentRepository, "cancel_scheduled_owned", AsyncMock(return_value=True))
    monkeypatch.setattr(AppointmentService, "_mark_cancelled_capture_for_reconciliation", AsyncMock())
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="formatted"))

    result = await AppointmentService.cancel_patient_appointment(
        str(appointment.id),
        patient_user_id,
    )

    assert result == "formatted"
    AppointmentRepository.cancel_scheduled_owned.assert_awaited_once()
    args = AppointmentRepository.cancel_scheduled_owned.await_args.args
    assert args[:2] == (str(appointment.id), patient_id)
    assert isinstance(args[2], datetime)
    assert AppointmentService._mark_cancelled_capture_for_reconciliation.await_count == 1


@pytest.mark.asyncio
async def test_patient_cannot_cancel_another_patients_appointment(monkeypatch):
    patient_id = "111111111111111111111111"
    appointment = appointment_double(patient_id="333333333333333333333333")

    from app.repositories.appointment_repository import AppointmentRepository
    from app.repositories.profile_repository import ProfileRepository

    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=type("PatientDouble", (), {"id": PydanticObjectId(patient_id)})()
    ))
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(AppointmentRepository, "cancel_scheduled_owned", AsyncMock())

    with pytest.raises(HTTPException) as error:
        await AppointmentService.cancel_patient_appointment(
            str(appointment.id),
            "000000000000000000000000",
        )

    assert error.value.status_code == 404
    AppointmentRepository.cancel_scheduled_owned.assert_not_awaited()


@pytest.mark.asyncio
async def test_patient_cancellation_requires_patient_profile(monkeypatch):
    from app.repositories.profile_repository import ProfileRepository

    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as error:
        await AppointmentService.cancel_patient_appointment(
            "222222222222222222222222",
            "000000000000000000000000",
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_patient_cannot_cancel_within_24_hour_cutoff(monkeypatch):
    patient_id = "111111111111111111111111"
    appointment = appointment_double(patient_id=patient_id)
    appointment.starts_at = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)

    from app.repositories.appointment_repository import AppointmentRepository
    from app.repositories.profile_repository import ProfileRepository

    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=type("PatientDouble", (), {"id": PydanticObjectId(patient_id)})()
    ))
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(AppointmentRepository, "cancel_scheduled_owned", AsyncMock())

    with pytest.raises(HTTPException) as error:
        await AppointmentService.cancel_patient_appointment(
            str(appointment.id),
            "000000000000000000000000",
            now=datetime(2026, 10, 31, 11, tzinfo=timezone.utc),
        )

    assert error.value.status_code == 409
    AppointmentRepository.cancel_scheduled_owned.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_cancellation_is_idempotent(monkeypatch):
    patient_id = "111111111111111111111111"
    appointment = appointment_double(patient_id=patient_id, status="cancelled")

    from app.repositories.appointment_repository import AppointmentRepository
    from app.repositories.profile_repository import ProfileRepository

    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=type("PatientDouble", (), {"id": PydanticObjectId(patient_id)})()
    ))
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(AppointmentRepository, "cancel_scheduled_owned", AsyncMock())
    monkeypatch.setattr(AppointmentService, "_mark_cancelled_capture_for_reconciliation", AsyncMock())
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="formatted"))

    result = await AppointmentService.cancel_patient_appointment(
        str(appointment.id),
        "000000000000000000000000",
    )

    assert result == "formatted"
    AppointmentRepository.cancel_scheduled_owned.assert_not_awaited()
    AppointmentService._mark_cancelled_capture_for_reconciliation.assert_awaited_once_with(appointment)


@pytest.mark.asyncio
async def test_doctor_cannot_update_an_unassigned_appointment(monkeypatch):
    appointment = appointment_double(patient_id="111111111111111111111111")
    from app.repositories.appointment_repository import AppointmentRepository
    from app.repositories.profile_repository import ProfileRepository

    doctor = type("DoctorDouble", (), {"id": PydanticObjectId("888888888888888888888888")})()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))

    with pytest.raises(HTTPException) as error:
        await AppointmentService.update_appointment(
            str(appointment.id),
            MagicMock(status="completed", billing_status=None, billing_amount=None),
            actor_user_id="777777777777777777777777",
            actor_role="doctor",
        )

    assert error.value.status_code == 404
