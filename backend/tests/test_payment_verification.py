"""
Phase 4 Task 4 tests — server-side Razorpay payment verification.

Covers the mandated appointment tests (1-14), laboratory tests (15-29), and
cross-domain/security checks (30-36). All Razorpay API calls are mocked at
the payment-service boundary; signature fixtures are real HMACs computed
with a deterministic TEST-ONLY secret so the Task 1 helper runs for real.
No real Razorpay transaction is performed.
"""
import hashlib
import hmac
import inspect
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import HTTPException

from app.core.config import settings
from app.services.payment_service import PaymentService

TEST_KEY_ID = "rzp_test_unitkeyid123"
TEST_SECRET = "test_key_secret_for_unit_tests_only"

P1 = "111111111111111111111111"
P2 = "222222222222222222222222"
APT = "333333333333333333333333"
BOOK = "444444444444444444444444"
ORDER = "order_backend123"
PAY = "pay_backend456"


def _sig(order_id: str, payment_id: str, secret: str = TEST_SECRET) -> str:
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


VALID = {
    "razorpay_payment_id": PAY,
    "razorpay_order_id": ORDER,
    "razorpay_signature": _sig(ORDER, PAY),
}

# Razorpay payment dict as the real Payments API would return for our order.
GOOD_PAYMENT = {
    "id": PAY,
    "order_id": ORDER,
    "amount": 50000,
    "currency": "INR",
    "status": "captured",
}


@pytest.fixture(autouse=True)
def razorpay_test_config(monkeypatch):
    """Point the real Task 1 signature helper at a deterministic test secret."""
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", TEST_KEY_ID)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", TEST_SECRET)


def make_patient(pid):
    p = MagicMock()
    p.id = pid
    return p


def make_appointment(order_id=ORDER, payment_id=None, payment_status="pending",
                     billing_status="pending", status="pending_payment",
                     amount=500.0, patient_id=P1):
    import datetime as _dt
    a = MagicMock()
    a.id = APT
    a.patient_id = patient_id
    a.payment_order_id = order_id
    a.payment_id = payment_id
    a.payment_status = payment_status
    a.billing_status = billing_status
    a.status = status
    a.billing_amount = amount
    a.appointment_date = _dt.datetime(2026, 10, 1, 12, 0)
    return a


def make_booking(order_id=ORDER, payment_id=None, payment_status=None,
                 billing_status="pending", status="pending_payment",
                 amount=500.0, patient_id=P1):
    b = MagicMock()
    b.id = BOOK
    b.patient_id = patient_id
    b.payment_order_id = order_id
    b.payment_id = payment_id
    b.payment_status = payment_status
    b.billing_status = billing_status
    b.status = status
    b.billing_amount = amount
    return b


def paid_appt_doc():
    return {"_id": APT, "billing_amount": 500.0, "billing_status": "paid",
            "payment_status": "success", "status": "confirmed",
            "payment_id": PAY, "payment_order_id": ORDER}


def paid_booking_doc():
    return {"_id": BOOK, "billing_amount": 500.0, "billing_status": "paid",
            "payment_status": "success", "status": "confirmed",
            "payment_id": PAY, "payment_order_id": ORDER}


def _patch_domain(domain, obj, updated, notify):
    """Patch the full verification dependency set for one domain."""
    if domain == "appointment":
        get_repo = "app.services.payment_service.AppointmentRepository.get_by_id"
        claim = "app.services.payment_service.PaymentRepository.mark_appointment_paid"
    else:
        get_repo = "app.services.payment_service.LaboratoryBookingRepository.get_by_id"
        claim = "app.services.payment_service.PaymentRepository.mark_laboratory_paid"
    return [
        patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
              new=AsyncMock(return_value=make_patient(P1))),
        patch(get_repo, new=AsyncMock(return_value=obj)),
        patch(claim, new=claim_mock(updated)),
        patch("app.services.payment_service.PaymentService._fetch_payment_safe",
              new=AsyncMock(return_value=dict(GOOD_PAYMENT))),
        patch("app.services.payment_service.PaymentService._notify_payment_success", new=notify),
    ]


def claim_mock(updated):
    m = AsyncMock(return_value=updated)
    return m


class _Stack:
    """Enter a list of patches, expose (entered_values, notify_mock)."""

    def __init__(self, patches):
        self._patches = patches

    def __enter__(self):
        from contextlib import ExitStack
        self._exit = ExitStack()
        values = [self._exit.enter_context(p) for p in self._patches]
        # last patch is the notification mock
        return values, values[-1]

    def __exit__(self, *a):
        return self._exit.__exit__(*a)


def happy(domain="appointment", updated=None):
    notify = AsyncMock()
    updated = updated if updated is not None else (
        paid_appt_doc() if domain == "appointment" else paid_booking_doc()
    )
    obj = make_appointment() if domain == "appointment" else make_booking()
    patches = _patch_domain(domain, obj, updated, notify)
    return _Stack(patches), patches, notify


async def _run(domain, obj_id=None, **overrides):
    from app.schemas.payment import RazorpayVerifyRequest
    body = RazorpayVerifyRequest(**{**VALID, **overrides})
    fn = (PaymentService.verify_appointment_payment if domain == "appointment"
          else PaymentService.verify_laboratory_payment)
    return await fn("user-1", obj_id or (APT if domain == "appointment" else BOOK), body)


# ---------------------------------------------------------------------------
# APPOINTMENTS (tests 1-14)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_appointment_valid_verification_succeeds():
    """TEST 1: valid signature + correct order + correct payment verifies."""
    stack, patches, notify = happy("appointment")
    with stack:
        resp = await _run("appointment")
    assert resp.status == "verified"
    assert resp.payment_status == "success"
    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_appointment_invalid_signature_rejected():
    """TEST 2"""
    stack, _, _ = happy("appointment")
    with stack:
        with pytest.raises(HTTPException) as e:
            await _run("appointment", razorpay_signature="A" * 64)
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_appointment_tampered_payment_id_rejected():
    """TEST 3: self-consistent signature for a payment that is not ours —
    the Razorpay-side lookup must catch it."""
    stack, _, _ = happy("appointment")
    with stack as (values, _):
        # make the Razorpay fetch reject the unknown payment id
        values[3].side_effect = HTTPException(502, "Payment is being verified. Please try again shortly.")
        with pytest.raises(HTTPException) as e:
            await _run("appointment",
                       razorpay_payment_id="pay_evil1",
                       razorpay_signature=_sig(ORDER, "pay_evil1"))
    assert e.value.status_code in (400, 502)


@pytest.mark.asyncio
async def test_appointment_tampered_order_id_rejected():
    """TEST 4: submitted order id differs from the backend-stored binding."""
    stack, _, _ = happy("appointment")
    with stack:
        with pytest.raises(HTTPException) as e:
            await _run("appointment", razorpay_order_id="order_evil1")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_appointment_wrong_patient_rejected():
    """TEST 5: patient A cannot verify patient B's appointment."""
    appt = make_appointment(patient_id=P2)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        with pytest.raises(HTTPException) as e:
            await _run("appointment")
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_appointment_wrong_order_rejected():
    """TEST 6: valid-signature order that is not the stored binding."""
    appt = make_appointment(order_id="order_other999")
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        with pytest.raises(HTTPException) as e:
            await _run("appointment")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_appointment_wrong_amount_rejected():
    """TEST 7: Razorpay reports a different captured amount."""
    appt = make_appointment(amount=500.0)
    bad = {**GOOD_PAYMENT, "amount": 9999}
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(return_value=bad)):
        with pytest.raises(HTTPException) as e:
            await _run("appointment")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_appointment_wrong_currency_rejected():
    """TEST 8"""
    appt = make_appointment()
    bad = {**GOOD_PAYMENT, "currency": "USD"}
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(return_value=bad)):
        with pytest.raises(HTTPException) as e:
            await _run("appointment")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_appointment_invalid_payment_state_rejected():
    """TEST 9: Razorpay reports created/failed — not confirmable."""
    appt = make_appointment()
    bad = {**GOOD_PAYMENT, "status": "created"}
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(return_value=bad)):
        with pytest.raises(HTTPException) as e:
            await _run("appointment")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_appointment_razorpay_api_failure_safe():
    """TEST 10: Razorpay outage maps to a neutral retryable 502."""
    appt = make_appointment()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(side_effect=HTTPException(502, "Payment is being verified. Please try again shortly."))):
        with pytest.raises(HTTPException) as e:
            await _run("appointment")
    assert e.value.status_code == 502
    assert TEST_SECRET not in str(e.value.detail)


@pytest.mark.asyncio
async def test_appointment_persists_payment_id_and_transitions():
    """TESTS 11 + 12: the atomic transition receives the payment id and the
    appointment lands in its paid/confirmed state."""
    stack, patches, notify = happy("appointment")
    with stack as (values, _):
        claim = values[2]
        resp = await _run("appointment")
    claim.assert_awaited_once_with(APT, PAY, ORDER)
    assert resp.billing_status == "paid"
    assert resp.entity_status == "confirmed"
    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_appointment_repeated_same_verification_idempotent():
    """TEST 13: replaying the same payment is a safe idempotent success."""
    appt = make_appointment(payment_id=PAY, payment_status="success",
                            billing_status="paid", status="confirmed")
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        resp = await _run("appointment")
    assert resp.status == "verified"
    assert resp.message == "Payment already verified"


@pytest.mark.asyncio
async def test_appointment_different_payment_after_verification_rejected():
    """TEST 14: a second payment can never overwrite the first."""
    appt = make_appointment(payment_id="pay_first1", payment_status="success",
                            billing_status="paid", status="confirmed")
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):
        with pytest.raises(HTTPException) as e:
            await _run("appointment")
    assert e.value.status_code == 409


# ---------------------------------------------------------------------------
# LABORATORY (tests 15-29)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lab_valid_verification_succeeds():
    """TEST 15"""
    stack, _, notify = happy("laboratory")
    with stack:
        resp = await _run("laboratory")
    assert resp.status == "verified"
    assert resp.payment_status == "success"
    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_lab_invalid_signature_rejected():
    """TEST 16"""
    stack, _, _ = happy("laboratory")
    with stack:
        with pytest.raises(HTTPException) as e:
            await _run("laboratory", razorpay_signature="B" * 64)
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_lab_tampered_payment_id_rejected():
    """TEST 17"""
    stack, _, _ = happy("laboratory")
    with stack as (values, _):
        values[3].side_effect = HTTPException(502, "Payment is being verified. Please try again shortly.")
        with pytest.raises(HTTPException) as e:
            await _run("laboratory",
                       razorpay_payment_id="pay_evil2",
                       razorpay_signature=_sig(ORDER, "pay_evil2"))
    assert e.value.status_code in (400, 502)


@pytest.mark.asyncio
async def test_lab_tampered_order_id_rejected():
    """TEST 18"""
    stack, _, _ = happy("laboratory")
    with stack:
        with pytest.raises(HTTPException) as e:
            await _run("laboratory", razorpay_order_id="order_evil2")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_lab_wrong_patient_rejected():
    """TEST 19"""
    booking = make_booking(patient_id=P2)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)):
        with pytest.raises(HTTPException) as e:
            await _run("laboratory")
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_lab_wrong_order_rejected():
    """TEST 20"""
    booking = make_booking(order_id="order_other777")
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)):
        with pytest.raises(HTTPException) as e:
            await _run("laboratory")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_lab_wrong_amount_rejected():
    """TEST 21"""
    booking = make_booking(amount=500.0)
    bad = {**GOOD_PAYMENT, "amount": 1}
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(return_value=bad)):
        with pytest.raises(HTTPException) as e:
            await _run("laboratory")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_lab_wrong_currency_rejected():
    """TEST 22"""
    booking = make_booking()
    bad = {**GOOD_PAYMENT, "currency": "EUR"}
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(return_value=bad)):
        with pytest.raises(HTTPException) as e:
            await _run("laboratory")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_lab_invalid_payment_state_rejected():
    """TEST 23: a created payment state cannot confirm a booking.

    Task 5 note: Razorpay-reported FAILED payments no longer land here —
    they take the authoritative failure transition (see the Task 5 suite in
    test_payment_lifecycle.py). Only genuinely indeterminate states
    (created/pending) are rejected with the booking kept safely pending.
    """
    booking = make_booking()
    bad = {**GOOD_PAYMENT, "status": "created"}
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(return_value=bad)):
        with pytest.raises(HTTPException) as e:
            await _run("laboratory")
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_lab_razorpay_api_failure_safe():
    """TEST 24"""
    booking = make_booking()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(side_effect=HTTPException(502, "Payment is being verified. Please try again shortly."))):
        with pytest.raises(HTTPException) as e:
            await _run("laboratory")
    assert e.value.status_code == 502
    assert TEST_SECRET not in str(e.value.detail)


@pytest.mark.asyncio
async def test_lab_persists_payment_id_and_transitions():
    """TESTS 25 + 26: pending -> paid/confirmed with the payment id persisted."""
    stack, patches, notify = happy("laboratory")
    with stack as (values, _):
        claim = values[2]
        resp = await _run("laboratory")
    claim.assert_awaited_once_with(BOOK, PAY, ORDER)
    assert resp.billing_status == "paid"
    assert resp.entity_status == "confirmed"
    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_lab_repeated_same_verification_idempotent():
    """TEST 27"""
    booking = make_booking(payment_id=PAY, payment_status="success",
                           billing_status="paid", status="confirmed")
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)):
        resp = await _run("laboratory")
    assert resp.status == "verified"
    assert resp.message == "Payment already verified"


@pytest.mark.asyncio
async def test_lab_different_payment_after_verification_rejected():
    """TEST 28"""
    booking = make_booking(payment_id="pay_first2", payment_status="success",
                           billing_status="paid", status="confirmed")
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)):
        with pytest.raises(HTTPException) as e:
            await _run("laboratory")
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_lab_notification_exactly_once():
    """TEST 29: exactly one success notification for one verification.

    First call verifies and notifies. Second call sees the updated (paid)
    booking and takes the idempotent replay path — no second notification.
    """
    stack, _, notify = happy("laboratory")
    with stack:
        await _run("laboratory")
        notify.assert_awaited_once()

    # Replay: the database now holds the verified booking.
    paid = make_booking(payment_id=PAY, payment_status="success",
                        billing_status="paid", status="confirmed")
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=paid)):
        resp = await _run("laboratory")
    assert resp.message == "Payment already verified"
    notify.assert_awaited_once()  # still exactly once


# ---------------------------------------------------------------------------
# CROSS-DOMAIN / SECURITY (tests 30-36)
# ---------------------------------------------------------------------------

def test_frontend_cannot_override_authoritative_values():
    """TESTS 30-33: the verify schema and service signatures carry no
    client-controllable amount/currency/patient/payment-status fields."""
    from app.schemas.payment import RazorpayVerifyRequest
    fields = set(RazorpayVerifyRequest.model_fields.keys())
    assert fields == {"razorpay_payment_id", "razorpay_order_id",
                      "razorpay_signature"}
    for fn in (PaymentService.verify_appointment_payment,
               PaymentService.verify_laboratory_payment):
        params = inspect.signature(fn).parameters
        assert "amount" not in params
        assert "currency" not in params
        assert "patient_id" not in params
        assert "payment_status" not in params
        assert "billing_status" not in params


def test_frontend_cannot_override_order_binding():
    """TEST 7 (binding): the service derives order authority from the stored
    payment_order_id — the schema's razorpay_order_id is only ever compared,
    never persisted as authoritative state."""
    from app.schemas.payment import RazorpayVerifyRequest
    import app.services.payment_service as ps
    src = inspect.getsource(ps)
    assert 'payment_order_id": order_id' in src or "payment_order_id\": order_id" in inspect.getsource(
        __import__("app.repositories.payment_repository", fromlist=["PaymentRepository"])
    )


@pytest.mark.asyncio
async def test_secret_never_in_errors():
    """TEST 34: configuration failure yields a neutral 503 with no secret."""
    from app.core.razorpay_client import RazorpayConfigError
    appt = make_appointment()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.verify_payment_signature",
               side_effect=RazorpayConfigError("no config")):
        with pytest.raises(HTTPException) as e:
            await _run("appointment")
    assert e.value.status_code == 503
    assert TEST_SECRET not in str(e.value.detail)


@pytest.mark.asyncio
async def test_invalid_verification_never_changes_state():
    """TEST 35: every rejection path leaves the atomic transition uncalled."""
    cases = [
        {"razorpay_signature": "X" * 64},          # invalid signature
        {"razorpay_order_id": "order_evil"},       # wrong order
        {"razorpay_payment_id": "pay_x"},          # malformed payment id
    ]
    for override in cases:
        claim = AsyncMock()
        with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
                   new=AsyncMock(return_value=make_patient(P1))), \
             patch("app.services.payment_service.AppointmentRepository.get_by_id",
                   new=AsyncMock(return_value=make_appointment())), \
             patch("app.services.payment_service.PaymentRepository.mark_appointment_paid",
                   new=claim):
            with pytest.raises(HTTPException):
                await _run("appointment", **override)
        claim.assert_not_awaited()


def test_checkout_callback_alone_never_changes_state():
    """TEST 36: the verification service contains NO unguarded save() — the
    only write path is the guarded atomic transition, which requires
    signature + order + amount + currency + state to have passed."""
    import app.services.payment_service as ps
    src = inspect.getsource(ps)
    assert ".save()" not in src, "verification must use guarded atomic transitions only"


@pytest.mark.asyncio
async def test_wrong_order_with_valid_signature_cannot_confirm():
    """BINDING: a signature valid for a DIFFERENT order never confirms —
    stored payment_order_id is authoritative (tested at the stored-order
    gate before any Razorpay call)."""
    stack, patches, _ = happy("appointment")
    with stack as (values, _):
        fetch = values[3]
        with pytest.raises(HTTPException) as e:
            # signature genuinely valid for order_other999, appointment bound to ORDER
            await _run("appointment",
                       razorpay_order_id="order_other999",
                       razorpay_signature=_sig("order_other999", PAY))
    assert e.value.status_code == 400
    fetch.assert_not_awaited()  # rejected before any Razorpay traffic
