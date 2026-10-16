"""
Refund repository (Phase 4, Task 12).

ALL refund mutations go through single atomic MongoDB operations. Every
state transition includes the EXPECTED CURRENT STATE in its update filter —
the same guarded find_one_and_update discipline this codebase uses for
payment transitions (PaymentRepository). No load → modify → save path
exists for refund state; a second worker/request can never claim the same
refund because the database guard lets exactly one filter match.

State machine (only these transitions exist; terminal states match
nothing):

    requested ──(claim_for_processing)──> processing
    processing ──(mark_completed)──> completed
    processing ──(mark_failed)──> failed
    requested ──(cancel)──> cancelled

Razorpay is never called from here — this module only reads and writes the
payment_refunds collection.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.models.payment_refund import PaymentRefund, REFUND_STATUSES

# Reconciliation metadata bound (Task 18): the longest outcome category
# that may ever be persisted on a refund record. Categories are short
# allowlisted codes (see refund_reconciliation_service), so this is a
# defensive ceiling, not a truncation that normally triggers.
RECONCILIATION_OUTCOME_MAX_LEN = 64


class PaymentRefundRepository:

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    @staticmethod
    async def get_by_id(refund_id: str) -> Optional[PaymentRefund]:
        """Fetch a refund record by its own id (Beanie document id)."""
        try:
            oid = PydanticObjectId(refund_id)
        except Exception:
            return None
        return await PaymentRefund.get(oid)

    @staticmethod
    async def get_active_by_payment_id(payment_id: str) -> Optional[PaymentRefund]:
        """Fetch the ACTIVE (requested/processing) refund for a payment.

        The partial unique index guarantees at most one exists, so
        find_one is exact. Returns None when no active refund exists —
        including when a previous refund reached a terminal state
        (completed/failed/cancelled), which is what permits a future
        retry after terminal failure.
        """
        if not payment_id:
            return None
        return await PaymentRefund.find_one(
            {
                "payment_id": payment_id,
                "status": {"$in": ["requested", "processing"]},
            }
        )

    @staticmethod
    async def list_reconcilable_refunds(
        limit: int = 50,
    ) -> List[PaymentRefund]:
        """List refunds eligible for reconciliation (Task 16).

        Eligibility is exactly status == "processing". The persisted
        Razorpay identity is deliberately NOT part of the filter: a
        processing refund whose identity was lost with an ambiguous
        response is still reconcilable — the reconciliation service
        re-discovers the identity from Razorpay's own refund list for the
        stored payment_id (never by guessing, never across unrelated
        payments, never by re-refunding). Requested and terminal records
        are excluded: terminal outcomes always stand, and requested
        records have not been claimed yet.

        Read-only. It never mutates state, never calls Razorpay, and
        never creates anything. Bounded by `limit` so one run cannot
        issue an unbounded number of Razorpay lookups.
        """
        if limit <= 0:
            return []
        # Oldest-updated first (plain field-name sort — Beanie-safe and
        # covered by existing index fields; no new index required).
        return await PaymentRefund.find(
            {"status": "processing"}
        ).sort("updated_at").limit(limit).to_list()

    @staticmethod
    async def get_processing_by_payment_id(payment_id: str) -> Optional[PaymentRefund]:
        """Fetch the PROCESSING refund for a payment, if one exists.

        Reconciliation aid for the Task 13 execution layer: a refund that
        hit an ambiguous Razorpay outcome stays `processing`; this lookup
        lets a later operator/internal flow find it by payment_id without
        creating anything. The partial unique index guarantees at most one
        active (requested/processing) record per payment.
        """
        if not payment_id:
            return None
        return await PaymentRefund.find_one(
            {"payment_id": payment_id, "status": "processing"}
        )

    @staticmethod
    async def get_by_razorpay_refund_id(razorpay_refund_id: str) -> Optional[PaymentRefund]:
        """Fetch the refund record holding a given Razorpay refund id.

        The partial unique index (uniq_razorpay_refund_id_when_present)
        guarantees at most one record can ever hold a non-null value, so
        find_one is exact. Returns None when the identifier is unclaimed —
        including when it is empty/None (a null identity matches no
        record by definition of the partial index).
        """
        rid = (razorpay_refund_id or "").strip()
        if not rid:
            return None
        return await PaymentRefund.find_one(
            {"razorpay_refund_id": rid}
        )

    @staticmethod
    async def attach_razorpay_refund_id(
        refund_id: str,
        razorpay_refund_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Atomically attach Razorpay's refund identity to a PROCESSING
        refund that does not yet carry one (Task 14).

        Semantic contract:

            processing + no refund id
                    ↓
            processing + razorpay_refund_id

        The single guarded find_one_and_update refuses by construction:
          - completed / failed / cancelled refunds (status filter is
            "processing"-only — terminal states can never be re-identified),
          - requested refunds (not yet claimed — no Razorpay call can
            have produced an identity for them),
          - OVERWRITING an existing identity (razorpay_refund_id must be
            null/missing to match — a persisted identity is immutable),
            including the same-value rewrite (identity is write-once).

        Duplicate Razorpay identities across DIFFERENT records are
        rejected by the partial unique index: the second attach raises
        DuplicateKeyError, which this method surfaces as None — callers
        MUST treat None as an invariant violation and fail closed (never
        mark the refund completed without a durably persisted identity).

        Args:
            refund_id: the PaymentRefund document id.
            razorpay_refund_id: the rfnd_... identifier EXACTLY as
                Razorpay returned it — never fabricated, never caller-
                supplied. An empty value is refused without a write.

        Returns the updated document dict when THIS call attached the
        identity; None on any refusal (wrong state, identity already
        present, duplicate identity race, or transient DB error).
        """
        rid = (razorpay_refund_id or "").strip()
        if not rid:
            # Fail closed: never write an empty/absent identity.
            return None
        coll = PaymentRefund.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {
                    "_id": PydanticObjectId(refund_id),
                    "status": "processing",
                    "razorpay_refund_id": None,
                },
                {
                    "$set": {
                        "razorpay_refund_id": rid,
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            # Another record already holds this Razorpay refund id: the
            # unique partial index enforced the one-refund-per-identity
            # invariant. Callers fail closed.
            return None
        except PyMongoError:
            return None

    @staticmethod
    async def get_completed_by_payment_id(payment_id: str) -> Optional[PaymentRefund]:
        """Fetch the COMPLETED refund for a payment, if one exists.

        A completed refund is terminal and the service-level anti-
        double-refund gate blocks any new record for the same payment
        afterwards, so at most one can ever exist (find_one is exact).
        Used to answer "has this payment already been refunded?" — never
        to fabricate success.
        """
        if not payment_id:
            return None
        return await PaymentRefund.find_one(
            {"payment_id": payment_id, "status": "completed"}
        )

    @staticmethod
    async def get_by_payment_id(payment_id: str) -> Optional[PaymentRefund]:
        """Most-recent refund record for a payment, active or terminal.

        Audit/inspection helper. The find+sort+to_list form follows the
        codebase's proven Beanie 2.1.0 pattern (FindMany sort), avoiding
        the FindOne-chaining quirks noted in laboratory_booking_repository.
        """
        if not payment_id:
            return None
        rows = await PaymentRefund.find(
            {"payment_id": payment_id}
        ).sort(-PaymentRefund.created_at).to_list()
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Creation (atomic by construction)
    # ------------------------------------------------------------------

    @staticmethod
    async def create_refund(refund: PaymentRefund) -> Optional[PaymentRefund]:
        """Insert a new refund record.

        The partial unique index (uniq_active_refund_per_payment) is the
        authoritative idempotency guard: under two concurrent create
        requests for the same payment, exactly one insert wins and the
        loser raises DuplicateKeyError. There is deliberately NO
        application-level find-then-insert protection here — the
        database enforces the invariant.

        Returns the inserted record, or None on a transient database
        error (callers re-read to find the winner).
        """
        try:
            return await refund.insert()
        except PyMongoError:
            # Includes DuplicateKeyError (lost the idempotency race) and
            # transient failures; callers re-read state either way.
            return None

    # ------------------------------------------------------------------
    # Atomic state transitions (expected state in every filter)
    # ------------------------------------------------------------------

    @staticmethod
    async def claim_for_processing(refund_id: str) -> Optional[Dict[str, Any]]:
        """Atomically claim requested → processing.

        Matches ONLY a document in state "requested". Two concurrent
        claims: exactly one find_one_and_update matches; the other sees
        the status already changed and gets None. A refund in any other
        state (processing/completed/failed/cancelled) never matches.

        Returns the updated document dict when THIS call performed the
        transition, None otherwise (lost race, wrong state, or transient
        database error).
        """
        coll = PaymentRefund.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {"_id": PydanticObjectId(refund_id), "status": "requested"},
                {
                    "$set": {
                        "status": "processing",
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    @staticmethod
    async def mark_completed(refund_id: str) -> Optional[Dict[str, Any]]:
        """Atomically mark processing → completed.

        RESERVED for the future Razorpay refund integration task: only
        that task may call this, and only after Razorpay itself confirms
        the refund. Task 12 ships the operation but has NO caller that
        can fabricate a success.

        Matches ONLY a document in state "processing" (never requested,
        never terminal). Returns the updated document dict when THIS
        call performed the transition, None otherwise.
        """
        coll = PaymentRefund.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {"_id": PydanticObjectId(refund_id), "status": "processing"},
                {
                    "$set": {
                        "status": "completed",
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    @staticmethod
    async def mark_failed(refund_id: str) -> Optional[Dict[str, Any]]:
        """Atomically mark processing → failed (terminal).

        Reserved for the future Razorpay refund integration task as the
        outcome when Razorpay refuses or errors the refund. Matches ONLY
        a document in state "processing". A `failed` refund can never
        silently become `completed`: no later transition filter matches
        "failed".
        """
        coll = PaymentRefund.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {"_id": PydanticObjectId(refund_id), "status": "processing"},
                {
                    "$set": {
                        "status": "failed",
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    @staticmethod
    async def cancel_if_requested(refund_id: str) -> Optional[Dict[str, Any]]:
        """Atomically cancel requested → cancelled (terminal).

        Only permitted from "requested": a refund that has already been
        claimed for processing reflects a real-world operation in flight
        and cannot be cancelled from this path (that is the future
        integration's `failed` outcome, not a cancellation).
        """
        coll = PaymentRefund.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {"_id": PydanticObjectId(refund_id), "status": "requested"},
                {
                    "$set": {
                        "status": "cancelled",
                        "updated_at": datetime.utcnow(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    # ------------------------------------------------------------------
    # Validation helper (test/integration support)
    # ------------------------------------------------------------------

    @staticmethod
    async def record_reconciliation_attempt(
        refund_id: str,
        outcome_category: str,
    ) -> bool:
        """Atomically record reconciliation metadata on a PROCESSING
        refund (Phase 4, Task 18).

        Single guarded update — no load → modify → save:

            processing  →  processing
                           + last_reconciliation_attempt_at = now
                           + last_reconciliation_error = <bounded category>
                           + updated_at = now (queue rotation)

        The status filter is "processing" ONLY, so the write can never
        touch a record another worker has terminalized (completed /
        failed / cancelled are immutable, Task 12 contract) and can never
        revive or alter a terminal outcome. The outcome_category is a
        short, allowlisted internal code chosen by the reconciliation
        service (never a raw exception message, never a Razorpay API
        description, never a payload); it is defensively truncated here
        to RECONCILIATION_OUTCOME_MAX_LEN so a caller mistake can never
        persist an unbounded string.

        Returns True when THIS call wrote the metadata, False otherwise
        (record missing/terminal, or transient database error). Callers
        treat the return value as informational only — reconciliation
        outcomes never depend on bookkeeping.
        """
        category = (outcome_category or "").strip()
        if not category:
            # Fail closed: never persist an empty category.
            return False
        category = category[:RECONCILIATION_OUTCOME_MAX_LEN]
        now = datetime.utcnow()
        coll = PaymentRefund.get_pymongo_collection()
        try:
            result = await coll.update_one(
                {
                    "_id": PydanticObjectId(refund_id),
                    "status": "processing",
                },
                {
                    "$set": {
                        "last_reconciliation_attempt_at": now,
                        "last_reconciliation_error": category,
                        "updated_at": now,
                    }
                },
            )
            return bool(getattr(result, "modified_count", 0))
        except PyMongoError:
            return False

    @staticmethod
    async def touch_processing(refund_id: str) -> Optional[Dict[str, Any]]:
        """Refresh updated_at on a PROCESSING refund (no status change).

        Used by the Task 13 execution layer to timestamp an ambiguous
        Razorpay outcome while deliberately PRESERVING the `processing`
        state: the refund may have been accepted by Razorpay and must
        stay claimed for reconciliation. The guarded update matches only
        a document still in `processing` — a concurrently terminalized
        record is never touched.
        """
        coll = PaymentRefund.get_pymongo_collection()
        try:
            return await coll.find_one_and_update(
                {"_id": PydanticObjectId(refund_id), "status": "processing"},
                {"$set": {"updated_at": datetime.utcnow()}},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError:
            return None

    @staticmethod
    def validate_status_transition(current: str, target: str) -> bool:
        """Pure helper: is current → target a permitted refund transition?

        Encodes the same state machine the atomic filters enforce. Used
        by tests and by future integration code to double-check intent
        before attempting a guarded write.
        """
        allowed = {
            "requested": {"processing", "cancelled"},
            "processing": {"completed", "failed"},
        }
        return (
            current in REFUND_STATUSES
            and target in REFUND_STATUSES
            and target in allowed.get(current, set())
        )
