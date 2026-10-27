from datetime import date, datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from app.core.appointment_time import parse_time_slot
from app.core.config import settings

class AppointmentCreate(BaseModel):
    doctor_id: str
    appointment_date: date
    time_slot: str
    reason: str

    @field_validator("appointment_date", mode="before")
    @classmethod
    def normalize_calendar_date(cls, value):
        if isinstance(value, datetime):
            aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
            return aware.astimezone(ZoneInfo(settings.CLINIC_TIMEZONE)).date()
        if isinstance(value, str) and "T" in value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            aware = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
            return aware.astimezone(ZoneInfo(settings.CLINIC_TIMEZONE)).date()
        return value

    @field_validator("time_slot")
    @classmethod
    def validate_time_slot(cls, value: str) -> str:
        return parse_time_slot(value).strftime("%I:%M %p")


class AdminAppointmentCreate(AppointmentCreate):
    patient_id: str


class ReceptionAppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str
    doctor_id: str
    appointment_date: date
    time_slot: str

    _normalize_calendar_date = field_validator("appointment_date", mode="before")(
        AppointmentCreate.normalize_calendar_date.__func__
    )
    _validate_time_slot = field_validator("time_slot")(
        AppointmentCreate.validate_time_slot.__func__
    )

class AppointmentUpdate(BaseModel):
    status: Optional[Literal["scheduled", "in_progress", "completed", "cancelled", "no_show"]] = None
    billing_status: Optional[str] = None
    billing_amount: Optional[float] = None

class AppointmentOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    doctor_assignment_pending: bool = False
    appointment_date: datetime
    starts_at: Optional[datetime] = None
    clinic_timezone: str
    time_slot: str
    reason: str
    service_mode: Literal["clinic", "home_visit"] = "clinic"
    home_address: Optional[str] = None
    city: Optional[str] = None
    body_regions: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    duration_days: Optional[int] = None
    pain_severity: Optional[str] = None
    status: str
    billing_status: str
    billing_amount: float
    cancelled_at: Optional[datetime] = None
    can_patient_cancel: bool
    cancellation_deadline: Optional[datetime] = None
    cancellation_message: str
    created_at: datetime


class DoctorAppointmentOut(BaseModel):
    """Assigned clinical view without patient cancellation or financial fields."""

    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    appointment_date: datetime
    starts_at: Optional[datetime] = None
    clinic_timezone: str
    time_slot: str
    reason: str
    service_mode: Literal["clinic", "home_visit"] = "clinic"
    home_address: Optional[str] = None
    city: Optional[str] = None
    body_regions: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    duration_days: Optional[int] = None
    pain_severity: Optional[str] = None
    status: str
    created_at: datetime


class ReceptionAppointmentOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    patient_email: str
    patient_phone: Optional[str] = None
    doctor_id: str
    doctor_name: str
    doctor_assignment_pending: bool = False
    appointment_date: datetime
    starts_at: Optional[datetime] = None
    clinic_timezone: str
    time_slot: str
    service_mode: Literal["clinic", "home_visit"] = "clinic"
    home_address: Optional[str] = None
    city: Optional[str] = None
    status: str
    can_reception_cancel: bool
    cancellation_deadline: Optional[datetime] = None
    cancellation_message: str


class AppointmentSlotOut(BaseModel):
    time_slot: str
    available: bool
    availability_state: Literal["available", "occupied", "past"]


class BookingWindowOut(BaseModel):
    clinic_timezone: str
    earliest_date: date
    latest_date: date
    horizon_days: int


class AppointmentAvailabilityOut(BaseModel):
    doctor_id: str
    appointment_date: date
    clinic_timezone: str
    demo_configuration: bool = True
    configuration_label: str
    slot_minutes: int
    window_start: str
    window_end: str
    slots: list[AppointmentSlotOut]
