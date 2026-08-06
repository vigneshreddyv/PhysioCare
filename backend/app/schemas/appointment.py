from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class AppointmentCreate(BaseModel):
    doctor_id: str
    appointment_date: datetime
    time_slot: str
    reason: str

class AppointmentUpdate(BaseModel):
    status: Optional[str] = None
    billing_status: Optional[str] = None
    billing_amount: Optional[float] = None

class AppointmentOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    specialization: Optional[str] = None
    appointment_date: datetime
    time_slot: str
    reason: str
    status: str
    billing_status: str
    billing_amount: float
    created_at: datetime
