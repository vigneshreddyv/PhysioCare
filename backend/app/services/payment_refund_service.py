"""
Refund service (Phase 4, Task 12).

Internal foundation for Razorpay refunds/recovery. Creates and manages
refund RECORDS only:

- It NEVER calls Razorpay — no refund API, no payment fetch, no network
  call of any kind. Authoritative facts (payment_id, payment_order_id,
  amount) come exclusively from the backend's own domain records
  (Appointment / LaboratoryBooking), which were themselves only ever
  populated through the verified Razorpay payment flow (Tasks 4/8).
- It NEVER mutates the appointment/booking. Creating a refund record
  does not touch billing_status, payment_status, status, payment_id, or
  payment_order_id. `requested`/`processing` do NOT mean the Razorpay
  refund succeeded.
- It is IDEMPOTENT: repeated requests for the same payment return the
  existing active refund record rather than creating another one (the
  partial unique index is the concurrent authority; the service re-reads
  after a lost insert race).

REFUND POLICY (documented, not invented):
- FULL-refund requests only. The product defines no partial-refund
  semantics (no partial-refund workflow, no per-payment refund tracking,
  no remainder-handling rules), so implementing partial refunds here
  would be inventing policy. The refund amount is derived entirely from
  the domain record's authoritative billing_amount. There is no
  client-supplied amount parameter at all — over-refunding via client
  input is structurally impossible.
- INR only — every booking amount in this system is INR.
- A payment is refundable only when the domain record is genuinely in
  its paid state per existing domain semantics (billing_status "paid" +
  payment_status "success" + status "confirmed" + a stored online
  payment reference). Offline-marked, failed, expired, cancelled, and
  unpaid records are not refundable.

AUTHORIZATION MODEL (fail-closed):
- Refunds are INTERNAL. There is deliberately NO HTTP endpoint in Task
  12 — the Task 11 security suite pins this
  (test_no_refund_surface_exists forbids any refund route). Only
  server-side code (a future admin refund workflow / the future
  Razorpay refund integration) may call this service.
- Ownership is an explicit, required gate: the caller must pass
  `owner_patient_id` — the patient profile id whose record is being
  refunded — and the service independently verifies the loaded domain
  object belongs to that patient. A mismatch is answered with the same
  404 as a missing record (no existence leak), exactly like the
  existing LaboratoryService.get_booking_by_id(booking_id, patient_id)
  convention. A caller cannot "forget" ownership: the parameter is
  mandatory.
- A patient can therefore never reach another patient's payment through
  this service: any patient-scoped path must supply that patient's own
  profile id, and any other patient's record is indistinguishable from
  a nonexistent one. No code path here can mark a refund completed or
  mark a payment refunded — those transitions are not even offered.
"""
import asyncio
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpayRefundOutcome,
    RazorpayRequestError,
    create_refund,
    fetch_refund,
)
from app.models.appointment import Appointment
from app.models.laboratory_booking import LaboratoryBooking
from app.models.payment_refund import (
    PaymentRefund,
    REFUND_CURRENCY,
    REFUNDABLE_PAYABLE_TYPES,
    REFUND_STATUSES,
)
from app.repositories.payment_refund_repository import PaymentRefundRepository

logger = logging.getLogger(__name__)

# Bounded audit reason (no arbitrary frontend metadata storage).
MAX_REASON_LENGTH = 256


class PaymentRefundService:

    # ------------------------------------------------------------------
    # Public API (internal only — no HTTP route calls this in Task 12)
    # ------------------------------------------------------------------

    @staticmethod
    async def request_refund(
        payable_type: str,
        payable_id: str,
        requested_by: str,
        owner_patient_id: str,
        reason: str = "refund_requested",
    ) -> PaymentRefund:
        """Create (or reuse) the refund record for a domain object's payment.

        Args:
            payable_type: "appointment" or "laboratory".
            payable_id: the domain object's id.
            requested_by: the authenticated USER id requesting the
                refund — supplied by the caller from its authenticated
                principal, never from client input. Recorded for audit.
            owner_patient_id: the patient profile id whose record this
                is. The service independently verifies the loaded domain
                object belongs to this patient; any other patient's
                record is answered 404 (indistinguishable from missing —
                no existence leak).
            reason: bounded audit note (truncated to
                MAX_REASON_LENGTH). Free of metadata and secrets by
                policy — the service stores it verbatim, never renders
                it unsafely.

        Returns the existing active refund record when one already
        exists for the payment (idempotent reuse), otherwise the newly
        created "requested" record.

        All failure modes raise HTTPException with safe, non-leaking
        details (no credentials, no raw database errors, no
        cross-patient existence leaks).
        """
        if payable_type not in REFUNDABLE_PAYABLE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid refundable type",
            )
        if not requested_by or not str(requested_by).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A requesting user is required",
            )
        if not owner_patient_id or not str(owner_patient_id).strip():
            # Fail closed: no ownership scope -> no operation.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Record not found",
            )
        if not reason or not str(reason).strip():
            reason = "refund_requested"
        reason = str(reason).strip()[:MAX_REASON_LENGTH]

        # 1+2. Load the domain object under the ownership gate.
        payable = await PaymentRefundService._load_payable(
            payable_type, payable_id, owner_patient_id
        )

        # 3. Authoritative payment references (stored on the domain
        # record — never from client input).
        payment_id = payable.get("payment_id")
        payment_order_id = payable.get("payment_order_id")

        if not payment_id or not payment_order_id:
            # Missing payment/order id: never paid through the online
            # flow — nothing to refund.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This record has no online payment to refund",
            )

        # 4. Refundable/paid state per existing domain semantics.
        PaymentRefundService._require_refundable_state(payable)

        # ANTI-DOUBLE-REFUND GATE. A refund that already reached
        # "completed" is money already returned: no new refund record may
        # ever be created for that payment (fail closed — this is a
        # permanent rejection, not a reuse, because reusing a completed
        # record as the answer to a NEW refund request would look like
        # success). Retry-after-terminal-failure semantics are
        # deliberately limited to "failed"/"cancelled": those terminal
        # states mean no money moved, so a fresh "requested" record is a
        # legitimate new attempt (the partial unique index excludes
        # terminal statuses for exactly this reason).
        completed = await PaymentRefundRepository.get_completed_by_payment_id(
            payment_id
        )
        if completed is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This payment has already been refunded",
            )

        # 5+6+7. Authoritative amount (backend-derived, full refund).
        amount_paise = PaymentRefundService._authoritative_refund_amount_paise(
            payable.get("billing_amount"), payable_type
        )

        # 8+9. Idempotent creation. The partial unique index
        # (uniq_active_refund_per_payment) is the concurrency authority;
        # this reuse-check is only the fast path, never the sole guard.
        existing = await PaymentRefundRepository.get_active_by_payment_id(payment_id)
        if existing is not None:
            return existing

        refund = PaymentRefund(
            payable_type=payable_type,
            payable_id=str(payable["_id"]),
            payment_id=payment_id,
            payment_order_id=payment_order_id,
            amount=amount_paise,
            currency=REFUND_CURRENCY,
            status="requested",
            reason=reason,
            requested_by=str(requested_by),
        )

        created = await PaymentRefundRepository.create_refund(refund)
        if created is not None:
            return created

        # Lost the concurrent-create race (DuplicateKeyError inside the
        # repository — the unique index chose a winner) or a transient
        # database failure. Re-read: reuse the winner when one exists,
        # otherwise surface a safe retryable error.
        return await PaymentRefundService._resolve_lost_create(payment_id)

    # ------------------------------------------------------------------
    # Race resolution
    # ------------------------------------------------------------------

    @staticmethod
    async def _resolve_lost_create(payment_id: str) -> PaymentRefund:
        """Re-read after a lost create. Returns the winning record when
        one exists; raises a safe retryable 503 otherwise (no raw
        database error, no secrets)."""
        existing = await PaymentRefundRepository.get_active_by_payment_id(payment_id)
        if existing is not None:
            return existing
        logger.error(
            "Refund record for payment %s could not be created or found",
            payment_id[:12],
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not record the refund request. Please try again.",
        )

    # ------------------------------------------------------------------
    # Domain loading + ownership (fail-closed)
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_payable(
        payable_type: str, payable_id: str, owner_patient_id: str
    ) -> dict:
        """Load the domain object and return a normalized fact dict.

        Raises 404 "Record not found" — identically, deliberately — for:
          a nonexistent object, a malformed id, an object belonging to a
          DIFFERENT patient than `owner_patient_id`, or a missing
          ownership scope. Cross-patient access is therefore
          indistinguishable from a missing record: no existence leak.

        The domain object's stored payment_id / payment_order_id /
        billing_amount are the authoritative values for the refund.
        """
        if payable_type == "appointment":
            appt = await PaymentRefundService._get_appointment(payable_id)
            if (
                appt is None
                or str(appt.patient_id) != str(owner_patient_id)
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Record not found",
                )
            return {
                "_id": str(appt.id),
                "payment_id": appt.payment_id,
                "payment_order_id": appt.payment_order_id,
                "billing_amount": appt.billing_amount,
                "billing_status": appt.billing_status,
                "payment_status": appt.payment_status,
                "status": appt.status,
            }

        booking = await PaymentRefundService._get_laboratory_booking(payable_id)
        if (
            booking is None
            or str(booking.patient_id) != str(owner_patient_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Record not found",
            )
        return {
            "_id": str(booking.id),
            "payment_id": booking.payment_id,
            "payment_order_id": booking.payment_order_id,
            "billing_amount": booking.billing_amount,
            "billing_status": booking.billing_status,
            "payment_status": booking.payment_status,
            "status": booking.status,
        }

    @staticmethod
    async def _get_appointment(payable_id: str) -> Optional[Appointment]:
        try:
            return await Appointment.get(PydanticObjectId(payable_id))
        except Exception:
            return None

    @staticmethod
    async def _get_laboratory_booking(payable_id: str) -> Optional[LaboratoryBooking]:
        try:
            return await LaboratoryBooking.get(PydanticObjectId(payable_id))
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Domain semantics
    # ------------------------------------------------------------------

    @staticmethod
    def _require_refundable_state(payable: dict) -> None:
        """Confirm the domain record is genuinely in its paid state.

        Existing domain vocabulary (identical for both domains after the
        verified Razorpay transitions): billing_status "paid",
        payment_status "success", status "confirmed".

        Anything else — pending, failed, expired, cancelled, or an
        offline-marked "paid" without a captured online payment — is not
        refundable: no refund against money the backend does not
        affirmatively know was captured. (Offline records are also
        already rejected earlier by the payment_id/order_id presence
        gate.)
        """
        if (
            payable.get("billing_status") == "paid"
            and payable.get("payment_status") == "success"
            and payable.get("status") == "confirmed"
        ):
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This record is not in a refundable paid state",
        )

    @staticmethod
    def _authoritative_refund_amount_paise(billing_amount, label: str) -> int:
        """Convert the backend-stored rupee amount to integer paise.

        Exact-money discipline identical to PaymentService:
        Decimal(str(x)) → quantize 2dp (ROUND_HALF_UP) → integer paise.
        No float arithmetic anywhere. Zero/negative/non-numeric amounts
        are rejected (fail closed).
        """
        if billing_amount is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {label} record does not have a valid billing amount",
            )
        try:
            d = Decimal(str(billing_amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {label} record does not have a valid billing amount",
            )
        if d <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {label} record does not have a valid billing amount",
            )
        paise = int(d * 100)
        if paise <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {label} record does not have a valid billing amount",
            )
        return paise

    # ------------------------------------------------------------------
    # Pure validation helpers (used by tests and future integration code)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_currency(currency: str) -> bool:
        """INR-only. The future Razorpay integration must re-confirm the
        currency against Razorpay's own payment record before refunding."""
        return currency == REFUND_CURRENCY

    @staticmethod
    def validate_refund_amount(requested_paise: int, authoritative_paise: int) -> bool:
        """A refund must be positive and must not exceed the
        authoritative amount (general over-refund invariant; the
        full-refund policy additionally means equality)."""
        return 0 < requested_paise <= authoritative_paise

    @staticmethod
    def is_terminal(status_value: str) -> bool:
        """True for completed/failed/cancelled — no transition may start
        from a terminal state."""
        return status_value in ("completed", "failed", "cancelled")

    @staticmethod
    def valid_status(status_value: str) -> bool:
        return status_value in REFUND_STATUSES

    # ==================================================================
    # Razorpay refund execution (Phase 4, Task 13)
    # ==================================================================

    # Razorpay refund statuses that prove SUCCESS per the Refunds API
    # contract (razorpay.com/docs/api/refunds): "processed" is the final
    # success state. A "pending" response means Razorpay is still
    # attempting the refund — money has been committed to a refund
    # attempt but the outcome is not yet final, so it is treated as
    # ambiguous (the record stays `processing` for reconciliation),
    # never as completed and never as failed.
    _RAZORPAY_REFUND_SUCCESS_STATUSES = ("processed",)
    _RAZORPAY_REFUND_PENDING_STATUSES = ("pending",)

    @staticmethod
    async def execute_refund(refund_id: str) -> PaymentRefund:
        """Execute a requested refund against Razorpay's refund API.

        INTERNAL ONLY — there is deliberately no HTTP route to this
        method (Task 11's no-refund-surface invariant is pinned by
        tests). A future admin workflow / operations tool calls this
        from server-side code with the refund record's own id.

        Execution flow (all-or-nothing per stage):

            load refund record
                ↓ (must be in state "requested")
            coherence gate (self-consistent persisted record)
                ↓
            ATOMIC claim requested → processing
                ↓ (only the claim winner continues)
            Razorpay refund API (stored payment_id + stored amount)
                ↓
            validate Razorpay response against the persisted record
                ↓
            completed (proven success) | failed (proven rejection)
                | (ambiguous → processing preserved)

        Concurrency: exactly one execution wins the atomic claim; a
        concurrent attempt for the same refund observes state !=
        "requested" and returns without issuing a second Razorpay call.

        Idempotency: executing an already-terminal refund never
        re-contacts Razorpay — completed/failed/cancelled records are
        returned as-is (their outcome stands).

        Outcome semantics (the critical distinctions):

        - DEFINITIVE Razorpay rejection (4xx-class: invalid payment,
          refund not possible, validation failure) → processing →
          failed. No money moved; retrying cannot help.
        - AMBIGUOUS outcome (timeout / connection error / 5xx /
          malformed response / Razorpay "pending" status) → the refund
          STAYS `processing`. Razorpay may have accepted the refund even
          though no usable proof arrived; claiming `failed` here could
          double-refund a retry, claiming `completed` could lie. The
          record is timestamped (touch_processing) and a safe 409-style
          signal is raised for the caller to reconcile.
        - Proven success ("processed" + matching payment/amount/
          currency) → processing → completed.

        There is NO automatic retry mechanism: a retry that blindly re-
        POSTs the refund after a timeout risks a second real refund.
        Ambiguous refunds require Razorpay-side reconciliation (see
        reconcile_ambiguous_refund).

        Raises HTTPException (safe details only):
            404 — refund record not found.
            409 — refund not in an executable state (already claimed/
                  terminal), OR ambiguous outcome requiring
                  reconciliation, OR Razorpay reported a pending refund.
            503 — Razorpay not configured.
        """
        refund = await PaymentRefundRepository.get_by_id(refund_id)
        if refund is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Refund not found",
            )

        # Terminal/claimed records are simply returned — their outcome
        # (or an in-flight claim by another worker) stands. No Razorpay
        # call is ever made for them.
        if refund.status != "requested":
            return refund

        # Coherence gate: the persisted record must be internally
        # consistent BEFORE any claim or Razorpay interaction. A corrupt
        # record fails safely here without contacting Razorpay.
        PaymentRefundService._require_coherent_refund(refund)

        # Atomic claim. The loser of this race (or a late duplicate
        # execution) never calls Razorpay.
        claimed = await PaymentRefundRepository.claim_for_processing(refund_id)
        if claimed is None:
            # Someone else claimed it (or a transient DB error). Re-read
            # for the current truth; never blind-retry the claim (a
            # transient failure could actually have succeeded).
            fresh = await PaymentRefundRepository.get_by_id(refund_id)
            if fresh is not None:
                return fresh
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not claim the refund for execution. Please try again.",
            )

        # ---------------- Razorpay call (claim winner only) ----------
        try:
            rp_refund = await asyncio.to_thread(
                create_refund,
                refund.payment_id,
                refund.amount,
            )
        except RazorpayConfigError:
            logger.error("Razorpay configuration missing during refund execution")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service is not available",
            )
        except RazorpayRequestError as exc:
            if RazorpayRefundOutcome.DEFINITIVE in str(exc):
                # Proven rejection: Razorpay said no. No money moved.
                await PaymentRefundRepository.mark_failed(refund_id)
                fresh = await PaymentRefundRepository.get_by_id(refund_id)
                return fresh if fresh is not None else refund
            # AMBIGUOUS: Razorpay may have accepted the refund. Preserve
            # `processing` (timestamp the attempt) and report that
            # reconciliation is required. NEVER mark failed on ambiguity.
            logger.error(
                "Refund %s execution ended ambiguously; reconciliation "
                "required (payment=%s)",
                refund_id,
                str(refund.payment_id)[:8],
            )
            await PaymentRefundRepository.touch_processing(refund_id)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The refund outcome is unclear. The refund remains "
                    "in processing and must be reconciled with Razorpay "
                    "before any retry."
                ),
            )

        # ---------------- Razorpay response validation ----------------
        validation = PaymentRefundService._validate_razorpay_refund_response(
            rp_refund,
            expected_payment_id=refund.payment_id,
            expected_amount_paise=refund.amount,
        )

        # Task 15 §3: if an identity is somehow ALREADY persisted on this
        # record (an execution re-entered after a prior claim), the
        # response's refund id must MATCH it — a different identity is an
        # invariant violation, fail closed without completing and without
        # overwriting. (In the normal requested→claimed flow the identity
        # is null here and the attach below establishes it.)
        if validation in ("success", "pending"):
            persisted_identity = str(
                getattr(refund, "razorpay_refund_id", "") or ""
            ).strip()
            rp_refund_id = str(rp_refund.get("id") or "").strip()
            if persisted_identity and rp_refund_id != persisted_identity:
                logger.error(
                    "Refund %s got a Razorpay refund id that differs from "
                    "the persisted identity; completion refused "
                    "(payment=%s)",
                    refund_id,
                    str(refund.payment_id)[:8],
                )
                await PaymentRefundRepository.touch_processing(refund_id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The Razorpay refund id in the response does not "
                        "match the identity persisted for this refund. "
                        "The refund remains in processing for manual "
                        "review — it was NOT marked completed."
                    ),
                )

        if validation == "success":
            # ORDERING REQUIREMENT (Task 14): Razorpay's refund identity
            # must be durably attached BEFORE the refund can be considered
            # completed — "completed without a persisted refund id" must
            # be structurally impossible. attach_razorpay_refund_id is an
            # atomic guarded write (processing + no identity → processing
            # + identity) whose partial unique index also rejects the
            # identifier colliding with ANOTHER refund record.
            rp_refund_id = str(rp_refund.get("id") or "").strip()
            attached = await PaymentRefundRepository.attach_razorpay_refund_id(
                refund_id, rp_refund_id
            )
            if attached is None:
                # FAIL CLOSED on identity failure: a conflict (another
                # record already holds this Razorpay refund id), a
                # concurrent identity write, or a transient database
                # failure. In any of these cases the refund must NOT be
                # marked completed — the invariant violation is surfaced
                # for manual review while the record stays processing.
                logger.error(
                    "Refund %s could not durably persist Razorpay refund "
                    "identity; completion refused (payment=%s)",
                    refund_id,
                    str(refund.payment_id)[:8],
                )
                await PaymentRefundRepository.touch_processing(refund_id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The Razorpay refund identity could not be "
                        "recorded for this refund. The refund remains "
                        "in processing and requires manual review — it "
                        "was NOT marked completed."
                    ),
                )
            # Identity durably persisted; only now may the refund be
            # completed. Two completion attempts cannot both win (the
            # atomic filter matches only "processing").
            await PaymentRefundRepository.mark_completed(refund_id)
            fresh = await PaymentRefundRepository.get_by_id(refund_id)
            return fresh if fresh is not None else refund

        if validation == "pending":
            # Razorpay accepted the request but the refund is still being
            # processed there. Committed-but-unproven: stays processing
            # for reconciliation. Not completed (not proven), not failed
            # (not rejected). NOTE: the identity is deliberately NOT
            # persisted here — Razorpay may still reverse a pending
            # refund, and reconciliation re-fetches the (possibly final)
            # entity by that id.
            logger.info(
                "Refund %s accepted by Razorpay but still pending; "
                "reconciliation required",
                refund_id,
            )
            await PaymentRefundRepository.touch_processing(refund_id)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Razorpay accepted the refund but it is still "
                    "processing. The refund must be reconciled with "
                    "Razorpay before completion."
                ),
            )

        # validation == "ambiguous": malformed/invalid response. Not
        # proof of success AND not proof of rejection. Razorpay may have
        # accepted the refund (e.g. a truncated 2xx body). Preserve
        # processing — never completed from an incomplete response.
        logger.error(
            "Refund %s got an unusable Razorpay response; reconciliation "
            "required (payment=%s)",
            refund_id,
            str(refund.payment_id)[:8],
        )
        await PaymentRefundRepository.touch_processing(refund_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The refund response from Razorpay could not be "
                "validated. The refund remains in processing and must "
                "be reconciled with Razorpay."
            ),
        )

    # ------------------------------------------------------------------
    # Execution internals
    # ------------------------------------------------------------------

    @staticmethod
    def _require_coherent_refund(refund: PaymentRefund) -> None:
        """Fail closed when the persisted refund record is not internally
        coherent. Called BEFORE the claim and any Razorpay interaction.

        All fields are the backend's own persisted values — the caller
        supplies only the refund record id.
        """
        if getattr(refund, "payable_type", None) not in REFUNDABLE_PAYABLE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refund record is not coherent (invalid payable type)",
            )
        payable_id = str(getattr(refund, "payable_id", "") or "")
        if not payable_id.strip():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refund record is not coherent (missing payable id)",
            )
        payment_id = str(getattr(refund, "payment_id", "") or "")
        if not payment_id.strip():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refund record is not coherent (missing payment id)",
            )
        order_id = str(getattr(refund, "payment_order_id", "") or "")
        if not order_id.strip():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refund record is not coherent (missing order id)",
            )
        amount = getattr(refund, "amount", None)
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refund record is not coherent (invalid amount)",
            )
        if str(getattr(refund, "currency", "") or "") != REFUND_CURRENCY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refund record is not coherent (invalid currency)",
            )

    @staticmethod
    def _validate_razorpay_refund_response(
        rp_refund: dict,
        expected_payment_id: str,
        expected_amount_paise: int,
    ) -> str:
        """Classify a Razorpay refund response against the persisted
        refund record.

        "HTTP 200" is NOT proof of success. Every one of these must hold
        before "success" is returned:
          - the response is a dict with a refund id
          - response payment_id == the stored payment_id
          - response amount == the stored refund amount (integer paise)
          - response currency == INR
          - response status == "processed" (Razorpay's final success
            state per the Refunds API contract)

        Returns:
            "success"   — proven success (completed may follow).
            "pending"   — Razorpay accepted but refund still processing
                          there (stays processing here).
            "ambiguous" — malformed/invalid/unproven (stays processing;
                          never completed, never failed).
        """
        if not isinstance(rp_refund, dict) or not rp_refund.get("id"):
            return "ambiguous"

        rp_status = rp_refund.get("status")
        if rp_status in PaymentRefundService._RAZORPAY_REFUND_PENDING_STATUSES:
            # Even a well-shaped pending response must still match the
            # persisted facts before it is trusted as "our refund".
            if (
                str(rp_refund.get("payment_id") or "") == str(expected_payment_id)
                and rp_refund.get("amount") == expected_amount_paise
                and rp_refund.get("currency") == REFUND_CURRENCY
            ):
                return "pending"
            return "ambiguous"

        if rp_status not in PaymentRefundService._RAZORPAY_REFUND_SUCCESS_STATUSES:
            # Unknown/unrecognized status: unproven — ambiguous. (A
            # Razorpay "failed" refund status arrives as a definitive
            # API rejection path or is reconciled; it is never silently
            # mapped to completed here.)
            return "ambiguous"

        # Proven-success status: now require exact agreement with the
        # persisted record on every financial fact.
        if str(rp_refund.get("payment_id") or "") != str(expected_payment_id):
            return "ambiguous"
        if rp_refund.get("amount") != expected_amount_paise:
            return "ambiguous"
        if rp_refund.get("currency") != REFUND_CURRENCY:
            return "ambiguous"

        return "success"

    # ------------------------------------------------------------------
    # Reconciliation (durable identity — Phase 4, Task 14)
    # ------------------------------------------------------------------

    @staticmethod
    async def reconcile_ambiguous_refund(
        refund_id: str,
        razorpay_refund_id: Optional[str] = None,
    ) -> PaymentRefund:
        """Resolve a `processing` refund using its Razorpay refund identity.

        Task 14 normal path — NO caller-supplied identity needed:

            load PaymentRefund
                ↓ require status == processing
                ↓ require persisted razorpay_refund_id
            fetch THAT refund from Razorpay's API (persisted id)
                ↓ execution-grade validation (payment/amount/currency/status)
            completed  |  remain processing

        Task 13 fallback (unchanged semantics, narrowed scope): an
        operator may still supply the Razorpay refund id from Razorpay's
        dashboard/support for a processing record whose identity was
        never persisted (e.g. a Task 13-era record, or a pending-then-
        lost response). The supplied identity is accepted ONLY when it
        belongs to THIS record:

        - it is validated against Razorpay's response for this record's
          payment_id/amount/currency BEFORE being attached, and
        - it is attached atomically only to a processing record with no
          persisted identity — never overwriting one, never shared with
          another record (the partial unique index rejects a colliding
          identity; the refund then fails closed, uncompleted).

        The supplied identity is never treated as trusted by itself: if
        Razorpay's own response for it does not match this record's
        persisted facts, nothing is attached and the record stays
        processing.

        For a processing record with NO persisted identity and NO
        supplied one: do NOT guess, do NOT search unrelated refunds, do
        NOT create another refund — return the record untouched; the
        caller must obtain the identity from Razorpay first.

        Only a `processing` record may be reconciled; requested/terminal
        records are returned untouched — terminal outcomes always stand.
        """
        refund = await PaymentRefundRepository.get_by_id(refund_id)
        if refund is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Refund not found",
            )
        if refund.status != "processing":
            # requested / terminal records are not reconciliation targets.
            # A completed refund reconciled twice is a no-op here.
            return refund

        PaymentRefundService._require_coherent_refund(refund)

        supplied_id = (razorpay_refund_id or "").strip()
        persisted_id = str(getattr(refund, "razorpay_refund_id", "") or "").strip()

        if persisted_id:
            # Durable identity path (Task 14): use EXACTLY the persisted
            # identifier. A caller-supplied value that disagrees with the
            # persisted one is an identity violation — rejected, never
            # allowed to redirect the lookup.
            if supplied_id and supplied_id != persisted_id:
                logger.error(
                    "Refund %s reconciliation supplied a Razorpay refund id "
                    "that differs from the persisted identity (payment=%s)",
                    refund_id,
                    str(refund.payment_id)[:8],
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The supplied Razorpay refund id does not match "
                        "the identity persisted for this refund. The "
                        "refund remains in processing."
                    ),
                )
            lookup_id = persisted_id
        elif supplied_id:
            # Operator fallback (Task 13 semantics, Task 14 scope): the
            # supplied id is NOT trusted on its own — it is validated
            # against Razorpay's response for THIS record's facts before
            # anything is attached. A mismatched identity is rejected
            # outright (no write, no state change).
            try:
                probe = await asyncio.to_thread(
                    fetch_refund,
                    refund.payment_id,
                    supplied_id,
                )
            except RazorpayConfigError:
                logger.error(
                    "Razorpay configuration missing during refund reconciliation"
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Payment service is not available",
                )
            except RazorpayRequestError:
                # Ambiguous or definitive lookup failure: the record
                # stays processing either way (a definitive "no such
                # refund" is itself an anomaly that requires human
                # review — the refund POST may still have landed).
                await PaymentRefundRepository.touch_processing(refund_id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The refund could not be reconciled with "
                        "Razorpay. It remains in processing."
                    ),
                )

            probe_validation = (
                PaymentRefundService._validate_razorpay_refund_response(
                    probe,
                    expected_payment_id=refund.payment_id,
                    expected_amount_paise=refund.amount,
                )
            )
            if probe_validation not in ("success", "pending"):
                # Razorpay's entity for the supplied id does not belong
                # to this record. Nothing is attached; no state change.
                logger.error(
                    "Refund %s reconciliation: Razorpay refund %s does not "
                    "match this record's payment/amount (payment=%s)",
                    refund_id,
                    supplied_id[:12],
                    str(refund.payment_id)[:8],
                )
                await PaymentRefundRepository.touch_processing(refund_id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The supplied Razorpay refund id does not "
                        "correspond to this refund record. The refund "
                        "remains in processing."
                    ),
                )

            # Identity belongs to this record: attach it atomically.
            # Only a processing record with no identity can match; the
            # partial unique index rejects a colliding identity on
            # another record.
            attached = await PaymentRefundRepository.attach_razorpay_refund_id(
                refund_id, supplied_id
            )
            if attached is None:
                # Lost an identity race, record moved state, or — the
                # invariant case — the identity is already claimed by
                # another refund. Fail closed: uncompleted.
                logger.error(
                    "Refund %s could not durably persist the supplied "
                    "Razorpay refund identity; completion refused "
                    "(payment=%s)",
                    refund_id,
                    str(refund.payment_id)[:8],
                )
                await PaymentRefundRepository.touch_processing(refund_id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The Razorpay refund identity could not be "
                        "recorded for this refund. The refund remains "
                        "in processing and requires manual review — it "
                        "was NOT marked completed."
                    ),
                )
            lookup_id = supplied_id
        else:
            # No persisted identity, none supplied: reconciliation is NOT
            # possible without guessing. Leave the record untouched.
            logger.info(
                "Refund %s has no persisted Razorpay refund identity; "
                "reconciliation requires the identifier from Razorpay",
                refund_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This refund has no persisted Razorpay refund id to "
                    "reconcile with. It remains in processing; obtain "
                    "the refund identifier from Razorpay and retry the "
                    "reconciliation."
                ),
            )

        # Final authoritative read of the identified Razorpay refund.
        try:
            rp_refund = await asyncio.to_thread(
                fetch_refund,
                refund.payment_id,
                lookup_id,
            )
        except RazorpayConfigError:
            logger.error("Razorpay configuration missing during refund reconciliation")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service is not available",
            )
        except RazorpayRequestError:
            # Ambiguous or definitive lookup failure: the record stays
            # processing either way (a definitive "no such refund" from
            # Razorpay is itself an anomaly that requires human review,
            # not an automatic failed marking — the refund POST may still
            # have landed).
            await PaymentRefundRepository.touch_processing(refund_id)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The refund could not be reconciled with Razorpay. "
                    "It remains in processing."
                ),
            )

        validation = PaymentRefundService._validate_razorpay_refund_response(
            rp_refund,
            expected_payment_id=refund.payment_id,
            expected_amount_paise=refund.amount,
        )
        # §7 identity match: Razorpay's entity must BE the persisted
        # identity — a matching-looking refund under a different id is
        # not proof this record's refund succeeded.
        if validation == "success" and (
            str(rp_refund.get("id") or "") != str(lookup_id)
        ):
            validation = "ambiguous"
        if validation == "pending" and (
            str(rp_refund.get("id") or "") != str(lookup_id)
        ):
            validation = "ambiguous"
        if validation == "success":
            # Task 14 ordering guarantee: the identity is already durably
            # persisted here (both paths attach/verify it before this
            # point), so completing now can never yield "completed without
            # a persisted refund id".
            await PaymentRefundRepository.mark_completed(refund_id)
            fresh = await PaymentRefundRepository.get_by_id(refund_id)
            return fresh if fresh is not None else refund
        if validation == "pending":
            await PaymentRefundRepository.touch_processing(refund_id)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Razorpay reports the refund is still processing. "
                    "The refund remains in processing here."
                ),
            )
        # ambiguous: response did not match the persisted record.
        await PaymentRefundRepository.touch_processing(refund_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The Razorpay refund response did not match this refund "
                "record. The refund remains in processing for manual "
                "review."
            ),
        )
