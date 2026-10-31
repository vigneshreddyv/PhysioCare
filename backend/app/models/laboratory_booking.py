from datetime import datetime
from typing import List, Optional

from beanie import Document, PydanticObjectId
from pydantic import Field, BaseModel

from app.core.time import utc_now


class EmbeddedTest(BaseModel):
    test_id: str
    name: str
    sample: str
    price: float


class LaboratoryBooking(Document):
    patient_id: PydanticObjectId
    selected_tests: List[EmbeddedTest]
    visit_type: str
    appointment_date: datetime
    time_slot: str
    address: Optional[str] = None
    status: str = "pending_payment"  # pending_payment, confirmed, failed, completed, cancelled
    billing_status: str = "pending"  # pending, paid, failed
    billing_amount: float
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None  # pending, success, failed
    payment_id: Optional[str] = None
    payment_order_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "laboratory_bookings"
