"""Offline bounded recent-update queries used by the patient dashboard."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import httpx
import pytest

from app.core.pagination import PageWindow
from app.main import app
from app.middleware.auth import get_current_user
from app.models.home_visit_request import HomeVisitRequest
from app.models.lab_request import LabRequest
from app.repositories.demo_service_repository import DemoServiceRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.services.home_visit_service import HomeVisitService
from app.services.lab_request_service import LabRequestService


PATIENT = PydanticObjectId("507f1f77bcf86cd799439011")


@pytest.mark.asyncio
@pytest.mark.parametrize("model,repository", [
    (LabRequest, LabRequestRepository),
    (HomeVisitRequest, DemoServiceRepository),
])
async def test_updated_order_is_owner_scoped_and_bounded(monkeypatch, model, repository):
    query = Mock()
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    finder = Mock(return_value=query)
    collection = SimpleNamespace(find=finder)
    monkeypatch.setattr(model, "get_pymongo_collection", lambda: collection)
    method = (repository.list_page_for_patient if repository is LabRequestRepository
              else repository.list_page_by_patient)
    await method(str(PATIENT), PageWindow(21, 50), True)
    assert finder.call_args.args[0] == {"patient_id": PATIENT}
    assert finder.call_args.args[1] == repository._CLINICAL_LIST_PROJECTION
    query.sort.assert_called_once_with([("updated_at", -1), ("_id", -1)])
    query.skip.assert_called_once_with(1000)
    query.limit.assert_called_once_with(50)
    query.to_list.assert_awaited_once_with(length=50)


@pytest.mark.asyncio
async def test_recent_update_routes_require_patient_and_validate_order(monkeypatch):
    lab_getter = AsyncMock(return_value=[])
    home_getter = AsyncMock(return_value=[])
    monkeypatch.setattr(LabRequestService, "list_own", lab_getter)
    monkeypatch.setattr(HomeVisitService, "list_patient_requests", home_getter)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            for role, expected in (("patient", 200), ("doctor", 403), ("admin", 403)):
                app.dependency_overrides[get_current_user] = (
                    lambda role=role: SimpleNamespace(id=PATIENT, role=role, is_active=True)
                )
                for path in ("/api/lab-requests/me", "/api/home-visit-requests/me"):
                    response = await client.get(path, params={"order": "updated", "page": 21})
                    assert response.status_code == expected
                    if role == "patient":
                        assert response.headers["cache-control"] == "private, no-store"
            app.dependency_overrides[get_current_user] = (
                lambda: SimpleNamespace(id=PATIENT, role="patient", is_active=True)
            )
            for path in ("/api/lab-requests/me", "/api/home-visit-requests/me"):
                assert (await client.get(path, params={"order": "unknown"})).status_code == 422
        lab_getter.assert_awaited_once_with(str(PATIENT), PageWindow(21, 50), recent_updates=True)
        home_getter.assert_awaited_once_with(str(PATIENT), PageWindow(21, 50), recent_updates=True)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
