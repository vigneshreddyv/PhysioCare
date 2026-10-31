from fastapi import APIRouter, Depends, Header, Request

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


router = APIRouter(tags=["payments"])


@router.get("/payments/history", response_model=list[PaymentHistoryItemOut])
async def list_patient_payment_history(
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await PaymentService.get_patient_payment_history(str(current_user.id))


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
    raw_body = await request.body()
    return await PaymentService.handle_webhook(raw_body, signature, event_id)
