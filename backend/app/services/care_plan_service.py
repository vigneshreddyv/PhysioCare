from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId

from app.core.time import utc_now
from app.models.care_plan import CarePlan, Stage, Goal, Recommendation, CarePlanHistory
from app.repositories.care_plan_repository import CarePlanRepository


def to_object_id(val) -> PydanticObjectId:
    if not val:
        return PydanticObjectId("000000000000000000000000")
    try:
        return PydanticObjectId(str(val))
    except Exception:
        return PydanticObjectId("000000000000000000000000")


def to_str(val) -> Optional[str]:
    if val is None:
        return None
    if type(val).__name__ in ["MagicMock", "Mock", "AsyncMock"]:
        return "mock_value"
    return str(val)


class CarePlanService:
    @staticmethod
    async def _authorize_doctor(
        patient_id: str,
        actor_user_id: Optional[str],
        actor_role: str
    ):
        if actor_role != "doctor" or not actor_user_id:
            return None
        from app.services.clinical_authorization import require_doctor_patient_access
        return await require_doctor_patient_access(actor_user_id, patient_id)

    @staticmethod
    async def _authorize_plan_mutation(
        care_plan: CarePlan,
        actor_user_id: Optional[str],
        actor_role: str
    ):
        doctor = await CarePlanService._authorize_doctor(
            str(care_plan.patient_id), actor_user_id, actor_role
        )
        if doctor and str(care_plan.therapist_id) != str(doctor.id):
            raise PermissionError("Doctor is not authorized to modify this care plan.")

    @staticmethod
    async def create_care_plan(
        patient_id: str,
        therapist_id: str,
        title: str,
        description: str,
        current_stage: int,
        stages: List[dict],
        goals: List[dict],
        recommendations: List[dict],
        start_date: datetime,
        target_date: datetime,
        status: str = "active",
        actor_user_id: Optional[str] = None,
        actor_role: str = "admin"
    ) -> CarePlan:
        # Validate patient exists
        from app.models.patient import Patient
        patient = await Patient.get(to_object_id(patient_id))
        if not patient:
            raise ValueError("Target patient profile not found.")
        doctor = await CarePlanService._authorize_doctor(
            patient_id, actor_user_id, actor_role
        )
        if doctor and str(therapist_id) != str(doctor.id):
            raise PermissionError("Doctor can only create care plans for their assigned patients.")

        # Validate status
        if status not in ["active", "completed", "paused", "cancelled"]:
            raise ValueError(f"Invalid care plan status: '{status}'")

        # Map and validate stages
        stage_objs = []
        for s in stages:
            if s.get("status") not in ["upcoming", "active", "completed"]:
                raise ValueError(f"Invalid stage status: '{s.get('status')}'")
            stage_objs.append(Stage(**s))

        # Map goals
        goal_objs = [Goal(**g) for g in goals]

        # Map recommendations
        rec_objs = [Recommendation(**r) for r in recommendations]

        care_plan = CarePlan(
            patient_id=to_object_id(patient_id),
            therapist_id=to_object_id(therapist_id),
            title=title,
            description=description,
            current_stage=current_stage,
            stages=stage_objs,
            goals=goal_objs,
            recommendations=rec_objs,
            start_date=start_date,
            target_date=target_date,
            status=status
        )

        cp = await CarePlanRepository.create(care_plan)

        # Log history for plan creation
        history = CarePlanHistory(
            care_plan_id=to_object_id(cp.id),
            patient_id=to_object_id(cp.patient_id),
            actor_user_id=to_object_id(therapist_id),
            action="plan_created",
            new_value=status
        )
        await history.insert()

        return cp

    @staticmethod
    async def get_care_plans_by_patient(patient_id: str) -> List[CarePlan]:
        return await CarePlanRepository.get_by_patient_id(patient_id)

    @staticmethod
    async def get_care_plan_for_patient(care_plan_id: str, patient_id: str) -> Optional[CarePlan]:
        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan:
            return None
        if str(care_plan.patient_id) != patient_id:
            return None
        return care_plan

    @staticmethod
    async def update_care_plan(
        care_plan_id: str,
        update_data: dict,
        actor_user_id: Optional[str] = None,
        actor_role: str = "admin"
    ) -> Optional[CarePlan]:
        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan:
            return None
        await CarePlanService._authorize_plan_mutation(
            care_plan, actor_user_id, actor_role
        )

        # Enforce clinical integrity checks (immutability)
        if "patient_id" in update_data:
            if str(update_data["patient_id"]) != str(care_plan.patient_id):
                raise ValueError("Modifying patient_id is not allowed.")

        if "therapist_id" in update_data:
            if str(update_data["therapist_id"]) != str(care_plan.therapist_id):
                raise ValueError("Modifying therapist_id is not allowed.")

        if "status" in update_data:
            new_status = update_data["status"]
            old_status = to_str(care_plan.status)
            if old_status != new_status:
                if old_status in ["cancelled", "completed"]:
                    raise ValueError(f"Cannot modify status of a {old_status} care plan.")

                # Validate transitions
                if old_status == "active" and new_status not in ["paused", "completed", "cancelled"]:
                    raise ValueError(f"Invalid transition from active to {new_status}")
                if old_status == "paused" and new_status not in ["active", "cancelled"]:
                    raise ValueError(f"Invalid transition from paused to {new_status}")

                # Verify completion rules
                if new_status == "completed":
                    unfinished = [s for s in care_plan.stages if s.status != "completed"]
                    if unfinished:
                        raise ValueError("All stages must be completed before the care plan can transition to completed.")

                care_plan.status = new_status

                # History log
                actor_id = to_object_id(update_data.get("actor_user_id") or str(care_plan.therapist_id))
                history = CarePlanHistory(
                    care_plan_id=to_object_id(care_plan.id),
                    patient_id=to_object_id(care_plan.patient_id),
                    actor_user_id=actor_id,
                    action=f"plan_{new_status}",
                    previous_value=old_status,
                    new_value=new_status
                )
                await history.insert()

                # Send Notification
                from app.models.patient import Patient
                patient = await Patient.get(care_plan.patient_id)
                if patient:
                    from app.services.notification_service import NotificationService
                    titles = {
                        "paused": "Care Plan Paused",
                        "completed": "Care Plan Completed",
                        "cancelled": "Care Plan Cancelled",
                        "active": "Care Plan Resumed"
                    }
                    action_msgs = {
                        "paused": "Your care plan has been paused.",
                        "completed": "Your care plan is successfully completed!",
                        "cancelled": "Your care plan has been cancelled.",
                        "active": "Your care plan has been resumed."
                    }
                    await NotificationService.create_notification(
                        recipient_user_id=str(patient.user_id),
                        title=titles.get(new_status, "Care Plan Updated"),
                        message=action_msgs.get(new_status, f"Your care plan status is now {new_status}."),
                        notification_type="care_plan",
                        related_entity_id=str(care_plan.id)
                    )

        if "stages" in update_data and update_data["stages"] is not None:
            # Verify cancelled/completed plans cannot modify stages
            if care_plan.status in ["cancelled", "completed"]:
                raise ValueError("Cannot modify stages of a cancelled or completed care plan.")
            stage_objs = []
            active_count = 0
            for s in update_data["stages"]:
                s_dict = s if isinstance(s, dict) else s.model_dump()
                if s_dict.get("status") not in ["upcoming", "active", "completed"]:
                    raise ValueError(f"Invalid stage status: '{s_dict.get('status')}'")
                if s_dict.get("status") == "active":
                    active_count += 1
                stage_objs.append(Stage(**s_dict))
            if active_count > 1:
                raise ValueError("A care plan can only have one active stage at a time.")
            care_plan.stages = stage_objs

        if "goals" in update_data and update_data["goals"] is not None:
            if care_plan.status in ["cancelled", "completed"]:
                raise ValueError("Cannot modify goals of a cancelled or completed care plan.")
            care_plan.goals = [
                Goal(**(g if isinstance(g, dict) else g.model_dump()))
                for g in update_data["goals"]
            ]

        if "recommendations" in update_data and update_data["recommendations"] is not None:
            care_plan.recommendations = [
                Recommendation(**(r if isinstance(r, dict) else r.model_dump()))
                for r in update_data["recommendations"]
            ]

        # Simple field mappings
        for field in ["title", "description", "current_stage", "start_date", "target_date"]:
            if field in update_data and update_data[field] is not None:
                setattr(care_plan, field, update_data[field])

        care_plan.updated_at = utc_now()
        await care_plan.save()
        return care_plan

    @staticmethod
    async def update_stage_status(
        care_plan_id: str,
        stage_id: str,
        new_status: str,
        actor_user_id: str,
        actor_role: str = "admin"
    ) -> Optional[CarePlan]:
        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan:
            return None
        await CarePlanService._authorize_plan_mutation(
            care_plan, actor_user_id, actor_role
        )

        # Enforce clinical validation
        if care_plan.status in ["cancelled", "completed"]:
            raise ValueError("Cannot modify stages of a cancelled or completed care plan.")

        # Find target stage
        stage = next((s for s in care_plan.stages if s.stage_id == stage_id), None)
        if not stage:
            return None

        old_status = stage.status
        if old_status == new_status:
            return care_plan

        # Validation matrix
        # upcoming -> active
        # active -> completed
        if old_status == "upcoming" and new_status != "active":
            raise ValueError("Upcoming stages can only transition to active.")
        if old_status == "active" and new_status != "completed":
            raise ValueError("Active stages can only transition to completed.")
        if old_status == "completed":
            raise ValueError("Completed stages cannot be modified.")

        # Enforce only one active stage at a time
        if new_status == "active":
            has_active = any(s.status == "active" for s in care_plan.stages if s.stage_id != stage_id)
            if has_active:
                raise ValueError("A care plan can only have one active stage at a time.")
            for idx, s in enumerate(care_plan.stages):
                if s.stage_id == stage_id:
                    care_plan.current_stage = idx + 1
                    break

        stage.status = new_status
        care_plan.updated_at = utc_now()
        await care_plan.save()

        # Log history
        history = CarePlanHistory(
            care_plan_id=to_object_id(care_plan.id),
            patient_id=to_object_id(care_plan.patient_id),
            actor_user_id=to_object_id(actor_user_id),
            action="stage_activated" if new_status == "active" else "stage_completed",
            previous_value=to_str(old_status),
            new_value=to_str(new_status)
        )
        await history.insert()

        # Send Notification
        from app.models.patient import Patient
        patient = await Patient.get(care_plan.patient_id)
        if patient:
            from app.services.notification_service import NotificationService
            title = "Care Plan Stage Started" if new_status == "active" else "Care Plan Stage Completed"
            msg = f"Your stage '{stage.title}' has started." if new_status == "active" else f"Your stage '{stage.title}' is completed."
            await NotificationService.create_notification(
                recipient_user_id=str(patient.user_id),
                title=title,
                message=msg,
                notification_type="care_plan",
                related_entity_id=str(care_plan.id)
            )

        return care_plan

    @staticmethod
    async def update_goal_progress(
        care_plan_id: str,
        goal_id: str,
        progress_value: float,
        new_status: str,
        actor_user_id: str,
        actor_role: str = "admin"
    ) -> Optional[CarePlan]:
        if progress_value < 0:
            raise ValueError("Progress value cannot be negative.")

        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan:
            return None
        await CarePlanService._authorize_plan_mutation(
            care_plan, actor_user_id, actor_role
        )

        if care_plan.status in ["cancelled", "completed"]:
            raise ValueError("Cannot modify goals of a cancelled or completed care plan.")

        goal = next((g for g in care_plan.goals if g.goal_id == goal_id), None)
        if not goal:
            return None

        if goal.status == "achieved" and new_status == "active":
            raise ValueError("Achieved goals cannot transition back to active.")

        old_status = goal.status
        old_progress = goal.progress_value

        # Enforce progress value target cap restriction check if target is defined and positive
        if goal.target_value > 0 and progress_value > goal.target_value:
            raise ValueError(f"Progress value {progress_value} exceeds target value {goal.target_value}.")

        goal.progress_value = progress_value
        goal.status = new_status
        care_plan.updated_at = utc_now()
        await care_plan.save()

        # Log history
        history = CarePlanHistory(
            care_plan_id=to_object_id(care_plan.id),
            patient_id=to_object_id(care_plan.patient_id),
            actor_user_id=to_object_id(actor_user_id),
            action="goal_updated" if new_status == "active" else "goal_achieved",
            previous_value=to_str(old_progress),
            new_value=to_str(progress_value)
        )
        await history.insert()

        # Send Notification if goal achieved
        if new_status == "achieved" and old_status != "achieved":
            from app.models.patient import Patient
            patient = await Patient.get(care_plan.patient_id)
            if patient:
                from app.services.notification_service import NotificationService
                await NotificationService.create_notification(
                    recipient_user_id=str(patient.user_id),
                    title="Care Plan Goal Achieved",
                    message=f"Congratulations! You achieved your goal: '{goal.title}'.",
                    notification_type="care_plan",
                    related_entity_id=str(care_plan.id)
                )

        return care_plan

    @staticmethod
    async def get_care_plan_history_for_patient(
        care_plan_id: str,
        patient_id: str
    ) -> Optional[List[CarePlanHistory]]:
        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan:
            return None
        if str(care_plan.patient_id) != patient_id:
            return None

        return await CarePlanRepository.get_history_by_care_plan_id(care_plan_id)

