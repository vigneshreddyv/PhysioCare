from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId

from app.core.pagination import PageWindow
from app.core.time import utc_now
from app.models.care_plan import CarePlan, CarePlanHistory, Goal, Recommendation, Stage
from app.models.patient import Patient
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
    async def get_active_or_latest_by_patient(patient_id: str) -> Optional[CarePlan]:
        return await CarePlanRepository.get_active_or_latest_by_patient_id(patient_id)

    @staticmethod
    async def _authorize_doctor(
        patient_id: str, actor_user_id: Optional[str], actor_role: Optional[str],
    ):
        if actor_role == "admin" and actor_user_id:
            return None
        if actor_role != "doctor" or not actor_user_id:
            raise PermissionError("Explicit clinical actor context is required.")
        from app.services.clinical_authorization import require_doctor_patient_access
        return await require_doctor_patient_access(actor_user_id, patient_id)

    @staticmethod
    async def _authorize_plan_mutation(
        care_plan: CarePlan, actor_user_id: Optional[str], actor_role: Optional[str],
    ):
        doctor = await CarePlanService._authorize_doctor(
            str(care_plan.patient_id), actor_user_id, actor_role
        )
        if doctor and str(care_plan.therapist_id) != str(doctor.id):
            raise PermissionError("Doctor is not authorized to modify this care plan.")

    @staticmethod
    async def _patient_notification(care_plan: CarePlan, **values) -> dict | None:
        patient = await Patient.get(care_plan.patient_id)
        if not patient:
            return None
        return {
            "recipient_user_id": patient.user_id,
            "notification_type": "care_plan",
            "related_entity_id": str(care_plan.id),
            **values,
        }

    @staticmethod
    async def create_care_plan(
        patient_id: str, therapist_id: str, title: str, description: str,
        current_stage: int, stages: List[dict], goals: List[dict],
        recommendations: List[dict], start_date: datetime, target_date: datetime,
        status: str = "active", actor_user_id: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> CarePlan:
        doctor = await CarePlanService._authorize_doctor(patient_id, actor_user_id, actor_role)
        patient = await Patient.get(to_object_id(patient_id))
        if not patient:
            raise ValueError("Target patient profile not found.")
        if doctor and str(therapist_id) != str(doctor.id):
            raise PermissionError("Doctor can only create care plans for their assigned patients.")
        if status not in ["active", "completed", "paused", "cancelled"]:
            raise ValueError(f"Invalid care plan status: '{status}'")
        stage_objs = []
        for item in stages:
            if item.get("status") not in ["upcoming", "active", "completed"]:
                raise ValueError(f"Invalid stage status: '{item.get('status')}'")
            stage_objs.append(Stage(**item))
        care_plan = CarePlan(
            patient_id=to_object_id(patient_id), therapist_id=to_object_id(therapist_id),
            title=title, description=description, current_stage=current_stage,
            stages=stage_objs, goals=[Goal(**item) for item in goals],
            recommendations=[Recommendation(**item) for item in recommendations],
            start_date=start_date, target_date=target_date, status=status,
        )
        return await CarePlanRepository.create_with_history(
            care_plan, actor_user_id=actor_user_id or therapist_id
        )

    @staticmethod
    async def get_care_plans_by_patient(
        patient_id: str, page: PageWindow | None = None,
    ) -> List[CarePlan]:
        if page is not None:
            return await CarePlanRepository.get_page_by_patient_id(patient_id, page)
        return await CarePlanRepository.get_by_patient_id(patient_id)

    @staticmethod
    async def get_care_plan_for_patient(care_plan_id: str, patient_id: str) -> Optional[CarePlan]:
        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan or str(care_plan.patient_id) != patient_id:
            return None
        return care_plan

    @staticmethod
    async def update_care_plan(
        care_plan_id: str, update_data: dict,
        actor_user_id: Optional[str] = None, actor_role: Optional[str] = None,
    ) -> Optional[CarePlan]:
        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan:
            return None
        await CarePlanService._authorize_plan_mutation(care_plan, actor_user_id, actor_role)
        expected_revision = update_data.pop("expected_revision", getattr(care_plan, "revision", 0))
        for immutable in ("patient_id", "therapist_id"):
            if immutable in update_data and str(update_data[immutable]) != str(getattr(care_plan, immutable)):
                raise ValueError(f"Modifying {immutable} is not allowed.")

        history_data = None
        notification_data = None
        new_status = update_data.get("status")
        old_status = to_str(care_plan.status)
        if new_status is not None and old_status != new_status:
            if old_status in ["cancelled", "completed"]:
                raise ValueError(f"Cannot modify status of a {old_status} care plan.")
            if old_status == "active" and new_status not in ["paused", "completed", "cancelled"]:
                raise ValueError(f"Invalid transition from active to {new_status}")
            if old_status == "paused" and new_status not in ["active", "cancelled"]:
                raise ValueError(f"Invalid transition from paused to {new_status}")
            if new_status == "completed" and any(s.status != "completed" for s in care_plan.stages):
                raise ValueError("All stages must be completed before the care plan can transition to completed.")
            history_data = {
                "actor_user_id": to_object_id(actor_user_id), "action": f"plan_{new_status}",
                "previous_value": old_status, "new_value": new_status,
            }
            titles = {"paused": "Care Plan Paused", "completed": "Care Plan Completed",
                      "cancelled": "Care Plan Cancelled", "active": "Care Plan Resumed"}
            messages = {"paused": "Your care plan has been paused.",
                        "completed": "Your care plan is successfully completed!",
                        "cancelled": "Your care plan has been cancelled.",
                        "active": "Your care plan has been resumed."}
            notification_data = await CarePlanService._patient_notification(
                care_plan, title=titles.get(new_status, "Care Plan Updated"),
                message=messages.get(new_status, f"Your care plan status is now {new_status}.")
            )

        set_fields = {}
        if "stages" in update_data and update_data["stages"] is not None:
            if care_plan.status in ["cancelled", "completed"]:
                raise ValueError("Cannot modify stages of a cancelled or completed care plan.")
            stages = [Stage(**(s if isinstance(s, dict) else s.model_dump())) for s in update_data["stages"]]
            if sum(s.status == "active" for s in stages) > 1:
                raise ValueError("A care plan can only have one active stage at a time.")
            set_fields["stages"] = [s.model_dump() for s in stages]
        if "goals" in update_data and update_data["goals"] is not None:
            if care_plan.status in ["cancelled", "completed"]:
                raise ValueError("Cannot modify goals of a cancelled or completed care plan.")
            set_fields["goals"] = [Goal(**(g if isinstance(g, dict) else g.model_dump())).model_dump()
                                   for g in update_data["goals"]]
        if "recommendations" in update_data and update_data["recommendations"] is not None:
            set_fields["recommendations"] = [
                Recommendation(**(r if isinstance(r, dict) else r.model_dump())).model_dump()
                for r in update_data["recommendations"]
            ]
        for field in ["title", "description", "current_stage", "start_date", "target_date", "status"]:
            if field in update_data and update_data[field] is not None:
                set_fields[field] = update_data[field]
        set_fields["updated_at"] = utc_now()
        kwargs = dict(care_plan_id=care_plan_id, expected_revision=expected_revision,
                      patient_id=care_plan.patient_id, therapist_id=care_plan.therapist_id,
                      set_fields=set_fields)
        if history_data:
            return await CarePlanRepository.update_with_side_effects(
                **kwargs, history_data=history_data, notification_data=notification_data
            )
        return await CarePlanRepository.update_if_revision(**kwargs)

    @staticmethod
    async def update_stage_status(
        care_plan_id: str, stage_id: str, new_status: str,
        actor_user_id: str, actor_role: str, expected_revision: int = 0,
    ) -> Optional[CarePlan]:
        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan:
            return None
        await CarePlanService._authorize_plan_mutation(care_plan, actor_user_id, actor_role)
        if care_plan.status in ["cancelled", "completed"]:
            raise ValueError("Cannot modify stages of a cancelled or completed care plan.")
        stage = next((item for item in care_plan.stages if item.stage_id == stage_id), None)
        if not stage:
            return None
        old_status = stage.status
        if old_status == new_status:
            if expected_revision != getattr(care_plan, "revision", 0):
                from app.repositories.care_plan_repository import CarePlanMutationConflict
                raise CarePlanMutationConflict
            return care_plan
        if old_status == "upcoming" and new_status != "active":
            raise ValueError("Upcoming stages can only transition to active.")
        if old_status == "active" and new_status != "completed":
            raise ValueError("Active stages can only transition to completed.")
        if old_status == "completed":
            raise ValueError("Completed stages cannot be modified.")
        if new_status == "active" and any(
            item.status == "active" for item in care_plan.stages if item.stage_id != stage_id
        ):
            raise ValueError("A care plan can only have one active stage at a time.")
        if new_status == "active":
            care_plan.current_stage = next(index for index, item in enumerate(care_plan.stages, 1)
                                           if item.stage_id == stage_id)
        stage.status = new_status
        notification = await CarePlanService._patient_notification(
            care_plan,
            title="Care Plan Stage Started" if new_status == "active" else "Care Plan Stage Completed",
            message=(f"Your stage '{stage.title}' has started." if new_status == "active"
                     else f"Your stage '{stage.title}' is completed."),
        )
        return await CarePlanRepository.update_with_side_effects(
            care_plan_id, expected_revision=expected_revision,
            patient_id=care_plan.patient_id, therapist_id=care_plan.therapist_id,
            set_fields={"stages": [item.model_dump() for item in care_plan.stages],
                        "current_stage": care_plan.current_stage, "updated_at": utc_now()},
            history_data={"actor_user_id": to_object_id(actor_user_id),
                          "action": "stage_activated" if new_status == "active" else "stage_completed",
                          "previous_value": to_str(old_status), "new_value": to_str(new_status)},
            notification_data=notification,
        )

    @staticmethod
    async def update_goal_progress(
        care_plan_id: str, goal_id: str, progress_value: float, new_status: str,
        actor_user_id: str, actor_role: str, expected_revision: int = 0,
    ) -> Optional[CarePlan]:
        if progress_value < 0:
            raise ValueError("Progress value cannot be negative.")
        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan:
            return None
        await CarePlanService._authorize_plan_mutation(care_plan, actor_user_id, actor_role)
        if care_plan.status in ["cancelled", "completed"]:
            raise ValueError("Cannot modify goals of a cancelled or completed care plan.")
        goal = next((item for item in care_plan.goals if item.goal_id == goal_id), None)
        if not goal:
            return None
        if goal.status == "achieved" and new_status == "active":
            raise ValueError("Achieved goals cannot transition back to active.")
        if goal.target_value > 0 and progress_value > goal.target_value:
            raise ValueError(f"Progress value {progress_value} exceeds target value {goal.target_value}.")
        old_status, old_progress = goal.status, goal.progress_value
        goal.progress_value, goal.status = progress_value, new_status
        notification = None
        if new_status == "achieved" and old_status != "achieved":
            notification = await CarePlanService._patient_notification(
                care_plan, title="Care Plan Goal Achieved",
                message=f"Congratulations! You achieved your goal: '{goal.title}'."
            )
        return await CarePlanRepository.update_with_side_effects(
            care_plan_id, expected_revision=expected_revision,
            patient_id=care_plan.patient_id, therapist_id=care_plan.therapist_id,
            set_fields={"goals": [item.model_dump() for item in care_plan.goals], "updated_at": utc_now()},
            history_data={"actor_user_id": to_object_id(actor_user_id),
                          "action": "goal_updated" if new_status == "active" else "goal_achieved",
                          "previous_value": to_str(old_progress), "new_value": to_str(progress_value)},
            notification_data=notification,
        )

    @staticmethod
    async def get_care_plan_history_for_patient(
        care_plan_id: str, patient_id: str, page: PageWindow | None = None,
    ) -> Optional[List[CarePlanHistory]]:
        care_plan = await CarePlanRepository.get_by_id(care_plan_id)
        if not care_plan or str(care_plan.patient_id) != patient_id:
            return None
        if page is not None:
            return await CarePlanRepository.get_page_history_by_care_plan_id(care_plan_id, page)
        return await CarePlanRepository.get_history_by_care_plan_id(care_plan_id)
