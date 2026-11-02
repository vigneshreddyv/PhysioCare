"""Bounded, patient-scoped payment-history queries."""

from datetime import date, datetime, time, timedelta, timezone

from beanie import PydanticObjectId

from app.core.pagination import PageWindow
from app.models.payment_attempt import PaymentAttempt


class PaymentQueryRepository:
    @staticmethod
    async def list_patient_history(
        patient_id: str,
        page: PageWindow,
        *,
        payment_status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        match: dict = {"patient_id": PydanticObjectId(patient_id)}
        if payment_status:
            match["status"] = payment_status
        if start_date or end_date:
            created_at: dict = {}
            if start_date:
                created_at["$gte"] = datetime.combine(
                    start_date, time.min, tzinfo=timezone.utc,
                )
            if end_date:
                created_at["$lt"] = datetime.combine(
                    end_date + timedelta(days=1), time.min, tzinfo=timezone.utc,
                )
            match["created_at"] = created_at

        pipeline = [
            {"$match": match},
            {"$sort": {"created_at": -1, "_id": -1}},
            {"$skip": page.offset},
            {"$limit": page.size},
            {"$lookup": {
                "from": "appointments",
                "localField": "appointment_id",
                "foreignField": "_id",
                "as": "appointment",
            }},
            {"$unwind": {
                "path": "$appointment",
                "preserveNullAndEmptyArrays": True,
            }},
            {"$project": {
                "_id": 1,
                "appointment_id": 1,
                "amount_paise": 1,
                "currency": 1,
                "status": 1,
                "reconciliation_status": 1,
                "appointment.billing_status": 1,
                "appointment.payment_status": 1,
                "appointment.appointment_date": 1,
                "appointment.time_slot": 1,
                "appointment.service_mode": 1,
            }},
        ]
        return await PaymentAttempt.get_pymongo_collection().aggregate(
            pipeline,
        ).to_list(length=page.size)
