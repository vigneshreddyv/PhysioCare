from pydantic import BaseModel
from typing import Optional

class PatientOut(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    subscription_status: str
