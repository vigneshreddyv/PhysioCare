"""Offline query-count, authorization-shape, and projection contracts for Group C."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from beanie import PydanticObjectId
from fastapi import HTTPException
import pytest

from app.core.pagination import PageWindow
from app.models.doctor import Doctor
from app.models.home_visit_request import HomeVisitRequest
from app.models.lab_request import LabRequest
from app.models.patient import Patient
from app.models.payment_attempt import PaymentAttempt
from app.models.user import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.demo_service_repository import DemoServiceRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.payment_query_repository import PaymentQueryRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.appointment_service import AppointmentService
from app.services.home_visit_service import HomeVisitService
from app.services.lab_request_service import LabRequestService


def oid(number: int) -> PydanticObjectId:
    return PydanticObjectId(f"{number:024x}")


def find_collection(rows):
    collection = MagicMock()
    collection.find.return_value.to_list = AsyncMock(return_value=rows)
    return collection


def raw_page_collection(rows=None):
    collection = MagicMock()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=rows or [])
    collection.find.return_value = cursor
    return collection, cursor


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [1, 10, 50, 100])
async def test_appointment_identity_queries_are_constant_and_page_bounded(monkeypatch, size):
    appointments = [SimpleNamespace(patient_id=oid(i + 1), doctor_id=oid(i + 501))
                    for i in range(size)]
    patient_rows = [{"_id": item.patient_id, "user_id": oid(i + 1001)}
                    for i, item in enumerate(appointments)]
    doctor_rows = [{"_id": item.doctor_id, "user_id": oid(i + 2001)}
                   for i, item in enumerate(appointments)]
    patient_users = [{"_id": row["user_id"], "full_name": f"Patient {i}"}
                     for i, row in enumerate(patient_rows)]
    doctor_users = [{"_id": row["user_id"], "full_name": f"Doctor {i}"}
                    for i, row in enumerate(doctor_rows)]
    patient_collection = find_collection(patient_rows)
    doctor_collection = find_collection(doctor_rows)
    user_collection = MagicMock()
    patient_cursor = MagicMock()
    patient_cursor.to_list = AsyncMock(return_value=patient_users)
    doctor_cursor = MagicMock()
    doctor_cursor.to_list = AsyncMock(return_value=doctor_users)
    user_collection.find.side_effect = [patient_cursor, doctor_cursor]
    monkeypatch.setattr(Patient, "get_pymongo_collection", lambda: patient_collection)
    monkeypatch.setattr(Doctor, "get_pymongo_collection", lambda: doctor_collection)
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: user_collection)

    patients, doctors, users = await AppointmentService._page_profile_maps(appointments)

    assert (len(patients), len(doctors), len(users)) == (size, size, size * 2)
    assert patient_collection.find.call_count == 1
    assert doctor_collection.find.call_count == 1
    assert user_collection.find.call_count == 2
    assert patient_collection.find.call_args.args[1] == {"user_id": 1}
    assert doctor_collection.find.call_args.args[1] == {"user_id": 1}
    assert user_collection.find.call_args_list[0].args[1] == {"full_name": 1}
    assert user_collection.find.call_args_list[1].args[1] == {"full_name": 1}
    assert patient_collection.find.return_value.to_list.await_args.kwargs["length"] == size
    assert doctor_collection.find.return_value.to_list.await_args.kwargs["length"] == size


@pytest.mark.asyncio
async def test_appointment_page_fails_closed_when_related_identity_is_missing(monkeypatch):
    appointment = SimpleNamespace(patient_id=oid(1), doctor_id=oid(2))
    monkeypatch.setattr(AppointmentService, "_page_profile_maps", AsyncMock(return_value=({}, {}, {})))
    formatter = AsyncMock()
    monkeypatch.setattr(AppointmentService, "_format_appointment", formatter)

    with pytest.raises(HTTPException) as error:
        await AppointmentService._format_appointment_page([appointment])

    assert error.value.status_code == 404
    formatter.assert_not_awaited()


@pytest.mark.asyncio
async def test_all_four_appointment_operations_use_bounded_page_formatter(monkeypatch):
    row = SimpleNamespace(id=oid(1), patient_id=oid(2), doctor_id=oid(3))
    page = PageWindow(1, 50)
    patient = SimpleNamespace(id=oid(2))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(AppointmentRepository, "list_page_all", AsyncMock(return_value=[row]))
    monkeypatch.setattr(AppointmentRepository, "list_page_by_patient_id", AsyncMock(return_value=[row]))
    monkeypatch.setattr(AppointmentRepository, "list_page_billing", AsyncMock(return_value=[row]))
    monkeypatch.setattr(AppointmentRepository, "list_page_by_patient_status", AsyncMock(return_value=[row]))
    page_formatter = AsyncMock(return_value=["formatted"])
    monkeypatch.setattr(AppointmentService, "_format_appointment_page", page_formatter)

    assert await AppointmentService.list_appointments("admin", "admin", page) == ["formatted"]
    assert await AppointmentService.list_patient_home_visits("patient", page) == ["formatted"]
    assert await AppointmentService.list_admin_billing(page) == ["formatted"]
    assert await AppointmentService.list_patient_appointment_history(
        "patient", "completed", page,
    ) == ["formatted"]
    assert page_formatter.await_count == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [1, 10, 50, 100])
@pytest.mark.parametrize("view", ["admin", "doctor", "reception"])
async def test_patient_directory_is_one_aggregation_with_role_projection(monkeypatch, size, view):
    collection = MagicMock()
    collection.aggregate.return_value.to_list = AsyncMock(return_value=[])
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)

    await ProfileRepository.search_patients(
        "", PageWindow(1, size), doctor_id=str(oid(700)) if view == "doctor" else None,
        active_only=view == "reception", view=view,
    )

    assert collection.aggregate.call_count == 1
    assert collection.aggregate.return_value.to_list.await_args.kwargs["length"] == size
    pipeline = collection.aggregate.call_args.args[0]
    skip_index = next(i for i, stage in enumerate(pipeline) if "$skip" in stage)
    project = pipeline[-1]["$project"]
    assert pipeline[skip_index]["$skip"] == 0
    assert "password_hash" not in project and "refresh_token" not in project
    if view == "doctor":
        assignment_index = next(i for i, stage in enumerate(pipeline)
                                if stage.get("$lookup", {}).get("from") == "appointments")
        assert assignment_index < skip_index
        assert "email" not in project
        assert "profile.subscription_status" not in project
    elif view == "reception":
        assert "email" in project
        assert "profile.date_of_birth" not in project
        assert "profile.gender" not in project
    else:
        assert "email" in project
        assert "profile.subscription_status" in project


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [1, 10, 50, 100])
async def test_doctor_home_visit_identity_queries_are_constant_and_private(monkeypatch, size):
    requests = [SimpleNamespace(patient_id=oid(i + 1)) for i in range(size)]
    patient_rows = [{"_id": item.patient_id, "user_id": oid(i + 1001), "phone": "synthetic"}
                    for i, item in enumerate(requests)]
    user_rows = [{"_id": row["user_id"], "full_name": f"Patient {i}"}
                 for i, row in enumerate(patient_rows)]
    patient_collection = find_collection(patient_rows)
    user_collection = find_collection(user_rows)
    monkeypatch.setattr(Patient, "get_pymongo_collection", lambda: patient_collection)
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: user_collection)

    patients, users = await HomeVisitService._page_patient_maps(requests)

    assert (len(patients), len(users)) == (size, size)
    assert patient_collection.find.call_count == user_collection.find.call_count == 1
    assert patient_collection.find.call_args.args[1] == {"user_id": 1, "phone": 1}
    assert user_collection.find.call_args.args[1] == {"full_name": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [1, 10, 50, 100])
@pytest.mark.parametrize("laboratory_view", [False, True])
async def test_lab_identity_queries_are_constant_and_role_scoped(monkeypatch, size, laboratory_view):
    requests = [SimpleNamespace(
        patient_id=oid(i + 1), assigned_laboratorian_user_id=oid(i + 2001),
    ) for i in range(size)]
    patient_rows = [{"_id": item.patient_id, "user_id": oid(i + 1001), "phone": "synthetic"}
                    for i, item in enumerate(requests)]
    patient_users = [{"_id": row["user_id"], "full_name": f"Patient {i}",
                      "email": f"patient-{i}@example.invalid"}
                     for i, row in enumerate(patient_rows)]
    assigned_users = [{"_id": item.assigned_laboratorian_user_id, "full_name": f"Lab {i}"}
                      for i, item in enumerate(requests)]
    patient_collection = find_collection(patient_rows)
    user_collection = MagicMock()
    patient_cursor = MagicMock()
    patient_cursor.to_list = AsyncMock(return_value=patient_users)
    assigned_cursor = MagicMock()
    assigned_cursor.to_list = AsyncMock(return_value=assigned_users)
    user_collection.find.side_effect = (
        [patient_cursor] if laboratory_view else [patient_cursor, assigned_cursor]
    )
    monkeypatch.setattr(Patient, "get_pymongo_collection", lambda: patient_collection)
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: user_collection)

    patients, users, assigned = await LabRequestService._page_identity_maps(
        requests,
        include_patient_email=not laboratory_view,
        include_assignee=not laboratory_view,
    )

    assert (len(patients), len(users)) == (size, size)
    assert len(assigned) == (0 if laboratory_view else size)
    assert patient_collection.find.call_count == 1
    assert user_collection.find.call_count == (1 if laboratory_view else 2)
    patient_projection = user_collection.find.call_args_list[0].args[1]
    assert patient_projection == (
        {"full_name": 1} if laboratory_view else {"full_name": 1, "email": 1}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("repository,model,method,args,query,sort", [
    (DemoServiceRepository, HomeVisitRequest, "list_page_by_patient", (str(oid(1)),),
     {"patient_id": oid(1)}, [("created_at", -1), ("_id", -1)]),
    (DemoServiceRepository, HomeVisitRequest, "list_page_all", (), {},
     [("created_at", -1), ("_id", -1)]),
    (DemoServiceRepository, HomeVisitRequest, "list_page_doctor_coordination", (str(oid(2)),),
     {"preferred_doctor_id": oid(2), "status": "approved_for_coordination"},
     [("created_at", -1), ("_id", -1)]),
    (LabRequestRepository, LabRequest, "list_page_for_patient", (str(oid(1)),),
     {"patient_id": oid(1)}, [("created_at", -1), ("_id", -1)]),
    (LabRequestRepository, LabRequest, "list_page_all", (), {},
     [("created_at", -1), ("_id", -1)]),
    (LabRequestRepository, LabRequest, "list_page_for_laboratorian", (str(oid(3)),),
     {"assigned_laboratorian_user_id": oid(3)}, [("updated_at", -1), ("_id", -1)]),
])
async def test_clinical_main_queries_filter_page_sort_and_project(
    monkeypatch, repository, model, method, args, query, sort,
):
    collection, cursor = raw_page_collection()
    monkeypatch.setattr(model, "get_pymongo_collection", lambda: collection)

    assert await getattr(repository, method)(*args, PageWindow(3, 17)) == []

    assert collection.find.call_args.args[0] == query
    assert collection.find.call_args.args[1] == repository._CLINICAL_LIST_PROJECTION
    cursor.sort.assert_called_once_with(sort)
    cursor.skip.assert_called_once_with(34)
    cursor.limit.assert_called_once_with(17)
    cursor.to_list.assert_awaited_once_with(length=17)
    projection = collection.find.call_args.args[1]
    for forbidden in (
        "report_storage_key", "assignment_history", "report_publication_history",
        "reviewed_by_user_id", "submission_key", "demo_rehearsal_tag",
    ):
        assert forbidden not in projection


@pytest.mark.asyncio
async def test_group_a_dual_classified_paths_remain_single_bounded_aggregations(monkeypatch):
    payment_collection = MagicMock()
    payment_collection.aggregate.return_value.to_list = AsyncMock(return_value=[])
    entitlement_collection = MagicMock()
    entitlement_collection.aggregate.return_value.to_list = AsyncMock(return_value=[])
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", lambda: payment_collection)
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: entitlement_collection)

    await PaymentQueryRepository.list_patient_history(str(oid(1)), PageWindow(2, 50))
    await DemoServiceRepository.search_entitlements(PageWindow(2, 50), "")

    assert payment_collection.aggregate.call_count == 1
    assert entitlement_collection.aggregate.call_count == 1
    for collection in (payment_collection, entitlement_collection):
        pipeline = collection.aggregate.call_args.args[0]
        assert {"$skip": 50} in pipeline and {"$limit": 50} in pipeline
        collection.aggregate.return_value.to_list.assert_awaited_once_with(length=50)
