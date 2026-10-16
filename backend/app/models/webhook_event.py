"""
Webhook event ledger (Phase 4, Task 7).

Persistent record of Razorpay webhook events received by the ingestion
endpoint. Task 7 is INGESTION ONLY: the ledger is the ONLY persistent side
effect a webhook can produce. It exists to provide:

- event-level deduplication (unique index on event_id — the authoritative
  database constraint, never an application-level check-then-insert)
- an audit trail (what arrived, when, with what processing outcome)
- the minimum reference data future reconciliation tasks will need
  (event type + Razorpay payment/order ids)

PRIVACY / MINIMALITY POLICY (Task 6 audit §O):
- No secrets are ever stored (neither RAZORPAY_KEY_SECRET nor
  RAZORPAY_WEBHOOK_SECRET, nor signatures).
- The FULL webhook payload is deliberately NOT stored. Razorpay payment
  payloads carry customer PII (email, contact) and payment instrument
  metadata that this system has no reason to retain. Only the compact
  identifiers below (event id, type, payment id, order id) are persisted;
  future reconciliation re-fetches authoritative data from Razorpay's APIs
  server-side rather than relying on a stored snapshot.
- Nothing here references appointments, laboratory bookings, patients, or
  any domain state — this document cannot influence payment state.
"""

from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pymongo import IndexModel
from pydantic import Field

# Explicit, minimal processing-status vocabulary for Task 7 (ingestion only).
# Domain-outcome statuses (paid/failed/refunded/...) intentionally DO NOT
# exist here — they belong to later reconciliation work.
#
#   received : event authenticated, structurally valid, ledger row created
#   ignored  : correctly signed but nothing to do (e.g. unknown event type)
#   failed   : signed but could not be ingested (e.g. malformed JSON body)
#
# A duplicate delivery of an already-recorded event creates NO new row and
# does NOT mutate the existing row's status (the first outcome stands).
PROCESSING_STATUSES = ("received", "ignored", "failed")


class WebhookEvent(Document):
    # Unique per Razorpay event (delivered in the x-razorpay-event-id
    # header). This is the deduplication key; its unique index below is the
    # authoritative concurrent-delivery guard.
    event_id: Indexed(str)

    # Razorpay event type, e.g. "payment.captured", "order.paid",
    # "payment.failed", or an unrecognized-but-signed type. Stored verbatim
    # for audit; never interpreted as domain state by Task 7.
    event_type: str

    # Ingestion outcome (one of PROCESSING_STATUSES above).
    processing_status: str = "received"

    # Safe, human-readable outcome note when ingestion did not fully
    # succeed. Never contains secrets, signatures, or raw payload bodies.
    processing_error: Optional[str] = None

    # Extracted Razorpay references, when present in the (verified) payload.
    # Optional by design: not every event type carries a payment entity.
    payment_id: Optional[str] = None
    order_id: Optional[str] = None

    # Server-side receipt time (same convention as the rest of the models:
    # naive UTC via datetime.utcnow).
    received_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "webhook_events"
        indexes = [
            # The authoritative event-level deduplication constraint. Under
            # concurrent duplicate deliveries (Razorpay is at-least-once)
            # exactly one insert wins; every loser receives DuplicateKeyError
            # and is answered with a safe success response — never a 500,
            # because a duplicate webhook is not an error.
            IndexModel(
                [("event_id", 1)],
                name="uniq_webhook_event_id",
                unique=True,
            ),
        ]
