from typing import List, Optional
from beanie import PydanticObjectId
from app.models.report import Report


class ReportRepository:
    @staticmethod
    async def create(report: Report) -> Report:
        return await report.insert()

    @staticmethod
    async def get_by_id(id: str) -> Optional[Report]:
        try:
            return await Report.get(PydanticObjectId(id))
        except Exception:
            return None

    @staticmethod
    async def get_by_patient_id(patient_id: str) -> List[Report]:
        return await Report.find(
            Report.patient_id == PydanticObjectId(patient_id)
        ).sort(-Report.date).to_list()
