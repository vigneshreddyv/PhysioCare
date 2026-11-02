from collections import Counter
from datetime import datetime, timedelta, timezone

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.core.config import settings
from zoneinfo import ZoneInfo
import re


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _shift_month(value: datetime, offset: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 + offset
    return value.replace(year=month_index // 12, month=month_index % 12 + 1, day=1)


class AnalyticsService:
    @staticmethod
    async def get_admin_daily_activity() -> dict:
        clinic_today = datetime.now(ZoneInfo(settings.CLINIC_TIMEZONE)).date()
        yesterday = clinic_today - timedelta(days=1)
        rows = await Appointment.get_pymongo_collection().aggregate([
            {"$match": {"appointment_date": {
                "$gte": datetime.combine(yesterday, datetime.min.time()),
                "$lt": datetime.combine(clinic_today + timedelta(days=1), datetime.min.time()),
            }}},
            {"$group": {
                "_id": {
                    "day": {"$dateToString": {
                        "format": "%Y-%m-%d", "date": "$appointment_date",
                        "timezone": settings.CLINIC_TIMEZONE,
                    }},
                    "slot": "$time_slot",
                },
                "count": {"$sum": 1},
            }},
        ]).to_list(length=None)
        today_count = yesterday_count = 0
        schedule = {"morning": 0, "afternoon": 0, "evening": 0}
        for row in rows:
            day = row["_id"]["day"]
            count = row["count"]
            if day == yesterday.isoformat():
                yesterday_count += count
            elif day == clinic_today.isoformat():
                today_count += count
                match = re.fullmatch(r"(\d{1,2}):\d{2}\s*(AM|PM)", row["_id"]["slot"] or "", re.I)
                if match:
                    hour = int(match.group(1)) % 12 + (12 if match.group(2).upper() == "PM" else 0)
                    schedule["morning" if hour < 12 else "afternoon" if hour < 17 else "evening"] += count
                else:
                    schedule["morning"] += count
        return {
            "today_appointments": today_count,
            "yesterday_appointments": yesterday_count,
            "schedule_counts": schedule,
        }

    @staticmethod
    async def get_clinic_stats(days: int = 30):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        period_start = now - timedelta(days=days)
        week_count = max(1, (days + 6) // 7)
        week_starts = [period_start + timedelta(days=index * 7) for index in range(week_count)]
        week_boundaries = [*week_starts, now + timedelta(microseconds=1)]
        current_month = _month_start(now)
        month_starts = [_shift_month(current_month, offset) for offset in range(-5, 1)]
        period_rows = await Appointment.get_pymongo_collection().aggregate([
            {"$match": {"appointment_date": {"$gte": period_start, "$lte": now}}},
            {"$facet": {
                "summary": [{"$group": {
                    "_id": None,
                    "count": {"$sum": 1},
                    "cancelled": {"$sum": {"$cond": [
                        {"$eq": ["$status", "cancelled"]}, 1, 0,
                    ]}},
                    "paid": {"$sum": {"$cond": [
                        {"$eq": ["$billing_status", "paid"]},
                        {"$ifNull": ["$billing_amount", 0]}, 0,
                    ]}},
                }}],
                "weeks": [{"$bucket": {
                    "groupBy": "$appointment_date",
                    "boundaries": week_boundaries,
                    "output": {"count": {"$sum": 1}},
                }}],
                "statuses": [{"$group": {"_id": "$status", "count": {"$sum": 1}}}],
            }},
        ]).to_list(length=1)
        period_data = period_rows[0] if period_rows else {}
        summary = (period_data.get("summary") or [{}])[0]
        period_count = summary.get("count", 0)
        period_cancelled = summary.get("cancelled", 0)
        recorded_paid_total = summary.get("paid", 0)
        week_totals = {item["_id"]: item["count"] for item in period_data.get("weeks", [])}
        appointments_per_week = [
            {
                "name": start.strftime("%b %d").replace(" 0", " "),
                "appointments": week_totals.get(start, 0),
            }
            for start in week_starts
        ]
        status_counts = {
            item["_id"]: item["count"] for item in period_data.get("statuses", [])
        }

        revenue_rows = await Appointment.get_pymongo_collection().aggregate([
            {"$match": {
                "billing_status": "paid",
                "appointment_date": {
                    "$gte": month_starts[0],
                    "$lt": _shift_month(current_month, 1),
                },
            }},
            {"$group": {
                "_id": {"$dateToString": {
                    "format": "%Y-%m", "date": "$appointment_date", "timezone": "UTC",
                }},
                "revenue": {"$sum": {"$ifNull": ["$billing_amount", 0]}},
            }},
        ]).to_list(length=6)
        revenue_by_month = {item["_id"]: item["revenue"] for item in revenue_rows}
        revenue_trend = [
            {"name": start.strftime("%b"),
             "revenue": revenue_by_month.get(start.strftime("%Y-%m"), 0)}
            for start in month_starts
        ]

        doctor_rows = await Doctor.get_pymongo_collection().aggregate([
            {"$group": {"_id": "$specialization", "count": {"$sum": 1}}},
        ]).to_list(length=None)
        specialization_counts = Counter()
        for item in doctor_rows:
            specialization_counts[item["_id"] or "Not specified"] += item["count"]
        doctor_specializations = [
            {"name": name, "value": count}
            for name, count in sorted(
                specialization_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

        new_patients = await User.find({
            "role": "patient",
            "created_at": {"$gte": period_start},
        }).count()
        total_patients = await Patient.count()
        active_subscriptions = await Patient.find({
            "subscription_status": "active",
        }).count()
        total_appointments = await Appointment.find_all().count()
        total_doctors = await Doctor.find_all().count()

        return {
            "period_days": days,
            "period_appointments": period_count,
            "total_appointments": total_appointments,
            "recorded_paid_total": recorded_paid_total,
            "cancellation_rate": (
                round(period_cancelled / period_count * 100, 1)
                if period_count
                else 0
            ),
            "total_doctors": total_doctors,
            "total_patients": total_patients,
            "new_patients": new_patients,
            "active_subscriptions": active_subscriptions,
            "appointments_per_week": appointments_per_week,
            "doctor_specializations": doctor_specializations,
            "revenue_trend": revenue_trend,
            "status_counts": status_counts,
            "availability": {
                "growth_comparisons": False,
                "payment_provider": False,
                "revenue_source": "Recorded appointment billing status only",
                "service_volume": False,
            },
        }
