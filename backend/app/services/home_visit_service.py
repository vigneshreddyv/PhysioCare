from datetime import datetime, timezone
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

from beanie import PydanticObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.appointment_time import (
    active_slot_claim,
    clinic_start_to_utc_naive,
    resolve_appointment_start_utc,
    validate_booking_date,
)
from app.core.config import settings
from app.models.appointment import Appointment
from app.models.home_visit_request import HomeVisitRequest
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.demo_service_repository import DemoServiceRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.home_visit import (
    AdminDemoEntitlementOut,
    DemoEntitlementOut,
    DoctorHomeVisitRequestOut,
    HomeVisitBookingCreate,
    HomeVisitContextOut,
    HomeVisitRequestCreate,
    HomeVisitRequestOut,
    ReceptionHomeVisitRequestOut,
)
from app.schemas.appointment import AppointmentAvailabilityOut, AppointmentSlotOut
from app.services.appointment_service import AppointmentService
from app.services.clinician_schedule_service import ClinicianScheduleService


class HomeVisitService:
    NO_PREFERENCE_DOCTOR_ID = "no_preference"

    @staticmethod
    async def _eligible_home_visit_doctors():
        eligible = []
        for doctor in await ProfileRepository.list_doctors():
            user = await UserRepository.get_by_id(str(doctor.user_id))
            if (
                user
                and user.is_active
                and getattr(doctor, "accepts_home_visits", True)
            ):
                eligible.append(doctor)
        return sorted(eligible, key=lambda item: str(item.id))

    @staticmethod
    async def _entitled_patient(user_id: str):
        if not settings.DEMO_HOME_VISIT_REQUESTS_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Demo home-visit booking is disabled",
            )
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
        entitlement = await DemoServiceRepository.get_entitlement(str(patient.id))
        if not entitlement or not entitlement.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Demo home-visit booking access has not been granted for this patient",
            )
        return patient

    @staticmethod
    async def get_patient_context(user_id: str) -> HomeVisitContextOut:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
        return HomeVisitContextOut(
            coverage_city=settings.DEMO_HOME_SERVICE_CITY,
            saved_home_address=patient.saved_home_address,
        )

    @staticmethod
    async def get_patient_entitlement(user_id: str) -> DemoEntitlementOut:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")
        entitlement = await DemoServiceRepository.get_entitlement(str(patient.id))
        active = bool(entitlement and entitlement.active and settings.DEMO_HOME_VISIT_REQUESTS_ENABLED)
        return DemoEntitlementOut(
            patient_id=str(patient.id),
            active=active,
            requests_enabled=settings.DEMO_HOME_VISIT_REQUESTS_ENABLED,
        )

    @staticmethod
    async def list_admin_entitlements() -> list[AdminDemoEntitlementOut]:
        patients = await ProfileRepository.list_patients()
        result = []
        for patient in patients:
            user = await UserRepository.get_by_id(str(patient.user_id))
            if not user:
                continue
            entitlement = await DemoServiceRepository.get_entitlement(str(patient.id))
            result.append(AdminDemoEntitlementOut(
                patient_id=str(patient.id),
                patient_name=user.full_name,
                patient_email=user.email,
                patient_phone=patient.phone,
                active=bool(entitlement and entitlement.active and settings.DEMO_HOME_VISIT_REQUESTS_ENABLED),
                requests_enabled=settings.DEMO_HOME_VISIT_REQUESTS_ENABLED,
            ))
        return result

    @staticmethod
    async def set_demo_entitlement(
        patient_id: str,
        admin_user_id: str,
        active: bool,
    ) -> AdminDemoEntitlementOut:
        patient = await ProfileRepository.get_patient_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        user = await UserRepository.get_by_id(str(patient.user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient account not found")
        await DemoServiceRepository.set_entitlement(patient_id, admin_user_id, active)
        return AdminDemoEntitlementOut(
            patient_id=patient_id,
            patient_name=user.full_name,
            patient_email=user.email,
            patient_phone=patient.phone,
            active=active and settings.DEMO_HOME_VISIT_REQUESTS_ENABLED,
            requests_enabled=settings.DEMO_HOME_VISIT_REQUESTS_ENABLED,
        )

    @staticmethod
    async def create_request(user_id: str, schema: HomeVisitRequestCreate) -> HomeVisitRequestOut:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Legacy home-visit requests are retired. Use direct home-visit booking.",
        )

    @staticmethod
    async def get_booking_availability(
        user_id: str,
        doctor_id: str,
        appointment_date,
    ) -> AppointmentAvailabilityOut:
        await HomeVisitService._entitled_patient(user_id)
        try:
            validate_booking_date(appointment_date)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        if doctor_id == HomeVisitService.NO_PREFERENCE_DOCTOR_ID:
            doctors = await HomeVisitService._eligible_home_visit_doctors()
        else:
            doctor = await ProfileRepository.get_doctor_by_id(doctor_id)
            if not doctor or not getattr(doctor, "accepts_home_visits", True):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")
            user = await UserRepository.get_by_id(str(doctor.user_id))
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")
            doctors = [doctor]

        occupied_by_doctor = {}
        schedule_slots_by_doctor = {}
        published_by_doctor = {}
        for doctor in doctors:
            occupied = set()
            for appointment in await AppointmentRepository.list_active_by_doctor_id(str(doctor.id)):
                try:
                    occupied.add(resolve_appointment_start_utc(appointment).replace(tzinfo=None))
                except ValueError:
                    continue
            occupied_by_doctor[str(doctor.id)] = occupied
            schedule_slots, published = await ClinicianScheduleService.effective_slots(
                str(doctor.id), appointment_date, "home_visit"
            )
            schedule_slots_by_doctor[str(doctor.id)] = set(schedule_slots)
            published_by_doctor[str(doctor.id)] = published

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        slots = []
        all_slot_values = sorted(
            set().union(*schedule_slots_by_doctor.values()) if schedule_slots_by_doctor else set(),
            key=lambda value: clinic_start_to_utc_naive(appointment_date, value),
        )
        for time_slot in all_slot_values:
            starts_at = clinic_start_to_utc_naive(appointment_date, time_slot)
            has_capacity = any(
                time_slot in schedule_slots_by_doctor[str(doctor.id)]
                and starts_at not in occupied_by_doctor[str(doctor.id)]
                for doctor in doctors
            )
            state = "past" if starts_at <= now_utc else "available" if has_capacity else "occupied"
            slots.append(AppointmentSlotOut(
                time_slot=time_slot,
                available=state == "available",
                availability_state=state,
            ))

        all_published = bool(doctors) and all(published_by_doctor.values())
        any_published = any(published_by_doctor.values())
        return AppointmentAvailabilityOut(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            clinic_timezone=settings.CLINIC_TIMEZONE,
            demo_configuration=not all_published,
            configuration_label=(
                "Administrator-published home-visit availability; travel time is not automatically calculated"
                if all_published
                else "Published schedules are used where available; unconfigured clinicians use the demonstration fallback"
                if any_published
                else "Configurable demonstration home-visit schedule; travel buffers and practitioner working hours require configuration"
            ),
            slot_minutes=settings.DEMO_HOME_SLOT_MINUTES,
            window_start=all_slot_values[0] if all_slot_values else "Closed",
            window_end=all_slot_values[-1] if all_slot_values else "Closed",
            slots=slots,
        )

    @staticmethod
    async def create_booking(user_id: str, schema: HomeVisitBookingCreate):
        patient = await HomeVisitService._entitled_patient(user_id)
        if schema.city.casefold() != settings.DEMO_HOME_SERVICE_CITY.casefold():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Home visits are currently limited to {settings.DEMO_HOME_SERVICE_CITY} city",
            )
        submission_digest = sha256(schema.submission_key.encode("utf-8")).hexdigest()
        submission_claim = f"home:{patient.id}:{submission_digest}"
        submission_fingerprint = sha256(json.dumps(
            schema.model_dump(mode="json", exclude={"submission_key"}),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        existing = await AppointmentRepository.get_by_submission_claim(submission_claim)
        if existing:
            if getattr(existing, "submission_fingerprint", None) != submission_fingerprint:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This booking form changed after submission. Refresh availability before confirming again.",
                )
            return await AppointmentService._format_appointment(existing)

        no_preference = not schema.preferred_doctor_id
        if no_preference:
            candidate_doctors = await HomeVisitService._eligible_home_visit_doctors()
            if not candidate_doctors:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No home-visit clinician is available for this time. Choose another slot.",
                )
        else:
            doctor = await ProfileRepository.get_doctor_by_id(schema.preferred_doctor_id)
            if not doctor or not getattr(doctor, "accepts_home_visits", True):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")
            user = await UserRepository.get_by_id(str(doctor.user_id))
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")
            candidate_doctors = [doctor]

        eligible_candidates = []
        schedule_error = None
        starts_at = None
        for doctor in candidate_doctors:
            try:
                candidate_start, _published = await ClinicianScheduleService.validate_effective_slot(
                    str(doctor.id), schema.appointment_date, schema.time_slot, "home_visit"
                )
                starts_at = candidate_start
                eligible_candidates.append(doctor)
            except HTTPException as exc:
                schedule_error = exc
        if not eligible_candidates:
            if not no_preference and schedule_error:
                raise schedule_error
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No home-visit clinician is scheduled for this time. Choose another slot.",
            )
        candidate_doctors = eligible_candidates

        saved = None
        for doctor in candidate_doctors:
            appointment = Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                doctor_assignment_pending=no_preference,
                appointment_date=datetime.combine(schema.appointment_date, datetime.min.time()),
                starts_at=starts_at,
                slot_claim=active_slot_claim(str(doctor.id), starts_at),
                submission_claim=submission_claim,
                submission_fingerprint=submission_fingerprint,
                clinic_timezone=settings.CLINIC_TIMEZONE,
                time_slot=schema.time_slot,
                reason=schema.reason or "",
                service_mode="home_visit",
                home_address=schema.home_address,
                city=settings.DEMO_HOME_SERVICE_CITY,
                body_regions=schema.body_regions,
                symptoms=schema.symptoms,
                duration_days=schema.duration_days,
                pain_severity=schema.pain_severity,
                billing_status="unconfigured",
                billing_amount=0,
            )
            try:
                saved = await AppointmentRepository.create(appointment)
                break
            except DuplicateKeyError as exc:
                repeated = await AppointmentRepository.get_by_submission_claim(submission_claim)
                if repeated:
                    if getattr(repeated, "submission_fingerprint", None) != submission_fingerprint:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="This booking form changed after submission. Refresh availability before confirming again.",
                        ) from exc
                    return await AppointmentService._format_appointment(repeated)
                continue

        if saved is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That slot was just taken. Refresh availability and choose another time.",
            )

        if schema.save_address:
            patient.saved_home_address = schema.home_address
            await ProfileRepository.save_patient(patient)
        return await AppointmentService._format_appointment(saved)

    @staticmethod
    async def assign_booking_doctor(
        appointment_id: str,
        doctor_id: str,
        admin_user_id: str,
    ):
        appointment = await AppointmentRepository.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Home visit not found")
        if getattr(appointment, "service_mode", "clinic") != "home_visit":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only home visits can be allocated here")
        if appointment.status != "scheduled":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only scheduled home visits can be allocated")

        doctor = await ProfileRepository.get_doctor_by_id(doctor_id)
        if not doctor or not getattr(doctor, "accepts_home_visits", True):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")
        doctor_user = await UserRepository.get_by_id(str(doctor.user_id))
        if not doctor_user or not doctor_user.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")

        clinic_zone = ZoneInfo(settings.CLINIC_TIMEZONE)
        try:
            appointment_local = resolve_appointment_start_utc(appointment).astimezone(clinic_zone)
            await ClinicianScheduleService.validate_effective_slot(
                str(doctor.id), appointment_local.date(), appointment.time_slot, "home_visit"
            )
        except (ValueError, HTTPException) as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That physiotherapist is not scheduled for this home-visit time. The current reservation was kept.",
            ) from exc

        if str(appointment.doctor_id) == str(doctor.id) and not getattr(appointment, "doctor_assignment_pending", False):
            return await AppointmentService._format_appointment(appointment)

        try:
            starts_at = resolve_appointment_start_utc(appointment).replace(tzinfo=None)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This home visit time cannot be allocated safely.",
            ) from exc

        try:
            updated = await AppointmentRepository.assign_home_visit_doctor(
                appointment_id=appointment_id,
                current_doctor_id=str(appointment.doctor_id),
                doctor_id=str(doctor.id),
                slot_claim=active_slot_claim(str(doctor.id), starts_at),
                changed_by_user_id=admin_user_id,
                changed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That physiotherapist already has a booking at this time. The current reservation was kept.",
            ) from exc

        if updated is None:
            latest = await AppointmentRepository.get_by_id(appointment_id)
            if not latest:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Home visit not found")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This home visit changed before allocation. Refresh and try again.",
            )
        return await AppointmentService._format_appointment(updated)

    @staticmethod
    async def list_patient_requests(user_id: str) -> list[HomeVisitRequestOut]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            return []
        requests = await DemoServiceRepository.list_by_patient(str(patient.id))
        return [await HomeVisitService._format_full(request) for request in requests]

    @staticmethod
    async def list_admin_requests() -> list[HomeVisitRequestOut]:
        requests = await DemoServiceRepository.list_all()
        return [await HomeVisitService._format_full(request) for request in requests]

    @staticmethod
    async def list_reception_requests() -> list[ReceptionHomeVisitRequestOut]:
        requests = await DemoServiceRepository.list_reception_coordination()
        return [await HomeVisitService._format_reception(request) for request in requests]

    @staticmethod
    async def list_doctor_requests(user_id: str) -> list[DoctorHomeVisitRequestOut]:
        doctor = await ProfileRepository.get_doctor_by_user_id(user_id)
        if not doctor:
            return []
        requests = await DemoServiceRepository.list_doctor_coordination(str(doctor.id))
        return [await HomeVisitService._format_doctor(request) for request in requests]

    @staticmethod
    async def review_request(
        request_id: str,
        admin_user_id: str,
        target_status: str,
    ) -> HomeVisitRequestOut:
        request = await DemoServiceRepository.get_request(request_id)
        if not request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Home-visit request not found")
        if request.status == target_status:
            return await HomeVisitService._format_full(request)
        changed = await DemoServiceRepository.transition_request(
            request_id,
            ["pending_clinic_confirmation"],
            target_status,
            admin_user_id,
        )
        updated = await DemoServiceRepository.get_request(request_id)
        if not changed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending requests can be reviewed",
            )
        return await HomeVisitService._format_full(updated)

    @staticmethod
    async def withdraw_request(request_id: str, user_id: str) -> HomeVisitRequestOut:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        request = await DemoServiceRepository.get_request(request_id)
        if not patient or not request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Home-visit request not found")
        if str(request.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may withdraw only your own home-visit requests",
            )
        if request.status == "withdrawn":
            return await HomeVisitService._format_full(request)
        changed = await DemoServiceRepository.transition_request(
            request_id,
            ["pending_clinic_confirmation", "approved_for_coordination"],
            "withdrawn",
        )
        updated = await DemoServiceRepository.get_request(request_id)
        if not changed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This request can no longer be withdrawn online",
            )
        return await HomeVisitService._format_full(updated)

    @staticmethod
    def _confirmation_message(request_status: str) -> str:
        messages = {
            "pending_clinic_confirmation": "Request received. The clinic must review it; this is not a confirmed appointment and no capacity is reserved.",
            "approved_for_coordination": "Approved for coordination only. Reception must confirm details; no visit time or capacity is reserved.",
            "declined": "The clinic could not accept this request. No appointment was created.",
            "withdrawn": "This request was withdrawn. No appointment was created.",
        }
        return messages.get(request_status, "This request is not a confirmed appointment.")

    @staticmethod
    async def _related(request: HomeVisitRequest):
        patient = await ProfileRepository.get_patient_by_id(str(request.patient_id))
        doctor = await ProfileRepository.get_doctor_by_id(str(request.preferred_doctor_id))
        if not patient or not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Related patient or physiotherapist not found")
        patient_user = await UserRepository.get_by_id(str(patient.user_id))
        doctor_user = await UserRepository.get_by_id(str(doctor.user_id))
        if not patient_user or not doctor_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Related account not found")
        return patient, doctor, patient_user, doctor_user

    @staticmethod
    async def _format_full(request: HomeVisitRequest) -> HomeVisitRequestOut:
        patient, doctor, patient_user, doctor_user = await HomeVisitService._related(request)
        return HomeVisitRequestOut(
            id=str(request.id),
            patient_id=str(patient.id),
            patient_name=patient_user.full_name,
            patient_email=patient_user.email,
            patient_phone=patient.phone,
            preferred_doctor_id=str(doctor.id),
            preferred_doctor_name=doctor_user.full_name,
            home_address=request.home_address,
            reason=request.reason,
            city=request.city,
            body_regions=request.body_regions,
            symptoms=request.symptoms,
            duration_days=request.duration_days,
            pain_severity=request.pain_severity,
            status=request.status,
            created_at=request.created_at,
            updated_at=request.updated_at,
            confirmation_message=HomeVisitService._confirmation_message(request.status),
        )

    @staticmethod
    async def _format_reception(request: HomeVisitRequest) -> ReceptionHomeVisitRequestOut:
        patient, doctor, patient_user, doctor_user = await HomeVisitService._related(request)
        return ReceptionHomeVisitRequestOut(
            id=str(request.id),
            patient_id=str(patient.id),
            patient_name=patient_user.full_name,
            patient_email=patient_user.email,
            patient_phone=patient.phone,
            preferred_doctor_id=str(doctor.id),
            preferred_doctor_name=doctor_user.full_name,
            home_address=request.home_address,
            city=request.city,
            status="approved_for_coordination",
            created_at=request.created_at,
            confirmation_message=HomeVisitService._confirmation_message(request.status),
        )

    @staticmethod
    async def _format_doctor(request: HomeVisitRequest) -> DoctorHomeVisitRequestOut:
        patient, _doctor, patient_user, _doctor_user = await HomeVisitService._related(request)
        return DoctorHomeVisitRequestOut(
            id=str(request.id),
            patient_id=str(patient.id),
            patient_name=patient_user.full_name,
            patient_phone=patient.phone,
            home_address=request.home_address,
            reason=request.reason,
            city=request.city,
            body_regions=request.body_regions,
            symptoms=request.symptoms,
            duration_days=request.duration_days,
            pain_severity=request.pain_severity,
            status="approved_for_coordination",
            created_at=request.created_at,
            confirmation_message=HomeVisitService._confirmation_message(request.status),
        )
