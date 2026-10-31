from datetime import datetime
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field

from app.core.time import utc_now


class Report(Document):
    patient_id: PydanticObjectId
    booking_id: Optional[PydanticObjectId] = None
    title: str
    category: str  # assessment, summary, diagnostic
    date: datetime
    description: str
    therapist: str
    content: dict  # symptoms, findings, recommendations
    file_path: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "reports"
