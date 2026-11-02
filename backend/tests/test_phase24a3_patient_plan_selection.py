"""Offline active/latest care-plan selection without scanning lifetime plans."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import httpx
import pytest

from app.main import app
from app.middleware.auth import get_current_user
from app.models.care_plan import CarePlan
from app.repositories.care_plan_repository import CarePlanRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.care_plan_service import CarePlanService


PATIENT = PydanticObjectId("507f1f77bcf86cd799439011")


def one_result(value):
    query = Mock()
    query.sort.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[value] if value else [])
    return query


@pytest.mark.asyncio
async def test_active_plan_is_selected_before_latest_fallback(monkeypatch):
    selected = SimpleNamespace(id="fictional-active")
    finder = Mock(return_value=one_result(selected))
    monkeypatch.setattr(CarePlan, "find", finder)
    assert await CarePlanRepository.get_active_or_latest_by_patient_id(str(PATIENT)) is selected
    finder.assert_called_once_with({"patient_id": PATIENT, "status": "active"})
    finder.return_value.sort.assert_called_once_with("-created_at", "-_id")
    finder.return_value.limit.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_latest_plan_fallback_is_still_patient_scoped(monkeypatch):
    latest = SimpleNamespace(id="fictional-latest")
    finder = Mock(side_effect=[one_result(None), one_result(latest)])
    monkeypatch.setattr(CarePlan, "find", finder)
    assert await CarePlanRepository.get_active_or_latest_by_patient_id(str(PATIENT)) is latest
    assert finder.call_args_list[0].args[0] == {"patient_id": PATIENT, "status": "active"}
    assert finder.call_args_list[1].args[0] == {"patient_id": PATIENT}


@pytest.mark.asyncio
async def test_patient_selection_route_validates_page_and_role(monkeypatch):
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id=PATIENT),
    ))
    selector = AsyncMock(return_value=None)
    monkeypatch.setattr(CarePlanService, "get_active_or_latest_by_patient", selector)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        monkeypatch.setitem(app.dependency_overrides, get_current_user,
                            lambda: SimpleNamespace(id=PATIENT, role="patient", is_active=True))
        first = await client.get("/api/care-plans", params={"selection": "active_latest"})
        assert first.status_code == 200
        assert first.json() == []
        selector.assert_awaited_once_with(str(PATIENT))
        later = await client.get("/api/care-plans", params={
            "selection": "active_latest", "page": 21,
        })
        assert later.status_code == 200
        assert later.json() == []
        selector.assert_awaited_once()
        invalid = await client.get("/api/care-plans", params={"selection": "typo"})
        assert invalid.status_code == 422
        monkeypatch.setitem(app.dependency_overrides, get_current_user,
                            lambda: SimpleNamespace(id=PATIENT, role="doctor", is_active=True))
        denied = await client.get("/api/care-plans", params={"selection": "active_latest"})
        assert denied.status_code == 403
