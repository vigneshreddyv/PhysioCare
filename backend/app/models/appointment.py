from datetime import datetime
from beanie import Document, Link, Indexed
from pydantic import Field
from app.models.patient import Patient
from app.models.doctor import Doctor

class Appointment(Document):
    patient: Link[Patient]
    doctor: Link[Doctor]
    appointment_date: datetime
    time_slot: str  # e.g., "10:30 AM", "02:30 PM"
    reason: str
    status: Indexed(str) = "scheduled"  # scheduled, in_progress, completed, cancelled
    billing_status: str = "pending"  # pending, paid, unpaid
    billing_amount: float = 120.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "appointments"
