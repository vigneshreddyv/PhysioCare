from datetime import datetime, time, timedelta
from typing import List, Optional

from beanie import PydanticObjectId

from app.models.appointment import ACTIVE_STATUSES, Appointment, canonical_appointment_date


class AppointmentRepository:

    @staticmethod
    async def get_by_id(id: str) -> Optional[Appointment]:
        return await Appointment.get(PydanticObjectId(id))

    @staticmethod
    async def get_by_order_id(payment_order_id: str) -> Optional[Appointment]:
        """Locate an appointment by its stored Razorpay order binding.

        Used by webhook payment reconciliation (Phase 4, Task 8): the
        backend-stored payment_order_id is the authoritative mapping from
        a Razorpay event to a domain record (Task 6 §H). Read-only lookup
        — it never mutates state. At most one appointment can hold a given
        binding (the Task 2 atomic claim guarantees this).
        """
        if not payment_order_id:
            return None
        return await Appointment.find_one(
            Appointment.payment_order_id == payment_order_id
        )

    @staticmethod
    async def list_stale_pending_payments(cutoff: datetime) -> List[Appointment]:
        """List online-payment appointments eligible for stale-payment
        reconciliation (Phase 4, Task 9).

        A candidate is an appointment that:
          - is still in the payable state (status == "pending_payment"),
          - was created before `cutoff` (booking creation is the only
            timestamp the model has — the Razorpay order's own created_at is
            checked by the service before any expiry), and
          - HAS a stored payment_order_id (records without an order were
            never taken to Checkout; there is nothing authoritative to check
            against Razorpay, so the service can never safely expire them).

        Read-only: it never mutates state. Expiry itself happens only through
        the guarded atomic transition in PaymentRepository.
        """
        # Dict-form query (same convention as the existing conflict checks):
        # matches only genuinely pending online-payment bookings that carry a
        # stored order binding and are old enough to consider stale.
        return await Appointment.find(
            {
                "status": "pending_payment",
                "payment_order_id": {"$nin": [None, ""]},
                "created_at": {"$lt": cutoff},
            }
        ).to_list()

    @staticmethod
    async def create(appointment: Appointment) -> Appointment:
        return await appointment.insert()

    @staticmethod
    async def create_safely(appointment: Appointment) -> Optional[Appointment]:
        """Insert the appointment, returning None when a concurrent request
        already created the same active patient/date/slot booking.

        The unique index in MongoDB makes the conflict check and the insert a
        single atomic operation, closing the check-then-insert race window.
        """
        from pymongo.errors import DuplicateKeyError

        try:
            return await appointment.insert()
        except DuplicateKeyError:
            return None

    @staticmethod
    async def list_all() -> List[Appointment]:
        return await Appointment.find().sort(
            -Appointment.appointment_date
        ).to_list()

    @staticmethod
    async def list_by_patient_id(patient_id: str) -> List[Appointment]:
        return await Appointment.find(
            Appointment.patient_id == PydanticObjectId(patient_id)
        ).sort(
            -Appointment.appointment_date
        ).to_list()

    @staticmethod
    async def list_by_doctor_id(doctor_id: str) -> List[Appointment]:
        return await Appointment.find(
            Appointment.doctor_id == PydanticObjectId(doctor_id)
        ).sort(
            -Appointment.appointment_date
        ).to_list()

    @staticmethod
    async def list_today() -> List[Appointment]:
        today = datetime.utcnow().date()

        start_of_day = datetime.combine(today, time.min)
        end_of_day = datetime.combine(today, time.max)

        return await Appointment.find(
            Appointment.appointment_date >= start_of_day,
            Appointment.appointment_date <= end_of_day,
        ).to_list()

    @staticmethod
    async def doctor_has_slot(
        doctor_id: str,
        appointment_date: datetime,
        time_slot: str,
        exclude_appointment_id: Optional[str] = None
    ) -> bool:
        # Availability is keyed on the calendar day + time slot, never on the
        # incidental clock time stored in appointment_date (legacy/seeded
        # records carry arbitrary timestamps).
        day_start = canonical_appointment_date(appointment_date)
        day_end = day_start + timedelta(days=1)

        query_filters = [
            Appointment.doctor_id == PydanticObjectId(doctor_id),
            Appointment.appointment_date >= day_start,
            Appointment.appointment_date < day_end,
            Appointment.time_slot == time_slot,
            Appointment.status.in_(ACTIVE_STATUSES),
        ]
        if exclude_appointment_id:
            query_filters.append(Appointment.id != PydanticObjectId(exclude_appointment_id))

        appointment = await Appointment.find_one(*query_filters)
        return appointment is not None

    @staticmethod
    async def patient_has_slot(
        patient_id: str,
        appointment_date: datetime,
        time_slot: str,
        exclude_appointment_id: Optional[str] = None
    ) -> bool:
        # Same calendar day + time slot conflicts regardless of the stored
        # timestamp's clock time.
        day_start = canonical_appointment_date(appointment_date)
        day_end = day_start + timedelta(days=1)

        query_filters = [
            Appointment.patient_id == PydanticObjectId(patient_id),
            Appointment.appointment_date >= day_start,
            Appointment.appointment_date < day_end,
            Appointment.time_slot == time_slot,
            Appointment.status.in_(ACTIVE_STATUSES),
        ]
        if exclude_appointment_id:
            query_filters.append(Appointment.id != PydanticObjectId(exclude_appointment_id))

        appointment = await Appointment.find_one(*query_filters)
        return appointment is not None
