"""Run the connected laboratory lifecycle against a disposable local database.

This script is intentionally guarded. It never targets the normal verification
database, never prints generated credentials, and leaves cleanup to the caller
so non-secret evidence can be inspected before the disposable database is
dropped.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from pymongo import MongoClient

from app.core.security import get_password_hash


EXPECTED_MONGO_URL = "mongodb://127.0.0.1:27018"
DATABASE_PREFIX = "physiocare_lab_rehearsal_"
EXPECTED_ACK = "isolated-lab-rehearsal"
API_BASE_URL = os.environ.get("PHYSIOCARE_REHEARSAL_API", "http://127.0.0.1:8001")
FRONTEND_ORIGIN = "http://localhost:5175"


def require_isolation() -> tuple[str, Path]:
    mongo_url = os.environ.get("MONGODB_URL")
    database_name = os.environ.get("DATABASE_NAME", "")
    storage_root = Path(os.environ.get("LAB_REPORT_STORAGE_DIR", ""))
    if os.environ.get("PHYSIOCARE_REHEARSAL_ACK") != EXPECTED_ACK:
        raise RuntimeError("The explicit isolated-rehearsal acknowledgement is missing")
    if mongo_url != EXPECTED_MONGO_URL:
        raise RuntimeError("The rehearsal must use the approved loopback MongoDB listener")
    if not database_name.startswith(DATABASE_PREFIX):
        raise RuntimeError("Refusing to run outside a disposable rehearsal database")
    if database_name == "physiocare_local_verification_6077c2718ea1":
        raise RuntimeError("Refusing to use the existing verification database")
    if not storage_root.is_absolute() or not str(storage_root).startswith("/tmp/physiocare_lab_rehearsal_"):
        raise RuntimeError("The rehearsal report directory must be isolated under /tmp")
    return database_name, storage_root


def assert_status(response: httpx.Response, expected: int, label: str) -> dict:
    if response.status_code != expected:
        detail = response.text[:500]
        raise AssertionError(f"{label}: expected {expected}, got {response.status_code}: {detail}")
    if not response.content:
        return {}
    return response.json()


def login(client: httpx.Client, email: str, password: str) -> str:
    payload = assert_status(
        client.post("/api/auth/login", json={"email": email, "password": password}),
        200,
        "login",
    )
    return payload["csrf_token"]


def unsafe_headers(csrf: str, **extra: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf, **extra}


def main() -> None:
    database_name, storage_root = require_isolation()
    mongo = MongoClient(EXPECTED_MONGO_URL)
    database = mongo[database_name]
    collection_names = database.list_collection_names()
    if any(database[name].count_documents({}) for name in collection_names):
        raise RuntimeError("Disposable rehearsal database contains records")

    run_suffix = database_name.removeprefix(DATABASE_PREFIX)
    passwords = {role: secrets.token_urlsafe(24) for role in ("patient", "admin", "laboratorian", "doctor")}
    emails = {role: f"rehearsal.{role}.{run_suffix}@example.com" for role in passwords}

    admin_id = database.users.insert_one({
        "email": emails["admin"],
        "hashed_password": get_password_hash(passwords["admin"]),
        "role": "admin",
        "full_name": "Fictional Rehearsal Administrator",
        "is_active": True,
        "created_at": datetime.utcnow(),
    }).inserted_id

    clients = {
        role: httpx.Client(
            base_url=API_BASE_URL,
            headers={"Origin": FRONTEND_ORIGIN},
            timeout=15,
            follow_redirects=False,
        )
        for role in passwords
    }
    summary: dict[str, object] = {
        "database": database_name,
        "existing_database_targeted": False,
        "fictional_accounts": 4,
    }

    try:
        assert_status(clients["patient"].post("/api/auth/register", json={
            "email": emails["patient"],
            "password": passwords["patient"],
            "full_name": "Fictional Rehearsal Patient",
        }), 201, "patient registration")

        admin_csrf = login(clients["admin"], emails["admin"], passwords["admin"])
        for role, name in (
            ("laboratorian", "Fictional Rehearsal Laboratorian"),
            ("doctor", "Fictional Rehearsal Doctor"),
        ):
            assert_status(clients["admin"].post(
                "/api/users/staff",
                json={"email": emails[role], "password": passwords[role], "full_name": name, "role": role},
                headers=unsafe_headers(admin_csrf),
            ), 201, f"administrator creates {role}")

        patient_csrf = login(clients["patient"], emails["patient"], passwords["patient"])
        laboratorian_csrf = login(
            clients["laboratorian"], emails["laboratorian"], passwords["laboratorian"]
        )
        doctor_csrf = login(clients["doctor"], emails["doctor"], passwords["doctor"])

        doctors = assert_status(clients["patient"].get("/api/users/public/doctors"), 200, "doctor directory")
        doctor = next(item for item in doctors if item["full_name"] == "Fictional Rehearsal Doctor")
        window = assert_status(
            clients["patient"].get("/api/appointments/booking-window"), 200, "booking window"
        )
        earliest = date.fromisoformat(window["earliest_date"])
        latest = date.fromisoformat(window["latest_date"])
        appointment_date = min(earliest + timedelta(days=1), latest)
        availability = assert_status(clients["patient"].get(
            "/api/appointments/availability",
            params={"doctor_id": doctor["id"], "appointment_date": appointment_date.isoformat()},
        ), 200, "doctor availability")
        slot = next(item["time_slot"] for item in availability["slots"] if item["available"])
        assert_status(clients["patient"].post(
            "/api/appointments",
            json={
                "doctor_id": doctor["id"],
                "appointment_date": appointment_date.isoformat(),
                "time_slot": slot,
                "reason": "Fictional report-access rehearsal",
            },
            headers=unsafe_headers(patient_csrf),
        ), 201, "patient appointment")

        request_payload = assert_status(clients["patient"].post(
            "/api/lab-requests",
            json={
                "mode": "clinic_visit",
                "selected_tests": ["cbc", "albumin"],
                "save_address": False,
            },
            headers=unsafe_headers(patient_csrf, **{"Idempotency-Key": f"lab-{run_suffix}"}),
        ), 201, "patient laboratory request")
        request_id = request_payload["id"]

        # Negative role checks before the administrative workflow proceeds.
        assert_status(clients["patient"].get("/api/lab-requests/admin"), 403, "patient admin-list denial")
        assert_status(
            clients["patient"].post(
                f"/api/lab-requests/admin/{request_id}/publish-report",
                headers=unsafe_headers(patient_csrf),
            ),
            403,
            "patient publication denial",
        )
        assert_status(
            clients["doctor"].get(f"/api/lab-requests/{request_id}/report-file"),
            404,
            "doctor unreleased-file invisibility",
        )

        assert_status(clients["admin"].patch(
            f"/api/lab-requests/admin/{request_id}",
            json={"status": "approved_for_coordination"},
            headers=unsafe_headers(admin_csrf),
        ), 200, "administrator approval")
        laboratorians = assert_status(
            clients["admin"].get("/api/users/laboratorians"), 200, "laboratorian directory"
        )
        laboratorian_id = next(
            item["id"] for item in laboratorians if item["full_name"] == "Fictional Rehearsal Laboratorian"
        )
        assert_status(clients["admin"].patch(
            f"/api/lab-requests/admin/{request_id}/assignment",
            json={"laboratorian_user_id": laboratorian_id},
            headers=unsafe_headers(admin_csrf),
        ), 200, "administrator assignment")

        assigned = assert_status(
            clients["laboratorian"].get("/api/lab-requests/laboratory/assigned"),
            200,
            "assigned Laboratorian queue",
        )
        if [item["id"] for item in assigned] != [request_id]:
            raise AssertionError("Laboratorian queue was not limited to the assigned fictional order")
        assert_status(
            clients["patient"].get("/api/lab-requests/laboratory/assigned"),
            403,
            "patient Laboratorian-queue denial",
        )

        fictional_pdf = b"%PDF-1.4\n% Fictional rehearsal report; not clinical data.\n%%EOF\n"
        upload = assert_status(clients["laboratorian"].put(
            f"/api/lab-requests/laboratory/{request_id}/report",
            content=fictional_pdf,
            headers=unsafe_headers(
                laboratorian_csrf,
                **{"Content-Type": "application/pdf", "X-Report-Filename": "fictional-rehearsal-report.pdf"},
            ),
        ), 200, "Laboratorian finalized upload")
        if upload["report_status"] != "awaiting_publication":
            raise AssertionError("Finalized upload was not held for administrator publication")
        assert_status(
            clients["laboratorian"].post(
                f"/api/lab-requests/admin/{request_id}/publish-report",
                headers=unsafe_headers(laboratorian_csrf),
            ),
            403,
            "Laboratorian publication denial",
        )
        assert_status(
            clients["patient"].get(f"/api/lab-requests/{request_id}/report-file"),
            404,
            "patient unpublished-file invisibility",
        )

        published = assert_status(clients["admin"].post(
            f"/api/lab-requests/admin/{request_id}/publish-report",
            headers=unsafe_headers(admin_csrf),
        ), 200, "administrator publication")
        if published["report_status"] != "released":
            raise AssertionError("Administrator publication did not release the report")
        repeated = assert_status(clients["admin"].post(
            f"/api/lab-requests/admin/{request_id}/publish-report",
            headers=unsafe_headers(admin_csrf),
        ), 200, "idempotent administrator publication")
        if repeated["report_status"] != "released":
            raise AssertionError("Repeated publication was not idempotent")

        patient_reports = assert_status(
            clients["patient"].get("/api/lab-requests/me/reports"), 200, "patient released reports"
        )
        doctor_reports = assert_status(
            clients["doctor"].get("/api/lab-requests/doctor/reports"), 200, "assigned-doctor reports"
        )
        if [item["request_id"] for item in patient_reports] != [request_id]:
            raise AssertionError("Patient did not receive exactly the owned released report")
        if [item["request_id"] for item in doctor_reports] != [request_id]:
            raise AssertionError("Assigned doctor did not receive exactly the linked released report")

        patient_file = clients["patient"].get(f"/api/lab-requests/{request_id}/report-file")
        doctor_file = clients["doctor"].get(f"/api/lab-requests/{request_id}/report-file")
        if patient_file.status_code != 200 or doctor_file.status_code != 200:
            raise AssertionError("Released report file was not available to patient and assigned doctor")
        if patient_file.content != fictional_pdf or doctor_file.content != fictional_pdf:
            raise AssertionError("Downloaded report bytes did not match the finalized upload")

        stored = database.lab_requests.find_one({"_id": request_payload["id"]})
        if stored is not None:
            raise AssertionError("Unexpected string identifier storage")
        stored = database.lab_requests.find_one({"report_status": "released"})
        history = stored.get("report_publication_history", []) if stored else []
        if len(history) != 1 or history[0].get("action") != "administratively_published":
            raise AssertionError("Administrator publication audit was not recorded exactly once")

        summary.update({
            "patient_registration": "passed",
            "admin_protected_staff_creation": "passed",
            "fictional_appointment_link": "passed",
            "patient_lab_request": "passed",
            "admin_approval_and_assignment": "passed",
            "laboratorian_finalized_upload": "passed",
            "admin_only_publication": "passed",
            "publication_idempotency": "passed",
            "patient_released_report_access": "passed",
            "assigned_doctor_released_report_access": "passed",
            "negative_role_and_unreleased_checks": "passed",
            "publication_audit_entries": len(history),
            "database_counts": {
                "users": database.users.count_documents({}),
                "patients": database.patients.count_documents({}),
                "doctors": database.doctors.count_documents({}),
                "appointments": database.appointments.count_documents({}),
                "lab_requests": database.lab_requests.count_documents({}),
                "sessions": database.auth_sessions.count_documents({}),
            },
            "temporary_report_files": len(list(storage_root.glob("*.pdf"))),
        })
        print(json.dumps(summary, sort_keys=True))
    finally:
        for client in clients.values():
            client.close()
        mongo.close()


if __name__ == "__main__":
    main()
