from datetime import datetime

from beanie import Document, Indexed
from pydantic import EmailStr, Field

from app.core.time import utc_now


class User(Document):
    email: Indexed(EmailStr, unique=True)
    hashed_password: str
    role: str
    full_name: str
    is_active: bool = True
    demo_rehearsal_tag: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "users"
