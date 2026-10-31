import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.doctor_history_service import DoctorHistoryService


def test_missing_doctor_profile_does_not_expose_patient_history(monkeypatch):
    monkeypatch.setattr(
        ProfileRepository,
        "get_doctor_by_user_id",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(DoctorHistoryService.get_assigned_patient_history(
            "fictional-doctor-user",
            "507f1f77bcf86cd799439011",
        ))

    assert error.value.status_code == 404
    assert error.value.detail == "Assigned patient history not found"


def test_doctor_cannot_open_unassigned_patient_history(monkeypatch):
    doctor = type("DoctorDouble", (), {"id": "assigned-doctor"})()
    unrelated = type("AppointmentDouble", (), {
        "patient_id": "507f1f77bcf86cd799439099",
        "doctor_assignment_pending": False,
    })()
    monkeypatch.setattr(
        ProfileRepository,
        "get_doctor_by_user_id",
        AsyncMock(return_value=doctor),
    )
    monkeypatch.setattr(
        AppointmentRepository,
        "list_by_doctor_id",
        AsyncMock(return_value=[unrelated]),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(DoctorHistoryService.get_assigned_patient_history(
            "fictional-doctor-user",
            "507f1f77bcf86cd799439011",
        ))

    assert error.value.status_code == 404
    assert error.value.detail == "Assigned patient history not found"
