from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScheduleBlockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day_of_week: int = Field(ge=0, le=6)
    service_mode: Literal["clinic", "home_visit"]
    start_time: str
    end_time: str


class ScheduleDateExceptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    blocks: list[ScheduleBlockIn] = Field(default_factory=list, max_length=12)


def _minutes(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("Schedule times must use 24-hour HH:MM format")
    hour, minute = map(int, parts)
    if hour not in range(24) or minute not in {0, 30}:
        raise ValueError("Schedule times must align to 30-minute boundaries")
    return hour * 60 + minute


def _validate_non_overlapping(blocks: list[ScheduleBlockIn], context: str) -> None:
    by_day: dict[int, list[tuple[int, int]]] = {}
    for block in blocks:
        start, end = _minutes(block.start_time), _minutes(block.end_time)
        if start >= end:
            raise ValueError(f"{context} block end must be after its start")
        by_day.setdefault(block.day_of_week, []).append((start, end))
    for ranges in by_day.values():
        ordered = sorted(ranges)
        if any(current[0] < previous[1] for previous, current in zip(ordered, ordered[1:])):
            raise ValueError(f"{context} clinic and home blocks cannot overlap")


class ScheduleDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weekly_blocks: list[ScheduleBlockIn] = Field(default_factory=list, max_length=56)
    date_exceptions: list[ScheduleDateExceptionIn] = Field(default_factory=list, max_length=31)

    @model_validator(mode="after")
    def validate_schedule(self):
        _validate_non_overlapping(self.weekly_blocks, "Weekly")
        dates = [item.date for item in self.date_exceptions]
        if len(dates) != len(set(dates)):
            raise ValueError("Only one exception is allowed per date")
        for exception in self.date_exceptions:
            expected_day = exception.date.weekday()
            normalized = [block.model_copy(update={"day_of_week": expected_day}) for block in exception.blocks]
            _validate_non_overlapping(normalized, "Date exception")
        return self


class SchedulePublish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class ScheduleAuditOut(BaseModel):
    action: str
    revision: int
    occurred_at: datetime


class ClinicianScheduleOut(BaseModel):
    doctor_id: str
    doctor_name: str
    timezone: str
    slot_minutes: int
    status: Literal["unconfigured", "draft", "published", "draft_changes"]
    draft_revision: int
    published_revision: int | None = None
    published_at: datetime | None = None
    weekly_blocks: list[ScheduleBlockIn]
    date_exceptions: list[ScheduleDateExceptionIn]
    published_weekly_blocks: list[ScheduleBlockIn]
    published_date_exceptions: list[ScheduleDateExceptionIn]
    audit_history: list[ScheduleAuditOut]
