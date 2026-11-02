"""Offline contracts for the six remaining administrator work queues."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from beanie import PydanticObjectId

from app.main import app
from app.middleware.auth import get_current_user
from app.api.users import get_admin_patient_history, list_laboratorians, list_public_doctors
from app.core.pagination import PageWindow
from app.models.user import User
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.exercise import Exercise
from app.models.exercise import ExerciseAssignment
from app.models.care_plan import CarePlan
from app.models.lab_request import LabRequest
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.demo_service_repository import DemoServiceRepository
from app.repositories.exercise_repository import ExerciseRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointment import AppointmentOut
from app.services.admin_patient_history_service import AdminPatientHistoryService
from app.services.appointment_service import AppointmentService
from app.services.user_service import UserService


PATIENT = "507f1f77bcf86cd799439011"
DOCTOR = "507f1f77bcf86cd799439012"


def fake_collection(rows=None):
    collection = MagicMock()
    collection.aggregate.return_value.to_list = AsyncMock(return_value=rows or [])
    collection.find.return_value.to_list = AsyncMock(return_value=rows or [])
    return collection


@pytest.mark.asyncio
async def test_public_doctor_search_uses_only_published_profile_fields_and_is_bounded(monkeypatch):
    collection = fake_collection()
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)

    assert await ProfileRepository.search_doctors(
        "fictional 1201",
        PageWindow(25, 50),
        active_only=True,
        home_visits_only=True,
        include_email_in_search=False,
    ) == []

    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0]["$match"] == {"role": "doctor", "is_active": True}
    public_search = next(
        stage["$match"]["$or"] for stage in pipeline
        if "$or" in stage.get("$match", {})
    )
    assert {next(iter(predicate)) for predicate in public_search} == {
        "full_name", "profile.specialization", "profile.qualifications", "profile.specialties",
    }
    assert all("email" not in next(iter(predicate)) for predicate in public_search)
    assert {"$match": {"profile.accepts_home_visits": {"$ne": False}}} in pipeline
    assert next(stage["$skip"] for stage in pipeline if "$skip" in stage) == 1200
    assert next(stage["$limit"] for stage in pipeline if "$limit" in stage) == 50


@pytest.mark.asyncio
async def test_public_doctor_and_laboratorian_routes_pass_bounded_pages(monkeypatch):
    public_search = AsyncMock(return_value=[])
    laboratory_search = AsyncMock(return_value=[])
    monkeypatch.setattr(UserService, "search_public_doctors", public_search)
    monkeypatch.setattr(UserService, "search_laboratorians", laboratory_search)

    assert await list_public_doctors(
        page=21, page_size=50, search=" Fictional ", home_visits_only=True,
    ) == []
    assert await list_laboratorians(
        current_user=SimpleNamespace(role="admin"),
        page=21, page_size=50, search=" Laboratory ",
    ) == []

    public_search.assert_awaited_once_with(
        "Fictional", PageWindow(21, 50), home_visits_only=True,
    )
    laboratory_search.assert_awaited_once_with("Laboratory", PageWindow(21, 50))


@pytest.mark.asyncio
async def test_patient_search_filters_before_page_and_scopes_clinician(monkeypatch):
    collection = fake_collection()
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)
    assert await ProfileRepository.search_patients("fictional 1201", PageWindow(25, 50), doctor_id=DOCTOR) == []
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0]["$match"]["role"] == "patient"
    assert pipeline[0]["$match"]["$or"][0]["full_name"]["$regex"] == "fictional\\ 1201"
    assert any(stage.get("$lookup", {}).get("from") == "appointments" for stage in pipeline)
    assert next(stage["$skip"] for stage in pipeline if "$skip" in stage) == 1200
    assert next(stage["$limit"] for stage in pipeline if "$limit" in stage) == 50
    assert pipeline.index(next(stage for stage in pipeline if "$sort" in stage)) < pipeline.index({"$skip": 1200})


@pytest.mark.asyncio
async def test_patient_search_returns_a_fictional_record_beyond_1000(monkeypatch):
    user_id = PydanticObjectId("507f1f77bcf86cd799439099")
    row = {"_id": user_id, "full_name": "Fictional Patient 1201",
           "email": "fictional1201@example.invalid", "is_active": True,
           "profile": {"_id": PydanticObjectId(PATIENT), "user_id": user_id,
                       "phone": None, "subscription_status": "active"}}
    collection = fake_collection([row])
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)
    monkeypatch.setattr(Patient, "model_validate", staticmethod(lambda doc: SimpleNamespace(
        id=doc["_id"], user_id=doc["user_id"], phone=doc["phone"],
        subscription_status=doc["subscription_status"], date_of_birth=None, gender=None,
    )))
    result = await ProfileRepository.search_patients("1201", PageWindow(25, 50))
    assert len(result) == 1
    assert str(result[0][0].id) == PATIENT
    assert result[0][1].full_name == "Fictional Patient 1201"
    assert next(stage["$skip"] for stage in collection.aggregate.call_args.args[0]
                if "$skip" in stage) == 1200


@pytest.mark.asyncio
async def test_doctor_search_applies_home_visit_eligibility_before_page(monkeypatch):
    collection = fake_collection()
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)
    await ProfileRepository.search_doctors("fictional", PageWindow(21, 50), home_visits_only=True)
    pipeline = collection.aggregate.call_args.args[0]
    eligibility = next(i for i, stage in enumerate(pipeline)
                       if stage.get("$match", {}).get("profile.accepts_home_visits"))
    skip = next(i for i, stage in enumerate(pipeline) if "$skip" in stage)
    assert eligibility < skip
    assert pipeline[skip]["$skip"] == 1000


@pytest.mark.asyncio
async def test_clinician_search_returns_no_patients_without_profile(monkeypatch):
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=None))
    search = AsyncMock()
    monkeypatch.setattr(ProfileRepository, "search_patients", search)
    assert await UserService.search_patients("fictional", PageWindow(1, 50), doctor_user_id=DOCTOR) == []
    search.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("assigned", [False, True])
async def test_doctor_direct_patient_lookup_hides_foreign_or_missing(monkeypatch, assigned):
    from fastapi import HTTPException
    doctor = SimpleNamespace(id=PydanticObjectId(DOCTOR))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "has_assigned_patient", AsyncMock(return_value=assigned))
    profile = AsyncMock(return_value=None)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", profile)
    with pytest.raises(HTTPException) as error:
        await UserService.get_doctor_patient(DOCTOR, PATIENT)
    assert error.value.status_code == 404
    assert error.value.detail == "Patient not found"
    if assigned:
        profile.assert_awaited_once_with(PATIENT)
    else:
        profile.assert_not_awaited()


@pytest.mark.asyncio
async def test_doctor_detail_route_is_role_restricted(monkeypatch):
    getter = AsyncMock(return_value={"id": PATIENT, "full_name": "Fictional Patient"})
    monkeypatch.setattr(UserService, "get_doctor_patient", getter)
    for role, expected in (("doctor", 200), ("admin", 403), ("patient", 403)):
        app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(
            id=PydanticObjectId(DOCTOR), role=role, is_active=True,
        )
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get(f"/api/users/doctor/patients/{PATIENT}")
        assert response.status_code == expected
        if role == "doctor":
            assert response.headers["cache-control"] == "private, no-store"
    app.dependency_overrides.pop(get_current_user, None)
    getter.assert_awaited_once_with(DOCTOR, PATIENT)


@pytest.mark.asyncio
async def test_search_route_keeps_role_scope(monkeypatch):
    calls = AsyncMock(return_value=[])
    monkeypatch.setattr(UserService, "search_patients", calls)
    for role, expected in (("doctor", 200), ("admin", 200), ("patient", 403), ("receptionist", 403)):
        app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(
            id=PydanticObjectId(DOCTOR), role=role, is_active=True,
        )
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get("/api/users/patients", params={"search": "fictional", "page": 25})
        assert response.status_code == expected
    app.dependency_overrides.pop(get_current_user, None)
    assert calls.await_count == 2
    assert calls.await_args_list[0].kwargs["doctor_user_id"] == DOCTOR
    assert calls.await_args_list[1].kwargs["doctor_user_id"] is None


@pytest.mark.asyncio
async def test_history_date_range_uses_patient_scoped_database_filters(monkeypatch):
    query = MagicMock()
    query.sort.return_value.skip.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
    appointment_find = MagicMock(return_value=query)
    report_find = MagicMock(return_value=query)
    monkeypatch.setattr(Appointment, "find", appointment_find)
    monkeypatch.setattr(LabRequest, "find", report_find)
    window = PageWindow(21, 50)
    await AppointmentRepository.list_page_by_patient_id(PATIENT, window,
                                                        start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    await LabRequestRepository.list_page_released_for_patients([PATIENT], window,
                                                               start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    appointments = appointment_find.call_args.args[0]
    reports = report_find.call_args.args[0]
    assert appointments["patient_id"] == PydanticObjectId(PATIENT)
    assert appointments["appointment_date"] == {
        "$gte": datetime(2026, 1, 1), "$lt": datetime(2026, 2, 1),
    }
    assert reports["patient_id"]["$in"] == [PydanticObjectId(PATIENT)]
    assert reports["report_status"] == "released"
    assert reports["report_released_at"]["$lt"] == datetime(2026, 2, 1)
    assert query.sort.return_value.skip.call_args.args[0] == 1000
    assert query.sort.return_value.skip.return_value.limit.call_args.args[0] == 50


@pytest.mark.asyncio
async def test_history_route_passes_dates_without_cross_patient_expansion(monkeypatch):
    history = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setattr(AdminPatientHistoryService, "get_patient_history", history)
    await get_admin_patient_history(PATIENT, SimpleNamespace(role="admin"), 3, 50,
                                    date(2026, 1, 1), date(2026, 1, 31))
    history.assert_awaited_once_with(PATIENT, PageWindow(3, 50),
                                     date(2026, 1, 1), date(2026, 1, 31))


@pytest.mark.asyncio
async def test_history_page_formats_fifty_visits_with_two_bulk_lookups(monkeypatch):
    patient_id = PydanticObjectId(PATIENT)
    doctor_id = PydanticObjectId(DOCTOR)
    patient_user_id = PydanticObjectId("507f1f77bcf86cd799439099")
    doctor_user_id = PydanticObjectId("507f1f77bcf86cd799439098")
    patient = SimpleNamespace(id=patient_id, user_id=patient_user_id,
                              phone=None, date_of_birth=None, gender=None,
                              subscription_status="active", admin_edit_audit=[])
    patient_user = SimpleNamespace(full_name="Fictional Patient", email="patient@example.invalid")
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    user_lookup = AsyncMock(return_value=patient_user)
    monkeypatch.setattr(UserRepository, "get_by_id", user_lookup)
    rows = [SimpleNamespace(patient_id=patient_id, doctor_id=doctor_id) for _ in range(50)]
    monkeypatch.setattr(AppointmentRepository, "list_page_by_patient_id", AsyncMock(return_value=rows))
    monkeypatch.setattr(LabRequestRepository, "list_page_released_for_patients", AsyncMock(return_value=[]))
    doctor_collection = fake_collection([{"_id": doctor_id, "user_id": doctor_user_id}])
    doctor_user_collection = fake_collection([{"_id": doctor_user_id, "full_name": "Fictional Doctor"}])
    monkeypatch.setattr(Doctor, "get_pymongo_collection", lambda: doctor_collection)
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: doctor_user_collection)
    when = datetime(2026, 11, 5)
    formatted = AppointmentOut(
        id="507f1f77bcf86cd799439097", patient_id=PATIENT, patient_name="Fictional Patient",
        doctor_id=DOCTOR, doctor_name="Fictional Doctor", appointment_date=when,
        clinic_timezone="Asia/Kolkata", time_slot="09:00 AM", reason="Fictional",
        status="scheduled", billing_status="pending", billing_amount=0,
        can_patient_cancel=True, cancellation_message="Fictional", created_at=when,
    )
    formatter = AsyncMock(return_value=formatted)
    monkeypatch.setattr(AppointmentService, "_format_appointment", formatter)
    result = await AdminPatientHistoryService.get_patient_history(PATIENT, PageWindow(25, 50))
    assert len(result.appointments) == 50
    assert formatter.await_count == 50
    assert doctor_collection.find.call_count == 1
    assert doctor_user_collection.find.call_count == 1
    user_lookup.assert_awaited_once_with(str(patient_user_id))


@pytest.mark.asyncio
async def test_scheduled_home_visits_filter_before_pagination(monkeypatch):
    collection = fake_collection()
    monkeypatch.setattr(Appointment, "get_pymongo_collection", lambda: collection)
    await AppointmentRepository.list_page_scheduled_home_visits(PageWindow(22, 50))
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {"service_mode": "home_visit", "status": "scheduled"}}
    assert pipeline[1] == {"$sort": {"appointment_date": 1, "_id": 1}}
    assert pipeline[2:4] == [{"$skip": 1050}, {"$limit": 50}]
    assert {stage["$lookup"]["from"] for stage in pipeline if "$lookup" in stage} == {"patients", "users"}
    assert pipeline[-1]["$project"].keys() >= {"patient_name", "doctor_id", "time_slot"}


@pytest.mark.asyncio
async def test_home_visit_booking_projection_retains_pending_assignment(monkeypatch):
    rows = [{"_id": PydanticObjectId(PATIENT), "patient_name": "Fictional Patient",
             "doctor_id": PydanticObjectId(DOCTOR), "doctor_assignment_pending": True,
             "appointment_date": datetime(2026, 11, 5), "time_slot": "09:00 AM"}]
    monkeypatch.setattr(AppointmentRepository, "list_page_scheduled_home_visits", AsyncMock(return_value=rows))
    result = await AppointmentService.list_scheduled_home_visits(PageWindow(1, 50))
    assert len(result) == 1
    assert result[0].doctor_id == ""
    assert result[0].doctor_assignment_pending is True
    assert result[0].patient_name == "Fictional Patient"


@pytest.mark.asyncio
async def test_scheduled_home_visits_route_is_admin_only(monkeypatch):
    getter = AsyncMock(return_value=[])
    monkeypatch.setattr(AppointmentService, "list_scheduled_home_visits", getter)
    for role, expected in (("admin", 200), ("doctor", 403), ("patient", 403), ("receptionist", 403)):
        app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(
            id=PydanticObjectId(DOCTOR), role=role, is_active=True,
        )
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get("/api/home-visit-bookings/admin/scheduled", params={"page": 21})
        assert response.status_code == expected
        if role == "admin":
            assert response.headers["cache-control"] == "private, no-store"
    app.dependency_overrides.pop(get_current_user, None)
    getter.assert_awaited_once_with(PageWindow(21, 50))


@pytest.mark.asyncio
async def test_demo_entitlement_search_bounded_and_joined(monkeypatch):
    collection = fake_collection()
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)
    await DemoServiceRepository.search_entitlements(PageWindow(25, 50), "fictional")
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0]["$match"]["role"] == "patient"
    assert {stage["$lookup"]["from"] for stage in pipeline if "$lookup" in stage} == {"patients", "demo_entitlements"}
    assert next(stage["$skip"] for stage in pipeline if "$skip" in stage) == 1200
    assert next(stage["$limit"] for stage in pipeline if "$limit" in stage) == 50


@pytest.mark.asyncio
async def test_exercise_selector_search_is_bounded_and_escaped(monkeypatch):
    query = MagicMock()
    query.sort.return_value.skip.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
    finder = MagicMock(return_value=query)
    monkeypatch.setattr(Exercise, "find", finder)
    await ExerciseRepository.list_page_exercises(True, PageWindow(21, 50), search="fictional.*")
    assert finder.call_args.args[0] == {"active": True,
                                        "title": {"$regex": "fictional\\.\\*", "$options": "i"}}
    assert query.sort.return_value.skip.call_args.args == (1000,)


@pytest.mark.asyncio
async def test_assignment_page_reaches_fictional_record_1201_without_retaining_prior_pages(monkeypatch):
    records = [SimpleNamespace(id=f"fictional-{index}") for index in range(1205)]

    class Query:
        offset = 0
        size = 0

        def sort(self, *keys):
            assert keys == ("-assigned_at", "-_id")
            return self

        def skip(self, offset):
            self.offset = offset
            return self

        def limit(self, size):
            self.size = size
            return self

        async def to_list(self):
            return records[self.offset:self.offset + self.size]

    finder = MagicMock(return_value=Query())
    monkeypatch.setattr(ExerciseAssignment, "find", finder)
    page = await ExerciseRepository.list_page_assignments_by_patient(PATIENT, PageWindow(25, 50))
    assert [item.id for item in page] == [f"fictional-{index}" for index in range(1200, 1205)]
    assert finder.call_args.args[0] == {"patient_id": PydanticObjectId(PATIENT)}


@pytest.mark.asyncio
async def test_assignment_labels_use_bounded_bulk_projections(monkeypatch):
    exercise_collection = fake_collection([{"_id": PydanticObjectId(DOCTOR), "title": "Fictional movement"}])
    plan_collection = fake_collection([{"_id": PydanticObjectId(PATIENT), "title": "Fictional plan",
                                        "stages": [{"stage_id": "stage-1", "title": "First stage"}]}])
    monkeypatch.setattr(Exercise, "get_pymongo_collection", lambda: exercise_collection)
    monkeypatch.setattr(CarePlan, "get_pymongo_collection", lambda: plan_collection)
    assignments = [SimpleNamespace(exercise_id=PydanticObjectId(DOCTOR),
                                   care_plan_id=PydanticObjectId(PATIENT)) for _ in range(50)]
    exercises, plans = await ExerciseRepository.assignment_labels(assignments)
    assert exercises[PydanticObjectId(DOCTOR)] == "Fictional movement"
    assert plans[PydanticObjectId(PATIENT)]["stages"][0]["title"] == "First stage"
    assert exercise_collection.find.call_args.args[1] == {"title": 1}
    assert plan_collection.find.call_args.args[1] == {"title": 1, "stages.stage_id": 1,
                                                     "stages.title": 1}
    assert exercise_collection.find.return_value.to_list.call_args.kwargs["length"] == 1
    assert plan_collection.find.return_value.to_list.call_args.kwargs["length"] == 1


@pytest.mark.asyncio
async def test_booking_service_rechecks_selected_patient_and_doctor(monkeypatch):
    from app.schemas.appointment import AdminAppointmentCreate
    from fastapi import HTTPException
    from app.repositories.profile_repository import ProfileRepository
    schema = AdminAppointmentCreate(patient_id=PATIENT, doctor_id=DOCTOR,
                                    appointment_date=date(2026, 11, 5), time_slot="09:00 AM", reason="Fictional")
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as error:
        await AppointmentService.create_admin_appointment(schema)
    assert error.value.status_code == 404
