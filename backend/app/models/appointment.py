from datetime import datetime
from typing import Optional

from beanie import Document, PydanticObjectId, Indexed
from pydantic import BaseModel, Field, field_validator
from pymongo import ASCENDING, IndexModel

from app.core.time import utc_now


class DoctorAssignmentAudit(BaseModel):
    changed_by_user_id: PydanticObjectId
    previous_doctor_id: PydanticObjectId
    new_doctor_id: PydanticObjectId
    changed_at: datetime


class Appointment(Document):
    patient_id: PydanticObjectId

    doctor_id: PydanticObjectId

    doctor_assignment_pending: bool = False

    doctor_assignment_audit: list[DoctorAssignmentAudit] = Field(default_factory=list)

    appointment_date: datetime

    starts_at: Optional[datetime] = None

    slot_claim: Optional[str] = None

    clinic_timezone: str = "Asia/Kolkata"

    time_slot: str

    reason: str

    service_mode: str = "clinic"

    home_address: Optional[str] = None

    city: Optional[str] = None

    body_regions: list[str] = Field(default_factory=list)

    symptoms: list[str] = Field(default_factory=list)

    @field_validator("symptoms", mode="before")
    @classmethod
    def normalize_null_symptoms(cls, value):
        return [] if value is None else value

    duration_days: Optional[int] = None

    pain_severity: Optional[str] = None

    submission_claim: Optional[str] = None

    submission_fingerprint: Optional[str] = None

    status: Indexed(str) = "scheduled"

    billing_status: str = "pending"

    billing_amount: float = 120.0

    billing_currency: Optional[str] = None

    payment_status: str = "not_started"

    payment_order_id: Optional[str] = None

    payment_id: Optional[str] = None

    cancelled_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "appointments"
        indexes = [
            IndexModel(
                [("slot_claim", ASCENDING)],
                unique=True,
                name="unique_active_doctor_slot_claim",
                partialFilterExpression={"slot_claim": {"$type": "string"}},
            ),
            IndexModel(
                [("submission_claim", ASCENDING)],
                unique=True,
                name="unique_home_booking_submission_claim",
                partialFilterExpression={"submission_claim": {"$type": "string"}},
            ),
        ]
