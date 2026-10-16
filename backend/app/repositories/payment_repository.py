"""
Razorpay order binding repository (Phase 4, Task 2).

Provides the ONLY write path for binding a Razorpay order id to a payable
domain object (appointment / laboratory booking). Binding happens through a
single atomic MongoDB find_one_and_update that matches the payable object
only while it is STILL in a payable state AND its payment_order_id is unset
(null or missing — both match None in Mongo). Two concurrent "Pay" requests
can therefore never bind two different orders to the same payable object,
and a cancelled/paid object can never be bound after the fact.

No new fields or indexes are used: payment_order_id already exists on both
models.
"""
from typing import Any, Dict, Optional

from beanie import PydanticObjectId
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from app.models.appointment import Appointment
from app.models.laboratory_booking import LaboratoryBooking


class PaymentRepository:

    @staticmethod
    async def claim_appointment_order(
        appointment_id: str,
        order_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Atomically bind order_id to the appointment iff still payable+unbound.

        Matches only:
          - this appointment id
          - payment_order_id unset (None/missing)
          - status still "pending_payment" (the online-payment state)

        Returns the updated appointment document dict when the claim wins.
        Returns None when it loses the race (another request bound first),
        when the appointment was concurrently moved out of the payable state,
        or on a transient database error — callers must re-read state and
        decide (reuse the winner's order, or reject).
        """
        coll = Appointment.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {
                    "_id": PydanticObjectId(appointment_id),
                    "payment_order_id": None,
                    "status": "pending_payment",
                },
                {"$set": {"payment_order_id": order_id}},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    @staticmethod
    async def claim_laboratory_order(
        booking_id: str,
        order_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Atomically bind order_id to the laboratory booking iff still
        payable+unbound.

        Matches only:
          - this booking id
          - payment_order_id unset (None/missing)
          - billing_status still "pending" (paid/failed bookings are not
            payable) and physical status still "pending_payment"

        Same return semantics as claim_appointment_order.
        """
        coll = LaboratoryBooking.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {
                    "_id": PydanticObjectId(booking_id),
                    "payment_order_id": None,
                    "billing_status": "pending",
                    "status": "pending_payment",
                },
                {"$set": {"payment_order_id": order_id}},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    # ------------------------------------------------------------------
    # Verification-phase transitions (Task 4)
    # ------------------------------------------------------------------

    @staticmethod
    async def mark_appointment_paid(
        appointment_id: str,
        payment_id: str,
        order_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Atomically transition the appointment to its paid/confirmed state.

        The update matches ONLY while the appointment is still awaiting
        payment AND still bound to THIS order id. Two concurrent verification
        requests for the same payment can therefore never both perform the
        transition (and its notification side effect); a different payment
        can never overwrite an already-verified payment.

        Returns the updated document dict when THIS request performed the
        transition, None when the transition did not happen here (already
        verified elsewhere, stale order binding, or state moved on).
        """
        coll = Appointment.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {
                    "_id": PydanticObjectId(appointment_id),
                    "payment_order_id": order_id,
                    "status": "pending_payment",
                },
                {
                    "$set": {
                        "status": "confirmed",
                        "billing_status": "paid",
                        "payment_status": "success",
                        "payment_id": payment_id,
                        "payment_method": "online",
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    @staticmethod
    async def mark_laboratory_paid(
        booking_id: str,
        payment_id: str,
        order_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Atomically transition the laboratory booking to paid/confirmed.

        Matches ONLY while billing_status is still pending and the booking is
        bound to THIS order id, mirroring LaboratoryService.update_payment's
        existing success semantics (billing_status -> paid,
        payment_status -> success, status -> confirmed) without its
        check-then-save race.
        """
        coll = LaboratoryBooking.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {
                    "_id": PydanticObjectId(booking_id),
                    "payment_order_id": order_id,
                    "billing_status": "pending",
                    "status": "pending_payment",
                },
                {
                    "$set": {
                        "status": "confirmed",
                        "billing_status": "paid",
                        "payment_status": "success",
                        "payment_id": payment_id,
                        "payment_method": "online",
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    @staticmethod
    async def mark_laboratory_failed(
        booking_id: str,
        payment_id: str,
        order_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Atomically transition the laboratory booking to its failed state.

        Used ONLY for Razorpay-AUTHORITATIVE failures: the payment signature
        verified and Razorpay itself reports status="failed" for a payment
        belonging to the stored order. This is the existing accepted
        failed-payment slot-release path (billing_status=failed removes the
        booking from uniq_patient_date_slot's partial filter and from the
        application-level conflict check).

        Guarded exactly like mark_laboratory_paid: matches only while the
        booking is still pending and bound to THIS order id. Returns the
        updated document dict when THIS request performed the transition,
        None otherwise (already failed elsewhere, state moved, or a
        transient database error).
        """
        coll = LaboratoryBooking.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {
                    "_id": PydanticObjectId(booking_id),
                    "payment_order_id": order_id,
                    "billing_status": "pending",
                    "status": "pending_payment",
                },
                {
                    "$set": {
                        "status": "failed",
                        "billing_status": "failed",
                        "payment_status": "failed",
                        "payment_id": payment_id,
                        "payment_method": "online",
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    # ------------------------------------------------------------------
    # Stale-payment expiry (Phase 4, Task 9)
    # ------------------------------------------------------------------

    @staticmethod
    async def expire_appointment_pending_payment(
        appointment_id: str,
        order_id: str,
        payment_status: str = "expired",
    ) -> Optional[Dict[str, Any]]:
        """Atomically expire a stale pending-payment appointment.

        Guarded exactly like the mark-paid transitions: matches ONLY while
        the appointment is still in its payable state (status="pending_payment")
        AND still bound to the stored order id. If a verification/webhook
        transition won the race first, the guard does not match and nothing
        is mutated — a paid record can NEVER be flipped by expiry.

        Final state (existing state vocabulary only, no new states):
          - status: "pending_payment" → "cancelled"
            (mirrors the existing patient-cancellation semantics; "cancelled"
            is excluded from ACTIVE_STATUSES, so the partial unique index
            releases the slot — the only slot-release mechanism that exists
            for appointments)
          - billing_status: "pending" → "failed"
            (internally consistent: a cancelled booking is never payable;
            "failed" matches the Task 5 no-money-taken billing vocabulary —
            the value "cancelled" does not exist in the appointment billing
            contract, and inventing it would be a new financial state)
          - payment_status: "pending" → "expired"

        "expired" is a VALUE of the existing payment_status field, not a new
        domain state: appointment.payment_status has no constrained enum in
        the model or schema, so adding an observable value is safe and makes
        the expiry reason explicit for later reconciliation tooling.

        payment_id is NEVER written: no payment moved. payment_method is
        left untouched so the record still truthfully says how it was being
        paid ("online").

        Args:
            payment_status: the payment_status value to set. Defaults to
                "expired"; a caller may pass "failed" to reuse the exact
                Task 5 failure vocabulary instead.
        """
        coll = Appointment.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {
                    "_id": PydanticObjectId(appointment_id),
                    "payment_order_id": order_id,
                    "status": "pending_payment",
                },
                {
                    "$set": {
                        "status": "cancelled",
                        "billing_status": "failed",
                        "payment_status": payment_status,
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    @staticmethod
    async def expire_laboratory_pending_payment(
        booking_id: str,
        order_id: str,
        payment_status: str = "expired",
    ) -> Optional[Dict[str, Any]]:
        """Atomically expire a stale pending-payment laboratory booking.

        THE critical invariant (Task 9): after expiry the booking must NOT
        remain billing_status="pending", because the laboratory partial
        unique index treats billing_status in (pending, paid) as an active
        slot reservation. The guard matches ONLY while billing_status is
        still "pending" and the booking is still bound to this order, so:
        - a paid booking can never be expired (guard mismatch), and
        - a lost race against verification/webhook mutates nothing.

        Final state (existing vocabulary, mirroring the existing Task 5
        Razorpay-authoritative failure semantics — the only lifecycle path
        that releases a laboratory slot):
          - status: "pending_payment" → "failed"
          - billing_status: "pending" → "failed"
          - payment_status: "pending" → payment_status arg (default "expired")

        Why not status="cancelled"? The laboratory lifecycle map
        (LaboratoryService.update_booking_status) allows pending_payment →
        {confirmed, failed, cancelled}, but "cancelled" is an ADMIN/DOCTOR
        action with its own "Lab Booking Cancelled" notification semantics,
        and no laboratory code path has ever set status="cancelled" with
        billing_status="failed" together. status="failed" +
        billing_status="failed" is exactly the existing accepted post-failure
        record shape (mark_laboratory_failed), just without a payment_id
        because no payment was taken. This keeps every expired record
        indistinguishable in shape from the already-accepted failure records.

        payment_id is NEVER written (no money moved).
        """
        coll = LaboratoryBooking.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {
                    "_id": PydanticObjectId(booking_id),
                    "payment_order_id": order_id,
                    "billing_status": "pending",
                    "status": "pending_payment",
                },
                {
                    "$set": {
                        "status": "failed",
                        "billing_status": "failed",
                        "payment_status": payment_status,
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None
