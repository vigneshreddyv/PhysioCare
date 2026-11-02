"""Offline patient-scoped report search and bounded page contract."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import httpx
import pytest

from app.core.pagination import PageWindow
from app.main import app
from app.middleware.auth import get_current_user
from app.models.report import Report
from app.repositories.profile_repository import ProfileRepository
from app.repositories.report_repository import ReportRepository
from app.services.report_service import ReportService


PATIENT = PydanticObjectId("507f1f77bcf86cd799439011")


@pytest.mark.asyncio
async def test_report_search_filters_owner_and_escapes_literal_before_page(monkeypatch):
    query = Mock()
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    finder = Mock(return_value=query)
    monkeypatch.setattr(Report, "find", finder)

    assert await ReportRepository.get_page_by_patient_id(str(PATIENT), PageWindow(21, 50), "Fict.*") == []
    match = finder.call_args.args[0]
    assert match["patient_id"] == PATIENT
    assert match["$or"] == [
        {"title": {"$regex": r"Fict\.\*", "$options": "i"}},
        {"category": {"$regex": r"Fict\.\*", "$options": "i"}},
    ]
    query.sort.assert_called_once_with("-date", "-_id")
    query.skip.assert_called_once_with(1000)
    query.limit.assert_called_once_with(50)
    query.to_list.assert_awaited_once()


@pytest.mark.asyncio
async def test_patient_report_search_route_and_role_boundary(monkeypatch):
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id=PATIENT),
    ))
    getter = AsyncMock(return_value=[])
    monkeypatch.setattr(ReportService, "get_reports_by_patient_id", getter)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        for role, expected in (("patient", 200), ("doctor", 403), ("admin", 403)):
            monkeypatch.setitem(app.dependency_overrides, get_current_user,
                                lambda role=role: SimpleNamespace(id=PATIENT, role=role, is_active=True))
            response = await client.get("/api/reports", params={
                "page": 21, "page_size": 50, "search": "Fictional",
            })
            assert response.status_code == expected
            if role == "patient":
                assert response.json() == []
                assert response.headers["cache-control"] == "private, no-store"
        monkeypatch.setitem(app.dependency_overrides, get_current_user,
                            lambda: SimpleNamespace(id=PATIENT, role="patient", is_active=True))
        too_long = await client.get("/api/reports", params={"search": "x" * 101})
        assert too_long.status_code == 422
    getter.assert_awaited_once()
    args = getter.await_args.args
    assert args[0] == str(PATIENT)
    assert args[1] == PageWindow(21, 50)
    assert args[2] == "Fictional"
