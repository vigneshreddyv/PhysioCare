from typing import List, Optional
from beanie import PydanticObjectId
from pymongo import ReturnDocument
from app.models.care_plan import CarePlan, CarePlanHistory
from app.models.notification import Notification
from app.core.pagination import PageWindow


class CarePlanMutationConflict(Exception):
    """The care plan no longer has the revision authorized by the caller."""


class CarePlanRepository:
    @staticmethod
    def _revision_filter(expected_revision: int) -> dict:
        if expected_revision == 0:
            return {"$or": [{"revision": 0}, {"revision": {"$exists": False}}]}
        return {"revision": expected_revision}

    @staticmethod
    async def create_with_history(
        care_plan: CarePlan,
        *,
        actor_user_id: str,
    ) -> CarePlan:
        """Create a plan and its mandatory initial history in one transaction."""
        values = care_plan.model_dump(exclude={"id"})
        client = CarePlan.get_pymongo_collection().database.client
        async with client.start_session() as session:
            async def create_in_transaction(active_session):
                attempt = CarePlan(**values)
                saved = await attempt.insert(session=active_session)
                await CarePlanHistory(
                    care_plan_id=saved.id,
                    patient_id=saved.patient_id,
                    actor_user_id=PydanticObjectId(actor_user_id),
                    action="plan_created",
                    new_value=saved.status,
                ).insert(session=active_session)
                return saved

            return await session.with_transaction(create_in_transaction)

    @staticmethod
    async def update_if_revision(
        care_plan_id: str,
        *,
        expected_revision: int,
        patient_id,
        therapist_id,
        set_fields: dict,
    ) -> CarePlan:
        query = {
            "_id": PydanticObjectId(care_plan_id),
            "patient_id": patient_id,
            "therapist_id": therapist_id,
            **CarePlanRepository._revision_filter(expected_revision),
        }
        row = await CarePlan.get_pymongo_collection().find_one_and_update(
            query,
            {"$set": set_fields, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if row is None:
            raise CarePlanMutationConflict
        return CarePlan.model_validate(row)

    @staticmethod
    async def update_with_side_effects(
        care_plan_id: str,
        *,
        expected_revision: int,
        patient_id,
        therapist_id,
        set_fields: dict,
        history_data: dict,
        notification_data: dict | None = None,
    ) -> CarePlan:
        """Commit primary state, audit history and optional notification together."""
        client = CarePlan.get_pymongo_collection().database.client
        async with client.start_session() as session:
            async def update_in_transaction(active_session):
                query = {
                    "_id": PydanticObjectId(care_plan_id),
                    "patient_id": patient_id,
                    "therapist_id": therapist_id,
                    **CarePlanRepository._revision_filter(expected_revision),
                }
                row = await CarePlan.get_pymongo_collection().find_one_and_update(
                    query,
                    {"$set": set_fields, "$inc": {"revision": 1}},
                    return_document=ReturnDocument.AFTER,
                    session=active_session,
                )
                if row is None:
                    raise CarePlanMutationConflict
                await CarePlanHistory(
                    care_plan_id=PydanticObjectId(care_plan_id),
                    patient_id=patient_id,
                    **history_data,
                ).insert(session=active_session)
                if notification_data is not None:
                    await Notification(**notification_data).insert(session=active_session)
                return CarePlan.model_validate(row)

            return await session.with_transaction(update_in_transaction)

    @staticmethod
    async def get_active_or_latest_by_patient_id(patient_id: str) -> Optional[CarePlan]:
        patient_object_id = PydanticObjectId(patient_id)
        active = await CarePlan.find({
            "patient_id": patient_object_id, "status": "active",
        }).sort("-created_at", "-_id").limit(1).to_list()
        if active:
            return active[0]
        latest = await CarePlan.find({
            "patient_id": patient_object_id,
        }).sort("-created_at", "-_id").limit(1).to_list()
        return latest[0] if latest else None

    @staticmethod
    async def get_active_stage_titles(patient_id: str) -> dict[str, str]:
        plan = await CarePlan.get_pymongo_collection().find_one(
            {"patient_id": PydanticObjectId(patient_id), "status": "active"},
            projection={"stages.stage_id": 1, "stages.title": 1},
            sort=[("created_at", -1), ("_id", -1)],
        )
        return {stage["stage_id"]: stage["title"] for stage in plan.get("stages", [])} if plan else {}

    @staticmethod
    async def create(care_plan: CarePlan) -> CarePlan:
        return await care_plan.insert()

    @staticmethod
    async def get_by_id(id: str) -> Optional[CarePlan]:
        if not PydanticObjectId.is_valid(id):
            return None
        return await CarePlan.get(PydanticObjectId(id))

    @staticmethod
    async def get_by_patient_id(patient_id: str) -> List[CarePlan]:
        return await CarePlan.find(
            CarePlan.patient_id == PydanticObjectId(patient_id)
        ).sort(-CarePlan.created_at).to_list()

    @staticmethod
    async def get_history_by_care_plan_id(care_plan_id: str) -> List[CarePlanHistory]:
        if not PydanticObjectId.is_valid(care_plan_id):
            return []
        return await CarePlanHistory.find(
            CarePlanHistory.care_plan_id == PydanticObjectId(care_plan_id)
        ).sort(-CarePlanHistory.created_at).to_list()

    @staticmethod
    async def get_page_by_patient_id(patient_id: str, page: PageWindow) -> List[CarePlan]:
        return await CarePlan.find({
            "patient_id": PydanticObjectId(patient_id),
        }).sort("-created_at", "-_id").skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def get_page_history_by_care_plan_id(
        care_plan_id: str, page: PageWindow,
    ) -> List[CarePlanHistory]:
        if not PydanticObjectId.is_valid(care_plan_id):
            return []
        return await CarePlanHistory.find({
            "care_plan_id": PydanticObjectId(care_plan_id),
        }).sort("-created_at", "-_id").skip(page.offset).limit(page.size).to_list()

