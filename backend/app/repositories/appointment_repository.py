from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from beanie import PydanticObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from app.core.time import utc_now
from app.core.pagination import PageWindow
from app.core.config import settings
from app.models.appointment import Appointment


class AppointmentMutationConflict(Exception):
    """The appointment changed after the caller loaded it."""


class AppointmentRepository:
    @staticmethod
    def _revision_filter(expected_revision: int) -> dict:
        if expected_revision == 0:
            return {"$or": [{"revision": 0}, {"revision": {"$exists": False}}]}
        return {"revision": expected_revision}

    @staticmethod
    async def update_if_revision(
        appointment_id: str,
        *,
        patient_id,
        doctor_id,
        expected_revision: int,
        set_fields: dict,
        unset_fields: dict | None = None,
    ) -> Appointment:
        update = {"$set": set_fields, "$inc": {"revision": 1}}
        if unset_fields:
            update["$unset"] = unset_fields
        row = await Appointment.get_pymongo_collection().find_one_and_update(
            {
                "_id": PydanticObjectId(appointment_id),
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                **AppointmentRepository._revision_filter(expected_revision),
            },
            update,
            return_document=ReturnDocument.AFTER,
        )
        if row is None:
            raise AppointmentMutationConflict
        return Appointment.model_validate(row)

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
                "$inc": {"revision": 1},
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
        expected_revision: int | None = None,
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
        if expected_revision is not None:
            base_filter.update(AppointmentRepository._revision_filter(expected_revision))

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
                "$inc": {"revision": 1},
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
                "$inc": {"revision": 1},
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
                "$inc": {"revision": 1},
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def cancel_from_status(
        appointment_id: str,
        expected_status: str,
        cancelled_at: datetime,
        expected_revision: int | None = None,
    ) -> bool:
        """Admin status-edit cancellation, guarded against stale model saves."""
        if expected_status == "scheduled":
            return await AppointmentRepository._cancel_scheduled(
                appointment_id, cancelled_at, expected_revision=expected_revision
            )
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
        if expected_revision is not None:
            captured_filter.update(AppointmentRepository._revision_filter(expected_revision))
        result = await collection.update_one(
            captured_filter,
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": cancelled_at,
                    "payment_status": "reconciliation_required",
                },
                "$unset": {"slot_claim": ""},
                "$inc": {"revision": 1},
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
        if expected_revision is not None:
            legacy_paid_filter.update(AppointmentRepository._revision_filter(expected_revision))
        result = await collection.update_one(
            legacy_paid_filter,
            {
                "$set": {"status": "cancelled", "cancelled_at": cancelled_at},
                "$unset": {"slot_claim": ""},
                "$inc": {"revision": 1},
            },
        )
        if result.modified_count == 1:
            return True
        unpaid_filter = {
                "_id": object_id,
                "status": expected_status,
                "billing_status": {"$ne": "paid"},
            }
        if expected_revision is not None:
            unpaid_filter.update(AppointmentRepository._revision_filter(expected_revision))
        result = await collection.update_one(
            unpaid_filter,
            {
                "$set": {"status": "cancelled", "cancelled_at": cancelled_at},
                "$unset": {"slot_claim": ""},
                "$inc": {"revision": 1},
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
                },
                "$inc": {"revision": 1},
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
    async def list_page_all(page: PageWindow) -> List[Appointment]:
        return await Appointment.find().sort(
            "-appointment_date", "-_id"
        ).skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def list_page_scheduled_home_visits(page: PageWindow) -> list[dict]:
        return await Appointment.get_pymongo_collection().aggregate([
            {"$match": {"service_mode": "home_visit", "status": "scheduled"}},
            {"$sort": {"appointment_date": 1, "_id": 1}},
            {"$skip": page.offset}, {"$limit": page.size},
            {"$lookup": {"from": "patients", "localField": "patient_id",
                         "foreignField": "_id", "as": "patient"}},
            {"$lookup": {"from": "users", "localField": "patient.user_id",
                         "foreignField": "_id", "as": "patient_user"}},
            {"$project": {"_id": 1, "doctor_id": 1, "doctor_assignment_pending": 1,
                          "appointment_date": 1, "time_slot": 1,
                          "patient_name": {"$ifNull": [
                              {"$arrayElemAt": ["$patient_user.full_name", 0]},
                              "Patient record unavailable",
                          ]}}},
        ]).to_list(length=page.size)

    @staticmethod
    async def list_page_billing(
        page: PageWindow, billing_status: str | None = None,
        start_date: date | None = None, end_date: date | None = None,
    ) -> List[Appointment]:
        query = {}
        if billing_status:
            query["billing_status"] = billing_status
        if start_date or end_date:
            bounds = {}
            if start_date:
                bounds["$gte"] = datetime.combine(start_date, time.min)
            if end_date:
                bounds["$lt"] = datetime.combine(end_date + timedelta(days=1), time.min)
            query["appointment_date"] = bounds
        return await Appointment.find(query).sort(
            "-appointment_date", "-_id"
        ).skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def list_page_by_patient_id(
        patient_id: str, page: PageWindow, service_mode: str | None = None,
        start_date: date | None = None, end_date: date | None = None,
    ) -> List[Appointment]:
        query = {
            "patient_id": PydanticObjectId(patient_id),
        }
        if service_mode:
            query["service_mode"] = service_mode
        if start_date or end_date:
            query["appointment_date"] = {}
            if start_date:
                query["appointment_date"]["$gte"] = datetime.combine(start_date, time.min)
            if end_date:
                query["appointment_date"]["$lt"] = datetime.combine(end_date + timedelta(days=1), time.min)
        return await Appointment.find(query).sort(
            "-appointment_date", "-_id"
        ).skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def list_page_by_patient_status(
        patient_id: str, statuses: list[str], page: PageWindow, ascending: bool = False,
        future_only: bool = False,
    ) -> List[Appointment]:
        direction = "+" if ascending else "-"
        query = {
            "patient_id": PydanticObjectId(patient_id),
            "status": {"$in": statuses},
        }
        if future_only:
            clinic_today = datetime.now(ZoneInfo(settings.CLINIC_TIMEZONE)).date()
            query["$or"] = [
                {"starts_at": {"$gte": utc_now()}},
                {"starts_at": None, "appointment_date": {
                    "$gte": datetime.combine(clinic_today, time.min),
                }},
            ]
        return await Appointment.find(query).sort(
            f"{direction}appointment_date", f"{direction}time_slot", f"{direction}_id",
        ).skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def list_page_by_doctor_id(
        doctor_id: str, page: PageWindow, statuses: list[str] | None = None,
        start_date: date | None = None, end_date: date | None = None,
    ) -> List[Appointment]:
        query = {
            "doctor_id": PydanticObjectId(doctor_id),
            "doctor_assignment_pending": {"$ne": True},
        }
        if statuses:
            query["status"] = {"$in": statuses}
        if start_date or end_date:
            query["appointment_date"] = {}
            if start_date:
                query["appointment_date"]["$gte"] = datetime.combine(start_date, time.min)
            if end_date:
                query["appointment_date"]["$lt"] = datetime.combine(end_date + timedelta(days=1), time.min)
        return await Appointment.find(query).sort("-appointment_date", "-_id").skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def doctor_dashboard_summary(doctor_id: str) -> dict[str, int]:
        rows = await Appointment.get_pymongo_collection().aggregate([
            {"$match": {"doctor_id": PydanticObjectId(doctor_id),
                        "doctor_assignment_pending": {"$ne": True}}},
            {"$facet": {
                "statuses": [{"$group": {"_id": "$status", "count": {"$sum": 1}}}],
                "patients": [{"$group": {"_id": "$patient_id"}}, {"$count": "count"}],
            }},
        ]).to_list(length=1)
        result = rows[0] if rows else {"statuses": [], "patients": []}
        counts = {row["_id"]: row["count"] for row in result["statuses"]}
        return {
            "open_visits": counts.get("scheduled", 0) + counts.get("in_progress", 0),
            "completed_sessions": counts.get("completed", 0),
            "assigned_patients": result["patients"][0]["count"] if result["patients"] else 0,
        }

    @staticmethod
    async def has_assigned_patient(doctor_id: str, patient_id: str) -> bool:
        try:
            doctor_object_id = PydanticObjectId(doctor_id)
            patient_object_id = PydanticObjectId(patient_id)
        except (InvalidId, ValueError, TypeError):
            return False
        appointment = await Appointment.find_one({
            "doctor_id": doctor_object_id,
            "patient_id": patient_object_id,
            "doctor_assignment_pending": {"$ne": True},
        })
        return appointment is not None

    @staticmethod
    async def list_page_by_doctor_and_patient(
        doctor_id: str, patient_id: str, page: PageWindow,
        statuses: list[str] | None = None,
        start_date: date | None = None, end_date: date | None = None,
    ) -> List[Appointment]:
        query = {
            "doctor_id": PydanticObjectId(doctor_id),
            "patient_id": PydanticObjectId(patient_id),
            "doctor_assignment_pending": {"$ne": True},
        }
        if statuses:
            query["status"] = {"$in": statuses}
        if start_date or end_date:
            query["appointment_date"] = {}
            if start_date:
                query["appointment_date"]["$gte"] = datetime.combine(start_date, time.min)
            if end_date:
                query["appointment_date"]["$lt"] = datetime.combine(end_date + timedelta(days=1), time.min)
        return await Appointment.find(query).sort("-appointment_date", "-_id").skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def list_page_operational_schedule(
        page: PageWindow, start_date: date | None = None, end_date: date | None = None,
    ) -> List[Appointment]:
        query = {
            "status": {"$in": ["scheduled", "in_progress"]},
        }
        if start_date or end_date:
            query["appointment_date"] = {}
            if start_date:
                query["appointment_date"]["$gte"] = datetime.combine(start_date, time.min)
            if end_date:
                query["appointment_date"]["$lt"] = datetime.combine(end_date + timedelta(days=1), time.min)
        projection = {field: 1 for field in (
            "patient_id", "doctor_id", "doctor_assignment_pending", "appointment_date",
            "starts_at", "clinic_timezone", "time_slot", "service_mode",
            "home_address", "city", "status",
        )}
        rows = await Appointment.get_pymongo_collection().find(query, projection).sort(
            [("appointment_date", 1), ("_id", 1)],
        ).skip(page.offset).limit(page.size).to_list(length=page.size)
        return [SimpleNamespace(
            id=row["_id"], patient_id=row["patient_id"], doctor_id=row["doctor_id"],
            appointment_date=row["appointment_date"], time_slot=row["time_slot"],
            status=row["status"], starts_at=row.get("starts_at"),
            clinic_timezone=row.get("clinic_timezone"),
            service_mode=row.get("service_mode", "clinic"),
            home_address=row.get("home_address"), city=row.get("city"),
            doctor_assignment_pending=row.get("doctor_assignment_pending", False),
        ) for row in rows]

    @staticmethod
    async def reception_schedule_summary(
        start_date: date | None = None, end_date: date | None = None,
    ) -> dict[str, int]:
        query = {"status": {"$in": ["scheduled", "in_progress"]}}
        if start_date or end_date:
            query["appointment_date"] = {}
            if start_date:
                query["appointment_date"]["$gte"] = datetime.combine(start_date, time.min)
            if end_date:
                query["appointment_date"]["$lt"] = datetime.combine(end_date + timedelta(days=1), time.min)
        rows = await Appointment.get_pymongo_collection().aggregate([
            {"$match": query}, {"$count": "active_appointments"},
        ]).to_list(length=1)
        return {"active_appointments": rows[0]["active_appointments"] if rows else 0}

    @staticmethod
    async def distinct_assigned_patient_ids(doctor_id: str) -> list[str]:
        ids = await Appointment.get_pymongo_collection().distinct("patient_id", {
            "doctor_id": PydanticObjectId(doctor_id),
            "doctor_assignment_pending": {"$ne": True},
        })
        return [str(item) for item in ids]

    @staticmethod
    async def page_assigned_patient_ids(doctor_id: str, page: PageWindow) -> list[str]:
        cursor = Appointment.get_pymongo_collection().aggregate([
            {"$match": {
                "doctor_id": PydanticObjectId(doctor_id),
                "doctor_assignment_pending": {"$ne": True},
            }},
            {"$group": {"_id": "$patient_id"}},
            {"$sort": {"_id": 1}},
            {"$skip": page.offset},
            {"$limit": page.size},
        ])
        return [str(item["_id"]) for item in await cursor.to_list(length=page.size)]

    @staticmethod
    async def list_active_by_doctor_id(
        doctor_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> List[Appointment]:
        base_filter = {
            "doctor_id": PydanticObjectId(doctor_id),
            "status": {"$in": ["scheduled", "in_progress"]},
        }
        if start_date is None and end_date is None:
            # Legacy internal callers retain their old contract. Runtime
            # availability and publication paths pass a calendar window.
            return await Appointment.find(base_filter).to_list()
        if start_date is None or end_date is None or end_date < start_date:
            raise ValueError("A complete appointment date window is required")

        clinic_zone = ZoneInfo(settings.CLINIC_TIMEZONE)
        clinic_start = datetime.combine(start_date, time.min, tzinfo=clinic_zone)
        clinic_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=clinic_zone)
        utc_start = clinic_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = clinic_end.astimezone(timezone.utc).replace(tzinfo=None)
        # Older records stored the clinic-local date as a UTC instant. The
        # padded date range includes those records without scanning history.
        legacy_start = datetime.combine(start_date - timedelta(days=1), time.min)
        legacy_end = datetime.combine(end_date + timedelta(days=1), time.min)
        cursor = Appointment.get_pymongo_collection().find(
            {**base_filter, "$or": [
                {"starts_at": {"$gte": utc_start, "$lt": utc_end}},
                {"appointment_date": {"$gte": legacy_start, "$lt": legacy_end}},
            ]},
            {"starts_at": 1, "appointment_date": 1, "time_slot": 1, "service_mode": 1},
        )
        return [SimpleNamespace(
            id=item["_id"],
            starts_at=item.get("starts_at"),
            appointment_date=item.get("appointment_date"),
            time_slot=item.get("time_slot"),
            service_mode=item.get("service_mode", "clinic"),
        ) for item in await cursor.to_list(length=None)]

    @staticmethod
    async def list_operational_schedule() -> List[Appointment]:
        return await Appointment.find({
            "status": {"$in": ["scheduled", "in_progress"]},
        }).sort(+Appointment.appointment_date).to_list()

    @staticmethod
    async def list_today() -> List[Appointment]:
        today = utc_now().date()

        start_of_day = datetime.combine(today, time.min)
        end_of_day = datetime.combine(today, time.max)

        return await Appointment.find(
            Appointment.appointment_date >= start_of_day,
            Appointment.appointment_date <= end_of_day,
        ).to_list()
