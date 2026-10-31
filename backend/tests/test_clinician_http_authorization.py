import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


def make_user(role, user_id=None):
    return SimpleNamespace(id=user_id or f"{role}-user", role=role, is_active=True)


def make_care_plan(patient_id="patient-profile"):
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


def make_assignment(patient_id="patient-profile"):
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
        save=AsyncMock(),
    )


def make_appointment():
    return SimpleNamespace(
        id="appointment-id",
        patient_id="patient-profile",
        doctor_id="doctor-profile",
        service_type="clinic_consultation",
        appointment_date=datetime(2026, 12, 1),
        time_slot="09:00 AM",
        reason="Knee pain",
        symptoms=None,
        duration_days=None,
        pain_level=None,
        visit_address=None,
        status="confirmed",
        billing_status="pending",
        billing_amount=120.0,
        payment_method="offline",
        payment_status="pending",
        payment_id=None,
        payment_order_id=None,
        meeting_link=None,
        feedback_rating=None,
        feedback_comment=None,
        created_at=datetime(2026, 1, 1),
        save=AsyncMock(),
    )


def make_report(patient_id="patient-profile"):
    return SimpleNamespace(
        id="report-id",
        patient_id=patient_id,
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


def report_form(patient_id="patient-profile"):
    return {
        "report_data_str": json.dumps({
            "patient_id": patient_id,
            "title": "Report",
            "category": "assessment",
            "date": "2026-01-01T00:00:00",
            "description": "Assessment",
            "therapist": "Clinician",
            "content": {"symptoms": "x", "findings": "y", "recommendations": "z"},
        })
    }


@pytest.fixture
def client_for(monkeypatch):
    """Use TestClient without startup database access and inject only the user dependency."""
    import app.main as main
    from app.middleware.auth import get_current_user

    monkeypatch.setattr(main, "init_db", AsyncMock())
    monkeypatch.setattr(main.StalePaymentReconciliationService, "start_background_loop", lambda: None)
    monkeypatch.setattr(main.RefundReconciliationService, "start_background_loop", lambda: None)
    main.app.dependency_overrides.clear()

    def build(user=None):
        if user is None:
            main.app.dependency_overrides.pop(get_current_user, None)
        else:
            main.app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(main.app)

    yield build
    main.app.dependency_overrides.clear()


def install_caseload(monkeypatch, *, assigned=True):
    from app.repositories.profile_repository import ProfileRepository

    doctor = SimpleNamespace(id="doctor-profile", user_id="doctor-user")
    patient = SimpleNamespace(
        id="patient-profile",
        user_id="patient-user",
        primary_doctor_id="doctor-profile" if assigned else "different-doctor-profile",
    )
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    return doctor, patient


def care_plan_create_body():
    return {
        "patient_id": "patient-profile",
        "title": "Recovery",
        "description": "Plan",
        "start_date": "2026-01-01T00:00:00",
        "target_date": "2026-02-01T00:00:00",
    }


def exercise_create_body():
    return {
        "patient_id": "patient-profile",
        "care_plan_id": "care-plan-id",
        "stage_id": "stage-1",
        "exercise_id": "exercise-id",
        "sets": 2,
        "reps": 8,
        "duration_seconds": 0,
        "frequency": "daily",
    }


def setup_appointment_response(monkeypatch, *, doctor_id="doctor-profile"):
    from app.repositories.appointment_repository import AppointmentRepository
    from app.repositories.profile_repository import ProfileRepository
    from app.repositories.user_repository import UserRepository
    from app.services.notification_service import NotificationService

    appointment = make_appointment()
    appointment.doctor_id = doctor_id
    doctor = SimpleNamespace(id=doctor_id, user_id="doctor-user", specialization="Physical Therapy")
    patient = SimpleNamespace(id="patient-profile", user_id="patient-user")
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(side_effect=[appointment, appointment]))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(
        UserRepository,
        "get_by_id",
        AsyncMock(side_effect=[SimpleNamespace(full_name="Patient"), SimpleNamespace(full_name="Doctor")]),
    )
    monkeypatch.setattr(NotificationService, "create_notification", AsyncMock())
    return appointment


@pytest.mark.parametrize("role", ["doctor", "admin"])
def test_http_appointment_update_authenticates_and_allows_assigned_doctor_and_admin(monkeypatch, client_for, role):
    appointment = setup_appointment_response(monkeypatch)
    client = client_for(make_user(role))

    response = client.patch(
        "/api/appointments/appointment-id",
        json={"status": "in_progress", "meeting_link": "https://example.test/visit"},
    )

    assert response.status_code == 200
    assert response.json()["meeting_link"] == "https://example.test/visit"
    appointment.save.assert_awaited_once()


def test_http_appointment_update_requires_auth_and_rejects_unassigned_doctor(monkeypatch, client_for):
    unauthenticated = client_for().patch(
        "/api/appointments/appointment-id", json={"status": "in_progress"}
    )
    assert unauthenticated.status_code == 401

    appointment = setup_appointment_response(monkeypatch, doctor_id="assigned-doctor-profile")
    from app.repositories.profile_repository import ProfileRepository
    monkeypatch.setattr(
        ProfileRepository,
        "get_doctor_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id="different-doctor-profile")),
    )
    response = client_for(make_user("doctor")).patch(
        "/api/appointments/appointment-id", json={"status": "in_progress"}
    )

    assert response.status_code == 404
    appointment.save.assert_not_awaited()


@pytest.mark.parametrize(
    "method,path,request_kwargs",
    [
        ("post", "/api/care-plans", {"json": care_plan_create_body()}),
        ("patch", "/api/care-plans/care-plan-id", {"json": {"title": "Updated"}}),
        ("patch", "/api/care-plans/care-plan-id/stages/stage-1", {"json": {"status": "active"}}),
        ("patch", "/api/care-plans/care-plan-id/goals/goal-1", {"json": {"progress_value": 25}}),
        ("post", "/api/exercise-assignments", {"json": exercise_create_body()}),
        ("patch", "/api/exercise-assignments/assignment-id", {"json": {"status": "in_progress"}}),
        ("post", "/api/reports", {"data": report_form()}),
    ],
)
def test_http_clinician_routes_require_authentication(client_for, method, path, request_kwargs):
    response = getattr(client_for(), method)(path, **request_kwargs)

    assert response.status_code == 401


@pytest.mark.parametrize("role,expected", [("doctor", 201), ("admin", 201), ("patient", 403)])
def test_http_care_plan_create_role_and_caseload(monkeypatch, client_for, role, expected):
    from app.services.care_plan_service import CarePlanService

    install_caseload(monkeypatch)
    create = AsyncMock(return_value=make_care_plan())
    monkeypatch.setattr(CarePlanService, "create_care_plan", create)
    response = client_for(make_user(role)).post("/api/care-plans", json=care_plan_create_body())

    assert response.status_code == expected
    assert create.await_count == (1 if expected == 201 else 0)


def test_http_care_plan_create_denies_doctor_outside_caseload(monkeypatch, client_for):
    from app.services.care_plan_service import CarePlanService

    install_caseload(monkeypatch, assigned=False)
    create = AsyncMock()
    monkeypatch.setattr(CarePlanService, "create_care_plan", create)
    response = client_for(make_user("doctor")).post("/api/care-plans", json=care_plan_create_body())

    assert response.status_code == 404
    create.assert_not_awaited()


@pytest.mark.parametrize("role,expected", [("doctor", 200), ("admin", 200), ("patient", 403)])
def test_http_care_plan_update_role_and_caseload(monkeypatch, client_for, role, expected):
    from app.repositories.care_plan_repository import CarePlanRepository
    from app.services.care_plan_service import CarePlanService

    plan = make_care_plan()
    install_caseload(monkeypatch)
    monkeypatch.setattr(CarePlanRepository, "get_by_id", AsyncMock(return_value=plan))
    update = AsyncMock(return_value=plan)
    monkeypatch.setattr(CarePlanService, "update_care_plan", update)
    response = client_for(make_user(role)).patch(
        "/api/care-plans/care-plan-id", json={"title": "Updated"}
    )

    assert response.status_code == expected
    assert update.await_count == (1 if expected == 200 else 0)


def test_http_care_plan_update_denies_doctor_outside_caseload(monkeypatch, client_for):
    from app.repositories.care_plan_repository import CarePlanRepository
    from app.services.care_plan_service import CarePlanService

    install_caseload(monkeypatch, assigned=False)
    monkeypatch.setattr(CarePlanRepository, "get_by_id", AsyncMock(return_value=make_care_plan()))
    update = AsyncMock()
    monkeypatch.setattr(CarePlanService, "update_care_plan", update)
    response = client_for(make_user("doctor")).patch(
        "/api/care-plans/care-plan-id", json={"title": "Updated"}
    )

    assert response.status_code == 404
    update.assert_not_awaited()


@pytest.mark.parametrize(
    "path,payload,method_name",
    [
        ("stages/stage-1", {"status": "active"}, "update_stage_status"),
        ("goals/goal-1", {"progress_value": 25, "status": "active"}, "update_goal_progress"),
    ],
)
@pytest.mark.parametrize("assigned,expected", [(True, 200), (False, 404)])
def test_http_care_plan_stage_and_goal_caseload(monkeypatch, client_for, path, payload, method_name, assigned, expected):
    from app.repositories.care_plan_repository import CarePlanRepository
    from app.services.care_plan_service import CarePlanService

    install_caseload(monkeypatch, assigned=assigned)
    plan = make_care_plan()
    monkeypatch.setattr(CarePlanRepository, "get_by_id", AsyncMock(return_value=plan))
    update = AsyncMock(return_value=plan)
    monkeypatch.setattr(CarePlanService, method_name, update)
    response = client_for(make_user("doctor")).patch(
        f"/api/care-plans/care-plan-id/{path}", json=payload
    )

    assert response.status_code == expected
    assert update.await_count == (1 if expected == 200 else 0)


@pytest.mark.parametrize("role,expected", [("doctor", 200), ("admin", 200), ("patient", 403)])
def test_http_exercise_assignment_create_role_and_caseload(monkeypatch, client_for, role, expected):
    from app.services.exercise_service import ExerciseService

    install_caseload(monkeypatch)
    create = AsyncMock(return_value=make_assignment())
    monkeypatch.setattr(ExerciseService, "create_assignment", create)
    response = client_for(make_user(role)).post(
        "/api/exercise-assignments", json=exercise_create_body()
    )

    assert response.status_code == expected
    assert create.await_count == (1 if expected == 200 else 0)


def test_http_exercise_assignment_create_denies_unassigned_doctor(monkeypatch, client_for):
    from app.services.exercise_service import ExerciseService

    install_caseload(monkeypatch, assigned=False)
    create = AsyncMock()
    monkeypatch.setattr(ExerciseService, "create_assignment", create)
    response = client_for(make_user("doctor")).post(
        "/api/exercise-assignments", json=exercise_create_body()
    )

    assert response.status_code == 404
    create.assert_not_awaited()


@pytest.mark.parametrize("operation", ["get", "patch"])
def test_http_exercise_assignment_read_and_update_require_doctor_caseload(monkeypatch, client_for, operation):
    from app.services.exercise_service import ExerciseService

    install_caseload(monkeypatch, assigned=False)
    get_assignment = AsyncMock(return_value=make_assignment())
    update = AsyncMock()
    monkeypatch.setattr(ExerciseService, "get_assignment", get_assignment)
    monkeypatch.setattr(ExerciseService, "update_assignment", update)
    if operation == "get":
        response = client_for(make_user("doctor")).get("/api/exercise-assignments/assignment-id")
    else:
        response = client_for(make_user("doctor")).patch(
            "/api/exercise-assignments/assignment-id", json={"reps": 10}
        )

    assert response.status_code == 404
    update.assert_not_awaited()


@pytest.mark.parametrize("role,assigned,expected", [("doctor", True, 200), ("doctor", False, 404), ("admin", True, 200)])
def test_http_exercise_assignment_update_role_caseload_and_admin_policy(monkeypatch, client_for, role, assigned, expected):
    from app.repositories.exercise_repository import ExerciseRepository
    from app.services.exercise_service import ExerciseService

    install_caseload(monkeypatch, assigned=assigned)
    record = make_assignment()
    monkeypatch.setattr(ExerciseService, "get_assignment", AsyncMock(return_value=record))
    monkeypatch.setattr(ExerciseRepository, "get_assignment_by_id", AsyncMock(side_effect=[record, record]))
    update = AsyncMock(wraps=ExerciseService.update_assignment)
    # Keep the actual service transition/role behavior while the repository is isolated.
    monkeypatch.setattr(ExerciseService, "update_assignment", update)
    response = client_for(make_user(role)).patch(
        "/api/exercise-assignments/assignment-id", json={"reps": 10}
    )

    assert response.status_code == expected
    assert update.await_count == (1 if expected == 200 else 0)


@pytest.mark.parametrize("role,expected", [("doctor", 201), ("admin", 201), ("patient", 403)])
def test_http_report_create_role_and_caseload(monkeypatch, client_for, role, expected):
    from app.services.report_service import ReportService

    install_caseload(monkeypatch)
    create = AsyncMock(return_value=make_report())
    monkeypatch.setattr(ReportService, "create_report", create)
    response = client_for(make_user(role)).post("/api/reports", data=report_form())

    assert response.status_code == expected
    assert create.await_count == (1 if expected == 201 else 0)


def test_http_report_create_denies_unassigned_doctor(monkeypatch, client_for):
    from app.services.report_service import ReportService

    install_caseload(monkeypatch, assigned=False)
    create = AsyncMock()
    monkeypatch.setattr(ReportService, "create_report", create)
    response = client_for(make_user("doctor")).post("/api/reports", data=report_form())

    assert response.status_code == 404
    create.assert_not_awaited()


@pytest.mark.parametrize("role,assigned,owns_assignment,payload,expected", [
    ("patient", True, True, {"status": "in_progress"}, 200),
    ("patient", True, True, {"reps": 10}, 403),
    ("patient", True, False, {"status": "in_progress"}, 404),
    ("doctor", True, True, {"reps": 10}, 200),
    ("doctor", False, True, {"reps": 10}, 404),
    ("admin", False, True, {"reps": 10}, 200),
])
def test_http_exercise_assignment_update_ownership_and_roles(monkeypatch, client_for, role, assigned, owns_assignment, payload, expected):
    from app.repositories.exercise_repository import ExerciseRepository
    from app.repositories.profile_repository import ProfileRepository
    from app.services.exercise_service import ExerciseService

    install_caseload(monkeypatch, assigned=assigned)
    record = make_assignment("patient-profile" if owns_assignment else "another-patient-profile")
    patient_profile = SimpleNamespace(id="patient-profile", user_id="patient-user")
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient_profile))
    monkeypatch.setattr(ExerciseService, "get_assignment", AsyncMock(return_value=record))
    monkeypatch.setattr(ExerciseRepository, "get_assignment_by_id", AsyncMock(side_effect=[record, record]))
    response = client_for(make_user(role, "patient-user" if role == "patient" else f"{role}-user")).patch(
        "/api/exercise-assignments/assignment-id", json=payload
    )

    assert response.status_code == expected
    if response.status_code == 200:
        if "status" in payload:
            assert response.json()["status"] == "in_progress"
        if "reps" in payload:
            assert response.json()["reps"] == 10
