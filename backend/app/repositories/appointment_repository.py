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
        return await AppointmentRepository._cancel_scheduled(
            appointment_id, cancelled_at, patient_id=patient_id
        )

    @staticmethod
    async def cancel_scheduled(
        appointment_id: str,
        cancelled_at: datetime,
    ) -> bool:
        return await AppointmentRepository._cancel_scheduled(appointment_id, cancelled_at)

    @staticmethod
    async def _cancel_scheduled(
        appointment_id: str,
        cancelled_at: datetime,
        patient_id: str | None = None,
    ) -> bool:
        """Atomically cancel while preserving a verified capture for reconciliation.

        The paid and unpaid branches race safely with payment finalization because
        both transitions condition on the appointment still being scheduled.
        """
        try:
            appointment_object_id = PydanticObjectId(appointment_id)
            patient_object_id = PydanticObjectId(patient_id) if patient_id else None
        except (ValueError, TypeError):
            return False

        collection = Appointment.get_pymongo_collection()
        base_filter = {"_id": appointment_object_id, "status": "scheduled"}
        if patient_object_id is not None:
            base_filter["patient_id"] = patient_object_id

        paid_filter = {
            **base_filter,
            "billing_status": "paid",
            "payment_status": "success",
        }
        result = await collection.update_one(
            paid_filter,
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": cancelled_at,
                    "payment_status": "reconciliation_required",
                },
                "$unset": {"slot_claim": ""},
            },
        )
        if result.modified_count == 1:
            return True

        legacy_paid_filter = {
            **base_filter,
            "billing_status": "paid",
            "payment_status": {"$ne": "success"},
        }
        result = await collection.update_one(
            legacy_paid_filter,
            {
                "$set": {"status": "cancelled", "cancelled_at": cancelled_at},
                "$unset": {"slot_claim": ""},
            },
        )
        if result.modified_count == 1:
            return True

        unpaid_filter = {**base_filter, "billing_status": {"$ne": "paid"}}
        result = await collection.update_one(
            unpaid_filter,
            {
                "$set": {"status": "cancelled", "cancelled_at": cancelled_at},
                "$unset": {"slot_claim": ""},
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def cancel_from_status(
        appointment_id: str,
        expected_status: str,
        cancelled_at: datetime,
    ) -> bool:
        """Admin status-edit cancellation, guarded against stale model saves."""
        if expected_status == "scheduled":
            return await AppointmentRepository.cancel_scheduled(appointment_id, cancelled_at)
        try:
            object_id = PydanticObjectId(appointment_id)
        except (ValueError, TypeError):
            return False
        collection = Appointment.get_pymongo_collection()
        captured_filter = {
            "_id": object_id,
            "status": expected_status,
            "billing_status": "paid",
            "payment_status": "success",
        }
        result = await collection.update_one(
            captured_filter,
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": cancelled_at,
                    "payment_status": "reconciliation_required",
                },
                "$unset": {"slot_claim": ""},
            },
        )
        if result.modified_count == 1:
            return True
        legacy_paid_filter = {
            "_id": object_id,
            "status": expected_status,
            "billing_status": "paid",
            "payment_status": {"$ne": "success"},
        }
        result = await collection.update_one(
            legacy_paid_filter,
            {
                "$set": {"status": "cancelled", "cancelled_at": cancelled_at},
                "$unset": {"slot_claim": ""},
            },
        )
        if result.modified_count == 1:
            return True
        result = await collection.update_one(
            {
                "_id": object_id,
                "status": expected_status,
                "billing_status": {"$ne": "paid"},
            },
            {
                "$set": {"status": "cancelled", "cancelled_at": cancelled_at},
                "$unset": {"slot_claim": ""},
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def mark_cancelled_capture_for_reconciliation(
        appointment_id: str,
        order_id: str,
        payment_id: str,
        currency: str,
    ) -> bool:
        try:
            object_id = PydanticObjectId(appointment_id)
        except (ValueError, TypeError):
            return False
        result = await Appointment.get_pymongo_collection().update_one(
            {
                "_id": object_id,
                "status": "cancelled",
                "$or": [
                    {"payment_order_id": order_id},
                    {"payment_order_id": None},
                ],
            },
            {
                "$set": {
                    "payment_status": "reconciliation_required",
                    "payment_order_id": order_id,
                    "payment_id": payment_id,
                    "billing_currency": currency,
                }
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
