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
    async def get_by_order_id(payment_order_id: str) -> Optional[LaboratoryBooking]:
        """Locate a laboratory booking by its stored Razorpay order binding.

        Used by webhook payment reconciliation (Phase 4, Task 8): the
        backend-stored payment_order_id is the authoritative mapping from
        a Razorpay event to a domain record (Task 6 §H). Read-only lookup
        — it never mutates state. At most one booking can hold a given
        binding (the Task 2 atomic capture guarantees this).
        """
        if not payment_order_id:
            return None
        return await LaboratoryBooking.find_one(
            LaboratoryBooking.payment_order_id == payment_order_id
        )

    @staticmethod
    async def list_stale_pending_payments(cutoff: datetime) -> List[LaboratoryBooking]:
        """List laboratory bookings eligible for stale-payment reconciliation
        (Phase 4, Task 9).

        A candidate is a booking that:
          - is still payable (billing_status == "pending" — the exact value
            the partial unique index treats as an active slot reservation),
          - is still physically pending (status == "pending_payment"),
          - was created before `cutoff`, and
          - HAS a stored payment_order_id (nothing authoritative to check
            against Razorpay otherwise — never expired).

        Read-only: it never mutates state. Expiry itself happens only through
        the guarded atomic transition in PaymentRepository.
        """
        # Dict-form query (same convention as find_conflicting_booking):
        # matches only genuinely pending bookings that carry a stored order
        # binding and are old enough to consider stale. billing_status=pending
        # is the exact value the partial unique index treats as an active
        # reservation.
        return await LaboratoryBooking.find(
            {
                "billing_status": "pending",
                "status": "pending_payment",
                "payment_order_id": {"$nin": [None, ""]},
                "created_at": {"$lt": cutoff},
            }
        ).to_list()

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
        query: dict = {
            "patient_id": PydanticObjectId(patient_id),
            "appointment_date": appointment_date,
            "time_slot": time_slot,
            "billing_status": {"$in": ["pending", "paid"]},
        }
        if exclude_booking_id:
            query["_id"] = {"$ne": PydanticObjectId(exclude_booking_id)}

        # Beanie 2.1.0's AggregationQuery has no first_or_none(), and its
        # aggregation path is incompatible with the Motor client used by this
        # app (collection.aggregate() is not awaitable on Motor). find_one()
        # runs the same conditions through the supported find path and returns
        # at most one matching document.
        booking = await LaboratoryBooking.find_one(query)
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