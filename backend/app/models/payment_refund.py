"""
Internal refund/recovery record (Phase 4, Task 12).

A durable, idempotent INTERNAL representation of a refund/recovery operation
against an already-captured Razorpay payment on an appointment or laboratory
booking. Task 12 establishes ONLY the data + state foundation:

- No Razorpay refund API is called anywhere in this task. `processing`
  means "a future integration may attempt the Razorpay refund" — it is NOT
  a success signal. Only a future Razorpay refund integration task may
  transition a refund to `completed`, and only after Razorpay itself
  confirms the refund. No code path in this task can fabricate success.
- Creating a refund record NEVER mutates the appointment/booking: not
  billing_status, not payment_status, not status, not payment_id, not
  payment_order_id. A refund record is a request ledger, not a payment
  state change.

PRIVACY / MINIMALITY POLICY (same discipline as the Task 7 webhook ledger):
- No Razorpay credentials or webhook secrets are ever stored.
- No raw Razorpay payloads, signatures, or payment instrument data (card /
  UPI / bank) are stored.
- No arbitrary frontend metadata is stored. The fields below are the
  minimum needed to represent the operation and to let a future
  integration locate the payment it must refund.

STATUS MACHINE (strictly constrained vocabulary, terminal states marked *):

    requested ──(atomic claim)──> processing ──(atomic result)──> completed*
        │                                                        ↘ failed*
        └──(atomic cancel, only while requested)──> cancelled*

Transitions happen exclusively through the atomic guarded updates in
PaymentRefundRepository (expected current state in every filter). Terminal
states (completed, failed, cancelled) are immutable — no transition filter
matches them, so no code path can revive or overwrite a terminal refund.
"""

from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pymongo import IndexModel
from pydantic import Field

# Explicit, minimal status vocabulary. No speculative states: this task
# defines exactly the lifecycle it can enforce atomically.
REFUND_STATUSES = ("requested", "processing", "completed", "failed", "cancelled")

# States from which no further transition is possible.
TERMINAL_REFUND_STATUSES = ("completed", "failed", "cancelled")

# The two payable domain types a refund can target (validated at the
# service boundary; the model stores the value verbatim).
REFUNDABLE_PAYABLE_TYPES = ("appointment", "laboratory")

# The refund is INR-only by product semantics (all booking amounts are INR).
REFUND_CURRENCY = "INR"


class PaymentRefund(Document):
    # --- What is being refunded ---------------------------------------
    # "appointment" or "laboratory" (REFUNDABLE_PAYABLE_TYPES).
    payable_type: Indexed(str)

    # The referenced domain object's id. Kept as a string rather than a
    # PydanticObjectId: one field serves both domain collections, and the
    # service validates the referenced object's existence + ownership
    # before any record is created.
    payable_id: Indexed(str)

    # --- Which Razorpay payment is being refunded ---------------------
    # Both copied from the backend's authoritative domain record at
    # creation time — NEVER from client input — and never mutated after.
    payment_id: Indexed(str)
    payment_order_id: str

    # --- Financial facts (backend-authoritative at creation) ----------
    # Refund amount in INR, stored as integer paise (the same exact-money
    # representation the Razorpay order pipeline uses). Derived ONLY from
    # the domain record's billing_amount via the shared Decimal/paise
    # conversion; full-refund semantics (see below).
    amount: int

    # Fixed to INR by product semantics; rejected otherwise at the service
    # boundary. Stored (not hardcoded at read time) so the record is
    # self-describing for future reconciliation tooling.
    currency: str = REFUND_CURRENCY

    # --- Lifecycle -----------------------------------------------------
    # One of REFUND_STATUSES; transitions only via the atomic repository
    # operations.
    status: str = "requested"

    # Free-text reason for audit. Bounded; never rendered unsafely.
    reason: str

    # The admin/doctor user id who requested this refund. Set by the
    # service from the authenticated principal — never client input.
    requested_by: Indexed(str)

    # --- Razorpay-side identity (Phase 4, Task 14) ---------------------
    # The refund identifier Razorpay itself assigned (rfnd_...). Absent
    # (None/missing) until Razorpay supplies one — it is NEVER fabricated
    # locally, NEVER accepted from client input (request_refund does not
    # take it), and NEVER overwritten once persisted. It is attached
    # only by the atomic repository operation from a validated Razorpay
    # response, and its uniqueness across refund records is enforced by
    # the partial unique index below (the database is the authority —
    # never an application-level check-then-insert).
    razorpay_refund_id: Optional[str] = None

    # --- Reconciliation observability (Phase 4, Task 18) ---------------
    # Server-side operational metadata ONLY — written exclusively by the
    # atomic, processing-guarded repository operation
    # (PaymentRefundRepository.record_reconciliation_attempt); never
    # accepted from client input; never read by any HTTP surface (Task
    # 12: refunds have no HTTP surface). These fields answer exactly two
    # operator questions about a STUCK (processing) refund — "when was
    # reconciliation last attempted?" and "why is it still ambiguous?" —
    # without adding any refund state: the status vocabulary above is
    # unchanged.
    #
    # last_reconciliation_attempt_at is refreshed on every reconciliation
    # attempt that leaves the refund `processing` (guarded update — it
    # can never touch a record another worker has terminalized).
    #
    # last_reconciliation_error holds a BOUNDED SANITIZED OUTCOME
    # CATEGORY (an allowlisted short code such as "kept_razorpay_ambiguous"
    # or "kept_mismatch", truncated to 64 characters by the repository)
    # — never a raw exception message, never a Razorpay API description,
    # never a payload, never credentials, never customer/card/UPI/bank
    # information. It is deliberately NOT an error log: detailed,
    # credential-free diagnostics live in server logs only.
    last_reconciliation_attempt_at: Optional[datetime] = None
    last_reconciliation_error: Optional[str] = None

    # --- Timestamps (server-side, same convention as other models) -----
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "payment_refunds"
        indexes = [
            # The authoritative idempotency constraint: at most ONE active
            # refund per Razorpay payment. Partial unique over
            # payment_id where the status is still non-terminal — exactly
            # one of {requested, processing} can ever exist for a given
            # payment_id, so two concurrent create requests cannot both
            # insert (MongoDB's unique index decides the winner; the
            # loser receives DuplicateKeyError and reuses the winner's
            # record). Terminal statuses are deliberately EXCLUDED from
            # the partial filter so that, after a refund reaches
            # `failed` or `cancelled`, a future retry (new
            # requested-record for the same payment) remains possible —
            # while a `completed` refund also no longer blocks, the
            # service's own refundable-state gate (paid domain state +
            # amount authority) and the future Razorpay integration's
            # reconciliation remain the guards against over-refunding
            # real money.
            #
            # This mirrors the established partial-unique-index pattern of
            # this codebase (uniq_patient_date_slot on both domain
            # collections, uniq_webhook_event_id for webhook dedupe).
            IndexModel(
                [("payment_id", 1)],
                name="uniq_active_refund_per_payment",
                unique=True,
                partialFilterExpression={
                    "status": {"$in": ["requested", "processing"]}
                },
            ),
            # Operational lookup support: find refunds for a domain object
            # (e.g. "which refunds exist for this booking?"). Non-unique.
            IndexModel(
                [("payable_type", 1), ("payable_id", 1)],
                name="idx_refund_payable",
            ),
            # Razorpay refund identity (Task 14): globally unique WHENEVER
            # the identifier exists. The partial filter (field != null)
            # admits unlimited documents whose razorpay_refund_id is still
            # absent (requested records, ambiguous-in-processing records,
            # and terminal records that predate an identity), while
            # rejecting any TWO records claiming the SAME non-null
            # identifier — one Razorpay refund can never be represented by
            # two PaymentRefund records. MongoDB enforces this at write
            # time; there is no application-level check-then-insert.
            # Task 12/13 indexes are untouched.
            IndexModel(
                [("razorpay_refund_id", 1)],
                name="uniq_razorpay_refund_id_when_present",
                unique=True,
                partialFilterExpression={
                    "razorpay_refund_id": {"$gt": None}
                },
            ),
        ]
