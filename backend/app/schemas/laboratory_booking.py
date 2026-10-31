from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class EmbeddedTestBase(BaseModel):
    test_id: str
    name: str
    sample: str
    price: float


class LaboratoryBookingBase(BaseModel):
    test_ids: List[str] = Field(..., min_length=1)
    appointment_date: str  # Expected in YYYY-MM-DD format
    time_slot: str
    visit_type: str  # Must be 'home' or 'clinic'
    address: Optional[str] = None


class LaboratoryBookingCreate(LaboratoryBookingBase):
    pass


class LaboratoryBookingResponse(BaseModel):
    id: str
    patient_id: str
    selected_tests: List[EmbeddedTestBase]
    visit_type: str
    appointment_date: datetime
    time_slot: str
    address: Optional[str]
    status: str
    billing_status: str
    billing_amount: float
    payment_method: Optional[str]
    payment_status: Optional[str]
    payment_id: Optional[str]
    payment_order_id: Optional[str]
    created_at: datetime


class LaboratoryBookingPaymentUpdate(BaseModel):
    payment_method: str
    payment_id: str
    payment_order_id: str
    payment_status: str  # Expected 'success' or 'failed'


class LaboratoryBookingStatusUpdate(BaseModel):
    status: Literal["completed", "cancelled"]
