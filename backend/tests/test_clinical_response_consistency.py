from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import care_plans, exercises
from app.middleware.auth import RoleChecker
from app.models.patient import Patient
from app.services import clinical_authorization
from app.services.care_plan_service import CarePlanService
from app.services.exercise_service import ExerciseService
from app.services.appointment_service import AppointmentService
from app.services.lab_request_service import LabRequestService
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.appointment import AppointmentUpdate


@pytest.mark.asyncio
async def test_assigned_clinician_can_list_patient_care_plans(monkeypatch):
    authorize = AsyncMock(return_value=object())
    monkeypatch.setattr(
        clinical_authorization,
        "require_doctor_patient_access",
        authorize,
    )
    monkeypatch.setattr(
        care_plans.CarePlanService,
        "get_care_plans_by_patient",
        AsyncMock(return_value=[]),
    )
    doctor = SimpleNamespace(role="doctor", id="doctor-user")

    result = await care_plans.get_patient_care_plans_by_clinician(
        "000000000000000000000000",
        doctor,
    )

    assert result == []
    authorize.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "patient_id",
    ["111111111111111111111111", "ffffffffffffffffffffffff"],
)
async def test_unassigned_and_nonexistent_patient_are_externally_identical(
    monkeypatch,
    patient_id,
):
    monkeypatch.setattr(
        clinical_authorization,
        "require_doctor_patient_access",
        AsyncMock(side_effect=PermissionError("internal assignment detail")),
    )
    doctor = SimpleNamespace(role="doctor", id="doctor-user")

    with pytest.raises(HTTPException) as error:
        await care_plans.get_patient_care_plans_by_clinician(patient_id, doctor)

    assert error.value.status_code == 404
    assert error.value.detail == "Patient not found"
    assert "assignment" not in error.value.detail.casefold()


@pytest.mark.asyncio
async def test_admin_access_does_not_require_clinician_assignment(monkeypatch):
    service = AsyncMock(return_value=[])
    monkeypatch.setattr(
        care_plans.CarePlanService,
        "get_care_plans_by_patient",
        service,
    )
    result = await care_plans.get_patient_care_plans_by_clinician(
        "000000000000000000000000",
        SimpleNamespace(role="admin", id="admin-user"),
    )
    assert result == []
    service.assert_awaited_once()


def test_patient_cannot_use_clinician_care_plan_route():
    with pytest.raises(HTTPException) as error:
        RoleChecker(["admin", "doctor"])(SimpleNamespace(role="patient"))
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_unassigned_and_nonexistent_assignment_return_same_response(monkeypatch):
    doctor = SimpleNamespace(role="doctor", id="doctor-user")
    assignment = SimpleNamespace(patient_id="000000000000000000000000")
    monkeypatch.setattr(
        exercises.ExerciseService,
        "get_assignment",
        AsyncMock(return_value=assignment),
    )
    monkeypatch.setattr(
        clinical_authorization,
        "require_doctor_patient_access",
        AsyncMock(side_effect=PermissionError("internal assignment detail")),
    )
    with pytest.raises(HTTPException) as unassigned:
        await exercises.get_assignment("existing-assignment", doctor)

    monkeypatch.setattr(
        exercises.ExerciseService,
        "get_assignment",
        AsyncMock(return_value=None),
    )
    with pytest.raises(HTTPException) as missing:
        await exercises.get_assignment("missing-assignment", doctor)

    assert (unassigned.value.status_code, unassigned.value.detail) == (
        missing.value.status_code,
        missing.value.detail,
    ) == (404, "Assignment not found")


@pytest.mark.asyncio
async def test_invalid_patient_id_is_a_nondisclosing_denial(monkeypatch):
    monkeypatch.setattr(
        clinical_authorization.ProfileRepository,
        "get_doctor_by_user_id",
        AsyncMock(return_value=object()),
    )
    with pytest.raises(PermissionError, match="not available"):
        await clinical_authorization.require_doctor_patient_access(
            "doctor-user",
            "not-an-object-id",
        )


@pytest.mark.asyncio
async def test_doctor_care_plan_creation_authorizes_before_patient_existence_lookup(
    monkeypatch,
):
    authorize = AsyncMock(side_effect=PermissionError("not available"))
    patient_get = AsyncMock(return_value=None)
    monkeypatch.setattr(
        clinical_authorization,
        "require_doctor_patient_access",
        authorize,
    )
    monkeypatch.setattr(Patient, "get", patient_get)

    with pytest.raises(PermissionError, match="not available"):
        await CarePlanService.create_care_plan(
            patient_id="111111111111111111111111",
            therapist_id="222222222222222222222222",
            title="Fictional plan",
            description="Fictional description",
            current_stage=1,
            stages=[],
            goals=[],
            recommendations=[],
            start_date=SimpleNamespace(),
            target_date=SimpleNamespace(),
            actor_user_id="doctor-user",
            actor_role="doctor",
        )

    authorize.assert_awaited_once()
    patient_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_doctor_exercise_creation_authorizes_before_patient_existence_lookup(
    monkeypatch,
):
    authorize = AsyncMock(side_effect=PermissionError("not available"))
    patient_get = AsyncMock(return_value=None)
    monkeypatch.setattr(
        clinical_authorization,
        "require_doctor_patient_access",
        authorize,
    )
    monkeypatch.setattr(Patient, "get", patient_get)

    with pytest.raises(PermissionError, match="not available"):
        await ExerciseService.create_assignment(
            {
                "patient_id": "111111111111111111111111",
                "care_plan_id": "222222222222222222222222",
                "stage_id": "stage-1",
                "exercise_id": "333333333333333333333333",
            },
            assigned_by_user_id="doctor-user",
            assigned_by_role="doctor",
        )

    authorize.assert_awaited_once()
    patient_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_doctor_appointment_missing_and_unassigned_are_identical(monkeypatch):
    doctor = SimpleNamespace(id="assigned-doctor")
    foreign = SimpleNamespace(
        doctor_id="other-doctor",
        doctor_assignment_pending=False,
    )
    monkeypatch.setattr(
        ProfileRepository,
        "get_doctor_by_user_id",
        AsyncMock(return_value=doctor),
    )

    responses = []
    for appointment in (None, foreign):
        monkeypatch.setattr(
            AppointmentRepository,
            "get_by_id",
            AsyncMock(return_value=appointment),
        )
        with pytest.raises(HTTPException) as error:
            await AppointmentService.update_appointment(
                "opaque-appointment-id",
                AppointmentUpdate(status="in_progress"),
                actor_user_id="doctor-user",
                actor_role="doctor",
            )
        responses.append((error.value.status_code, error.value.detail))

    assert responses == [(404, "Appointment not found")] * 2


@pytest.mark.asyncio
async def test_patient_appointment_missing_and_foreign_are_identical(monkeypatch):
    patient = SimpleNamespace(id="patient-profile")
    monkeypatch.setattr(
        ProfileRepository,
        "get_patient_by_user_id",
        AsyncMock(return_value=patient),
    )

    responses = []
    for appointment in (None, SimpleNamespace(patient_id="other-patient")):
        monkeypatch.setattr(
            AppointmentRepository,
            "get_by_id",
            AsyncMock(return_value=appointment),
        )
        with pytest.raises(HTTPException) as error:
            await AppointmentService.cancel_patient_appointment(
                "opaque-appointment-id",
                "patient-user",
            )
        responses.append((error.value.status_code, error.value.detail))

    assert responses == [(404, "Appointment not found")] * 2


@pytest.mark.asyncio
async def test_lab_report_missing_and_foreign_are_identical(monkeypatch):
    patient = SimpleNamespace(id="patient-profile")
    foreign = SimpleNamespace(
        report_storage_key="opaque.pdf",
        report_file_name="report.pdf",
        report_status="released",
        patient_id="other-patient",
        assigned_laboratorian_user_id=None,
    )
    monkeypatch.setattr(
        ProfileRepository,
        "get_patient_by_user_id",
        AsyncMock(return_value=patient),
    )

    responses = []
    for request in (None, foreign):
        monkeypatch.setattr(
            LabRequestRepository,
            "get",
            AsyncMock(return_value=request),
        )
        with pytest.raises(HTTPException) as error:
            await LabRequestService.get_report_file(
                "opaque-request-id",
                "patient-user",
                "patient",
            )
        responses.append((error.value.status_code, error.value.detail))

    assert responses == [(404, "Laboratory report not found")] * 2


@pytest.mark.asyncio
async def test_lab_withdraw_missing_and_foreign_are_identical(monkeypatch):
    patient = SimpleNamespace(id="patient-profile")
    monkeypatch.setattr(
        ProfileRepository,
        "get_patient_by_user_id",
        AsyncMock(return_value=patient),
    )

    responses = []
    for request in (None, SimpleNamespace(patient_id="other-patient")):
        monkeypatch.setattr(
            LabRequestRepository,
            "get",
            AsyncMock(return_value=request),
        )
        with pytest.raises(HTTPException) as error:
            await LabRequestService.withdraw("opaque-request-id", "patient-user")
        responses.append((error.value.status_code, error.value.detail))

    assert responses == [(404, "Laboratory request not found")] * 2
