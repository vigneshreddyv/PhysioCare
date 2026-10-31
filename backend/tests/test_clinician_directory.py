from unittest.mock import AsyncMock

import pytest
from beanie import PydanticObjectId

from app.api.users import list_patients
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_doctor_directory_contains_only_unique_assigned_patients(monkeypatch):
    doctor = type("DoctorDouble", (), {"id": "assigned-doctor"})()
    patient_a_id = "111111111111111111111111"
    patient_b_id = "222222222222222222222222"
    appointments = [
        type("AppointmentDouble", (), {"patient_id": patient_a_id, "doctor_assignment_pending": False})(),
        type("AppointmentDouble", (), {"patient_id": patient_a_id, "doctor_assignment_pending": False})(),
        type("AppointmentDouble", (), {"patient_id": patient_b_id, "doctor_assignment_pending": True})(),
    ]
    patient = type("PatientDouble", (), {
        "id": PydanticObjectId(patient_a_id),
        "user_id": "333333333333333333333333",
        "phone": "+91 90000 00001",
        "date_of_birth": "1990-01-01",
        "gender": None,
    })()
    user = type("UserDouble", (), {"full_name": "Fictional Patient"})()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_by_doctor_id", AsyncMock(return_value=appointments))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=user))

    result = await UserService.list_assigned_patients("authenticated-doctor-user")

    assert len(result) == 1
    assert result[0].id == patient_a_id
    assert result[0].full_name == "Fictional Patient"
    assert set(result[0].model_dump()) == {"id", "full_name", "phone", "date_of_birth", "gender"}
    AppointmentRepository.list_by_doctor_id.assert_awaited_once_with("assigned-doctor")
    ProfileRepository.get_patient_by_id.assert_awaited_once_with(patient_a_id)


@pytest.mark.asyncio
async def test_doctor_directory_is_empty_without_doctor_profile(monkeypatch):
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=None))
    monkeypatch.setattr(AppointmentRepository, "list_by_doctor_id", AsyncMock())

    result = await UserService.list_assigned_patients("authenticated-doctor-user")

    assert result == []
    AppointmentRepository.list_by_doctor_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_patient_directory_route_uses_authenticated_doctor_identity(monkeypatch):
    doctor_user = type("UserDouble", (), {
        "id": PydanticObjectId("000000000000000000000000"),
        "role": "doctor",
    })()
    list_assigned = AsyncMock(return_value=[])
    monkeypatch.setattr(UserService, "list_assigned_patients", list_assigned)

    await list_patients(current_user=doctor_user)

    list_assigned.assert_awaited_once_with(str(doctor_user.id))


@pytest.mark.asyncio
async def test_patient_directory_route_keeps_admin_listing_separate(monkeypatch):
    admin_user = type("UserDouble", (), {
        "id": PydanticObjectId("777777777777777777777777"),
        "role": "admin",
    })()
    list_admin = AsyncMock(return_value=[])
    list_assigned = AsyncMock(return_value=[])
    monkeypatch.setattr(UserService, "list_patients", list_admin)
    monkeypatch.setattr(UserService, "list_assigned_patients", list_assigned)

    await list_patients(current_user=admin_user)

    list_admin.assert_awaited_once_with()
    list_assigned.assert_not_awaited()
