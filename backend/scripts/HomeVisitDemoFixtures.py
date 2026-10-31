"""Prepare fictional Home Visit Demo identities and booking prerequisites."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
import uuid
from pathlib import Path

import httpx
from beanie import init_beanie
from pydantic import EmailStr, TypeAdapter

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.time import utc_now


HOME_VISIT_DEMO_TAG = "home_visit_demo_fixture_v1"
ACCOUNT_DEFINITIONS = {
    "patient": {
        "email": "homevisit.patient@physiocare-demo.internal",
        "full_name": "Fictional Home Visit Patient",
        "role": "patient",
    },
    "doctor": {
        "email": "homevisit.doctor@physiocare-demo.internal",
        "full_name": "Fictional Home Visit Clinician",
        "role": "doctor",
    },
    "admin": {
        "email": "homevisit.admin@physiocare-demo.internal",
        "full_name": "Fictional Home Visit Administrator",
        "role": "admin",
    },
}
PATIENT_ADDRESS = "12 Demo Lane, Nellore, Andhra Pradesh 524001"
API_ORIGIN = "http://127.0.0.1:8002"


def demo_home() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "PhysioCareHomeVisitDemo"


def environment_file() -> Path:
    return demo_home() / ".env"


def credentials_file() -> Path:
    return demo_home() / "credentials.json"


def _ensure_dedicated_environment() -> None:
    env_file = environment_file()
    if not env_file.is_file() or env_file.is_symlink():
        raise RuntimeError("The dedicated Home Visit Demo environment file is unavailable")
    os.environ["PHYSIOCARE_HOME_VISIT_ENV_FILE"] = str(env_file)
    os.environ["PHYSIOCARE_ENV_FILE"] = ""


def _write_credentials(credentials: dict[str, dict[str, str]]) -> None:
    path = credentials_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(credentials, indent=2, sort_keys=True).encode("utf-8")
    temporary = path.with_name(f".credentials.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as target:
            target.write(encoded)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_or_create_credentials() -> dict[str, dict[str, str]]:
    path = credentials_file()
    if path.is_symlink():
        raise RuntimeError("The Home Visit Demo credential file cannot be a symbolic link")
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for role, definition in ACCOUNT_DEFINITIONS.items():
            item = data.get(role)
            if (
                not isinstance(item, dict)
                or item.get("email") != definition["email"]
                or not isinstance(item.get("password"), str)
                or len(item["password"]) < 32
            ):
                raise RuntimeError("The protected Home Visit Demo credential file is invalid")
        return data

    data = {
        role: {
            "email": definition["email"],
            "password": secrets.token_urlsafe(32),
        }
        for role, definition in ACCOUNT_DEFINITIONS.items()
    }
    _write_credentials(data)
    return data


async def _init_database():
    from app.core.config import (
        HOME_VISIT_DEMO_DATABASE_NAME,
        HOME_VISIT_DEMO_MONGODB_URL,
        settings,
    )
    from app.database import BeanieCompatibleMotorClient
    from app.models.auth_session import AuthSession
    from app.models.clinician_schedule import ClinicianSchedule
    from app.models.demo_entitlement import DemoEntitlement
    from app.models.doctor import Doctor
    from app.models.patient import Patient
    from app.models.user import User

    settings.validate_home_visit_demo_isolation()
    if (
        not settings.HOME_VISIT_DEMO_MODE
        or settings.MONGODB_URL != HOME_VISIT_DEMO_MONGODB_URL
        or settings.DATABASE_NAME != HOME_VISIT_DEMO_DATABASE_NAME
        or settings.HOST != "127.0.0.1"
        or settings.PORT != 8002
    ):
        raise RuntimeError("Refusing to prepare fixtures outside the dedicated Home Visit Demo configuration")

    client = BeanieCompatibleMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    await client.admin.command("ping")
    await init_beanie(
        database=client[settings.DATABASE_NAME],
        document_models=[
            User,
            Patient,
            Doctor,
            DemoEntitlement,
            ClinicianSchedule,
            AuthSession,
        ],
    )
    return client


async def _ensure_user(role: str, password: str):
    from app.core.security import get_password_hash
    from app.models.user import User

    definition = ACCOUNT_DEFINITIONS[role]
    email = TypeAdapter(EmailStr).validate_python(definition["email"])
    user = await User.find_one(User.email == email)
    if user:
        if (
            user.role != definition["role"]
            or user.full_name != definition["full_name"]
            or user.demo_rehearsal_tag != HOME_VISIT_DEMO_TAG
        ):
            raise RuntimeError(f"Existing {role} identity does not match the Home Visit Demo fixture")
        return user

    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        role=definition["role"],
        full_name=definition["full_name"],
        demo_rehearsal_tag=HOME_VISIT_DEMO_TAG,
    )
    await user.insert()
    return user


async def _ensure_profiles(patient_user, doctor_user):
    from app.models.doctor import Doctor
    from app.models.patient import Patient

    patient = await Patient.find_one(Patient.user_id == patient_user.id)
    if not patient:
        patient = Patient(user_id=patient_user.id)
    patient.subscription_status = "active"
    patient.saved_home_address = PATIENT_ADDRESS
    patient.demo_rehearsal_tag = HOME_VISIT_DEMO_TAG
    await patient.save()

    doctor = await Doctor.find_one(Doctor.user_id == doctor_user.id)
    if not doctor:
        doctor = Doctor(user_id=doctor_user.id, specialization="Physiotherapy")
    doctor.specialization = "Physiotherapy"
    doctor.bio = "Fictional clinician profile for local Home Visit Demo testing."
    doctor.is_active_today = True
    doctor.accepts_home_visits = True
    await doctor.save()
    return patient, doctor


async def _ensure_entitlement(patient, admin_user):
    from app.models.demo_entitlement import DemoEntitlement

    entitlement = await DemoEntitlement.find_one(DemoEntitlement.patient_id == patient.id)
    if not entitlement:
        entitlement = DemoEntitlement(
            patient_id=patient.id,
            granted_by_user_id=admin_user.id,
        )
    entitlement.active = True
    entitlement.granted_by_user_id = admin_user.id
    entitlement.granted_at = utc_now()
    entitlement.revoked_at = None
    await entitlement.save()


async def _ensure_schedule(doctor, admin_user):
    from app.models.clinician_schedule import ClinicianSchedule, ScheduleAuditEvent, ScheduleBlock

    blocks = [
        ScheduleBlock(
            day_of_week=day,
            service_mode="home_visit",
            start_time="09:00",
            end_time="10:00",
        )
        for day in range(7)
    ]
    schedule = await ClinicianSchedule.find_one(ClinicianSchedule.doctor_id == doctor.id)
    if not schedule:
        schedule = ClinicianSchedule(doctor_id=doctor.id)
    now = utc_now()
    schedule.timezone = "Asia/Kolkata"
    schedule.slot_minutes = 30
    schedule.draft_weekly_blocks = blocks
    schedule.published_weekly_blocks = blocks
    schedule.draft_date_exceptions = []
    schedule.published_date_exceptions = []
    schedule.draft_revision = max(schedule.draft_revision, 1)
    schedule.published_revision = schedule.draft_revision
    schedule.published_at = now
    schedule.updated_at = now
    schedule.audit_history = [
        ScheduleAuditEvent(
            action="published",
            actor_user_id=admin_user.id,
            revision=schedule.published_revision,
            occurred_at=now,
        )
    ]
    await schedule.save()


async def _verify_logins(credentials):
    async with httpx.AsyncClient(base_url=API_ORIGIN, timeout=10.0) as client:
        for role, definition in ACCOUNT_DEFINITIONS.items():
            response = await client.post(
                "/api/auth/login",
                json={
                    "email": definition["email"],
                    "password": credentials[role]["password"],
                },
            )
            if response.status_code != 200 or response.json().get("role") != definition["role"]:
                raise RuntimeError(f"Authentication verification failed for {role}")


async def prepare() -> None:
    credentials = _load_or_create_credentials()
    client = await _init_database()
    try:
        patient_user = await _ensure_user("patient", credentials["patient"]["password"])
        doctor_user = await _ensure_user("doctor", credentials["doctor"]["password"])
        admin_user = await _ensure_user("admin", credentials["admin"]["password"])
        patient, doctor = await _ensure_profiles(patient_user, doctor_user)
        await _ensure_entitlement(patient, admin_user)
        await _ensure_schedule(doctor, admin_user)
        await _verify_logins(credentials)
        print("Home Visit Demo fixtures are ready.")
        print(f"Credentials stored locally at: {credentials_file()}")
        print("Verified fictional patient, doctor, and administrator authentication.")
        print("Verified active Nellore entitlement and published home-visit schedule.")
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare",))
    args = parser.parse_args()
    _ensure_dedicated_environment()
    asyncio.run(prepare())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Home Visit Demo fixture preparation stopped safely ({type(exc).__name__}).")
        sys.exit(1)
