from pydantic import BaseModel
from typing import List


class LaboratoryTestBase(BaseModel):
    test_id: str
    name: str
    category: str
    sample: str
    price: float


class LaboratoryTestResponse(LaboratoryTestBase):
    pass


class LaboratoryTestsResponse(BaseModel):
    tests: List[LaboratoryTestResponse]