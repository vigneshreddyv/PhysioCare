from typing import List, Optional
from beanie import Document, PydanticObjectId
from pydantic import Field


class Doctor(Document):
    user_id: PydanticObjectId

    specialization: str

    profile_image: Optional[str] = None

    bio: Optional[str] = None

    qualifications: Optional[str] = None

    years_experience: Optional[int] = None

    specialties: List[str] = Field(default_factory=list)

    linkedin_url: Optional[str] = None

    website_url: Optional[str] = None

    is_active_today: bool = True

    accepts_home_visits: bool = True

    class Settings:
        name = "doctors"
