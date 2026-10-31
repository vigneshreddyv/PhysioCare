from datetime import datetime, timezone
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class PaymentAttempt(Document):
    """One Razorpay order per appointment; retries reuse the same provider order."""

    appointment_id: PydanticObjectId
    patient_id: PydanticObjectId
    amount_paise: int
    currency: str = "INR"
    provider_order_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    # success means the provider confirmed capture; appointment.payment_status
    # is the booking-resolution state (success vs reconciliation_required).
    status: str = "creating"  # creating, pending, success, failed, cancelled, abandoned
    reconciliation_status: str = "pending"  # pending, reconciled, clinic_review
    reconciliation_checked_at: Optional[datetime] = None
    processed_event_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "payment_attempts"
        indexes = [
            IndexModel([("appointment_id", ASCENDING)], unique=True, name="unique_payment_per_appointment"),
            IndexModel(
                [("provider_order_id", ASCENDING)],
                unique=True,
                name="unique_razorpay_order",
                partialFilterExpression={"provider_order_id": {"$type": "string"}},
            ),
            IndexModel(
                [("status", ASCENDING), ("reconciliation_status", ASCENDING), ("updated_at", ASCENDING)],
                name="payment_reconciliation_status_updated_at",
            ),
        ]


class RazorpayWebhookEvent(Document):
    event_id: str
    provider_order_id: Optional[str] = None
    status: str = "processing"  # processing, processed
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None

    class Settings:
        name = "razorpay_webhook_events"
        indexes = [IndexModel([("event_id", ASCENDING)], unique=True, name="unique_razorpay_webhook_event")]
