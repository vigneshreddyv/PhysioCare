from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, Optional
from datetime import datetime


ReportClinicalText = Annotated[str, Field(max_length=16000)]


class ReportContentSchema(BaseModel):
    symptoms: str
    findings: str
    recommendations: str


class ReportContentCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symptoms: ReportClinicalText
    findings: ReportClinicalText
    recommendations: ReportClinicalText


class ReportResponse(BaseModel):
    id: str
    patient_id: str
    booking_id: Optional[str] = None
    title: str
    category: str
    date: datetime
    description: str
    therapist: str
    content: ReportContentSchema
    has_file: bool = False
    created_at: datetime


class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=128)
    booking_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    date: datetime
    description: str = Field(max_length=8000)
    therapist: str = Field(min_length=1, max_length=200)
    content: ReportContentCreateSchema
