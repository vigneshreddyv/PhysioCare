from typing import List, Optional
from beanie import PydanticObjectId
from app.models.care_plan import CarePlan, CarePlanHistory


class CarePlanRepository:
    @staticmethod
    async def create(care_plan: CarePlan) -> CarePlan:
        return await care_plan.insert()

    @staticmethod
    async def get_by_id(id: str) -> Optional[CarePlan]:
        try:
            return await CarePlan.get(PydanticObjectId(id))
        except Exception:
            return None

    @staticmethod
    async def get_by_patient_id(patient_id: str) -> List[CarePlan]:
        return await CarePlan.find(
            CarePlan.patient_id == PydanticObjectId(patient_id)
        ).sort(-CarePlan.created_at).to_list()

    @staticmethod
    async def get_history_by_care_plan_id(care_plan_id: str) -> List[CarePlanHistory]:
        # Parse safely in case of mocks in tests
        try:
            parsed_id = PydanticObjectId(str(care_plan_id))
        except Exception:
            parsed_id = PydanticObjectId("000000000000000000000000")
        return await CarePlanHistory.find(
            CarePlanHistory.care_plan_id == parsed_id
        ).sort(-CarePlanHistory.created_at).to_list()

