from datetime import datetime, timezone
from fastapi import HTTPException, status
from typing import List

from app.models.appointment import Appointment
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentOut,
)


class AppointmentService:

    @staticmethod
    async def create_appointment(
        user_id: str,
        schema: AppointmentCreate,
    ) -> AppointmentOut:

        patient = await ProfileRepository.get_patient_by_user_id(user_id)

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        doctor = await ProfileRepository.get_doctor_by_id(schema.doctor_id)

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found",
            )

    # Prevent booking appointments in the past
        appointment_date = schema.appointment_date

        if appointment_date.tzinfo is None:
            appointment_date = appointment_date.replace(tzinfo=timezone.utc)

        if appointment_date < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment date must be in the future",
            )

    # Doctor availability
        doctor_busy = await AppointmentRepository.doctor_has_slot(
            str(doctor.id),
            appointment_date,
            schema.time_slot,
        )

        if doctor_busy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is not available for the selected time slot",
            )

    # Patient availability
        patient_busy = await AppointmentRepository.patient_has_slot(
            str(patient.id),
            schema.appointment_date,
            schema.time_slot,
        )

        if patient_busy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an appointment at this time",
            )

        payment_method = (schema.payment_method or "offline").lower()

        if payment_method == "online":
            appointment_status = "pending_payment"
        else:
            appointment_status = "confirmed"

        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            service_type=schema.service_type,
            appointment_date=schema.appointment_date,
            time_slot=schema.time_slot,
            reason=schema.reason,
            symptoms=schema.symptoms,
            duration_days=schema.duration_days,
            pain_level=schema.pain_level,
            visit_address=schema.visit_address,
            status=appointment_status,
            billing_status="pending",
            # The doctor profile is the authoritative price source. The Review
            # screen reads consultation_fee from the same profile, so the
            # displayed amount and the stored billing amount always agree.
            billing_amount=float(doctor.consultation_fee),
            payment_method=payment_method,
            payment_status="pending",
        )

        # The unique patient/date/slot index makes this insert the final
        # concurrency authority. Two racing requests: exactly one wins, the
        # loser gets a safe conflict response instead of a 500.
        saved = await AppointmentRepository.create_safely(appointment)

        if saved is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an appointment at this date and time",
            )

        # Notify patient and doctor
        try:
            from app.services.notification_service import NotificationService
            patient_user = await UserRepository.get_by_id(str(patient.user_id))
            doctor_user = await UserRepository.get_by_id(str(doctor.user_id))
            if patient_user and doctor_user:
                # Patient notification
                await NotificationService.create_notification(
                    recipient_user_id=str(patient.user_id),
                    title="Appointment Booked",
                    message=f"Your appointment for {schema.service_type.replace('_', ' ')} with Dr. {doctor_user.full_name} is successfully scheduled on {schema.appointment_date.strftime('%Y-%m-%d')} at {schema.time_slot}.",
                    notification_type="appointment",
                    related_entity_id=str(saved.id)
                )
                # Doctor notification
                await NotificationService.create_notification(
                    recipient_user_id=str(doctor.user_id),
                    title="New Appointment Scheduled",
                    message=f"A new {schema.service_type.replace('_', ' ')} appointment has been booked by {patient_user.full_name} for {schema.appointment_date.strftime('%Y-%m-%d')} at {schema.time_slot}.",
                    notification_type="appointment",
                    related_entity_id=str(saved.id)
                )
        except Exception as e:
            print(f"Failed to create appointment notification: {e}")

        return await AppointmentService._format_appointment(saved)

    @staticmethod
    async def list_appointments(user_id: str, role: str) -> List[AppointmentOut]:

        if role == "admin":
            appointments = await AppointmentRepository.list_all()

        elif role == "doctor":
            doctor = await ProfileRepository.get_doctor_by_user_id(user_id)

            if not doctor:
                return []

            appointments = await AppointmentRepository.list_by_doctor_id(str(doctor.id))

        elif role == "patient":
            patient = await ProfileRepository.get_patient_by_user_id(user_id)

            if not patient:
                return []

            appointments = await AppointmentRepository.list_by_patient_id(str(patient.id))

        else:
            appointments = []

        result = []

        for appointment in appointments:
            result.append(await AppointmentService._format_appointment(appointment))

        return result

    @staticmethod
    async def update_appointment(
        appointment_id: str,
        schema: AppointmentUpdate,
        current_user_role: str = "admin",
        current_user_id: str = None
    ) -> AppointmentOut:

        appointment = await AppointmentRepository.get_by_id(appointment_id)

        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        if current_user_role == "patient":
            # Authenticated patient ownership verification
            patient = await ProfileRepository.get_patient_by_user_id(current_user_id)
            if not patient or str(appointment.patient_id) != str(patient.id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Appointment not found",
                )

            update_data = schema.model_dump(exclude_unset=True)
            modified_fields = set(update_data.keys())

            is_cancellation = modified_fields == {"status"} and schema.status == "cancelled"
            allowed_reschedule_fields = {"appointment_date", "time_slot"}
            is_rescheduling = modified_fields.issubset(allowed_reschedule_fields) and modified_fields

            if not is_cancellation and not is_rescheduling:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Patients are only permitted to cancel or reschedule their own appointments.",
                )

            if is_cancellation:
                # Valid cancellation states check: completed, cancelled, no_show cannot be cancelled
                if appointment.status in ["completed", "cancelled", "no_show"]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot cancel an appointment that is already completed or cancelled.",
                    )
            elif is_rescheduling:
                # Valid rescheduling states check: completed, cancelled, no_show cannot be rescheduled
                if appointment.status in ["completed", "cancelled", "no_show"]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot reschedule an appointment that is completed, cancelled, or marked as no-show.",
                    )

                # Date & slot validation
                from datetime import timezone
                new_date = schema.appointment_date or appointment.appointment_date
                new_slot = schema.time_slot or appointment.time_slot

                if new_date.tzinfo is None:
                    new_date = new_date.replace(tzinfo=timezone.utc)

                if new_date < datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Appointment date must be in the future",
                    )

                # Doctor existence & association
                doctor = await ProfileRepository.get_doctor_by_id(str(appointment.doctor_id))
                if not doctor:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Associated doctor not found",
                    )

                # Availability slot verification with self-exclusion
                doctor_busy = await AppointmentRepository.doctor_has_slot(
                    str(doctor.id),
                    new_date,
                    new_slot,
                    exclude_appointment_id=str(appointment.id)
                )
                if doctor_busy:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Doctor is not available for the selected time slot",
                    )

                patient_busy = await AppointmentRepository.patient_has_slot(
                    str(patient.id),
                    new_date,
                    new_slot,
                    exclude_appointment_id=str(appointment.id)
                )
                if patient_busy:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="You already have an appointment at this time",
                    )

        old_status = appointment.status
        old_date = appointment.appointment_date
        old_slot = appointment.time_slot

        if schema.status is not None:
            appointment.status = schema.status

        if schema.appointment_date is not None:
            appointment.appointment_date = schema.appointment_date

        if schema.time_slot is not None:
            appointment.time_slot = schema.time_slot

        # -----------------------------------------------------------------
        # Billing mutation guards (Phase 4, Task 11).
        #
        # Admin/doctor may keep the LEGITIMATE OFFLINE billing workflow
        # (marking an offline appointment's billing record as paid/failed),
        # but a generic PATCH must never fabricate an ONLINE payment or
        # silently change the amount of an in-flight online payment:
        #
        # 1. billing_status="paid" (or payment-success semantics) is only
        #    accepted for OFFLINE appointments (payment_method != "online").
        #    Online appointments confirm exclusively through the        #    Razorpay-verified paths (Task 4 verification / Task 8 webhook),
        #    both of which use atomic guarded transitions that a generic
        #    PATCH cannot reproduce.
        # 2. billing_amount changes are rejected once a Razorpay order has
        #    been atomically bound (payment_order_id set): the bound order's
        #    amount is the financial truth and must not diverge from the
        #    stored billing_amount.
        # -----------------------------------------------------------------
        if schema.billing_status is not None:
            if (
                schema.billing_status == "paid"
                and (appointment.payment_method or "").lower() == "online"
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Online payments are confirmed only through the "
                        "verified Razorpay payment flow"
                    ),
                )
            appointment.billing_status = schema.billing_status

        if schema.billing_amount is not None:
            if appointment.payment_order_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The billing amount cannot be changed after a "
                        "payment order has been created"
                    ),
                )
            appointment.billing_amount = schema.billing_amount

        await appointment.save()

        # Notify patient on status change
        if schema.status is not None and schema.status != old_status:
            try:
                from app.services.notification_service import NotificationService
                patient_profile = await ProfileRepository.get_patient_by_id(str(appointment.patient_id))
                if patient_profile:
                    status_text = schema.status.replace('_', ' ').capitalize()
                    await NotificationService.create_notification(
                        recipient_user_id=str(patient_profile.user_id),
                        title=f"Appointment {status_text}",
                        message=f"Your appointment scheduled for {appointment.appointment_date.strftime('%Y-%m-%d')} has been marked as {schema.status.replace('_', ' ')}.",
                        notification_type="appointment",
                        related_entity_id=str(appointment.id)
                    )
            except Exception as e:
                print(f"Failed to create appointment status update notification: {e}")

        # Notify patient and doctor on rescheduling
        if (schema.appointment_date is not None or schema.time_slot is not None) and (schema.appointment_date != old_date or schema.time_slot != old_slot):
            try:
                from app.services.notification_service import NotificationService
                patient_profile = await ProfileRepository.get_patient_by_id(str(appointment.patient_id))
                doctor_profile = await ProfileRepository.get_doctor_by_id(str(appointment.doctor_id))
                if patient_profile and doctor_profile:
                    patient_user = await UserRepository.get_by_id(str(patient_profile.user_id))
                    doctor_user = await UserRepository.get_by_id(str(doctor_profile.user_id))
                    if patient_user and doctor_user:
                        date_str = appointment.appointment_date.strftime('%Y-%m-%d')
                        # Patient notification
                        await NotificationService.create_notification(
                            recipient_user_id=str(patient_profile.user_id),
                            title="Appointment Rescheduled",
                            message=f"Your appointment with Dr. {doctor_user.full_name} has been rescheduled to {date_str} at {appointment.time_slot}.",
                            notification_type="appointment",
                            related_entity_id=str(appointment.id)
                        )
                        # Doctor notification
                        await NotificationService.create_notification(
                            recipient_user_id=str(doctor_profile.user_id),
                            title="Appointment Rescheduled",
                            message=f"Your appointment with {patient_user.full_name} has been rescheduled to {date_str} at {appointment.time_slot}.",
                            notification_type="appointment",
                            related_entity_id=str(appointment.id)
                        )
            except Exception as e:
                print(f"Failed to create reschedule notification: {e}")

        updated = await AppointmentRepository.get_by_id(appointment_id)

        return await AppointmentService._format_appointment(updated)

    @staticmethod
    async def _format_appointment(a: Appointment) -> AppointmentOut:

        patient = await ProfileRepository.get_patient_by_id(str(a.patient_id))
        doctor = await ProfileRepository.get_doctor_by_id(str(a.doctor_id))

        if not patient or not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Related patient or doctor not found",
            )

        patient_user = await UserRepository.get_by_id(str(patient.user_id))
        doctor_user = await UserRepository.get_by_id(str(doctor.user_id))

        if not patient_user or not doctor_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Related user not found",
            )

        return AppointmentOut(
            id=str(a.id),

            patient_id=str(patient.id),
            patient_name=patient_user.full_name,

            doctor_id=str(doctor.id),
            doctor_name=doctor_user.full_name,
            specialization=doctor.specialization,

            service_type=a.service_type,

            appointment_date=a.appointment_date,
            time_slot=a.time_slot,

            reason=a.reason,
            symptoms=a.symptoms,
            duration_days=a.duration_days,
            pain_level=a.pain_level,

            visit_address=a.visit_address,

            status=a.status,

            billing_status=a.billing_status,
            billing_amount=a.billing_amount,

            payment_method=a.payment_method,
            payment_status=a.payment_status,
            payment_id=a.payment_id,
            payment_order_id=a.payment_order_id,

            meeting_link=a.meeting_link,

            feedback_rating=a.feedback_rating,
            feedback_comment=a.feedback_comment,

            created_at=a.created_at,
        )