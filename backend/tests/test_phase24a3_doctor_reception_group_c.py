"""Offline contracts for bounded doctor and reception workspaces."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from app.main import app
from app.middleware.auth import get_current_user
from app.core.pagination import PageWindow
from app.models.appointment import Appointment
from app.models.home_visit_request import HomeVisitRequest
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.demo_service_repository import DemoServiceRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.services.appointment_service import AppointmentService
from app.services.doctor_history_service import DoctorHistoryService


DOCTOR = "507f1f77bcf86cd799439012"
OTHER_DOCTOR = "507f1f77bcf86cd799439013"
PATIENT = "507f1f77bcf86cd799439011"


def find_probe(monkeypatch):
    query = MagicMock()
    query.sort.return_value.skip.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
    find = MagicMock(return_value=query)
    monkeypatch.setattr(Appointment, "find", find)
    return find, query


def aggregate_probe(monkeypatch, rows):
    collection = MagicMock()
    collection.aggregate.return_value.to_list = AsyncMock(return_value=rows)
    monkeypatch.setattr(Appointment, "get_pymongo_collection", lambda: collection)
    return collection


@pytest.mark.asyncio
async def test_doctor_summary_matches_identity_before_aggregation(monkeypatch):
    collection = aggregate_probe(monkeypatch, [{
        "statuses": [{"_id": "scheduled", "count": 601},
                     {"_id": "in_progress", "count": 2},
                     {"_id": "completed", "count": 1201}],
        "patients": [{"count": 1001}],
    }])
    assert await AppointmentRepository.doctor_dashboard_summary(DOCTOR) == {
        "open_visits": 603, "completed_sessions": 1201, "assigned_patients": 1001,
    }
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {
        "doctor_id": PydanticObjectId(DOCTOR),
        "doctor_assignment_pending": {"$ne": True},
    }}
    assert "$facet" in pipeline[1]
    collection.aggregate.return_value.to_list.return_value = [{"statuses": [], "patients": []}]
    assert await AppointmentRepository.doctor_dashboard_summary(OTHER_DOCTOR) == {
        "open_visits": 0, "completed_sessions": 0, "assigned_patients": 0,
    }


@pytest.mark.asyncio
async def test_doctor_summary_without_profile_never_queries_appointments(monkeypatch):
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=None))
    summary = AsyncMock()
    monkeypatch.setattr(AppointmentRepository, "doctor_dashboard_summary", summary)
    assert (await AppointmentService.doctor_dashboard_summary(DOCTOR))["assigned_patients"] == 0
    summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_doctor_agenda_filters_before_stable_page(monkeypatch):
    find, query = find_probe(monkeypatch)
    await AppointmentRepository.list_page_by_doctor_id(
        DOCTOR, PageWindow(25, 50), ["scheduled", "in_progress"],
        date(2026, 1, 1), date(2026, 1, 31),
    )
    predicate = find.call_args.args[0]
    assert predicate["doctor_id"] == PydanticObjectId(DOCTOR)
    assert predicate["doctor_assignment_pending"] == {"$ne": True}
    assert predicate["status"] == {"$in": ["scheduled", "in_progress"]}
    assert predicate["appointment_date"] == {
        "$gte": datetime(2026, 1, 1), "$lt": datetime(2026, 2, 1),
    }
    query.sort.assert_called_once_with("-appointment_date", "-_id")
    query.sort.return_value.skip.assert_called_once_with(1200)
    query.sort.return_value.skip.return_value.limit.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_history_assignment_checked_before_patient_or_report_lookup(monkeypatch):
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id=PydanticObjectId(DOCTOR)),
    ))
    monkeypatch.setattr(AppointmentRepository, "has_assigned_patient", AsyncMock(return_value=False))
    patient_lookup = AsyncMock()
    report_lookup = AsyncMock()
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", patient_lookup)
    monkeypatch.setattr(LabRequestRepository, "list_page_released_for_patients", report_lookup)
    for patient_id in (PATIENT, "invalid-id"):
        with pytest.raises(HTTPException) as error:
            await DoctorHistoryService.get_assigned_patient_history(DOCTOR, patient_id, PageWindow(21, 50))
        assert error.value.status_code == 404
        assert error.value.detail == "Assigned patient history not found"
    patient_lookup.assert_not_awaited()
    report_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_history_scopes_status_and_date_before_paging(monkeypatch):
    find, query = find_probe(monkeypatch)
    await AppointmentRepository.list_page_by_doctor_and_patient(
        DOCTOR, PATIENT, PageWindow(21, 50), ["completed"],
        date(2026, 2, 1), date(2026, 2, 28),
    )
    predicate = find.call_args.args[0]
    assert predicate["doctor_id"] == PydanticObjectId(DOCTOR)
    assert predicate["patient_id"] == PydanticObjectId(PATIENT)
    assert predicate["doctor_assignment_pending"] == {"$ne": True}
    assert predicate["status"] == {"$in": ["completed"]}
    assert predicate["appointment_date"] == {
        "$gte": datetime(2026, 2, 1), "$lt": datetime(2026, 3, 1),
    }
    query.sort.assert_called_once_with("-appointment_date", "-_id")
    query.sort.return_value.skip.assert_called_once_with(1000)


@pytest.mark.asyncio
async def test_assigned_history_uses_doctor_and_patient_scope_for_both_pages(monkeypatch):
    doctor = SimpleNamespace(id=PydanticObjectId(DOCTOR), user_id=PydanticObjectId(OTHER_DOCTOR))
    patient = SimpleNamespace(id=PydanticObjectId(PATIENT), user_id=PydanticObjectId(PATIENT),
                              phone=None, date_of_birth=None, gender=None)
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    assignment = AsyncMock(return_value=True)
    appointments = AsyncMock(return_value=[])
    reports = AsyncMock(return_value=[])
    monkeypatch.setattr(AppointmentRepository, "has_assigned_patient", assignment)
    monkeypatch.setattr(AppointmentRepository, "list_page_by_doctor_and_patient", appointments)
    monkeypatch.setattr(LabRequestRepository, "list_page_released_for_patients", reports)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=SimpleNamespace(full_name="Fictional Patient")))
    result = await DoctorHistoryService.get_assigned_patient_history(
        DOCTOR, PATIENT, PageWindow(21, 50), status_group="completed",
        start_date=date(2026, 1, 1), end_date=date(2026, 1, 31),
    )
    assert result.patient.full_name == "Fictional Patient"
    assert result.appointments == result.reports == []
    assignment.assert_awaited_once_with(DOCTOR, PATIENT)
    appointments.assert_awaited_once_with(
        DOCTOR, PATIENT, PageWindow(21, 50), statuses=["completed"],
        start_date=date(2026, 1, 1), end_date=date(2026, 1, 31),
    )
    reports.assert_awaited_once_with(
        [PATIENT], PageWindow(21, 50), start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )


@pytest.mark.asyncio
async def test_page_profile_enrichment_uses_three_bounded_bulk_queries(monkeypatch):
    from app.models.patient import Patient
    from app.models.doctor import Doctor
    from app.models.user import User

    collections = []
    for model in (Patient, Doctor, User):
        collection = MagicMock()
        collection.find.return_value.to_list = AsyncMock(return_value=[])
        monkeypatch.setattr(model, "get_pymongo_collection", lambda collection=collection: collection)
        collections.append(collection)
    records = [SimpleNamespace(patient_id=PydanticObjectId(PATIENT),
                               doctor_id=PydanticObjectId(DOCTOR)) for _ in range(50)]
    await AppointmentService._page_profile_maps(records)
    assert collections[0].find.call_count == 1
    assert collections[1].find.call_count == 1
    assert collections[2].find.call_count == 0  # no matching profiles
    assert collections[0].find.return_value.to_list.await_args.kwargs["length"] == 1
    assert collections[1].find.return_value.to_list.await_args.kwargs["length"] == 1


@pytest.mark.asyncio
async def test_reception_summary_and_page_filter_active_visits_in_database(monkeypatch):
    collection = aggregate_probe(monkeypatch, [{"active_appointments": 1201}])
    assert await AppointmentRepository.reception_schedule_summary(
        date(2026, 1, 1), date(2026, 1, 31),
    ) == {"active_appointments": 1201}
    match = collection.aggregate.call_args.args[0][0]["$match"]
    assert match["status"] == {"$in": ["scheduled", "in_progress"]}
    assert match["appointment_date"]["$lt"] == datetime(2026, 2, 1)
    page_collection = MagicMock()
    query = page_collection.find.return_value
    query.sort.return_value.skip.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
    monkeypatch.setattr(Appointment, "get_pymongo_collection", lambda: page_collection)
    await AppointmentRepository.list_page_operational_schedule(
        PageWindow(21, 50), date(2026, 1, 1), date(2026, 1, 31),
    )
    predicate, projection = page_collection.find.call_args.args
    assert predicate == match
    assert "reason" not in projection and "billing_status" not in projection
    assert "patient_id" in projection and "time_slot" in projection
    query.sort.assert_called_once_with([("appointment_date", 1), ("_id", 1)])
    query.sort.return_value.skip.assert_called_once_with(1000)
    query.sort.return_value.skip.return_value.limit.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_reception_home_queue_projects_only_coordination_fields(monkeypatch):
    collection = MagicMock()
    query = collection.find.return_value
    query.sort.return_value.skip.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
    monkeypatch.setattr(HomeVisitRequest, "get_pymongo_collection", lambda: collection)
    assert await DemoServiceRepository.list_page_reception_coordination(PageWindow(21, 50)) == []
    predicate, projection = collection.find.call_args.args
    assert predicate == {"status": "approved_for_coordination"}
    assert {"patient_id", "preferred_doctor_id", "home_address", "city"} <= projection.keys()
    assert {"reason", "symptoms", "billing_status", "pain_severity"}.isdisjoint(projection)
    query.sort.assert_called_once_with([("created_at", -1), ("_id", -1)])
    query.sort.return_value.skip.assert_called_once_with(1000)
    query.sort.return_value.skip.return_value.limit.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_summary_routes_are_role_restricted_and_private(monkeypatch):
    doctor_summary = AsyncMock(return_value={
        "open_visits": 1, "completed_sessions": 2, "assigned_patients": 1,
    })
    reception_summary = AsyncMock(return_value={"active_appointments": 3})
    monkeypatch.setattr(AppointmentService, "doctor_dashboard_summary", doctor_summary)
    monkeypatch.setattr(AppointmentService, "reception_schedule_summary", reception_summary)
    try:
        for role in ("doctor", "receptionist", "patient", "admin"):
            app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(
                id=PydanticObjectId(DOCTOR), role=role, is_active=True,
            )
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                doctor_response = await client.get("/api/appointments/doctor/summary")
                reception_response = await client.get("/api/appointments/reception/summary")
            assert doctor_response.status_code == (200 if role == "doctor" else 403)
            assert reception_response.status_code == (200 if role == "receptionist" else 403)
            if role == "doctor":
                assert doctor_response.headers["cache-control"] == "private, no-store"
            if role == "receptionist":
                assert reception_response.headers["cache-control"] == "private, no-store"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    doctor_summary.assert_awaited_once_with(DOCTOR)
    reception_summary.assert_awaited_once_with(None, None)


@pytest.mark.asyncio
async def test_doctor_history_route_rejects_bad_filters_and_reception_cannot_read_it():
    try:
        for role in ("doctor", "receptionist"):
            app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(
                id=PydanticObjectId(DOCTOR), role=role, is_active=True,
            )
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                response = await client.get(f"/api/users/doctor/patients/{PATIENT}/history", params={
                    "start_date": "2026-02-01", "end_date": "2026-01-01",
                })
            assert response.status_code == (422 if role == "doctor" else 403)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
