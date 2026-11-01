"""Opt-in report transaction contract for an approved empty replica-set database.

The test is skipped unless mode, database, URI, identity and acknowledgment
match one of the tightly scoped targets below. It removes only its own fictional
documents and never drops a collection or database.
"""

import asyncio
import os
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from beanie import PydanticObjectId, init_beanie
from pymongo import AsyncMongoClient

from app.models.laboratory_booking import LaboratoryBooking
from app.models.report import Report
from app.repositories.report_repository import BookingClaimFailed, ReportRepository


TEST_MODE = os.environ.get("PHYSIOCARE_PHASE15_TXN_TEST_MODE", "")
TEST_URL = os.environ.get("PHYSIOCARE_PHASE15_TXN_TEST_URL", "")
TEST_DATABASE = os.environ.get("PHYSIOCARE_PHASE15_TXN_TEST_DATABASE", "")
TEST_ACK = os.environ.get("PHYSIOCARE_PHASE15_TXN_TEST_ACK", "")
APPROVED_HOST = os.environ.get("PHYSIOCARE_PHASE15_TXN_TEST_APPROVED_HOST", "")
APPROVED_REPLICA_SET = os.environ.get("PHYSIOCARE_PHASE15_TXN_TEST_APPROVED_REPLICA_SET", "")


def explicitly_enabled() -> bool:
    try:
        parsed = urlsplit(TEST_URL)
        port = parsed.port
    except ValueError:
        return False
    single_direct_target = (
        parsed.scheme == "mongodb"
        and port is not None
        and "," not in parsed.netloc
        and parsed.path == f"/{TEST_DATABASE}"
        and parsed.fragment == ""
    )
    if not single_direct_target:
        return False
    if TEST_MODE == "loopback":
        return (
            TEST_DATABASE == "physiocare_phase15_txn_contract"
            and TEST_ACK == "empty-loopback-replica-set-only"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and parsed.username is None
            and parsed.password is None
        )
    if TEST_MODE == "staging":
        options = {
            key.casefold(): values[-1].casefold()
            for key, values in parse_qs(parsed.query).items()
        }
        return (
            TEST_DATABASE == "physiocare_staging"
            and TEST_ACK == "approved-empty-isolated-staging-only"
            and bool(APPROVED_HOST)
            and APPROVED_HOST not in {"127.0.0.1", "localhost", "::1"}
            and parsed.hostname == APPROVED_HOST
            and bool(APPROVED_REPLICA_SET)
            and options.get("tls", options.get("ssl")) == "true"
            and options.get("tlsinsecure") != "true"
            and options.get("tlsallowinvalidcertificates") != "true"
            and options.get("tlsallowinvalidhostnames") != "true"
        )
    return False


pytestmark = pytest.mark.skipif(
    not explicitly_enabled(),
    reason="an empty loopback or staging replica set was not explicitly approved",
)


@pytest.fixture(autouse=True)
def mock_beanie_document_init():
    """Keep real Beanie settings and initialization for this connected test."""


def fictional_report(patient_id, booking_id):
    return Report(
        patient_id=patient_id,
        booking_id=booking_id,
        title="Fictional diagnostic result",
        category="diagnostic",
        date=datetime.now(timezone.utc),
        description="Synthetic transaction contract",
        therapist="Test clinician",
        content={},
    )


async def confirmed_booking(collection, patient_id, booking_id):
    await collection.insert_one(
        {
            "_id": booking_id,
            "patient_id": patient_id,
            "status": "confirmed",
        }
    )


@pytest.mark.asyncio
async def test_report_booking_commit_rollback_ownership_and_concurrency(monkeypatch):
    client = AsyncMongoClient(TEST_URL, serverSelectionTimeoutMS=2000)
    database = client[TEST_DATABASE]
    booking_collection = database["laboratory_bookings"]
    report_collection = database["reports"]
    patient_id = PydanticObjectId()
    other_patient_id = PydanticObjectId()
    booking_ids = [PydanticObjectId() for _ in range(4)]
    cleanup_allowed = False

    try:
        hello = await database.command("hello")
        assert hello.get("setName"), "the approved test Mongo must be a replica set"
        if TEST_MODE == "staging":
            assert hello["setName"] == APPROVED_REPLICA_SET, "replica-set identity mismatch"
        existing = set(await database.list_collection_names())
        for name in existing:
            assert await database[name].count_documents({}) == 0, "test database contains records"

        cleanup_allowed = True
        await init_beanie(database=database, document_models=[LaboratoryBooking, Report])
        for booking_id in booking_ids:
            await confirmed_booking(booking_collection, patient_id, booking_id)

        # The patient filter must prevent a foreign report from changing a booking.
        with pytest.raises(BookingClaimFailed):
            await ReportRepository.create_for_confirmed_booking(
                fictional_report(other_patient_id, booking_ids[0])
            )
        assert (await booking_collection.find_one({"_id": booking_ids[0]}))["status"] == "confirmed"
        assert await report_collection.count_documents({"booking_id": booking_ids[0]}) == 0

        original_insert = Report.insert

        async def fail_before_insert(self, **_):
            raise RuntimeError("synthetic pre-insert failure")

        with monkeypatch.context() as patcher:
            patcher.setattr(Report, "insert", fail_before_insert)
            with pytest.raises(RuntimeError, match="pre-insert"):
                await ReportRepository.create_for_confirmed_booking(
                    fictional_report(patient_id, booking_ids[1])
                )
        assert (await booking_collection.find_one({"_id": booking_ids[1]}))["status"] == "confirmed"
        assert await report_collection.count_documents({"booking_id": booking_ids[1]}) == 0

        async def fail_after_insert(self, **kwargs):
            await original_insert(self, **kwargs)
            raise RuntimeError("synthetic pre-commit failure")

        with monkeypatch.context() as patcher:
            patcher.setattr(Report, "insert", fail_after_insert)
            with pytest.raises(RuntimeError, match="pre-commit"):
                await ReportRepository.create_for_confirmed_booking(
                    fictional_report(patient_id, booking_ids[2])
                )
        assert (await booking_collection.find_one({"_id": booking_ids[2]}))["status"] == "confirmed"
        assert await report_collection.count_documents({"booking_id": booking_ids[2]}) == 0

        outcomes = await asyncio.gather(
            *(
                ReportRepository.create_for_confirmed_booking(
                    fictional_report(patient_id, booking_ids[3])
                )
                for _ in range(2)
            ),
            return_exceptions=True,
        )
        assert sum(isinstance(outcome, Report) for outcome in outcomes) == 1
        assert sum(isinstance(outcome, BookingClaimFailed) for outcome in outcomes) == 1
        assert (await booking_collection.find_one({"_id": booking_ids[3]}))["status"] == "completed"
        assert await report_collection.count_documents({"booking_id": booking_ids[3]}) == 1
    finally:
        try:
            if cleanup_allowed:
                try:
                    await report_collection.delete_many({"booking_id": {"$in": booking_ids}})
                finally:
                    await booking_collection.delete_many({"_id": {"$in": booking_ids}})
                assert await report_collection.count_documents({"booking_id": {"$in": booking_ids}}) == 0
                assert await booking_collection.count_documents({"_id": {"$in": booking_ids}}) == 0
        finally:
            await client.close()
