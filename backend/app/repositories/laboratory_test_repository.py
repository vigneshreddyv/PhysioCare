from typing import List, Optional
from beanie import PydanticObjectId

from app.models.laboratory_test import LaboratoryTest


class LaboratoryTestRepository:
    @staticmethod
    async def get_active_tests() -> List[LaboratoryTest]:
        return await LaboratoryTest.find(LaboratoryTest.active == True).to_list()

    @staticmethod
    async def get_by_test_id(test_id: str) -> Optional[LaboratoryTest]:
        return await LaboratoryTest.find_one(LaboratoryTest.test_id == test_id)

    @staticmethod
    async def get_by_test_ids(test_ids: List[str]) -> List[LaboratoryTest]:
        return await LaboratoryTest.find(
            {"test_id": {"$in": test_ids}, "active": True}
        ).to_list()