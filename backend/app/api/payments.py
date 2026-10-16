from datetime import datetime, timezone

import razorpay

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.middleware.auth import RoleChecker
from app.models.appointment import Appointment
from app.models.user import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.appointment_service import AppointmentService
from app.schemas.appointment import AppointmentCreate


router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


# =========================================================
# REQUEST SCHEMAS
# =========================================================

class CreateOrderRequest(BaseModel):
    appointment: AppointmentCreate


class VerifyPaymentRequest(BaseModel):
    appointment: AppointmentCreate
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# =========================================================
# RAZORPAY CLIENT
# =========================================================

def get_razorpay_client():
    if (
        not settings.RAZORPAY_KEY_ID
        or not settings.RAZORPAY_KEY_SECRET
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Razorpay configuration is missing",
        )

    return razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )


# =========================================================
# CREATE RAZORPAY ORDER
# =========================================================

@router.post("/create-order")
async def create_order(
    data: CreateOrderRequest,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    """
    Create a Razorpay order.

    IMPORTANT:
    The appointment is NOT created here.

    Appointment creation happens only after
    successful payment verification.
    """

    # -----------------------------------------------------
    # Patient
    # -----------------------------------------------------

    patient = await ProfileRepository.get_patient_by_user_id(
        str(current_user.id)
    )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )

    # -----------------------------------------------------
    # Doctor
    # -----------------------------------------------------

    doctor = await ProfileRepository.get_doctor_by_id(
        data.appointment.doctor_id
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    # -----------------------------------------------------
    # Appointment date
    # -----------------------------------------------------

    appointment_date = data.appointment.appointment_date

    if appointment_date.tzinfo is None:
        appointment_date = appointment_date.replace(
            tzinfo=timezone.utc
        )

    if appointment_date < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment date must be in the future",
        )

    # -----------------------------------------------------
    # Doctor availability
    # -----------------------------------------------------

    doctor_busy = await AppointmentRepository.doctor_has_slot(
        str(doctor.id),
        appointment_date,
        data.appointment.time_slot,
    )

    if doctor_busy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor is not available for the selected time slot",
        )

    # -----------------------------------------------------
    # Patient availability
    # -----------------------------------------------------

    patient_busy = await AppointmentRepository.patient_has_slot(
        str(patient.id),
        appointment_date,
        data.appointment.time_slot,
    )

    if patient_busy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an appointment at this time",
        )

    # -----------------------------------------------------
    # Service availability
    # -----------------------------------------------------

    service_type = data.appointment.service_type

    if (
        service_type == "online"
        and not doctor.online_consultation_available
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Online consultation is not available for this doctor",
        )

    if (
        service_type == "home_visit"
        and not doctor.home_visit_available
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Home visit is not available for this doctor",
        )

    # -----------------------------------------------------
    # Server-side amount
    # -----------------------------------------------------

    consultation_fee = float(
        doctor.consultation_fee or 500.0
    )

    amount_in_paise = int(
        round(consultation_fee * 100)
    )

    if amount_in_paise <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid consultation fee",
        )

    # -----------------------------------------------------
    # Razorpay order
    # -----------------------------------------------------

    client = get_razorpay_client()

    try:
        order = client.order.create(
            {
                "amount": amount_in_paise,
                "currency": "INR",
                "payment_capture": 1,
                "notes": {
                    "patient_id": str(patient.id),
                    "doctor_id": str(doctor.id),
                    "service_type": service_type,
                    "appointment_date": appointment_date.isoformat(),
                    "time_slot": data.appointment.time_slot,
                },
            }
        )

    except Exception as exc:
        print(f"Razorpay order creation failed: {exc}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create Razorpay order",
        )

    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "key_id": settings.RAZORPAY_KEY_ID,
    }


# =========================================================
# VERIFY RAZORPAY PAYMENT
# =========================================================

@router.post("/verify")
async def verify_payment(
    data: VerifyPaymentRequest,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    """
    Verify Razorpay payment and create the appointment.

    The appointment is created ONLY after:
    1. Razorpay signature verification succeeds.
    2. Payment belongs to the requested order.
    3. Payment amount matches the doctor's fee.
    4. Payment status is captured.
    5. Appointment slot is still available.
    """

    # -----------------------------------------------------
    # Get Razorpay client
    # -----------------------------------------------------

    client = get_razorpay_client()

    # -----------------------------------------------------
    # Get patient
    # -----------------------------------------------------

    patient = await ProfileRepository.get_patient_by_user_id(
        str(current_user.id)
    )

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )

    # -----------------------------------------------------
    # Get doctor
    # -----------------------------------------------------

    doctor = await ProfileRepository.get_doctor_by_id(
        data.appointment.doctor_id
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    # -----------------------------------------------------
    # Verify Razorpay signature
    # -----------------------------------------------------

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": data.razorpay_order_id,
                "razorpay_payment_id": data.razorpay_payment_id,
                "razorpay_signature": data.razorpay_signature,
            }
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature verification failed",
        )

    # -----------------------------------------------------
    # Fetch payment from Razorpay
    # -----------------------------------------------------

    try:
        payment = client.payment.fetch(
            data.razorpay_payment_id
        )

    except Exception as exc:
        print(f"Unable to fetch Razorpay payment: {exc}")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to verify Razorpay payment",
        )

    # -----------------------------------------------------
    # Make sure payment belongs to our order
    # -----------------------------------------------------

    if payment.get("order_id") != data.razorpay_order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment does not belong to this order",
        )

    # -----------------------------------------------------
    # Get doctor's actual fee
    # -----------------------------------------------------

    consultation_fee = float(
        doctor.consultation_fee or 500.0
    )

    expected_amount = int(
        round(consultation_fee * 100)
    )

    # -----------------------------------------------------
    # Verify payment amount
    # -----------------------------------------------------

    if int(payment.get("amount", 0)) != expected_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount does not match appointment fee",
        )

    # -----------------------------------------------------
    # Payment must be captured
    # -----------------------------------------------------

    if payment.get("status") != "captured":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Payment is not captured. "
                f"Current status: {payment.get('status')}"
            ),
        )

    # -----------------------------------------------------
    # Prevent duplicate payment processing
    # -----------------------------------------------------

    existing_payment = await Appointment.find_one(
        Appointment.payment_id == data.razorpay_payment_id
    )

    if existing_payment:
        return await AppointmentService._format_appointment(
            existing_payment
        )

    # -----------------------------------------------------
    # Normalize appointment date
    # -----------------------------------------------------

    appointment_date = data.appointment.appointment_date

    if appointment_date.tzinfo is None:
        appointment_date = appointment_date.replace(
            tzinfo=timezone.utc
        )

    # -----------------------------------------------------
    # Re-check doctor slot
    # -----------------------------------------------------

    doctor_busy = await AppointmentRepository.doctor_has_slot(
        str(doctor.id),
        appointment_date,
        data.appointment.time_slot,
    )

    if doctor_busy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor is no longer available for this time slot",
        )

    # -----------------------------------------------------
    # Re-check patient slot
    # -----------------------------------------------------

    patient_busy = await AppointmentRepository.patient_has_slot(
        str(patient.id),
        appointment_date,
        data.appointment.time_slot,
    )

    if patient_busy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an appointment at this time",
        )

    # -----------------------------------------------------
    # Service availability
    # -----------------------------------------------------

    service_type = data.appointment.service_type

    if (
        service_type == "online"
        and not doctor.online_consultation_available
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Online consultation is not available for this doctor",
        )

    if (
        service_type == "home_visit"
        and not doctor.home_visit_available
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Home visit is not available for this doctor",
        )

    # -----------------------------------------------------
    # Create appointment AFTER successful payment
    # -----------------------------------------------------

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        service_type=service_type,
        appointment_date=appointment_date,
        time_slot=data.appointment.time_slot,
        reason=data.appointment.reason,
        symptoms=data.appointment.symptoms,
        duration_days=data.appointment.duration_days,
        pain_level=data.appointment.pain_level,
        visit_address=data.appointment.visit_address,

        # Our new consistent lifecycle
        status="confirmed",

        # Payment information
        billing_status="paid",
        billing_amount=consultation_fee,
        payment_method="online",
        payment_status="paid",
        payment_id=data.razorpay_payment_id,
    )

    saved = await AppointmentRepository.create(
        appointment
    )

    return await AppointmentService._format_appointment(saved)