from typing import Optional
from beanie import Document, Link
from app.models.user import User

class Doctor(Document):
    user: Link[User]
    specialization: str
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    is_active_today: bool = True
    
    class Settings:
        name = "doctors"
