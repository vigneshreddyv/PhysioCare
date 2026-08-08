from datetime import datetime, time
from typing import List, Optional

from beanie import PydanticObjectId

from app.models.appointment import Appointment


class AppointmentRepository:

    @staticmethod
    async def get_by_id(id: str) -> Optional[Appointment]:
        return await Appointment.get(PydanticObjectId(id))

    @staticmethod
    async def create(appointment: Appointment) -> Appointment:
        return await appointment.insert()

    @staticmethod
    async def list_all() -> List[Appointment]:
        return await Appointment.find().sort(
            -Appointment.appointment_date
        ).to_list()

    @staticmethod
    async def list_by_patient_id(patient_id: str) -> List[Appointment]:
        return await Appointment.find(
            Appointment.patient_id == PydanticObjectId(patient_id)
        ).sort(
            -Appointment.appointment_date
        ).to_list()

    @staticmethod
    async def list_by_doctor_id(doctor_id: str) -> List[Appointment]:
        return await Appointment.find(
            Appointment.doctor_id == PydanticObjectId(doctor_id)
        ).sort(
            -Appointment.appointment_date
        ).to_list()

    @staticmethod
    async def list_today() -> List[Appointment]:
        today = datetime.utcnow().date()

        start_of_day = datetime.combine(today, time.min)
        end_of_day = datetime.combine(today, time.max)

        return await Appointment.find(
            Appointment.appointment_date >= start_of_day,
            Appointment.appointment_date <= end_of_day,
        ).to_list()

    @staticmethod
    async def doctor_has_slot(
        doctor_id: str,
        appointment_date: datetime,
        time_slot: str,
    ) -> bool:
        appointment = await Appointment.find_one(
            Appointment.doctor_id == PydanticObjectId(doctor_id),
            Appointment.appointment_date == appointment_date,
            Appointment.time_slot == time_slot,
            Appointment.status != "cancelled",
        )

        return appointment is not None

    @staticmethod
    async def patient_has_slot(
        patient_id: str,
        appointment_date: datetime,
        time_slot: str,
    ) -> bool:
        appointment = await Appointment.find_one(
            Appointment.patient_id == PydanticObjectId(patient_id),
            Appointment.appointment_date == appointment_date,
            Appointment.time_slot == time_slot,
            Appointment.status != "cancelled",
        )

        return appointment is not None