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
from app.services.laboratory_service import LaboratoryService
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


@router.patch("/bookings/{booking_id}/payment", response_model=LaboratoryBookingResponse)
async def update_laboratory_booking_payment(
    booking_id: str,
    payment_update: LaboratoryBookingPaymentUpdate,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """
    Update payment status for a laboratory booking.
    """
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )

    updated_booking = await LaboratoryService.update_payment(
        booking_id=booking_id,
        patient_id=str(patient.id),
        payment_method=payment_update.payment_method,
        payment_id=payment_update.payment_id,
        payment_order_id=payment_update.payment_order_id,
        payment_status=payment_update.payment_status
    )
    if not updated_booking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking, payment update not allowed, or access denied"
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
            new_status=status_update.status,
            actor_user_id=str(current_user.id),
            actor_role=current_user.role,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        ) from None
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
