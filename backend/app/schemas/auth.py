from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from typing import Literal

STAFF_ROLES = ("doctor", "admin", "receptionist", "laboratorian")


class UserRegister(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(..., min_length=6, max_length=1024)
    full_name: str = Field(min_length=2, max_length=100)

class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    password: str = Field(..., min_length=8, max_length=1024)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: Literal["doctor", "admin", "receptionist", "laboratorian"]
    demo_rehearsal_tag: str | None = Field(default=None, max_length=128)

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
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=1024)

class SessionResponse(BaseModel):
    role: str
    full_name: str
    email: str
    csrf_token: str


class CsrfResponse(BaseModel):
    csrf_token: str
