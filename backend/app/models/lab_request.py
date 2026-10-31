from datetime import datetime

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.core.time import utc_now


class LabRequest(Document):
    patient_id: PydanticObjectId
    submission_key: str | None = None
    demo_rehearsal_tag: str | None = None
    mode: str
    selected_tests: list[str] = Field(default_factory=list)
    home_address: str | None = None
    city: str | None = None
    status: Indexed(str) = "pending_clinic_confirmation"
    reviewed_by_user_id: PydanticObjectId | None = None
    reviewed_at: datetime | None = None
    assigned_laboratorian_user_id: PydanticObjectId | None = None
    assigned_by_user_id: PydanticObjectId | None = None
    assigned_at: datetime | None = None
    assignment_history: list[dict] = Field(default_factory=list)
    report_status: Indexed(str) = "not_started"
    report_storage_key: str | None = None
    report_file_name: str | None = None
    report_content_type: str | None = None
    report_size_bytes: int | None = None
    report_uploaded_by_user_id: PydanticObjectId | None = None
    report_uploaded_at: datetime | None = None
    report_released_by_user_id: PydanticObjectId | None = None
    report_released_at: datetime | None = None
    report_publication_history: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "lab_requests"
        indexes = [
            IndexModel(
                [("patient_id", ASCENDING), ("submission_key", ASCENDING)],
                name="unique_patient_lab_submission_key",
                unique=True,
                partialFilterExpression={"submission_key": {"$type": "string"}},
            )
        ]
