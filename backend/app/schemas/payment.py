from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CheckoutVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    razorpay_order_id: str = Field(min_length=1, max_length=128)
    razorpay_payment_id: str = Field(min_length=1, max_length=128)
    razorpay_signature: str = Field(min_length=1, max_length=256)


class PaymentOrderOut(BaseModel):
    appointment_id: str
    order_id: str
    amount: int
    currency: Literal["INR"]
    key_id: str
    status: str


class PaymentStatusOut(BaseModel):
    appointment_id: str
    status: str
    billing_status: str
    amount: float
    currency: Optional[Literal["INR"]] = None


class PaymentVerificationOut(BaseModel):
    appointment_id: str
    status: str
    billing_status: str


class PaymentReadinessOut(BaseModel):
    available: bool
    mode: Literal["test"]
    currency: Optional[Literal["INR"]] = None


class PaymentHistoryItemOut(BaseModel):
    id: str
    appointment_id: str
    amount: float
    currency: Literal["INR"]
    status: str
    reconciliation_status: str
    billing_status: str
    payment_status: str
    appointment_date: Optional[datetime] = None
    time_slot: Optional[str] = None
    service_mode: Optional[str] = None


class CapturedPaymentIssueOut(BaseModel):
    appointment_id: str
    amount_paise: int
    currency: str
    appointment_status: Optional[str] = None
    payment_status: Optional[str] = None
    reason: str


class CapturedPaymentReconciliationOut(BaseModel):
    examined: int
    recovered: int
    clinic_review: list[CapturedPaymentIssueOut]
    failed: list[CapturedPaymentIssueOut]


class CapturedPaymentReviewListOut(BaseModel):
    clinic_review: list[CapturedPaymentIssueOut]
