from beanie import PydanticObjectId

from app.core.time import utc_now
from app.models.demo_entitlement import DemoEntitlement
from app.models.home_visit_request import HomeVisitRequest


class DemoServiceRepository:
    @staticmethod
    async def get_entitlement(patient_id: str) -> DemoEntitlement | None:
        return await DemoEntitlement.find_one(
            DemoEntitlement.patient_id == PydanticObjectId(patient_id)
        )

    @staticmethod
    async def set_entitlement(patient_id: str, admin_user_id: str, active: bool) -> DemoEntitlement:
        now = utc_now()
        await DemoEntitlement.get_pymongo_collection().update_one(
            {"patient_id": PydanticObjectId(patient_id)},
            {
                "$set": {
                    "active": active,
                    "granted_by_user_id": PydanticObjectId(admin_user_id),
                    "granted_at": now,
                    "revoked_at": None if active else now,
                },
                "$setOnInsert": {"patient_id": PydanticObjectId(patient_id)},
            },
            upsert=True,
        )
        return await DemoServiceRepository.get_entitlement(patient_id)

    @staticmethod
    async def create_request(request: HomeVisitRequest) -> HomeVisitRequest:
        return await request.insert()

    @staticmethod
    async def get_request(request_id: str) -> HomeVisitRequest | None:
        try:
            return await HomeVisitRequest.get(PydanticObjectId(request_id))
        except (ValueError, TypeError):
            return None

    @staticmethod
    async def list_by_patient(patient_id: str) -> list[HomeVisitRequest]:
        return await HomeVisitRequest.find(
            HomeVisitRequest.patient_id == PydanticObjectId(patient_id)
        ).sort(-HomeVisitRequest.created_at).to_list()

    @staticmethod
    async def list_all() -> list[HomeVisitRequest]:
        return await HomeVisitRequest.find().sort(-HomeVisitRequest.created_at).to_list()

    @staticmethod
    async def list_reception_coordination() -> list[HomeVisitRequest]:
        return await HomeVisitRequest.find(
            HomeVisitRequest.status == "approved_for_coordination"
        ).sort(-HomeVisitRequest.created_at).to_list()

    @staticmethod
    async def list_doctor_coordination(doctor_id: str) -> list[HomeVisitRequest]:
        return await HomeVisitRequest.find({
            "preferred_doctor_id": PydanticObjectId(doctor_id),
            "status": "approved_for_coordination",
        }).sort(-HomeVisitRequest.created_at).to_list()

    @staticmethod
    async def transition_request(
        request_id: str,
        allowed_from: list[str],
        target_status: str,
        actor_user_id: str | None = None,
    ) -> bool:
        now = utc_now()
        updates = {
            "status": target_status,
            "updated_at": now,
        }
        if actor_user_id:
            updates["reviewed_by_user_id"] = PydanticObjectId(actor_user_id)
            updates["reviewed_at"] = now
        result = await HomeVisitRequest.get_pymongo_collection().update_one(
            {
                "_id": PydanticObjectId(request_id),
                "status": {"$in": allowed_from},
            },
            {"$set": updates},
        )
        return result.modified_count == 1
