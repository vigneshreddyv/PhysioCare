import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal, Optional


class PatientProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=24)
    gender: Optional[str] = Field(default=None, max_length=80)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Full name must contain at least 2 characters")
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            return None
        if not re.fullmatch(r"[+0-9()\- ]+", normalized):
            raise ValueError("Phone number contains unsupported characters")
        digit_count = sum(character.isdigit() for character in normalized)
        if digit_count < 7 or digit_count > 15:
            raise ValueError("Phone number must contain between 7 and 15 digits")
        return normalized

    @field_validator("gender")
    @classmethod
    def normalize_gender(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = " ".join(value.split())
        return normalized or None

class DoctorPatientOut(BaseModel):
    id: str
    full_name: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None


class ReceptionPatientOut(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str] = None


class ReceptionPatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=24)

    _normalize_full_name = field_validator("full_name")(PatientProfileUpdate.normalize_full_name.__func__)
    _validate_phone = field_validator("phone")(PatientProfileUpdate.validate_phone.__func__)


class PatientOut(DoctorPatientOut):
    email: str
    subscription_status: str


class AdminPatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=24)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(default=None, max_length=80)
    subscription_status: Optional[Literal["active", "inactive", "pending"]] = None

    _normalize_full_name = field_validator("full_name")(
        PatientProfileUpdate.normalize_full_name.__func__
    )
    _validate_phone = field_validator("phone")(
        PatientProfileUpdate.validate_phone.__func__
    )
    _normalize_gender = field_validator("gender")(
        PatientProfileUpdate.normalize_gender.__func__
    )

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value
