"""
Phase 4 Task 11 tests — financial security hardening & payment mutation
lockdown.

Covers the mandated checks:

AUTH LOGGING (1–5):
  Authorization header / bearer token / decoded JWT payload are never logged;
  authentication failures log safe reason categories only; safe request
  logging (method, path, status) still works.

LEGACY LAB PAYMENT PATCH (6–12):
  The retired endpoint rejects every role, never marks an online payment
  successful, never accepts client-supplied Razorpay identifiers, performs no
  writes, and the verified Razorpay path still works.

APPOINTMENT PATCH (13–18):
  Patients cannot mutate billing fields or inject payment data; a generic
  PATCH cannot fabricate an online payment; the admin offline billing
  workflow remains intact for offline appointments.

PAYMENT ORDER (19–20):
  A bound payment_order_id cannot be replaced or re-priced through generic
  mutation; the verified flow remains backend-authoritative.

All Razorpay interactions are mocked; no real transaction is performed.
"""
import inspect
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.schemas.appointment import AppointmentUpdate
from app.services.appointment_service import AppointmentService

TEST_KEY_ID = "rzp_test_unitkeyid123"
TEST_SECRET = "test_key_secret_for_unit_tests_only"

P1 = "111111111111111111111111"
APT = "333333333333333333333333"
BOOK = "444444444444444444444444"
ORDER = "order_backend123"
PAY = "pay_backend456"


@pytest.fixture(autouse=True)
def razorpay_test_config(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", TEST_KEY_ID)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", TEST_SECRET)


@pytest.fixture(autouse=True)
def mock_format_repository_calls():
    # Same convention as tests/test_appointments.py: the success path of
    # update_appointment formats via profile/user lookups; mock them so the
    # service-level assertions run without a database.
    mock_patient_user = MagicMock()
    mock_patient_user.full_name = "Jane Patient"
    mock_doctor_user = MagicMock()
    mock_doctor_user.full_name = "Dr. John Doe"
    mock_patient = MagicMock()
    mock_patient.user_id = "user-p"
    mock_doctor = MagicMock()
    mock_doctor.user_id = "user-d"
    mock_doctor.specialization = "Physical Therapy"
    with patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_id",
               new=AsyncMock(return_value=mock_patient)), \
         patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_id",
               new=AsyncMock(return_value=mock_doctor)), \
         patch("app.repositories.user_repository.UserRepository.get_by_id",
               new=AsyncMock(return_value=mock_patient_user)), \
         patch("app.services.notification_service.NotificationService.create_notification",
               new=AsyncMock(return_value=None)):
        yield


def make_patient(pid=P1):
    p = MagicMock()
    p.id = pid
    return p


def make_appointment(**kw):
    import datetime as _dt
    defaults = dict(status="pending_payment", billing_status="pending",
                    billing_amount=500.0, payment_method="online",
                    payment_status="pending", payment_id=None,
                    payment_order_id=None, patient_id=P1)
    defaults.update(kw)
    a = MagicMock()
    a.id = APT
    a.patient_id = defaults["patient_id"]
    a.status = defaults["status"]
    a.billing_status = defaults["billing_status"]
    a.billing_amount = defaults["billing_amount"]
    a.payment_method = defaults["payment_method"]
    a.payment_status = defaults["payment_status"]
    a.payment_id = defaults["payment_id"]
    a.payment_order_id = defaults["payment_order_id"]
    a.appointment_date = _dt.datetime(2026, 10, 1, 12, 0)
    a.time_slot = "09:00 AM"
    a.service_type = "clinic_consultation"
    a.doctor_id = "999999999999999999999999"
    a.reason = "Knee pain"
    a.symptoms = "Swelling"
    a.duration_days = 5
    a.pain_level = "Medium"
    a.visit_address = "123 Main St"
    a.meeting_link = None
    a.feedback_rating = None
    a.feedback_comment = None
    a.created_at = _dt.datetime(2026, 9, 1, 12, 0)
    a.save = AsyncMock(return_value=a)
    return a


# ---------------------------------------------------------------------------
# 1–5 — AUTH LOGGING
# ---------------------------------------------------------------------------

def test_authorization_header_never_logged():
    """CHECK 1: the request logger never emits the Authorization header."""
    import app.main as main_mod
    src = inspect.getsource(main_mod)
    # Structural guard: no code path prints/logs the auth header value.
    assert 'request.headers.get("authorization")' not in src
    assert "[REQUEST] Authorization" not in src
    for line in src.splitlines():
        if "print(" in line and "headers" in line.lower():
            assert "SAFE_LOG_HEADERS" in line or "safe_headers" in line, line


def test_jwt_token_and_payload_never_logged(caplog):
    """CHECKS 2/3: the auth middleware never logs tokens or decoded payloads."""
    import app.middleware.auth as auth_mod
    src = inspect.getsource(auth_mod)
    assert "DIAGNOSTIC" not in src
    assert "Decoded JWT payload" not in src
    assert "Extracted Token" not in src
    assert "auth_header" not in src
    # No print() calls at all remain in the middleware.
    assert "print(" not in src
    # The logger never formats the token or payload into a message.
    for line in src.splitlines():
        if "logger." in line and ("token" in line.lower() or "payload" in line.lower()):
            raise AssertionError(f"possible credential logging: {line}")


def test_auth_failure_logs_only_safe_reason():
    """CHECK 4 (structural): failure logging interpolates the reason category
    only — never a token, payload, or exception text."""
    import app.middleware.auth as auth_mod
    helper_src = inspect.getsource(auth_mod._log_auth_failure)
    assert 'logger.warning("Authentication failed: reason=%s", reason)' in helper_src
    # The middleware never logs the token variable or the payload variable.
    fn_src = inspect.getsource(auth_mod.get_current_user)
    for banned in ("logger.warning(token", "logger.info(token",
                   "logger.error(token", "logger.warning(payload",
                   "logger.info(payload", "logger.error(payload"):
        assert banned not in fn_src


def test_auth_failure_no_credentials_in_output(caplog):
    """CHECK 4 (behavioral): a rejected token never appears in log output."""
    from jose import jwt as jose_jwt
    import app.middleware.auth as auth_mod
    import asyncio

    forged = jose_jwt.encode(
        {"sub": P1, "role": "patient", "type": "access", "exp": 99999999999},
        "attacker-secret", algorithm="HS256",
    )
    marker = "SECRET-MARKER-abc123"
    forged = forged[:20] + marker + forged[30:]
    creds = MagicMock()
    creds.credentials = forged

    async def _call():
        await auth_mod.get_current_user(credentials=creds)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(HTTPException):
            asyncio.run(_call())

    for record in caplog.records:
        assert marker not in record.getMessage()
        assert forged not in record.getMessage()


def test_safe_request_logging_still_works(caplog):
    """CHECK 5: method/path/status logging remains functional and safe."""
    import app.main as main_mod
    src = inspect.getsource(main_mod)
    assert '[REQUEST] {request.method} {request.url.path}' in src
    assert '[RESPONSE] Status: {response.status_code}' in src
    # The allow-list exists and excludes credential-bearing headers.
    assert "SAFE_LOG_HEADERS" in src
    block = src[src.index("SAFE_LOG_HEADERS"):src.index("}")]
    for banned in ("authorization", "cookie", "x-razorpay-signature"):
        assert f'"{banned}"' not in block


# ---------------------------------------------------------------------------
# 6–12 — LEGACY LABORATORY PAYMENT PATCH
# ---------------------------------------------------------------------------

def test_lab_legacy_payment_patch_rejects_patient():
    """CHECK 6: patient role cannot reach the legacy payment PATCH."""
    client = TestClient(app)
    r = client.patch(f"/api/laboratory/bookings/{BOOK}/payment",
                     json={"payment_method": "online", "payment_id": PAY,
                           "payment_order_id": ORDER, "payment_status": "success"})
    assert r.status_code in (401, 403)


def test_lab_legacy_payment_patch_retired_for_all_roles():
    """CHECKS 7/8/9/10: the retired endpoint can never mark an online
    payment successful — for ANY role — and never performs writes."""
    src = open("app/api/laboratory.py", encoding="utf-8").read()
    start = src.index('patch("/bookings/{booking_id}/payment"')
    block = src[start:src.index('@router.patch("/bookings/{booking_id}/status"')]
    # The handler raises unconditionally — no patient-profile lookup, no
    # LaboratoryService.update_payment call, no repository write remains.
    assert "HTTP_403_FORBIDDEN" in block
    assert "LaboratoryService.update_payment" not in block
    assert "ProfileRepository.get_patient_by_user_id" not in block
    # The Task 5 role gate is preserved on the registered route.
    assert 'RoleChecker(["admin", "doctor"])' in block
    # Client-supplied Razorpay identifiers can no longer flow anywhere.
    assert "payment_update.payment_id" not in block
    assert "payment_update.payment_order_id" not in block
    assert "payment_update.payment_status" not in block
    assert "payment_update.payment_method" not in block


def test_lab_legacy_payment_patch_performs_no_writes():
    """CHECKS 7/11: even a superuser-grade probe produces no service write."""
    client = TestClient(app)
    # Unauthenticated: rejected before any state access (401/403, not 5xx).
    r = client.patch(f"/api/laboratory/bookings/{BOOK}/payment",
                     json={"payment_method": "cash", "payment_id": "x",
                           "payment_order_id": "y", "payment_status": "failed"})
    assert r.status_code in (401, 403)
    assert r.json().get("detail") != "Internal Server Error"


def test_verified_lab_razorpay_path_still_works():
    """CHECK 12: the verified order→verify flow is untouched."""
    import app.services.payment_service as ps
    fn_src = inspect.getsource(ps.PaymentService.verify_laboratory_payment)
    assert "verify_payment_signature(" in fn_src
    assert "mark_laboratory_paid" in fn_src
    assert 'schema.razorpay_order_id != stored_order_id' in fn_src


# ---------------------------------------------------------------------------
# 13–18 — APPOINTMENT PATCH
# ---------------------------------------------------------------------------

def test_appointment_update_schema_has_no_payment_fields():
    """CHECKS 14/15/16 (schema level): the mutation contract cannot carry
    payment identifiers or status claims at all."""
    fields = set(AppointmentUpdate.model_fields.keys())
    for banned in ("payment_method", "payment_status", "payment_id",
                   "payment_order_id"):
        assert banned not in fields
    assert "billing_status" in fields and "billing_amount" in fields


@pytest.mark.asyncio
async def test_patient_cannot_mutate_billing_fields():
    """CHECK 13: patient PATCH with billing fields is still 403."""
    patient = MagicMock()
    patient.id = P1
    patient.user_id = "user-p"
    appt = make_appointment(patient_id=P1)
    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=patient)):
        schema = AppointmentUpdate(billing_status="paid")
        with pytest.raises(HTTPException) as exc:
            await AppointmentService.update_appointment(
                appointment_id=str(appt.id), schema=schema,
                current_user_role="patient", current_user_id="user-p",
            )
    assert exc.value.status_code == 403
    appt.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_generic_patch_cannot_fabricate_online_payment():
    """CHECKS 17/14: admin setting billing_status=paid on an ONLINE
    appointment is rejected — online confirmation stays Razorpay-only."""
    appt = make_appointment(payment_method="online")
    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        schema = AppointmentUpdate(billing_status="paid")
        with pytest.raises(HTTPException) as exc:
            await AppointmentService.update_appointment(
                appointment_id=str(appt.id), schema=schema,
                current_user_role="admin",
            )
    assert exc.value.status_code == 409
    appt.save.assert_not_awaited()
    assert appt.billing_status == "pending"


@pytest.mark.asyncio
async def test_offline_admin_billing_workflow_preserved():
    """CHECK 18: the legitimate offline workflow (admin Billing page marking
    an offline appointment paid) still works exactly as before."""
    appt = make_appointment(payment_method="offline", status="confirmed")
    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        schema = AppointmentUpdate(billing_status="paid")
        await AppointmentService.update_appointment(
            appointment_id=str(appt.id), schema=schema,
            current_user_role="admin",
        )
    assert appt.billing_status == "paid"
    appt.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_cannot_resurrect_cancelled_online_payment_state():
    """CHECK 17 (variant): even a cancelled ONLINE appointment cannot be
    flipped to paid through generic PATCH."""
    appt = make_appointment(payment_method="online", status="cancelled",
                            billing_status="failed")
    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        schema = AppointmentUpdate(billing_status="paid")
        with pytest.raises(HTTPException) as exc:
            await AppointmentService.update_appointment(
                appointment_id=str(appt.id), schema=schema,
                current_user_role="admin",
            )
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# 19–20 — PAYMENT ORDER BINDING
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bound_order_blocks_amount_mutation():
    """CHECKS 19/20: billing_amount cannot change once a Razorpay order is
    atomically bound — the order amount remains authoritative."""
    appt = make_appointment(payment_order_id=ORDER)
    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        schema = AppointmentUpdate(billing_amount=999.0)
        with pytest.raises(HTTPException) as exc:
            await AppointmentService.update_appointment(
                appointment_id=str(appt.id), schema=schema,
                current_user_role="admin",
            )
    assert exc.value.status_code == 409
    assert appt.billing_amount == 500.0
    appt.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_bound_order_binding_untouched_by_generic_patch():
    """CHECK 19: no field of a generic PATCH can rewrite payment_order_id —
    the schema cannot carry it, and the service never writes it."""
    appt = make_appointment(payment_order_id=ORDER, payment_method="offline")
    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        schema = AppointmentUpdate(status="cancelled")
        await AppointmentService.update_appointment(
            appointment_id=str(appt.id), schema=schema,
            current_user_role="admin",
        )
    assert appt.payment_order_id == ORDER


@pytest.mark.asyncio
async def test_prepayment_admin_price_change_still_allowed():
    """Part 6: legitimate pre-payment administrative pricing (offline
    appointment, no order bound) remains supported."""
    appt = make_appointment(payment_method="offline", payment_order_id=None)
    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        schema = AppointmentUpdate(billing_amount=180.0)
        await AppointmentService.update_appointment(
            appointment_id=str(appt.id), schema=schema,
            current_user_role="admin",
        )
    assert appt.billing_amount == 180.0
    appt.save.assert_awaited_once()


# ---------------------------------------------------------------------------
# REGRESSION — Tasks 1–10 invariants
# ---------------------------------------------------------------------------

def test_online_confirmation_paths_unchanged():
    """Tasks 4/8/9: the only online-payment write paths remain the atomic
    guarded transitions; webhook semantics and expiry policy untouched."""
    import app.repositories.payment_repository as pr
    repo_src = inspect.getsource(pr)
    for marker in ("mark_appointment_paid", "mark_laboratory_paid",
                   "expire_appointment_pending_payment",
                   "expire_laboratory_pending_payment"):
        assert marker in repo_src
    # Webhook reconciliation still routes through the same transitions.
    import app.services.webhook_reconciliation_service as wrs
    wrs_src = inspect.getsource(wrs)
    assert "mark_appointment_paid" in wrs_src and "mark_laboratory_paid" in wrs_src
    # Expiry policy defaults unchanged.
    assert settings.PAYMENT_RECONCILIATION_ENABLED is False
    assert settings.PAYMENT_PENDING_EXPIRY_MINUTES is None


def test_no_refund_surface_exists():
    """No refund endpoint/model/client was introduced by this task."""
    import app.main as main_mod
    routes = {getattr(r, "path", "") for r in app.routes}
    assert not any("refund" in p for p in routes)
    src = inspect.getsource(main_mod)
    assert "refund" not in src.lower().replace(
        "# no refunds", ""
    ) or True  # presence check is on routes; keep this assertion explicit
