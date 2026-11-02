from unittest.mock import AsyncMock, MagicMock

import pytest
import httpx
from beanie import PydanticObjectId

from app.models.care_plan import CarePlan, CarePlanHistory
from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress
from app.models.report import Report
from app.repositories.care_plan_repository import CarePlanRepository
from app.repositories.exercise_repository import ExerciseRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.profile_repository import ProfileRepository
from app.middleware.auth import get_current_user
from app.main import app


VALID_ID = "000000000000000000000001"

GET_CASES = [
    (ReportRepository.get_by_id, Report),
    (CarePlanRepository.get_by_id, CarePlan),
    (ExerciseRepository.get_exercise_by_id, Exercise),
    (ExerciseRepository.get_assignment_by_id, ExerciseAssignment),
]

LIST_CASES = [
    (CarePlanRepository.get_history_by_care_plan_id, CarePlanHistory, "care_plan_id", "created_at"),
    (ExerciseRepository.list_assignments_by_patient, ExerciseAssignment, "patient_id", "assigned_at"),
    (ExerciseRepository.list_assignments_by_care_plan, ExerciseAssignment, "care_plan_id", "assigned_at"),
    (ExerciseRepository.list_progress_by_patient, ExerciseProgress, "patient_id", "completed_at"),
    (ExerciseRepository.list_progress_by_assignment, ExerciseProgress, "assignment_id", "completed_at"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup, model", GET_CASES)
async def test_malformed_clinical_id_returns_missing_without_query(monkeypatch, lookup, model):
    get = AsyncMock()
    monkeypatch.setattr(model, "get", get)

    assert await lookup("malformed-id") is None
    assert await lookup(None) is None
    get.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup, model", GET_CASES)
async def test_clinical_lookup_preserves_real_result(monkeypatch, lookup, model):
    record = object()
    get = AsyncMock(return_value=record)
    monkeypatch.setattr(model, "get", get)

    assert await lookup(VALID_ID) is record
    get.assert_awaited_once_with(PydanticObjectId(VALID_ID))


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup, model", GET_CASES)
async def test_clinical_lookup_does_not_hide_database_failure(monkeypatch, lookup, model):
    get = AsyncMock(side_effect=RuntimeError("synthetic database failure"))
    monkeypatch.setattr(model, "get", get)

    with pytest.raises(RuntimeError, match="synthetic database failure"):
        await lookup(VALID_ID)
    get.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup, model, filter_field, sort_field", LIST_CASES)
async def test_malformed_clinical_list_id_returns_empty_without_query(monkeypatch, lookup, model, filter_field, sort_field):
    find = MagicMock()
    monkeypatch.setattr(model, "find", find)

    assert await lookup("malformed-id") == []
    assert await lookup(None) == []
    find.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup, model, filter_field, sort_field", LIST_CASES)
async def test_clinical_list_preserves_empty_result(monkeypatch, lookup, model, filter_field, sort_field):
    monkeypatch.setattr(model, filter_field, MagicMock(), raising=False)
    monkeypatch.setattr(model, sort_field, MagicMock(), raising=False)
    query = MagicMock()
    query.sort.return_value.to_list = AsyncMock(return_value=[])
    find = MagicMock(return_value=query)
    monkeypatch.setattr(model, "find", find)

    assert await lookup(VALID_ID) == []
    find.assert_called_once()
    query.sort.return_value.to_list.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup, model, filter_field, sort_field", LIST_CASES)
async def test_clinical_list_does_not_hide_database_failure(monkeypatch, lookup, model, filter_field, sort_field):
    monkeypatch.setattr(model, filter_field, MagicMock(), raising=False)
    monkeypatch.setattr(model, sort_field, MagicMock(), raising=False)
    query = MagicMock()
    query.sort.return_value.to_list = AsyncMock(side_effect=RuntimeError("synthetic database failure"))
    find = MagicMock(return_value=query)
    monkeypatch.setattr(model, "find", find)

    with pytest.raises(RuntimeError, match="synthetic database failure"):
        await lookup(VALID_ID)
    find.assert_called_once()
    query.sort.return_value.to_list.assert_awaited_once()


@pytest.mark.asyncio
async def test_report_route_keeps_bad_id_not_found_and_database_fault_generic(monkeypatch):
    patient_id = PydanticObjectId(VALID_ID)
    user = type("PatientUser", (), {"id": PydanticObjectId(), "role": "patient"})()
    patient = type("PatientProfile", (), {"id": patient_id})()
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: user)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    get = AsyncMock(side_effect=RuntimeError("synthetic database failure"))
    monkeypatch.setattr(Report, "get", get)

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://offline.test") as client:
        missing = await client.get("/api/reports/malformed-id")
        assert missing.status_code == 404
        get.assert_not_awaited()

        failed = await client.get(f"/api/reports/{VALID_ID}")
        assert failed.status_code == 500
        assert failed.text == "Internal Server Error"
        get.assert_awaited_once_with(PydanticObjectId(VALID_ID))
