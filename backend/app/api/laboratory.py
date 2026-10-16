from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models.user import User
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.laboratory_test import LaboratoryTestResponse, LaboratoryTestsResponse
from app.schemas.laboratory_booking import (
    LaboratoryBookingCreate,
    LaboratoryBookingResponse,
    LaboratoryBookingPaymentUpdate,
    LaboratoryBookingStatusUpdate
)
from app.schemas.payment import RazorpayOrderRequest, RazorpayOrderResponse, RazorpayVerifyRequest, RazorpayVerifyResponse
from app.services.laboratory_service import LaboratoryService
from app.services.payment_service import PaymentService
from app.models.laboratory_test import LaboratoryTest


router = APIRouter(prefix="/laboratory", tags=["laboratory"])


@router.get("/tests", response_model=LaboratoryTestsResponse)
async def get_laboratory_tests(
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """
    Get all active laboratory tests.
    """
    tests = await LaboratoryService.get_laboratory_tests()
    test_responses = [
        LaboratoryTestResponse(
            test_id=t.test_id,
            name=t.name,
            category=t.category,
            sample=t.sample,
            price=t.price
        ) for t in tests
    ]
    return LaboratoryTestsResponse(tests=test_responses)


@router.post("/bookings", response_model=LaboratoryBookingResponse, status_code=status.HTTP_201_CREATED)
async def create_laboratory_booking(
    booking_create: LaboratoryBookingCreate,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """
    Create a new laboratory booking.
    """
    # Get patient profile for the current user
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )

    try:
        booking = await LaboratoryService.validate_and_create_booking(
            patient_id=str(patient.id),
            test_ids=booking_create.test_ids,
            appointment_date_str=booking_create.appointment_date,
            time_slot=booking_create.time_slot,
            visit_type=booking_create.visit_type,
            address=booking_create.address
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Convert to response model
    return LaboratoryBookingResponse(
        id=str(booking.id),
        patient_id=str(booking.patient_id),
        selected_tests=[
            {
                "test_id": t.test_id,
                "name": t.name,
                "sample": t.sample,
                "price": t.price
            } for t in booking.selected_tests
        ],
        visit_type=booking.visit_type,
        appointment_date=booking.appointment_date,
        time_slot=booking.time_slot,
        address=booking.address,
        status=getattr(booking, "status", "pending_payment") or "pending_payment",
        billing_status=booking.billing_status,
        billing_amount=booking.billing_amount,
        payment_method=booking.payment_method,
        payment_status=booking.payment_status,
        payment_id=booking.payment_id,
        payment_order_id=booking.payment_order_id,
        created_at=booking.created_at
    )


@router.get("/bookings", response_model=List[LaboratoryBookingResponse])
async def list_laboratory_bookings(
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """
    Get all laboratory bookings for the authenticated patient.
    """
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )

    bookings = await LaboratoryService.get_bookings_by_patient_id(str(patient.id))
    return [
        LaboratoryBookingResponse(
            id=str(booking.id),
            patient_id=str(booking.patient_id),
            selected_tests=[
                {
                    "test_id": t.test_id,
                    "name": t.name,
                    "sample": t.sample,
                    "price": t.price
                } for t in booking.selected_tests
            ],
            visit_type=booking.visit_type,
            appointment_date=booking.appointment_date,
            time_slot=booking.time_slot,
            address=booking.address,
            status=getattr(booking, "status", "pending_payment") or "pending_payment",
            billing_status=booking.billing_status,
            billing_amount=booking.billing_amount,
            payment_method=booking.payment_method,
            payment_status=booking.payment_status,
            payment_id=booking.payment_id,
            payment_order_id=booking.payment_order_id,
            created_at=booking.created_at
        ) for booking in bookings
    ]


@router.get("/bookings/{booking_id}", response_model=LaboratoryBookingResponse)
async def get_laboratory_booking(
    booking_id: str,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """
    Get a laboratory booking by ID (patient-only access).
    """
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )

    booking = await LaboratoryService.get_booking_by_id(booking_id, str(patient.id))
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or access denied"
        )

    return LaboratoryBookingResponse(
        id=str(booking.id),
        patient_id=str(booking.patient_id),
        selected_tests=[
            {
                "test_id": t.test_id,
                "name": t.name,
                "sample": t.sample,
                "price": t.price
            } for t in booking.selected_tests
        ],
        visit_type=booking.visit_type,
        appointment_date=booking.appointment_date,
        time_slot=booking.time_slot,
        address=booking.address,
        status=getattr(booking, "status", "pending_payment") or "pending_payment",
        billing_status=booking.billing_status,
        billing_amount=booking.billing_amount,
        payment_method=booking.payment_method,
        payment_status=booking.payment_status,
        payment_id=booking.payment_id,
        payment_order_id=booking.payment_order_id,
        created_at=booking.created_at
    )


@router.post("/bookings/{booking_id}/payment/order", response_model=RazorpayOrderResponse)
async def create_laboratory_booking_payment_order(
    booking_id: str,
    body: RazorpayOrderRequest,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """Create (or reuse) the Razorpay order for this patient's lab booking.

    Backend-authoritative: the amount comes from the stored billing_amount
    (catalog-derived at booking time), never from the request body. Creating
    an order does not mark the booking as paid.
    """
    return await PaymentService.create_laboratory_booking_order(
        str(current_user.id), booking_id
    )


@router.post("/bookings/{booking_id}/payment/verify", response_model=RazorpayVerifyResponse)
async def verify_laboratory_booking_payment(
    booking_id: str,
    body: RazorpayVerifyRequest,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """Verify a laboratory booking's Razorpay payment server-side.

    Only the backend can transition billing_status to paid / status to
    confirmed. A Checkout callback alone is never treated as proof of payment.
    """
    return await PaymentService.verify_laboratory_payment(
        str(current_user.id), booking_id, body
    )


@router.patch("/bookings/{booking_id}/payment", response_model=LaboratoryBookingResponse)
async def update_laboratory_booking_payment(
    booking_id: str,
    payment_update: LaboratoryBookingPaymentUpdate,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """
    RETIRED (Phase 4, Task 11 — financial security hardening).

    This legacy endpoint accepted client-supplied payment_method / payment_id /
    payment_order_id / payment_status and wrote them to the booking WITHOUT any
    Razorpay verification — i.e. it could fabricate an online payment record.

    Inspection (Task 11) confirmed it has no legitimate current use:
      - no frontend caller exists anywhere in the codebase,
      - the operator patient-profile lookup always fails for admin/doctor
        users, so the endpoint could never have completed a mutation, and
      - the application has NO offline laboratory-payment workflow (laboratory
        bookings are created exclusively for online payment), so there is no
        legitimate offline behavior to preserve.

    The endpoint is therefore DISABLED: it always answers 403 and performs no
    reads or writes. It is intentionally kept registered (with its
    admin/doctor role gate) so the retired surface remains visible and the
    Task 5 lifecycle contract is unchanged.

    Online payment confirmation happens ONLY through the Razorpay-verified
    paths: POST /bookings/{id}/payment/verify (Task 4) and the payment.captured
    webhook reconciliation (Task 8).
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "This payment endpoint has been retired. Online payments are "
            "confirmed only through the verified Razorpay payment flow."
        ),
    )


@router.patch("/bookings/{booking_id}/status", response_model=LaboratoryBookingResponse)
async def update_laboratory_booking_status(
    booking_id: str,
    status_update: LaboratoryBookingStatusUpdate,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """
    Update the physical status of a laboratory booking.
    Restricted to admin and doctor roles.
    """
    try:
        updated_booking = await LaboratoryService.update_booking_status(
            booking_id=booking_id,
            new_status=status_update.status
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not updated_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )

    return LaboratoryBookingResponse(
        id=str(updated_booking.id),
        patient_id=str(updated_booking.patient_id),
        selected_tests=[
            {
                "test_id": t.test_id,
                "name": t.name,
                "sample": t.sample,
                "price": t.price
            } for t in updated_booking.selected_tests
        ],
        visit_type=updated_booking.visit_type,
        appointment_date=updated_booking.appointment_date,
        time_slot=updated_booking.time_slot,
        address=updated_booking.address,
        status=getattr(updated_booking, "status", "pending_payment") or "pending_payment",
        billing_status=updated_booking.billing_status,
        billing_amount=updated_booking.billing_amount,
        payment_method=updated_booking.payment_method,
        payment_status=updated_booking.payment_status,
        payment_id=updated_booking.payment_id,
        payment_order_id=updated_booking.payment_order_id,
        created_at=updated_booking.created_at
    )