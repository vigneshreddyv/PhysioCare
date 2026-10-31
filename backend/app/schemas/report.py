from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ReportContentSchema(BaseModel):
    symptoms: str
    findings: str
    recommendations: str


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
    patient_id: str
    booking_id: Optional[str] = None
    title: str
    category: str
    date: datetime
    description: str
    therapist: str
    content: ReportContentSchema
