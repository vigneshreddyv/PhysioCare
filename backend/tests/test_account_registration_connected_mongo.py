"""Opt-in registration transaction contract for one empty local replica-set DB.

This file must not run without separate approval for the exact URI below.
It creates a User email index and fictional records in that database only.
Finally cleanup deletes its records, but intentionally does not drop collections
or indexes; an independent post-run emptiness check is still required.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from beanie import init_beanie
from fastapi import HTTPException
from pymongo import AsyncMongoClient

from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.auth import StaffCreate, UserRegister
from app.services.auth_service import AuthService


TEST_DATABASE = "physiocare_phase19_registration_contract"
TEST_URL = (
    "mongodb://127.0.0.1:27020/physiocare_phase19_registration_contract"
    "?replicaSet=physiocareDevRs&directConnection=true"
)
EXPECTED_DATA_PATH = (
    Path.home() / "Library/Application Support/PhysioCare/dev-mongo-27020/data"
)
EXPECTED_LOG_PATH = (
    Path.home() / "Library/Application Support/PhysioCare/dev-mongo-27020/log/mongod.log"
)


def explicitly_enabled() -> bool:
    return (
        os.environ.get("PHYSIOCARE_PHASE19_REG_TEST_MODE") == "loopback"
        and os.environ.get("PHYSIOCARE_PHASE19_REG_TEST_URL") == TEST_URL
        and os.environ.get("PHYSIOCARE_PHASE19_REG_TEST_DATABASE") == TEST_DATABASE
        and os.environ.get("PHYSIOCARE_PHASE19_REG_TEST_ACK")
        == "approved-empty-registration-contract-only"
        and os.environ.get("MONGODB_URL") == TEST_URL
        and os.environ.get("DATABASE_NAME") == TEST_DATABASE
    )


pytestmark = pytest.mark.skipif(
    not explicitly_enabled(),
    reason="the exact empty local registration contract database was not approved",
)


@pytest.fixture(autouse=True)
def mock_beanie_document_init():
    """Override the global mock so this module uses real Beanie initialization."""


async def assert_empty(collections):
    for collection in collections:
        assert await collection.count_documents({}) == 0


@pytest.mark.asyncio
async def test_patient_and_doctor_registration_commit_rollback_and_retry(monkeypatch):
    client = AsyncMongoClient(TEST_URL, serverSelectionTimeoutMS=2000)
    database = client[TEST_DATABASE]
    users = database["users"]
    patients = database["patients"]
    doctors = database["doctors"]
    collections = (users, patients, doctors)
    cleanup_allowed = False
    attempted_user_ids = set()
    suffix = uuid4().hex
    patient_email = f"phase19-patient-{suffix}@example.com"
    doctor_email = f"phase19-doctor-{suffix}@example.com"
    test_emails = [patient_email, doctor_email]

    try:
        build_info = await client.admin.command("buildInfo")
        assert build_info["version"] == "8.3.7"
        hello = await client.admin.command("hello")
        assert hello["setName"] == "physiocareDevRs"
        assert hello["isWritablePrimary"] is True
        replica_config = (await client.admin.command("replSetGetConfig"))["config"]
        assert replica_config["_id"] == "physiocareDevRs"
        assert [member["host"] for member in replica_config["members"]] == ["localhost:27020"]
        cmdline = (await client.admin.command("getCmdLineOpts"))["parsed"]
        assert cmdline["net"]["port"] == 27020
        assert set(cmdline["net"]["bindIp"].split(",")) == {"127.0.0.1", "::1"}
        assert Path(cmdline["storage"]["dbPath"]).resolve() == EXPECTED_DATA_PATH.resolve()
        assert Path(cmdline["systemLog"]["path"]).resolve() == EXPECTED_LOG_PATH.resolve()

        existing = set(await database.list_collection_names())
        assert existing <= {"users", "patients", "doctors"}
        for name in existing:
            assert await database[name].count_documents({}) == 0

        cleanup_allowed = True
        await init_beanie(database=database, document_models=[User, Patient, Doctor])

        patient_schema = UserRegister(
            email=patient_email,
            password="fictional-registration-password",
            full_name="Fictional Patient",
        )
        doctor_schema = StaffCreate(
            email=doctor_email,
            password="fictional-registration-password",
            full_name="Fictional Clinician",
            role="doctor",
        )

        original_patient_insert = Patient.insert

        async def fail_after_patient_insert(self, **kwargs):
            attempted_user_ids.add(self.user_id)
            await original_patient_insert(self, **kwargs)
            raise RuntimeError("synthetic patient profile failure")

        with monkeypatch.context() as patcher:
            patcher.setattr(Patient, "insert", fail_after_patient_insert)
            with pytest.raises(HTTPException) as failure:
                await AuthService.register(patient_schema)
        assert failure.value.status_code == 503
        await assert_empty(collections)

        patient_user = await AuthService.register(patient_schema)
        assert patient_user is not None
        attempted_user_ids.add(patient_user.id)
        assert patient_user.hashed_password != patient_schema.password
        assert await users.count_documents({"email": patient_email}) == 1
        assert await patients.count_documents({"user_id": patient_user.id}) == 1
        assert await AuthService.register(patient_schema) is None
        assert await users.count_documents({"email": patient_email}) == 1

        original_doctor_insert = Doctor.insert

        async def fail_after_doctor_insert(self, **kwargs):
            attempted_user_ids.add(self.user_id)
            await original_doctor_insert(self, **kwargs)
            raise RuntimeError("synthetic doctor profile failure")

        with monkeypatch.context() as patcher:
            patcher.setattr(Doctor, "insert", fail_after_doctor_insert)
            with pytest.raises(HTTPException) as failure:
                await AuthService.register_staff(doctor_schema)
        assert failure.value.status_code == 503
        assert await users.count_documents({"email": doctor_email}) == 0
        assert await users.count_documents({}) == 1
        assert await patients.count_documents({}) == 1
        assert await doctors.count_documents({"user_id": {"$in": list(attempted_user_ids)}}) == 0

        doctor_user = await AuthService.register_staff(doctor_schema)
        attempted_user_ids.add(doctor_user.id)
        assert doctor_user.hashed_password != doctor_schema.password
        assert await users.count_documents({"email": doctor_email}) == 1
        assert await doctors.count_documents({"user_id": doctor_user.id}) == 1
        with pytest.raises(HTTPException) as duplicate:
            await AuthService.register_staff(doctor_schema)
        assert duplicate.value.status_code == 400
        assert await users.count_documents({"email": doctor_email}) == 1
    finally:
        try:
            if cleanup_allowed:
                try:
                    await patients.delete_many({"user_id": {"$in": list(attempted_user_ids)}})
                finally:
                    try:
                        await doctors.delete_many({"user_id": {"$in": list(attempted_user_ids)}})
                    finally:
                        await users.delete_many({"email": {"$in": test_emails}})
                await assert_empty(collections)
        finally:
            await client.close()
