from datetime import datetime
from typing import Annotated, List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field


LaboratoryTestId = Annotated[str, Field(min_length=1, max_length=128)]


class EmbeddedTestBase(BaseModel):
    test_id: str
    name: str
    sample: str
    price: float


class LaboratoryBookingBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_ids: List[LaboratoryTestId] = Field(..., min_length=1, max_length=12)
    appointment_date: str = Field(min_length=10, max_length=10)  # YYYY-MM-DD
    time_slot: str = Field(min_length=1, max_length=20)
    visit_type: Literal["home", "clinic"]
    address: Optional[str] = Field(default=None, max_length=500)


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
    created_at: datetime


class LaboratoryBookingPaymentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method: str = Field(min_length=1, max_length=50)
    payment_id: str = Field(min_length=1, max_length=128)
    payment_order_id: str = Field(min_length=1, max_length=128)
    payment_status: Literal["success", "failed"]


class LaboratoryBookingStatusUpdate(BaseModel):
    status: Literal["completed", "cancelled"]
