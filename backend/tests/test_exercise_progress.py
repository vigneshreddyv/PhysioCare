import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from beanie import PydanticObjectId
from app.models.exercise import ExerciseProgress
from app.services.exercise_service import ExerciseService

@pytest.fixture(autouse=True)
def mock_progress_insert_globally():
    with patch("app.models.exercise.ExerciseProgress.insert", new_callable=AsyncMock) as mock_ins:
        yield mock_ins


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
    # Mock active assignments and progress logs list
    mock_assign = MagicMock()
    mock_assign.status = "completed"
    
    mock_record = MagicMock()
    # Mock date mapping check
    from datetime import datetime
    mock_record.completed_at = datetime.utcnow()

    with patch("app.repositories.exercise_repository.ExerciseRepository.list_assignments_by_patient", return_value=[mock_assign]), \
         patch("app.repositories.exercise_repository.ExerciseRepository.list_progress_by_patient", return_value=[mock_record]), \
         patch("app.repositories.care_plan_repository.CarePlanRepository.get_by_patient_id", return_value=[]), \
         patch("app.repositories.exercise_repository.ExerciseRepository.list_exercises", return_value=[]):
        
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
    # 1. Test zero assignments case (division-by-zero protection)
    with patch("app.repositories.exercise_repository.ExerciseRepository.list_assignments_by_patient", return_value=[]), \
         patch("app.repositories.exercise_repository.ExerciseRepository.list_progress_by_patient", return_value=[]), \
         patch("app.repositories.care_plan_repository.CarePlanRepository.get_by_patient_id", return_value=[]), \
         patch("app.repositories.exercise_repository.ExerciseRepository.list_exercises", return_value=[]):
        
        stats = await ExerciseService.get_exercise_progress_stats("patient_1")
        assert stats["percentage"] == 100
        assert stats["completed_sessions"] == 0
        assert len(stats["recent_activity"]) == 0
        assert len(stats["exercise_breakdown"]) == 0
        assert len(stats["stage_breakdown"]) == 0

    # 2. Test multiple assignments, some cancelled, mixed completion statuses
    mock_ex = MagicMock()
    mock_ex.id = PydanticObjectId("000000000000000000000003")
    mock_ex.title = "Flexion Stretch"

    mock_assign_1 = MagicMock()
    mock_assign_1.id = PydanticObjectId("000000000000000000000001")
    mock_assign_1.exercise_id = mock_ex.id
    mock_assign_1.status = "completed"
    mock_assign_1.sets = 3
    mock_assign_1.reps = 10
    mock_assign_1.stage_id = "st_1"

    # Cancelled assignment should be ignored in active total
    mock_assign_cancelled = MagicMock()
    mock_assign_cancelled.id = PydanticObjectId("000000000000000000000002")
    mock_assign_cancelled.status = "cancelled"

    from datetime import datetime, timedelta
    p1 = MagicMock()
    p1.assignment_id = mock_assign_1.id
    p1.exercise_id = mock_ex.id
    p1.completion_status = "completed"
    p1.completed_at = datetime.utcnow()
    p1.completed_sets = 3
    p1.completed_reps = 10
    p1.duration_seconds = 120
    p1.notes = "No pain"

    p2 = MagicMock()
    p2.assignment_id = mock_assign_1.id
    p2.exercise_id = mock_ex.id
    p2.completion_status = "partial"
    p2.completed_at = datetime.utcnow() - timedelta(hours=2)
    p2.completed_sets = 2
    p2.completed_reps = 10
    p2.duration_seconds = 100
    p2.notes = "Slight stiffness"

    mock_cp = MagicMock()
    mock_cp.status = "active"
    stage_mock = MagicMock()
    stage_mock.stage_id = "st_1"
    stage_mock.title = "Milestone Phase 1"
    mock_cp.stages = [stage_mock]

    with patch("app.repositories.exercise_repository.ExerciseRepository.list_assignments_by_patient", return_value=[mock_assign_1, mock_assign_cancelled]), \
         patch("app.repositories.exercise_repository.ExerciseRepository.list_progress_by_patient", return_value=[p1, p2]), \
         patch("app.repositories.care_plan_repository.CarePlanRepository.get_by_patient_id", return_value=[mock_cp]), \
         patch("app.repositories.exercise_repository.ExerciseRepository.list_exercises", return_value=[mock_ex]):
        
        stats = await ExerciseService.get_exercise_progress_stats("patient_1")
        assert stats["percentage"] == 100
        assert stats["completed_sessions"] == 1
        assert stats["partial_sessions"] == 1
        assert stats["active_assignments"] == 1  # Cancelled assignment correctly excluded

        # Recent activity sorted chronological order checks
        assert len(stats["recent_activity"]) == 2
        assert stats["recent_activity"][0]["completion_status"] == "completed"  # p1 is newer
        assert stats["recent_activity"][1]["completion_status"] == "partial"

        # Exercise Breakdown checking
        assert len(stats["exercise_breakdown"]) == 1
        eb = stats["exercise_breakdown"][0]
        assert eb["exercise_name"] == "Flexion Stretch"
        assert eb["completed_sessions"] == 1
        assert eb["partial_sessions"] == 1

        # Stage Breakdown checking
        assert len(stats["stage_breakdown"]) == 1
        sb = stats["stage_breakdown"][0]
        assert sb["stage_title"] == "Milestone Phase 1"
        assert sb["assigned_exercise_count"] == 1
        assert sb["completed_sessions"] == 1


