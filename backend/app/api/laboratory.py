from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models.user import User
from app.middleware.auth import RoleChecker
from app.schemas.laboratory_test import LaboratoryTestResponse, LaboratoryTestsResponse
from app.schemas.laboratory_booking import (
    LaboratoryBookingCreate,
    LaboratoryBookingResponse,
    LaboratoryBookingPaymentUpdate,
    LaboratoryBookingStatusUpdate
)
from app.services.laboratory_service import LaboratoryService
from app.core.pagination import DEFAULT_PAGE_SIZE, page_window


router = APIRouter(prefix="/laboratory", tags=["laboratory"])


def laboratory_booking_response(booking) -> LaboratoryBookingResponse:
    """Serialize the compatibility booking without provider identifiers."""
    return LaboratoryBookingResponse(
        id=str(booking.id),
        patient_id=str(booking.patient_id),
        selected_tests=[
            {
                "test_id": test.test_id,
                "name": test.name,
                "sample": test.sample,
                "price": test.price,
            }
            for test in booking.selected_tests
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
        created_at=booking.created_at,
    )


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

    return laboratory_booking_response(booking)


@router.get("/bookings", response_model=List[LaboratoryBookingResponse])
async def list_laboratory_bookings(
    current_user: User = Depends(RoleChecker(["patient"])),
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
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

    bookings = await LaboratoryService.get_bookings_by_patient_id(
        str(patient.id), page_window(page, page_size),
    )
    return [laboratory_booking_response(booking) for booking in bookings]


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

    return laboratory_booking_response(booking)


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

    return laboratory_booking_response(updated_booking)


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

    return laboratory_booking_response(updated_booking)
