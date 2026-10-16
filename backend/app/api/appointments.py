from fastapi import APIRouter, Depends, status
from typing import List
from app.models.user import User
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentOut
from app.schemas.payment import RazorpayOrderRequest, RazorpayOrderResponse, RazorpayVerifyRequest, RazorpayVerifyResponse
from app.services.appointment_service import AppointmentService
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/appointments", tags=["appointments"])

@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    schema: AppointmentCreate,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    return await AppointmentService.create_appointment(str(current_user.id), schema)

@router.get("", response_model=List[AppointmentOut])
async def list_appointments(
    current_user: User = Depends(get_current_user)
):
    return await AppointmentService.list_appointments(str(current_user.id), current_user.role)

@router.post("/{appointment_id}/payment/order", response_model=RazorpayOrderResponse)
async def create_appointment_payment_order(
    appointment_id: str,
    body: RazorpayOrderRequest,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """Create (or reuse) the Razorpay order for this patient's appointment.

    Backend-authoritative: the amount comes from the stored billing_amount,
    never from the request body. Creating an order does not mark the
    appointment as paid.
    """
    return await PaymentService.create_appointment_order(
        str(current_user.id), appointment_id
    )


@router.post("/{appointment_id}/payment/verify", response_model=RazorpayVerifyResponse)
async def verify_appointment_payment(
    appointment_id: str,
    body: RazorpayVerifyRequest,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """Verify an appointment's Razorpay payment server-side.

    Only the backend can transition the appointment to paid/confirmed. A
    Checkout callback alone is never treated as proof of payment.
    """
    return await PaymentService.verify_appointment_payment(
        str(current_user.id), appointment_id, body
    )


@router.patch("/{appointment_id}", response_model=AppointmentOut)
async def update_appointment(
    appointment_id: str,
    schema: AppointmentUpdate,
    current_user: User = Depends(RoleChecker(["admin", "doctor", "patient"]))
):
    return await AppointmentService.update_appointment(
        appointment_id,
        schema,
        current_user_role=current_user.role,
        current_user_id=str(current_user.id)
    )
