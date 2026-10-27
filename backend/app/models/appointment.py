from datetime import datetime
from beanie import Document, PydanticObjectId, Indexed
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel
from typing import Optional


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

    duration_days: Optional[int] = None

    pain_severity: Optional[str] = None

    submission_claim: Optional[str] = None

    submission_fingerprint: Optional[str] = None

    status: Indexed(str) = "scheduled"

    billing_status: str = "pending"

    billing_amount: float = 120.0

    cancelled_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

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
