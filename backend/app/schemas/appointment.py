from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    doctor_id: str

    service_type: str

    appointment_date: datetime
    time_slot: str

    reason: str

    symptoms: Optional[str] = None
    duration_days: Optional[int] = Field(default=None, ge=0)
    pain_level: Optional[str] = None

    visit_address: Optional[str] = None

    payment_method: Optional[str] = None


class AppointmentUpdate(BaseModel):
    status: Optional[str] = None

    billing_status: Optional[str] = None
    billing_amount: Optional[float] = None

    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_id: Optional[str] = None
    payment_order_id: Optional[str] = None

    meeting_link: Optional[str] = None

    feedback_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
    )

    feedback_comment: Optional[str] = None


class AppointmentOut(BaseModel):
    id: str

    patient_id: str
    patient_name: str

    doctor_id: str
    doctor_name: str
    specialization: Optional[str] = None

    service_type: str

    appointment_date: datetime
    time_slot: str

    reason: str
    symptoms: Optional[str] = None
    duration_days: Optional[int] = None
    pain_level: Optional[str] = None

    visit_address: Optional[str] = None

    status: str

    billing_status: str
    billing_amount: float

    payment_method: Optional[str] = None
    payment_status: str
    payment_id: Optional[str] = None
    payment_order_id: Optional[str] = None

    meeting_link: Optional[str] = None

    feedback_rating: Optional[int] = None
    feedback_comment: Optional[str] = None

    created_at: datetime