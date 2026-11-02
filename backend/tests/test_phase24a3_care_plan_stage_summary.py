"""Offline patient care-plan stage totals without loading all assignments."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import httpx
import pytest

from app.main import app
from app.middleware.auth import get_current_user
from app.models.exercise import ExerciseAssignment
from app.repositories.care_plan_repository import CarePlanRepository
from app.repositories.exercise_repository import ExerciseRepository
from app.repositories.profile_repository import ProfileRepository


PATIENT = PydanticObjectId("507f1f77bcf86cd799439011")
OTHER = PydanticObjectId("507f1f77bcf86cd799439012")
PLAN = PydanticObjectId("507f1f77bcf86cd799439013")


@pytest.mark.asyncio
async def test_stage_summary_aggregates_only_owned_plan_and_preserves_counts(monkeypatch):
    rows = [{"stage_id": "fictional-stage", "prescribed": 1201, "completed": 601}]
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=rows))
    collection = SimpleNamespace(aggregate=Mock(return_value=cursor))
    monkeypatch.setattr(ExerciseAssignment, "get_pymongo_collection", Mock(return_value=collection))
    assert await ExerciseRepository.aggregate_care_plan_stage_counts(str(PATIENT), str(PLAN)) == rows
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {"patient_id": PATIENT, "care_plan_id": PLAN}}
    assert pipeline[1]["$group"]["prescribed"] == {"$sum": 1}
    assert pipeline[1]["$group"]["completed"]["$sum"]["$cond"][0] == {
        "$eq": ["$status", "completed"],
    }
    cursor.to_list.assert_awaited_once_with(length=None)


@pytest.mark.asyncio
async def test_stage_summary_route_is_patient_only_and_conceals_foreign_plan(monkeypatch):
    finder = AsyncMock(return_value=SimpleNamespace(patient_id=PATIENT))
    profile = AsyncMock(return_value=SimpleNamespace(id=PATIENT))
    summary = AsyncMock(return_value=[])
    monkeypatch.setattr(CarePlanRepository, "get_by_id", finder)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", profile)
    monkeypatch.setattr(ExerciseRepository, "aggregate_care_plan_stage_counts", summary)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            for role, expected in (("patient", 200), ("doctor", 403), ("admin", 403)):
                app.dependency_overrides[get_current_user] = (
                    lambda role=role: SimpleNamespace(id=PATIENT, role=role, is_active=True)
                )
                response = await client.get(f"/api/care-plans/{PLAN}/exercise-summary")
                assert response.status_code == expected
                if role == "patient":
                    assert response.headers["cache-control"] == "private, no-store"
            finder.return_value = SimpleNamespace(patient_id=OTHER)
            app.dependency_overrides[get_current_user] = (
                lambda: SimpleNamespace(id=PATIENT, role="patient", is_active=True)
            )
            denied = await client.get(f"/api/care-plans/{PLAN}/exercise-summary")
            assert denied.status_code == 404
        summary.assert_awaited_once_with(str(PATIENT), str(PLAN))
    finally:
        app.dependency_overrides.pop(get_current_user, None)
