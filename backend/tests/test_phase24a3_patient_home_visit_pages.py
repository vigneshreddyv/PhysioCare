"""Offline ownership and bounded-query checks for the patient home-visit list."""

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
async def test_home_visit_query_applies_owner_and_mode_before_page(monkeypatch):
    query = Mock()
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    finder = Mock(return_value=query)
    monkeypatch.setattr(Appointment, "find", finder)

    result = await AppointmentRepository.list_page_by_patient_id(
        str(PATIENT), PageWindow(21, 50), "home_visit",
    )
    assert result == []
    assert finder.call_args.args[0] == {
        "patient_id": PATIENT, "service_mode": "home_visit",
    }
    query.sort.assert_called_once_with("-appointment_date", "-_id")
    query.skip.assert_called_once_with(1000)
    query.limit.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_home_visit_service_scopes_patient_and_formats_only_own_rows(monkeypatch):
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id=PATIENT),
    ))
    finder = AsyncMock(return_value=[])
    monkeypatch.setattr(AppointmentRepository, "list_page_by_patient_id", finder)
    assert await AppointmentService.list_patient_home_visits("fictional-user", PageWindow(21, 50)) == []
    finder.assert_awaited_once_with(str(PATIENT), PageWindow(21, 50), "home_visit")


@pytest.mark.asyncio
async def test_home_visit_http_route_is_patient_only(monkeypatch):
    getter = AsyncMock(return_value=[])
    monkeypatch.setattr(AppointmentService, "list_patient_home_visits", getter)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            for role, expected in (("patient", 200), ("doctor", 403), ("admin", 403)):
                app.dependency_overrides[get_current_user] = (
                    lambda role=role: SimpleNamespace(id=PATIENT, role=role, is_active=True)
                )
                response = await client.get("/api/appointments/me/home-visits", params={
                    "page": 21, "page_size": 50,
                })
                assert response.status_code == expected
                if role == "patient":
                    assert response.json() == []
                    assert response.headers["cache-control"] == "private, no-store"
        getter.assert_awaited_once_with(str(PATIENT), PageWindow(21, 50))
    finally:
        app.dependency_overrides.pop(get_current_user, None)
