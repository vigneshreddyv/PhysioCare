from datetime import datetime
from typing import Optional

from beanie import Document
from pymongo import IndexModel


class AuthSession(Document):
    """Server-side state for one refresh-token in a rotation family."""

    user_id: str
    family_id: str
    jti: str
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    rotated_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    replaced_by_jti: Optional[str] = None
    revocation_reason: Optional[str] = None

    class Settings:
        name = "auth_sessions"
        indexes = [
            IndexModel([ ("jti", 1) ], unique=True, name="uniq_auth_session_jti"),
            IndexModel([ ("token_hash", 1) ], unique=True, name="uniq_auth_session_token_hash"),
            IndexModel([ ("expires_at", 1) ], expireAfterSeconds=0, name="ttl_auth_sessions"),
            IndexModel([ ("family_id", 1), ("user_id", 1) ], name="idx_auth_session_family_user"),
        ]
