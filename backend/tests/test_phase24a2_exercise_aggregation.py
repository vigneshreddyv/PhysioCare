"""Offline aggregation and output contracts for patient exercise statistics."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import pytest

from app.models.care_plan import CarePlan
from app.models.exercise import ExerciseAssignment, ExerciseProgress
from app.repositories.care_plan_repository import CarePlanRepository
from app.repositories.exercise_repository import ExerciseRepository
from app.services.exercise_service import ExerciseService


PATIENT = PydanticObjectId("507f1f77bcf86cd799439011")
EXERCISE = PydanticObjectId("507f1f77bcf86cd799439012")
ASSIGNMENT = PydanticObjectId("507f1f77bcf86cd799439013")


def collection_with_rows(rows):
    collection = Mock()
    collection.aggregate.return_value = SimpleNamespace(to_list=AsyncMock(return_value=[rows]))
    return collection


@pytest.mark.asyncio
async def test_assignment_aggregation_filters_patient_and_cancelled_before_grouping(monkeypatch):
    collection = collection_with_rows({"summary": [{"total": 2, "completed": 1}]})
    monkeypatch.setattr(ExerciseAssignment, "get_pymongo_collection", Mock(return_value=collection))
    result = await ExerciseRepository.aggregate_assignment_stats(str(PATIENT))
    assert result["summary"] == [{"total": 2, "completed": 1}]
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {
        "patient_id": PATIENT, "status": {"$ne": "cancelled"},
    }}
    assert pipeline[1] == {"$sort": {"assigned_at": -1, "_id": -1}}
    facets = pipeline[2]["$facet"]
    assert set(facets) == {"summary", "stages", "targets"}
    assert facets["summary"][0]["$group"]["completed"] == {
        "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]},
    }
    assert facets["targets"][0]["$group"]["sets"] == {"$first": "$sets"}


@pytest.mark.asyncio
async def test_progress_aggregation_projects_recent_and_rechecks_assignment_ownership(monkeypatch):
    collection = collection_with_rows({"summary": [], "recent": []})
    monkeypatch.setattr(ExerciseProgress, "get_pymongo_collection", Mock(return_value=collection))
    start = datetime(2026, 11, 2)
    end = start + timedelta(days=1)
    await ExerciseRepository.aggregate_progress_stats(str(PATIENT), start, end)
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {"patient_id": PATIENT}}
    facets = pipeline[1]["$facet"]
    assert facets["week"][0] == {"$match": {
        "completed_at": {"$gte": start, "$lt": end},
    }}
    assert facets["recent"][0] == {"$sort": {"completed_at": -1, "_id": -1}}
    assert facets["recent"][1] == {"$limit": 5}
    assert facets["recent"][-1]["$project"]["exercise_name"]
    assert facets["exercises"][0]["$group"]["performance_count"] == {"$sum": 1}
    assert facets["stages"][0]["$lookup"]["from"] == "exercise_assignments"
    assert facets["stages"][2] == {"$match": {
        "assignment.patient_id": PATIENT,
        "assignment.status": {"$ne": "cancelled"},
    }}


@pytest.mark.asyncio
async def test_active_care_plan_titles_use_one_projected_patient_query(monkeypatch):
    collection = Mock()
    collection.find_one = AsyncMock(return_value={"stages": [
        {"stage_id": "stage-a", "title": "Fictional mobility"},
    ]})
    monkeypatch.setattr(CarePlan, "get_pymongo_collection", Mock(return_value=collection))
    assert await CarePlanRepository.get_active_stage_titles(str(PATIENT)) == {
        "stage-a": "Fictional mobility",
    }
    assert collection.find_one.call_args.args[0] == {
        "patient_id": PATIENT, "status": "active",
    }
    assert collection.find_one.call_args.kwargs["projection"] == {
        "stages.stage_id": 1, "stages.title": 1,
    }


@pytest.mark.asyncio
async def test_large_grouped_totals_keep_existing_response_without_full_collection_reads(monkeypatch):
    now = datetime(2026, 11, 2, 12)
    assignment_data = {
        "summary": [{"total": 100_000, "completed": 75_000}],
        "stages": [{"_id": "stage-a", "assigned_exercise_count": 100_000}],
        "targets": [{"_id": EXERCISE, "sets": 3, "reps": 12}],
    }
    progress_data = {
        "summary": [{"completed_sessions": 100_000, "partial_sessions": 10_000}],
        "week": [{"_id": now.date().isoformat()}],
        "recent": [{
            "assignment_id": ASSIGNMENT, "exercise_id": EXERCISE,
            "exercise_name": "Fictional exercise", "completed_at": now,
            "completed_sets": 3, "completed_reps": 12, "duration_seconds": 60,
            "completion_status": "completed", "notes": None,
        }],
        "exercises": [{
            "_id": EXERCISE, "exercise_name": "Fictional exercise",
            "performance_count": 110_000, "completed_sessions": 100_000,
            "partial_sessions": 10_000, "latest_completion": now,
        }],
        "stages": [{
            "_id": "stage-a", "exercises_with_activity": 1,
            "completed_sessions": 100_000, "latest_completion": now,
        }],
    }
    monkeypatch.setattr(ExerciseRepository, "aggregate_assignment_stats", AsyncMock(
        return_value=assignment_data,
    ))
    monkeypatch.setattr(ExerciseRepository, "aggregate_progress_stats", AsyncMock(
        return_value=progress_data,
    ))
    monkeypatch.setattr(CarePlanRepository, "get_active_stage_titles", AsyncMock(
        return_value={"stage-a": "Fictional stage"},
    ))
    old_reads = ("list_assignments_by_patient", "list_progress_by_patient", "list_exercises")
    for method in old_reads:
        monkeypatch.setattr(ExerciseRepository, method, AsyncMock(
            side_effect=AssertionError(f"{method} materializes full records"),
        ))
    stats = await ExerciseService.get_exercise_progress_stats(str(PATIENT))
    assert stats["total"] == 100_000
    assert stats["completed"] == 75_000
    assert stats["percentage"] == 75
    assert stats["completed_sessions"] == 100_000
    assert stats["partial_sessions"] == 10_000
    assert len(stats["recent_activity"]) == 1
    assert stats["exercise_breakdown"][0]["prescribed_target"] == "3 sets x 12 reps"
    assert stats["stage_breakdown"][0]["stage_title"] == "Fictional stage"


@pytest.mark.asyncio
async def test_empty_patient_statistics_keep_existing_neutral_contract(monkeypatch):
    assignment = AsyncMock(return_value={"summary": [], "stages": [], "targets": []})
    progress = AsyncMock(return_value={
        "summary": [], "week": [], "recent": [], "exercises": [], "stages": [],
    })
    monkeypatch.setattr(ExerciseRepository, "aggregate_assignment_stats", assignment)
    monkeypatch.setattr(ExerciseRepository, "aggregate_progress_stats", progress)
    monkeypatch.setattr(CarePlanRepository, "get_active_stage_titles", AsyncMock(return_value={}))

    stats = await ExerciseService.get_exercise_progress_stats(str(PATIENT))

    assignment.assert_awaited_once_with(str(PATIENT))
    assert progress.await_args.args[0] == str(PATIENT)
    assert stats["total"] == 0
    assert stats["completed"] == 0
    assert stats["percentage"] == 100
    assert stats["completed_sessions"] == 0
    assert stats["partial_sessions"] == 0
    assert stats["recent_activity"] == []
    assert stats["exercise_breakdown"] == []
    assert stats["stage_breakdown"] == []
    assert len(stats["log"]) == 7

