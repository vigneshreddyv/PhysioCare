"""Offline patient status navigation queries and role boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import httpx
import pytest

from app.core.pagination import PageWindow
from app.main import app
from app.middleware.auth import get_current_user
from app.models.appointment import Appointment
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.appointment_service import AppointmentService


PATIENT = PydanticObjectId("507f1f77bcf86cd799439011")


@pytest.mark.asyncio
@pytest.mark.parametrize("status_group,statuses,direction", [
    ("upcoming", ["scheduled", "in_progress"], "+"),
    ("completed", ["completed"], "-"),
    ("cancelled", ["cancelled"], "-"),
])
async def test_status_filter_precedes_page(monkeypatch, status_group, statuses, direction):
    query = Mock()
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    finder = Mock(return_value=query)
    monkeypatch.setattr(Appointment, "find", finder)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id=PATIENT),
    ))
    result = await AppointmentService.list_patient_appointment_history(
        "fictional-user", status_group, PageWindow(21, 50),
    )
    assert result == []
    assert finder.call_args.args[0] == {
        "patient_id": PATIENT, "status": {"$in": statuses},
    }
    query.sort.assert_called_once_with(
        f"{direction}appointment_date", f"{direction}time_slot", f"{direction}_id",
    )
    query.skip.assert_called_once_with(1000)
    query.limit.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_future_only_applies_date_filter_before_paging(monkeypatch):
    query = Mock()
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    finder = Mock(return_value=query)
    monkeypatch.setattr(Appointment, "find", finder)
    await AppointmentRepository.list_page_by_patient_status(
        str(PATIENT), ["scheduled", "in_progress"], PageWindow(21, 50),
        ascending=True, future_only=True,
    )
    match = finder.call_args.args[0]
    assert match["patient_id"] == PATIENT
    assert match["status"] == {"$in": ["scheduled", "in_progress"]}
    assert match["$or"][0]["starts_at"]["$gte"]
    assert match["$or"][1]["starts_at"] is None
    assert match["$or"][1]["appointment_date"]["$gte"]
    query.skip.assert_called_once_with(1000)
    query.limit.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_history_route_rejects_other_roles_and_unknown_status(monkeypatch):
    getter = AsyncMock(return_value=[])
    monkeypatch.setattr(AppointmentService, "list_patient_appointment_history", getter)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            for role, expected in (("patient", 200), ("doctor", 403), ("admin", 403)):
                app.dependency_overrides[get_current_user] = (
                    lambda role=role: SimpleNamespace(id=PATIENT, role=role, is_active=True)
                )
                response = await client.get("/api/appointments/me/history", params={
                    "status_group": "completed", "page": 21,
                })
                assert response.status_code == expected
                if role == "patient":
                    assert response.headers["cache-control"] == "private, no-store"
            app.dependency_overrides[get_current_user] = (
                lambda: SimpleNamespace(id=PATIENT, role="patient", is_active=True)
            )
            invalid = await client.get("/api/appointments/me/history?status_group=unknown")
            assert invalid.status_code == 422
            future = await client.get(
                "/api/appointments/me/history?status_group=upcoming&future_only=true&page=21"
            )
            assert future.status_code == 200
        assert getter.await_count == 2
        assert getter.await_args_list[0].args == (str(PATIENT), "completed", PageWindow(21, 50))
        assert getter.await_args_list[1].args == (str(PATIENT), "upcoming", PageWindow(21, 50))
        assert getter.await_args_list[1].kwargs == {"future_only": True}
    finally:
        app.dependency_overrides.pop(get_current_user, None)
