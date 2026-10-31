from datetime import datetime
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field

from app.core.time import utc_now


class PatientAdminEditAudit(BaseModel):
    actor_user_id: PydanticObjectId
    changed_fields: list[str]
    changed_at: datetime = Field(default_factory=utc_now)


class Patient(Document):
    user_id: PydanticObjectId

    phone: Optional[str] = None

    date_of_birth: Optional[str] = None

    # Patient-recorded identity field. This is not inferred from name, title,
    # date of birth, or any clinical data.
    gender: Optional[str] = None

    subscription_status: str = "active"

    primary_doctor_id: Optional[PydanticObjectId] = None

    saved_home_address: Optional[str] = None
    demo_rehearsal_tag: Optional[str] = None

    # Metadata-only audit history. Values are intentionally excluded so
    # contact and identity data are not duplicated into an audit log.
    admin_edit_audit: list[PatientAdminEditAudit] = Field(default_factory=list)

    class Settings:
        name = "patients"
