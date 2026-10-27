from datetime import datetime

from beanie import PydanticObjectId
from pymongo import ReturnDocument

from app.models.clinician_schedule import ClinicianSchedule, ScheduleAuditEvent


class ClinicianScheduleRepository:
    @staticmethod
    async def get_by_doctor_id(doctor_id: str) -> ClinicianSchedule | None:
        try:
            return await ClinicianSchedule.find_one(ClinicianSchedule.doctor_id == PydanticObjectId(doctor_id))
        except (ValueError, TypeError):
            return None

    @staticmethod
    async def save_draft(schedule: ClinicianSchedule, actor_user_id: str) -> ClinicianSchedule:
        schedule.draft_revision += 1
        schedule.updated_at = datetime.utcnow()
        schedule.audit_history.append(ScheduleAuditEvent(
            action="draft_saved",
            actor_user_id=PydanticObjectId(actor_user_id),
            revision=schedule.draft_revision,
            occurred_at=schedule.updated_at,
        ))
        if schedule.id is None:
            return await schedule.insert()
        return await schedule.save()

    @staticmethod
    async def publish(schedule: ClinicianSchedule, actor_user_id: str, expected_revision: int) -> ClinicianSchedule | None:
        now = datetime.utcnow()
        updated = await ClinicianSchedule.get_pymongo_collection().find_one_and_update(
            {"_id": schedule.id, "draft_revision": expected_revision},
            {
                "$set": {
                    "published_weekly_blocks": [block.model_dump(mode="python") for block in schedule.draft_weekly_blocks],
                    "published_date_exceptions": [item.model_dump(mode="python") for item in schedule.draft_date_exceptions],
                    "published_revision": expected_revision,
                    "published_at": now,
                    "updated_at": now,
                },
                "$push": {
                    "audit_history": ScheduleAuditEvent(
                        action="published",
                        actor_user_id=PydanticObjectId(actor_user_id),
                        revision=expected_revision,
                        occurred_at=now,
                    ).model_dump(mode="python")
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        return ClinicianSchedule.model_validate(updated) if updated else None
