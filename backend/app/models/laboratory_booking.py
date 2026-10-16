from datetime import datetime
from typing import List, Optional
from beanie import Document, PydanticObjectId
from pymongo import IndexModel
from pydantic import Field, BaseModel

# Booking statuses that reserve a patient's slot. Mirrors the application-level
# conflict check exactly (find_conflicting_booking gates on billing_status
# pending|paid): a booking keeps reserving its slot until payment is marked
# failed, which is the release path that exists in the current application.
ACTIVE_BILLING_STATUSES = ["pending", "paid"]


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
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "laboratory_bookings"
        indexes = [
            # Concurrency safety net for laboratory booking creation: the same
            # patient can never hold two active bookings for the same calendar
            # day and time slot, even when duplicate requests race past the
            # check-then-insert window (LaboratoryService step 8).
            # Keys on billing_status (pending|paid) — the same field and values
            # the application-level conflict check gates on — so failed/cancelled
            # releases stay in lockstep with the existing rules. Partial so a
            # billing-failed booking stops reserving the slot.
            IndexModel(
                [("patient_id", 1), ("appointment_date", 1), ("time_slot", 1)],
                name="uniq_patient_date_slot",
                unique=True,
                partialFilterExpression={"billing_status": {"$in": ACTIVE_BILLING_STATUSES}},
            ),
        ]