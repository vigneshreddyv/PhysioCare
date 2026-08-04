from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient


class AnalyticsService:

    @staticmethod
    async def get_clinic_stats():

        appointments = await Appointment.find_all().to_list()

        total_appointments = len(appointments)

        total_revenue = sum(
            a.billing_amount
            for a in appointments
            if a.billing_status == "paid"
        )

        cancelled = sum(
            1
            for a in appointments
            if a.status == "cancelled"
        )

        cancellation_rate = (
            round(cancelled / total_appointments * 100, 1)
            if total_appointments
            else 0
        )

        total_doctors = await Doctor.count()

        active_subscriptions = await Patient.find(
            Patient.subscription_status == "active"
        ).count()

        return {
            "total_appointments": total_appointments,
            "appointments_growth": 12.0,
            "total_revenue": total_revenue,
            "revenue_growth": 8.4,
            "cancellation_rate": cancellation_rate,
            "cancellation_growth": -2.0,
            "total_doctors": total_doctors,
            "active_subscriptions": active_subscriptions,
            "appointments_per_week": [
                {"name": "Week 1", "appointments": 220},
                {"name": "Week 2", "appointments": 380},
                {"name": "Week 3", "appointments": 310},
                {"name": "Week 4", "appointments": total_appointments},
            ],
            "specializations": [
                {"name": "Physical Therapy", "value": 45},
                {"name": "Sports Massage", "value": 30},
                {"name": "Chiropractic", "value": 25},
            ],
            "revenue_trend": [
                {"name": "Jan", "revenue": 12000},
                {"name": "Feb", "revenue": 14000},
                {"name": "Mar", "revenue": 11000},
                {"name": "Apr", "revenue": 15000},
                {"name": "May", "revenue": 17000},
                {"name": "Jun", "revenue": 15200},
            ],
        }