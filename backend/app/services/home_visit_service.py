from datetime import datetime, timezone
from hashlib import sha256
import json
from types import SimpleNamespace
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
from app.models.patient import Patient
from app.models.user import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.demo_service_repository import DemoServiceRepository
from app.repositories.home_visit_query_repository import HomeVisitQueryRepository
from app.core.pagination import PageWindow
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
    @staticmethod
    async def _persist_requested_address(patient, schema: HomeVisitBookingCreate) -> None:
        """Idempotently finish the optional preference write on initial or retry."""
        if schema.save_address and patient.saved_home_address != schema.home_address:
            patient.saved_home_address = schema.home_address
            await ProfileRepository.save_patient(patient)

    @staticmethod
    async def search_admin_entitlements(page: PageWindow, search: str) -> list[AdminDemoEntitlementOut]:
        rows = await DemoServiceRepository.search_entitlements(page, search)
        return [AdminDemoEntitlementOut(
            patient_id=str(row["patient"]["_id"]),
            patient_name=row["full_name"], patient_email=row["email"],
            patient_phone=row["patient"].get("phone"),
            active=bool(row.get("entitlement") and row["entitlement"][0].get("active")
                        and settings.DEMO_HOME_VISIT_REQUESTS_ENABLED),
            requests_enabled=settings.DEMO_HOME_VISIT_REQUESTS_ENABLED,
        ) for row in rows]
    NO_PREFERENCE_DOCTOR_ID = "no_preference"

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
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        all_slot_values: set[str] = set()
        available_slot_values: set[str] = set()
        clinician_count = 0
        published_count = 0
        if doctor_id == HomeVisitService.NO_PREFERENCE_DOCTOR_ID:
            async for context in HomeVisitQueryRepository.iter_clinician_contexts(appointment_date):
                clinician_count += 1
                schedule_slots, published = ClinicianScheduleService.effective_slots_from_schedule(
                    context.schedule, appointment_date, "home_visit",
                )
                published_count += int(published)
                all_slot_values.update(schedule_slots)
                occupied = set()
                for appointment in context.appointments:
                    try:
                        occupied.add(resolve_appointment_start_utc(appointment).replace(tzinfo=None))
                    except ValueError:
                        continue
                for time_slot in schedule_slots:
                    if clinic_start_to_utc_naive(appointment_date, time_slot) not in occupied:
                        available_slot_values.add(time_slot)
        else:
            doctor = await ProfileRepository.get_doctor_by_id(doctor_id)
            if not doctor or not getattr(doctor, "accepts_home_visits", True):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")
            user = await UserRepository.get_by_id(str(doctor.user_id))
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")
            clinician_count = 1
            appointments = await AppointmentRepository.list_active_by_doctor_id(
                doctor_id, appointment_date, appointment_date,
            )
            schedule_slots, published = await ClinicianScheduleService.effective_slots(
                doctor_id, appointment_date, "home_visit",
            )
            published_count = int(published)
            all_slot_values.update(schedule_slots)
            occupied = set()
            for appointment in appointments:
                try:
                    occupied.add(resolve_appointment_start_utc(appointment).replace(tzinfo=None))
                except ValueError:
                    continue
            for time_slot in schedule_slots:
                if clinic_start_to_utc_naive(appointment_date, time_slot) not in occupied:
                    available_slot_values.add(time_slot)

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        slots = []
        all_slot_values = sorted(all_slot_values, key=lambda value: clinic_start_to_utc_naive(appointment_date, value))
        for time_slot in all_slot_values:
            starts_at = clinic_start_to_utc_naive(appointment_date, time_slot)
            has_capacity = time_slot in available_slot_values
            state = "past" if starts_at <= now_utc else "available" if has_capacity else "occupied"
            slots.append(AppointmentSlotOut(
                time_slot=time_slot,
                available=state == "available",
                availability_state=state,
            ))

        all_published = clinician_count > 0 and published_count == clinician_count
        any_published = published_count > 0
        return AppointmentAvailabilityOut(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            clinic_timezone=settings.CLINIC_TIMEZONE,
            demo_configuration=not all_published and ClinicianScheduleService.demo_fallback_enabled(),
            configuration_label=(
                "Administrator-published home-visit availability; travel time is not automatically calculated"
                if all_published
                else "Published schedules are used where available; unconfigured clinicians use the demonstration fallback"
                if any_published and ClinicianScheduleService.demo_fallback_enabled()
                else "Configurable demonstration home-visit schedule; travel buffers and practitioner working hours require configuration"
                if ClinicianScheduleService.demo_fallback_enabled()
                else "Only published clinician home-visit schedules are available"
                if any_published
                else "No published clinician home-visit schedule is available"
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
            await HomeVisitService._persist_requested_address(patient, schema)
            return await AppointmentService._format_appointment(existing)

        no_preference = not schema.preferred_doctor_id
        doctor = None
        if not no_preference:
            doctor = await ProfileRepository.get_doctor_by_id(schema.preferred_doctor_id)
            if not doctor or not getattr(doctor, "accepts_home_visits", True):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")
            user = await UserRepository.get_by_id(str(doctor.user_id))
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist is not available for home visits")

        saw_clinician = False
        saw_scheduled_clinician = False

        async def candidates():
            nonlocal saw_clinician, saw_scheduled_clinician
            if not no_preference:
                starts_at, _published = await ClinicianScheduleService.validate_effective_slot(
                    str(doctor.id), schema.appointment_date, schema.time_slot, "home_visit",
                )
                saw_clinician = True
                saw_scheduled_clinician = True
                yield doctor.id, starts_at
                return
            async for context in HomeVisitQueryRepository.iter_clinician_contexts(schema.appointment_date):
                saw_clinician = True
                slots, published = ClinicianScheduleService.effective_slots_from_schedule(
                    context.schedule, schema.appointment_date, "home_visit",
                )
                try:
                    starts_at, _published = ClinicianScheduleService.validate_effective_slot_values(
                        schema.appointment_date, schema.time_slot, slots, published,
                    )
                except HTTPException:
                    continue
                occupied = False
                for appointment in context.appointments:
                    try:
                        occupied = resolve_appointment_start_utc(appointment).replace(tzinfo=None) == starts_at
                    except ValueError:
                        continue
                    if occupied:
                        break
                if occupied:
                    continue
                saw_scheduled_clinician = True
                yield context.id, starts_at

        saved = None
        async for candidate_doctor_id, starts_at in candidates():
            appointment = Appointment(
                patient_id=patient.id,
                doctor_id=candidate_doctor_id,
                doctor_assignment_pending=no_preference,
                appointment_date=datetime.combine(schema.appointment_date, datetime.min.time()),
                starts_at=starts_at,
                slot_claim=active_slot_claim(str(candidate_doctor_id), starts_at),
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
                    await HomeVisitService._persist_requested_address(patient, schema)
                    return await AppointmentService._format_appointment(repeated)
                continue

        if saved is None:
            if no_preference and not saw_clinician:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No home-visit clinician is available for this time. Choose another slot.",
                )
            if no_preference and not saw_scheduled_clinician:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No home-visit clinician is scheduled for this time. Choose another slot.",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That slot was just taken. Refresh availability and choose another time.",
            )

        await HomeVisitService._persist_requested_address(patient, schema)
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
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Only home visits can be allocated here")
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
    async def list_patient_requests(
        user_id: str, page: PageWindow | None = None, recent_updates: bool = False,
    ) -> list[HomeVisitRequestOut]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            return []
        requests = (
            await DemoServiceRepository.list_page_by_patient(
                str(patient.id), page, recent_updates=True,
            ) if recent_updates else await DemoServiceRepository.list_page_by_patient(str(patient.id), page)
            if page is not None else await DemoServiceRepository.list_by_patient(str(patient.id))
        )
        if page is not None:
            return await HomeVisitService._format_full_page(requests)
        return [await HomeVisitService._format_full(request) for request in requests]

    @staticmethod
    async def list_admin_requests(page: PageWindow | None = None) -> list[HomeVisitRequestOut]:
        requests = (
            await DemoServiceRepository.list_page_all(page)
            if page is not None else await DemoServiceRepository.list_all()
        )
        if page is not None:
            return await HomeVisitService._format_full_page(requests)
        return [await HomeVisitService._format_full(request) for request in requests]

    @staticmethod
    async def list_reception_requests(
        page: PageWindow | None = None,
    ) -> list[ReceptionHomeVisitRequestOut]:
        requests = (
            await DemoServiceRepository.list_page_reception_coordination(page)
            if page is not None else await DemoServiceRepository.list_reception_coordination()
        )
        if page is not None and requests:
            patients, doctors, users = await AppointmentService._page_profile_maps(
                requests,
                "preferred_doctor_id",
                include_patient_phone=True,
                include_patient_email=True,
            )
            result = []
            for request in requests:
                patient = patients.get(request.patient_id)
                doctor = doctors.get(request.preferred_doctor_id)
                patient_user = users.get(patient.user_id) if patient else None
                doctor_user = users.get(doctor.user_id) if doctor else None
                if not all((patient, doctor, patient_user, doctor_user)):
                    raise HTTPException(status_code=404, detail="Related patient or physiotherapist not found")
                result.append(await HomeVisitService._format_reception(
                    request, related=(patient, doctor, patient_user, doctor_user),
                ))
            return result
        return [await HomeVisitService._format_reception(request) for request in requests]

    @staticmethod
    async def list_doctor_requests(
        user_id: str, page: PageWindow | None = None,
    ) -> list[DoctorHomeVisitRequestOut]:
        doctor = await ProfileRepository.get_doctor_by_user_id(user_id)
        if not doctor:
            return []
        requests = (
            await DemoServiceRepository.list_page_doctor_coordination(str(doctor.id), page)
            if page is not None else await DemoServiceRepository.list_doctor_coordination(str(doctor.id))
        )
        if page is not None:
            patients, users = await HomeVisitService._page_patient_maps(requests)
            result = []
            for request in requests:
                patient = patients.get(request.patient_id)
                patient_user = users.get(patient.user_id) if patient else None
                if not patient or not patient_user:
                    raise HTTPException(status_code=404, detail="Related patient account not found")
                result.append(await HomeVisitService._format_doctor(
                    request, patient=patient, patient_user=patient_user,
                ))
            return result
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
    async def _page_patient_maps(requests: list):
        """Fetch only doctor-visible patient identity fields for one authorized page."""
        if not requests:
            return {}, {}
        patient_ids = list({request.patient_id for request in requests})
        patients = await Patient.get_pymongo_collection().find(
            {"_id": {"$in": patient_ids}}, {"user_id": 1, "phone": 1},
        ).to_list(length=len(patient_ids))
        user_ids = list({row["user_id"] for row in patients})
        users = await User.get_pymongo_collection().find(
            {"_id": {"$in": user_ids}}, {"full_name": 1},
        ).to_list(length=len(user_ids)) if user_ids else []
        return (
            {row["_id"]: SimpleNamespace(
                id=row["_id"], user_id=row["user_id"], phone=row.get("phone"),
            ) for row in patients},
            {row["_id"]: SimpleNamespace(id=row["_id"], full_name=row["full_name"])
             for row in users},
        )

    @staticmethod
    async def _format_full_page(requests: list) -> list[HomeVisitRequestOut]:
        if not requests:
            return []
        patients, doctors, users = await AppointmentService._page_profile_maps(
            requests,
            "preferred_doctor_id",
            include_patient_phone=True,
            include_patient_email=True,
        )
        result = []
        for request in requests:
            patient = patients.get(request.patient_id)
            doctor = doctors.get(request.preferred_doctor_id)
            patient_user = users.get(patient.user_id) if patient else None
            doctor_user = users.get(doctor.user_id) if doctor else None
            if not all((patient, doctor, patient_user, doctor_user)):
                raise HTTPException(status_code=404, detail="Related patient or physiotherapist not found")
            result.append(await HomeVisitService._format_full(
                request, related=(patient, doctor, patient_user, doctor_user),
            ))
        return result

    @staticmethod
    async def _format_full(
        request: HomeVisitRequest, *, related=None,
    ) -> HomeVisitRequestOut:
        patient, doctor, patient_user, doctor_user = (
            related if related is not None else await HomeVisitService._related(request)
        )
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
    async def _format_reception(
        request: HomeVisitRequest, *, related=None,
    ) -> ReceptionHomeVisitRequestOut:
        patient, doctor, patient_user, doctor_user = (
            related if related is not None else await HomeVisitService._related(request)
        )
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
    async def _format_doctor(
        request: HomeVisitRequest, *, patient=None, patient_user=None,
    ) -> DoctorHomeVisitRequestOut:
        if patient is None or patient_user is None:
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
