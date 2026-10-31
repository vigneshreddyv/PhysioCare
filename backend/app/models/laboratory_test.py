from datetime import datetime
from beanie import Document, PydanticObjectId, Indexed
from pydantic import Field


class LaboratoryTest(Document):
    test_id: Indexed(str, unique=True)
    name: str
    category: str
    sample: str
    price: float
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "laboratory_tests"