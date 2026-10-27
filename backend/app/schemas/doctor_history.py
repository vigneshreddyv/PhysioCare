from pydantic import BaseModel

from app.schemas.appointment import DoctorAppointmentOut
from app.schemas.lab_request import LabReportOut
from app.schemas.patient import DoctorPatientOut


class DoctorPatientHistoryOut(BaseModel):
    patient: DoctorPatientOut
    appointments: list[DoctorAppointmentOut]
    reports: list[LabReportOut]
