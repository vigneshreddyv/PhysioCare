from datetime import datetime
from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DEMO_LAB_TEST_IDS = {
    "albumin", "alp", "alt", "ast", "bilirubin", "creatinine",
    "csf-protein", "cbc", "esr", "crp", "stool-routine", "urine-routine",
}


class LabRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["home_collection", "clinic_visit"]
    selected_tests: list[str] = Field(min_length=1, max_length=12)
    home_address: str | None = Field(default=None, min_length=10, max_length=500)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    save_address: bool = False

    @model_validator(mode="after")
    def validate_request(self):
        self.selected_tests = list(dict.fromkeys(self.selected_tests))
        if not set(self.selected_tests).issubset(DEMO_LAB_TEST_IDS):
            raise ValueError("One or more laboratory tests are not in the demo catalogue")
        if self.mode == "home_collection" and (not self.home_address or not self.city):
            raise ValueError("Home collection requires a city and address")
        if self.mode == "clinic_visit":
            self.home_address = None
            self.city = None
            self.save_address = False
        if self.home_address:
            self.home_address = " ".join(self.home_address.split())
        if self.city:
            self.city = " ".join(self.city.split())
        return self


class LabRequestStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["approved_for_coordination", "declined"]


class LabRequestAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    laboratorian_user_id: str = Field(min_length=24, max_length=24)

    @field_validator("laboratorian_user_id")
    @classmethod
    def validate_object_id(cls, value: str) -> str:
        if not PydanticObjectId.is_valid(value):
            raise ValueError("Choose a valid Laboratorian account")
        return value


class LaboratorianSummary(BaseModel):
    id: str
    full_name: str


class LabReportOut(BaseModel):
    request_id: str
    patient_name: str | None = None
    selected_tests: list[str]
    report_status: str
    report_file_name: str | None = None
    report_uploaded_at: datetime | None = None
    report_released_at: datetime | None = None


class LaboratorianLabRequestOut(BaseModel):
    id: str
    patient_name: str
    patient_phone: str | None = None
    mode: str
    selected_tests: list[str]
    home_address: str | None = None
    city: str | None = None
    status: str
    report_status: str
    report_file_name: str | None = None
    report_uploaded_at: datetime | None = None
    created_at: datetime


class LabRequestOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    patient_email: str
    patient_phone: str | None = None
    mode: str
    selected_tests: list[str]
    home_address: str | None = None
    city: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    confirmation_message: str
    payment_configured: bool = False
    is_confirmed_booking: bool = False
    assigned_laboratorian_user_id: str | None = None
    assigned_laboratorian_name: str | None = None
    report_status: str = "not_started"
    report_file_name: str | None = None
    report_uploaded_at: datetime | None = None
    report_released_at: datetime | None = None
