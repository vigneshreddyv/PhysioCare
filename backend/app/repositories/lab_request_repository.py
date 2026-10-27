from datetime import datetime

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.models.lab_request import LabRequest


class LabRequestRepository:
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
    async def assign_laboratorian(request_id: str, laboratorian_id: str, admin_id: str) -> bool:
        now = datetime.utcnow()
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
        now = datetime.utcnow()
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
        now = datetime.utcnow()
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
        now = datetime.utcnow()
        updates = {"status": target, "updated_at": now}
        if actor_id:
            updates.update({"reviewed_by_user_id": PydanticObjectId(actor_id), "reviewed_at": now})
        result = await LabRequest.get_pymongo_collection().update_one(
            {"_id": PydanticObjectId(request_id), "status": {"$in": allowed_from}},
            {"$set": updates},
        )
        return result.modified_count == 1
