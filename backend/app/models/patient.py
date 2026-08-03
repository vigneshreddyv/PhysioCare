from typing import Optional
from beanie import Document, Link
from app.models.user import User
from app.models.doctor import Doctor

class Patient(Document):
    user: Link[User]
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    subscription_status: str = "active"  # active, inactive
    primary_doctor: Optional[Link[Doctor]] = None
    
    class Settings:
        name = "patients"
