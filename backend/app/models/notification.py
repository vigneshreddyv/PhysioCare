from datetime import datetime
from typing import Optional

from beanie import Document, PydanticObjectId, Indexed
from pydantic import Field

from app.core.time import utc_now


class Notification(Document):
    recipient_user_id: Indexed(PydanticObjectId)
    title: str
    message: str
    notification_type: str = "general" # general, appointment, laboratory
    is_read: bool = False
    related_entity_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "notifications"
