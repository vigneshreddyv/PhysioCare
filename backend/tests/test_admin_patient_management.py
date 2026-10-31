from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError

from app.api.users import router as users_router
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointment import AppointmentOut
from app.schemas.lab_request import LabReportOut
from app.schemas.patient import AdminPatientUpdate
from app.services.admin_patient_history_service import AdminPatientHistoryService
from app.services.appointment_service import AppointmentService
from app.services.lab_request_service import LabRequestService
from app.services.user_service import UserService


PATIENT_ID = "111111111111111111111111"
PATIENT_USER_ID = "222222222222222222222222"
ADMIN_USER_ID = "333333333333333333333333"


def patient_double(**overrides):
    values = {
        "id": PydanticObjectId(PATIENT_ID),
        "user_id": PydanticObjectId(PATIENT_USER_ID),
        "phone": "+91 90000 00000",
        "date_of_birth": "1990-01-01",
        "gender": "Woman",
        "subscription_status": "active",
        "admin_edit_audit": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def user_double():
    return SimpleNamespace(
        id=PydanticObjectId(PATIENT_USER_ID),
        full_name="Fictional Patient",
        email="fictional.patient@example.test",
    )


def allowed_roles(path: str, method: str) -> set[str]:
    route = next(
        route
        for route in users_router.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and method in route.methods
    )
    checker = next(
        dependency.call
        for dependency in route.dependant.dependencies
        if hasattr(dependency.call, "allowed_roles")
    )
    return set(checker.allowed_roles)


def test_admin_patient_routes_are_admin_only():
    assert allowed_roles("/users/patients/{patient_id}", "GET") == {"admin"}
    assert allowed_roles("/users/patients/{patient_id}", "PATCH") == {"admin"}
    assert allowed_roles("/users/patients/{patient_id}/history", "GET") == {"admin"}


def test_admin_update_schema_is_narrow_and_validated():
    assert set(AdminPatientUpdate.model_fields) == {
        "full_name",
        "phone",
        "date_of_birth",
        "gender",
        "subscription_status",
    }
    with pytest.raises(ValidationError):
        AdminPatientUpdate(email="replacement@example.test")
    with pytest.raises(ValidationError):
        AdminPatientUpdate(date_of_birth=date.today() + timedelta(days=1))
    with pytest.raises(ValidationError):
        AdminPatientUpdate(subscription_status="paid")


@pytest.mark.asyncio
async def test_admin_patient_edit_updates_allowed_fields_and_records_metadata_audit(monkeypatch):
    patient = patient_double()
    user = user_double()
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=user))
    save_user = AsyncMock(return_value=user)
    save_patient = AsyncMock(return_value=patient)
    monkeypatch.setattr(UserRepository, "save", save_user)
    monkeypatch.setattr(ProfileRepository, "save_patient", save_patient)

    result = await UserService.update_admin_patient(
        PATIENT_ID,
        AdminPatientUpdate(
            full_name="  Updated   Patient ",
            phone="+91 98888 88888",
            date_of_birth=date(1992, 2, 3),
            gender=None,
            subscription_status="pending",
        ),
        ADMIN_USER_ID,
    )

    assert result.full_name == "Updated Patient"
    assert result.date_of_birth == "1992-02-03"
    assert result.subscription_status == "pending"
    assert patient.gender is None
    assert len(patient.admin_edit_audit) == 1
    audit = patient.admin_edit_audit[0]
    assert str(audit.actor_user_id) == ADMIN_USER_ID
    assert audit.changed_fields == [
        "date_of_birth",
        "full_name",
        "gender",
        "phone",
        "subscription_status",
    ]
    assert not hasattr(audit, "old_values")
    assert not hasattr(audit, "new_values")
    save_user.assert_awaited_once_with(user)
    save_patient.assert_awaited_once_with(patient)


@pytest.mark.asyncio
async def test_admin_patient_edit_rejects_empty_and_missing_records(monkeypatch):
    patient = patient_double()
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=user_double()))

    with pytest.raises(HTTPException) as empty_error:
        await UserService.update_admin_patient(
            PATIENT_ID,
            AdminPatientUpdate(),
            ADMIN_USER_ID,
        )
    assert empty_error.value.status_code == 422

    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as missing_error:
        await UserService.get_admin_patient(PATIENT_ID)
    assert missing_error.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_patient_history_combines_visits_reports_and_audit(monkeypatch):
    audit_event = SimpleNamespace(
        actor_user_id=PydanticObjectId(ADMIN_USER_ID),
        changed_fields=["phone"],
        changed_at=datetime(2026, 10, 31, 12, 0),
    )
    patient = patient_double(admin_edit_audit=[audit_event])
    user = user_double()
    appointment_record = object()
    report_record = object()
    appointment = AppointmentOut(
        id="appointment-id",
        patient_id=PATIENT_ID,
        patient_name=user.full_name,
        doctor_id="444444444444444444444444",
        doctor_name="Fictional Doctor",
        appointment_date=datetime(2026, 10, 20),
        clinic_timezone="Asia/Kolkata",
        time_slot="09:00 AM",
        reason="Follow-up",
        status="completed",
        billing_status="paid",
        billing_amount=120,
        can_patient_cancel=False,
        cancellation_message="Completed",
        created_at=datetime(2026, 10, 1),
    )
    report = LabReportOut(
        request_id="555555555555555555555555",
        patient_name=user.full_name,
        selected_tests=["cbc"],
        report_status="released",
    )
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(
        AppointmentRepository,
        "list_by_patient_id",
        AsyncMock(return_value=[appointment_record]),
    )
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value=appointment))
    monkeypatch.setattr(
        LabRequestRepository,
        "list_released_for_patients",
        AsyncMock(return_value=[report_record]),
    )
    monkeypatch.setattr(LabRequestService, "_format_report", AsyncMock(return_value=report))

    result = await AdminPatientHistoryService.get_patient_history(PATIENT_ID)

    assert result.patient.email == user.email
    assert [item.id for item in result.appointments] == ["appointment-id"]
    assert [item.request_id for item in result.reports] == [report.request_id]
    assert result.profile_audit[0].changed_fields == ["phone"]
    assert result.profile_audit[0].actor_user_id == ADMIN_USER_ID
    AppointmentRepository.list_by_patient_id.assert_awaited_once_with(PATIENT_ID)
    LabRequestRepository.list_released_for_patients.assert_awaited_once_with([PATIENT_ID])
