from pydantic import BaseModel
from typing import Optional

class DoctorOut(BaseModel):
    id: str
    full_name: str
    email: str
    specialization: str
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    is_active_today: bool
