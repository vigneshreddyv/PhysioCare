"""Read-only, streaming query for no-preference home-visit allocation."""

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.clinician_schedule import ScheduleBlock, ScheduleDateException
from app.models.user import User


class HomeVisitQueryRepository:
    @staticmethod
    async def iter_clinician_contexts(appointment_date: date):
        """Stream eligible clinician IDs with projected schedule/conflict data.

        Eligibility, account activity, ordering, schedule join, and the one-day
        appointment window are evaluated by one MongoDB aggregation.
        Iteration avoids materializing an unbounded clinician collection.
        """
        clinic_zone = ZoneInfo(settings.CLINIC_TIMEZONE)
        clinic_start = datetime.combine(appointment_date, time.min, tzinfo=clinic_zone)
        clinic_end = datetime.combine(
            appointment_date + timedelta(days=1), time.min, tzinfo=clinic_zone,
        )
        utc_start = clinic_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = clinic_end.astimezone(timezone.utc).replace(tzinfo=None)
        legacy_start = datetime.combine(appointment_date - timedelta(days=1), time.min)
        legacy_end = datetime.combine(appointment_date + timedelta(days=1), time.min)

        pipeline: list[dict] = [
            {"$match": {"role": "doctor", "is_active": True}},
            {"$lookup": {
                "from": "doctors",
                "let": {"user_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$and": [
                        {"$eq": ["$user_id", "$$user_id"]},
                        {"$ne": [
                            {"$ifNull": ["$accepts_home_visits", True]}, False,
                        ]},
                    ]}}},
                    {"$project": {"_id": 1}},
                ],
                "as": "doctor",
            }},
            {"$unwind": "$doctor"},
            {"$lookup": {
                "from": "clinician_schedules",
                "let": {"doctor_id": "$doctor._id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$doctor_id", "$$doctor_id"]}}},
                    {"$project": {
                        "doctor_id": 1,
                        "slot_minutes": 1,
                        "published_revision": 1,
                        "published_weekly_blocks": 1,
                        "published_date_exceptions": 1,
                    }},
                    {"$limit": 1},
                ],
                "as": "schedule",
            }},
        ]
        pipeline.append({"$lookup": {
            "from": "appointments",
            "let": {"doctor_id": "$doctor._id"},
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$doctor_id", "$$doctor_id"]},
                    {"$in": ["$status", ["scheduled", "in_progress"]]},
                    {"$or": [
                        {"$and": [
                            {"$gte": ["$starts_at", utc_start]},
                            {"$lt": ["$starts_at", utc_end]},
                        ]},
                        {"$and": [
                            {"$gte": ["$appointment_date", legacy_start]},
                            {"$lt": ["$appointment_date", legacy_end]},
                        ]},
                    ]},
                ]}}},
                {"$project": {
                    "starts_at": 1,
                    "appointment_date": 1,
                    "time_slot": 1,
                    "service_mode": 1,
                }},
            ],
            "as": "appointments",
        }})
        pipeline.extend([
            {"$sort": {"doctor._id": 1}},
            {"$project": {
                "_id": 0,
                "doctor_id": "$doctor._id",
                "schedule": {"$arrayElemAt": ["$schedule", 0]},
                "appointments": 1,
            }},
        ])

        cursor = User.get_pymongo_collection().aggregate(pipeline)
        async for row in cursor:
            schedule_row = row.get("schedule")
            schedule = SimpleNamespace(
                doctor_id=schedule_row["doctor_id"],
                slot_minutes=schedule_row.get("slot_minutes", settings.DEMO_SLOT_MINUTES),
                published_revision=schedule_row.get("published_revision"),
                published_weekly_blocks=[
                    ScheduleBlock.model_validate(item)
                    for item in schedule_row.get("published_weekly_blocks", [])
                ],
                published_date_exceptions=[
                    ScheduleDateException.model_validate(item)
                    for item in schedule_row.get("published_date_exceptions", [])
                ],
            ) if schedule_row else None
            appointments = [SimpleNamespace(
                id=item["_id"],
                starts_at=item.get("starts_at"),
                appointment_date=item.get("appointment_date"),
                time_slot=item.get("time_slot"),
                service_mode=item.get("service_mode", "clinic"),
            ) for item in row.get("appointments", [])]
            yield SimpleNamespace(
                id=row["doctor_id"],
                schedule=schedule,
                appointments=appointments,
            )
