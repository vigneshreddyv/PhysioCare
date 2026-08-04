from typing import Optional
from beanie import Document, PydanticObjectId


class Patient(Document):
    user_id: PydanticObjectId

    phone: Optional[str] = None

    date_of_birth: Optional[str] = None

    subscription_status: str = "active"

    primary_doctor_id: Optional[PydanticObjectId] = None

    class Settings:
        name = "patients"