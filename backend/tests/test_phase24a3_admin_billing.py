"""Offline admin billing filter, page, and role contracts."""

from datetime import date, datetime
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
from app.services.appointment_service import AppointmentService


USER = PydanticObjectId("507f1f77bcf86cd799439011")


@pytest.mark.asyncio
async def test_billing_filters_before_page_21(monkeypatch):
    query = Mock()
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    finder = Mock(return_value=query)
    monkeypatch.setattr(Appointment, "find", finder)
    assert await AppointmentRepository.list_page_billing(
        PageWindow(21, 50), "paid", date(2040, 1, 1), date(2040, 1, 31),
    ) == []
    assert finder.call_args.args[0] == {
        "billing_status": "paid",
        "appointment_date": {"$gte": datetime(2040, 1, 1), "$lt": datetime(2040, 2, 1)},
    }
    query.sort.assert_called_once_with("-appointment_date", "-_id")
    query.skip.assert_called_once_with(1000)
    query.limit.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_admin_only_billing_route(monkeypatch):
    getter = AsyncMock(return_value=[])
    monkeypatch.setattr(AppointmentService, "list_admin_billing", getter)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            for role, expected in (("admin", 200), ("patient", 403), ("doctor", 403),
                                   ("receptionist", 403)):
                app.dependency_overrides[get_current_user] = (
                    lambda role=role: SimpleNamespace(id=USER, role=role, is_active=True)
                )
                response = await client.get("/api/appointments/admin/billing", params={
                    "page": 21, "billing_status": "paid", "start_date": "2040-01-01",
                    "end_date": "2040-01-31",
                })
                assert response.status_code == expected
                if role == "admin":
                    assert response.headers["cache-control"] == "private, no-store"
            app.dependency_overrides[get_current_user] = (
                lambda: SimpleNamespace(id=USER, role="admin", is_active=True)
            )
            assert (await client.get(
                "/api/appointments/admin/billing?start_date=2040-02-01&end_date=2040-01-01"
            )).status_code == 422
        getter.assert_awaited_once_with(
            PageWindow(21, 50), "paid", date(2040, 1, 1), date(2040, 1, 31),
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
