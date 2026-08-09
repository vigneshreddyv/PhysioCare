from pydantic import BaseModel
from typing import Optional


class DoctorOut(BaseModel):
    id: str
    full_name: str
    email: str

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

    is_active_today: bool