from datetime import datetime, timezone
from typing import Annotated, Optional

from beanie import Document, Indexed, PydanticObjectId
from pymongo import IndexModel
from pydantic import Field

# Booked slots are protected by a unique index only while the appointment is
# active. Cancelled/completed/no_show records must free the slot again.
ACTIVE_STATUSES = ["pending_payment", "confirmed", "in_progress"]


def canonical_appointment_date(value: datetime) -> datetime:
    """Normalize any appointment_date to a stable calendar-day value (UTC midnight).

    Patients submit their chosen date with arbitrary times attached (the UI uses
    noon), while seeded/legacy records carry incidental timestamps. Availability
    must key on the calendar day + time_slot, never on the stored clock time.
    """
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


class Appointment(Document):
    patient_id: PydanticObjectId
    doctor_id: PydanticObjectId

    # Service selected by the patient
    service_type: str = "clinic_consultation"

    appointment_date: datetime
    time_slot: str

    # Patient health information
    reason: str
    symptoms: Optional[str] = None
    duration_days: Optional[int] = None
    pain_level: Optional[str] = None

    # Required for home visits
    visit_address: Optional[str] = None

    # Appointment status
    # pending_payment → confirmed → in_progress → completed
    # confirmed → cancelled
    status: Annotated[str, Indexed()] = "pending_payment"

    # Billing
    billing_status: str = "pending"
    billing_amount: float = 120.0

    # Payment
    payment_method: Optional[str] = None
    payment_status: str = "pending"
    payment_id: Optional[str] = None
    payment_order_id: Optional[str] = None

    # Online consultation
    meeting_link: Optional[str] = None

    # Feedback after treatment
    feedback_rating: Optional[int] = None
    feedback_comment: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "appointments"
        indexes = [
            # Concurrency safety net for appointment creation: the same patient
            # can never hold two active bookings for the same calendar day and
            # time slot, even when duplicate requests race past the
            # check-then-insert window. Partial so cancelled/completed
            # appointments release their slot.
            IndexModel(
                [("patient_id", 1), ("appointment_date", 1), ("time_slot", 1)],
                name="uniq_patient_date_slot",
                unique=True,
                partialFilterExpression={"status": {"$in": ACTIVE_STATUSES}},
            ),
        ]