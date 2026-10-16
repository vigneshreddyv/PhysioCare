"""
Server-side Razorpay order creation (Phase 4, Task 2).

Creates or reuses a Razorpay Order for an authenticated patient's
appointment or laboratory booking. The backend remains authoritative for:
- the payable amount (from stored billing_amount, never from the client)
- currency (INR)
- patient ownership
- payable state
- the stored payment_order_id binding

Creating an order NEVER marks anything as paid and NEVER transitions any
state — it only establishes the Razorpay order that the later
checkout/verification phase will consume.

Idempotency: the payment_order_id binding is claimed with a single atomic
find_one_and_update (see PaymentRepository). Repeated "Pay" requests reuse
the existing active order instead of creating duplicates.
"""
import asyncio
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpayRequestError,
    RazorpaySignatureError,
    create_order,
    fetch_payment,
    get_razorpay_client,
    rupees_to_paise,
    verify_payment_signature,
)
from app.models.appointment import Appointment
from app.models.laboratory_booking import LaboratoryBooking
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.laboratory_booking_repository import LaboratoryBookingRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.payment import RazorpayOrderResponse, RazorpayVerifyRequest, RazorpayVerifyResponse

logger = logging.getLogger(__name__)

_CURRENCY = "INR"


class PaymentService:

    # ------------------------------------------------------------------
    # Appointments
    # ------------------------------------------------------------------
    @staticmethod
    async def create_appointment_order(
        user_id: str,
        appointment_id: str,
    ) -> RazorpayOrderResponse:
        """Create (or reuse) the Razorpay order for an appointment.

        Raises HTTPException with project-conventional status codes on:
        not found, ownership failure, non-payable state, invalid billing
        amount, missing configuration, and Razorpay failures.
        """
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        appointment = await AppointmentRepository.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        # Ownership: another patient's appointment is indistinguishable from
        # a missing one (no existence leak).
        if str(appointment.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        # Reuse: an existing binding IS the active payable order. No Razorpay
        # call is made on this path.
        if appointment.payment_order_id:
            return PaymentService._existing_appointment_response(appointment)

        # Payable state: only online bookings awaiting payment are payable.
        # Offline bookings are created directly as "confirmed"; paid/
        # cancelled/completed appointments can never be re-ordered.
        if appointment.status != "pending_payment":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This appointment is not awaiting payment",
            )

        amount_paise = PaymentService._authoritative_amount_paise(
            appointment.billing_amount, "appointment"
        )

        order = await PaymentService._create_razorpay_order(
            amount_paise=amount_paise,
            receipt=f"apt_{appointment.id}",
            notes={
                "payable_type": "appointment",
                "payable_id": str(appointment.id),
            },
        )

        claimed = await PaymentRepository.claim_appointment_order(
            str(appointment.id), order["id"]
        )

        if claimed is None:
            # Lost the race, the state changed concurrently, or the atomic
            # claim hit a transient database error. Re-read and resolve.
            return await PaymentService._resolve_lost_appointment_claim(
                str(appointment.id), order["id"]
            )

        # Winner: the binding is persisted. Return the checkout data.
        return PaymentService._order_response(
            order["id"], claimed.get("billing_amount", appointment.billing_amount)
        )

    # ------------------------------------------------------------------
    # Laboratory bookings
    # ------------------------------------------------------------------
    @staticmethod
    async def create_laboratory_booking_order(
        user_id: str,
        booking_id: str,
    ) -> RazorpayOrderResponse:
        """Create (or reuse) the Razorpay order for a laboratory booking."""
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        booking = await LaboratoryBookingRepository.get_by_id(booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied",
            )

        # Ownership (mirrors LaboratoryService.get_booking_by_id semantics).
        if str(booking.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied",
            )

        if booking.payment_order_id:
            return PaymentService._existing_laboratory_response(booking)

        # Payable state: pending billing AND pending_payment physical status.
        # Paid, failed, cancelled, and completed bookings are not payable.
        # This preserves the existing failed-payment slot-release semantics:
        # order creation never resurrects or mutates those states.
        if booking.billing_status != "pending" or booking.status != "pending_payment":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This booking is not awaiting payment",
            )

        amount_paise = PaymentService._authoritative_amount_paise(
            booking.billing_amount, "laboratory booking"
        )

        order = await PaymentService._create_razorpay_order(
            amount_paise=amount_paise,
            receipt=f"lab_{booking.id}",
            notes={
                "payable_type": "laboratory_booking",
                "payable_id": str(booking.id),
            },
        )

        claimed = await PaymentRepository.claim_laboratory_order(
            str(booking.id), order["id"]
        )

        if claimed is None:
            return await PaymentService._resolve_lost_laboratory_claim(
                str(booking.id), order["id"]
            )

        return PaymentService._order_response(
            order["id"], claimed.get("billing_amount", booking.billing_amount)
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _authoritative_amount_paise(billing_amount, label: str) -> int:
        """Convert the backend-stored rupee amount to integer paise.

        Stored amounts are floats (existing schema), and multi-test
        laboratory totals carry binary float noise (e.g. 1050.3000000000002).
        Normalization is exact-money-safe: Decimal(str(x)) then quantize to
        2 dp (ROUND_HALF_UP) BEFORE the Task 1 conversion helper. No float
        arithmetic is used anywhere in this path. Client input is never
        involved.
        """
        if billing_amount is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {label} does not have a valid billing amount",
            )
        try:
            d = Decimal(str(billing_amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {label} does not have a valid billing amount",
            )
        if d <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {label} does not have a valid billing amount",
            )
        try:
            return rupees_to_paise(d)
        except RazorpayRequestError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {label} does not have a valid billing amount",
            )

    @staticmethod
    async def _create_razorpay_order(
        amount_paise: int,
        receipt: str,
        notes: dict,
    ) -> dict:
        """Call the Task 1 helper and map its safe errors to HTTP semantics."""
        # Validate configuration up front so a misconfiguration surfaces as
        # 503 even on paths that would otherwise skip client construction.
        try:
            get_razorpay_client()
        except RazorpayConfigError:
            logger.error("Razorpay configuration missing during order creation")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service is not available",
            )

        try:
            return create_order(amount_paise, _CURRENCY, receipt, notes)
        except RazorpayConfigError:
            logger.error("Razorpay configuration missing during order creation")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service is not available",
            )
        except RazorpayRequestError:
            # Safe error from Task 1 (API failure, timeout, malformed
            # response). Details are logged server-side only; the client gets
            # a generic retryable message. No secrets, no SDK internals.
            logger.exception("Razorpay order creation failed (receipt=%s)", receipt)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not create the payment order. Please try again.",
            )

    @staticmethod
    def _order_response(order_id: str, billing_amount) -> RazorpayOrderResponse:
        # key_id is the PUBLIC key and is explicitly required in the response
        # shape; key_secret never leaves the backend.
        return RazorpayOrderResponse(
            key_id=settings.RAZORPAY_KEY_ID,
            order_id=order_id,
            amount=PaymentService._authoritative_amount_paise(billing_amount, "payable"),
            currency=_CURRENCY,
        )

    @staticmethod
    def _existing_appointment_response(appointment: Appointment) -> RazorpayOrderResponse:
        return PaymentService._order_response(
            appointment.payment_order_id, appointment.billing_amount
        )

    @staticmethod
    def _existing_laboratory_response(booking: LaboratoryBooking) -> RazorpayOrderResponse:
        return PaymentService._order_response(
            booking.payment_order_id, booking.billing_amount
        )

    # -- Race resolution -------------------------------------------------
    @staticmethod
    async def _resolve_lost_appointment_claim(
        appointment_id: str, created_order_id: str
    ) -> RazorpayOrderResponse:
        fresh = await AppointmentRepository.get_by_id(appointment_id)
        if not fresh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )
        if fresh.payment_order_id:
            if fresh.payment_order_id == created_order_id:
                # Defensive: the claim actually persisted but reported failure.
                return PaymentService._order_response(
                    created_order_id, fresh.billing_amount
                )
            # A concurrent request bound its own order first: reuse it so the
            # application never casually ends up with two active orders.
            return PaymentService._order_response(
                fresh.payment_order_id, fresh.billing_amount
            )
        if fresh.status != "pending_payment":
            # State moved (cancelled/paid) while we were talking to Razorpay.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This appointment is not awaiting payment",
            )
        # Transient claim failure on a still-payable appointment: one retry.
        claimed = await PaymentRepository.claim_appointment_order(
            appointment_id, created_order_id
        )
        if claimed is not None:
            return PaymentService._order_response(
                created_order_id, claimed.get("billing_amount")
            )
        logger.error(
            "Could not bind Razorpay order %s to appointment %s",
            created_order_id,
            appointment_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not associate the payment order. Please try again.",
        )

    @staticmethod
    async def _resolve_lost_laboratory_claim(
        booking_id: str, created_order_id: str
    ) -> RazorpayOrderResponse:
        fresh = await LaboratoryBookingRepository.get_by_id(booking_id)
        if not fresh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied",
            )
        if fresh.payment_order_id:
            if fresh.payment_order_id == created_order_id:
                return PaymentService._order_response(
                    created_order_id, fresh.billing_amount
                )
            return PaymentService._order_response(
                fresh.payment_order_id, fresh.billing_amount
            )
        if fresh.billing_status != "pending" or fresh.status != "pending_payment":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This booking is not awaiting payment",
            )
        claimed = await PaymentRepository.claim_laboratory_order(
            booking_id, created_order_id
        )
        if claimed is not None:
            return PaymentService._order_response(
                created_order_id, claimed.get("billing_amount")
            )
        logger.error(
            "Could not bind Razorpay order %s to laboratory booking %s",
            created_order_id,
            booking_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not associate the payment order. Please try again.",
        )

    # ==================================================================
    # Payment verification (Phase 4, Task 4)
    # ==================================================================

    @staticmethod
    async def verify_appointment_payment(
        user_id: str,
        appointment_id: str,
        schema: RazorpayVerifyRequest,
    ) -> RazorpayVerifyResponse:
        """Verify and confirm an appointment's Razorpay payment.

        Every frontend value is untrusted. The gate sequence is:
        ownership -> stored-order match -> HMAC signature -> Razorpay-side
        payment truth (order/amount/currency/state) -> atomic state
        transition -> notification. Any failure leaves the appointment
        untouched (still pending_payment, no payment_id stored).
        """
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        appointment = await AppointmentRepository.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        # Ownership: no existence leak for other patients' appointments.
        if str(appointment.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        # The backend-stored binding is authoritative: a valid signature for
        # a DIFFERENT order must never confirm this appointment.
        stored_order_id = appointment.payment_order_id
        if not stored_order_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No payment order exists for this appointment",
            )
        if schema.razorpay_order_id != stored_order_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment does not match this appointment",
            )

        # Already verified? Idempotent replay: same payment -> safe success,
        # different payment -> reject (never overwrite the first payment).
        if appointment.payment_status == "success" or appointment.status == "confirmed":
            if schema.razorpay_payment_id == appointment.payment_id:
                return RazorpayVerifyResponse(
                    status="verified",
                    payment_status="success",
                    billing_status=appointment.billing_status,
                    entity_status=appointment.status,
                    message="Payment already verified",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A different payment was already verified for this appointment",
            )

        # 1. HMAC-SHA256 via the Task 1 helper (constant-time compare).
        try:
            valid = verify_payment_signature(
                schema.razorpay_order_id,
                schema.razorpay_payment_id,
                schema.razorpay_signature,
            )
        except RazorpayConfigError:
            logger.error("Razorpay configuration missing during verification")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service is not available",
            )
        except RazorpaySignatureError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed",
            )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed",
            )

        # 2. Razorpay-side truth via the centralized client. Signature alone
        #    is NOT trusted when the API can provide authoritative details.
        expected_paise = PaymentService._authoritative_amount_paise(
            appointment.billing_amount, "appointment"
        )
        payment = await PaymentService._fetch_payment_safe(schema.razorpay_payment_id)
        PaymentService._validate_payment_against_domain(
            payment,
            stored_order_id,
            expected_paise,
            "appointment",
        )

        # 3. Atomic transition. Side effects (notification) only when THIS
        #    request performed the transition.
        updated = await PaymentRepository.mark_appointment_paid(
            str(appointment.id),
            schema.razorpay_payment_id,
            stored_order_id,
        )

        if updated is not None:
            await PaymentService._notify_payment_success(
                recipient_user_id=str(appointment.patient_id),
                title="Payment Successful",
                message=(
                    f"Your payment of ₹{updated.get('billing_amount')} for your "
                    f"appointment on {appointment.appointment_date.strftime('%Y-%m-%d')} "
                    "was successful."
                ),
                related_entity_id=str(appointment.id),
                notification_type="appointment",
            )
            return RazorpayVerifyResponse(
                status="verified",
                payment_status="success",
                billing_status=updated.get("billing_status"),
                entity_status=updated.get("status"),
            )

        # Transition not performed here: either a concurrent request just
        # verified the same payment, or state moved on. Re-read for the
        # idempotent answer; never overwrite an existing payment.
        fresh = await AppointmentRepository.get_by_id(appointment_id)
        if fresh and fresh.payment_id == schema.razorpay_payment_id:
            return RazorpayVerifyResponse(
                status="verified",
                payment_status="success",
                billing_status=fresh.billing_status,
                entity_status=fresh.status,
                message="Payment already verified",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment can no longer be verified in its current state",
        )

    @staticmethod
    async def verify_laboratory_payment(
        user_id: str,
        booking_id: str,
        schema: RazorpayVerifyRequest,
    ) -> RazorpayVerifyResponse:
        """Verify and confirm a laboratory booking's Razorpay payment.

        Same untrusted-input gate sequence as the appointment flow.
        """
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        booking = await LaboratoryBookingRepository.get_by_id(booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied",
            )

        if str(booking.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied",
            )

        stored_order_id = booking.payment_order_id
        if not stored_order_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No payment order exists for this booking",
            )
        if schema.razorpay_order_id != stored_order_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment does not match this booking",
            )

        if booking.payment_status == "success" or booking.billing_status == "paid":
            if schema.razorpay_payment_id == booking.payment_id:
                return RazorpayVerifyResponse(
                    status="verified",
                    payment_status="success",
                    billing_status=booking.billing_status,
                    entity_status=booking.status,
                    message="Payment already verified",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A different payment was already verified for this booking",
            )

        try:
            valid = verify_payment_signature(
                schema.razorpay_order_id,
                schema.razorpay_payment_id,
                schema.razorpay_signature,
            )
        except RazorpayConfigError:
            logger.error("Razorpay configuration missing during verification")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service is not available",
            )
        except RazorpaySignatureError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed",
            )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed",
            )

        expected_paise = PaymentService._authoritative_amount_paise(
            booking.billing_amount, "laboratory booking"
        )
        payment = await PaymentService._fetch_payment_safe(schema.razorpay_payment_id)

        # Razorpay-AUTHORITATIVE failure: the signature is valid and Razorpay
        # itself reports this payment (for the stored order, expected amount
        # and currency) as failed. This is the ONLY trusted failure signal —
        # frontend failure callbacks are never trusted. Transition to the
        # existing failed state, which releases the slot through the already
        # accepted partial-index/conflict-check semantics. Any non-captured,
        # non-failed status (created/pending/…) falls through to the strict
        # validation below and leaves the booking safely pending.
        if (
            payment.get("status") == "failed"
            and payment.get("order_id") == stored_order_id
            and payment.get("currency") == _CURRENCY
            and payment.get("amount") == expected_paise
        ):
            return await PaymentService._fail_laboratory_payment(
                booking, booking_id, schema.razorpay_payment_id, stored_order_id
            )

        PaymentService._validate_payment_against_domain(
            payment,
            stored_order_id,
            expected_paise,
            "laboratory booking",
        )

        updated = await PaymentRepository.mark_laboratory_paid(
            str(booking.id),
            schema.razorpay_payment_id,
            stored_order_id,
        )

        if updated is not None:
            await PaymentService._notify_payment_success(
                recipient_user_id=str(booking.patient_id),
                title="Lab Payment Success",
                message=(
                    f"Your payment of ₹{updated.get('billing_amount')} for your "
                    "laboratory booking was successful."
                ),
                related_entity_id=str(booking.id),
                notification_type="laboratory",
            )
            return RazorpayVerifyResponse(
                status="verified",
                payment_status="success",
                billing_status=updated.get("billing_status"),
                entity_status=updated.get("status"),
            )

        fresh = await LaboratoryBookingRepository.get_by_id(booking_id)
        if fresh and fresh.payment_id == schema.razorpay_payment_id:
            return RazorpayVerifyResponse(
                status="verified",
                payment_status="success",
                billing_status=fresh.billing_status,
                entity_status=fresh.status,
                message="Payment already verified",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This booking can no longer be verified in its current state",
        )

    # ------------------------------------------------------------------
    # Verification internals
    # ------------------------------------------------------------------
    # A Razorpay payment is confirmation-worthy ONLY when captured.
    #
    # Task 5 decision (authorized vs captured): an "authorized" payment has
    # NOT moved money yet — it still requires an explicit capture (server
    # capture API, auth-and-capture flow) to complete. This architecture has
    # NO capture endpoint and NO reconciliation/webhook system, so an
    # authorized payment could never progress to captured after being marked
    # paid. Confirming on "authorized" would therefore strand bookings in a
    # paid state for potentially uncollected money. Standard Razorpay
    # Checkout (no capture options set) always returns "captured" for
    # successful payments, so this restriction changes nothing for the
    # integrated flow — it only prevents confirming money that was never
    # collected. If auth-and-capture is introduced later (with a capture
    # path), "authorized" can be revisited with explicit tests.
    _PAYMENT_CONFIRMABLE_STATES = ("captured",)

    @staticmethod
    async def _fail_laboratory_payment(
        booking,
        booking_id: str,
        payment_id: str,
        order_id: str,
    ) -> RazorpayVerifyResponse:
        """Perform the Razorpay-authoritative failed transition exactly once.

        The atomic claim matches only while the booking is still pending and
        bound to THIS order. The transition winner notifies; replayed failure
        verifications take the idempotent branch below (no duplicate
        notification). Failed bookings release their slot via the existing
        billing_status=failed semantics (partial unique index + conflict
        check both exclude failed).
        """
        updated = await PaymentRepository.mark_laboratory_failed(
            str(booking.id), payment_id, order_id
        )
        if updated is not None:
            await PaymentService._notify_payment_success(
                recipient_user_id=str(booking.patient_id),
                title="Lab Payment Failed",
                message=(
                    f"Your payment of ₹{updated.get('billing_amount')} for your "
                    "laboratory booking has failed. Your slot has been released "
                    "— you can safely book again."
                ),
                related_entity_id=str(booking.id),
                notification_type="laboratory",
            )
            return RazorpayVerifyResponse(
                status="failed",
                payment_status="failed",
                billing_status=updated.get("billing_status"),
                entity_status=updated.get("status"),
            )

        # Transition not performed here: replayed verification, or the state
        # moved concurrently. Re-read for the idempotent answer.
        fresh = await LaboratoryBookingRepository.get_by_id(booking_id)
        if (
            fresh
            and fresh.payment_id == payment_id
            and fresh.billing_status == "failed"
        ):
            return RazorpayVerifyResponse(
                status="failed",
                payment_status="failed",
                billing_status=fresh.billing_status,
                entity_status=fresh.status,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This booking can no longer be verified in its current state",
        )

    @staticmethod
    async def _fetch_payment_safe(payment_id: str) -> dict:
        """Fetch payment details via the Task 1 client with safe HTTP mapping."""
        try:
            return await asyncio.to_thread(fetch_payment, payment_id)
        except RazorpayConfigError:
            logger.error("Razorpay configuration missing during verification")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service is not available",
            )
        except RazorpayRequestError:
            logger.exception(
                "Razorpay payment lookup failed during verification (payment=%s)",
                payment_id[:8],
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Payment is being verified. Please try again shortly."
                ),
            )

    @staticmethod
    def _validate_payment_against_domain(
        payment: dict,
        stored_order_id: str,
        expected_paise: int,
        label: str,
    ) -> None:
        """Cross-check Razorpay's authoritative payment data against the
        backend's own records. Every mismatch is a hard rejection that leaves
        domain state untouched.
        """
        # The payment must belong to the backend-stored order.
        if payment.get("order_id") != stored_order_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment does not match this booking",
            )

        # Amount: Razorpay's captured amount must equal the backend's
        # authoritative amount (both integer paise).
        if payment.get("amount") != expected_paise:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount does not match the expected amount",
            )

        # Currency: the backend only creates INR orders.
        if payment.get("currency") != _CURRENCY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment currency is not supported",
            )

        # Payment state: only captured/authorized payments may confirm.
        if payment.get("status") not in PaymentService._PAYMENT_CONFIRMABLE_STATES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment is not in a confirmable state",
            )

    @staticmethod
    async def _notify_payment_success(
        recipient_user_id: str,
        title: str,
        message: str,
        related_entity_id: str,
        notification_type: str,
    ) -> None:
        """Create the existing success notification exactly once — only the
        request that performed the atomic transition calls this. Notification
        failures never fail an already-committed verification.
        """
        try:
            from app.models.patient import Patient

            patient = await Patient.get(PydanticObjectId(recipient_user_id))
            recipient = str(patient.user_id) if patient else recipient_user_id
        except Exception:
            recipient = recipient_user_id

        try:
            from app.services.notification_service import NotificationService

            await NotificationService.create_notification(
                recipient_user_id=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                related_entity_id=related_entity_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to create payment success notification: %s", exc
            )
