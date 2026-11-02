"""Offline registration transaction contracts; no MongoDB connection is made."""

from types import SimpleNamespace

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import StaffCreate, UserRegister
from app.services import auth_service
from app.services.auth_service import AuthService


USER_ID = PydanticObjectId("507f1f77bcf86cd799439099")


class RegistrationSessionDouble:
    def __init__(self, committed, *, transaction_error=None):
        self.committed = committed
        self.transaction_error = transaction_error
        self.staged = []
        self.transaction_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def with_transaction(self, callback):
        self.transaction_calls += 1
        if self.transaction_error:
            raise self.transaction_error
        try:
            result = await callback(self)
        except Exception:
            self.staged.clear()
            raise
        self.committed.extend(self.staged)
        self.staged.clear()
        return result


def install_transaction(monkeypatch, *, profile_failure=False, transaction_error=None):
    committed = []
    sessions = []
    observed = []
    fail_profile = [profile_failure]

    def start_session():
        session = RegistrationSessionDouble(committed, transaction_error=transaction_error)
        sessions.append(session)
        return session

    collection = SimpleNamespace(database=SimpleNamespace(client=SimpleNamespace(start_session=start_session)))
    for model in (User, Patient, Doctor):
        monkeypatch.setattr(model, "get_pymongo_collection", lambda *_: collection)
    monkeypatch.setattr(auth_service, "get_password_hash", lambda password: f"hashed:{password}")

    async def get_by_email(email):
        return next((record for kind, record in committed if kind == "user" and record.email == email), None)

    async def find_user(query, *, session):
        assert session in sessions
        observed.append(("read", session))
        return next(
            (record for kind, record in committed if kind == "user" and record.email == query["email"]),
            None,
        )

    async def insert_user(self, *, session):
        assert session in sessions
        observed.append(("user", session))
        self.id = USER_ID
        session.staged.append(("user", self))
        return self

    async def insert_patient(self, *, session):
        assert session in sessions
        observed.append(("patient", session))
        if fail_profile[0]:
            raise RuntimeError("synthetic profile write failure")
        session.staged.append(("patient", self))
        return self

    async def insert_doctor(self, *, session):
        assert session in sessions
        observed.append(("doctor", session))
        if fail_profile[0]:
            raise RuntimeError("synthetic profile write failure")
        session.staged.append(("doctor", self))
        return self

    monkeypatch.setattr(UserRepository, "get_by_email", get_by_email)
    monkeypatch.setattr(User, "find_one", find_user)
    monkeypatch.setattr(User, "insert", insert_user)
    monkeypatch.setattr(Patient, "insert", insert_patient)
    monkeypatch.setattr(Doctor, "insert", insert_doctor)
    return committed, sessions, observed, fail_profile


def patient_schema():
    return UserRegister(
        email="patient@example.com",
        password="fictional-password",
        full_name="Fictional Patient",
    )


def doctor_schema():
    return StaffCreate(
        email="doctor@example.com",
        password="fictional-password",
        full_name="Fictional Doctor",
        role="doctor",
    )


@pytest.mark.asyncio
async def test_patient_and_profile_commit_in_one_session(monkeypatch):
    committed, sessions, observed, _ = install_transaction(monkeypatch)

    user = await AuthService.register(patient_schema())

    assert [kind for kind, _ in committed] == ["user", "patient"]
    assert [kind for kind, _ in observed] == ["read", "user", "patient"]
    assert observed[0][1] is observed[1][1] is observed[2][1] is sessions[0]
    assert sessions[0].transaction_calls == 1
    assert committed[1][1].user_id == user.id
    assert user.role == "patient"
    assert user.hashed_password == "hashed:fictional-password"


@pytest.mark.asyncio
async def test_doctor_staff_and_profile_commit_in_one_session(monkeypatch):
    committed, sessions, observed, _ = install_transaction(monkeypatch)

    user = await AuthService.register_staff(doctor_schema())

    assert [kind for kind, _ in committed] == ["user", "doctor"]
    assert [kind for kind, _ in observed] == ["read", "user", "doctor"]
    assert observed[0][1] is observed[1][1] is observed[2][1] is sessions[0]
    assert committed[1][1].user_id == user.id
    assert committed[1][1].specialization == "General Physiotherapy"
    assert user.hashed_password == "hashed:fictional-password"


@pytest.mark.asyncio
async def test_profile_failure_rolls_back_user_and_same_registration_can_retry(monkeypatch):
    committed, sessions, _observed, fail_profile = install_transaction(monkeypatch, profile_failure=True)

    with pytest.raises(HTTPException) as error:
        await AuthService.register(patient_schema())
    assert error.value.status_code == 503
    assert error.value.detail == "Account creation is temporarily unavailable"
    assert committed == []
    assert sessions[0].staged == []

    fail_profile[0] = False
    user = await AuthService.register(patient_schema())
    assert user is not None
    assert [kind for kind, _ in committed] == ["user", "patient"]
    assert sessions[1].transaction_calls == 1


@pytest.mark.asyncio
async def test_unsupported_transactions_fail_closed_without_single_write_fallback(monkeypatch):
    committed, sessions, observed, _ = install_transaction(
        monkeypatch,
        transaction_error=OperationFailure("synthetic standalone transaction rejection", code=20),
    )

    with pytest.raises(HTTPException) as error:
        await AuthService.register(patient_schema())
    assert error.value.status_code == 503
    assert committed == []
    assert observed == []
    assert sessions[0].transaction_calls == 1


@pytest.mark.asyncio
async def test_unsupported_transactions_do_not_reveal_whether_public_email_exists(monkeypatch):
    committed, _sessions, observed, _ = install_transaction(
        monkeypatch,
        transaction_error=OperationFailure("synthetic standalone transaction rejection", code=20),
    )
    committed.append(("user", SimpleNamespace(email="patient@example.com")))

    for email in ("patient@example.com", "new.patient@example.com"):
        with pytest.raises(HTTPException) as error:
            await AuthService.register(
                UserRegister(email=email, password="fictional-password", full_name="Fictional Patient")
            )
        assert error.value.status_code == 503
        assert error.value.detail == "Account creation is temporarily unavailable"
    assert len(committed) == 1
    assert observed == []


@pytest.mark.asyncio
async def test_existing_email_is_neutral_publicly_and_rejected_for_staff(monkeypatch):
    committed, _sessions, _observed, _ = install_transaction(monkeypatch)
    await AuthService.register(patient_schema())
    assert await AuthService.register(patient_schema()) is None
    assert len(committed) == 2

    with pytest.raises(HTTPException) as error:
        await AuthService.register_staff(
            StaffCreate(
                email="patient@example.com",
                password="fictional-password",
                full_name="Fictional Doctor",
                role="doctor",
            )
        )
    assert error.value.status_code == 400
    assert error.value.detail == "Email already registered"


@pytest.mark.asyncio
async def test_unique_email_race_does_not_create_profile(monkeypatch):
    committed, sessions, observed, _ = install_transaction(monkeypatch)

    async def duplicate_user_insert(self, *, session):
        observed.append(("user", session))
        raise DuplicateKeyError("synthetic unique email collision")

    monkeypatch.setattr(User, "insert", duplicate_user_insert)

    assert await AuthService.register(patient_schema()) is None
    assert committed == []
    assert [kind for kind, _ in observed] == ["read", "user"]
    assert sessions[0].staged == []
