from pydantic import BaseModel
from typing import Optional


class SavedAddress(BaseModel):
    building_name: str
    door_number: str
    area: str
    street: str
    landmark: str
    pincode: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class SavedAddressUpdate(BaseModel):
    building_name: str
    door_number: str
    area: str
    street: str
    landmark: str
    pincode: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class PatientOut(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    subscription_status: str
    saved_address: Optional[SavedAddress] = None