from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.laboratory import (
    get_laboratory_booking,
    laboratory_booking_response,
    router as laboratory_router,
)
from app.main import create_fastapi_application
from app.models.laboratory_booking import LaboratoryBooking
from app.models.laboratory_test import LaboratoryTest
from app.repositories.laboratory_test_repository import (
    LEGACY_LABORATORY_CATALOG_MAX,
    LaboratoryTestRepository,
)
from app.repositories.profile_repository import ProfileRepository
from app.schemas.laboratory_booking import LaboratoryBookingResponse
from app.services.laboratory_service import LaboratoryService


def find_collection(rows):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=rows)
    collection = MagicMock()
    collection.find.return_value = cursor
    return collection, cursor


def catalogue_row(index: int) -> dict:
    return {
        "test_id": f"test-{index:03d}",
        "name": f"Test {index:03d}",
        "category": "Synthetic",
        "sample": "Synthetic sample",
        "price": float(index),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [0, 2, LEGACY_LABORATORY_CATALOG_MAX])
async def test_legacy_catalogue_is_active_only_stable_projected_and_bounded(
    monkeypatch, size,
):
    rows = [catalogue_row(index) for index in range(size)]
    collection, cursor = find_collection(rows)
    monkeypatch.setattr(LaboratoryTest, "get_pymongo_collection", lambda: collection)

    result = await LaboratoryTestRepository.get_active_tests()

    assert [item.test_id for item in result] == [row["test_id"] for row in rows]
    collection.find.assert_called_once_with(
        {"active": True},
        {
            "_id": 0,
            "test_id": 1,
            "name": 1,
            "category": 1,
            "sample": 1,
            "price": 1,
        },
    )
    cursor.sort.assert_called_once_with([
        ("category", 1),
        ("name", 1),
        ("test_id", 1),
        ("_id", 1),
    ])
    cursor.limit.assert_called_once_with(LEGACY_LABORATORY_CATALOG_MAX)
    cursor.to_list.assert_awaited_once_with(length=LEGACY_LABORATORY_CATALOG_MAX)


@pytest.mark.asyncio
async def test_legacy_catalogue_over_limit_never_requests_or_returns_more_than_cap(
    monkeypatch,
):
    capped_rows = [
        catalogue_row(index) for index in range(LEGACY_LABORATORY_CATALOG_MAX)
    ]
    collection, cursor = find_collection(capped_rows)
    monkeypatch.setattr(LaboratoryTest, "get_pymongo_collection", lambda: collection)

    result = await LaboratoryTestRepository.get_active_tests()

    assert len(result) == LEGACY_LABORATORY_CATALOG_MAX
    cursor.limit.assert_called_once_with(LEGACY_LABORATORY_CATALOG_MAX)
    cursor.to_list.assert_awaited_once_with(length=LEGACY_LABORATORY_CATALOG_MAX)


def route_roles(path: str, method: str) -> set[str]:
    route = next(
        candidate for candidate in laboratory_router.routes
        if candidate.path == path and method in candidate.methods
    )
    checker = next(
        dependency.call for dependency in route.dependant.dependencies
        if hasattr(dependency.call, "allowed_roles")
    )
    return set(checker.allowed_roles)


def test_legacy_catalogue_and_booking_routes_retain_narrow_roles():
    assert route_roles("/laboratory/tests", "GET") == {"patient"}
    assert route_roles("/laboratory/bookings", "GET") == {"patient"}
    assert route_roles("/laboratory/bookings/{booking_id}", "GET") == {"patient"}
    assert route_roles("/laboratory/bookings/{booking_id}/status", "PATCH") == {
        "admin", "doctor",
    }


def booking_with_internal_provider_ids():
    return SimpleNamespace(
        id="booking-id",
        patient_id="patient-id",
        selected_tests=[SimpleNamespace(
            test_id="cbc",
            name="CBC",
            sample="Blood",
            price=350.0,
        )],
        visit_type="clinic",
        appointment_date=datetime(2026, 11, 3, tzinfo=timezone.utc),
        time_slot="09:00 AM",
        address=None,
        status="confirmed",
        billing_status="paid",
        billing_amount=350.0,
        payment_method="razorpay",
        payment_status="success",
        payment_id="pay_internal_only",
        payment_order_id="order_internal_only",
        created_at=datetime(2026, 11, 2, tzinfo=timezone.utc),
    )


def test_general_booking_response_excludes_provider_ids_but_preserves_contract():
    response = laboratory_booking_response(booking_with_internal_provider_ids())
    payload = response.model_dump(mode="json")

    assert "payment_id" not in LaboratoryBookingResponse.model_fields
    assert "payment_order_id" not in LaboratoryBookingResponse.model_fields
    assert "payment_id" not in payload
    assert "payment_order_id" not in payload
    assert payload == {
        "id": "booking-id",
        "patient_id": "patient-id",
        "selected_tests": [{
            "test_id": "cbc",
            "name": "CBC",
            "sample": "Blood",
            "price": 350.0,
        }],
        "visit_type": "clinic",
        "appointment_date": "2026-11-03T00:00:00Z",
        "time_slot": "09:00 AM",
        "address": None,
        "status": "confirmed",
        "billing_status": "paid",
        "billing_amount": 350.0,
        "payment_method": "razorpay",
        "payment_status": "success",
        "created_at": "2026-11-02T00:00:00Z",
    }


def test_internal_booking_model_retains_provider_ids_for_internal_workflows():
    assert "payment_id" in LaboratoryBooking.model_fields
    assert "payment_order_id" in LaboratoryBooking.model_fields


@pytest.mark.asyncio
async def test_booking_detail_still_derives_patient_ownership_from_session(monkeypatch):
    patient = SimpleNamespace(id="patient-profile-id")
    booking = booking_with_internal_provider_ids()
    profile_lookup = AsyncMock(return_value=patient)
    booking_lookup = AsyncMock(return_value=booking)
    monkeypatch.setattr(
        ProfileRepository, "get_patient_by_user_id", profile_lookup,
    )
    monkeypatch.setattr(
        LaboratoryService, "get_booking_by_id", booking_lookup,
    )

    response = await get_laboratory_booking(
        "booking-id", SimpleNamespace(id="authenticated-user-id"),
    )

    profile_lookup.assert_awaited_once_with("authenticated-user-id")
    booking_lookup.assert_awaited_once_with("booking-id", "patient-profile-id")
    assert "payment_id" not in response.model_dump()
    assert "payment_order_id" not in response.model_dump()


def documentation_settings(
    environment: str,
    *,
    enabled: bool | None = None,
    lab_demo: bool = False,
    home_demo: bool = False,
):
    return SimpleNamespace(
        ENVIRONMENT=environment,
        API_DOCUMENTATION_ENABLED=enabled,
        LAB_DEMO_MODE=lab_demo,
        HOME_VISIT_DEMO_MODE=home_demo,
    )


@pytest.mark.parametrize(
    ("configured", "expected_status"),
    [
        (documentation_settings("development"), 200),
        (documentation_settings("development", enabled=False), 404),
        (documentation_settings("test"), 200),
        (documentation_settings("staging"), 404),
        (documentation_settings("staging", enabled=True), 200),
        (documentation_settings("development", lab_demo=True), 404),
        (documentation_settings("development", lab_demo=True, enabled=True), 200),
        (documentation_settings("development", home_demo=True), 404),
        (documentation_settings("development", home_demo=True, enabled=True), 200),
        (documentation_settings("production"), 404),
        (documentation_settings("production", enabled=True), 404),
    ],
)
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentation_policy_controls_actual_fastapi_routes(
    configured, expected_status, path,
):
    candidate = create_fastapi_application(configured)

    assert TestClient(candidate).get(path).status_code == expected_status

