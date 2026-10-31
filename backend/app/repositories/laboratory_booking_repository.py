from typing import List, Optional
from beanie import PydanticObjectId
from datetime import datetime, time

from app.models.laboratory_booking import LaboratoryBooking, EmbeddedTest


class LaboratoryBookingRepository:
    @staticmethod
    async def create(booking: LaboratoryBooking) -> LaboratoryBooking:
        return await booking.insert()

    @staticmethod
    async def get_by_id(id: str) -> Optional[LaboratoryBooking]:
        return await LaboratoryBooking.get(PydanticObjectId(id))

    @staticmethod
    async def get_by_patient_id(patient_id: str) -> List[LaboratoryBooking]:
        return await LaboratoryBooking.find(
            LaboratoryBooking.patient_id == PydanticObjectId(patient_id)
        ).sort(-LaboratoryBooking.created_at).to_list()

    @staticmethod
    async def find_conflicting_booking(
        patient_id: str,
        appointment_date: datetime,
        time_slot: str,
        exclude_booking_id: Optional[str] = None
    ) -> Optional[LaboratoryBooking]:
        # We consider pending and paid as active bookings that conflict.
        query = [
            {
                "$match": {
                    "patient_id": PydanticObjectId(patient_id),
                    "appointment_date": appointment_date,
                    "time_slot": time_slot,
                    "billing_status": {"$in": ["pending", "paid"]},
                }
            }
        ]
        if exclude_booking_id:
            query.append({"$match": {"_id": {"$ne": PydanticObjectId(exclude_booking_id)}}})

        booking = await LaboratoryBooking.aggregate(query).first_or_none()
        return booking

    @staticmethod
    async def update_payment(
        booking_id: str,
        payment_method: str,
        payment_id: str,
        payment_order_id: str,
        payment_status: str,
        billing_status: str
    ) -> Optional[LaboratoryBooking]:
        booking = await LaboratoryBooking.get(PydanticObjectId(booking_id))
        if not booking:
            return None
        booking.payment_method = payment_method
        booking.payment_id = payment_id
        booking.payment_order_id = payment_order_id
        booking.payment_status = payment_status
        booking.billing_status = billing_status
        booking.status = "confirmed" if payment_status == "success" else "failed"
        await booking.save()
        return booking