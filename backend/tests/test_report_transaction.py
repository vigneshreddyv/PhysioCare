"""Local transaction-boundary checks; connected Mongo commit/rollback is a separate gate."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pymongo.errors import OperationFailure

from app.models.report import Report
from app.models.laboratory_booking import LaboratoryBooking
from app.repositories.laboratory_booking_repository import LaboratoryBookingRepository
from app.repositories.report_repository import BookingClaimFailed, ReportRepository


PATIENT_ID = "000000000000000000000000"
BOOKING_ID = "111111111111111111111111"


class SessionDouble:
    def __init__(self, *, transaction_error=None):
        self.transaction_error = transaction_error
        self.transaction_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def with_transaction(self, callback):
        self.transaction_calls += 1
        if self.transaction_error:
            raise self.transaction_error
        return await callback(self)


def report():
    return Report(
        patient_id=PATIENT_ID,
        booking_id=BOOKING_ID,
        title="Fictional diagnostic report",
        category="diagnostic",
        date="2026-11-01T12:00:00Z",
        description="Synthetic fixture",
        therapist="Test clinician",
        content={},
    )


def install_session(monkeypatch, session):
    client = SimpleNamespace(start_session=lambda: session)
    collection = SimpleNamespace(database=SimpleNamespace(client=client))
    monkeypatch.setattr(Report, "get_pymongo_collection", lambda *_: collection)


@pytest.mark.asyncio
async def test_booking_claim_and_report_insert_share_one_transaction(monkeypatch):
    session = SessionDouble()
    install_session(monkeypatch, session)
    claim = AsyncMock(return_value=True)
    insert = AsyncMock(return_value="created")
    monkeypatch.setattr(LaboratoryBookingRepository, "complete_confirmed_for_report", claim)
    monkeypatch.setattr(Report, "insert", insert)

    assert await ReportRepository.create_for_confirmed_booking(report()) == "created"
    assert session.transaction_calls == 1
    claim.assert_awaited_once_with(BOOKING_ID, PATIENT_ID, session=session)
    assert insert.await_args.kwargs == {"session": session}


@pytest.mark.asyncio
async def test_lost_booking_claim_prevents_report_insert(monkeypatch):
    session = SessionDouble()
    install_session(monkeypatch, session)
    monkeypatch.setattr(
        LaboratoryBookingRepository,
        "complete_confirmed_for_report",
        AsyncMock(return_value=False),
    )
    insert = AsyncMock()
    monkeypatch.setattr(Report, "insert", insert)

    with pytest.raises(BookingClaimFailed):
        await ReportRepository.create_for_confirmed_booking(report())
    insert.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsupported_transactions_fail_closed_before_writes(monkeypatch):
    session = SessionDouble(transaction_error=OperationFailure("transactions unavailable"))
    install_session(monkeypatch, session)
    claim = AsyncMock()
    insert = AsyncMock()
    monkeypatch.setattr(LaboratoryBookingRepository, "complete_confirmed_for_report", claim)
    monkeypatch.setattr(Report, "insert", insert)

    with pytest.raises(OperationFailure):
        await ReportRepository.create_for_confirmed_booking(report())
    claim.assert_not_awaited()
    insert.assert_not_awaited()


@pytest.mark.asyncio
async def test_booking_compare_and_set_uses_the_transaction_session(monkeypatch):
    session = object()
    update = AsyncMock(return_value={"status": "completed"})
    collection = SimpleNamespace(find_one_and_update=update)
    monkeypatch.setattr(
        LaboratoryBooking,
        "get_pymongo_collection",
        lambda: collection,
    )

    assert await LaboratoryBookingRepository.complete_confirmed_for_report(
        BOOKING_ID, PATIENT_ID, session=session
    )
    query, change = update.await_args.args
    assert str(query["_id"]) == BOOKING_ID
    assert str(query["patient_id"]) == PATIENT_ID
    assert query["status"] == "confirmed"
    assert change == {"$set": {"status": "completed"}}
    assert update.await_args.kwargs["session"] is session
