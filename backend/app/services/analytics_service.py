from collections import Counter
from datetime import datetime, timedelta, timezone

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _shift_month(value: datetime, offset: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 + offset
    return value.replace(year=month_index // 12, month=month_index % 12 + 1, day=1)


class AnalyticsService:
    @staticmethod
    async def get_clinic_stats(days: int = 30):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        period_start = now - timedelta(days=days)
        appointments = await Appointment.find_all().to_list()
        doctors = await Doctor.find_all().to_list()

        period_appointments = [
            appointment
            for appointment in appointments
            if period_start <= appointment.appointment_date <= now
        ]
        period_cancelled = sum(
            appointment.status == "cancelled"
            for appointment in period_appointments
        )
        recorded_paid_total = sum(
            appointment.billing_amount
            for appointment in period_appointments
            if appointment.billing_status == "paid"
        )

        week_count = max(1, (days + 6) // 7)
        appointments_per_week = []
        for index in range(week_count):
            bucket_start = period_start + timedelta(days=index * 7)
            bucket_end = min(bucket_start + timedelta(days=7), now + timedelta(microseconds=1))
            appointments_per_week.append({
                "name": bucket_start.strftime("%b %d").replace(" 0", " "),
                "appointments": sum(
                    bucket_start <= appointment.appointment_date < bucket_end
                    for appointment in period_appointments
                ),
            })

        current_month = _month_start(now)
        month_starts = [_shift_month(current_month, offset) for offset in range(-5, 1)]
        revenue_trend = []
        for month_start in month_starts:
            month_end = _shift_month(month_start, 1)
            revenue_trend.append({
                "name": month_start.strftime("%b"),
                "revenue": sum(
                    appointment.billing_amount
                    for appointment in appointments
                    if appointment.billing_status == "paid"
                    and month_start <= appointment.appointment_date < month_end
                ),
            })

        specialization_counts = Counter(
            doctor.specialization or "Not specified"
            for doctor in doctors
        )
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

        return {
            "period_days": days,
            "period_appointments": len(period_appointments),
            "total_appointments": len(appointments),
            "recorded_paid_total": recorded_paid_total,
            "cancellation_rate": (
                round(period_cancelled / len(period_appointments) * 100, 1)
                if period_appointments
                else 0
            ),
            "total_doctors": len(doctors),
            "total_patients": total_patients,
            "new_patients": new_patients,
            "active_subscriptions": active_subscriptions,
            "appointments_per_week": appointments_per_week,
            "doctor_specializations": doctor_specializations,
            "revenue_trend": revenue_trend,
            "status_counts": dict(Counter(
                appointment.status for appointment in period_appointments
            )),
            "availability": {
                "growth_comparisons": False,
                "payment_provider": False,
                "revenue_source": "Recorded appointment billing status only",
                "service_volume": False,
            },
        }
