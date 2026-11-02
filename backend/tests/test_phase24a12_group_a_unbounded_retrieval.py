from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from app.api.home_visits import list_demo_entitlements, router as home_visits_router
from app.api.payments import list_patient_payment_history, router as payments_router
from app.api.users import list_staff, router as users_router
from app.core.pagination import PageWindow
from app.models.payment_attempt import PaymentAttempt
from app.models.user import User
from app.repositories.demo_service_repository import DemoServiceRepository
from app.repositories.payment_query_repository import PaymentQueryRepository
from app.repositories.user_repository import UserRepository
from app.services.home_visit_service import HomeVisitService
from app.services.payment_service import PaymentService
from app.services.user_service import UserService


PATIENT_ID = "111111111111111111111111"
USER_ID = "222222222222222222222222"


def aggregate_collection(rows=None):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=rows or [])
    collection = MagicMock()
    collection.aggregate.return_value = cursor
    return collection, cursor


def find_collection(rows=None):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=rows or [])
    collection = MagicMock()
    collection.find.return_value = cursor
    return collection, cursor


def route_roles(router, path: str) -> set[str]:
    route = next(
        candidate for candidate in router.routes
        if candidate.path == path and "GET" in candidate.methods
    )
    checker = next(
        dependency.call for dependency in route.dependant.dependencies
        if hasattr(dependency.call, "allowed_roles")
    )
    return set(checker.allowed_roles)


def test_group_a_routes_retain_narrow_role_authorization():
    assert route_roles(payments_router, "/payments/history") == {"patient"}
    assert route_roles(users_router, "/users/staff") == {"admin"}
    assert route_roles(home_visits_router, "/demo-services/entitlements") == {"admin"}


@pytest.mark.asyncio
async def test_payment_history_query_filters_before_stable_bounded_page(monkeypatch):
    collection, cursor = aggregate_collection()
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", lambda: collection)

    await PaymentQueryRepository.list_patient_history(
        PATIENT_ID,
        PageWindow(21, 50),
        payment_status="failed",
        start_date=date(2026, 1, 2),
        end_date=date(2026, 2, 3),
    )

    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0]["$match"] == {
        "patient_id": PydanticObjectId(PATIENT_ID),
        "status": "failed",
        "created_at": {
            "$gte": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "$lt": datetime(2026, 2, 4, tzinfo=timezone.utc),
        },
    }
    assert pipeline[1:4] == [
        {"$sort": {"created_at": -1, "_id": -1}},
        {"$skip": 1000},
        {"$limit": 50},
    ]
    assert pipeline[4]["$lookup"]["from"] == "appointments"
    projection = pipeline[-1]["$project"]
    assert set(projection) == {
        "_id", "appointment_id", "amount_paise", "currency", "status",
        "reconciliation_status", "appointment.billing_status",
        "appointment.payment_status", "appointment.appointment_date",
        "appointment.time_slot", "appointment.service_mode",
    }
    assert "provider_order_id" not in projection
    assert "provider_payment_id" not in projection
    cursor.to_list.assert_awaited_once_with(length=50)


@pytest.mark.asyncio
async def test_payment_history_service_uses_one_bounded_join_for_many_rows(monkeypatch):
    patient = SimpleNamespace(id=PydanticObjectId(PATIENT_ID))
    monkeypatch.setattr(
        "app.services.payment_service.ProfileRepository.get_patient_by_user_id",
        AsyncMock(return_value=patient),
    )
    rows = [{
        "_id": PydanticObjectId(f"{index:024x}"),
        "appointment_id": PydanticObjectId(f"{index + 1000:024x}"),
        "amount_paise": 12000,
        "currency": "INR",
        "status": "success",
        "reconciliation_status": "reconciled",
        "appointment": {},
    } for index in range(50)]
    query = AsyncMock(return_value=rows)
    monkeypatch.setattr(PaymentQueryRepository, "list_patient_history", query)

    result = await PaymentService.get_patient_payment_history(USER_ID, PageWindow(25, 50))

    assert len(result) == 50
    query.assert_awaited_once_with(
        PATIENT_ID, PageWindow(25, 50),
        payment_status=None, start_date=None, end_date=None,
    )


@pytest.mark.asyncio
async def test_payment_history_route_enforces_page_bounds_and_date_order(monkeypatch):
    current_user = SimpleNamespace(id=PydanticObjectId(USER_ID), role="patient")
    service = AsyncMock(return_value=[])
    monkeypatch.setattr(PaymentService, "get_patient_payment_history", service)

    assert await list_patient_payment_history(
        current_user=current_user, page=1, page_size=100,
        payment_status=None, start_date=None, end_date=None,
    ) == []
    service.assert_awaited_once_with(
        USER_ID, PageWindow(1, 100),
        payment_status=None, start_date=None, end_date=None,
    )
    with pytest.raises(HTTPException) as invalid_page:
        await list_patient_payment_history(
            current_user=current_user, page=0, page_size=50,
            payment_status=None, start_date=None, end_date=None,
        )
    assert invalid_page.value.status_code == 422
    with pytest.raises(HTTPException) as invalid_dates:
        await list_patient_payment_history(
            current_user=current_user, page=1, page_size=50,
            payment_status=None, start_date=date(2026, 2, 2), end_date=date(2026, 2, 1),
        )
    assert invalid_dates.value.status_code == 422


@pytest.mark.asyncio
async def test_payment_history_route_uses_project_default_page(monkeypatch):
    current_user = SimpleNamespace(id=PydanticObjectId(USER_ID), role="patient")
    service = AsyncMock(return_value=[])
    monkeypatch.setattr(PaymentService, "get_patient_payment_history", service)

    assert await list_patient_payment_history(current_user=current_user) == []
    service.assert_awaited_once_with(
        USER_ID, PageWindow(1, 50),
        payment_status=None, start_date=None, end_date=None,
    )


@pytest.mark.asyncio
async def test_staff_query_filters_projects_escapes_and_pages_in_database(monkeypatch):
    collection, cursor = find_collection()
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)

    await UserRepository.list_staff(
        PageWindow(22, 50), search="fictional.*", role="doctor", is_active=False,
    )

    query, projection = collection.find.call_args.args
    assert query == {
        "role": "doctor",
        "is_active": False,
        "$or": [
            {"full_name": {"$regex": "fictional\\.\\*", "$options": "i"}},
            {"email": {"$regex": "fictional\\.\\*", "$options": "i"}},
        ],
    }
    assert projection == {
        "full_name": 1, "email": 1, "role": 1,
        "is_active": 1, "created_at": 1,
    }
    cursor.sort.assert_called_once_with([("full_name", 1), ("_id", 1)])
    cursor.skip.assert_called_once_with(1050)
    cursor.limit.assert_called_once_with(50)
    cursor.to_list.assert_awaited_once_with(length=50)


@pytest.mark.asyncio
async def test_staff_service_returns_only_safe_projection(monkeypatch):
    row = SimpleNamespace(
        id=PydanticObjectId(USER_ID), full_name="Fictional Staff",
        email="staff@example.com", role="receptionist", is_active=True,
        created_at=datetime(2026, 1, 1), hashed_password="not-projected",
    )
    repository = AsyncMock(return_value=[row])
    monkeypatch.setattr(UserRepository, "list_staff", repository)

    result = await UserService.list_staff(
        PageWindow(2, 25), search="staff", role="receptionist", is_active=True,
    )

    assert result[0].model_dump() == {
        "id": USER_ID, "full_name": "Fictional Staff", "email": "staff@example.com",
        "role": "receptionist", "is_active": True,
        "created_at": datetime(2026, 1, 1),
    }
    assert "hashed_password" not in result[0].model_dump()
    repository.assert_awaited_once_with(
        PageWindow(2, 25), search="staff", role="receptionist", is_active=True,
    )


@pytest.mark.asyncio
async def test_staff_route_passes_bounded_server_filters(monkeypatch):
    service = AsyncMock(return_value=[])
    monkeypatch.setattr(UserService, "list_staff", service)
    admin = SimpleNamespace(id=PydanticObjectId(USER_ID), role="admin")

    assert await list_staff(
        current_user=admin, page=1000, page_size=100, search="  name  ",
        role="laboratorian", account_status="inactive",
    ) == []
    service.assert_awaited_once_with(
        PageWindow(1000, 100), search="name", role="laboratorian", is_active=False,
    )
    with pytest.raises(HTTPException):
        await list_staff(
            current_user=admin, page=1001, page_size=100, search=None,
            role=None, account_status=None,
        )


@pytest.mark.asyncio
async def test_staff_route_uses_default_page_and_preserves_all_staff_states(monkeypatch):
    service = AsyncMock(return_value=[])
    monkeypatch.setattr(UserService, "list_staff", service)
    admin = SimpleNamespace(id=PydanticObjectId(USER_ID), role="admin")

    assert await list_staff(current_user=admin, search=None) == []
    service.assert_awaited_once_with(
        PageWindow(1, 50), search="", role=None, is_active=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_search", [None, "", "   ", " patient "])
async def test_entitlement_route_always_uses_bounded_join_for_every_search_shape(
    monkeypatch, raw_search,
):
    search = AsyncMock(return_value=[])
    monkeypatch.setattr(HomeVisitService, "search_admin_entitlements", search)
    admin = SimpleNamespace(id=PydanticObjectId(USER_ID), role="admin")

    assert await list_demo_entitlements(
        current_user=admin, page=25, page_size=50, search=raw_search,
    ) == []
    search.assert_awaited_once_with(PageWindow(25, 50), (raw_search or "").strip())


@pytest.mark.asyncio
async def test_entitlement_join_filters_before_stable_page_and_projects_current_state(monkeypatch):
    collection, cursor = aggregate_collection()
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)

    await DemoServiceRepository.search_entitlements(PageWindow(3, 25), "patient.*")

    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0]["$match"] == {
        "role": "patient",
        "$or": [
            {"full_name": {"$regex": "patient\\.\\*", "$options": "i"}},
            {"email": {"$regex": "patient\\.\\*", "$options": "i"}},
        ],
    }
    assert pipeline[3] == {"$lookup": {
        "from": "demo_entitlements", "localField": "patient._id",
        "foreignField": "patient_id", "as": "entitlement",
    }}
    assert pipeline[4:7] == [
        {"$sort": {"full_name": 1, "_id": 1}},
        {"$skip": 50},
        {"$limit": 25},
    ]
    assert pipeline[-1]["$project"] == {
        "full_name": 1, "email": 1, "patient._id": 1, "patient.phone": 1,
        "entitlement.active": 1,
    }
    cursor.to_list.assert_awaited_once_with(length=25)


@pytest.mark.asyncio
async def test_entitlement_eligibility_remains_targeted_not_page_dependent(monkeypatch):
    patient = SimpleNamespace(id=PydanticObjectId(PATIENT_ID))
    entitlement = SimpleNamespace(active=True)
    monkeypatch.setattr(
        "app.services.home_visit_service.ProfileRepository.get_patient_by_user_id",
        AsyncMock(return_value=patient),
    )
    targeted = AsyncMock(return_value=entitlement)
    monkeypatch.setattr(DemoServiceRepository, "get_entitlement", targeted)
    monkeypatch.setattr("app.services.home_visit_service.settings.DEMO_HOME_VISIT_REQUESTS_ENABLED", True)

    assert await HomeVisitService._entitled_patient(USER_ID) is patient
    targeted.assert_awaited_once_with(PATIENT_ID)


@pytest.mark.asyncio
async def test_entitlement_inactive_state_still_denies_booking(monkeypatch):
    patient = SimpleNamespace(id=PydanticObjectId(PATIENT_ID))
    monkeypatch.setattr(
        "app.services.home_visit_service.ProfileRepository.get_patient_by_user_id",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        DemoServiceRepository, "get_entitlement", AsyncMock(return_value=SimpleNamespace(active=False)),
    )
    monkeypatch.setattr("app.services.home_visit_service.settings.DEMO_HOME_VISIT_REQUESTS_ENABLED", True)

    with pytest.raises(HTTPException) as denied:
        await HomeVisitService._entitled_patient(USER_ID)
    assert denied.value.status_code == 403
