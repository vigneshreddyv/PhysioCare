from typing import Optional
from beanie import Document, PydanticObjectId


class Doctor(Document):
    user_id: PydanticObjectId

    specialization: str

    profile_image: Optional[str] = None

    bio: Optional[str] = None

    is_active_today: bool = True

    class Settings:
        name = "doctors"