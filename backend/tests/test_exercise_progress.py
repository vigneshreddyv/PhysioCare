import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from beanie import PydanticObjectId
from app.core.time import utc_now
from app.models.exercise import ExerciseProgress
from app.services.exercise_service import ExerciseService
from app.repositories.exercise_repository import ExerciseRepository

@pytest.fixture(autouse=True)
def mock_progress_insert_globally():
    with patch("app.models.exercise.ExerciseProgress.insert", new_callable=AsyncMock) as mock_ins:
        yield mock_ins


@pytest.fixture(autouse=True)
def mock_progress_transaction_repository():
    async def apply_transition(progress, **kwargs):
        assignment = await ExerciseRepository.get_assignment_by_id(kwargs["assignment_id"])
        assignment.status = kwargs["next_status"]
        assignment.revision = kwargs["expected_revision"] + 1
        return progress

    with patch.object(
        ExerciseRepository,
        "create_progress_with_assignment_transition",
        side_effect=apply_transition,
    ):
        yield


@pytest.mark.asyncio
async def test_progress_model_creation():
    progress = ExerciseProgress(
        patient_id=PydanticObjectId("000000000000000000000001"),
        assignment_id=PydanticObjectId("000000000000000000000002"),
        exercise_id=PydanticObjectId("000000000000000000000003"),
        care_plan_id=PydanticObjectId("000000000000000000000004"),
        stage_id="stage_1",
        completed_sets=3,
        completed_reps=10,
        duration_seconds=300,
        completion_status="completed",
        notes="Pain was minimal."
    )
    assert progress.completed_sets == 3
    assert progress.completion_status == "completed"


@pytest.mark.asyncio
async def test_create_progress_record_success():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("000000000000000000000001")

    mock_assignment = MagicMock()
    mock_assignment.id = PydanticObjectId("000000000000000000000002")
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    mock_assignment.exercise_id = PydanticObjectId("000000000000000000000003")
    mock_assignment.care_plan_id = PydanticObjectId("000000000000000000000004")
    mock_assignment.stage_id = "stage_1"
    mock_assignment.status = "assigned"
    mock_assignment.save = AsyncMock()

    with patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient), \
         patch("app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id", return_value=mock_assignment), \
         patch("app.repositories.exercise_repository.ExerciseRepository.create_progress", return_value=MagicMock(completion_status="completed")):
        
        progress_data = {
            "assignment_id": "000000000000000000000002",
            "completed_sets": 3,
            "completed_reps": 10,
            "duration_seconds": 300,
            "completion_status": "completed"
        }
        res = await ExerciseService.create_progress_record(progress_data, "user_id_1")
        assert res is not None
        assert mock_assignment.status == "completed"  # Automatical transition checked!


@pytest.mark.asyncio
async def test_create_progress_wrong_owner_rejected():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("000000000000000000000001")

    mock_assignment = MagicMock()
    # Mismatched owner
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000099")

    with patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient), \
         patch("app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id", return_value=mock_assignment):
        
        progress_data = {
            "assignment_id": "000000000000000000000002",
            "completed_sets": 3,
            "completed_reps": 10,
            "duration_seconds": 300
        }
        with pytest.raises(PermissionError) as exc:
            await ExerciseService.create_progress_record(progress_data, "user_id_1")
        assert "Assignment does not belong to the patient" in str(exc.value)


@pytest.mark.asyncio
async def test_create_progress_cancelled_assignment_rejected():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("000000000000000000000001")

    mock_assignment = MagicMock()
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    # Cancelled assignment status
    mock_assignment.status = "cancelled"

    with patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient), \
         patch("app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id", return_value=mock_assignment):
        
        progress_data = {
            "assignment_id": "000000000000000000000002",
            "completed_sets": 3,
            "completed_reps": 10,
            "duration_seconds": 300
        }
        with pytest.raises(ValueError) as exc:
            await ExerciseService.create_progress_record(progress_data, "user_id_1")
        assert "Cannot record progress against a cancelled assignment" in str(exc.value)


@pytest.mark.asyncio
async def test_get_exercise_progress_stats():
    with patch("app.repositories.exercise_repository.ExerciseRepository.aggregate_assignment_stats",
               new_callable=AsyncMock, return_value={"summary": [{"total": 1, "completed": 1}]}), \
         patch("app.repositories.exercise_repository.ExerciseRepository.aggregate_progress_stats",
               new_callable=AsyncMock, return_value={"week": [{"_id": utc_now().date().isoformat()}]}), \
         patch("app.repositories.care_plan_repository.CarePlanRepository.get_active_stage_titles",
               new_callable=AsyncMock, return_value={}):
        stats = await ExerciseService.get_exercise_progress_stats("patient_id_1")
        assert stats["percentage"] == 100
        assert stats["completed"] == 1
        assert stats["total"] == 1
        assert len(stats["log"]) == 7


@pytest.mark.asyncio
async def test_progress_record_prescription_isolation():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("000000000000000000000001")

    mock_assignment = MagicMock()
    mock_assignment.id = PydanticObjectId("000000000000000000000002")
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    mock_assignment.exercise_id = PydanticObjectId("000000000000000000000003")
    mock_assignment.care_plan_id = PydanticObjectId("000000000000000000000004")
    mock_assignment.stage_id = "stage_1"
    mock_assignment.status = "assigned"
    # Prescriptions
    mock_assignment.sets = 3
    mock_assignment.reps = 10
    mock_assignment.duration_seconds = 300
    mock_assignment.save = AsyncMock()

    with patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient), \
         patch("app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id", return_value=mock_assignment), \
         patch("app.repositories.exercise_repository.ExerciseRepository.create_progress", return_value=MagicMock(completion_status="completed")):
        
        progress_data = {
            "assignment_id": "000000000000000000000002",
            "completed_sets": 5,  # Performed differently
            "completed_reps": 15,
            "duration_seconds": 450,
            "completion_status": "completed"
        }
        await ExerciseService.create_progress_record(progress_data, "user_id_1")
        # Ensure assignment prescription fields remain unmodified!
        assert mock_assignment.sets == 3
        assert mock_assignment.reps == 10
        assert mock_assignment.duration_seconds == 300


@pytest.mark.asyncio
async def test_progress_record_negative_metrics_rejected():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("000000000000000000000001")

    mock_assignment = MagicMock()
    mock_assignment.id = PydanticObjectId("000000000000000000000002")
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    mock_assignment.status = "assigned"

    with patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient), \
         patch("app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id", return_value=mock_assignment):
        
        progress_data = {
            "assignment_id": "000000000000000000000002",
            "completed_sets": -1,  # Negative sets
            "completed_reps": 10,
            "duration_seconds": 300
        }
        with pytest.raises(ValueError) as exc:
            await ExerciseService.create_progress_record(progress_data, "user_id_1")
        assert "Sets, reps, and duration must be non-negative" in str(exc.value)


@pytest.mark.asyncio
async def test_longitudinal_progress_analytics():
    from datetime import timedelta

    with patch("app.repositories.exercise_repository.ExerciseRepository.aggregate_assignment_stats",
               new_callable=AsyncMock, return_value={}), \
         patch("app.repositories.exercise_repository.ExerciseRepository.aggregate_progress_stats",
               new_callable=AsyncMock, return_value={}), \
         patch("app.repositories.care_plan_repository.CarePlanRepository.get_active_stage_titles",
               new_callable=AsyncMock, return_value={}):
        stats = await ExerciseService.get_exercise_progress_stats("patient_1")
        assert stats["percentage"] == 100
        assert stats["completed_sessions"] == 0
        assert stats["recent_activity"] == []
        assert stats["exercise_breakdown"] == []
        assert stats["stage_breakdown"] == []

    exercise_id = PydanticObjectId("000000000000000000000003")
    assignment_id = PydanticObjectId("000000000000000000000001")
    now = utc_now()
    assignments = {
        "summary": [{"total": 1, "completed": 1}],
        "targets": [{"_id": exercise_id, "sets": 3, "reps": 10}],
        "stages": [{"_id": "st_1", "assigned_exercise_count": 1}],
    }
    progress = {
        "summary": [{"completed_sessions": 1, "partial_sessions": 1}],
        "week": [{"_id": now.date().isoformat()}],
        "recent": [
            {"assignment_id": assignment_id, "exercise_id": exercise_id,
             "exercise_name": "Flexion Stretch", "completed_at": now,
             "completed_sets": 3, "completed_reps": 10, "duration_seconds": 120,
             "completion_status": "completed", "notes": "No pain"},
            {"assignment_id": assignment_id, "exercise_id": exercise_id,
             "exercise_name": "Flexion Stretch", "completed_at": now - timedelta(hours=2),
             "completed_sets": 2, "completed_reps": 10, "duration_seconds": 100,
             "completion_status": "partial", "notes": "Slight stiffness"},
        ],
        "exercises": [{"_id": exercise_id, "exercise_name": "Flexion Stretch",
                       "performance_count": 2, "completed_sessions": 1,
                       "partial_sessions": 1, "latest_completion": now}],
        "stages": [{"_id": "st_1", "exercises_with_activity": 1,
                    "completed_sessions": 1, "latest_completion": now}],
    }
    with patch("app.repositories.exercise_repository.ExerciseRepository.aggregate_assignment_stats",
               new_callable=AsyncMock, return_value=assignments) as assignment_query, \
         patch("app.repositories.exercise_repository.ExerciseRepository.aggregate_progress_stats",
               new_callable=AsyncMock, return_value=progress) as progress_query, \
         patch("app.repositories.care_plan_repository.CarePlanRepository.get_active_stage_titles",
               new_callable=AsyncMock, return_value={"st_1": "Milestone Phase 1"}) as titles_query:
        stats = await ExerciseService.get_exercise_progress_stats("patient_1")

    assignment_query.assert_awaited_once_with("patient_1")
    progress_query.assert_awaited_once()
    titles_query.assert_awaited_once_with("patient_1")
    assert stats["percentage"] == 100
    assert stats["completed_sessions"] == 1
    assert stats["partial_sessions"] == 1
    assert stats["active_assignments"] == 1
    assert stats["recent_activity"][0]["completion_status"] == "completed"
    assert stats["recent_activity"][1]["completion_status"] == "partial"
    assert stats["exercise_breakdown"][0]["exercise_name"] == "Flexion Stretch"
    assert stats["exercise_breakdown"][0]["prescribed_target"] == "3 sets x 10 reps"
    assert stats["stage_breakdown"][0]["stage_title"] == "Milestone Phase 1"
    assert stats["stage_breakdown"][0]["completed_sessions"] == 1
    assert any(day["completed"] is True for day in stats["log"])


