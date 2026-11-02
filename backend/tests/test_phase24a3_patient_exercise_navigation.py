"""Offline patient exercise category and assignment-join pagination contracts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import httpx
import pytest

from app.core.pagination import PageWindow
from app.main import app
from app.middleware.auth import get_current_user
from app.models.exercise import Exercise, ExerciseAssignment
from app.repositories.exercise_repository import ExerciseRepository
from app.repositories.profile_repository import ProfileRepository


PATIENT = PydanticObjectId("507f1f77bcf86cd799439011")
EXERCISE = PydanticObjectId("507f1f77bcf86cd799439012")
ASSIGNMENT = PydanticObjectId("507f1f77bcf86cd799439013")


@pytest.mark.asyncio
async def test_catalog_category_filter_precedes_stable_page(monkeypatch):
    query = Mock()
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    finder = Mock(return_value=query)
    monkeypatch.setattr(Exercise, "find", finder)
    assert await ExerciseRepository.list_page_exercises(True, PageWindow(21, 50), "mobility") == []
    assert finder.call_args.args[0] == {"active": True, "category": "mobility"}
    query.sort.assert_called_once_with("+title", "+_id")
    query.skip.assert_called_once_with(1000)
    query.limit.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_assignment_join_scopes_owner_and_category_before_page(monkeypatch):
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=[]))
    collection = SimpleNamespace(aggregate=Mock(return_value=cursor))
    monkeypatch.setattr(ExerciseAssignment, "get_pymongo_collection", Mock(return_value=collection))
    assert await ExerciseRepository.list_patient_assignment_details(
        str(PATIENT), PageWindow(21, 50), "strength",
    ) == []
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {"patient_id": PATIENT}}
    assert pipeline[3] == {"$match": {"exercise.active": True, "exercise.category": "strength"}}
    assert pipeline[4] == {"$sort": {"assigned_at": -1, "_id": -1}}
    assert pipeline[5:7] == [{"$skip": 1000}, {"$limit": 50}]
    cursor.to_list.assert_awaited_once_with(length=50)


@pytest.mark.asyncio
async def test_patient_detail_route_and_foreign_roles(monkeypatch):
    row = {
        "_id": ASSIGNMENT, "exercise_id": EXERCISE,
        "exercise": {"title": "Fictional mobility", "category": "mobility",
                     "description": "Fictional exercise", "instructions": [],
                     "safety_precautions": []},
        "sets": 2, "reps": 3, "duration_seconds": 60, "status": "assigned",
    }
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id=PATIENT),
    ))
    getter = AsyncMock(return_value=[row])
    monkeypatch.setattr(ExerciseRepository, "list_patient_assignment_details", getter)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            for role, expected in (("patient", 200), ("doctor", 403), ("admin", 403)):
                app.dependency_overrides[get_current_user] = (
                    lambda role=role: SimpleNamespace(id=PATIENT, role=role, is_active=True)
                )
                response = await client.get("/api/exercise-assignments/me/details", params={
                    "category": "mobility", "page": 21,
                })
                assert response.status_code == expected
                if role == "patient":
                    assert response.json()[0]["title"] == "Fictional mobility"
                    assert response.headers["cache-control"] == "private, no-store"
            app.dependency_overrides[get_current_user] = (
                lambda: SimpleNamespace(id=PATIENT, role="patient", is_active=True)
            )
            assert (await client.get("/api/exercise-assignments/me/details?category=unknown")).status_code == 422
        getter.assert_awaited_once_with(str(PATIENT), PageWindow(21, 50), "mobility")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
