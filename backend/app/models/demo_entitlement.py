from datetime import datetime

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class DemoEntitlement(Document):
    patient_id: PydanticObjectId
    active: bool = True
    granted_by_user_id: PydanticObjectId
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    revoked_at: datetime | None = None

    class Settings:
        name = "demo_entitlements"
        indexes = [
            IndexModel(
                [("patient_id", ASCENDING)],
                unique=True,
                name="unique_demo_entitlement_patient",
            ),
        ]
