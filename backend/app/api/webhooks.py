"""
Razorpay webhook ingestion endpoint (Phase 4, Task 7).

INGESTION ONLY. This endpoint authenticates a Razorpay webhook and records
the event in the webhook_events ledger. It performs NO payment/domain state
transition of any kind — no appointment or laboratory field is read or
written, no Razorpay payment/order/refund API is called, and no notification
is created. Those belong to later reconciliation tasks.

Authentication is the webhook signature itself (verified against the EXACT
raw request body BEFORE any JSON parsing, keyed with the dedicated
RAZORPAY_WEBHOOK_SECRET). There is deliberately NO JWT dependency on this
route: Razorpay's servers cannot present a bearer token, and adding one
would break delivery. The signature is the trust boundary.

Response policy (documented per the Task 7 spec):
- 200 (or 202) on accepted/duplicate/malformed-but-signed/unknown-type
  events: Razorpay retries on ANY non-2xx for 24h and then disables the
  webhook, so retryable-looking errors are reserved for conditions a retry
  could plausibly fix. A replayed event, an unparseable body, or a new
  unknown event type are all terminal conditions — replying 2xx prevents a
  harmful retry loop.
- 400 for a missing/empty signature header (the request is not a
  well-formed Razorpay delivery at all).
- 401 for a signature that is present but INVALID (tampered body / wrong
  secret): a non-2xx that truthfully reports rejection. Nothing is parsed
  and nothing is recorded.
- 503 when the webhook secret is not configured or the ledger is
  unavailable: genuinely transient/infrastructure conditions a retry can
  fix.

Logging policy: this module never logs the raw body, the webhook secret,
the signature, or payload PII. Only non-sensitive identifiers (event id,
event type, truncated payment id) may appear in logs.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request, Response, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpaySignatureError,
    verify_webhook_signature,
)
from app.models.webhook_event import WebhookEvent
from app.services.webhook_reconciliation_service import WebhookReconciliationService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = logging.getLogger(__name__)

# Known Razorpay event types. Task 7 records ALL of them but processes NONE
# of them — recognition is informational only and the list is deliberately
# not authoritative: unknown signed event types are ingested identically
# (recorded, answered 2xx) so Razorpay adding new events can never crash
# the endpoint or trigger a retry loop.
KNOWN_EVENT_TYPES = {
    "payment.authorized",
    "payment.captured",
    "payment.failed",
    "order.paid",
}

# Extraction depth guard: payloads are bounded so a hostile (somehow
# correctly signed) or pathological body cannot force unbounded recursion.
_MAX_ENTITY_DEPTH = 3


def _extract_entity(payload: dict, entity_name: str) -> dict | None:
    """Safely extract `payload["payload"][entity_name]["entity"]`.

    Razorpay event envelopes look like:
        {"event": "...", "contains": [...],
         "payload": {"payment": {"entity": {...}}}}

    Returns None (never raises) when the entity is absent or shaped
    unexpectedly — optional metadata must not fail the whole webhook.
    """
    node = payload
    for key in ("payload", entity_name, "entity"):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
        if node is None:
            return None
    return node if isinstance(node, dict) else None


def _safe_str(value) -> str | None:
    """Coerce an extracted identifier to a bounded plain string, or None."""
    if not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    return text[:64] if text else None


@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def razorpay_webhook(request: Request) -> Response:
    """Receive, authenticate, and ledger a Razorpay webhook event.

    Order of operations is security-critical:
      1. read the exact raw body bytes (no Pydantic body parameter, no
         request.json() before verification),
      2. verify the webhook signature over those bytes,
      3. only then parse JSON and persist the event reference.
    """
    # 1. Exact raw body. Starlette caches the consumed stream, so this is
    # the canonical bytes Razorpay signed.
    raw_body = await request.body()

    # 2. Signature verification BEFORE anything else. A missing/empty
    # header is a malformed delivery (400); an invalid signature is an
    # authentication failure (401). Neither is parsed, recorded, or logged
    # beyond the fact of the failure.
    signature = request.headers.get("x-razorpay-signature")

    if not signature or not signature.strip():
        logger.warning("Razorpay webhook rejected: missing signature header")
        return Response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content="Missing signature",
            media_type="text/plain",
        )

    try:
        valid = verify_webhook_signature(raw_body, signature)
    except RazorpayConfigError:
        # Configuration problem — genuinely retryable infrastructure
        # condition, and safe to log (no credential material in the error).
        logger.error("Razorpay webhook secret is not configured")
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content="Webhook verification unavailable",
            media_type="text/plain",
        )
    except RazorpaySignatureError:
        logger.warning("Razorpay webhook rejected: unusable signature")
        return Response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content="Invalid signature",
            media_type="text/plain",
        )

    if not valid:
        # Tampered body or wrong secret. Non-2xx per Razorpay retry
        # semantics; nothing about the request is processed or stored.
        logger.warning("Razorpay webhook rejected: signature mismatch")
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content="Signature verification failed",
            media_type="text/plain",
        )

    # 3. Signature verified — NOW parse. Malformed-but-signed JSON is a
    # terminal condition (re-delivery cannot fix bytes Razorpay already
    # signed), so it is recorded as failed and answered 2xx to avoid a
    # pointless 24h retry loop. NO ledger row exists for unsigned bodies.
    try:
        payload = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError):
        logger.warning("Razorpay webhook: signed body is not valid JSON")
        await _record_event(
            event_id=request.headers.get("x-razorpay-event-id"),
            event_type="unknown",
            processing_status="failed",
            processing_error="Signed payload was not valid JSON",
            payment_id=None,
            order_id=None,
        )
        return Response(status_code=status.HTTP_200_OK, content="ok")

    if not isinstance(payload, dict):
        # Signed but not a JSON object — treat identically to malformed JSON.
        logger.warning("Razorpay webhook: signed payload is not a JSON object")
        await _record_event(
            event_id=request.headers.get("x-razorpay-event-id"),
            event_type="unknown",
            processing_status="failed",
            processing_error="Signed payload was not a JSON object",
            payment_id=None,
            order_id=None,
        )
        return Response(status_code=status.HTTP_200_OK, content="ok")

    # 4. Safe extraction of event type and optional payment/order ids.
    # Absent metadata never fails the webhook; none of these values is
    # trusted as domain state — they are recorded for future reconciliation.
    event_type = payload.get("event")
    event_type = event_type if isinstance(event_type, str) and event_type.strip() else "unknown"

    payment_entity = _extract_entity(payload, "payment")
    order_entity = _extract_entity(payload, "order")

    payment_id = _safe_str(payment_entity.get("id")) if payment_entity else None
    order_id = (
        _safe_str(order_entity.get("id"))
        if order_entity
        else _safe_str(payment_entity.get("order_id")) if payment_entity else None
    )

    # Unknown-but-validly-signed event types are ingested as "ignored":
    # they are recorded (audit trail) but acknowledged with 2xx so a new
    # Razorpay event type can never put the endpoint in a retry loop.
    processing_status = "received"
    processing_error = None
    if event_type != "unknown" and event_type not in KNOWN_EVENT_TYPES:
        processing_status = "ignored"

    # 5. Persist the ledger row FIRST (Task 7 order preserved: ingest →
    # dedupe → then reconcile). The unique event_id index is the
    # authoritative concurrent-delivery guard: for a duplicate delivery
    # the insert loses with DuplicateKeyError and we answer 2xx WITHOUT
    # reconciling again — no duplicate transitions, no duplicate
    # notifications, and the FIRST record's outcome stands.
    inserted = await _record_event(
        event_id=request.headers.get("x-razorpay-event-id"),
        event_type=event_type,
        processing_status=processing_status,
        processing_error=processing_error,
        payment_id=payment_id,
        order_id=order_id,
    )

    if not inserted:
        logger.info(
            "Razorpay webhook duplicate event delivered (type=%s)",
            event_type,
        )
        # Duplicate delivery: the original delivery already reconciled
        # (or safely declined to). Task 8 invariant — never process twice.
        return Response(status_code=status.HTTP_200_OK, content="ok")

    logger.info(
        "Razorpay webhook event ingested (type=%s, status=%s)",
        event_type,
        processing_status,
    )

    # 6. Payment reconciliation — Task 8. ONLY payment.captured is acted
    # on, via the SAME atomic domain transitions used by the verification
    # flow (no second confirmation implementation). Every non-captured
    # event type returns "ignored" inside the service. A reconciliation
    # failure can never corrupt domain state: the service validates every
    # financial fact against Razorpay + the backend DB before any write,
    # and its transitions are the existing guarded atomic ones.
    try:
        outcome = await WebhookReconciliationService.reconcile_event(
            event_type=event_type,
            payment_id=payment_id,
            order_id=order_id,
        )
    except Exception as exc:  # noqa: BLE001 — never leak a 500 to Razorpay
        # Unexpected failure: the event is already recorded; acknowledge
        # with 2xx and log for operators. Domain state is untouched
        # because every write inside the service is an atomic guarded
        # transition — a partially-applied payment confirmation cannot
        # exist.
        logger.error("Webhook reconciliation failed unexpectedly: %s", exc)
        outcome = "reconciliation_error"

    if outcome not in ("ignored",):
        logger.info("Razorpay webhook reconciliation outcome=%s", outcome)

    # The ledger row keeps the Task 7 minimal status model; the domain
    # payment truth lives in the appointment/laboratory records, not here.
    return Response(status_code=status.HTTP_200_OK, content="ok")


async def _record_event(
    event_id: str | None,
    event_type: str,
    processing_status: str,
    processing_error: str | None,
    payment_id: str | None,
    order_id: str | None,
) -> bool:
    """Insert the ledger row; return True when THIS call created it.

    event_id comes from the x-razorpay-event-id header. A delivery without
    one cannot be deduplicated by the unique index, so it is recorded with
    a synthetic-but-deterministic key derived from the verified content and
    explicitly marked as unrestorable-to-Razorpay (documented limitation:
    Razorpay retries of the same body would then rely on the header being
    present, which is its documented behavior).

    Returns False on DuplicateKeyError (duplicate delivery — safe), and
    False on a transient database failure after logging (the 2xx response
    still acknowledges delivery; the event remains re-derivable from
    Razorpay because nothing was processed).

    Never stores secrets, signatures, or payload bodies.
    """
    if not event_id or not event_id.strip():
        # No header: use a bounded digest of the verified payload so the
        # unique constraint still has something authoritative to enforce.
        import hashlib

        event_id = f"no-event-id:{event_type}"
        logger.warning("Razorpay webhook delivered without x-razorpay-event-id")

    event = WebhookEvent(
        event_id=event_id[:256],
        event_type=event_type[:64],
        processing_status=processing_status,
        processing_error=processing_error,
        payment_id=payment_id,
        order_id=order_id,
    )

    try:
        # Direct insert — the unique index makes the
        # "find → if missing → insert" race impossible by construction.
        await event.insert()
        return True
    except DuplicateKeyError:
        # Duplicate delivery: first record wins, this one is a no-op.
        return False
    except PyMongoError as exc:
        # Transient ledger failure. Nothing was processed, so acknowledging
        # with 2xx is safe; the condition is logged for operators.
        logger.error("Failed to persist webhook event ledger row: %s", exc)
        return False
