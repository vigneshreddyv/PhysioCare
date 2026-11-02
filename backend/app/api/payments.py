from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.middleware.auth import RoleChecker
from app.models.user import User
from app.schemas.payment import (
    CapturedPaymentReconciliationOut,
    CapturedPaymentReviewListOut,
    CheckoutVerification,
    PaymentHistoryItemOut,
    PaymentOrderOut,
    PaymentReadinessOut,
    PaymentStatusOut,
    PaymentVerificationOut,
)
from app.services.payment_service import PaymentService
from app.core.pagination import DEFAULT_PAGE_SIZE, page_window
from app.core.request_limits import (
    MAX_RAZORPAY_EVENT_ID_CHARS,
    MAX_RAZORPAY_SIGNATURE_CHARS,
    MAX_RAZORPAY_WEBHOOK_BYTES,
    read_bounded_body,
)


router = APIRouter(tags=["payments"])


@router.get("/payments/history", response_model=list[PaymentHistoryItemOut])
async def list_patient_payment_history(
    current_user: User = Depends(RoleChecker(["patient"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    payment_status: Literal[
        "creating", "pending", "success", "failed", "cancelled", "abandoned"
    ] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Invalid payment-history date range")
    return await PaymentService.get_patient_payment_history(
        str(current_user.id),
        page_window(page, page_size),
        payment_status=payment_status,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/payments/readiness", response_model=PaymentReadinessOut)
async def get_payment_readiness(
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return PaymentService.readiness()


@router.post("/appointments/{appointment_id}/payments/order", response_model=PaymentOrderOut)
async def create_appointment_payment_order(
    appointment_id: str,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await PaymentService.create_order(appointment_id, str(current_user.id))


@router.post("/appointments/{appointment_id}/payments/verify", response_model=PaymentVerificationOut)
async def verify_appointment_payment(
    appointment_id: str,
    payload: CheckoutVerification,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await PaymentService.verify_checkout(appointment_id, str(current_user.id), payload.model_dump())


@router.get("/appointments/{appointment_id}/payments", response_model=PaymentStatusOut)
async def get_appointment_payment_status(
    appointment_id: str,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await PaymentService.get_status(appointment_id, str(current_user.id))


@router.post("/appointments/{appointment_id}/payments/abandon", response_model=PaymentStatusOut)
async def abandon_appointment_checkout(
    appointment_id: str,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await PaymentService.abandon_checkout(appointment_id, str(current_user.id))


@router.post("/payments/admin/reconcile-captured", response_model=CapturedPaymentReconciliationOut)
async def reconcile_captured_payments(
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await PaymentService.reconcile_captured_payments(include_clinic_review=True)


@router.get("/payments/admin/captured-review", response_model=CapturedPaymentReviewListOut)
async def list_captured_payment_reviews(
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await PaymentService.list_captured_payment_reviews()


@router.post("/appointments/{appointment_id}/payments/cancel", response_model=PaymentStatusOut)
async def cancel_appointment_checkout(
    appointment_id: str,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await PaymentService.cancel_checkout(appointment_id, str(current_user.id))


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
    event_id: str | None = Header(default=None, alias="X-Razorpay-Event-Id"),
):
    if not signature or not event_id:
        raise HTTPException(status_code=400, detail="Webhook signature and event ID are required")
    if (
        len(signature) > MAX_RAZORPAY_SIGNATURE_CHARS
        or len(event_id) > MAX_RAZORPAY_EVENT_ID_CHARS
    ):
        raise HTTPException(status_code=400, detail="Webhook headers are invalid")
    raw_body = await read_bounded_body(request, MAX_RAZORPAY_WEBHOOK_BYTES)
    return await PaymentService.handle_webhook(raw_body, signature, event_id)
