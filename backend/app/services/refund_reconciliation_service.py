"""
Refund reconciliation & recovery driver (Phase 4, Task 16).

Makes AMBIGUOUS refund outcomes recoverable through durable reconciliation
— WITHOUT ever issuing a duplicate Razorpay refund.

Strict division of Razorpay operations (the Task 16 boundary):

    create_refund()          — refund EXECUTION only (Task 13). NEVER
                               reachable from reconciliation.
    fetch_refund()           — authoritative read of an ALREADY-CREATED
                               refund by its identity (Task 14), used
                               through the existing reconciliation
                               operation.
    fetch_payment_refunds()  — authoritative LIST of a payment's refunds
                               (Task 16 discovery): the only way to
                               recover the identity of a refund that was
                               accepted before the response was lost.
                               Read-only; never creates anything.

Recoverability model:

    processing + persisted razorpay_refund_id
        → DIRECT: the existing Task 14 operation re-reads THAT refund,
          validates payment/amount/currency/refund-id/status, and only
          a proven `processed` refund is completed atomically.

    processing + no persisted identity
        → DISCOVERY: Razorpay's own refund list for the stored payment_id
          is read. Exactly ONE refund matching the stored payment id,
          amount, and currency with status `processed` is authoritative:
          its identity is attached atomically and completion follows
          through the SAME Task 14 validate → persist identity → complete
          path. Zero matches, multiple matches, `pending`, or any
          unrecognized status (including `failed`) leaves the refund in
          `processing` — never guessed, never re-created, never failed
          from uncertainty.

Every ambiguous Razorpay outcome preserves `processing` (never `failed`);
reconciliation is idempotent and safe to run repeatedly; the database's
atomic guards decide all races. No refund is ever CREATED here, and no
domain (appointment/booking) record is ever touched.

Scheduling (§6): the application DOES have an established background
mechanism — the Task 9 StalePaymentReconciliationService asyncio loop
(sleep-first, fixed interval, swallow-all-errors, opt-in via settings,
never a second loop). Task 16 reuses EXACTLY that pattern: a minimal loop
over list_reconcilable_refunds() → reconcile_ambiguous_refund(), gated by
REFUND_RECONCILIATION_ENABLED (default False — no automatic reconciliation
policy has been approved; the interval reuses the Task 9 constant, no new
polling policy is invented). With the default configuration nothing runs
automatically; reconcile_refundable_refunds() stays an internal callable.

Observability & recovery (Phase 4, Task 18) — operations only, never
policy:

- Every attempt that leaves a refund `processing` records a bounded,
  sanitized outcome category on the record itself
  (last_reconciliation_attempt_at / last_reconciliation_error, written by
  one atomic processing-guarded update) so an operator can see WHEN a
  stuck refund was last attempted and WHY it is still ambiguous without
  reading server logs. No refund state is added; the vocabulary stays
  requested/processing/completed/failed/cancelled.
- The batch emits a start line and a structured summary line; every
  per-refund outcome is also logged with truncated identifiers only.
- reconcile_single_refund(refund_id) is an internal operator helper that
  accepts ONLY a server-side refund record id — it creates no HTTP
  surface (Task 11's no-refund-surface invariant is pinned by tests).
- scheduler_status() reports disabled/not_started/running for explicit
  operational checks.

Security/logging policy: only truncated record/payment/refund ids and
outcome codes ever reach logs. No secrets, no raw Razorpay response
bodies, no patient PII.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpayRefundOutcome,
    RazorpayRequestError,
    fetch_payment_refunds,
)
from app.repositories.payment_refund_repository import PaymentRefundRepository
from app.services.payment_refund_service import PaymentRefundService

logger = logging.getLogger(__name__)

# Reuse the ESTABLISHED Task 9 cadence — no new polling interval is invented.
REFUND_RECONCILIATION_INTERVAL_SECONDS = 15 * 60

# The SAME Razorpay refund status vocabulary the Task 13/14 validation
# contract recognizes: "processed" (final success) and "pending"
# (committed-but-unproven). No new Razorpay statuses are introduced;
# anything else — including "failed" — is never trusted as an
# authoritative outcome and keeps the refund in `processing`.
_RP_REFUND_TRUSTED_STATUSES = ("processed", "pending")

# ---------------------------------------------------------------------
# Reconciliation OUTCOME vocabulary (Task 18) — observability ONLY.
#
# These classify how a reconciliation attempt ended. They are NEVER
# refund states: the refund status vocabulary is unchanged (requested /
# processing / completed / failed / cancelled), and every `kept_*`
# outcome leaves the refund in `processing` exactly as before. The codes
# are short, allowlisted, sanitized strings — safe to log and to persist
# as last_reconciliation_error (bounded to 64 chars by the repository).
# ---------------------------------------------------------------------
OUTCOME_COMPLETED = "reconciled_completed"            # proven processed → completed
OUTCOME_ALREADY_SETTLED = "already_settled"           # terminal/requested: outcome stands
OUTCOME_KEPT_PENDING = "kept_pending"                 # Razorpay: still pending / still processing
OUTCOME_NO_IDENTITY = "kept_no_identity"              # no persisted id and zero authoritative matches
OUTCOME_MULTIPLE_CANDIDATES = "kept_multiple_candidates"  # ambiguous match set — never guessed
OUTCOME_MISMATCH = "kept_mismatch"                    # authoritative data did not match stored facts
OUTCOME_RZP_AMBIGUOUS = "kept_razorpay_ambiguous"     # timeout/connection/5xx/malformed/pagination
OUTCOME_RZP_DEFINITIVE = "kept_razorpay_definitive"   # Razorpay 4xx-class lookup rejection
OUTCOME_CONFIG_ERROR = "kept_config_error"            # Razorpay not configured
OUTCOME_NOT_FOUND = "not_found"                       # record vanished
OUTCOME_INTERNAL_ERROR = "reconciliation_error"       # unexpected internal error
OUTCOME_SCAN_ERROR = "scan_error"                     # batch scan failed

# Outcomes that leave a refund stuck in `processing`; only these record
# attempt metadata on the record (terminal outcomes need no "why stuck"
# bookkeeping, and the guarded write would refuse them anyway).
_STUCK_OUTCOMES = frozenset({
    OUTCOME_KEPT_PENDING,
    OUTCOME_NO_IDENTITY,
    OUTCOME_MULTIPLE_CANDIDATES,
    OUTCOME_MISMATCH,
    OUTCOME_RZP_AMBIGUOUS,
    OUTCOME_RZP_DEFINITIVE,
    OUTCOME_CONFIG_ERROR,
    OUTCOME_INTERNAL_ERROR,
})


class RefundReconciliationService:

    # ------------------------------------------------------------------
    # Batch entry point (internal callable; safe to run repeatedly)
    # ------------------------------------------------------------------

    @staticmethod
    async def reconcile_refundable_refunds(
        limit: int = 50,
    ) -> Dict[str, int]:
        """Reconcile every `processing` refund in one run.

        Candidates come from the repository-gated scan
        (status == "processing" only — requested and terminal records are
        never reconciled). For each candidate, the reconciliation
        delegates to the EXISTING Task 14 reconcile_ambiguous_refund() —
        the same strict validation, the same atomic mark_completed, the
        same fail-closed semantics. create_refund() is NEVER reachable
        from here.

        Deterministic and idempotent: atomic guards make every completion
        a one-time event; repeated runs find nothing left to do.

        Args:
            limit: maximum candidates examined in one run (bounded so a
                single run cannot issue an unbounded number of Razorpay
                lookups).

        Returns:
            Summary dict with counts per outcome:
              scanned                          — candidates examined
              reconciled_completed             — proven `processed` refunds
                                                 completed via this run
              already_settled                  — terminal/requested record
                                                 found at pre-check (outcome
                                                 stands; zero Razorpay I/O)
              kept_pending                     — Razorpay reports the refund
                                                 still processing there —
                                                 stays processing
              kept_no_identity                 — no persisted identity and
                                                 Razorpay's refund list
                                                 yielded no single
                                                 authoritative match —
                                                 stays processing
              kept_multiple_candidates         — more than one
                                                 authoritative match —
                                                 never guessed — stays
                                                 processing
              kept_mismatch                    — authoritative data did not
                                                 match the stored facts —
                                                 stays processing
              kept_razorpay_ambiguous          — Razorpay lookup failure
                                                 (timeout/5xx/connection/
                                                 malformed/pagination,
                                                 including the collapsed
                                                 definitive case at the
                                                 Task 14 boundary) — stays
                                                 processing
              kept_razorpay_definitive         — Razorpay definitively
                                                 rejected a discovery list
                                                 lookup — stays processing
              not_found                        — record vanished since scan
              reconciliation_error             — unexpected internal error
                                                 (record untouched)
        """
        summary: Counter = Counter()
        logger.info(
            "Refund reconciliation batch started (limit=%s, enabled=%s)",
            limit,
            settings.REFUND_RECONCILIATION_ENABLED,
        )
        try:
            candidates = await PaymentRefundRepository.list_reconcilable_refunds(
                limit=limit
            )
        except Exception:
            # A failed scan must never crash a caller (or the loop).
            logger.exception("Refund reconciliation scan failed")
            summary[OUTCOME_SCAN_ERROR] = 1
            logger.info(
                "Refund reconciliation batch completed (summary=%s)",
                dict(summary),
            )
            return dict(summary)

        summary["scanned"] = len(candidates)

        for refund in candidates:
            refund_id = str(getattr(refund, "id", "") or "")
            if not refund_id:
                continue
            try:
                outcome = await RefundReconciliationService._reconcile_one(
                    refund_id
                )
            except Exception:
                # One bad candidate must never abort the rest of the run.
                logger.exception(
                    "Refund reconciliation: candidate failed (refund=%s)",
                    refund_id[:8],
                )
                outcome = OUTCOME_INTERNAL_ERROR
            summary[outcome] += 1

        logger.info(
            "Refund reconciliation batch completed (summary=%s)",
            dict(summary),
        )
        return dict(summary)

    # ------------------------------------------------------------------
    # Per-candidate reconciliation
    # ------------------------------------------------------------------

    @staticmethod
    async def _reconcile_one(refund_id: str) -> str:
        """Reconcile one refund through the existing Task 14 operation.

        Pre-checks the record's own state BEFORE delegating, so terminal
        records never trigger a Razorpay lookup. Outcome codes (Task 18
        observability vocabulary — never refund states):

          not_found                      — record vanished (no-op)
          already_settled                — terminal/requested record;
                                           outcome stands, ZERO Razorpay I/O
          reconciled_completed           — this run observed the record
                                           completed after a `processing`
                                           pre-check (atomic guards make
                                           exactly one transition)
          kept_pending                   — Razorpay reports the refund is
                                           still pending/processing there
          kept_no_identity               — no persisted identity and zero
                                           authoritative Razorpay matches
          kept_multiple_candidates       — more than one authoritative
                                           match: ambiguous, never guessed
          kept_mismatch                  — authoritative data did not
                                           match the stored facts
          kept_razorpay_ambiguous        — timeout/connection/5xx/
                                           malformed/pagination failure
                                           (also the collapsed definitive
                                           case surfacing through the
                                           Task 14 operation's 409)
          kept_razorpay_definitive       — Razorpay 4xx-class discovery
                                           lookup rejection (anomaly; not
                                           a local failure)
          kept_config_error              — Razorpay not configured
          reconciliation_error           — unexpected error; record untouched

        Every `kept_*` outcome ALSO records bounded, sanitized attempt
        metadata on the still-processing record (Task 18) — one atomic
        processing-guarded update; bookkeeping failure never changes the
        outcome.

        NEVER calls create_refund(); the only Razorpay operations reachable
        here are read-only lookups (fetch_payment_refunds for discovery,
        fetch_refund inside the Task 14 operation).
        """
        try:
            record = await PaymentRefundRepository.get_by_id(refund_id)
        except Exception:
            logger.exception(
                "Refund reconciliation: pre-check failed (refund=%s)",
                refund_id[:8],
            )
            return OUTCOME_INTERNAL_ERROR

        if record is None:
            logger.info(
                "Refund reconciliation: outcome=%s refund=%s",
                OUTCOME_NOT_FOUND,
                refund_id[:8],
            )
            return OUTCOME_NOT_FOUND

        status = getattr(record, "status", None)
        if status != "processing":
            # Terminal outcomes always stand; `requested` records are not
            # reconciliation targets. ZERO Razorpay interaction.
            logger.info(
                "Refund reconciliation: outcome=%s refund=%s status=%s",
                OUTCOME_ALREADY_SETTLED,
                refund_id[:8],
                status,
            )
            return OUTCOME_ALREADY_SETTLED

        identity = str(getattr(record, "razorpay_refund_id", "") or "").strip()
        if identity:
            # Known identity: the existing Task 14 operation re-reads THAT
            # refund from Razorpay and owns the completion transition.
            outcome = await RefundReconciliationService._delegate_reconciliation(
                refund_id
            )
        else:
            # No persisted identity: re-discover it from Razorpay's own
            # refund list for THIS record's stored payment. Never guessed,
            # never searched across unrelated payments, never re-created.
            outcome = await RefundReconciliationService._discover_and_reconcile(
                refund_id, record
            )

        await RefundReconciliationService._record_attempt_outcome(
            refund_id, outcome
        )
        logger.info(
            "Refund reconciliation: outcome=%s refund=%s payable=%s/%s "
            "payment=%s identity=%s",
            outcome,
            refund_id[:8],
            getattr(record, "payable_type", "?"),
            str(getattr(record, "payable_id", ""))[:8],
            str(getattr(record, "payment_id", ""))[:8],
            identity[:12] if identity else "-",
        )
        return outcome

    # ------------------------------------------------------------------
    # Delegation (single source of state transitions)
    # ------------------------------------------------------------------

    @staticmethod
    async def _delegate_reconciliation(
        refund_id: str,
        supplied_id: Optional[str] = None,
    ) -> str:
        """Run the EXISTING Task 14 reconciliation operation and classify
        its outcome. This is the ONLY path by which a refund can reach
        `completed`: validate → persist identity → atomic completion all
        live inside reconcile_ambiguous_refund(); nothing is duplicated
        here.

        `supplied_id` (discovery path only) is the identity Razorpay's own
        refund list returned for this record. It is NOT trusted on its
        own — the Task 14 operation re-fetches it and validates it against
        the persisted payment/amount/currency before attaching anything.
        """
        try:
            result = await PaymentRefundService.reconcile_ambiguous_refund(
                refund_id, supplied_id
            )
        except RazorpayConfigError:
            logger.error(
                "Refund reconciliation: Razorpay configuration missing "
                "(refund=%s) — keeping processing",
                refund_id[:8],
            )
            return OUTCOME_CONFIG_ERROR
        except RazorpayRequestError as exc:
            # Timeout / 5xx / network failure on a lookup: fail closed —
            # the refund stays processing, never failed, never re-created.
            # The DEFINITIVE/AMBIGUOUS taxonomy from the client boundary
            # is preserved verbatim in the outcome code.
            logger.warning(
                "Refund reconciliation: Razorpay lookup failed "
                "(refund=%s, class=%s) — keeping processing",
                refund_id[:8],
                "definitive" if RazorpayRefundOutcome.DEFINITIVE
                in str(exc) else "ambiguous",
            )
            if RazorpayRefundOutcome.DEFINITIVE in str(exc):
                return OUTCOME_RZP_DEFINITIVE
            return OUTCOME_RZP_AMBIGUOUS
        except Exception as exc:
            code = getattr(exc, "status_code", None)
            if code == 404:
                # The record vanished between the pre-check and the
                # operation's own load.
                return OUTCOME_NOT_FOUND
            if code == 503:
                # The Task 14 operation maps a missing Razorpay
                # configuration to 503.
                return OUTCOME_CONFIG_ERROR
            if code == 409:
                # The Task 14 operation signals "remains processing" with
                # a safe 409. Its detail text is a stable contract (pinned
                # by the Task 14 tests); the driver classifies the outcome
                # from it — observability only, the refund stays
                # processing in every case:
                #   "still processing" → Razorpay reports the refund
                #                        pending there (the benign reason).
                #   "could not be reconciled with Razorpay" → Razorpay
                #                        lookup failure. The operation
                #                        collapses its AMBIGUOUS/DEFINITIVE
                #                        taxonomy into this one 409, so
                #                        both surface as
                #                        kept_razorpay_ambiguous here;
                #                        DEFINITIVE lookup rejections are
                #                        distinguished individually
                #                        (kept_razorpay_definitive) on the
                #                        discovery path, where the driver
                #                        performs the lookup itself.
                #   anything else      → validation mismatch / identity
                #                        conflict / attach failure.
                detail = str(getattr(exc, "detail", "") or "").lower()
                if "still processing" in detail:
                    return OUTCOME_KEPT_PENDING
                if "could not be reconciled with razorpay" in detail:
                    return OUTCOME_RZP_AMBIGUOUS
                return OUTCOME_MISMATCH
            # Anything else is unexpected — log for operators, record
            # untouched.
            logger.exception(
                "Refund reconciliation: unexpected error (refund=%s)",
                refund_id[:8],
            )
            return OUTCOME_INTERNAL_ERROR

        status_after = getattr(result, "status", None)
        if status_after == "completed":
            # The pre-check confirmed this record was `processing` before
            # delegation; a completed result means the record reached
            # `completed` via the guarded transition (this run or a
            # concurrent worker — exactly one transition exists).
            logger.info(
                "Refund reconciliation: completed refund=%s",
                refund_id[:8],
            )
            return OUTCOME_COMPLETED
        if status_after == "processing":
            # The operation ran and returned without terminalizing — the
            # refund remains processing (e.g. pending on Razorpay).
            return OUTCOME_KEPT_PENDING
        # Any other status means another worker terminalized the record
        # concurrently; that outcome stands and needs no reconciliation.
        return OUTCOME_ALREADY_SETTLED

    # ------------------------------------------------------------------
    # Identity discovery (processing records without a persisted id)
    # ------------------------------------------------------------------

    @staticmethod
    async def _discover_and_reconcile(refund_id: str, record) -> str:
        """Recover a processing refund whose Razorpay identity was lost.

        Reads Razorpay's authoritative refund list for the record's STORED
        payment id (never a caller-supplied payment id). Exactly one
        refund matching the stored payment id, amount, and currency with
        status `processed` is handed to the Task 14 operation as the
        discovered identity (which re-validates it end to end before
        attaching and completing). Everything else — zero matches,
        multiple matches, `pending`, unrecognized statuses, lookup
        failures — keeps the refund in `processing`.
        """
        payment_id = str(getattr(record, "payment_id", "") or "").strip()
        amount = getattr(record, "amount", None)
        currency = str(getattr(record, "currency", "") or "").strip()
        if (
            not payment_id
            or not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount <= 0
            or not currency
        ):
            # Incoherent record: never guess, never look anything up.
            logger.error(
                "Refund reconciliation: refund=%s is not coherent for "
                "identity discovery — keeping processing",
                refund_id[:8],
            )
            return OUTCOME_NO_IDENTITY

        try:
            refunds = await asyncio.to_thread(
                fetch_payment_refunds, payment_id
            )
        except RazorpayConfigError:
            logger.error(
                "Refund reconciliation: Razorpay configuration missing "
                "during identity discovery (refund=%s) — keeping processing",
                refund_id[:8],
            )
            return OUTCOME_CONFIG_ERROR
        except RazorpayRequestError as exc:
            # Timeout / connection failure / 5xx / malformed response /
            # pagination anomaly: uncertainty is never converted into
            # failure. DEFINITIVE vs AMBIGUOUS from the client boundary
            # is preserved verbatim in the outcome code.
            logger.warning(
                "Refund reconciliation: Razorpay refund list lookup failed "
                "(refund=%s, class=%s) — keeping processing",
                refund_id[:8],
                "definitive" if RazorpayRefundOutcome.DEFINITIVE
                in str(exc) else "ambiguous",
            )
            await RefundReconciliationService._touch_processing(refund_id)
            if RazorpayRefundOutcome.DEFINITIVE in str(exc):
                return OUTCOME_RZP_DEFINITIVE
            return OUTCOME_RZP_AMBIGUOUS
        except Exception:
            logger.exception(
                "Refund reconciliation: unexpected identity discovery "
                "error (refund=%s)",
                refund_id[:8],
            )
            return OUTCOME_INTERNAL_ERROR

        match_outcome, candidate = (
            RefundReconciliationService._classify_refund_candidates(
                refunds, payment_id, amount, currency
            )
        )
        if match_outcome == "multiple":
            logger.info(
                "Refund reconciliation: refund=%s has MULTIPLE "
                "authoritative Razorpay refunds for its stored facts — "
                "never guessed, keeping processing",
                refund_id[:8],
            )
            await RefundReconciliationService._touch_processing(refund_id)
            return OUTCOME_MULTIPLE_CANDIDATES
        if match_outcome == "none":
            logger.info(
                "Refund reconciliation: refund=%s has no authoritative "
                "Razorpay refund for its stored facts — keeping processing",
                refund_id[:8],
            )
            await RefundReconciliationService._touch_processing(refund_id)
            return OUTCOME_NO_IDENTITY

        candidate_id, candidate_status = candidate
        if candidate_status != "processed":
            # Razorpay has the refund but it is not final there yet.
            logger.info(
                "Refund reconciliation: refund=%s found on Razorpay but "
                "still %s there — keeping processing",
                refund_id[:8],
                candidate_status,
            )
            await RefundReconciliationService._touch_processing(refund_id)
            return OUTCOME_KEPT_PENDING

        # Authoritative match: hand the discovered identity to the Task 14
        # operation, which re-fetches and fully re-validates it before the
        # atomic attach + completion (validate → persist identity →
        # complete, never the other order).
        return await RefundReconciliationService._delegate_reconciliation(
            refund_id, supplied_id=candidate_id
        )

    @staticmethod
    def _classify_refund_candidates(
        refunds,
        payment_id: str,
        amount_paise: int,
        currency: str,
    ) -> Tuple[str, Optional[Tuple[str, str]]]:
        """Pure classifier over Razorpay's refund list for this record.

        Returns ("unique", (refund_id, status)) when EXACTLY ONE refund
        matches all stored facts; ("none", None) for zero matches; and
        ("multiple", None) when more than one matches — multiple matches
        are ambiguous by definition and reconciliation must never pick one
        arbitrarily.

        A candidate must match ALL backend-stored facts exactly:
          - a non-empty refund id,
          - payment_id == the stored payment id,
          - amount == the stored amount (integer paise),
          - currency == the stored currency,
          - status in the trusted vocabulary (processed/pending) — an
            unrecognized status (including Razorpay's `failed`) is never
            treated as authoritative here.
        """
        if not isinstance(refunds, list):
            return ("none", None)
        candidates: List[Tuple[str, str]] = []
        for item in refunds:
            if not isinstance(item, dict):
                continue
            refund_id = str(item.get("id") or "").strip()
            if not refund_id:
                continue
            if str(item.get("payment_id") or "") != payment_id:
                continue
            if item.get("amount") != amount_paise:
                continue
            if str(item.get("currency") or "") != currency:
                continue
            status = str(item.get("status") or "")
            if status not in _RP_REFUND_TRUSTED_STATUSES:
                continue
            candidates.append((refund_id, status))
        if len(candidates) == 1:
            return ("unique", candidates[0])
        if not candidates:
            return ("none", None)
        return ("multiple", None)

    @staticmethod
    def _select_unambiguous_refund(
        refunds,
        payment_id: str,
        amount_paise: int,
        currency: str,
    ) -> Optional[Tuple[str, str]]:
        """Pure selector: the ONE Razorpay refund that can authoritatively
        belong to this record, or None when zero or more than one match.

        Thin compatibility wrapper over _classify_refund_candidates();
        the classifier is the single matching implementation (no second
        matching path exists)."""
        _outcome, candidate = (
            RefundReconciliationService._classify_refund_candidates(
                refunds, payment_id, amount_paise, currency
            )
        )
        return candidate

    @staticmethod
    async def _touch_processing(refund_id: str) -> None:
        """Bookkeeping refresh of a still-processing record.

        Timestamps the attempt (same guarded `touch_processing` the Task 13
        execution layer uses) and rotates the record behind newer ones so a
        bounded batch cannot starve the rest of the queue. Never changes
        the reconciliation outcome and can never match a record another
        worker has terminalized.
        """
        try:
            await PaymentRefundRepository.touch_processing(refund_id)
        except Exception:
            # Bookkeeping only — never mask the reconciliation outcome.
            logger.debug(
                "Refund reconciliation: touch failed (refund=%s)",
                refund_id[:8],
            )

    @staticmethod
    async def _record_attempt_outcome(refund_id: str, outcome: str) -> None:
        """Persist bounded, sanitized reconciliation metadata on a refund
        that is still `processing` (Task 18 observability).

        Only stuck outcomes (kept_*) are recorded: they answer "when was
        this last attempted and why is it still ambiguous". Terminal and
        skipped outcomes need no "why stuck" bookkeeping. The write is a
        single atomic processing-guarded repository update, so it can
        never touch a record another worker terminalized and can never
        revive a terminal outcome. Any failure here is logged at debug
        level and swallowed — bookkeeping must never change the
        reconciliation outcome. The persisted value is the short
        allowlisted outcome code itself (no exception text, no Razorpay
        payloads, no secrets).
        """
        if outcome not in _STUCK_OUTCOMES:
            return
        try:
            await PaymentRefundRepository.record_reconciliation_attempt(
                refund_id, outcome
            )
        except Exception:
            logger.debug(
                "Refund reconciliation: attempt metadata not recorded "
                "(refund=%s)",
                refund_id[:8],
            )

    # ------------------------------------------------------------------
    # Operational checks & manual recovery (Task 18)
    # ------------------------------------------------------------------

    @staticmethod
    def scheduler_status() -> str:
        """Report the scheduler's state for explicit operational checks
        (no logging side effects, no Razorpay interaction):

          "disabled"    — REFUND_RECONCILIATION_ENABLED is false (shipped
                          default): no loop exists and none will start;
                          no Razorpay calls and no reconciliation
                          mutations occur.
          "running"     — the background loop is alive.
          "not_started" — enabled, but the loop has not been started (or
                          it finished); it starts via
                          start_background_loop() from the startup event.
        """
        if not settings.REFUND_RECONCILIATION_ENABLED:
            return "disabled"
        task = RefundReconciliationService._background_task
        if task is not None and not task.done():
            return "running"
        return "not_started"

    @staticmethod
    async def reconcile_single_refund(refund_id: str) -> Dict[str, object]:
        """Internal operator recovery helper (Task 18 §7).

        Runs the STANDARD reconciliation path for one refund record and
        returns a small, safe outcome summary. Deliberately NOT exposed
        through any HTTP route (Task 11's no-refund-surface invariant is
        pinned by tests): callers are server-side operations tooling only.

        Accepts ONLY a server-side local refund record id. It never
        accepts — and has no parameter for — a payment id, Razorpay
        refund id, amount, currency, or any client-supplied financial
        fact; all authoritative data is reloaded from the stored record
        and Razorpay. Every existing state guard applies unchanged
        (terminal records are skipped with zero Razorpay I/O, identity is
        never overwritten, completion only via the atomic guarded
        transition).

        Returns a dict with:
            refund_id — the local record id, echoed back (internal id).
            outcome   — one of the Task 18 outcome codes (e.g.
                        reconciled_completed, already_settled,
                        kept_razorpay_ambiguous, not_found).
        """
        rid = str(refund_id or "").strip()
        if not rid:
            return {"refund_id": "", "outcome": OUTCOME_NOT_FOUND}
        outcome = await RefundReconciliationService._reconcile_one(rid)
        return {"refund_id": rid, "outcome": outcome}

    # ------------------------------------------------------------------
    # Minimal background mechanism (established Task 9 pattern reused)
    # ------------------------------------------------------------------

    _background_task: Optional["asyncio.Task"] = None

    @staticmethod
    def start_background_loop() -> Optional["asyncio.Task"]:
        """Start the periodic refund-reconciliation loop (opt-in).

        Mirrors the Task 9 StalePaymentReconciliationService loop exactly:
        - Opt-IN via REFUND_RECONCILIATION_ENABLED=true (default False —
          no automatic reconciliation policy has been approved).
        - Sleeps BEFORE the first run (startup is never blocked).
        - Fixed cadence: REFUND_RECONCILIATION_INTERVAL_SECONDS (reuses the
          Task 9 interval value; no new polling policy invented).
        - Every run error is logged and swallowed; the loop survives.
        - Idempotent: calling twice never creates a second loop.
        - No Celery/Redis/external queue; a plain asyncio task.
        """
        if not settings.REFUND_RECONCILIATION_ENABLED:
            logger.info(
                "Refund reconciliation is disabled by configuration "
                "(REFUND_RECONCILIATION_ENABLED=false) — loop not started"
            )
            return None

        existing = RefundReconciliationService._background_task
        if existing is not None and not existing.done():
            return existing

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "Refund reconciliation: no running event loop — "
                "background reconciliation not started"
            )
            return None

        RefundReconciliationService._background_task = loop.create_task(
            RefundReconciliationService._reconciliation_loop()
        )
        logger.info(
            "Refund reconciliation background loop started (interval=%ss)",
            REFUND_RECONCILIATION_INTERVAL_SECONDS,
        )
        return RefundReconciliationService._background_task

    @staticmethod
    async def _reconciliation_loop() -> None:
        # Sleep FIRST: never run Razorpay calls during application startup.
        await asyncio.sleep(REFUND_RECONCILIATION_INTERVAL_SECONDS)
        while True:
            try:
                summary = (
                    await RefundReconciliationService
                    .reconcile_refundable_refunds()
                )
                logger.info("Refund reconciliation run summary: %s", summary)
            except asyncio.CancelledError:
                raise
            except Exception:
                # The loop must never die from a bad run.
                logger.exception("Refund reconciliation run failed")
            await asyncio.sleep(REFUND_RECONCILIATION_INTERVAL_SECONDS)
