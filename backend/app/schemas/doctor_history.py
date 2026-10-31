from datetime import datetime

from pydantic import BaseModel

from app.schemas.appointment import AppointmentOut, DoctorAppointmentOut
from app.schemas.lab_request import LabReportOut
from app.schemas.patient import DoctorPatientOut, PatientOut


class DoctorPatientHistoryOut(BaseModel):
    patient: DoctorPatientOut
    appointments: list[DoctorAppointmentOut]
    reports: list[LabReportOut]


class PatientAdminEditAuditOut(BaseModel):
    actor_user_id: str
    changed_fields: list[str]
    changed_at: datetime


class AdminPatientHistoryOut(BaseModel):
    patient: PatientOut
    appointments: list[AppointmentOut]
    reports: list[LabReportOut]
    profile_audit: list[PatientAdminEditAuditOut]
