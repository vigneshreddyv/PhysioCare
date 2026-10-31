import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException


def configure_caseload(monkeypatch, *, assigned=True):
    """Use controlled profiles with the production verify_caseload helper."""
    from app.repositories.profile_repository import ProfileRepository

    doctor = SimpleNamespace(id="doctor-profile", user_id="doctor-user")
    patient = SimpleNamespace(
        id="patient-profile",
        user_id="patient-user",
        primary_doctor_id="doctor-profile" if assigned else "another-doctor-profile",
    )
    monkeypatch.setattr(
        ProfileRepository,
        "get_doctor_by_user_id",
        AsyncMock(return_value=doctor),
    )
    monkeypatch.setattr(
        ProfileRepository,
        "get_patient_by_id",
        AsyncMock(return_value=patient),
    )
    return doctor, patient


def clinician():
    return SimpleNamespace(id="doctor-user", role="doctor")


def care_plan(patient_id="patient-profile"):
    return SimpleNamespace(
        id="care-plan-id",
        patient_id=patient_id,
        therapist_id="doctor-profile",
        title="Recovery",
        description="Plan",
        current_stage=1,
        stages=[],
        goals=[],
        recommendations=[],
        start_date=datetime(2026, 1, 1),
        target_date=datetime(2026, 2, 1),
        status="active",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


def assignment(patient_id="patient-profile"):
    return SimpleNamespace(
        id="assignment-id",
        patient_id=patient_id,
        care_plan_id="care-plan-id",
        stage_id="stage-1",
        exercise_id="exercise-id",
        sets=2,
        reps=8,
        duration_seconds=0,
        frequency="daily",
        status="assigned",
        assigned_by="doctor-user",
        assigned_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


def exercise_payload():
    from app.schemas.exercise import ExerciseAssignmentCreate

    return ExerciseAssignmentCreate(
        patient_id="patient-profile",
        care_plan_id="care-plan-id",
        stage_id="stage-1",
        exercise_id="exercise-id",
        sets=2,
        reps=8,
        duration_seconds=0,
        frequency="daily",
    )


def report_payload(patient_id="patient-profile"):
    return json.dumps({
        "patient_id": patient_id,
        "title": "Report",
        "category": "assessment",
        "date": datetime(2026, 1, 1).isoformat(),
        "description": "Assessment",
        "therapist": "Clinician",
        "content": {"symptoms": "x", "findings": "y", "recommendations": "z"},
    })


@pytest.mark.asyncio
async def test_assigned_doctor_can_create_and_update_care_plan(monkeypatch):
    from app.api.care_plans import create_care_plan, update_care_plan
    from app.repositories.care_plan_repository import CarePlanRepository
    from app.schemas.care_plan import CarePlanCreate, CarePlanUpdate
    from app.services.care_plan_service import CarePlanService

    configure_caseload(monkeypatch)
    cp = care_plan()
    monkeypatch.setattr(CarePlanService, "create_care_plan", AsyncMock(return_value=cp))
    monkeypatch.setattr(CarePlanRepository, "get_by_id", AsyncMock(return_value=cp))
    update = AsyncMock(return_value=cp)
    monkeypatch.setattr(CarePlanService, "update_care_plan", update)

    created = await create_care_plan(
        CarePlanCreate(
            patient_id="patient-profile",
            title="Recovery",
            description="Plan",
            start_date=datetime(2026, 1, 1),
            target_date=datetime(2026, 2, 1),
        ),
        clinician(),
    )
    updated = await update_care_plan("care-plan-id", CarePlanUpdate(title="Updated"), clinician())

    assert created.patient_id == "patient-profile"
    assert updated.patient_id == "patient-profile"
    update.assert_awaited_once_with("care-plan-id", {"title": "Updated"})


@pytest.mark.asyncio
async def test_unassigned_doctor_cannot_create_or_update_care_plan(monkeypatch):
    from app.api.care_plans import create_care_plan, update_care_plan
    from app.repositories.care_plan_repository import CarePlanRepository
    from app.schemas.care_plan import CarePlanCreate, CarePlanUpdate
    from app.services.care_plan_service import CarePlanService

    configure_caseload(monkeypatch, assigned=False)
    cp = care_plan()
    monkeypatch.setattr(CarePlanRepository, "get_by_id", AsyncMock(return_value=cp))
    create = AsyncMock()
    update = AsyncMock()
    monkeypatch.setattr(CarePlanService, "create_care_plan", create)
    monkeypatch.setattr(CarePlanService, "update_care_plan", update)
    payload = CarePlanCreate(
        patient_id="patient-profile",
        title="Recovery",
        description="Plan",
        start_date=datetime(2026, 1, 1),
        target_date=datetime(2026, 2, 1),
    )

    with pytest.raises(HTTPException) as create_error:
        await create_care_plan(payload, clinician())
    with pytest.raises(HTTPException) as update_error:
        await update_care_plan("care-plan-id", CarePlanUpdate(title="Updated"), clinician())

    assert create_error.value.status_code == update_error.value.status_code == 404
    create.assert_not_awaited()
    update.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["stage", "goal"])
async def test_unassigned_doctor_cannot_modify_care_plan_stage_or_goal(monkeypatch, target):
    from app.api.care_plans import update_goal_progress_endpoint, update_stage_status_endpoint
    from app.repositories.care_plan_repository import CarePlanRepository
    from app.schemas.care_plan import GoalProgressUpdate, StageStatusUpdate
    from app.services.care_plan_service import CarePlanService

    configure_caseload(monkeypatch, assigned=False)
    monkeypatch.setattr(CarePlanRepository, "get_by_id", AsyncMock(return_value=care_plan()))
    stage_update = AsyncMock()
    goal_update = AsyncMock()
    monkeypatch.setattr(CarePlanService, "update_stage_status", stage_update)
    monkeypatch.setattr(CarePlanService, "update_goal_progress", goal_update)

    with pytest.raises(HTTPException) as exc_info:
        if target == "stage":
            await update_stage_status_endpoint(
                "care-plan-id", "stage-1", StageStatusUpdate(status="active"), clinician()
            )
        else:
            await update_goal_progress_endpoint(
                "care-plan-id", "goal-1", GoalProgressUpdate(progress_value=25, status="active"), clinician()
            )

    assert exc_info.value.status_code == 404
    stage_update.assert_not_awaited()
    goal_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_assigned_doctor_can_create_and_update_exercise_assignment(monkeypatch):
    from app.api.exercises import create_assignment, get_assignment, update_assignment
    from app.services.exercise_service import ExerciseService
    from app.schemas.exercise import ExerciseAssignmentUpdate

    configure_caseload(monkeypatch)
    record = assignment()
    create = AsyncMock(return_value=record)
    update = AsyncMock(return_value=record)
    get = AsyncMock(return_value=record)
    monkeypatch.setattr(ExerciseService, "create_assignment", create)
    monkeypatch.setattr(ExerciseService, "get_assignment", get)
    monkeypatch.setattr(ExerciseService, "update_assignment", update)

    created = await create_assignment(exercise_payload(), clinician())
    fetched = await get_assignment("assignment-id", clinician())
    updated = await update_assignment("assignment-id", ExerciseAssignmentUpdate(reps=10), clinician())

    assert created.patient_id == fetched.patient_id == updated.patient_id == "patient-profile"
    create.assert_awaited_once()
    update.assert_awaited_once_with(
        assignment_id="assignment-id",
        update_data={"reps": 10},
        user_role="doctor",
        actor_user_id="doctor-user",
    )


@pytest.mark.asyncio
async def test_unassigned_doctor_cannot_create_read_or_update_exercise_assignment(monkeypatch):
    from app.api.exercises import create_assignment, get_assignment, update_assignment
    from app.services.exercise_service import ExerciseService
    from app.schemas.exercise import ExerciseAssignmentUpdate

    configure_caseload(monkeypatch, assigned=False)
    record = assignment()
    create = AsyncMock()
    update = AsyncMock()
    get = AsyncMock(return_value=record)
    monkeypatch.setattr(ExerciseService, "create_assignment", create)
    monkeypatch.setattr(ExerciseService, "get_assignment", get)
    monkeypatch.setattr(ExerciseService, "update_assignment", update)

    with pytest.raises(HTTPException) as create_error:
        await create_assignment(exercise_payload(), clinician())
    with pytest.raises(HTTPException) as read_error:
        await get_assignment("assignment-id", clinician())
    with pytest.raises(HTTPException) as update_error:
        await update_assignment("assignment-id", ExerciseAssignmentUpdate(reps=10), clinician())

    assert [create_error.value.status_code, read_error.value.status_code, update_error.value.status_code] == [404] * 3
    create.assert_not_awaited()
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_patient_cannot_read_another_patients_exercise_assignment(monkeypatch):
    from app.api.exercises import get_assignment
    from app.repositories.profile_repository import ProfileRepository
    from app.services.exercise_service import ExerciseService

    patient_user = SimpleNamespace(id="patient-user", role="patient")
    patient_profile = SimpleNamespace(id="patient-profile")
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient_profile))
    monkeypatch.setattr(ExerciseService, "get_assignment", AsyncMock(return_value=assignment("someone-else")))

    with pytest.raises(HTTPException) as exc_info:
        await get_assignment("assignment-id", patient_user)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_assigned_doctor_can_create_report(monkeypatch):
    from app.api.reports import create_report_by_admin
    from app.services.report_service import ReportService

    configure_caseload(monkeypatch)
    report = SimpleNamespace(
        id="report-id",
        patient_id="patient-profile",
        booking_id=None,
        title="Report",
        category="assessment",
        date=datetime(2026, 1, 1),
        description="Assessment",
        therapist="Clinician",
        content={"symptoms": "x", "findings": "y", "recommendations": "z"},
        file_path=None,
        created_at=datetime(2026, 1, 1),
    )
    create = AsyncMock(return_value=report)
    monkeypatch.setattr(ReportService, "create_report", create)

    result = await create_report_by_admin(report_payload(), None, clinician())

    assert result.id == "report-id"
    create.assert_awaited_once()


@pytest.mark.asyncio
async def test_unassigned_doctor_cannot_create_report(monkeypatch):
    from app.api.reports import create_report_by_admin
    from app.services.report_service import ReportService

    configure_caseload(monkeypatch, assigned=False)
    create = AsyncMock()
    monkeypatch.setattr(ReportService, "create_report", create)

    with pytest.raises(HTTPException) as exc_info:
        await create_report_by_admin(report_payload(), None, clinician())

    assert exc_info.value.status_code == 404
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_care_plan_create_remains_allowed_without_caseload(monkeypatch):
    from app.api.care_plans import create_care_plan
    from app.schemas.care_plan import CarePlanCreate
    from app.services.care_plan_service import CarePlanService

    admin = SimpleNamespace(id="admin-user", role="admin")
    cp = care_plan()
    create = AsyncMock(return_value=cp)
    monkeypatch.setattr(CarePlanService, "create_care_plan", create)
    payload = CarePlanCreate(
        patient_id="patient-profile",
        title="Recovery",
        description="Plan",
        start_date=datetime(2026, 1, 1),
        target_date=datetime(2026, 2, 1),
    )

    result = await create_care_plan(payload, admin)

    assert result.patient_id == "patient-profile"
    create.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_report_and_exercise_assignment_operations_remain_allowed(monkeypatch):
    from app.api.exercises import create_assignment
    from app.api.reports import create_report_by_admin
    from app.services.exercise_service import ExerciseService
    from app.services.report_service import ReportService

    admin = SimpleNamespace(id="admin-user", role="admin")
    exercise_create = AsyncMock(return_value=assignment())
    report = SimpleNamespace(
        id="report-id",
        patient_id="patient-profile",
        booking_id=None,
        title="Report",
        category="assessment",
        date=datetime(2026, 1, 1),
        description="Assessment",
        therapist="Clinician",
        content={"symptoms": "x", "findings": "y", "recommendations": "z"},
        file_path=None,
        created_at=datetime(2026, 1, 1),
    )
    report_create = AsyncMock(return_value=report)
    monkeypatch.setattr(ExerciseService, "create_assignment", exercise_create)
    monkeypatch.setattr(ReportService, "create_report", report_create)

    created_assignment = await create_assignment(exercise_payload(), admin)
    created_report = await create_report_by_admin(report_payload(), None, admin)

    assert created_assignment.patient_id == "patient-profile"
    assert created_report.id == "report-id"
    exercise_create.assert_awaited_once()
    report_create.assert_awaited_once()
