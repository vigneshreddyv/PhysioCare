import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from beanie import PydanticObjectId
from fastapi import HTTPException
from app.models.exercise import Exercise, ExerciseAssignment
from app.services.exercise_service import ExerciseService
from app.api.exercises import (
    get_assignment,
    get_patient_stats_for_clinician,
    list_progress_for_clinician,
)

@pytest.fixture(autouse=True)
def mock_exercise_insert_globally():
    with patch("app.models.exercise.Exercise.insert", new_callable=AsyncMock) as mock_ins, \
         patch("app.models.exercise.ExerciseAssignment.insert", new_callable=AsyncMock) as mock_assign_ins:
        yield mock_ins, mock_assign_ins


@pytest.mark.asyncio
async def test_exercise_model_creation():
    exercise = Exercise(
        title="Rotator Cuff Strengthening",
        description="Strengthens rotator cuff stabilizers.",
        category="strength",
        difficulty="medium",
        instructions=["Pull band with elbow at side"],
        sets=3,
        reps=10,
        duration_seconds=300,
        target_muscles=["Rotator cuff", "Shoulder"],
        equipment=["Resistance band"]
    )
    assert exercise.title == "Rotator Cuff Strengthening"
    assert exercise.sets == 3
    assert exercise.active is True


@pytest.mark.asyncio
async def test_exercise_creation_validation():
    # Category validation
    invalid_data = {
        "title": "Ex",
        "description": "desc",
        "category": "cardio",  # Invalid category
        "difficulty": "medium",
        "instructions": ["Step"],
        "sets": 3,
        "reps": 10,
        "duration_seconds": 120
    }
    with pytest.raises(ValueError) as exc:
        await ExerciseService.create_exercise(invalid_data)
    assert "Invalid exercise category" in str(exc.value)

    # Sets validation
    invalid_sets_data = {
        "title": "Ex",
        "description": "desc",
        "category": "strength",
        "difficulty": "medium",
        "instructions": ["Step"],
        "sets": -1,  # Invalid sets
        "reps": 10,
        "duration_seconds": 120
    }
    with pytest.raises(ValueError) as exc:
        await ExerciseService.create_exercise(invalid_sets_data)
    assert "Sets, reps, and duration must be positive" in str(exc.value)


@pytest.mark.asyncio
async def test_assignment_creation_valid():
    mock_patient = MagicMock()
    mock_care_plan = MagicMock()
    mock_care_plan.patient_id = PydanticObjectId("000000000000000000000001")
    
    mock_stage = MagicMock()
    mock_stage.stage_id = "stage_1"
    mock_care_plan.stages = [mock_stage]

    mock_exercise = MagicMock()
    mock_exercise.active = True

    with patch("app.models.patient.Patient.get", return_value=mock_patient), \
         patch("app.repositories.care_plan_repository.CarePlanRepository.get_by_id", return_value=mock_care_plan), \
         patch("app.repositories.exercise_repository.ExerciseRepository.get_exercise_by_id", return_value=mock_exercise):
        
        assignment_data = {
            "patient_id": "000000000000000000000001",
            "care_plan_id": "000000000000000000000002",
            "stage_id": "stage_1",
            "exercise_id": "000000000000000000000003",
            "sets": 3,
            "reps": 10,
            "duration_seconds": 300,
            "frequency": "daily"
        }
        res = await ExerciseService.create_assignment(assignment_data, "000000000000000000000004")
        assert res is not None


@pytest.mark.asyncio
async def test_assignment_creation_missing_patient():
    with patch("app.models.patient.Patient.get", return_value=None):
        assignment_data = {
            "patient_id": "000000000000000000000001",
            "care_plan_id": "000000000000000000000002",
            "stage_id": "stage_1",
            "exercise_id": "000000000000000000000003",
            "sets": 3,
            "reps": 10,
            "duration_seconds": 300,
            "frequency": "daily"
        }
        with pytest.raises(ValueError) as exc:
            await ExerciseService.create_assignment(assignment_data, "000000000000000000000004")
        assert "Patient does not exist" in str(exc.value)


@pytest.mark.asyncio
async def test_assignment_creation_wrong_care_plan_owner():
    mock_patient = MagicMock()
    mock_care_plan = MagicMock()
    # Owner mismatch
    mock_care_plan.patient_id = PydanticObjectId("000000000000000000000099")

    with patch("app.models.patient.Patient.get", return_value=mock_patient), \
         patch("app.repositories.care_plan_repository.CarePlanRepository.get_by_id", return_value=mock_care_plan):
        
        assignment_data = {
            "patient_id": "000000000000000000000001",
            "care_plan_id": "000000000000000000000002",
            "stage_id": "stage_1",
            "exercise_id": "000000000000000000000003",
            "sets": 3,
            "reps": 10,
            "duration_seconds": 300,
            "frequency": "daily"
        }
        with pytest.raises(ValueError) as exc:
            await ExerciseService.create_assignment(assignment_data, "000000000000000000000004")
        assert "belong to the specified patient" in str(exc.value)


@pytest.mark.asyncio
async def test_assignment_creation_inactive_exercise_rejected():
    mock_patient = MagicMock()
    mock_care_plan = MagicMock()
    mock_care_plan.patient_id = PydanticObjectId("000000000000000000000001")
    mock_stage = MagicMock()
    mock_stage.stage_id = "stage_1"
    mock_care_plan.stages = [mock_stage]

    mock_exercise = MagicMock()
    mock_exercise.active = False  # Inactive

    with patch("app.models.patient.Patient.get", return_value=mock_patient), \
         patch("app.repositories.care_plan_repository.CarePlanRepository.get_by_id", return_value=mock_care_plan), \
         patch("app.repositories.exercise_repository.ExerciseRepository.get_exercise_by_id", return_value=mock_exercise):
        
        assignment_data = {
            "patient_id": "000000000000000000000001",
            "care_plan_id": "000000000000000000000002",
            "stage_id": "stage_1",
            "exercise_id": "000000000000000000000003",
            "sets": 3,
            "reps": 10,
            "duration_seconds": 300,
            "frequency": "daily"
        }
        with pytest.raises(ValueError) as exc:
            await ExerciseService.create_assignment(assignment_data, "000000000000000000000004")
        assert "Cannot assign an inactive exercise" in str(exc.value)


@pytest.mark.asyncio
async def test_assignment_update_patient_restricted():
    mock_assignment = MagicMock()
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    mock_assignment.status = "assigned"

    with patch("app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id", return_value=mock_assignment):
        # Patient trying to modify prescription parameters (sets/reps) -> PermissionError
        with pytest.raises(PermissionError) as exc:
            await ExerciseService.update_assignment(
                "assignment_id",
                {"sets": 5, "status": "in_progress"},
                user_role="patient",
                actor_user_id="000000000000000000000001"
            )
        assert "authorized to update the completion status" in str(exc.value)


@pytest.mark.asyncio
async def test_authorized_doctor_can_update_assignment():
    mock_assignment = MagicMock()
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    mock_assignment.status = "assigned"
    mock_assignment.save = AsyncMock()

    with patch(
        "app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id",
        return_value=mock_assignment,
    ), patch(
        "app.services.clinical_authorization.require_doctor_patient_access",
        return_value=MagicMock(),
    ):
        updated = await ExerciseService.update_assignment(
            "assignment_id",
            {"status": "in_progress"},
            user_role="doctor",
            actor_user_id="doctor-user",
        )

    assert updated is mock_assignment


@pytest.mark.asyncio
async def test_admin_can_update_assignment_without_doctor_patient_relationship():
    mock_assignment = MagicMock()
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    mock_assignment.status = "assigned"
    mock_assignment.save = AsyncMock()

    with patch(
        "app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id",
        return_value=mock_assignment,
    ), patch(
        "app.services.clinical_authorization.require_doctor_patient_access",
        new_callable=AsyncMock,
    ) as mock_authorization:
        updated = await ExerciseService.update_assignment(
            "assignment_id",
            {"status": "in_progress"},
            user_role="admin",
            actor_user_id="admin-user",
        )

    assert updated is mock_assignment
    mock_authorization.assert_not_awaited()


@pytest.mark.asyncio
async def test_unauthorized_doctor_cannot_update_assignment():
    mock_assignment = MagicMock()
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    mock_assignment.status = "assigned"

    with patch(
        "app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id",
        return_value=mock_assignment,
    ), patch(
        "app.services.clinical_authorization.require_doctor_patient_access",
        side_effect=PermissionError("Doctor is not authorized"),
    ):
        with pytest.raises(PermissionError, match="not authorized"):
            await ExerciseService.update_assignment(
                "assignment_id",
                {"status": "in_progress"},
                user_role="doctor",
                actor_user_id="other-doctor",
            )


@pytest.mark.asyncio
async def test_assignment_detail_rejects_non_clinical_authenticated_roles():
    current_user = MagicMock(role="receptionist")

    with pytest.raises(HTTPException) as exc_info:
        await get_assignment("assignment_id", current_user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_doctor_progress_stats_rejects_unassigned_patient():
    current_user = MagicMock(role="doctor", id="doctor-user")

    with patch(
        "app.services.clinical_authorization.require_doctor_patient_access",
        side_effect=PermissionError("Doctor is not authorized"),
    ), patch(
        "app.api.exercises.ExerciseService.get_exercise_progress_stats",
        new_callable=AsyncMock,
    ) as mock_stats:
        with pytest.raises(HTTPException) as exc_info:
            await get_patient_stats_for_clinician("patient-id", current_user)

    assert exc_info.value.status_code == 403
    mock_stats.assert_not_awaited()


@pytest.mark.asyncio
async def test_doctor_progress_history_rejects_unassigned_patient():
    current_user = MagicMock(role="doctor", id="doctor-user")

    with patch(
        "app.services.clinical_authorization.require_doctor_patient_access",
        side_effect=PermissionError("Doctor is not authorized"),
    ), patch(
        "app.api.exercises.ExerciseService.list_progress_for_patient",
        new_callable=AsyncMock,
    ) as mock_history:
        with pytest.raises(HTTPException) as exc_info:
            await list_progress_for_clinician("patient-id", current_user)

    assert exc_info.value.status_code == 403
    mock_history.assert_not_awaited()


@pytest.mark.asyncio
async def test_assignment_update_patient_lifecycle_ok():
    mock_assignment = MagicMock()
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    mock_assignment.status = "assigned"
    mock_assignment.save = AsyncMock()

    with patch("app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id", return_value=mock_assignment):
        # Patient modifying only status -> OK
        res = await ExerciseService.update_assignment(
            "assignment_id",
            {"status": "in_progress"},
            user_role="patient",
            actor_user_id="000000000000000000000001"
        )
        assert res is not None
        assert mock_assignment.status == "in_progress"


@pytest.mark.asyncio
async def test_assignment_update_invalid_lifecycle_transition():
    mock_assignment = MagicMock()
    mock_assignment.patient_id = PydanticObjectId("000000000000000000000001")
    mock_assignment.status = "assigned"
    mock_assignment.save = AsyncMock()

    with patch("app.repositories.exercise_repository.ExerciseRepository.get_assignment_by_id", return_value=mock_assignment):
        # assigned -> completed is not a direct status jump allowed (must pass through in_progress)
        with pytest.raises(ValueError) as exc:
            await ExerciseService.update_assignment(
                "assignment_id",
                {"status": "completed"},
                user_role="patient",
                actor_user_id="000000000000000000000001"
            )
        assert "Invalid transition from assigned to completed" in str(exc.value)
