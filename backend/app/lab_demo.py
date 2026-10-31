"""Prepare, verify, and clean the isolated laboratory demo."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from beanie import PydanticObjectId
from pymongo import MongoClient

from app.core.config import (
    LAB_DEMO_DATABASE_NAME,
    LAB_DEMO_MONGODB_URL,
    lab_demo_home,
    settings,
)
from app.core.lab_demo import LAB_DEMO_REHEARSAL_TAG
from app.core.lab_demo_storage import (
    SAMPLE_REPORT_NAME,
    is_generated_report_key,
    report_file_path,
    report_storage_root,
    secure_demo_home,
    secure_private_file,
    secure_report_storage,
)
from app.database import init_db
from app.models.lab_request import LabRequest
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import StaffCreate
from app.services.auth_service import AuthService
from app.services.lab_demo_service import LabDemoService


API_ORIGIN = "http://127.0.0.1:5175"
ACCOUNT_DETAILS = {
    "admin": ("physiocare.lab.demo.admin@example.com", "PhysioCare Lab Demo Administrator", "admin"),
    "patient": ("physiocare.lab.demo.patient@example.com", "PhysioCare Fictional Lab Demo Patient", "patient"),
    "laboratorian": (
        "physiocare.lab.demo.laboratorian@example.com",
        "PhysioCare Lab Demo Laboratorian",
        "laboratorian",
    ),
}
PROBE_EMAIL = "physiocare.lab.demo.probe@example.com"
PROBE_NAME = "PhysioCare Temporary Lab Access Probe"
ALLOWED_DEMO_COLLECTIONS = {"users", "patients", "lab_requests", "auth_sessions"}


def credentials_path() -> Path:
    return lab_demo_home() / "credentials.json"


def sample_report_path() -> Path:
    return report_storage_root() / SAMPLE_REPORT_NAME


def _build_pdf(stream: bytes) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, content in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(content)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def _legacy_sample_pdf_bytes() -> bytes:
    stream = (
        b"BT /F1 14 Tf 50 750 Td "
        b"(FICTIONAL DEMO ONLY - PhysioCare Laboratory Report) Tj ET"
    )
    return _build_pdf(stream)


def sample_pdf_bytes(generated_on: date | None = None) -> bytes:
    generated_on = generated_on or date.today()
    lines = [
        "DEMO ONLY - FICTIONAL DATA - NOT A CLINICAL REPORT",
        "PHYSIOCARE FICTIONAL LABORATORY",
        "Laboratory Report - Demonstration Sample",
        "Report ID: DEMO-LAB-0001",
        f"Generated: {generated_on.isoformat()}",
        "Patient: Fictional Demonstration Patient (not real)",
        "Status: DEMO ONLY - not for diagnosis or treatment",
        "",
        "TEST RESULTS (FABRICATED EXAMPLES ONLY)",
        "Test | Fictional value | Unit | Illustrative reference interval",
        "Sodium | 140 | mmol/L | 135-145",
        "Glucose, fasting | 5.2 | mmol/L | 3.9-5.5",
        "Hemoglobin | 13.5 | g/dL | 12.0-16.0",
        "",
        "All values and intervals are invented for interface testing.",
        "No patient, specimen, or laboratory analysis produced this report.",
        "Do not use these examples for medical interpretation or care.",
        "",
        "DEMO ONLY - NO CLINICAL RESULT - NO MEDICAL DECISION",
    ]
    stream = bytearray(b"BT /F1 11 Tf 52 748 Td\n")
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream.extend(f"({escaped}) Tj 0 -30 Td\n".encode("ascii"))
    stream.extend(b"ET")
    return _build_pdf(bytes(stream))


def _is_known_sample_pdf(content: bytes) -> bool:
    if content == _legacy_sample_pdf_bytes():
        return True
    match = re.search(rb"\(Generated: (\d{4}-\d{2}-\d{2})\) Tj", content)
    if not match:
        return False
    try:
        generated_on = date.fromisoformat(match.group(1).decode("ascii"))
    except ValueError:
        return False
    return content == sample_pdf_bytes(generated_on)


def _secure_write(path: Path, content: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise RuntimeError("Refusing to overwrite an existing private demo file")
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        descriptor = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        secure_private_file(temp)
        os.replace(temp, path)
        secure_private_file(path)
    finally:
        if temp.exists():
            temp.unlink()


def _write_credentials(data: dict[str, Any]) -> None:
    home = secure_demo_home()
    path = home / "credentials.json"
    if path.is_symlink():
        raise RuntimeError("Credentials path cannot be a symbolic link")
    encoded = json.dumps(data, sort_keys=True, indent=2).encode("utf-8")
    if path.exists():
        temp = home / f".credentials.{uuid.uuid4().hex}.tmp"
        try:
            descriptor = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as target:
                target.write(encoded)
                target.flush()
                os.fsync(target.fileno())
            secure_private_file(temp)
            os.replace(temp, path)
            secure_private_file(path)
        finally:
            if temp.exists():
                temp.unlink()
    else:
        _secure_write(path, encoded)


def _read_credentials() -> dict[str, Any]:
    path = credentials_path()
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Demo credentials are unavailable; run the explicit prepare command first")
    secure_private_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    for role, (email, _name, _expected_role) in ACCOUNT_DETAILS.items():
        item = data.get(role)
        if not isinstance(item, dict) or item.get("email") != email:
            raise RuntimeError("The protected demo credential file is incomplete or invalid")
        password = item.get("password")
        if not isinstance(password, str) or len(password) < 32:
            raise RuntimeError("The protected demo credential file is incomplete or invalid")
    return data


def _ensure_demo_settings() -> None:
    settings.validate_lab_demo_isolation()
    if (
        not settings.LAB_DEMO_MODE
        or settings.DATABASE_NAME != LAB_DEMO_DATABASE_NAME
        or settings.MONGODB_URL != LAB_DEMO_MONGODB_URL
    ):
        raise RuntimeError("Refusing to continue without the validated isolated laboratory demo configuration")


def _verify_database_contents() -> None:
    _ensure_demo_settings()
    with MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=3000) as client:
        client.admin.command("ping")
        database = client[settings.DATABASE_NAME]
        for collection_name in database.list_collection_names():
            collection = database[collection_name]
            count = collection.count_documents({})
            if count == 0:
                continue
            if collection_name not in ALLOWED_DEMO_COLLECTIONS:
                raise RuntimeError("The isolated demo database contains unexpected records")
            untagged = collection.count_documents({
                "demo_rehearsal_tag": {"$ne": LAB_DEMO_REHEARSAL_TAG},
            })
            if untagged:
                raise RuntimeError("The isolated demo database contains untagged records")


def _assert_existing_account(
    user: User | None,
    *,
    email: str,
    role: str,
    full_name: str,
) -> User | None:
    if user is None:
        return None
    if (
        user.email != email
        or user.role != role
        or user.full_name != full_name
        or not user.is_active
        or user.demo_rehearsal_tag != LAB_DEMO_REHEARSAL_TAG
    ):
        raise RuntimeError("A reserved demo account conflicts with an untagged or unexpected account")
    return user


def _new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{settings.PORT}/api",
        headers={"Origin": API_ORIGIN},
        timeout=20,
        follow_redirects=False,
    )


def _expect(response: httpx.Response, expected_status: int, step: str) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise RuntimeError(
            f"{step} failed: expected HTTP {expected_status}, received {response.status_code}"
        )
    if not response.content:
        return {}
    return response.json()


async def _login(client: httpx.AsyncClient, role: str, account: dict[str, str]) -> str:
    payload = _expect(
        await client.post(
            "/auth/login",
            json={"email": account["email"], "password": account["password"]},
        ),
        200,
        f"{role} login",
    )
    if payload.get("role") != role:
        raise RuntimeError(f"Authentication returned an unexpected role for the {role} account")
    current = _expect(await client.get("/auth/me"), 200, f"{role} session verification")
    if current.get("role") != role or current.get("email") != account["email"]:
        raise RuntimeError(f"The authenticated session does not match the {role} account")
    return payload["csrf_token"]


def _unsafe_headers(csrf_token: str, **extra: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf_token, **extra}


async def _ensure_admin_and_patient(credentials: dict[str, Any]) -> None:
    admin_email, admin_name, _ = ACCOUNT_DETAILS["admin"]
    await LabDemoService.ensure_account(
        role="admin",
        email=admin_email,
        password=credentials["admin"]["password"],
        full_name=admin_name,
    )
    patient_email, patient_name, _ = ACCOUNT_DETAILS["patient"]
    await LabDemoService.ensure_account(
        role="patient",
        email=patient_email,
        password=credentials["patient"]["password"],
        full_name=patient_name,
    )


async def _ensure_laboratorian_via_admin(
    admin_client: httpx.AsyncClient,
    admin_csrf: str,
    credentials: dict[str, Any],
) -> None:
    email, full_name, role = ACCOUNT_DETAILS["laboratorian"]
    existing = _assert_existing_account(
        await UserRepository.get_by_email(email),
        email=email,
        role=role,
        full_name=full_name,
    )
    if existing:
        return
    _expect(
        await admin_client.post(
            "/users/staff",
            json={
                "email": email,
                "password": credentials["laboratorian"]["password"],
                "full_name": full_name,
                "role": role,
                "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
            },
            headers=_unsafe_headers(admin_csrf),
        ),
        201,
        "Admin creates the demo laboratorian",
    )


def _ensure_sample_pdf() -> bytes:
    root = secure_report_storage()
    path = root / SAMPLE_REPORT_NAME
    sample = sample_pdf_bytes()
    if path.is_symlink():
        raise RuntimeError("The demo sample report cannot be a symbolic link")
    if path.exists():
        if not path.is_file():
            raise RuntimeError("An unexpected file already occupies the demo sample report path")
        existing = path.read_bytes()
        if not _is_known_sample_pdf(existing):
            raise RuntimeError("An unexpected file already occupies the demo sample report path")
        return existing
    else:
        _secure_write(path, sample)
    return sample


async def _verify_demo_storage_contents() -> None:
    root = secure_report_storage()
    requests = await LabRequest.find({
        "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
    }).to_list()
    expected_names = {SAMPLE_REPORT_NAME}
    for request in requests:
        key = request.report_storage_key
        if key:
            if not is_generated_report_key(key):
                raise RuntimeError("A tagged request has an unexpected report storage key")
            expected_names.add(key)
    if any(entry.is_dir() or entry.is_symlink() for entry in root.iterdir()):
        raise RuntimeError("Demo report storage contains an unexpected directory or link")
    if any(entry.name not in expected_names for entry in root.iterdir()):
        raise RuntimeError("Demo report storage contains a file not owned by the rehearsal")


async def prepare() -> None:
    _ensure_demo_settings()
    await init_db()
    await asyncio.to_thread(_verify_database_contents)
    path = credentials_path()
    tagged_user_count = await User.find({
        "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
    }).count()
    if path.exists():
        credentials = _read_credentials()
    elif tagged_user_count:
        raise RuntimeError("Tagged demo accounts already exist but their protected credentials are missing")
    else:
        credentials = {
            role: {"email": email, "password": secrets.token_urlsafe(36)}
            for role, (email, _name, _role) in ACCOUNT_DETAILS.items()
        }
        _write_credentials(credentials)

    for role, (email, _name, expected_role) in ACCOUNT_DETAILS.items():
        _assert_existing_account(
            await UserRepository.get_by_email(email),
            email=email,
            role=expected_role,
            full_name=ACCOUNT_DETAILS[role][1],
        )

    await _ensure_admin_and_patient(credentials)
    await _verify_demo_storage_contents()
    admin_client = _new_client()
    patient_client = _new_client()
    laboratorian_client = _new_client()
    try:
        admin_csrf = await _login(admin_client, "admin", credentials["admin"])
        await _ensure_laboratorian_via_admin(admin_client, admin_csrf, credentials)
        await _login(laboratorian_client, "laboratorian", credentials["laboratorian"])
        patient_csrf = await _login(patient_client, "patient", credentials["patient"])
        laboratorians = _expect(
            await admin_client.get("/users/laboratorians"),
            200,
            "Admin verifies the laboratorian directory",
        )
        if not any(
            item.get("full_name") == ACCOUNT_DETAILS["laboratorian"][1]
            for item in laboratorians
        ):
            raise RuntimeError("The Admin API does not list the demo laboratorian")
        _ensure_sample_pdf()

        request = _expect(
            await patient_client.post(
                "/lab-requests",
                json={
                    "mode": "clinic_visit",
                    "selected_tests": ["cbc", "albumin"],
                    "save_address": False,
                    "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
                },
                headers=_unsafe_headers(
                    patient_csrf,
                    **{"Idempotency-Key": LAB_DEMO_REHEARSAL_TAG},
                ),
            ),
            201,
            "Patient creates the demo laboratory request",
        )
        admin_requests = _expect(
            await admin_client.get("/lab-requests/admin"),
            200,
            "Admin views laboratory requests",
        )
        patient_requests = _expect(
            await patient_client.get("/lab-requests/me"),
            200,
            "Patient verifies the submitted request",
        )
        request_id = request.get("id")
        stored_request = (
            await LabRequest.get(PydanticObjectId(request_id))
            if request_id and PydanticObjectId.is_valid(request_id)
            else None
        )
        if (
            not request_id
            or request.get("status") not in {"pending_clinic_confirmation", "approved_for_coordination"}
            or request.get("report_status") not in {"not_started", "awaiting_publication", "released"}
            or request.get("selected_tests") != ["cbc", "albumin"]
            or not stored_request
            or stored_request.demo_rehearsal_tag != LAB_DEMO_REHEARSAL_TAG
            or not any(item.get("id") == request_id for item in admin_requests)
            or not any(item.get("id") == request_id for item in patient_requests)
        ):
            raise RuntimeError("The demo request was not visible in a reusable workflow state")
    finally:
        await admin_client.aclose()
        await patient_client.aclose()
        await laboratorian_client.aclose()

    print(json.dumps({
        "environment": "isolated",
        "database": LAB_DEMO_DATABASE_NAME,
        "accounts": "ready",
        "laboratory_request": request["status"],
        "sample_report": "ready in private demo storage",
        "workflow": "not yet run",
        "credentials": "stored in protected per-user storage; not displayed",
    }, sort_keys=True))


async def _check_upload_rejections(
    laboratorian_client: httpx.AsyncClient,
    request_id: str,
    csrf_token: str,
) -> None:
    headers = _unsafe_headers(
        csrf_token,
        **{"X-Report-Filename": "invalid-demo.pdf", "Content-Type": "application/pdf"},
    )
    _expect(
        await laboratorian_client.put(
            f"/lab-requests/laboratory/{request_id}/report",
            content=b"This is not a PDF",
            headers=headers,
        ),
        422,
        "Invalid PDF rejection",
    )
    oversized_headers = _unsafe_headers(
        csrf_token,
        **{"X-Report-Filename": "oversized-demo.pdf", "Content-Type": "application/pdf"},
    )
    _expect(
        await laboratorian_client.put(
            f"/lab-requests/laboratory/{request_id}/report",
            content=b"%PDF-1.4" + (b"x" * (settings.LAB_REPORT_MAX_BYTES + 1)),
            headers=oversized_headers,
        ),
        413,
        "Oversized PDF rejection",
    )


async def rehearse() -> None:
    _ensure_demo_settings()
    await init_db()
    await asyncio.to_thread(_verify_database_contents)
    credentials = _read_credentials()
    tagged_requests = await LabRequest.find({
        "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
    }).to_list()
    if len(tagged_requests) != 1:
        raise RuntimeError("The isolated database must contain exactly one tagged laboratory request")
    request = tagged_requests[0]
    if not request:
        raise RuntimeError("No tagged demo request exists; run the prepare command first")
    request_id = str(request.id)
    await _verify_demo_storage_contents()
    sample = sample_report_path()
    if sample.is_symlink() or not sample.is_file():
        raise RuntimeError("The private demo sample PDF is missing or unexpected")
    sample_content = sample.read_bytes()
    if not _is_known_sample_pdf(sample_content):
        raise RuntimeError("The private demo sample PDF is missing or unexpected")

    clients = {role: _new_client() for role in ("admin", "patient", "laboratorian")}
    try:
        csrf = {
            role: await _login(clients[role], role, credentials[role])
            for role in ("admin", "patient", "laboratorian")
        }
        admin_client = clients["admin"]
        patient_client = clients["patient"]
        laboratorian_client = clients["laboratorian"]

        listed = _expect(
            await admin_client.get("/lab-requests/admin"),
            200,
            "Admin request list",
        )
        if not any(item.get("id") == request_id for item in listed):
            raise RuntimeError("Admin request list does not contain the isolated demo request")

        if request.status == "pending_clinic_confirmation":
            reviewed = _expect(
                await admin_client.patch(
                    f"/lab-requests/admin/{request_id}",
                    json={"status": "approved_for_coordination"},
                    headers=_unsafe_headers(csrf["admin"]),
                ),
                200,
                "Admin approves the laboratory request",
            )
            if reviewed.get("status") != "approved_for_coordination":
                raise RuntimeError("The demo laboratory request was not approved")
        elif request.status != "approved_for_coordination":
            raise RuntimeError("The demo laboratory request is in an unexpected workflow state")

        laboratorians = _expect(
            await admin_client.get("/users/laboratorians"),
            200,
            "Admin laboratorian directory",
        )
        expected_laboratorian = next(
            (item for item in laboratorians if item.get("full_name") == ACCOUNT_DETAILS["laboratorian"][1]),
            None,
        )
        if not expected_laboratorian:
            raise RuntimeError("The demo laboratorian is not available for assignment")

        if request.assigned_laboratorian_user_id is None:
            assignment = _expect(
                await admin_client.patch(
                    f"/lab-requests/admin/{request_id}/assignment",
                    json={"laboratorian_user_id": expected_laboratorian["id"]},
                    headers=_unsafe_headers(csrf["admin"]),
                ),
                200,
                "Admin assigns the request to the laboratorian",
            )
            if assignment.get("assigned_laboratorian_user_id") != expected_laboratorian["id"]:
                raise RuntimeError("The request assignment was not persisted")
        elif str(request.assigned_laboratorian_user_id) != expected_laboratorian["id"]:
            raise RuntimeError("The demo request is assigned to an unexpected laboratorian")

        assigned = _expect(
            await laboratorian_client.get("/lab-requests/laboratory/assigned"),
            200,
            "Laboratorian assigned-request list",
        )
        if [item.get("id") for item in assigned] != [request_id]:
            raise RuntimeError("The laboratorian request list is not limited to the assigned demo request")

        _expect(
            await patient_client.get("/lab-requests/admin"),
            403,
            "Patient denial for Admin laboratory requests",
        )
        _expect(
            await patient_client.post(
                f"/lab-requests/admin/{request_id}/publish-report",
                headers=_unsafe_headers(csrf["patient"]),
            ),
            403,
            "Patient denial for report publication",
        )
        _expect(
            await laboratorian_client.post(
                f"/lab-requests/admin/{request_id}/publish-report",
                headers=_unsafe_headers(csrf["laboratorian"]),
            ),
            403,
            "Laboratorian denial for report publication",
        )

        if request.report_status in {"not_started", "awaiting_publication"}:
            await _check_upload_rejections(laboratorian_client, request_id, csrf["laboratorian"])

        probe_password = credentials.get("probe", {}).get("password")
        if not probe_password:
            probe_password = secrets.token_urlsafe(36)
            credentials["probe"] = {"email": PROBE_EMAIL, "password": probe_password}
            _write_credentials(credentials)
        probe_user = await LabDemoService.ensure_account(
            role="laboratorian",
            email=PROBE_EMAIL,
            password=probe_password,
            full_name=PROBE_NAME,
        )
        probe_client = _new_client()
        try:
            probe_csrf = await _login(
                probe_client,
                "laboratorian",
                {"email": PROBE_EMAIL, "password": probe_password},
            )
            _expect(
                await probe_client.put(
                    f"/lab-requests/laboratory/{request_id}/report",
                    content=b"This is not a PDF",
                    headers=_unsafe_headers(
                        probe_csrf,
                        **{
                            "X-Report-Filename": "unassigned-probe.pdf",
                            "Content-Type": "application/pdf",
                        },
                    ),
                ),
                403,
                "Cross-laboratorian upload denial",
            )
        finally:
            await probe_client.aclose()
            await LabDemoService.remove_temporary_laboratorian(str(probe_user.id))
            credentials.pop("probe", None)
            _write_credentials(credentials)

        current = await LabRequest.get(request.id)
        if not current:
            raise RuntimeError("The demo request disappeared during the rehearsal")
        if current.report_status == "not_started":
            uploaded = _expect(
                await laboratorian_client.put(
                    f"/lab-requests/laboratory/{request_id}/report",
                    content=sample_content,
                    headers=_unsafe_headers(
                        csrf["laboratorian"],
                        **{
                            "X-Report-Filename": SAMPLE_REPORT_NAME,
                            "Content-Type": "application/pdf",
                        },
                    ),
                ),
                200,
                "Laboratorian uploads the sample PDF",
            )
            if uploaded.get("report_status") != "awaiting_publication":
                raise RuntimeError("The uploaded report did not enter awaiting_publication")
        elif current.report_status == "awaiting_publication":
            draft = await admin_client.get(f"/lab-requests/{request_id}/report-file")
            if draft.status_code != 200 or draft.content != sample_content:
                raise RuntimeError("The unpublished demo report does not match the sample PDF")
        elif current.report_status != "released":
            raise RuntimeError("The demo report is in an unexpected workflow state")

        current = await LabRequest.get(request.id)
        if not current:
            raise RuntimeError("The demo request disappeared during report verification")
        if current.report_status == "awaiting_publication":
            _expect(
                await patient_client.get(f"/lab-requests/{request_id}/report-file"),
                404,
                "Patient denial for unpublished report",
            )
            published = _expect(
                await admin_client.post(
                    f"/lab-requests/admin/{request_id}/publish-report",
                    headers=_unsafe_headers(csrf["admin"]),
                ),
                200,
                "Admin publishes the finalized report",
            )
            if published.get("report_status") != "released":
                raise RuntimeError("Admin publication did not release the report")
        elif current.report_status != "released":
            raise RuntimeError("The demo report could not be published")

        final_request = await LabRequest.get(request.id)
        if (
            not final_request
            or final_request.demo_rehearsal_tag != LAB_DEMO_REHEARSAL_TAG
            or final_request.assigned_laboratorian_user_id is None
            or str(final_request.assigned_laboratorian_user_id) != expected_laboratorian["id"]
            or final_request.report_status != "released"
        ):
            raise RuntimeError("The persisted demo request or report state is incorrect")

        patient_reports = _expect(
            await patient_client.get("/lab-requests/me/reports"),
            200,
            "Patient released-report list",
        )
        if [item.get("request_id") for item in patient_reports] != [request_id]:
            raise RuntimeError("The patient did not receive exactly the demo report")
        patient_file = await patient_client.get(f"/lab-requests/{request_id}/report-file")
        if patient_file.status_code != 200 or patient_file.content != sample_content:
            raise RuntimeError("The patient could not retrieve the published sample report")

        print(json.dumps({
            "environment": "isolated",
            "admin_authentication": "passed",
            "laboratorian_authentication": "passed",
            "patient_authentication": "passed",
            "admin_request_review_and_assignment": "passed",
            "assigned_request_visibility": "passed",
            "cross_laboratorian_upload_denial": "passed",
            "invalid_and_oversized_pdf_rejection": (
                "passed" if request.report_status != "released" else "not re-run; report already released"
            ),
            "unpublished_report_patient_denial": (
                "passed" if request.report_status != "released" else "covered by backend contract tests"
            ),
            "admin_only_publication": "passed",
            "patient_published_report_access": "passed",
            "final_report_status": "released",
        }, sort_keys=True))
    finally:
        for client in clients.values():
            await client.aclose()


async def _validate_cleanup_files() -> list[Path]:
    root = report_storage_root()
    if not root.exists():
        return []
    requests = await LabRequest.find({"demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG}).to_list()
    expected_names = {SAMPLE_REPORT_NAME}
    report_paths: list[Path] = []
    for request in requests:
        key = request.report_storage_key
        if key:
            if not is_generated_report_key(key):
                raise RuntimeError("A tagged request has an unexpected report storage key")
            path = report_file_path(key)
            expected_names.add(key)
            report_paths.append(path)
    entries = list(root.iterdir())
    if any(entry.is_dir() or entry.is_symlink() for entry in entries):
        raise RuntimeError("Refusing cleanup because demo storage contains an unexpected directory or link")
    if any(entry.name not in expected_names for entry in entries):
        raise RuntimeError("Refusing cleanup because demo storage contains an untracked file")
    sample = root / SAMPLE_REPORT_NAME
    if sample.exists():
        if sample.is_symlink() or not sample.is_file():
            raise RuntimeError("Refusing cleanup because the demo sample path is not a regular file")
        report_paths.append(sample)
    return list(dict.fromkeys(report_paths))


async def _cleanup_records() -> tuple[int, int, int, int]:
    return await LabDemoService.delete_tagged_records()


async def cleanup() -> None:
    _ensure_demo_settings()
    await init_db()
    await asyncio.to_thread(_verify_database_contents)
    files = await _validate_cleanup_files()
    credential_file = credentials_path()
    if credential_file.is_symlink():
        raise RuntimeError("Refusing to remove a symbolic-link credentials path")
    tagged_counts = (
        await User.find({"demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG}).count(),
        await LabRequest.find({"demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG}).count(),
    )
    phrase = f"DELETE {LAB_DEMO_DATABASE_NAME} {LAB_DEMO_REHEARSAL_TAG}"
    confirmation = input(
        f"This removes only tagged demo records and files directly in private storage "
        f"(users={tagged_counts[0]}, requests={tagged_counts[1]}). Type {phrase}: "
    )
    if confirmation != phrase:
        raise RuntimeError("Cleanup confirmation did not match; no data was removed")

    for path in files:
        if path.exists():
            path.unlink()
    counts = await _cleanup_records()
    if credential_file.exists():
        credential_file.unlink()
    print(json.dumps({
        "database": LAB_DEMO_DATABASE_NAME,
        "tagged_users_removed": counts[0],
        "tagged_patients_removed": counts[1],
        "tagged_requests_removed": counts[2],
        "tagged_sessions_removed": counts[3],
        "private_files_removed": len(files),
        "storage_directory_removed": False,
        "database_dropped": False,
    }, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="Create/reuse tagged demo accounts and one request")
    prepare_parser.add_argument("--confirm", action="store_true")
    rehearsal_parser = commands.add_parser("rehearse", help="Verify the authenticated laboratory workflow")
    rehearsal_parser.add_argument("--confirm", action="store_true")
    commands.add_parser("cleanup", help="Remove only explicitly tagged demo records after confirmation")
    args = parser.parse_args(argv)
    try:
        _ensure_demo_settings()
        if args.command == "prepare":
            if not args.confirm:
                raise RuntimeError("Pass --confirm to create or reuse demo accounts and a request")
            asyncio.run(prepare())
        elif args.command == "rehearse":
            if not args.confirm:
                raise RuntimeError("Pass --confirm to run the upload and publication rehearsal")
            asyncio.run(rehearse())
        else:
            asyncio.run(cleanup())
    except Exception as exc:
        print(f"Laboratory demo command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
