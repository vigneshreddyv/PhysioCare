from typing import List, Optional
from beanie import PydanticObjectId
from app.models.report import Report
from app.repositories.laboratory_booking_repository import LaboratoryBookingRepository


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
        try:
            return await Report.get(PydanticObjectId(id))
        except Exception:
            return None

    @staticmethod
    async def get_by_patient_id(patient_id: str) -> List[Report]:
        return await Report.find(
            Report.patient_id == PydanticObjectId(patient_id)
        ).sort(-Report.date).to_list()
