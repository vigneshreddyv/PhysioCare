from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal

STAFF_ROLES = ("doctor", "admin", "receptionist", "laboratorian")


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str

class StaffCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)
    role: Literal["doctor", "admin", "receptionist", "laboratorian"]
    demo_rehearsal_tag: str | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class StaffOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: Literal["doctor", "admin", "receptionist", "laboratorian"]
    is_active: bool
    created_at: datetime | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str

class SessionResponse(BaseModel):
    role: str
    full_name: str
    email: str
    csrf_token: str


class CsrfResponse(BaseModel):
    csrf_token: str
