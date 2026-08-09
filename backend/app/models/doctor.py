from typing import Optional
from beanie import Document, PydanticObjectId


class Doctor(Document):
    user_id: PydanticObjectId

    specialization: str

    experience_years: int = 0

    expertise: list[str] = []

    profile_image: Optional[str] = None

    bio: Optional[str] = None

    rating: float = 0.0

    total_reviews: int = 0

    consultation_fee: float = 500.0

    home_visit_available: bool = True

    online_consultation_available: bool = True

    is_active_today: bool = True

    class Settings:
        name = "doctors"