from datetime import datetime, time
from typing import List, Optional

from beanie import PydanticObjectId
from pymongo import ReturnDocument

from app.models.appointment import Appointment


class AppointmentRepository:

    @staticmethod
    async def get_by_id(id: str) -> Optional[Appointment]:
        try:
            return await Appointment.get(PydanticObjectId(id))
        except (ValueError, TypeError):
            return None

    @staticmethod
    async def create(appointment: Appointment) -> Appointment:
        return await appointment.insert()

    @staticmethod
    async def get_by_submission_claim(submission_claim: str) -> Optional[Appointment]:
        return await Appointment.find_one(Appointment.submission_claim == submission_claim)

    @staticmethod
    async def assign_home_visit_doctor(
        appointment_id: str,
        current_doctor_id: str,
        doctor_id: str,
        slot_claim: str,
        changed_by_user_id: str,
        changed_at: datetime,
    ) -> Optional[Appointment]:
        try:
            appointment_object_id = PydanticObjectId(appointment_id)
            current_doctor_object_id = PydanticObjectId(current_doctor_id)
            doctor_object_id = PydanticObjectId(doctor_id)
            actor_object_id = PydanticObjectId(changed_by_user_id)
        except (ValueError, TypeError):
            return None

        updated = await Appointment.get_pymongo_collection().find_one_and_update(
            {
                "_id": appointment_object_id,
                "doctor_id": current_doctor_object_id,
                "service_mode": "home_visit",
                "status": "scheduled",
            },
            {
                "$set": {
                    "doctor_id": doctor_object_id,
                    "doctor_assignment_pending": False,
                    "slot_claim": slot_claim,
                },
                "$push": {
                    "doctor_assignment_audit": {
                        "changed_by_user_id": actor_object_id,
                        "previous_doctor_id": current_doctor_object_id,
                        "new_doctor_id": doctor_object_id,
                        "changed_at": changed_at,
                    }
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            return None
        return Appointment.model_validate(updated)

    @staticmethod
    async def cancel_scheduled_owned(
        appointment_id: str,
        patient_id: str,
        cancelled_at: datetime,
    ) -> bool:
        result = await Appointment.get_pymongo_collection().update_one(
            {
                "_id": PydanticObjectId(appointment_id),
                "patient_id": PydanticObjectId(patient_id),
                "status": "scheduled",
            },
            {
                "$set": {"status": "cancelled", "cancelled_at": cancelled_at},
                "$unset": {"slot_claim": ""},
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def cancel_scheduled(
        appointment_id: str,
        cancelled_at: datetime,
    ) -> bool:
        result = await Appointment.get_pymongo_collection().update_one(
            {
                "_id": PydanticObjectId(appointment_id),
                "status": "scheduled",
            },
            {
                "$set": {"status": "cancelled", "cancelled_at": cancelled_at},
                "$unset": {"slot_claim": ""},
            },
        )
        return result.modified_count == 1

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
    async def list_active_by_doctor_id(doctor_id: str) -> List[Appointment]:
        return await Appointment.find({
            "doctor_id": PydanticObjectId(doctor_id),
            "status": {"$in": ["scheduled", "in_progress"]},
        }).to_list()

    @staticmethod
    async def list_operational_schedule() -> List[Appointment]:
        return await Appointment.find({
            "status": {"$in": ["scheduled", "in_progress"]},
        }).sort(+Appointment.appointment_date).to_list()

    @staticmethod
    async def list_today() -> List[Appointment]:
        today = datetime.utcnow().date()

        start_of_day = datetime.combine(today, time.min)
        end_of_day = datetime.combine(today, time.max)

        return await Appointment.find(
            Appointment.appointment_date >= start_of_day,
            Appointment.appointment_date <= end_of_day,
        ).to_list()
