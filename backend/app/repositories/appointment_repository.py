from datetime import datetime, time
from typing import List, Optional
from beanie import PydanticObjectId
from app.models.appointment import Appointment

class AppointmentRepository:
    @staticmethod
    async def get_by_id(id: str) -> Optional[Appointment]:
        return await Appointment.get(PydanticObjectId(id), fetch_links=True)

    @staticmethod
    async def create(appointment: Appointment) -> Appointment:
        return await appointment.insert()

    @staticmethod
    async def list_all() -> List[Appointment]:
        return await Appointment.find(fetch_links=True).sort(-Appointment.appointment_date).to_list()

    @staticmethod
    async def list_by_patient_id(patient_id: str) -> List[Appointment]:
        return await Appointment.find({"patient.$id": PydanticObjectId(patient_id)}, fetch_links=True).sort(-Appointment.appointment_date).to_list()

    @staticmethod
    async def list_by_doctor_id(doctor_id: str) -> List[Appointment]:
        return await Appointment.find({"doctor.$id": PydanticObjectId(doctor_id)}, fetch_links=True).sort(-Appointment.appointment_date).to_list()

    @staticmethod
    async def list_today() -> List[Appointment]:
        # Filter from start of today to end of today UTC
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, time.min)
        end_of_day = datetime.combine(today, time.max)
        return await Appointment.find(
            Appointment.appointment_date >= start_of_day,
            Appointment.appointment_date <= end_of_day,
            fetch_links=True
        ).to_list()
