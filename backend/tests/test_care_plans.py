import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from beanie import PydanticObjectId
from app.models.care_plan import CarePlan
from app.services.care_plan_service import CarePlanService
from app.repositories.care_plan_repository import CarePlanRepository


@pytest.fixture(autouse=True)
def mock_history_insert_globally():
    with patch("app.models.care_plan.CarePlanHistory.insert", new_callable=AsyncMock) as mock_insert:
        yield mock_insert


@pytest.fixture(autouse=True)
def mock_patient_get_globally():
    mock_patient = MagicMock()
    mock_patient.user_id = PydanticObjectId("000000000000000000000004")
    with patch("app.models.patient.Patient.get", return_value=mock_patient):
        yield mock_patient


@pytest.fixture(autouse=True)
def mock_notification_create_globally():
    with patch("app.services.notification_service.NotificationService.create_notification", new_callable=AsyncMock) as mock_notif:
        yield mock_notif





@pytest.mark.asyncio
async def test_care_plan_model_creation():
    stages = [
        {
            "stage_id": "st1",
            "title": "Stage 1",
            "description": "Pain relief",
            "status": "active",
            "progress": 25.0
        }
    ]
    goals = [
        {
            "goal_id": "g1",
            "title": "Goal 1",
            "description": "Flexion restoration",
            "target_value": 120.0,
            "unit": "degrees",
            "status": "active"
        }
    ]
    recommendations = [
        {
            "recommendation_id": "r1",
            "title": "Exercise daily",
            "description": "Do yellow band rotator sets",
            "priority": "high"
        }
    ]

    cp_data = {
        "patient_id": "000000000000000000000000",
        "therapist_id": "111111111111111111111111",
        "title": "Frozen Shoulder Recovery",
        "description": "Recovery pathway for adhesive capsulitis.",
        "current_stage": 1,
        "stages": stages,
        "goals": goals,
        "recommendations": recommendations,
        "start_date": datetime.utcnow(),
        "target_date": datetime.utcnow() + timedelta(days=60),
        "status": "active"
    }

    care_plan = CarePlan.model_validate(cp_data)
    assert care_plan.title == "Frozen Shoulder Recovery"
    assert len(care_plan.stages) == 1
    assert care_plan.stages[0].status == "active"
    assert care_plan.goals[0].target_value == 120.0


@pytest.mark.asyncio
async def test_create_care_plan_success():
    mock_patient = MagicMock()
    mock_cp = MagicMock()
    mock_cp.id = "cp123"

    with patch("app.models.patient.Patient.get") as mock_patient_get, \
         patch("app.services.care_plan_service.CarePlanRepository.create") as mock_cp_create:

        mock_patient_get.return_value = mock_patient
        mock_cp_create.return_value = mock_cp

        res = await CarePlanService.create_care_plan(
            patient_id="000000000000000000000000",
            therapist_id="111111111111111111111111",
            title="Knee Rehab",
            description="Rehab plan",
            current_stage=1,
            stages=[{"stage_id": "st1", "title": "st", "description": "desc", "status": "active"}],
            goals=[],
            recommendations=[],
            start_date=datetime.utcnow(),
            target_date=datetime.utcnow() + timedelta(days=30),
            status="active"
        )
        assert res.id == "cp123"


@pytest.mark.asyncio
async def test_nonexistent_patient_rejected():
    with patch("app.models.patient.Patient.get") as mock_patient_get:
        mock_patient_get.return_value = None

        with pytest.raises(ValueError) as exc_info:
            await CarePlanService.create_care_plan(
                patient_id="000000000000000000000000",
                therapist_id="111111111111111111111111",
                title="Knee Rehab",
                description="Rehab plan",
                current_stage=1,
                stages=[],
                goals=[],
                recommendations=[],
                start_date=datetime.utcnow(),
                target_date=datetime.utcnow() + timedelta(days=30),
                status="active"
            )
        assert "Target patient profile not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_invalid_stage_status_rejected():
    mock_patient = MagicMock()
    with patch("app.models.patient.Patient.get") as mock_patient_get:
        mock_patient_get.return_value = mock_patient

        with pytest.raises(ValueError) as exc_info:
            await CarePlanService.create_care_plan(
                patient_id="000000000000000000000000",
                therapist_id="111111111111111111111111",
                title="Knee Rehab",
                description="Rehab plan",
                current_stage=1,
                stages=[{"stage_id": "st1", "title": "st", "description": "desc", "status": "invalid_status"}],
                goals=[],
                recommendations=[],
                start_date=datetime.utcnow(),
                target_date=datetime.utcnow() + timedelta(days=30),
                status="active"
            )
        assert "Invalid stage status" in str(exc_info.value)


@pytest.mark.asyncio
async def test_invalid_care_plan_status_rejected():
    mock_patient = MagicMock()
    with patch("app.models.patient.Patient.get") as mock_patient_get:
        mock_patient_get.return_value = mock_patient

        with pytest.raises(ValueError) as exc_info:
            await CarePlanService.create_care_plan(
                patient_id="000000000000000000000000",
                therapist_id="111111111111111111111111",
                title="Knee Rehab",
                description="Rehab plan",
                current_stage=1,
                stages=[],
                goals=[],
                recommendations=[],
                start_date=datetime.utcnow(),
                target_date=datetime.utcnow() + timedelta(days=30),
                status="invalid_status"
            )
        assert "Invalid care plan status" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_care_plans_by_patient():
    mock_plans = [MagicMock(), MagicMock()]
    with patch("app.services.care_plan_service.CarePlanRepository.get_by_patient_id") as mock_get_patient:
        mock_get_patient.return_value = mock_plans
        res = await CarePlanService.get_care_plans_by_patient("patient123")
        assert len(res) == 2


@pytest.mark.asyncio
async def test_get_care_plan_for_patient_owner_success():
    mock_cp = MagicMock()
    mock_cp.patient_id = "000000000000000000000000"
    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        res = await CarePlanService.get_care_plan_for_patient("cp123", "000000000000000000000000")
        assert res is not None


@pytest.mark.asyncio
async def test_get_care_plan_for_patient_idor_failure():
    mock_cp = MagicMock()
    mock_cp.patient_id = "000000000000000000000000"
    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        res = await CarePlanService.get_care_plan_for_patient("cp123", "999999999999999999999999")
        assert res is None


@pytest.mark.asyncio
async def test_update_care_plan_success():
    mock_cp = MagicMock()
    mock_cp.patient_id = "000000000000000000000000"

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        mock_cp.save = AsyncMock()

        # Update title and status
        updated = await CarePlanService.update_care_plan(
            "cp123",
            {"title": "Updated Title", "status": "completed"}
        )
        assert updated is not None
        assert mock_cp.title == "Updated Title"
        assert mock_cp.status == "completed"


@pytest.mark.asyncio
async def test_update_care_plan_not_found():
    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = None
        res = await CarePlanService.update_care_plan("nonexistent", {"title": "Updated"})
        assert res is None


@pytest.mark.asyncio
async def test_update_care_plan_partial_does_not_erase():
    mock_cp = MagicMock()
    mock_cp.patient_id = "000000000000000000000000"
    mock_cp.stages = ["existing_stage"]
    mock_cp.goals = ["existing_goal"]
    mock_cp.recommendations = ["existing_recommendation"]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        mock_cp.save = AsyncMock()

        # Update title only, nested items should not be erased
        updated = await CarePlanService.update_care_plan(
            "cp123",
            {"title": "Updated Title Only"}
        )
        assert updated is not None
        assert mock_cp.title == "Updated Title Only"
        assert mock_cp.stages == ["existing_stage"]
        assert mock_cp.goals == ["existing_goal"]
        assert mock_cp.recommendations == ["existing_recommendation"]


@pytest.mark.asyncio
async def test_update_care_plan_immutable_fields():
    mock_cp = MagicMock()
    mock_cp.patient_id = "000000000000000000000000"
    mock_cp.therapist_id = "111111111111111111111111"

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        mock_cp.save = AsyncMock()

        # Update with different patient_id should fail
        with pytest.raises(ValueError) as exc_info:
            await CarePlanService.update_care_plan(
                "cp123",
                {"patient_id": "999999999999999999999999"}
            )
        assert "Modifying patient_id is not allowed" in str(exc_info.value)

        # Update with different therapist_id should fail
        with pytest.raises(ValueError) as exc_info:
            await CarePlanService.update_care_plan(
                "cp123",
                {"therapist_id": "999999999999999999999999"}
            )
        assert "Modifying therapist_id is not allowed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_stage_upcoming_to_active():
    from app.models.care_plan import Stage
    mock_cp = MagicMock()
    mock_cp.id = PydanticObjectId("000000000000000000000001")
    mock_cp.patient_id = PydanticObjectId("000000000000000000000002")
    mock_cp.therapist_id = PydanticObjectId("000000000000000000000003")
    mock_cp.status = "active"
    stage = Stage(stage_id="st1", title="st", description="desc", status="upcoming")
    mock_cp.stages = [stage]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id, \
         patch("app.models.care_plan.CarePlanHistory.insert") as mock_hist_insert, \
         patch("app.models.patient.Patient.get") as mock_pat_get:
        
        mock_get_by_id.return_value = mock_cp
        mock_cp.save = AsyncMock()
        mock_pat_get.return_value = MagicMock()

        res = await CarePlanService.update_stage_status("cp123", "st1", "active", "111111111111111111111111")
        assert res is not None
        assert stage.status == "active"


@pytest.mark.asyncio
async def test_stage_active_to_completed(mock_notification_create_globally):
    from app.models.care_plan import Stage
    mock_cp = MagicMock()
    mock_cp.id = PydanticObjectId("000000000000000000000001")
    mock_cp.patient_id = PydanticObjectId("000000000000000000000002")
    mock_cp.therapist_id = PydanticObjectId("000000000000000000000003")
    mock_cp.status = "active"
    stage = Stage(stage_id="st1", title="st", description="desc", status="active")
    mock_cp.stages = [stage]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id, \
         patch("app.models.care_plan.CarePlanHistory.insert") as mock_hist_insert, \
         patch("app.models.patient.Patient.get") as mock_pat_get:
        
        mock_get_by_id.return_value = mock_cp
        mock_cp.save = AsyncMock()
        mock_pat_get.return_value = MagicMock()

        res = await CarePlanService.update_stage_status("cp123", "st1", "completed", "111111111111111111111111")
        assert res is not None
        assert stage.status == "completed"
        mock_notification_create_globally.assert_called_once()


@pytest.mark.asyncio
async def test_invalid_stage_skip():
    from app.models.care_plan import Stage
    mock_cp = MagicMock()
    mock_cp.status = "active"
    stage = Stage(stage_id="st1", title="st", description="desc", status="upcoming")
    mock_cp.stages = [stage]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        with pytest.raises(ValueError) as exc:
            await CarePlanService.update_stage_status("cp123", "st1", "completed", "111111111111111111111111")
        assert "Upcoming stages can only transition to active" in str(exc.value)


@pytest.mark.asyncio
async def test_invalid_stage_reverse_transition():
    from app.models.care_plan import Stage
    mock_cp = MagicMock()
    mock_cp.status = "active"
    stage = Stage(stage_id="st1", title="st", description="desc", status="completed")
    mock_cp.stages = [stage]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        with pytest.raises(ValueError) as exc:
            await CarePlanService.update_stage_status("cp123", "st1", "active", "111111111111111111111111")
        assert "Completed stages cannot be modified" in str(exc.value)


@pytest.mark.asyncio
async def test_multiple_active_stages_rejected():
    from app.models.care_plan import Stage
    mock_cp = MagicMock()
    mock_cp.status = "active"
    s1 = Stage(stage_id="st1", title="st1", description="desc", status="active")
    s2 = Stage(stage_id="st2", title="st2", description="desc", status="upcoming")
    mock_cp.stages = [s1, s2]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        with pytest.raises(ValueError) as exc:
            await CarePlanService.update_stage_status("cp123", "st2", "active", "111111111111111111111111")
        assert "A care plan can only have one active stage at a time" in str(exc.value)


@pytest.mark.asyncio
async def test_completed_plan_cannot_progress():
    from app.models.care_plan import Stage
    mock_cp = MagicMock()
    mock_cp.status = "completed"
    s1 = Stage(stage_id="st1", title="st1", description="desc", status="active")
    mock_cp.stages = [s1]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        with pytest.raises(ValueError) as exc:
            await CarePlanService.update_stage_status("cp123", "st1", "completed", "111111111111111111111111")
        assert "Cannot modify stages of a cancelled or completed care plan" in str(exc.value)


@pytest.mark.asyncio
async def test_complete_plan_with_unfinished_stages_rejected():
    from app.models.care_plan import Stage
    mock_cp = MagicMock()
    mock_cp.status = "active"
    s1 = Stage(stage_id="st1", title="st1", description="desc", status="active")
    mock_cp.stages = [s1]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_cp
        with pytest.raises(ValueError) as exc:
            await CarePlanService.update_care_plan("cp123", {"status": "completed"})
        assert "All stages must be completed before the care plan can transition to completed" in str(exc.value)


@pytest.mark.asyncio
async def test_complete_plan_success(mock_notification_create_globally):
    from app.models.care_plan import Stage
    mock_cp = MagicMock()
    mock_cp.status = "active"
    mock_cp.patient_id = PydanticObjectId("000000000000000000000002")
    mock_cp.therapist_id = PydanticObjectId("000000000000000000000003")
    s1 = Stage(stage_id="st1", title="st1", description="desc", status="completed")
    mock_cp.stages = [s1]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id, \
         patch("app.models.care_plan.CarePlanHistory.insert") as mock_hist_insert, \
         patch("app.models.patient.Patient.get") as mock_pat_get:
        
        mock_get_by_id.return_value = mock_cp
        mock_cp.save = AsyncMock()
        mock_pat_get.return_value = MagicMock()

        res = await CarePlanService.update_care_plan("cp123", {"status": "completed"})
        assert res is not None
        assert mock_cp.status == "completed"
        mock_notification_create_globally.assert_called_once()


@pytest.mark.asyncio
async def test_goal_progress_update():
    from app.models.care_plan import Goal
    mock_cp = MagicMock()
    mock_cp.id = PydanticObjectId("000000000000000000000001")
    mock_cp.patient_id = PydanticObjectId("000000000000000000000002")
    mock_cp.therapist_id = PydanticObjectId("000000000000000000000003")
    mock_cp.status = "active"
    goal = Goal(goal_id="g1", title="g", description="d", target_value=100.0, unit="u", status="active", progress_value=0.0)
    mock_cp.goals = [goal]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id, \
         patch("app.models.care_plan.CarePlanHistory.insert") as mock_hist_insert, \
         patch("app.models.patient.Patient.get") as mock_pat_get:
        
        mock_get_by_id.return_value = mock_cp
        mock_cp.save = AsyncMock()
        mock_pat_get.return_value = MagicMock()

        res = await CarePlanService.update_goal_progress("cp123", "g1", 50.0, "active", "111111111111111111111111")
        assert res is not None
        assert goal.progress_value == 50.0


@pytest.mark.asyncio
async def test_negative_goal_progress_rejected():
    with pytest.raises(ValueError) as exc:
        await CarePlanService.update_goal_progress("cp123", "g1", -10.0, "active", "111111111111111111111111")
    assert "Progress value cannot be negative" in str(exc.value)


@pytest.mark.asyncio
async def test_goal_achievement(mock_notification_create_globally):
    from app.models.care_plan import Goal
    mock_cp = MagicMock()
    mock_cp.id = PydanticObjectId("000000000000000000000001")
    mock_cp.patient_id = PydanticObjectId("000000000000000000000002")
    mock_cp.therapist_id = PydanticObjectId("000000000000000000000003")
    mock_cp.status = "active"
    goal = Goal(goal_id="g1", title="g", description="d", target_value=100.0, unit="u", status="active", progress_value=0.0)
    mock_cp.goals = [goal]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id") as mock_get_by_id, \
         patch("app.models.care_plan.CarePlanHistory.insert") as mock_hist_insert, \
         patch("app.models.patient.Patient.get") as mock_pat_get:
        
        mock_get_by_id.return_value = mock_cp
        mock_cp.save = AsyncMock()
        mock_pat_get.return_value = MagicMock()

        res = await CarePlanService.update_goal_progress("cp123", "g1", 100.0, "achieved", "111111111111111111111111")
        assert res is not None
        assert goal.status == "achieved"
        mock_notification_create_globally.assert_called_once()


@pytest.mark.asyncio
async def test_patient_can_read_own_care_plan_history():
    mock_cp = MagicMock()
    mock_cp.patient_id = "000000000000000000000002"
    
    mock_history_item = MagicMock()
    mock_history_item.action = "stage_completed"

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id", return_value=mock_cp), \
         patch("app.services.care_plan_service.CarePlanRepository.get_history_by_care_plan_id", new_callable=AsyncMock) as mock_get_hist:
        
        mock_get_hist.return_value = [mock_history_item]
        res = await CarePlanService.get_care_plan_history_for_patient("cp123", "000000000000000000000002")
        assert res is not None
        assert len(res) == 1
        assert res[0].action == "stage_completed"


@pytest.mark.asyncio
async def test_patient_cannot_read_other_patient_history():
    mock_cp = MagicMock()
    mock_cp.patient_id = "000000000000000000000002"

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id", return_value=mock_cp):
        res = await CarePlanService.get_care_plan_history_for_patient("cp123", "different_patient_id")
        assert res is None


@pytest.mark.asyncio
async def test_current_stage_synchronization():
    from app.models.care_plan import Stage
    mock_cp = MagicMock()
    mock_cp.id = PydanticObjectId("000000000000000000000001")
    mock_cp.patient_id = PydanticObjectId("000000000000000000000002")
    mock_cp.therapist_id = PydanticObjectId("000000000000000000000003")
    mock_cp.status = "active"
    mock_cp.current_stage = 1
    s1 = Stage(stage_id="st1", title="st1", description="desc", status="completed")
    s2 = Stage(stage_id="st2", title="st2", description="desc", status="upcoming")
    mock_cp.stages = [s1, s2]

    with patch("app.services.care_plan_service.CarePlanRepository.get_by_id", return_value=mock_cp), \
         patch("app.models.care_plan.CarePlanHistory.insert") as mock_hist_insert, \
         patch("app.models.patient.Patient.get") as mock_pat_get:
        
        mock_cp.save = AsyncMock()
        mock_pat_get.return_value = MagicMock()

        res = await CarePlanService.update_stage_status("cp123", "st2", "active", "111111111111111111111111")
        assert res is not None
        assert mock_cp.current_stage == 2


@pytest.mark.asyncio
async def test_get_care_plan_exercises_route():
    from app.api.care_plans import get_care_plan_exercises
    from fastapi import HTTPException
    
    mock_user = MagicMock()
    mock_user.id = PydanticObjectId("000000000000000000000001")
    mock_user.role = "patient"
    
    mock_cp = MagicMock()
    mock_cp.patient_id = PydanticObjectId("000000000000000000000002") # Mismatched owner

    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("000000000000000000000001")

    with patch("app.repositories.care_plan_repository.CarePlanRepository.get_by_id", return_value=mock_cp), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient):
        
        with pytest.raises(HTTPException) as exc:
            await get_care_plan_exercises("cp_id", mock_user)
        assert exc.value.status_code == 404



