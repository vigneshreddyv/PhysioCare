"""
Webhook payment reconciliation (Phase 4, Task 8).

Connects the Task 7 webhook ingestion foundation to payment confirmation
for exactly ONE event: payment.captured. Everything else keeps the Task 7
behavior (recorded, never acted on):

  - payment.captured  -> reconciled (validate + atomic mark-paid)
  - payment.authorized -> recorded/ignored (NO paid transition; the
                          captured-only rule from Task 5 is unchanged)
  - payment.failed     -> recorded ONLY (NO terminal failure transition;
                          Task 5's trusted failure path is unchanged)
  - order.paid         -> recorded/ignored BY DESIGN: it fires alongside
                          payment.captured for the same capture, so acting
                          on it would create a second capture-family
                          confirmation path (Task 6 §D decision)
  - unknown types      -> recorded/ignored (Task 7 behavior)

CRITICAL SAFETY RULE (Task 8 spec): there is NO second payment-
confirmation implementation here. Confirmation is performed by the SAME
atomic repository transitions the verification flow uses —
PaymentRepository.mark_appointment_paid / mark_laboratory_paid — with the
same guard semantics (matches only while the record is still pending and
bound to the stored order id). Verify → webhook and webhook → verify both
converge on the identical transition, and the winner-only notification
rules apply unchanged.

Trust model: the webhook payload itself is NEVER sufficient for financial
confirmation. The payload only supplies the payment_id hint; every
financial fact (existence, order binding, captured state, amount,
currency) is re-derived from Razorpay's Payments API via the Task 1
client, and every domain fact (billing amount, stored order binding) from
the backend database.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpayRequestError,
    fetch_payment,
)
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.laboratory_booking_repository import (
    LaboratoryBookingRepository,
)
from app.repositories.payment_repository import PaymentRepository

logger = logging.getLogger(__name__)

_CURRENCY = "INR"

# Captured-only confirmation (Task 5 rule, unchanged). An authorized
# payment has NOT moved money; this architecture has no capture endpoint,
# so "authorized" can never progress here. Reused conceptually — the
# actual check compares against this single state.
_CAPTURED_STATUS = "captured"


class WebhookReconciliationService:

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    @staticmethod
    async def reconcile_event(
        event_type: str,
        payment_id: Optional[str],
        order_id: Optional[str],
    ) -> str:
        """Reconcile one ingested webhook event.

        Returns a concise outcome string for the ledger's processing
        error/status bookkeeping:

          "reconciled_appointment" / "reconciled_laboratory"
              — this call performed the atomic paid transition.
          "already_paid"
              — the domain record was already paid with the SAME payment
                (verify-first, webhook replay, or duplicate delivery):
                idempotent success, nothing to do.
          "ignored"
              — event type is not reconcilable (authorized/failed/order.paid/
                unknown): recorded only.
          "unmapped"
              — the order_id does not match any stored payment_order_id:
                no domain record mutated.
          "skipped_<reason>"
              — financial validation failed (order/amount/currency/status/
                payment mismatch, Razorpay unreachable): domain state
                untouched, event stays recorded.

        Never raises for expected conditions; unexpected exceptions are
        caught by the caller and recorded as a failed ledger outcome.
        """
        if event_type != "payment.captured":
            # authorized / failed / order.paid / unknown: Task 7 semantics —
            # record only, never a paid transition, never a failure
            # transition.
            return "ignored"

        if not payment_id or not order_id:
            # A captured event without usable references cannot be mapped
            # safely. Recorded; Razorpay's payload shape makes this a
            # should-never-happen condition.
            logger.warning(
                "Webhook payment.captured missing payment/order reference"
            )
            return "skipped_missing_references"

        return await WebhookReconciliationService._reconcile_captured(
            payment_id, order_id
        )

    # ------------------------------------------------------------------
    # payment.captured reconciliation
    # ------------------------------------------------------------------
    @staticmethod
    async def _reconcile_captured(payment_id: str, order_id: str) -> str:
        """Validate a captured payment against backend truth and, only if
        every check passes, perform the existing atomic mark-paid
        transition.

        Validation gates (all must pass; any failure leaves domain state
        untouched):
          1. Razorpay payment fetch succeeds (authoritative source).
          2. Razorpay payment.order_id == the event's order_id.
          3. Razorpay payment.status == "captured" (captured-only rule).
          4. Razorpay payment.amount == backend billing_amount in paise.
          5. Razorpay payment.currency == "INR".
          6. The backend-stored payment_order_id binding matches the
             event's order_id (payment_order_id is authoritative).
        """
        # ---- 1. Authoritative Razorpay payment fetch (Task 1 client) ----
        try:
            payment = await asyncio.to_thread(fetch_payment, payment_id)
        except RazorpayConfigError:
            logger.error("Razorpay configuration missing during reconciliation")
            return "skipped_razorpay_config"
        except RazorpayRequestError:
            # Timeout / 5xx / malformed response: nothing was mutated.
            # The event remains recorded; Razorpay-side re-fetch can be
            # retried by a later delivery of the same payment.
            logger.exception(
                "Razorpay payment lookup failed during reconciliation (payment=%s)",
                payment_id[:8],
            )
            return "skipped_razorpay_unreachable"

        if not isinstance(payment, dict) or not payment.get("id"):
            logger.warning(
                "Webhook reconciliation: malformed Razorpay payment response"
            )
            return "skipped_malformed_payment"

        # ---- 2. The fetched payment must be the event's payment ----
        if str(payment.get("id")) != payment_id:
            logger.warning(
                "Webhook reconciliation: Razorpay returned a different payment id"
            )
            return "skipped_payment_id_mismatch"

        # ---- 3. The payment must belong to the event's order ----
        if str(payment.get("order_id") or "") != order_id:
            logger.warning(
                "Webhook reconciliation: payment/order mismatch (payment=%s)",
                payment_id[:8],
            )
            return "skipped_order_mismatch"

        # ---- 4. Captured-only rule (Task 5, unchanged) ----
        if payment.get("status") != _CAPTURED_STATUS:
            # authorized/failed/refunded/created etc.: never a paid
            # transition from a webhook.
            logger.warning(
                "Webhook reconciliation: payment not captured (status=%s)",
                payment.get("status"),
            )
            return "skipped_not_captured"

        # ---- 5. Currency must be INR (backend only creates INR orders) ----
        if payment.get("currency") != _CURRENCY:
            logger.warning("Webhook reconciliation: unsupported currency")
            return "skipped_currency_mismatch"

        # ---- 6. Locate the domain record via the stored binding ----
        # payment_order_id is THE authoritative mapping (Task 6 §H). No
        # notes/receipt trust, no client-supplied payable ids.
        appointment = await AppointmentRepository.get_by_order_id(order_id)
        booking = None
        if appointment is None:
            booking = await LaboratoryBookingRepository.get_by_order_id(order_id)

        if appointment is None and booking is None:
            # Unmapped order (other environment, foreign order, test-mode
            # leak): record safely, 2xx, never mutate anything.
            logger.warning(
                "Webhook reconciliation: order not mapped to any payable record"
            )
            return "unmapped"

        # ---- 7. Backend-authorized amount (in paise, Task 1 conversion) --
        from app.services.payment_service import PaymentService

        if appointment is not None:
            expected_paise = PaymentService._authoritative_amount_paise(
                appointment.billing_amount, "appointment"
            )
        else:
            expected_paise = PaymentService._authoritative_amount_paise(
                booking.billing_amount, "laboratory booking"
            )

        if payment.get("amount") != expected_paise:
            # Overpayment, underpayment, or tampered amount: never confirm.
            logger.warning(
                "Webhook reconciliation: amount mismatch (expected=%s)",
                expected_paise,
            )
            return "skipped_amount_mismatch"

        # ---- 8. Existing atomic mark-paid transition (THE write path) ----
        # Same methods, same guards, same winner-only semantics as the
        # verification flow. Returns None when this call did not perform
        # the transition (already paid elsewhere, or state moved on).
        if appointment is not None:
            updated = await PaymentRepository.mark_appointment_paid(
                str(appointment.id), payment_id, order_id
            )
        else:
            updated = await PaymentRepository.mark_laboratory_paid(
                str(booking.id), payment_id, order_id
            )

        if updated is not None:
            # Winner: fire the EXISTING winner-only notification helper —
            # the same one the verification flow uses.
            label = (
                "appointment" if appointment is not None else "laboratory"
            )
            recipient_id = (
                str(appointment.patient_id)
                if appointment is not None
                else str(booking.patient_id)
            )
            await PaymentService._notify_payment_success(
                recipient_user_id=recipient_id,
                title=(
                    "Payment Successful"
                    if appointment is not None
                    else "Lab Payment Success"
                ),
                message=(
                    f"Your payment of ₹{updated.get('billing_amount')} for your "
                    f"{label} was successful."
                ),
                related_entity_id=str(updated.get("_id")),
                notification_type=label,
            )
            return (
                "reconciled_appointment"
                if appointment is not None
                else "reconciled_laboratory"
            )

        # Transition not performed here: either a concurrent verify/webhook
        # just confirmed it, or the state moved on. Idempotent answer.
        return "already_paid"
