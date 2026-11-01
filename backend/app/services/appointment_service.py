from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError
from typing import List

from app.core.appointment_time import (
    AmbiguousLegacyAppointmentTime,
    active_slot_claim,
    booking_window,
    clinic_start_to_utc_naive,
    resolve_appointment_start_utc,
    validate_booking_date,
)
from app.core.config import settings
from app.models.appointment import Appointment
from app.models.payment_attempt import PaymentAttempt
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointment import (
    AdminAppointmentCreate,
    AppointmentAvailabilityOut,
    BookingWindowOut,
    AppointmentCreate,
    AppointmentSlotOut,
    AppointmentUpdate,
    AppointmentOut,
    ReceptionAppointmentCreate,
    ReceptionAppointmentOut,
)
from app.services.clinician_schedule_service import ClinicianScheduleService


class AppointmentService:
    @staticmethod
    def get_booking_window() -> BookingWindowOut:
        earliest, latest = booking_window()
        return BookingWindowOut(
            clinic_timezone=settings.CLINIC_TIMEZONE,
            earliest_date=earliest,
            latest_date=latest,
            horizon_days=settings.BOOKING_HORIZON_DAYS,
        )


    @staticmethod
    async def create_appointment(user_id: str, schema: AppointmentCreate) -> AppointmentOut:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        return await AppointmentService._create_for_patient(patient, schema)

    @staticmethod
    async def create_admin_appointment(schema: AdminAppointmentCreate) -> AppointmentOut:
        patient = await ProfileRepository.get_patient_by_id(schema.patient_id)

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        return await AppointmentService._create_for_patient(patient, schema)

    @staticmethod
    async def create_reception_appointment(
        schema: ReceptionAppointmentCreate,
    ) -> ReceptionAppointmentOut:
        patient = await ProfileRepository.get_patient_by_id(schema.patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        appointment = await AppointmentService._create_for_patient(
            patient,
            schema,
            reason="Reception booking; clinical reason not collected",
            format_output=False,
        )
        return await AppointmentService._format_reception_appointment(appointment)

    @staticmethod
    async def _create_for_patient(
        patient,
        schema,
        reason: str | None = None,
        format_output: bool = True,
    ):
        doctor = await ProfileRepository.get_doctor_by_id(schema.doctor_id)

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found",
            )

        starts_at, _published_schedule = await ClinicianScheduleService.validate_effective_slot(
            str(doctor.id), schema.appointment_date, schema.time_slot, "clinic"
        )

        if await AppointmentService._is_slot_occupied(str(doctor.id), starts_at):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That slot is already occupied for this physiotherapist. Choose another time.",
            )

        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=datetime.combine(schema.appointment_date, datetime.min.time()),
            starts_at=starts_at,
            slot_claim=active_slot_claim(str(doctor.id), starts_at),
            clinic_timezone=settings.CLINIC_TIMEZONE,
            billing_currency=settings.APPOINTMENT_BILLING_CURRENCY.strip().upper() or None,
            time_slot=schema.time_slot,
            reason=reason if reason is not None else schema.reason,
        )

        try:
            saved = await AppointmentRepository.create(appointment)
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That slot was just taken for this physiotherapist. Choose another time.",
            ) from exc

        if not format_output:
            return saved
        return await AppointmentService._format_appointment(saved)

    @staticmethod
    async def get_availability(doctor_id: str, appointment_date) -> AppointmentAvailabilityOut:
        try:
            validate_booking_date(appointment_date)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        doctor = await ProfileRepository.get_doctor_by_id(doctor_id)
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        appointments = await AppointmentRepository.list_active_by_doctor_id(doctor_id)
        occupied = set()
        for appointment in appointments:
            try:
                occupied.add(resolve_appointment_start_utc(appointment).replace(tzinfo=None))
            except (AmbiguousLegacyAppointmentTime, ValueError):
                continue

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        schedule_slots, published = await ClinicianScheduleService.effective_slots(doctor_id, appointment_date, "clinic")
        slots = []
        for time_slot in schedule_slots:
            starts_at = clinic_start_to_utc_naive(appointment_date, time_slot)
            if starts_at <= now_utc:
                availability_state = "past"
            elif starts_at in occupied:
                availability_state = "occupied"
            else:
                availability_state = "available"
            slots.append(AppointmentSlotOut(
                time_slot=time_slot,
                available=availability_state == "available",
                availability_state=availability_state,
            ))

        return AppointmentAvailabilityOut(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            clinic_timezone=settings.CLINIC_TIMEZONE,
            demo_configuration=not published,
            configuration_label=(
                "Administrator-published clinician schedule"
                if published
                else "Configurable demonstration schedule; not verified clinic or doctor working hours"
            ),
            slot_minutes=settings.DEMO_SLOT_MINUTES,
            window_start=schedule_slots[0] if schedule_slots else "Closed",
            window_end=schedule_slots[-1] if schedule_slots else "Closed",
            slots=slots,
        )

    @staticmethod
    async def _is_slot_occupied(
        doctor_id: str,
        starts_at: datetime,
        exclude_appointment_id: str | None = None,
    ) -> bool:
        appointments = await AppointmentRepository.list_active_by_doctor_id(doctor_id)
        for appointment in appointments:
            if exclude_appointment_id and str(appointment.id) == exclude_appointment_id:
                continue
            try:
                existing_start = resolve_appointment_start_utc(appointment).replace(tzinfo=None)
            except (AmbiguousLegacyAppointmentTime, ValueError):
                continue
            if existing_start == starts_at:
                return True
        return False

    @staticmethod
    async def list_appointments(user_id: str, role: str) -> List[AppointmentOut]:

        if role == "admin":
            appointments = await AppointmentRepository.list_all()

        elif role == "doctor":
            doctor = await ProfileRepository.get_doctor_by_user_id(user_id)

            if not doctor:
                return []

            appointments = [
                appointment
                for appointment in await AppointmentRepository.list_by_doctor_id(str(doctor.id))
                if not getattr(appointment, "doctor_assignment_pending", False)
            ]

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
    async def list_reception_schedule() -> List[ReceptionAppointmentOut]:
        appointments = await AppointmentRepository.list_operational_schedule()
        return [
            await AppointmentService._format_reception_appointment(appointment)
            for appointment in appointments
        ]

    @staticmethod
    async def update_appointment(
        appointment_id: str,
        schema: AppointmentUpdate,
        actor_user_id: str,
        actor_role: str,
    ) -> AppointmentOut:

        appointment = await AppointmentRepository.get_by_id(appointment_id)

        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        if actor_role == "doctor":
            doctor = await ProfileRepository.get_doctor_by_user_id(actor_user_id)
            if (
                not doctor
                or str(appointment.doctor_id) != str(doctor.id)
                or getattr(appointment, "doctor_assignment_pending", False)
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Appointment not found",
                )
            if schema.billing_status is not None or schema.billing_amount is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Doctors may update clinical appointment status only",
                )
        elif actor_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this role",
            )

        if schema.billing_status == "paid" and appointment.billing_status != "paid":
            verified_payment = await PaymentAttempt.find_one(
                {"appointment_id": appointment.id, "status": "success"}
            )
            if not verified_payment:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Appointment payments can be marked paid only after provider verification",
                )
        if schema.billing_amount is not None and schema.billing_amount != appointment.billing_amount:
            existing_payment = await PaymentAttempt.find_one({"appointment_id": appointment.id})
            if existing_payment:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The amount cannot change after payment setup has started",
                )

        if schema.status == "cancelled":
            if schema.billing_status is not None or schema.billing_amount is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cancel the appointment separately from billing changes",
                )
            if appointment.status == "cancelled":
                await AppointmentService._mark_cancelled_capture_for_reconciliation(appointment)
                return await AppointmentService._format_appointment(appointment)
            cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
            changed = await AppointmentRepository.cancel_from_status(
                appointment_id, appointment.status, cancelled_at
            )
            updated = await AppointmentRepository.get_by_id(appointment_id)
            if changed and updated and updated.status == "cancelled":
                await AppointmentService._mark_cancelled_capture_for_reconciliation(updated)
                return await AppointmentService._format_appointment(updated)
            if not updated:
                raise HTTPException(status_code=404, detail="Appointment not found")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The appointment changed before cancellation could be completed.",
            )

        if schema.status is not None:
            if schema.status in {"scheduled", "in_progress"}:
                try:
                    starts_at = resolve_appointment_start_utc(appointment).replace(tzinfo=None)
                except (AmbiguousLegacyAppointmentTime, ValueError) as exc:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="This appointment's clinic time cannot be reserved safely. Contact an administrator.",
                    ) from exc
                if await AppointmentService._is_slot_occupied(
                    str(appointment.doctor_id),
                    starts_at,
                    exclude_appointment_id=appointment_id,
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Another active appointment already occupies this physiotherapist's slot.",
                    )
                appointment.slot_claim = active_slot_claim(str(appointment.doctor_id), starts_at)
            else:
                appointment.slot_claim = None
            appointment.status = schema.status

        if schema.billing_status is not None:
            appointment.billing_status = schema.billing_status

        if schema.billing_amount is not None:
            appointment.billing_amount = schema.billing_amount

        try:
            await appointment.save()
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another active appointment already occupies this physiotherapist's slot.",
            ) from exc

        updated = await AppointmentRepository.get_by_id(appointment_id)

        return await AppointmentService._format_appointment(updated)

    @staticmethod
    async def cancel_patient_appointment(
        appointment_id: str,
        user_id: str,
        now: datetime | None = None,
    ) -> AppointmentOut:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        appointment = await AppointmentRepository.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )
        if str(appointment.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )
        if appointment.status == "cancelled":
            await AppointmentService._mark_cancelled_capture_for_reconciliation(appointment)
            return await AppointmentService._format_appointment(appointment)
        if appointment.status != "scheduled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=AppointmentService._status_cancellation_message(appointment.status),
            )

        try:
            starts_at = resolve_appointment_start_utc(appointment)
        except (AmbiguousLegacyAppointmentTime, ValueError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This appointment's clinic time cannot be verified for online cancellation. Contact the clinic for help.",
            )

        now_utc = now or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)
        deadline = starts_at - timedelta(hours=24)
        if now_utc > deadline:
            detail = (
                "This appointment has already started or passed. Contact the clinic if the record needs attention."
                if now_utc >= starts_at
                else "Online cancellation closes 24 hours before the appointment. Contact the clinic for late changes or emergencies."
            )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

        changed = await AppointmentRepository.cancel_scheduled_owned(
            appointment_id,
            str(patient.id),
            now_utc.replace(tzinfo=None),
        )
        updated = await AppointmentRepository.get_by_id(appointment_id)
        if changed or (updated and updated.status == "cancelled"):
            await AppointmentService._mark_cancelled_capture_for_reconciliation(updated)
            return await AppointmentService._format_appointment(updated)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=AppointmentService._status_cancellation_message(updated.status),
        )

    @staticmethod
    async def cancel_reception_appointment(
        appointment_id: str,
        now: datetime | None = None,
    ) -> ReceptionAppointmentOut:
        appointment = await AppointmentRepository.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        if appointment.status == "cancelled":
            await AppointmentService._mark_cancelled_capture_for_reconciliation(appointment)
            return await AppointmentService._format_reception_appointment(appointment)
        if appointment.status != "scheduled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reception may cancel only scheduled appointments.",
            )

        try:
            starts_at = resolve_appointment_start_utc(appointment)
        except (AmbiguousLegacyAppointmentTime, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This appointment's clinic time cannot be verified for cancellation. Ask an administrator for help.",
            ) from exc

        now_utc = now or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)
        if now_utc > starts_at - timedelta(hours=24):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reception cancellation follows the 24-hour cutoff. An approved staff override policy is not configured.",
            )

        changed = await AppointmentRepository.cancel_scheduled(
            appointment_id,
            now_utc.replace(tzinfo=None),
        )
        updated = await AppointmentRepository.get_by_id(appointment_id)
        if changed or (updated and updated.status == "cancelled"):
            await AppointmentService._mark_cancelled_capture_for_reconciliation(updated)
            return await AppointmentService._format_reception_appointment(updated)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment is no longer available for reception cancellation.",
        )

    @staticmethod
    async def _mark_cancelled_capture_for_reconciliation(appointment: Appointment) -> None:
        """Carry a previously verified provider capture onto the cancelled booking."""
        if (
            not appointment
            or appointment.status != "cancelled"
            or not getattr(appointment, "payment_order_id", None)
        ):
            return
        attempt = await PaymentAttempt.find_one(
            {"appointment_id": appointment.id, "status": "success"}
        )
        if attempt and attempt.provider_order_id and attempt.provider_payment_id:
            await AppointmentRepository.mark_cancelled_capture_for_reconciliation(
                str(appointment.id),
                attempt.provider_order_id,
                attempt.provider_payment_id,
                attempt.currency,
            )

    @staticmethod
    def _status_cancellation_message(appointment_status: str) -> str:
        messages = {
            "completed": "Completed appointments cannot be cancelled online.",
            "in_progress": "Appointments already in progress cannot be cancelled online. Contact the clinic for help.",
            "no_show": "Appointments marked as no-show cannot be cancelled online. Contact the clinic if the record needs attention.",
        }
        return messages.get(
            appointment_status,
            "This appointment cannot be cancelled online. Contact the clinic for help.",
        )

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

        starts_at = None
        cancellation_deadline = None
        can_patient_cancel = False
        cancellation_message = AppointmentService._status_cancellation_message(a.status)
        if a.status == "cancelled":
            cancellation_message = "This appointment is already cancelled."
        elif a.status == "scheduled":
            try:
                starts_at = resolve_appointment_start_utc(a)
                cancellation_deadline = starts_at - timedelta(hours=24)
                now_utc = datetime.now(timezone.utc)
                can_patient_cancel = now_utc <= cancellation_deadline
                if can_patient_cancel:
                    cancellation_message = "Online cancellation is available until 24 hours before the appointment."
                elif now_utc >= starts_at:
                    cancellation_message = "This appointment has already started or passed. Contact the clinic if the record needs attention."
                else:
                    cancellation_message = "Online cancellation has closed. Contact the clinic for late changes or emergencies."
            except (AmbiguousLegacyAppointmentTime, ValueError):
                cancellation_message = "This appointment's clinic time cannot be verified for online cancellation. Contact the clinic for help."

        assignment_pending = bool(getattr(a, "doctor_assignment_pending", False))
        return AppointmentOut(
            id=str(a.id),
            patient_id=str(patient.id),
            patient_name=patient_user.full_name,
            doctor_id="" if assignment_pending else str(doctor.id),
            doctor_name="Doctor assignment pending" if assignment_pending else doctor_user.full_name,
            doctor_assignment_pending=assignment_pending,
            appointment_date=a.appointment_date,
            starts_at=starts_at,
            clinic_timezone=a.clinic_timezone or settings.CLINIC_TIMEZONE,
            time_slot=a.time_slot,
            reason=a.reason,
            service_mode=getattr(a, "service_mode", "clinic"),
            home_address=getattr(a, "home_address", None),
            city=getattr(a, "city", None),
            body_regions=getattr(a, "body_regions", []),
            symptoms=getattr(a, "symptoms", []),
            duration_days=getattr(a, "duration_days", None),
            pain_severity=getattr(a, "pain_severity", None),
            status=a.status,
            billing_status=a.billing_status,
            billing_amount=a.billing_amount,
            billing_currency=getattr(a, "billing_currency", None),
            payment_status=getattr(a, "payment_status", "not_started"),
            payment_order_id=getattr(a, "payment_order_id", None),
            payment_id=getattr(a, "payment_id", None),
            cancelled_at=a.cancelled_at,
            can_patient_cancel=can_patient_cancel,
            cancellation_deadline=cancellation_deadline,
            cancellation_message=cancellation_message,
            created_at=a.created_at,
        )

    @staticmethod
    async def _format_reception_appointment(a: Appointment) -> ReceptionAppointmentOut:
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

        starts_at = None
        cancellation_deadline = None
        can_reception_cancel = False
        cancellation_message = "Reception may manage scheduled appointments only."
        if a.status == "cancelled":
            cancellation_message = "This appointment is already cancelled."
        elif a.status == "scheduled":
            try:
                starts_at = resolve_appointment_start_utc(a)
                cancellation_deadline = starts_at - timedelta(hours=24)
                can_reception_cancel = datetime.now(timezone.utc) <= cancellation_deadline
                cancellation_message = (
                    "Reception cancellation is available until 24 hours before the appointment."
                    if can_reception_cancel
                    else "The 24-hour cutoff has passed. No staff override policy is configured."
                )
            except (AmbiguousLegacyAppointmentTime, ValueError):
                cancellation_message = "This appointment's clinic time cannot be verified. Ask an administrator for help."

        assignment_pending = bool(getattr(a, "doctor_assignment_pending", False))
        return ReceptionAppointmentOut(
            id=str(a.id),
            patient_id=str(patient.id),
            patient_name=patient_user.full_name,
            patient_email=patient_user.email,
            patient_phone=patient.phone,
            doctor_id="" if assignment_pending else str(doctor.id),
            doctor_name="Doctor assignment pending" if assignment_pending else doctor_user.full_name,
            doctor_assignment_pending=assignment_pending,
            appointment_date=a.appointment_date,
            starts_at=starts_at,
            clinic_timezone=a.clinic_timezone or settings.CLINIC_TIMEZONE,
            time_slot=a.time_slot,
            service_mode=getattr(a, "service_mode", "clinic"),
            home_address=getattr(a, "home_address", None),
            city=getattr(a, "city", None),
            status=a.status,
            can_reception_cancel=can_reception_cancel,
            cancellation_deadline=cancellation_deadline,
            cancellation_message=cancellation_message,
        )
