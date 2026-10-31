from datetime import datetime
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class AuthSession(Document):
    user_id: PydanticObjectId
    refresh_token_hash: str
    csrf_token_hash: str
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    demo_rehearsal_tag: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    rotated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "auth_sessions"
        indexes = [
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
        ]
