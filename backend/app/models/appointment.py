from datetime import datetime
from beanie import Document, PydanticObjectId, Indexed
from pydantic import Field


class Appointment(Document):
    patient_id: PydanticObjectId

    doctor_id: PydanticObjectId

    appointment_date: datetime

    time_slot: str

    reason: str

    status: Indexed(str) = "scheduled"

    billing_status: str = "pending"

    billing_amount: float = 120.0

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "appointments"