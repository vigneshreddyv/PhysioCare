from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class NotificationOut(BaseModel):
    id: str
    recipient_user_id: str
    title: str
    message: str
    notification_type: str
    is_read: bool
    related_entity_id: Optional[str] = None
    created_at: datetime
