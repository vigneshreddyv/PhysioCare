from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.core.time import utc_now
from app.models.lab_request import LabRequest
from app.core.pagination import PageWindow


class LabRequestRepository:
    _CLINICAL_LIST_PROJECTION = {
        "patient_id": 1,
        "mode": 1,
        "selected_tests": 1,
        "home_address": 1,
        "city": 1,
        "status": 1,
        "assigned_laboratorian_user_id": 1,
        "report_status": 1,
        "report_file_name": 1,
        "report_uploaded_at": 1,
        "report_released_at": 1,
        "created_at": 1,
        "updated_at": 1,
    }

    @staticmethod
    async def _list_clinical_page(query: dict, page: PageWindow, sort_field: str):
        rows = await LabRequest.get_pymongo_collection().find(
            query, LabRequestRepository._CLINICAL_LIST_PROJECTION,
        ).sort([(sort_field, -1), ("_id", -1)]).skip(page.offset).limit(
            page.size,
        ).to_list(length=page.size)
        return [SimpleNamespace(
            id=row["_id"],
            patient_id=row["patient_id"],
            mode=row["mode"],
            selected_tests=row.get("selected_tests", []),
            home_address=row.get("home_address"),
            city=row.get("city"),
            status=row["status"],
            assigned_laboratorian_user_id=row.get("assigned_laboratorian_user_id"),
            report_status=row.get("report_status", "not_started"),
            report_file_name=row.get("report_file_name"),
            report_uploaded_at=row.get("report_uploaded_at"),
            report_released_at=row.get("report_released_at"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ) for row in rows]

    @staticmethod
    async def create(request: LabRequest) -> LabRequest:
        return await request.insert()

    @staticmethod
    async def create_idempotent(request: LabRequest) -> LabRequest:
        try:
            return await request.insert()
        except DuplicateKeyError:
            existing = await LabRequest.find_one({
                "patient_id": request.patient_id,
                "submission_key": request.submission_key,
            })
            if existing:
                return existing
            raise

    @staticmethod
    async def get(request_id: str) -> LabRequest | None:
        try:
            return await LabRequest.get(PydanticObjectId(request_id))
        except (ValueError, TypeError):
            return None

    @staticmethod
    async def list_for_patient(patient_id: str) -> list[LabRequest]:
        return await LabRequest.find(LabRequest.patient_id == PydanticObjectId(patient_id)).sort(-LabRequest.created_at).to_list()

    @staticmethod
    async def list_all() -> list[LabRequest]:
        return await LabRequest.find().sort(-LabRequest.created_at).to_list()

    @staticmethod
    async def list_for_laboratorian(user_id: str) -> list[LabRequest]:
        return await LabRequest.find(
            LabRequest.assigned_laboratorian_user_id == PydanticObjectId(user_id)
        ).sort(-LabRequest.updated_at).to_list()

    @staticmethod
    async def list_released_for_patients(patient_ids: list[str]) -> list[LabRequest]:
        if not patient_ids:
            return []
        return await LabRequest.find({
            "patient_id": {"$in": [PydanticObjectId(patient_id) for patient_id in patient_ids]},
            "report_status": "released",
        }).sort(-LabRequest.report_released_at).to_list()

    @staticmethod
    async def list_page_for_patient(
        patient_id: str, page: PageWindow, recent_updates: bool = False,
    ) -> list[LabRequest]:
        return await LabRequestRepository._list_clinical_page(
            {"patient_id": PydanticObjectId(patient_id)},
            page,
            "updated_at" if recent_updates else "created_at",
        )

    @staticmethod
    async def list_page_all(page: PageWindow) -> list[LabRequest]:
        return await LabRequestRepository._list_clinical_page({}, page, "created_at")

    @staticmethod
    async def list_page_for_laboratorian(user_id: str, page: PageWindow) -> list[LabRequest]:
        return await LabRequestRepository._list_clinical_page(
            {"assigned_laboratorian_user_id": PydanticObjectId(user_id)},
            page,
            "updated_at",
        )

    @staticmethod
    async def list_page_released_for_patients(
        patient_ids: list[str], page: PageWindow,
        start_date: date | None = None, end_date: date | None = None,
    ) -> list[LabRequest]:
        if not patient_ids:
            return []
        query = {
            "patient_id": {"$in": [PydanticObjectId(patient_id) for patient_id in patient_ids]},
            "report_status": "released",
        }
        if start_date or end_date:
            query["report_released_at"] = {}
            if start_date:
                query["report_released_at"]["$gte"] = datetime.combine(start_date, time.min)
            if end_date:
                query["report_released_at"]["$lt"] = datetime.combine(end_date + timedelta(days=1), time.min)
        return await LabRequest.find(query).sort("-report_released_at", "-_id").skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def list_page_released_for_doctor(doctor_id: str, page: PageWindow) -> list[LabRequest]:
        """Page released reports after checking assignment inside MongoDB."""
        doctor_object_id = PydanticObjectId(doctor_id)
        cursor = LabRequest.get_pymongo_collection().aggregate([
            {"$match": {"report_status": "released"}},
            {"$sort": {"report_released_at": -1, "_id": -1}},
            {"$lookup": {
                "from": "appointments",
                "let": {"report_patient_id": "$patient_id"},
                "pipeline": [
                    {"$match": {
                        "doctor_id": doctor_object_id,
                        "doctor_assignment_pending": {"$ne": True},
                        "$expr": {"$eq": ["$patient_id", "$$report_patient_id"]},
                    }},
                    {"$limit": 1},
                    {"$project": {"_id": 1}},
                ],
                "as": "assigned_appointments",
            }},
            {"$match": {"assigned_appointments.0": {"$exists": True}}},
            {"$skip": page.offset},
            {"$limit": page.size},
            {"$project": {"assigned_appointments": 0}},
        ])
        return [LabRequest.model_validate(row) for row in await cursor.to_list(length=page.size)]

    @staticmethod
    async def assign_laboratorian(request_id: str, laboratorian_id: str, admin_id: str) -> bool:
        now = utc_now()
        result = await LabRequest.get_pymongo_collection().update_one(
            {
                "_id": PydanticObjectId(request_id),
                "status": "approved_for_coordination",
                "report_status": {"$ne": "released"},
            },
            {
                "$set": {
                    "assigned_laboratorian_user_id": PydanticObjectId(laboratorian_id),
                    "assigned_by_user_id": PydanticObjectId(admin_id),
                    "assigned_at": now,
                    "updated_at": now,
                },
                "$push": {
                    "assignment_history": {
                        "laboratorian_user_id": laboratorian_id,
                        "assigned_by_user_id": admin_id,
                        "assigned_at": now,
                    }
                },
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def save_finalized_report(
        request_id: str,
        laboratorian_id: str,
        *,
        expected_storage_key: str | None,
        storage_key: str,
        file_name: str,
        content_type: str,
        size_bytes: int,
    ) -> bool:
        now = utc_now()
        result = await LabRequest.get_pymongo_collection().update_one(
            {
                "_id": PydanticObjectId(request_id),
                "assigned_laboratorian_user_id": PydanticObjectId(laboratorian_id),
                "status": "approved_for_coordination",
                "report_status": {"$ne": "released"},
                "report_storage_key": expected_storage_key,
            },
            {
                "$set": {
                    "report_status": "awaiting_publication",
                    "report_storage_key": storage_key,
                    "report_file_name": file_name,
                    "report_content_type": content_type,
                    "report_size_bytes": size_bytes,
                    "report_uploaded_by_user_id": PydanticObjectId(laboratorian_id),
                    "report_uploaded_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def publish_report(
        request_id: str,
        admin_id: str,
        *,
        expected_storage_key: str,
    ) -> bool:
        now = utc_now()
        result = await LabRequest.get_pymongo_collection().update_one(
            {
                "_id": PydanticObjectId(request_id),
                "status": "approved_for_coordination",
                "report_status": "awaiting_publication",
                "report_storage_key": expected_storage_key,
            },
            {
                "$set": {
                    "report_status": "released",
                    "report_released_by_user_id": PydanticObjectId(admin_id),
                    "report_released_at": now,
                    "updated_at": now,
                },
                "$push": {
                    "report_publication_history": {
                        "action": "administratively_published",
                        "published_by_user_id": admin_id,
                        "published_at": now,
                        "storage_key": expected_storage_key,
                    }
                },
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def transition(request_id: str, allowed_from: list[str], target: str, actor_id: str | None = None) -> bool:
        now = utc_now()
        updates = {"status": target, "updated_at": now}
        if actor_id:
            updates.update({"reviewed_by_user_id": PydanticObjectId(actor_id), "reviewed_at": now})
        result = await LabRequest.get_pymongo_collection().update_one(
            {"_id": PydanticObjectId(request_id), "status": {"$in": allowed_from}},
            {"$set": updates},
        )
        return result.modified_count == 1
