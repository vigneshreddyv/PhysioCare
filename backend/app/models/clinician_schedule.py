from datetime import date, datetime
from typing import Literal

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel

from app.core.time import utc_now


class ScheduleBlock(BaseModel):
    day_of_week: int
    service_mode: Literal["clinic", "home_visit"]
    start_time: str
    end_time: str


class ScheduleDateException(BaseModel):
    date: date
    blocks: list[ScheduleBlock] = Field(default_factory=list)


class ScheduleAuditEvent(BaseModel):
    action: Literal["draft_saved", "published"]
    actor_user_id: PydanticObjectId
    revision: int
    occurred_at: datetime


class ClinicianSchedule(Document):
    doctor_id: PydanticObjectId
    timezone: str = "Asia/Kolkata"
    slot_minutes: int = 30
    draft_weekly_blocks: list[ScheduleBlock] = Field(default_factory=list)
    draft_date_exceptions: list[ScheduleDateException] = Field(default_factory=list)
    published_weekly_blocks: list[ScheduleBlock] = Field(default_factory=list)
    published_date_exceptions: list[ScheduleDateException] = Field(default_factory=list)
    draft_revision: int = 0
    published_revision: int | None = None
    published_at: datetime | None = None
    audit_history: list[ScheduleAuditEvent] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "clinician_schedules"
        indexes = [
            IndexModel([("doctor_id", ASCENDING)], unique=True, name="unique_clinician_schedule"),
        ]
