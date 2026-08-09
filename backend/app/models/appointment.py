from datetime import datetime
from typing import Annotated, Optional

from beanie import Document, PydanticObjectId, Indexed
from pydantic import Field


class Appointment(Document):
    patient_id: PydanticObjectId
    doctor_id: PydanticObjectId

    # Service selected by the patient
    service_type: str

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
    status: Annotated[str, Indexed()] = "approved"

    # Billing
    billing_status: str = "pending"
    billing_amount: float = 120.0

    # Payment
    payment_method: Optional[str] = None
    payment_status: str = "pending"
    payment_id: Optional[str] = None

    # Feedback after treatment
    feedback_rating: Optional[int] = None
    feedback_comment: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "appointments"