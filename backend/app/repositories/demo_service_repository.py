from beanie import PydanticObjectId
from types import SimpleNamespace

from app.core.time import utc_now
from app.models.demo_entitlement import DemoEntitlement
from app.models.home_visit_request import HomeVisitRequest
from app.core.pagination import PageWindow
import re
from app.models.user import User


class DemoServiceRepository:
    _CLINICAL_LIST_PROJECTION = {
        "patient_id": 1,
        "preferred_doctor_id": 1,
        "home_address": 1,
        "reason": 1,
        "city": 1,
        "body_regions": 1,
        "symptoms": 1,
        "duration_days": 1,
        "pain_severity": 1,
        "status": 1,
        "created_at": 1,
        "updated_at": 1,
    }

    @staticmethod
    async def _list_clinical_page(query: dict, page: PageWindow, sort_field: str):
        rows = await HomeVisitRequest.get_pymongo_collection().find(
            query, DemoServiceRepository._CLINICAL_LIST_PROJECTION,
        ).sort([(sort_field, -1), ("_id", -1)]).skip(page.offset).limit(
            page.size,
        ).to_list(length=page.size)
        return [SimpleNamespace(
            id=row["_id"],
            patient_id=row["patient_id"],
            preferred_doctor_id=row["preferred_doctor_id"],
            home_address=row["home_address"],
            reason=row["reason"],
            city=row.get("city"),
            body_regions=row.get("body_regions", []),
            symptoms=row.get("symptoms", []),
            duration_days=row.get("duration_days"),
            pain_severity=row.get("pain_severity"),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ) for row in rows]

    @staticmethod
    async def search_entitlements(page: PageWindow, search: str) -> list[dict]:
        match: dict = {"role": "patient"}
        if search:
            pattern = re.escape(search)
            match["$or"] = [{"full_name": {"$regex": pattern, "$options": "i"}},
                            {"email": {"$regex": pattern, "$options": "i"}}]
        return await User.get_pymongo_collection().aggregate([
            {"$match": match},
            {"$lookup": {"from": "patients", "localField": "_id", "foreignField": "user_id", "as": "patient"}},
            {"$unwind": "$patient"},
            {"$lookup": {"from": "demo_entitlements", "localField": "patient._id",
                         "foreignField": "patient_id", "as": "entitlement"}},
            {"$sort": {"full_name": 1, "_id": 1}},
            {"$skip": page.offset}, {"$limit": page.size},
            {"$project": {"full_name": 1, "email": 1, "patient._id": 1, "patient.phone": 1,
                          "entitlement.active": 1}},
        ]).to_list(length=page.size)
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
    async def list_page_by_patient(
        patient_id: str, page: PageWindow, recent_updates: bool = False,
    ) -> list[HomeVisitRequest]:
        return await DemoServiceRepository._list_clinical_page(
            {"patient_id": PydanticObjectId(patient_id)},
            page,
            "updated_at" if recent_updates else "created_at",
        )

    @staticmethod
    async def list_page_all(page: PageWindow) -> list[HomeVisitRequest]:
        return await DemoServiceRepository._list_clinical_page({}, page, "created_at")

    @staticmethod
    async def list_page_reception_coordination(page: PageWindow) -> list[HomeVisitRequest]:
        rows = await HomeVisitRequest.get_pymongo_collection().find(
            {"status": "approved_for_coordination"},
            {"patient_id": 1, "preferred_doctor_id": 1, "home_address": 1,
             "city": 1, "status": 1, "created_at": 1},
        ).sort([("created_at", -1), ("_id", -1)]).skip(page.offset).limit(page.size).to_list(length=page.size)
        return [SimpleNamespace(
            id=row["_id"], patient_id=row["patient_id"],
            preferred_doctor_id=row["preferred_doctor_id"],
            home_address=row["home_address"], city=row.get("city"),
            status=row["status"], created_at=row["created_at"],
        ) for row in rows]

    @staticmethod
    async def list_page_doctor_coordination(
        doctor_id: str, page: PageWindow,
    ) -> list[HomeVisitRequest]:
        return await DemoServiceRepository._list_clinical_page({
            "preferred_doctor_id": PydanticObjectId(doctor_id),
            "status": "approved_for_coordination",
        }, page, "created_at")

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
