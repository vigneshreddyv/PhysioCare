"""
Request/response schemas for Razorpay order creation (Phase 4, Task 2).

The order-creation response contains ONLY the data the frontend's checkout
step will eventually need. It deliberately excludes:
- key_secret / any Razorpay credential
- internal database fields
"""
from typing import Optional

from pydantic import BaseModel, Field


class RazorpayOrderRequest(BaseModel):
    """Body for order-creation requests.

    Intentionally accepts NO amount/currency/patient_id/payment_order_id
    fields — every authoritative value is derived server-side from the
    database. This model exists so the endpoint has an explicit, empty-by-
    design request contract (and so accidental client-supplied fields are
    ignored, never trusted).
    """

    model_config = {"extra": "ignore"}


class RazorpayVerifyRequest(BaseModel):
    """Body for payment-verification requests (Task 4).

    Accepts ONLY the three Razorpay checkout response values. Deliberately
    rejects-as-untrusted (i.e. carries no fields for, and the service never
    reads): amount, billing_amount, currency, patient_id, billing_status,
    payment_status, appointment/booking status, or payment_order_id. The
    domain object id comes from the URL path; every authoritative value comes
    from the backend database or Razorpay itself.
    """

    razorpay_payment_id: str = Field(..., min_length=3, max_length=64)
    razorpay_order_id: str = Field(..., min_length=6, max_length=64)
    razorpay_signature: str = Field(..., min_length=8, max_length=256)

    model_config = {"extra": "ignore"}


class RazorpayVerifyResponse(BaseModel):
    """Result of backend payment verification.

    `status` is the BACKEND-confirmed payment outcome — never derived from
    the checkout callback alone:
      - "verified": payment verified and state transitioned (or already
        verified previously — idempotent replay).
      - "failed": verification definitively failed (bad signature, wrong
        order/amount, Razorpay confirms a non-captured state).
    `payment_status` mirrors the existing domain payment_status vocabulary
    ("success" / "failed") so the frontend can drive the EXISTING UI states
    without redesign.
    """

    status: str  # "verified" | "failed"
    payment_status: str  # existing vocabulary: "success" | "failed"
    billing_status: Optional[str] = None
    entity_status: Optional[str] = None  # appointment/booking lifecycle status
    message: Optional[str] = None


class RazorpayOrderResponse(BaseModel):
    """Everything the future checkout step needs — and nothing more.

    amount is integer paise (e.g. Rs.500.00 -> 50000), matching the value
    stored on the Razorpay order itself.
    """

    key_id: str
    order_id: str
    amount: int
    currency: str

    # Context returned for verification-phase bookkeeping (safe to expose):
    # which domain object this order belongs to. No credentials, no internals.
    payable_type: Optional[str] = None  # "appointment" | "laboratory_booking"
    payable_id: Optional[str] = None
