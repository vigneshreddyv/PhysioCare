from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.appointment_time import parse_time_slot
from app.core.config import settings


class DemoEntitlementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool


class DemoEntitlementOut(BaseModel):
    patient_id: str
    active: bool
    label: str = "Demo home-visit request access"
    demo_only: bool = True
    payment_configured: bool = False
    purchase_available: bool = False
    requests_enabled: bool


class AdminDemoEntitlementOut(DemoEntitlementOut):
    patient_name: str
    patient_email: str
    patient_phone: str | None = None


class HomeVisitRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferred_doctor_id: str
    home_address: str = Field(min_length=10, max_length=500)
    reason: str = Field(min_length=5, max_length=1000)
    city: str = Field(min_length=2, max_length=100)
    body_regions: list[Literal["Head", "Neck", "Shoulder", "Back", "Hip", "Knee", "Ankle", "Foot", "Other"]] = Field(min_length=1, max_length=9)
    symptoms: list[Literal["Pain", "Swelling", "Stiffness", "Muscle weakness", "Numbness", "Tingling", "Difficulty walking", "Difficulty moving", "Reduced flexibility", "Muscle tightness", "Balance problems", "Pain while standing", "Pain while sitting", "Pain while climbing stairs", "Other symptoms"]] = Field(min_length=1, max_length=15)
    duration_days: int = Field(ge=1, le=3650)
    pain_severity: Literal["low", "medium", "high"]
    save_address: bool = False

    @field_validator("home_address", "city")
    @classmethod
    def normalize_sensitive_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("This field cannot be empty")
        return normalized

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str:
        normalized = " ".join((value or "").split())
        if cls.__name__ != "HomeVisitBookingCreate" and len(normalized) < 5:
            raise ValueError("Instructions must contain at least 5 characters")
        return normalized

    @field_validator("body_regions", "symptoms")
    @classmethod
    def unique_choices(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class HomeVisitBookingCreate(HomeVisitRequestCreate):
    preferred_doctor_id: str | None = None
    reason: str | None = Field(default="", max_length=1000)
    appointment_date: date
    time_slot: str
    submission_key: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")

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
    def normalize_time_slot(cls, value: str) -> str:
        return parse_time_slot(value).strftime("%I:%M %p")


class HomeVisitDoctorAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doctor_id: str


class HomeVisitContextOut(BaseModel):
    coverage_city: str
    saved_home_address: str | None = None
    address_requires_clinic_verification: bool = True
    device_location_proves_coverage: bool = False


class HomeVisitRequestStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["approved_for_coordination", "declined"]


class HomeVisitRequestOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    patient_email: str
    patient_phone: str | None = None
    preferred_doctor_id: str
    preferred_doctor_name: str
    home_address: str
    reason: str
    city: str | None = None
    body_regions: list[str]
    symptoms: list[str]
    duration_days: int | None = None
    pain_severity: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    confirmation_message: str
    is_confirmed_appointment: bool = False
    reserves_capacity: bool = False


class ReceptionHomeVisitRequestOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    patient_email: str
    patient_phone: str | None = None
    preferred_doctor_id: str
    preferred_doctor_name: str
    home_address: str
    city: str | None = None
    status: Literal["approved_for_coordination"]
    created_at: datetime
    confirmation_message: str
    is_confirmed_appointment: bool = False
    reserves_capacity: bool = False


class DoctorHomeVisitRequestOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    patient_phone: str | None = None
    home_address: str
    reason: str
    city: str | None = None
    body_regions: list[str]
    symptoms: list[str]
    duration_days: int | None = None
    pain_severity: str | None = None
    status: Literal["approved_for_coordination"]
    created_at: datetime
    confirmation_message: str
    is_confirmed_appointment: bool = False
    reserves_capacity: bool = False
