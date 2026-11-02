from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

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
from app.core.pagination import PageWindow
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.user import User
from app.models.payment_attempt import PaymentAttempt
from app.repositories.appointment_repository import (
    AppointmentMutationConflict,
    AppointmentRepository,
)
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
from app.schemas.home_visit import AdminHomeVisitBookingOut
from app.services.clinician_schedule_service import ClinicianScheduleService


class AppointmentService:
    @staticmethod
    async def _page_profile_maps(
        appointments: list,
        doctor_field: str = "doctor_id",
        *,
        include_patient_phone: bool = False,
        include_patient_email: bool = False,
    ):
        """Fetch only the identity fields needed to format one authorized page."""
        if not appointments:
            return {}, {}, {}
        patient_ids = list({item.patient_id for item in appointments})
        doctor_ids = list({getattr(item, doctor_field) for item in appointments})
        patient_projection = {"user_id": 1}
        if include_patient_phone:
            patient_projection["phone"] = 1
        patients = await Patient.get_pymongo_collection().find(
            {"_id": {"$in": patient_ids}}, patient_projection,
        ).to_list(length=len(patient_ids))
        doctors = await Doctor.get_pymongo_collection().find(
            {"_id": {"$in": doctor_ids}}, {"user_id": 1},
        ).to_list(length=len(doctor_ids))
        patient_user_ids = list({row["user_id"] for row in patients})
        doctor_user_ids = list({row["user_id"] for row in doctors})
        user_projection = {"full_name": 1}
        if include_patient_email:
            user_projection["email"] = 1
        patient_users = await User.get_pymongo_collection().find(
            {"_id": {"$in": patient_user_ids}}, user_projection,
        ).to_list(length=len(patient_user_ids)) if patient_user_ids else []
        patient_user_id_set = set(patient_user_ids)
        doctor_only_user_ids = [item for item in doctor_user_ids if item not in patient_user_id_set]
        doctor_users = await User.get_pymongo_collection().find(
            {"_id": {"$in": doctor_only_user_ids}}, {"full_name": 1},
        ).to_list(length=len(doctor_only_user_ids)) if doctor_only_user_ids else []
        users = patient_users + doctor_users
        return (
            {row["_id"]: SimpleNamespace(id=row["_id"], user_id=row["user_id"],
                                          phone=row.get("phone")) for row in patients},
            {row["_id"]: SimpleNamespace(id=row["_id"], user_id=row["user_id"])
             for row in doctors},
            {row["_id"]: SimpleNamespace(id=row["_id"], full_name=row["full_name"],
                                          email=row.get("email")) for row in users},
        )

    @staticmethod
    async def _format_appointment_page(appointments: list) -> list[AppointmentOut]:
        if not appointments:
            return []
        patients, doctors, users = await AppointmentService._page_profile_maps(appointments)
        result = []
        for appointment in appointments:
            patient = patients.get(appointment.patient_id)
            doctor = doctors.get(appointment.doctor_id)
            patient_user = users.get(patient.user_id) if patient else None
            doctor_user = users.get(doctor.user_id) if doctor else None
            if not all((patient, doctor, patient_user, doctor_user)):
                raise HTTPException(status_code=404, detail="Related patient or doctor not found")
            result.append(await AppointmentService._format_appointment(
                appointment,
                patient=patient,
                doctor=doctor,
                patient_user=patient_user,
                doctor_user=doctor_user,
            ))
        return result

    @staticmethod
    async def doctor_dashboard_summary(user_id: str) -> dict[str, int]:
        doctor = await ProfileRepository.get_doctor_by_user_id(user_id)
        if not doctor:
            return {"open_visits": 0, "completed_sessions": 0, "assigned_patients": 0}
        return await AppointmentRepository.doctor_dashboard_summary(str(doctor.id))

    @staticmethod
    async def reception_schedule_summary(
        start_date: date | None = None, end_date: date | None = None,
    ) -> dict[str, int]:
        return await AppointmentRepository.reception_schedule_summary(start_date, end_date)
    @staticmethod
    async def list_scheduled_home_visits(page: PageWindow) -> list[AdminHomeVisitBookingOut]:
        rows = await AppointmentRepository.list_page_scheduled_home_visits(page)
        return [AdminHomeVisitBookingOut(
            id=str(row["_id"]), patient_name=row["patient_name"],
            doctor_id="" if row.get("doctor_assignment_pending") else str(row["doctor_id"]),
            doctor_assignment_pending=bool(row.get("doctor_assignment_pending")),
            appointment_date=row["appointment_date"], time_slot=row["time_slot"],
        ) for row in rows]
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

        appointments = await AppointmentRepository.list_active_by_doctor_id(
            doctor_id, appointment_date, appointment_date,
        )
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
            demo_configuration=not published and bool(schedule_slots),
            configuration_label=(
                "Administrator-published clinician schedule"
                if published
                else "Configurable demonstration schedule; not verified clinic or doctor working hours"
                if schedule_slots
                else "No published clinician schedule is available"
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
        clinic_date = starts_at.replace(tzinfo=timezone.utc).astimezone(
            ZoneInfo(settings.CLINIC_TIMEZONE)
        ).date()
        appointments = await AppointmentRepository.list_active_by_doctor_id(
            doctor_id, clinic_date, clinic_date,
        )
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
    async def list_appointments(
        user_id: str, role: str, page: PageWindow | None = None,
        *, statuses: list[str] | None = None,
        start_date: date | None = None, end_date: date | None = None,
    ) -> List[AppointmentOut]:

        if role == "admin":
            appointments = (
                await AppointmentRepository.list_page_all(page)
                if page is not None else await AppointmentRepository.list_all()
            )

        elif role == "doctor":
            doctor = await ProfileRepository.get_doctor_by_user_id(user_id)

            if not doctor:
                return []

            if page is not None:
                if statuses or start_date or end_date:
                    appointments = await AppointmentRepository.list_page_by_doctor_id(
                        str(doctor.id), page, statuses, start_date, end_date,
                    )
                else:
                    appointments = await AppointmentRepository.list_page_by_doctor_id(str(doctor.id), page)
            else:
                appointments = [
                    appointment
                    for appointment in await AppointmentRepository.list_by_doctor_id(str(doctor.id))
                    if not getattr(appointment, "doctor_assignment_pending", False)
                ]

        elif role == "patient":
            patient = await ProfileRepository.get_patient_by_user_id(user_id)

            if not patient:
                return []

            appointments = (
                await AppointmentRepository.list_page_by_patient_id(str(patient.id), page)
                if page is not None else await AppointmentRepository.list_by_patient_id(str(patient.id))
            )

        else:
            appointments = []

        if page is not None:
            return await AppointmentService._format_appointment_page(appointments)
        return [await AppointmentService._format_appointment(item) for item in appointments]

    @staticmethod
    async def get_patient_appointment(appointment_id: str, user_id: str) -> AppointmentOut:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        appointment = await AppointmentRepository.get_by_id(appointment_id)
        if not patient or not appointment or str(appointment.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )
        return await AppointmentService._format_appointment(appointment)

    @staticmethod
    async def list_patient_home_visits(user_id: str, page: PageWindow) -> List[AppointmentOut]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            return []
        appointments = await AppointmentRepository.list_page_by_patient_id(
            str(patient.id), page, "home_visit",
        )
        return await AppointmentService._format_appointment_page(appointments)

    @staticmethod
    async def list_admin_billing(
        page: PageWindow, billing_status: str | None = None,
        start_date=None, end_date=None,
    ) -> List[AppointmentOut]:
        appointments = await AppointmentRepository.list_page_billing(
            page, billing_status, start_date, end_date,
        )
        return await AppointmentService._format_appointment_page(appointments)

    @staticmethod
    async def list_patient_appointment_history(
        user_id: str, status_group: str, page: PageWindow, future_only: bool = False,
    ) -> List[AppointmentOut]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            return []
        groups = {
            "upcoming": ["scheduled", "in_progress"],
            "completed": ["completed"],
            "cancelled": ["cancelled"],
        }
        if future_only:
            appointments = await AppointmentRepository.list_page_by_patient_status(
                str(patient.id), groups[status_group], page,
                ascending=status_group == "upcoming", future_only=True,
            )
        else:
            appointments = await AppointmentRepository.list_page_by_patient_status(
                str(patient.id), groups[status_group], page, ascending=status_group == "upcoming",
            )
        return await AppointmentService._format_appointment_page(appointments)

    @staticmethod
    async def list_reception_schedule(
        page: PageWindow | None = None,
        start_date: date | None = None, end_date: date | None = None,
    ) -> List[ReceptionAppointmentOut]:
        appointments = (
            await AppointmentRepository.list_page_operational_schedule(page, start_date, end_date)
            if page is not None else await AppointmentRepository.list_operational_schedule()
        )
        if page is not None and appointments:
            patients, doctors, users = await AppointmentService._page_profile_maps(
                appointments,
                include_patient_phone=True,
                include_patient_email=True,
            )
            result = []
            for appointment in appointments:
                patient = patients.get(appointment.patient_id)
                doctor = doctors.get(appointment.doctor_id)
                patient_user = users.get(patient.user_id) if patient else None
                doctor_user = users.get(doctor.user_id) if doctor else None
                if not all((patient, doctor, patient_user, doctor_user)):
                    raise HTTPException(status_code=404, detail="Related patient or doctor not found")
                result.append(await AppointmentService._format_reception_appointment(
                    appointment, patient=patient, doctor=doctor,
                    patient_user=patient_user, doctor_user=doctor_user,
                ))
            return result
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
                reconciled = await AppointmentService._mark_cancelled_capture_for_reconciliation(appointment)
                if reconciled is True:
                    appointment = await AppointmentRepository.get_by_id(appointment_id)
                return await AppointmentService._format_appointment(appointment)
            cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
            changed = await AppointmentRepository.cancel_from_status(
                appointment_id,
                appointment.status,
                cancelled_at,
                expected_revision=schema.expected_revision,
            )
            updated = await AppointmentRepository.get_by_id(appointment_id)
            if changed and updated and updated.status == "cancelled":
                reconciled = await AppointmentService._mark_cancelled_capture_for_reconciliation(updated)
                if reconciled is True:
                    updated = await AppointmentRepository.get_by_id(appointment_id)
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
                slot_claim = active_slot_claim(str(appointment.doctor_id), starts_at)
            else:
                slot_claim = None

        set_fields = {}
        unset_fields = {}
        if schema.status is not None:
            set_fields["status"] = schema.status
            if slot_claim is None:
                unset_fields["slot_claim"] = ""
            else:
                set_fields["slot_claim"] = slot_claim
        if schema.billing_status is not None:
            set_fields["billing_status"] = schema.billing_status
        if schema.billing_amount is not None:
            set_fields["billing_amount"] = schema.billing_amount

        try:
            updated = await AppointmentRepository.update_if_revision(
                appointment_id,
                patient_id=appointment.patient_id,
                doctor_id=appointment.doctor_id,
                expected_revision=schema.expected_revision,
                set_fields=set_fields,
                unset_fields=unset_fields,
            )
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another active appointment already occupies this physiotherapist's slot.",
            ) from exc
        except AppointmentMutationConflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The appointment changed. Reload the latest record before trying again.",
            ) from exc

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
            reconciled = await AppointmentService._mark_cancelled_capture_for_reconciliation(appointment)
            if reconciled is True:
                appointment = await AppointmentRepository.get_by_id(appointment_id)
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
            reconciled = await AppointmentService._mark_cancelled_capture_for_reconciliation(updated)
            if reconciled is True:
                updated = await AppointmentRepository.get_by_id(appointment_id)
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
            reconciled = await AppointmentService._mark_cancelled_capture_for_reconciliation(appointment)
            if reconciled is True:
                appointment = await AppointmentRepository.get_by_id(appointment_id)
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
            reconciled = await AppointmentService._mark_cancelled_capture_for_reconciliation(updated)
            if reconciled is True:
                updated = await AppointmentRepository.get_by_id(appointment_id)
            return await AppointmentService._format_reception_appointment(updated)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment is no longer available for reception cancellation.",
        )

    @staticmethod
    async def _mark_cancelled_capture_for_reconciliation(appointment: Appointment) -> bool:
        """Carry a previously verified provider capture onto the cancelled booking."""
        if (
            not appointment
            or appointment.status != "cancelled"
            or not getattr(appointment, "payment_order_id", None)
        ):
            return False
        attempt = await PaymentAttempt.find_one(
            {"appointment_id": appointment.id, "status": "success"}
        )
        if attempt and attempt.provider_order_id and attempt.provider_payment_id:
            return await AppointmentRepository.mark_cancelled_capture_for_reconciliation(
                str(appointment.id),
                attempt.provider_order_id,
                attempt.provider_payment_id,
                attempt.currency,
            )
        return False

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
    async def _format_appointment(
        a: Appointment, *, patient=None, doctor=None, patient_user=None, doctor_user=None,
    ) -> AppointmentOut:

        patient = patient if patient is not None else await ProfileRepository.get_patient_by_id(str(a.patient_id))
        doctor = doctor if doctor is not None else await ProfileRepository.get_doctor_by_id(str(a.doctor_id))

        if not patient or not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Related patient or doctor not found",
            )

        patient_user = patient_user if patient_user is not None else await UserRepository.get_by_id(str(patient.user_id))
        doctor_user = doctor_user if doctor_user is not None else await UserRepository.get_by_id(str(doctor.user_id))

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
            revision=getattr(a, "revision", 0),
            can_patient_cancel=can_patient_cancel,
            cancellation_deadline=cancellation_deadline,
            cancellation_message=cancellation_message,
            created_at=a.created_at,
        )

    @staticmethod
    async def _format_reception_appointment(
        a: Appointment, *, patient=None, doctor=None, patient_user=None, doctor_user=None,
    ) -> ReceptionAppointmentOut:
        patient = patient if patient is not None else await ProfileRepository.get_patient_by_id(str(a.patient_id))
        doctor = doctor if doctor is not None else await ProfileRepository.get_doctor_by_id(str(a.doctor_id))
        if not patient or not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Related patient or doctor not found",
            )
        patient_user = patient_user if patient_user is not None else await UserRepository.get_by_id(str(patient.user_id))
        doctor_user = doctor_user if doctor_user is not None else await UserRepository.get_by_id(str(doctor.user_id))
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
