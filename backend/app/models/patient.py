from typing import Optional
from beanie import Document, PydanticObjectId


class Patient(Document):
    user_id: PydanticObjectId

    phone: Optional[str] = None

    date_of_birth: Optional[str] = None

    # Patient-recorded identity field. This is not inferred from name, title,
    # date of birth, or any clinical data.
    gender: Optional[str] = None

    subscription_status: str = "active"

    primary_doctor_id: Optional[PydanticObjectId] = None

    saved_home_address: Optional[str] = None

    class Settings:
        name = "patients"
