from pydantic import BaseModel, EmailStr, Field
from typing import Literal

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str

class StaffCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: Literal["doctor", "admin", "receptionist", "laboratorian"]

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
