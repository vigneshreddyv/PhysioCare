from datetime import date, datetime, time, timedelta, timezone
import re
from zoneinfo import ZoneInfo

from app.core.config import settings


TIME_SLOT_PATTERN = re.compile(r"^(0?[1-9]|1[0-2]):([0-5][0-9])\s(AM|PM)$", re.IGNORECASE)


class AmbiguousLegacyAppointmentTime(ValueError):
    pass


def booking_window(now: datetime | None = None) -> tuple[date, date]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    clinic_today = current.astimezone(ZoneInfo(settings.CLINIC_TIMEZONE)).date()
    return clinic_today, clinic_today + timedelta(days=settings.BOOKING_HORIZON_DAYS - 1)


def validate_booking_date(appointment_date: date, now: datetime | None = None) -> None:
    earliest, latest = booking_window(now)
    if appointment_date < earliest:
        raise ValueError("Choose today or a future booking date")
    if appointment_date > latest:
        raise ValueError(f"Choose a date within the next {settings.BOOKING_HORIZON_DAYS} days")


def parse_time_slot(value: str) -> time:
    match = TIME_SLOT_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError("Time slot must use h:mm AM/PM format")
    hour = int(match.group(1)) % 12
    if match.group(3).upper() == "PM":
        hour += 12
    return time(hour=hour, minute=int(match.group(2)))


def clinic_start_to_utc_naive(appointment_date: date, time_slot: str) -> datetime:
    clinic_zone = ZoneInfo(settings.CLINIC_TIMEZONE)
    local_start = datetime.combine(appointment_date, parse_time_slot(time_slot), tzinfo=clinic_zone)
    return local_start.astimezone(timezone.utc).replace(tzinfo=None)


def configured_schedule_slots(start_value: str, end_value: str, slot_minutes: int) -> list[str]:
    start = datetime.strptime(start_value, "%H:%M")
    end = datetime.strptime(end_value, "%H:%M")
    current = start
    slots = []
    while current < end:
        slots.append(current.strftime("%I:%M %p"))
        current += timedelta(minutes=slot_minutes)
    return slots


def demo_schedule_slots() -> list[str]:
    return configured_schedule_slots(
        settings.DEMO_SCHEDULE_START,
        settings.DEMO_SCHEDULE_END,
        settings.DEMO_SLOT_MINUTES,
    )


def demo_home_schedule_slots() -> list[str]:
    return configured_schedule_slots(
        settings.DEMO_HOME_SCHEDULE_START,
        settings.DEMO_HOME_SCHEDULE_END,
        settings.DEMO_HOME_SLOT_MINUTES,
    )


def validate_demo_slot(
    appointment_date: date,
    time_slot: str,
    now: datetime | None = None,
) -> datetime:
    validate_booking_date(appointment_date, now)
    normalized_slot = parse_time_slot(time_slot).strftime("%I:%M %p")
    if normalized_slot not in demo_schedule_slots():
        raise ValueError("Choose a slot inside the configured demonstration schedule")
    starts_at = clinic_start_to_utc_naive(appointment_date, normalized_slot)
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is not None:
        now_utc = now_utc.astimezone(timezone.utc).replace(tzinfo=None)
    if starts_at <= now_utc:
        raise ValueError("Choose a future appointment slot")
    return starts_at


def validate_demo_home_slot(
    appointment_date: date,
    time_slot: str,
    now: datetime | None = None,
) -> datetime:
    validate_booking_date(appointment_date, now)
    normalized_slot = parse_time_slot(time_slot).strftime("%I:%M %p")
    if normalized_slot not in demo_home_schedule_slots():
        raise ValueError("Choose a slot inside the configured demonstration home-visit schedule")
    starts_at = clinic_start_to_utc_naive(appointment_date, normalized_slot)
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is not None:
        now_utc = now_utc.astimezone(timezone.utc).replace(tzinfo=None)
    if starts_at <= now_utc:
        raise ValueError("Choose a future home-visit slot")
    return starts_at


def active_slot_claim(doctor_id: str, starts_at: datetime) -> str:
    normalized = starts_at.astimezone(timezone.utc).replace(tzinfo=None) if starts_at.tzinfo else starts_at
    return f"{doctor_id}:{normalized.isoformat(timespec='minutes')}Z"


def resolve_appointment_start_utc(appointment) -> datetime:
    if appointment.starts_at is not None:
        if appointment.starts_at.tzinfo is None:
            return appointment.starts_at.replace(tzinfo=timezone.utc)
        return appointment.starts_at.astimezone(timezone.utc)

    legacy_value = appointment.appointment_date
    legacy_utc = (
        legacy_value.replace(tzinfo=timezone.utc)
        if legacy_value.tzinfo is None
        else legacy_value.astimezone(timezone.utc)
    )
    clinic_value = legacy_utc.astimezone(ZoneInfo(settings.CLINIC_TIMEZONE))

    # The previous browser flow stored the selected local calendar date as a
    # UTC ISO instant. Only clinic-local midnight can be resolved without
    # guessing which date the user intended.
    if clinic_value.time().replace(tzinfo=None) != time.min:
        raise AmbiguousLegacyAppointmentTime(
            "This legacy appointment does not contain an unambiguous clinic-local date"
        )

    return clinic_start_to_utc_naive(
        clinic_value.date(),
        appointment.time_slot,
    ).replace(tzinfo=timezone.utc)
