import re
from typing import List, Optional
from beanie import PydanticObjectId
from app.models.report import Report
from app.repositories.laboratory_booking_repository import LaboratoryBookingRepository
from app.core.pagination import PageWindow


class BookingClaimFailed(Exception):
    """The booking was no longer confirmed when the transaction ran."""


class ReportRepository:
    @staticmethod
    async def create(report: Report) -> Report:
        return await report.insert()

    @staticmethod
    async def create_for_confirmed_booking(report: Report) -> Report:
        """Commit the booking transition and report insert as one Mongo transaction.

        A standalone Mongo deployment without transaction support fails closed.
        No notification or filesystem operation runs inside the retryable callback.
        """
        if report.booking_id is None:
            raise ValueError("A diagnostic booking is required")

        client = Report.get_pymongo_collection().database.client
        async with client.start_session() as session:
            async def create_in_transaction(active_session):
                claimed = await LaboratoryBookingRepository.complete_confirmed_for_report(
                    str(report.booking_id),
                    str(report.patient_id),
                    session=active_session,
                )
                if not claimed:
                    raise BookingClaimFailed
                return await report.insert(session=active_session)

            return await session.with_transaction(create_in_transaction)

    @staticmethod
    async def get_by_id(id: str) -> Optional[Report]:
        if not PydanticObjectId.is_valid(id):
            return None
        return await Report.get(PydanticObjectId(id))

    @staticmethod
    async def get_by_patient_id(patient_id: str) -> List[Report]:
        return await Report.find(
            Report.patient_id == PydanticObjectId(patient_id)
        ).sort(-Report.date).to_list()

    @staticmethod
    async def get_page_by_patient_id(
        patient_id: str, page: PageWindow, search: str | None = None,
    ) -> List[Report]:
        query = {
            "patient_id": PydanticObjectId(patient_id),
        }
        if search:
            escaped = re.escape(search)
            query["$or"] = [
                {"title": {"$regex": escaped, "$options": "i"}},
                {"category": {"$regex": escaped, "$options": "i"}},
            ]
        return await Report.find(query).sort("-date", "-_id").skip(page.offset).limit(page.size).to_list()
