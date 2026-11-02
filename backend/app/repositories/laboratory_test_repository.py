from types import SimpleNamespace
from typing import List, Optional
from beanie import PydanticObjectId

from app.models.laboratory_test import LaboratoryTest


LEGACY_LABORATORY_CATALOG_MAX = 100


class LaboratoryTestRepository:
    @staticmethod
    async def get_active_tests() -> List[SimpleNamespace]:
        """Return the bounded compatibility catalogue used by the legacy API."""
        rows = await LaboratoryTest.get_pymongo_collection().find(
            {"active": True},
            {
                "_id": 0,
                "test_id": 1,
                "name": 1,
                "category": 1,
                "sample": 1,
                "price": 1,
            },
        ).sort([
            ("category", 1),
            ("name", 1),
            ("test_id", 1),
            ("_id", 1),
        ]).limit(LEGACY_LABORATORY_CATALOG_MAX).to_list(
            length=LEGACY_LABORATORY_CATALOG_MAX,
        )
        return [SimpleNamespace(**row) for row in rows]

    @staticmethod
    async def get_by_test_id(test_id: str) -> Optional[LaboratoryTest]:
        return await LaboratoryTest.find_one(LaboratoryTest.test_id == test_id)

    @staticmethod
    async def get_by_test_ids(test_ids: List[str]) -> List[LaboratoryTest]:
        return await LaboratoryTest.find(
            {"test_id": {"$in": test_ids}, "active": True}
        ).to_list()
