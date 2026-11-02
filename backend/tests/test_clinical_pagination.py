"""Offline contracts for bounded clinical list routes and database queries."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import httpx
import pytest

from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageWindow
from app.main import app
from app.middleware.auth import get_current_user
from app.models.appointment import Appointment
from app.models.lab_request import LabRequest
from app.models.report import Report
from app.models.care_plan import CarePlan, CarePlanHistory
from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress
from app.models.home_visit_request import HomeVisitRequest
from app.models.laboratory_booking import LaboratoryBooking
from app.models.notification import Notification
from app.models.patient import Patient
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.care_plan_repository import CarePlanRepository
from app.repositories.demo_service_repository import DemoServiceRepository
from app.repositories.exercise_repository import ExerciseRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.laboratory_booking_repository import LaboratoryBookingRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.report_repository import ReportRepository
from app.services.appointment_service import AppointmentService
from app.services.care_plan_service import CarePlanService
from app.services.exercise_service import ExerciseService
from app.services.home_visit_service import HomeVisitService
from app.services.lab_request_service import LabRequestService
from app.services.laboratory_service import LaboratoryService
from app.services.notification_service import NotificationService
from app.services.report_service import ReportService
from app.services.user_service import UserService
from app.services.admin_patient_history_service import AdminPatientHistoryService
from app.services.doctor_history_service import DoctorHistoryService


PATIENT_ID = PydanticObjectId("507f1f77bcf86cd799439011")
USER_ID = PydanticObjectId("507f1f77bcf86cd799439012")
DOCTOR_ID = PydanticObjectId("507f1f77bcf86cd799439013")

LIST_ROUTES = [
    ("/api/appointments", "patient", AppointmentService, "list_appointments"),
    ("/api/appointments/reception", "receptionist", AppointmentService, "list_reception_schedule"),
    ("/api/reports", "patient", ReportService, "get_reports_by_patient_id"),
    ("/api/lab-requests/me", "patient", LabRequestService, "list_own"),
    ("/api/lab-requests/admin", "admin", LabRequestService, "list_admin"),
    ("/api/lab-requests/laboratory/assigned", "laboratorian", LabRequestService, "list_assigned"),
    ("/api/lab-requests/me/reports", "patient", LabRequestService, "list_patient_released_reports"),
    ("/api/lab-requests/doctor/reports", "doctor", LabRequestService, "list_doctor_released_reports"),
    ("/api/care-plans", "patient", CarePlanService, "get_care_plans_by_patient"),
    ("/api/exercise-assignments", "patient", ExerciseService, "list_assignments_for_patient"),
    ("/api/exercise-progress", "patient", ExerciseService, "list_progress_for_patient"),
    ("/api/laboratory/bookings", "patient", LaboratoryService, "get_bookings_by_patient_id"),
    ("/api/home-visit-requests/me", "patient", HomeVisitService, "list_patient_requests"),
    ("/api/home-visit-requests/admin", "admin", HomeVisitService, "list_admin_requests"),
    ("/api/home-visit-requests/reception", "receptionist", HomeVisitService, "list_reception_requests"),
    ("/api/home-visit-requests/doctor", "doctor", HomeVisitService, "list_doctor_requests"),
    ("/api/notifications", "patient", NotificationService, "get_user_notifications"),
    ("/api/users/patients", "admin", UserService, "search_patients"),
    ("/api/users/reception/patients", "receptionist", UserService, "search_patients"),
]


async def _get(path, params=None):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
    ) as client:
        return await client.get(path, params=params)


def _as_user(monkeypatch, role):
    user = SimpleNamespace(id=USER_ID, role=role, is_active=True)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: user)
    return user


@pytest.mark.asyncio
@pytest.mark.parametrize("path,role,service,method", LIST_ROUTES)
@pytest.mark.parametrize("params,expected", [
    (None, PageWindow(1, DEFAULT_PAGE_SIZE)),
    ({"page": "2", "page_size": str(MAX_PAGE_SIZE)}, PageWindow(2, MAX_PAGE_SIZE)),
])
async def test_clinical_list_routes_pass_bounded_page_to_service(
    monkeypatch, path, role, service, method, params, expected,
):
    _as_user(monkeypatch, role)
    monkeypatch.setattr(
        ProfileRepository, "get_patient_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=PATIENT_ID)),
    )
    monkeypatch.setattr(
        ProfileRepository, "get_doctor_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=DOCTOR_ID)),
    )
    list_service = AsyncMock(return_value=[])
    monkeypatch.setattr(service, method, list_service)

    response = await _get(path, params)

    assert response.status_code == 200
    assert response.json() == []
    list_service.assert_awaited_once()
    assert list_service.await_args.args[-1] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("path,role,service,method", LIST_ROUTES)
@pytest.mark.parametrize("params", [
    {"page": "0"}, {"page": "-1"}, {"page": "1001"},
    {"page": "not-a-number"}, {"page_size": "0"},
    {"page_size": "-1"}, {"page_size": "101"},
])
async def test_invalid_paging_is_rejected_before_clinical_service(
    monkeypatch, path, role, service, method, params,
):
    _as_user(monkeypatch, role)
    monkeypatch.setattr(
        ProfileRepository, "get_patient_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=PATIENT_ID)),
    )
    list_service = AsyncMock()
    monkeypatch.setattr(service, method, list_service)

    response = await _get(path, params)

    assert response.status_code == 422
    list_service.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,role,service,method",
    [item for item in LIST_ROUTES if item[0] not in {"/api/notifications", "/api/exercise-assignments"}],
)
async def test_wrong_role_cannot_page_clinical_list(
    monkeypatch, path, role, service, method,
):
    wrong_role = "receptionist" if role != "receptionist" else "patient"
    _as_user(monkeypatch, wrong_role)
    list_service = AsyncMock()
    monkeypatch.setattr(service, method, list_service)

    response = await _get(path, {"page": 2})

    assert response.status_code == 403
    list_service.assert_not_awaited()


class QueryProbe:
    def __init__(self, items=None):
        self.items = items or []
        self.sort_keys = None
        self.skip_count = None
        self.limit_count = None

    def sort(self, *keys):
        self.sort_keys = keys
        return self

    def skip(self, count):
        self.skip_count = count
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    async def to_list(self, length=None):
        items = self.items
        if not items:
            return []
        if self.sort_keys:
            for key in reversed(self.sort_keys):
                descending = key.startswith("-")
                field = key[1:] if key[0] in "+-" else key
                if field == "_id":
                    field = "id"
                items = sorted(items, key=lambda item: getattr(item, field), reverse=descending)
        return items[self.skip_count:self.skip_count + self.limit_count]


@pytest.mark.asyncio
@pytest.mark.parametrize("repository,method,model,args,sort_keys", [
    (AppointmentRepository, "list_page_all", Appointment, (), ("-appointment_date", "-_id")),
    (AppointmentRepository, "list_page_by_patient_id", Appointment, (str(PATIENT_ID),), ("-appointment_date", "-_id")),
    (AppointmentRepository, "list_page_by_doctor_id", Appointment, (str(DOCTOR_ID),), ("-appointment_date", "-_id")),
    (ReportRepository, "get_page_by_patient_id", Report, (str(PATIENT_ID),), ("-date", "-_id")),
    (LabRequestRepository, "list_page_for_patient", LabRequest, (str(PATIENT_ID),), ("-created_at", "-_id")),
    (LabRequestRepository, "list_page_all", LabRequest, (), ("-created_at", "-_id")),
    (LabRequestRepository, "list_page_for_laboratorian", LabRequest, (str(USER_ID),), ("-updated_at", "-_id")),
    (LabRequestRepository, "list_page_released_for_patients", LabRequest, ([str(PATIENT_ID)],), ("-report_released_at", "-_id")),
    (CarePlanRepository, "get_page_by_patient_id", CarePlan, (str(PATIENT_ID),), ("-created_at", "-_id")),
    (CarePlanRepository, "get_page_history_by_care_plan_id", CarePlanHistory, (str(PATIENT_ID),), ("-created_at", "-_id")),
    (ExerciseRepository, "list_page_exercises", Exercise, (True,), ("+title", "+_id")),
    (ExerciseRepository, "list_page_assignments_by_patient", ExerciseAssignment, (str(PATIENT_ID),), ("-assigned_at", "-_id")),
    (ExerciseRepository, "list_page_assignments_by_care_plan", ExerciseAssignment, (str(PATIENT_ID),), ("-assigned_at", "-_id")),
    (ExerciseRepository, "list_page_progress_by_patient", ExerciseProgress, (str(PATIENT_ID),), ("-completed_at", "-_id")),
    (DemoServiceRepository, "list_page_by_patient", HomeVisitRequest, (str(PATIENT_ID),), ("-created_at", "-_id")),
    (DemoServiceRepository, "list_page_all", HomeVisitRequest, (), ("-created_at", "-_id")),
    (DemoServiceRepository, "list_page_doctor_coordination", HomeVisitRequest, (str(DOCTOR_ID),), ("-created_at", "-_id")),
    (LaboratoryBookingRepository, "get_page_by_patient_id", LaboratoryBooking, (str(PATIENT_ID),), ("-created_at", "-_id")),
    (NotificationRepository, "list_page_by_recipient_id", Notification, (str(USER_ID),), ("-created_at", "-_id")),
    (ProfileRepository, "list_page_patients", Patient, (), ("+_id",)),
    (AppointmentRepository, "list_page_by_doctor_and_patient", Appointment, (str(DOCTOR_ID), str(PATIENT_ID)), ("-appointment_date", "-_id")),
])
async def test_repository_pages_sort_skip_and_limit_in_database_query(
    monkeypatch, repository, method, model, args, sort_keys,
):
    query = QueryProbe()
    find = Mock(return_value=query)
    raw_projection_methods = {
        (LabRequestRepository, "list_page_for_patient"),
        (LabRequestRepository, "list_page_all"),
        (LabRequestRepository, "list_page_for_laboratorian"),
        (DemoServiceRepository, "list_page_by_patient"),
        (DemoServiceRepository, "list_page_all"),
        (DemoServiceRepository, "list_page_doctor_coordination"),
    }
    uses_raw_projection = (repository, method) in raw_projection_methods
    if uses_raw_projection:
        collection = SimpleNamespace(find=find)
        monkeypatch.setattr(model, "get_pymongo_collection", lambda: collection)
    else:
        monkeypatch.setattr(model, "find", find)
    page = PageWindow(3, 17)

    assert await getattr(repository, method)(*args, page) == []

    find.assert_called_once()
    if uses_raw_projection:
        assert query.sort_keys == ([
            (sort_keys[0][1:], -1), ("_id", -1),
        ],)
        assert find.call_args.args[1] in (
            LabRequestRepository._CLINICAL_LIST_PROJECTION,
            DemoServiceRepository._CLINICAL_LIST_PROJECTION,
        )
    else:
        assert query.sort_keys == sort_keys
    assert query.skip_count == 34
    assert query.limit_count == 17
    if method in {
        "list_page_by_patient_id", "get_page_by_patient_id", "list_page_for_patient",
        "list_page_assignments_by_patient", "list_page_progress_by_patient",
        "list_page_by_patient", "list_page_released_for_patients",
    }:
        assert "patient_id" in str(find.call_args.args[0])
        assert str(PATIENT_ID) in str(find.call_args.args[0])
    if method == "list_page_by_doctor_id":
        assert find.call_args.args[0] == {
            "doctor_id": DOCTOR_ID,
            "doctor_assignment_pending": {"$ne": True},
        }
    if method == "list_page_released_for_patients":
        assert find.call_args.args[0] == {
            "patient_id": {"$in": [PATIENT_ID]},
            "report_status": "released",
        }


@pytest.mark.asyncio
async def test_static_tied_dates_have_no_duplicate_report_ids_across_pages(monkeypatch):
    date = datetime(2026, 11, 1, tzinfo=timezone.utc)
    items = [
        SimpleNamespace(id=PydanticObjectId(f"{number:024x}"), date=date)
        for number in range(1, 6)
    ]
    monkeypatch.setattr(Report, "find", Mock(side_effect=lambda *_args: QueryProbe(items)))

    pages = [
        await ReportRepository.get_page_by_patient_id(str(PATIENT_ID), PageWindow(page, 2))
        for page in (1, 2, 3, 4)
    ]

    ids = [str(item.id) for batch in pages for item in batch]
    assert [len(batch) for batch in pages] == [2, 2, 1, 0]
    assert len(ids) == len(set(ids)) == 5
    assert ids == sorted(ids, reverse=True)


@pytest.mark.asyncio
async def test_patient_page_uses_authenticated_profile_not_query_patient_id(monkeypatch):
    _as_user(monkeypatch, "patient")
    monkeypatch.setattr(
        ProfileRepository, "get_patient_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=PATIENT_ID)),
    )
    own = AsyncMock(return_value=[])
    monkeypatch.setattr(LabRequestRepository, "list_page_for_patient", own)

    response = await _get("/api/lab-requests/me", {"page": 2, "patient_id": str(DOCTOR_ID)})

    assert response.status_code == 200
    own.assert_awaited_once_with(str(PATIENT_ID), PageWindow(2, DEFAULT_PAGE_SIZE))


@pytest.mark.asyncio
@pytest.mark.parametrize("path,role,service,method,patient", [
    ("/api/users/patients/507f1f77bcf86cd799439011/history", "admin",
     AdminPatientHistoryService, "get_patient_history",
     {"id": str(PATIENT_ID), "full_name": "Fictional Patient", "email": "fictional@example.test",
      "subscription_status": "active"}),
    ("/api/users/doctor/patients/507f1f77bcf86cd799439011/history", "doctor",
     DoctorHistoryService, "get_assigned_patient_history",
     {"id": str(PATIENT_ID), "full_name": "Fictional Patient"}),
])
async def test_history_routes_pass_bounded_page_and_preserve_role_gate(
    monkeypatch, path, role, service, method, patient,
):
    _as_user(monkeypatch, role)
    history = AsyncMock(return_value={
        "patient": patient, "appointments": [], "reports": [], "profile_audit": [],
    })
    monkeypatch.setattr(service, method, history)
    response = await _get(path, {"page": 2, "page_size": 10})
    assert response.status_code == 200
    assert response.json()["appointments"] == []
    assert history.await_args.args[-1] == PageWindow(2, 10)

    response = await _get(path, {"page_size": 101})
    assert response.status_code == 422
    assert history.await_count == 1

    _as_user(monkeypatch, "patient")
    response = await _get(path)
    assert response.status_code == 403
    assert history.await_count == 1


@pytest.mark.asyncio
async def test_doctor_history_page_checks_assignment_before_page(monkeypatch):
    from app.repositories.user_repository import UserRepository

    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id",
                        AsyncMock(return_value=SimpleNamespace(id=DOCTOR_ID)))
    access = AsyncMock(return_value=False)
    page_query = AsyncMock()
    monkeypatch.setattr(AppointmentRepository, "has_assigned_patient", access)
    monkeypatch.setattr(AppointmentRepository, "list_page_by_doctor_and_patient", page_query)

    with pytest.raises(Exception) as denied:
        await DoctorHistoryService.get_assigned_patient_history(
            str(USER_ID), str(PATIENT_ID), PageWindow(2, 10),
        )
    assert getattr(denied.value, "status_code", None) == 404
    access.assert_awaited_once_with(str(DOCTOR_ID), str(PATIENT_ID))
    page_query.assert_not_awaited()

    monkeypatch.setattr(AppointmentRepository, "has_assigned_patient", AsyncMock(return_value=True))
    monkeypatch.setattr(AppointmentRepository, "list_page_by_doctor_and_patient",
                        AsyncMock(return_value=[]))
    patient = SimpleNamespace(id=PATIENT_ID, user_id=USER_ID, phone=None,
                              date_of_birth=None, gender=None)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "get_by_id",
                        AsyncMock(return_value=SimpleNamespace(full_name="Fictional Patient")))
    monkeypatch.setattr(LabRequestRepository, "list_page_released_for_patients",
                        AsyncMock(return_value=[]))

    history = await DoctorHistoryService.get_assigned_patient_history(
        str(USER_ID), str(PATIENT_ID), PageWindow(2, 10),
    )
    assert history.appointments == []
    assert history.reports == []
    AppointmentRepository.list_page_by_doctor_and_patient.assert_awaited_once_with(
        str(DOCTOR_ID), str(PATIENT_ID), PageWindow(2, 10),
    )


@pytest.mark.asyncio
async def test_assigned_patient_id_page_filters_before_grouping(monkeypatch):
    class Cursor:
        async def to_list(self, length):
            assert length == 12
            return [{"_id": PATIENT_ID}]

    collection = Mock()
    collection.aggregate.return_value = Cursor()
    monkeypatch.setattr(Appointment, "get_pymongo_collection", Mock(return_value=collection))
    result = await AppointmentRepository.page_assigned_patient_ids(str(DOCTOR_ID), PageWindow(3, 12))
    assert result == [str(PATIENT_ID)]
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline == [
        {"$match": {"doctor_id": DOCTOR_ID, "doctor_assignment_pending": {"$ne": True}}},
        {"$group": {"_id": "$patient_id"}},
        {"$sort": {"_id": 1}},
        {"$skip": 24},
        {"$limit": 12},
    ]


@pytest.mark.asyncio
async def test_doctor_assignment_existence_query_filters_pending_and_patient(monkeypatch):
    find_one = AsyncMock(return_value=object())
    monkeypatch.setattr(Appointment, "find_one", find_one)
    assert await AppointmentRepository.has_assigned_patient(
        str(DOCTOR_ID), str(PATIENT_ID),
    ) is True
    find_one.assert_awaited_once_with({
        "doctor_id": DOCTOR_ID,
        "patient_id": PATIENT_ID,
        "doctor_assignment_pending": {"$ne": True},
    })
    find_one.reset_mock(return_value=True)
    find_one.return_value = None
    assert await AppointmentRepository.has_assigned_patient(
        str(DOCTOR_ID), str(PATIENT_ID),
    ) is False
    assert await AppointmentRepository.has_assigned_patient(
        str(DOCTOR_ID), "invalid-id",
    ) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("path,service,method", [
    ("/api/care-plans", CarePlanService, "get_care_plans_by_patient"),
    ("/api/exercise-assignments", ExerciseService, "list_assignments_for_patient"),
    ("/api/exercise-progress", ExerciseService, "list_progress_for_patient"),
    ("/api/laboratory/bookings", LaboratoryService, "get_bookings_by_patient_id"),
])
async def test_own_clinical_pages_ignore_untrusted_patient_id(
    monkeypatch, path, service, method,
):
    _as_user(monkeypatch, "patient")
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id",
                        AsyncMock(return_value=SimpleNamespace(id=PATIENT_ID)))
    paged = AsyncMock(return_value=[])
    monkeypatch.setattr(service, method, paged)
    response = await _get(path, {"patient_id": str(DOCTOR_ID), "page": 2})
    assert response.status_code == 200
    assert paged.await_args.args[0] == str(PATIENT_ID)
    assert paged.await_args.args[-1] == PageWindow(2, DEFAULT_PAGE_SIZE)
