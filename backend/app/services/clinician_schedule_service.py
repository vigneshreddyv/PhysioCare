from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.core.appointment_time import (
    booking_window,
    clinic_start_to_utc_naive,
    configured_schedule_slots,
    demo_home_schedule_slots,
    demo_schedule_slots,
    parse_time_slot,
    resolve_appointment_start_utc,
    validate_booking_date,
)
from app.core.config import settings
from app.models.clinician_schedule import ClinicianSchedule, ScheduleBlock, ScheduleDateException
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.clinician_schedule_repository import ClinicianScheduleRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointment import AppointmentAvailabilityOut, AppointmentSlotOut
from app.schemas.clinician_schedule import (
    ClinicianScheduleOut,
    ScheduleAuditOut,
    ScheduleBlockIn,
    ScheduleDateExceptionIn,
    ScheduleDraftUpdate,
)


class ClinicianScheduleService:
    @staticmethod
    async def _doctor(doctor_id: str):
        doctor = await ProfileRepository.get_doctor_by_id(doctor_id)
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist not found")
        user = await UserRepository.get_by_id(str(doctor.user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physiotherapist account not found")
        return doctor, user

    @staticmethod
    def _status(schedule: ClinicianSchedule | None) -> str:
        if not schedule or schedule.draft_revision == 0:
            return "unconfigured"
        if schedule.published_revision is None:
            return "draft"
        if schedule.published_revision != schedule.draft_revision:
            return "draft_changes"
        return "published"

    @staticmethod
    async def _format(schedule: ClinicianSchedule | None, doctor_id: str, doctor_name: str) -> ClinicianScheduleOut:
        return ClinicianScheduleOut(
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            timezone=settings.CLINIC_TIMEZONE,
            slot_minutes=settings.DEMO_SLOT_MINUTES,
            status=ClinicianScheduleService._status(schedule),
            draft_revision=schedule.draft_revision if schedule else 0,
            published_revision=schedule.published_revision if schedule else None,
            published_at=schedule.published_at if schedule else None,
            weekly_blocks=[ScheduleBlockIn.model_validate(item.model_dump()) for item in (schedule.draft_weekly_blocks if schedule else [])],
            date_exceptions=[ScheduleDateExceptionIn.model_validate(item.model_dump()) for item in (schedule.draft_date_exceptions if schedule else [])],
            published_weekly_blocks=[ScheduleBlockIn.model_validate(item.model_dump()) for item in (schedule.published_weekly_blocks if schedule else [])],
            published_date_exceptions=[ScheduleDateExceptionIn.model_validate(item.model_dump()) for item in (schedule.published_date_exceptions if schedule else [])],
            audit_history=[
                ScheduleAuditOut(action=item.action, revision=item.revision, occurred_at=item.occurred_at)
                for item in (schedule.audit_history[-20:] if schedule else [])
            ],
        )

    @staticmethod
    async def get_admin(doctor_id: str) -> ClinicianScheduleOut:
        _doctor, user = await ClinicianScheduleService._doctor(doctor_id)
        schedule = await ClinicianScheduleRepository.get_by_doctor_id(doctor_id)
        return await ClinicianScheduleService._format(schedule, doctor_id, user.full_name)

    @staticmethod
    async def save_draft(doctor_id: str, actor_user_id: str, schema: ScheduleDraftUpdate) -> ClinicianScheduleOut:
        _doctor, user = await ClinicianScheduleService._doctor(doctor_id)
        earliest, latest = booking_window()
        for exception in schema.date_exceptions:
            if exception.date < earliest or exception.date > latest:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Date exceptions must stay inside the current {settings.BOOKING_HORIZON_DAYS}-day booking window",
                )
        schedule = await ClinicianScheduleRepository.get_by_doctor_id(doctor_id)
        if not schedule:
            schedule = ClinicianSchedule(doctor_id=PydanticObjectId(doctor_id))
        schedule.draft_weekly_blocks = [ScheduleBlock.model_validate(item.model_dump()) for item in schema.weekly_blocks]
        schedule.draft_date_exceptions = [ScheduleDateException.model_validate(item.model_dump()) for item in schema.date_exceptions]
        saved = await ClinicianScheduleRepository.save_draft(schedule, actor_user_id)
        return await ClinicianScheduleService._format(saved, doctor_id, user.full_name)

    @staticmethod
    def _slots_from(
        weekly_blocks: list[ScheduleBlock],
        exceptions: list[ScheduleDateException],
        appointment_date: date,
        service_mode: str,
        slot_minutes: int,
    ) -> list[str]:
        exception = next((item for item in exceptions if item.date == appointment_date), None)
        blocks = exception.blocks if exception is not None else [
            item for item in weekly_blocks if item.day_of_week == appointment_date.weekday()
        ]
        slots = {
            slot
            for block in blocks
            if block.service_mode == service_mode
            for slot in configured_schedule_slots(block.start_time, block.end_time, slot_minutes)
        }
        return sorted(slots, key=parse_time_slot)

    @staticmethod
    async def effective_slots(doctor_id: str, appointment_date: date, service_mode: str) -> tuple[list[str], bool]:
        schedule = await ClinicianScheduleRepository.get_by_doctor_id(doctor_id)
        if schedule and schedule.published_revision is not None:
            return ClinicianScheduleService._slots_from(
                schedule.published_weekly_blocks,
                schedule.published_date_exceptions,
                appointment_date,
                service_mode,
                schedule.slot_minutes,
            ), True
        fallback = demo_home_schedule_slots() if service_mode == "home_visit" else demo_schedule_slots()
        return fallback, False

    @staticmethod
    async def validate_effective_slot(doctor_id: str, appointment_date: date, time_slot: str, service_mode: str) -> tuple[datetime, bool]:
        try:
            validate_booking_date(appointment_date)
            normalized = parse_time_slot(time_slot).strftime("%I:%M %p")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        slots, published = await ClinicianScheduleService.effective_slots(doctor_id, appointment_date, service_mode)
        if normalized not in slots:
            source = "published clinician schedule" if published else "configured demonstration schedule"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Choose a slot inside the {source}")
        starts_at = clinic_start_to_utc_naive(appointment_date, normalized)
        if starts_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Choose a future appointment slot")
        return starts_at, published

    @staticmethod
    async def preview(doctor_id: str, appointment_date: date, service_mode: str) -> AppointmentAvailabilityOut:
        await ClinicianScheduleService._doctor(doctor_id)
        try:
            validate_booking_date(appointment_date)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        schedule = await ClinicianScheduleRepository.get_by_doctor_id(doctor_id)
        if not schedule or schedule.draft_revision == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Save a draft schedule before previewing it")
        slot_values = ClinicianScheduleService._slots_from(
            schedule.draft_weekly_blocks,
            schedule.draft_date_exceptions,
            appointment_date,
            service_mode,
            schedule.slot_minutes,
        )
        occupied = set()
        for appointment in await AppointmentRepository.list_active_by_doctor_id(doctor_id):
            try:
                occupied.add(resolve_appointment_start_utc(appointment).replace(tzinfo=None))
            except ValueError:
                continue
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        slots = []
        for value in slot_values:
            starts_at = clinic_start_to_utc_naive(appointment_date, value)
            state = "past" if starts_at <= now else "occupied" if starts_at in occupied else "available"
            slots.append(AppointmentSlotOut(time_slot=value, available=state == "available", availability_state=state))
        return AppointmentAvailabilityOut(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            clinic_timezone=settings.CLINIC_TIMEZONE,
            demo_configuration=True,
            configuration_label="Draft preview only; patients continue using the last published schedule or the demonstration fallback",
            slot_minutes=schedule.slot_minutes,
            window_start=slot_values[0] if slot_values else "Closed",
            window_end=slot_values[-1] if slot_values else "Closed",
            slots=slots,
        )

    @staticmethod
    async def publish(doctor_id: str, actor_user_id: str, expected_revision: int) -> ClinicianScheduleOut:
        _doctor, user = await ClinicianScheduleService._doctor(doctor_id)
        schedule = await ClinicianScheduleRepository.get_by_doctor_id(doctor_id)
        if not schedule or schedule.draft_revision == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Save a draft schedule before publishing")
        if schedule.draft_revision != expected_revision:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The draft changed; refresh before publishing")
        earliest, latest = booking_window()
        conflicts = 0
        clinic_zone = ZoneInfo(settings.CLINIC_TIMEZONE)
        for appointment in await AppointmentRepository.list_active_by_doctor_id(doctor_id):
            try:
                local = resolve_appointment_start_utc(appointment).astimezone(clinic_zone)
            except ValueError:
                continue
            if not earliest <= local.date() <= latest:
                continue
            mode = "home_visit" if getattr(appointment, "service_mode", "clinic") == "home_visit" else "clinic"
            slots = ClinicianScheduleService._slots_from(
                schedule.draft_weekly_blocks,
                schedule.draft_date_exceptions,
                local.date(),
                mode,
                schedule.slot_minutes,
            )
            if local.strftime("%I:%M %p") not in slots:
                conflicts += 1
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This draft excludes {conflicts} existing appointment slot(s). Adjust the schedule before publishing.",
            )
        published = await ClinicianScheduleRepository.publish(schedule, actor_user_id, expected_revision)
        if not published:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The draft changed; refresh before publishing")
        return await ClinicianScheduleService._format(published, doctor_id, user.full_name)
