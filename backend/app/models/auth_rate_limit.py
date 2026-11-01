from datetime import datetime

from beanie import Document, Indexed
from pymongo import ASCENDING, IndexModel


class AuthRateLimitBucket(Document):
    """Opaque, fixed-window authentication rate-limit state.

    ``bucket_key`` is an HMAC digest. Raw emails, tokens, passwords, and client
    addresses are never persisted in this collection.
    """

    bucket_key: Indexed(str, unique=True)
    attempt_count: int = 0
    expires_at: datetime

    class Settings:
        name = "auth_rate_limit_buckets"
        indexes = [
            IndexModel(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                name="expire_auth_rate_limit_buckets",
            )
        ]
