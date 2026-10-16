from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_serializer


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
    appointment_date: Optional[datetime] = None
    time_slot: Optional[str] = None

    billing_status: Optional[str] = None
    billing_amount: Optional[float] = None

    meeting_link: Optional[str] = None

    feedback_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
    )

    feedback_comment: Optional[str] = None

    # Phase 4, Task 11 — financial security hardening.
    # The payment fields below were REMOVED from this mutation schema:
    # payment_method / payment_status / payment_id / payment_order_id.
    # The update service never read them, but their presence advertised a
    # client-controlled payment-mutation surface (a generic PATCH could
    # carry a fabricated Razorpay payment_id/payment_order_id or claim
    # payment_status="success"). Online payment state is
    # backend-authoritative and may only be written by the Razorpay-verified
    # paths (Task 4 verification, Task 8 webhook reconciliation) or the
    # Task 9 expiry transition. Client-supplied extras are ignored by
    # Pydantic's default configuration.


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

    @field_serializer('appointment_date')
    def serialize_date(self, dt: datetime, _info):
        return dt.strftime('%Y-%m-%d')

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