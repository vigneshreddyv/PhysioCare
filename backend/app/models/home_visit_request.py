from datetime import datetime

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


class HomeVisitRequest(Document):
    patient_id: PydanticObjectId
    preferred_doctor_id: PydanticObjectId
    home_address: str
    reason: str
    city: str | None = None
    body_regions: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    duration_days: int | None = None
    pain_severity: str | None = None
    status: Indexed(str) = "pending_clinic_confirmation"
    reviewed_by_user_id: PydanticObjectId | None = None
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "home_visit_requests"
