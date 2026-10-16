"""
Stale pending-payment reconciliation & safe expiry (Phase 4, Task 9).

Releases slots held by pending_payment records that are no longer
legitimately reserved, WITHOUT ever risking captured money. The decision is
never a blind timeout: every candidate is checked against Razorpay first,
and the system fails CLOSED — any uncertainty keeps the booking pending.

Decision flow per candidate (appointment or laboratory booking):

    pending domain record
        ↓  (status=pending_payment [+ billing_status=pending for lab],
            created_at older than PAYMENT_PENDING_EXPIRY_MINUTES,
            payment_order_id stored — records without a stored order are
            NEVER touched: there is no order to check Razorpay against)
    fetch Razorpay order (Task 1 client, fetch_order)
        ↓
    Razorpay order created AFTER the expiry cutoff?
        YES → the payment attempt itself is fresh (the stored
              payment_order_id was created after the booking record, e.g. the
              patient only just clicked Pay): KEEP PENDING. This accounts for
              the created_at limitation — the models have no updated_at, so
              Razorpay's own order.created_at is the authoritative "payment
              attempt started at" signal.
        ↓  (order is old)
    fetch all payments for the order (fetch_order_payments)
        ↓
    captured payment exists?
        YES → DO NOT EXPIRE. Route through the EXISTING Task 8 captured
              reconciliation path (WebhookReconciliationService.reconcile_event),
              which re-fetches the payment authoritatively, validates order /
              captured status / amount vs backend billing_amount / currency,
              and performs the SAME atomic mark-paid transition with
              winner-only notification. If that validation does not succeed
              (skipped_* / unmapped outcomes), the booking is NOT expired —
              captured money with failed validation is an uncertain financial
              state, and uncertainty keeps it pending.
        ↓  (no captured payment)
    any payment in an in-flight state (created/authorized/pending/processing)?
        YES → KEEP PENDING (fail-closed: an attempt may still complete —
              Razorpay auto-capture passes through authorized)
        ↓
    any payment in an UNKNOWN state?
        YES → KEEP PENDING (fail-closed on anything unrecognized)
        ↓
    no payments, or every payment failed/refunded (terminal, no money taken)
        → ATOMIC EXPIRY via PaymentRepository.expire_*_pending_payment
          (guarded find_one_and_update; wins only while still pending)

Every Razorpay failure (timeout, 5xx, malformed response, config error)
keeps the booking pending. No API failure can cause an expiry.

Late capture after expiry is safe by construction: the expiry transition
guards on status="pending_payment", so a later captured payment can never
re-write the expired record. The captured evidence stays observable: the
Task 7 WebhookEvent ledger row (event/payment/order ids, received_at), the
record's retained payment_order_id binding, and a prominent warning log
(outcome "late_capture_after_expiry"). No automatic restore, no automatic
refund — financial recovery is future manual tooling, per the Task 9 spec.

created_at semantics (inspected, Task 9 §created_at limitation):
- Appointment.created_at / LaboratoryBooking.created_at are server-side
  booking-creation timestamps (Field(default_factory=datetime.utcnow)).
- A Razorpay order is bound later (at the Pay click), so created_at can be
  OLDER than the payment attempt. The Razorpay order.created_at freshness
  check above handles exactly that distinction. No updated_at is added.

Execution model: there is NO scheduler infrastructure in this application
(inspected: no background tasks, no worker libraries). This service exposes
one deterministic entry point, reconcile_stale_pending_payments(), and a
minimal asyncio background loop started from the FastAPI startup event
(start_background_loop). The loop sleeps FIRST (never blocks startup), runs
every STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS, swallows all errors.
No Celery / Redis / external queue / infinite polling without intervals is
introduced.

Expiry policy status (Task 9 policy remediation): NO expiry duration has
been approved by the product owner. Automatic expiry is therefore DISABLED
by default — PAYMENT_RECONCILIATION_ENABLED defaults to False and
PAYMENT_PENDING_EXPIRY_MINUTES defaults to None (no duration is chosen by
the implementation). With the default configuration,
reconcile_stale_pending_payments() performs NO expiry and NO Razorpay
calls; the reconciliation decision logic remains implemented and fully
tested, available for explicit future activation by setting BOTH
configuration values.

Logging policy: only non-sensitive identifiers (truncated record/order/
payment ids, outcome codes). Never the raw Razorpay payload, never
credentials, never patient PII.

Notifications: expiry creates NO notification (the existing cancel
notification mechanism is coupled to patient/admin-driven
AppointmentService.update_appointment / LaboratoryService.update_booking_status
flows and their semantics do not fit a silent system expiry of an unpaid
booking — documented decision). Payment-success notifications occur ONLY
through the reused Task 8 winner-only path when a captured payment
legitimately transitions the record to paid.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.core.config import settings
from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpayRequestError,
    fetch_order,
    fetch_order_payments,
)
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.laboratory_booking_repository import (
    LaboratoryBookingRepository,
)
from app.repositories.payment_repository import PaymentRepository
from app.services.webhook_reconciliation_service import (
    WebhookReconciliationService,
)

logger = logging.getLogger(__name__)

# Background loop cadence. A fixed, documented interval — not a busy poll.
STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS = 15 * 60

# Razorpay payment statuses that mean money may still move (fail-closed):
# the attempt could still complete, so the booking stays pending.
# - "authorized": money is held and auto-capture configs capture it moments
#   later; this architecture has no capture endpoint (Task 5 decision), but
#   expiring a booking under an authorization hold is exactly the kind of
#   uncertainty Task 9 forbids.
# - "created"/"pending"/"processing": attempt started, not concluded. Rare to
#   see on a genuinely abandoned order; the cost of waiting one more cycle is
#   a delayed expiry, while the cost of expiring a completing payment is a
#   late capture against a cancelled booking.
_IN_FLIGHT_PAYMENT_STATUSES = {"created", "authorized", "pending", "processing"}

# Razorpay payment statuses that conclusively mean NO money was taken.
# ONLY these (or the absence of payments) allow expiry.
_TERMINAL_NO_MONEY_PAYMENT_STATUSES = {"failed", "refunded"}

_CAPTURED_STATUS = "captured"

# Record-level marker written by the Task 9 expiry transitions (existing
# payment_status field, no new state): used to recognize an already-expired
# record when a late captured payment is discovered.
_EXPIRED_PAYMENT_STATUSES = {"expired", "failed"}

# Domain descriptors: everything domain-specific is injected so the decision
# logic is written and tested exactly once. Holders/method NAMES are stored
# (not bound functions) so collaborators resolve at call time — this keeps
# the transitions patchable and guarantees the calls always hit the
# repository modules' current attributes.
_DOMAINS: Dict[str, Dict[str, Any]] = {
    "appointment": {
        "repo": AppointmentRepository,
        "list_name": "list_stale_pending_payments",
        "get_by_order_name": "get_by_order_id",
        "expire_holder": PaymentRepository,
        "expire_name": "expire_appointment_pending_payment",
        "scan_key": "appointments_scanned",
    },
    "laboratory": {
        "repo": LaboratoryBookingRepository,
        "list_name": "list_stale_pending_payments",
        "get_by_order_name": "get_by_order_id",
        "expire_holder": PaymentRepository,
        "expire_name": "expire_laboratory_pending_payment",
        "scan_key": "laboratory_bookings_scanned",
    },
}


class StalePaymentReconciliationService:

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    @staticmethod
    async def reconcile_stale_pending_payments(
        now: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Reconcile every stale pending-payment record in both domains.

        Deterministic and side-effect-safe to run repeatedly: the atomic
        expiry guards make every transition a one-time event, and repeated
        runs simply find nothing left to do.

        Args:
            now: injectable clock (UTC naive, matching app convention) for
                deterministic tests; defaults to datetime.utcnow().

        Returns:
            A summary dict: {"appointments_scanned": n,
            "laboratory_bookings_scanned": n, "<domain>_<outcome>": count,
            ...}. Outcome vocabulary is documented on _reconcile_candidate.

        Policy gate (Task 9 remediation): automatic expiry requires BOTH an
        explicit expiry duration (PAYMENT_PENDING_EXPIRY_MINUTES) and the
        policy switch (PAYMENT_RECONCILIATION_ENABLED=true). With the default
        configuration (disabled, no duration) a run NEVER expires anything —
        it returns {"status": "disabled"} without touching any record. The
        Razorpay-first, fail-closed decision logic itself is unchanged.
        """
        if (
            not settings.PAYMENT_RECONCILIATION_ENABLED
            or settings.PAYMENT_PENDING_EXPIRY_MINUTES is None
        ):
            # Expiry policy disabled or undefined: never expire, never scan,
            # never contact Razorpay. Explicit future activation = setting
            # both values in configuration.
            logger.info(
                "Stale-payment reconciliation is disabled by configuration "
                "(PAYMENT_RECONCILIATION_ENABLED=%s, "
                "PAYMENT_PENDING_EXPIRY_MINUTES=%s) — no expiry performed",
                settings.PAYMENT_RECONCILIATION_ENABLED,
                settings.PAYMENT_PENDING_EXPIRY_MINUTES,
            )
            return {"status": "disabled"}

        now = now or datetime.utcnow()
        cutoff = now - timedelta(minutes=settings.PAYMENT_PENDING_EXPIRY_MINUTES)

        summary: Counter = Counter()
        for domain, parts in _DOMAINS.items():
            try:
                candidates = await getattr(parts["repo"], parts["list_name"])(cutoff)
            except Exception:
                # Candidate discovery failure must never crash a run (the
                # background loop would also survive this, but a failed scan
                # must not abort the OTHER domain's scan).
                logger.exception(
                    "Stale-payment scan failed for domain=%s", domain
                )
                continue
            summary[parts["scan_key"]] = len(candidates)
            for record in candidates:
                outcome = await StalePaymentReconciliationService._reconcile_candidate(
                    domain, record, cutoff
                )
                summary[f"{domain}_{outcome}"] += 1

        return dict(summary)

    # ------------------------------------------------------------------
    # Per-candidate decision flow
    # ------------------------------------------------------------------

    @staticmethod
    async def _reconcile_candidate(
        domain: str,
        record: Any,
        cutoff: datetime,
    ) -> str:
        """Run the Razorpay-first decision flow for one stale candidate.

        Returns a fine-grained outcome string (summarized by the caller):

          reconciled                    — captured payment found and the
                                          EXISTING Task 8 path confirmed the
                                          record paid (winner-only notify)
          already_paid                  — captured payment found; record was
                                          already legitimately paid
          late_capture_after_expiry     — captured payment found; record was
                                          already expired (never restored —
                                          evidence preserved + warning)
          expired                       — no captured/in-flight/unknown
                                          payment; atomic expiry WON
          transition_lost               — expiry guard did not match
                                          (verify/webhook/another expiry won
                                          the race first, or a transient DB
                                          error); nothing mutated
          kept_order_fresh              — Razorpay order itself is newer than
                                          the cutoff (attempt still live)
          kept_razorpay_unreachable     — timeout/5xx/config/API error
          kept_malformed_order          — unusable Razorpay order response
          kept_captured_unverifiable    — captured payment without a usable id
          kept_captured_validation_failed — captured money exists but the
                                          Task 8 validation did not confirm
                                          (amount/currency/order/unmapped…)
          kept_payment_in_flight        — a payment attempt may still complete
          kept_unknown_payment_state    — unrecognized Razorpay state
          kept_reconciliation_error     — unexpected error in the reused path

        Every "kept_*" outcome leaves the record EXACTLY as it was.
        """
        parts = _DOMAINS[domain]
        order_id = (getattr(record, "payment_order_id", None) or "").strip()
        record_label = f"{domain}={str(getattr(record, 'id', '?'))[:8]}"

        # ---- 1. Razorpay order truth (authoritative attempt timestamp) ----
        try:
            order = await asyncio.to_thread(fetch_order, order_id)
        except RazorpayConfigError:
            logger.error(
                "Stale-payment reconciliation: Razorpay configuration missing "
                "(%s) — keeping record pending",
                record_label,
            )
            return "kept_razorpay_unreachable"
        except RazorpayRequestError:
            # Timeout / 5xx / network error: fail CLOSED.
            logger.warning(
                "Stale-payment reconciliation: Razorpay unreachable (%s) — "
                "keeping record pending",
                record_label,
            )
            return "kept_razorpay_unreachable"

        if not isinstance(order, dict) or not order.get("id"):
            logger.warning(
                "Stale-payment reconciliation: malformed Razorpay order "
                "response (%s) — keeping record pending",
                record_label,
            )
            return "kept_malformed_order"

        try:
            order_created_epoch = int(order.get("created_at"))
        except (TypeError, ValueError):
            logger.warning(
                "Stale-payment reconciliation: Razorpay order missing "
                "created_at (%s) — keeping record pending",
                record_label,
            )
            return "kept_malformed_order"

        # ---- 2. Fresh order ⇒ live attempt ⇒ keep pending ----------------
        # The domain record's created_at predates the Pay click; Razorpay's
        # own order.created_at is the authoritative attempt-start signal.
        cutoff_epoch = cutoff.replace(tzinfo=timezone.utc).timestamp()
        if order_created_epoch > cutoff_epoch:
            return "kept_order_fresh"

        # ---- 3. Payments on the order ------------------------------------
        try:
            payments = await asyncio.to_thread(fetch_order_payments, order_id)
        except (RazorpayConfigError, RazorpayRequestError):
            logger.warning(
                "Stale-payment reconciliation: Razorpay order-payments "
                "lookup failed (%s) — keeping record pending",
                record_label,
            )
            return "kept_razorpay_unreachable"

        if not isinstance(payments, list):
            # fetch_order_payments already normalizes envelopes; a non-list
            # here is an unexpected shape → fail closed.
            logger.warning(
                "Stale-payment reconciliation: unexpected order-payments "
                "response (%s) — keeping record pending",
                record_label,
            )
            return "kept_unknown_payment_state"

        # ---- 4. Captured money ⇒ never expire; reuse Task 8 path ---------
        captured = [
            p for p in payments
            if isinstance(p, dict) and p.get("status") == _CAPTURED_STATUS
        ]
        if captured:
            payment_id = next(
                (
                    str(p.get("id")).strip()
                    for p in captured
                    if isinstance(p, dict) and p.get("id")
                ),
                None,
            )
            if not payment_id:
                logger.warning(
                    "Stale-payment reconciliation: captured payment without "
                    "usable id (%s) — keeping record pending",
                    record_label,
                )
                return "kept_captured_unverifiable"

            # THE existing captured-payment reconciliation path (Task 8): it
            # re-fetches the payment authoritatively, validates order binding,
            # captured status, amount vs backend billing_amount, and currency,
            # then performs the SAME atomic mark-paid transition with
            # winner-only notification. No second implementation here.
            try:
                outcome = await WebhookReconciliationService.reconcile_event(
                    event_type="payment.captured",
                    payment_id=payment_id,
                    order_id=order_id,
                )
            except Exception:
                logger.exception(
                    "Stale-payment reconciliation: reused captured path "
                    "raised (%s) — keeping record pending",
                    record_label,
                )
                return "kept_reconciliation_error"

            if outcome in ("reconciled_appointment", "reconciled_laboratory"):
                return "reconciled"
            if outcome == "already_paid":
                # Distinguish a legitimately-paid record from an EXPIRED one:
                # the Task 8 atomic guard reports both as "transition lost".
                fresh = None
                try:
                    fresh = await getattr(parts["repo"], parts["get_by_order_name"])(order_id)
                except Exception:
                    fresh = None
                fresh_status = getattr(fresh, "payment_status", None)
                if fresh is not None and fresh_status in _EXPIRED_PAYMENT_STATUSES:
                    logger.warning(
                        "Stale-payment reconciliation: LATE CAPTURED PAYMENT "
                        "for an expired record (domain=%s, order=%s, "
                        "payment=%s) — record NOT restored; captured "
                        "evidence preserved in webhook ledger and this log "
                        "for manual reconciliation",
                        domain,
                        order_id[:12],
                        payment_id[:12],
                    )
                    return "late_capture_after_expiry"
                return "already_paid"
            # skipped_* / unmapped: captured money exists but validation did
            # not confirm it → uncertain financial state → DO NOT expire.
            logger.warning(
                "Stale-payment reconciliation: captured payment failed "
                "validation (domain=%s, order=%s, outcome=%s) — keeping "
                "record pending for manual reconciliation",
                domain,
                order_id[:12],
                outcome,
            )
            return "kept_captured_validation_failed"

        # ---- 5. No captured money: in-flight / unknown ⇒ fail closed ------
        for payment in payments:
            if not isinstance(payment, dict):
                # Unexpected list element shape → fail closed.
                return "kept_unknown_payment_state"
            status = payment.get("status")
            if status in _IN_FLIGHT_PAYMENT_STATUSES:
                return "kept_payment_in_flight"
            if status not in _TERMINAL_NO_MONEY_PAYMENT_STATUSES:
                # Unknown/unrecognized state → fail closed.
                return "kept_unknown_payment_state"

        # ---- 6. Safe to expire: no money taken, order past its window ----
        return await StalePaymentReconciliationService._expire(
            domain, parts, record, order_id
        )

    # ------------------------------------------------------------------
    # Atomic expiry
    # ------------------------------------------------------------------

    @staticmethod
    async def _expire(
        domain: str,
        parts: Dict[str, Any],
        record: Any,
        order_id: str,
    ) -> str:
        """Perform the atomic guarded expiry for one domain.

        The repository transition (find_one_and_update guarded on the record
        id + stored order id + pending state) wins ONLY while the record is
        still pending. If a verification/webhook transition — or a concurrent
        expiry — moved the record first, the guard does not match, nothing is
        mutated, and the already-paid state remains intact.
        """
        expire_fn: Callable[..., Awaitable[Optional[Dict[str, Any]]]] = getattr(
            parts["expire_holder"], parts["expire_name"]
        )
        updated = await expire_fn(str(record.id), order_id)
        if updated is not None:
            logger.info(
                "Stale-payment reconciliation: expired %s=%s (order=%s) — "
                "slot released",
                domain,
                str(record.id)[:8],
                order_id[:12],
            )
            return "expired"
        # Lost the race (verification/webhook/expiry confirmed or moved the
        # record first) or a transient database error: nothing mutated.
        logger.info(
            "Stale-payment reconciliation: expiry transition lost (%s, "
            "order=%s) — record left untouched",
            domain,
            order_id[:12],
        )
        return "transition_lost"

    # ------------------------------------------------------------------
    # Minimal execution mechanism (no scheduler infrastructure)
    # ------------------------------------------------------------------

    _background_task: Optional["asyncio.Task"] = None

    @staticmethod
    def start_background_loop() -> Optional["asyncio.Task"]:
        """Start the periodic reconciliation loop from the app startup event.

        Lifecycle behavior (explicitly documented per the Task 9 spec):
        - Opt-IN via PAYMENT_RECONCILIATION_ENABLED=true (default False —
          no expiry policy has been approved by the product owner).
        - The loop sleeps BEFORE its first run, so startup is never blocked
          by Razorpay calls.
        - Runs reconcile_stale_pending_payments() every
          STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS (15 minutes).
        - Every run error is logged and swallowed; the loop survives.
        - Idempotent: calling twice never creates a second loop.
        - No Celery/Redis/external queue; a plain asyncio task tied to the
          app's own event loop.
        """
        if (
            not settings.PAYMENT_RECONCILIATION_ENABLED
            or settings.PAYMENT_PENDING_EXPIRY_MINUTES is None
        ):
            logger.info(
                "Stale-payment reconciliation is disabled by configuration "
                "(PAYMENT_RECONCILIATION_ENABLED=%s, "
                "PAYMENT_PENDING_EXPIRY_MINUTES=%s) — loop not started",
                settings.PAYMENT_RECONCILIATION_ENABLED,
                settings.PAYMENT_PENDING_EXPIRY_MINUTES,
            )
            return None

        existing = StalePaymentReconciliationService._background_task
        if existing is not None and not existing.done():
            return existing

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "Stale-payment reconciliation: no running event loop — "
                "background reconciliation not started"
            )
            return None

        StalePaymentReconciliationService._background_task = loop.create_task(
            StalePaymentReconciliationService._reconciliation_loop()
        )
        logger.info(
            "Stale-payment reconciliation background loop started "
            "(interval=%ss, expiry_threshold=%smin)",
            STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS,
            settings.PAYMENT_PENDING_EXPIRY_MINUTES,
        )
        return StalePaymentReconciliationService._background_task

    @staticmethod
    async def _reconciliation_loop() -> None:
        # Sleep FIRST: never run Razorpay calls during application startup.
        await asyncio.sleep(STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS)
        while True:
            try:
                summary = (
                    await StalePaymentReconciliationService
                    .reconcile_stale_pending_payments()
                )
                logger.info(
                    "Stale-payment reconciliation run summary: %s", summary
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                # The loop must never die from a bad run.
                logger.exception("Stale-payment reconciliation run failed")
            await asyncio.sleep(STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS)


# Backwards-compatible alias for the Task 9 spec's suggested name.
reconcile_stale_pending_payments = (
    StalePaymentReconciliationService.reconcile_stale_pending_payments
)
