from datetime import datetime, timedelta, time
from typing import List, Optional
from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.models.laboratory_test import LaboratoryTest
from app.models.laboratory_booking import LaboratoryBooking, EmbeddedTest
from app.repositories.laboratory_test_repository import LaboratoryTestRepository
from app.repositories.laboratory_booking_repository import LaboratoryBookingRepository
from app.models.user import User
from app.models.patient import Patient


class LaboratoryService:
    # Constants matching frontend
    ALLOWED_TIME_SLOTS = [
        '08:00 AM', '09:00 AM', '10:00 AM', '11:00 AM', '12:00 PM',
        '02:00 PM', '03:00 PM', '04:00 PM', '05:00 PM'
    ]
    DATE_RANGE_DAYS = 14  # Frontend allows next 14 days

    @staticmethod
    async def get_laboratory_tests() -> List[LaboratoryTest]:
        """Retrieve all active laboratory tests."""
        return await LaboratoryTestRepository.get_active_tests()

    @staticmethod
    async def validate_and_create_booking(
        patient_id: str,
        test_ids: List[str],
        appointment_date_str: str,
        time_slot: str,
        visit_type: str,
        address: Optional[str]
    ) -> LaboratoryBooking:
        """
        Validate booking request and create a new laboratory booking.
        Raises ValueError with descriptive message on validation failure.
        """
        # 1. Validate test_ids not empty
        if not test_ids:
            raise ValueError("At least one test must be selected")

        # 2. Validate no duplicate test IDs in request
        if len(test_ids) != len(set(test_ids)):
            raise ValueError("Duplicate test IDs are not allowed")

        # 3. Validate each test ID exists and is active
        tests = await LaboratoryTestRepository.get_by_test_ids(test_ids)
        found_test_ids = {t.test_id for t in tests}
        for test_id in test_ids:
            if test_id not in found_test_ids:
                raise ValueError(f"Test with ID '{test_id}' not found or inactive")

        # 4. Validate appointment date
        try:
            appointment_date = datetime.strptime(appointment_date_str, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format. Expected YYYY-MM-DD")

        # Normalize to start of day (00:00:00)
        appointment_date = datetime.combine(appointment_date.date(), time.min)
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, time.min)
        max_date = today_start + timedelta(days=LaboratoryService.DATE_RANGE_DAYS)

        if appointment_date < today_start:
            raise ValueError("Appointment date must be in the future")
        if appointment_date > max_date:
            raise ValueError(f"Appointment date must be within the next {LaboratoryService.DATE_RANGE_DAYS} days")

        # 5. Validate time slot
        if time_slot not in LaboratoryService.ALLOWED_TIME_SLOTS:
            raise ValueError(f"Invalid time slot. Allowed slots: {', '.join(LaboratoryService.ALLOWED_TIME_SLOTS)}")

        # 6. Validate visit type
        if visit_type not in ['home', 'clinic']:
            raise ValueError("Visit type must be either 'home' or 'clinic'")

        # 7. Validate address based on visit type
        if visit_type == 'home':
            if not address or not address.strip():
                raise ValueError("Address is required for home visits")
            address = address.strip()
        else:  # clinic
            address = None

        # 8. Check for conflicting booking (same patient, same date/time, pending or paid)
        conflicting = await LaboratoryBookingRepository.find_conflicting_booking(
            patient_id=patient_id,
            appointment_date=appointment_date,
            time_slot=time_slot
        )
        if conflicting:
            raise ValueError("You already have a pending or confirmed booking at this date and time")

        # 9. Create embedded test snapshots from authoritative catalog
        embedded_tests = []
        total_price = 0.0
        for test in tests:
            embedded_tests.append(EmbeddedTest(
                test_id=test.test_id,
                name=test.name,
                sample=test.sample,
                price=test.price
            ))
            total_price += test.price

        # 10. Create booking
        booking = LaboratoryBooking(
            patient_id=PydanticObjectId(patient_id),
            selected_tests=embedded_tests,
            visit_type=visit_type,
            appointment_date=appointment_date,
            time_slot=time_slot,
            address=address,
            billing_amount=total_price,
            billing_status="pending"
        )

        try:
            await LaboratoryBookingRepository.create(booking)
        except DuplicateKeyError:
            # Two truly concurrent requests can both pass the application-level
            # conflict check above; the partial unique index on laboratory_bookings
            # (patient_id, appointment_date, time_slot) makes the database the
            # final enforcement layer. Surface the same patient-facing conflict
            # message as the pre-insert check (the API maps ValueError → 400).
            raise ValueError("You already have a pending or confirmed booking at this date and time")

        # Notify patient
        try:
            patient = await Patient.get(PydanticObjectId(patient_id))
            if patient:
                from app.services.notification_service import NotificationService
                await NotificationService.create_notification(
                    recipient_user_id=str(patient.user_id),
                    title="Lab Test Booked",
                    message=f"Your laboratory booking for {len(embedded_tests)} tests is successfully scheduled on {appointment_date.strftime('%Y-%m-%d')} during the {time_slot} slot.",
                    notification_type="laboratory",
                    related_entity_id=str(booking.id)
                )
        except Exception as e:
            print(f"Failed to create laboratory booking notification: {e}")

        return booking

    @staticmethod
    async def get_bookings_by_patient_id(patient_id: str) -> List[LaboratoryBooking]:
        """
        Retrieve all bookings for the specified patient.
        """
        return await LaboratoryBookingRepository.get_by_patient_id(patient_id)

    @staticmethod
    async def get_booking_by_id(booking_id: str, patient_id: str) -> Optional[LaboratoryBooking]:
        """
        Retrieve a booking by ID, ensuring it belongs to the specified patient.
        Returns None if not found or access denied.
        """
        booking = await LaboratoryBookingRepository.get_by_id(booking_id)
        if not booking:
            return None
        if str(booking.patient_id) != patient_id:
            return None
        return booking

    @staticmethod
    async def update_payment(
        booking_id: str,
        patient_id: str,
        payment_method: str,
        payment_id: str,
        payment_order_id: str,
        payment_status: str
    ) -> Optional[LaboratoryBooking]:
        """
        Update payment status for a booking.
        Only allowed if booking is in pending_payment state.
        Returns updated booking or None if not found/access denied/invalid state.
        """
        booking = await LaboratoryBookingRepository.get_by_id(booking_id)
        if not booking:
            return None
        if str(booking.patient_id) != patient_id:
            return None
        if booking.billing_status != "pending":
            # Prevent updating payment on non-pending booking
            return None

        # Validate payment_status
        if payment_status not in ["success", "failed"]:
            return None

        # Update booking
        updated_booking = await LaboratoryBookingRepository.update_payment(
            booking_id=booking_id,
            payment_method=payment_method,
            payment_id=payment_id,
            payment_order_id=payment_order_id,
            payment_status=payment_status,
            billing_status="paid" if payment_status == "success" else "failed"
        )

        # Notify patient on payment update
        if updated_booking:
            try:
                patient = await Patient.get(PydanticObjectId(patient_id))
                if patient:
                    from app.services.notification_service import NotificationService
                    if payment_status == "success":
                        await NotificationService.create_notification(
                            recipient_user_id=str(patient.user_id),
                            title="Lab Payment Success",
                            message=f"Your payment of ₹{updated_booking.billing_amount} for your laboratory booking was successful.",
                            notification_type="laboratory",
                            related_entity_id=str(updated_booking.id)
                        )
                    else:
                        await NotificationService.create_notification(
                            recipient_user_id=str(patient.user_id),
                            title="Lab Payment Failed",
                            message=f"Your payment of ₹{updated_booking.billing_amount} for your laboratory booking has failed.",
                            notification_type="laboratory",
                            related_entity_id=str(updated_booking.id)
                        )
            except Exception as e:
                print(f"Failed to create laboratory payment notification: {e}")

        return updated_booking

    @staticmethod
    async def update_booking_status(
        booking_id: str,
        new_status: str
    ) -> Optional[LaboratoryBooking]:
        """
        Update the physical status of a booking with strict transition validation.
        Admin/Doctor authorized only.
        """
        booking = await LaboratoryBookingRepository.get_by_id(booking_id)
        if not booking:
            return None

        # Treat missing status field as pending_payment for backward compatibility
        current_status = getattr(booking, "status", "pending_payment") or "pending_payment"

        # Allowed transitions map
        allowed_transitions = {
            "pending_payment": ["confirmed", "failed", "cancelled"],
            "confirmed": ["completed", "cancelled"],
        }

        valid_targets = allowed_transitions.get(current_status, [])
        if new_status not in valid_targets:
            raise ValueError(f"Transition from '{current_status}' to '{new_status}' is not allowed.")

        # Update physical status
        booking.status = new_status
        await booking.save()

        # Notify patient on lifecycle milestones
        try:
            patient = await Patient.get(booking.patient_id)
            if patient:
                from app.services.notification_service import NotificationService
                if new_status == "completed":
                    await NotificationService.create_notification(
                        recipient_user_id=str(patient.user_id),
                        title="Lab Booking Completed",
                        message="Your laboratory booking has been completed.",
                        notification_type="laboratory",
                        related_entity_id=str(booking.id)
                    )
                elif new_status == "cancelled":
                    await NotificationService.create_notification(
                        recipient_user_id=str(patient.user_id),
                        title="Lab Booking Cancelled",
                        message="Your laboratory booking was cancelled.",
                        notification_type="laboratory",
                        related_entity_id=str(booking.id)
                    )
        except Exception as e:
            print(f"Failed to create status update notification: {e}")

        return booking