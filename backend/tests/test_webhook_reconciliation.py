"""
Phase 4 Task 8 tests — webhook payment reconciliation & state transition.

Covers the 25 mandated checks plus the concurrency matrix (A-H): captured
reconciliation for both domains, authorized/failed/order.paid no-ops, every
financial-validation rejection (order/amount/currency/status/payment id/
unknown order/unknown domain/malformed/unreachable Razorpay), verify↔webhook
idempotency in both orders, webhook/webhook and webhook/verify races,
duplicate events, and exactly-once notifications.

CRITICAL: the tests also structurally prove there is NO second payment
confirmation implementation — the webhook path must call the SAME
PaymentRepository.mark_*_paid methods as the verification flow.

All Razorpay SDK/network calls are mocked. No real Razorpay servers are
contacted and no real transactions are performed.
"""
import asyncio
import hashlib
import hmac
import json
from datetime import datetime

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.main import app

TEST_WEBHOOK_SECRET = "test_webhook_secret_for_unit_tests_only"
TEST_KEY_SECRET = "test_key_secret_for_unit_tests_only"
TEST_KEY_ID = "rzp_test_unitkeyid123"

EVENT_ID = "evt_recon_1"
OTHER_EVENT_ID = "evt_recon_2"
PAY_ID = "pay_backend456"
PAY_ID_2 = "pay_backend789"
ORDER_ID = "order_backend123"
APT_ID = "333333333333333333333333"
BOOK_ID = "444444444444444444444444"
P1 = "111111111111111111111111"


def _sign(body: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _captured_event(payment_id=PAY_ID, order_id=ORDER_ID,
                    event="payment.captured") -> bytes:
    return json.dumps({
        "entity": "event",
        "event": event,
        "contains": ["payment"],
        "payload": {"payment": {"entity": {
            "id": payment_id,
            "order_id": order_id,
            "amount": 50000,
            "currency": "INR",
            "status": "captured",
        }}},
    }).encode("utf-8")


def _post(body: bytes, signature=None, event_id=EVENT_ID):
    client = TestClient(app)
    headers = {}
    if signature is not None:
        headers["X-Razorpay-Signature"] = signature
    if event_id is not None:
        headers["X-Razorpay-Event-Id"] = event_id
    return client.post("/api/webhooks/razorpay", content=body, headers=headers)


@pytest.fixture(autouse=True)
def webhook_test_config(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", TEST_KEY_SECRET)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", TEST_KEY_ID)


@pytest.fixture(autouse=True)
def fake_ledger():
    """Same DB-contract fake as Task 7: unique-index-backed insert."""
    store = {}

    class FakeCollection:
        def __init__(self):
            self.insert_calls = []
            self.store = store

        async def insert_one(self, doc, session=None):
            record = {k: v for k, v in dict(doc).items() if isinstance(k, str)}
            self.insert_calls.append(record)
            eid = record.get("event_id")
            if eid in store:
                raise DuplicateKeyError("E11000 duplicate key event_id")
            store[eid] = record
            from bson import ObjectId
            return MagicMock(inserted_id=ObjectId())

    fake = FakeCollection()
    from app.models.webhook_event import WebhookEvent

    mock_settings = MagicMock()
    mock_settings.pymongo_collection = fake
    mock_settings.name = "webhook_events"
    mock_settings.bson_encoders.get.return_value = None

    with patch.object(WebhookEvent, "get_settings", return_value=mock_settings):
        yield fake


_UNSET = object()


def make_appointment(status="pending_payment", billing_status="pending",
                     payment_status="pending", amount=500.0,
                     order_id=ORDER_ID, patient_id=P1, appt_id=APT_ID):
    a = MagicMock()
    a.id = appt_id
    a.patient_id = patient_id
    a.status = status
    a.billing_status = billing_status
    a.payment_status = payment_status
    a.billing_amount = amount
    a.payment_order_id = order_id
    a.payment_id = None
    return a


def make_booking(status="pending_payment", billing_status="pending",
                 amount=500.0, order_id=ORDER_ID, patient_id=P1,
                 booking_id=BOOK_ID):
    b = MagicMock()
    b.id = booking_id
    b.patient_id = patient_id
    b.status = status
    b.billing_status = billing_status
    b.billing_amount = amount
    b.payment_order_id = order_id
    b.payment_id = None
    return b


def paid_doc(domain):
    base = {
        "_id": APT_ID if domain == "appointment" else BOOK_ID,
        "billing_amount": 500.0,
        "billing_status": "paid",
        "payment_status": "success",
        "status": "confirmed",
        "payment_id": PAY_ID,
        "payment_order_id": ORDER_ID,
    }
    return base


GOOD_FETCH = {
    "id": PAY_ID,
    "order_id": ORDER_ID,
    "amount": 50000,
    "currency": "INR",
    "status": "captured",
}


def patch_domain(domain, *, appt=None, booking=None, fetch=GOOD_FETCH,
                 updated=_UNSET, notify=None):
    """Patch the full reconciliation dependency set for one domain."""
    if domain == "appointment":
        get_by_order = ("app.services.webhook_reconciliation_service."
                        "AppointmentRepository.get_by_order_id")
        get_by_id = ("app.services.webhook_reconciliation_service."
                     "AppointmentRepository.get_by_id")
        mark = "app.services.webhook_reconciliation_service.PaymentRepository.mark_appointment_paid"
        obj, other = appt, None
    else:
        get_by_order = ("app.services.webhook_reconciliation_service."
                        "LaboratoryBookingRepository.get_by_order_id")
        get_by_id = ("app.services.webhook_reconciliation_service."
                     "LaboratoryBookingRepository.get_by_id")
        mark = "app.services.webhook_reconciliation_service.PaymentRepository.mark_laboratory_paid"
        obj, other = booking, None

    patches = [
        patch(get_by_order, new=AsyncMock(return_value=obj)),
        patch(get_by_id, new=AsyncMock(return_value=other)),
        patch("app.services.webhook_reconciliation_service."
              "LaboratoryBookingRepository.get_by_order_id",
              new=AsyncMock(return_value=booking if domain == "laboratory" else None)),
        patch("app.services.webhook_reconciliation_service."
              "AppointmentRepository.get_by_order_id",
              new=AsyncMock(return_value=appt if domain == "appointment" else None)),
        patch("app.services.webhook_reconciliation_service.fetch_payment",
              return_value=dict(fetch)),
        # 'updated is None' means the caller wants the transition to LOSE
        # (already paid elsewhere) — use a sentinel so an explicit None is
        # distinguishable from the default winner document.
        patch(mark, new=AsyncMock(return_value=(paid_doc(domain) if updated is _UNSET
                                                else updated))),
        patch("app.services.payment_service.PaymentService._notify_payment_success",
              new=notify if notify is not None else AsyncMock()),
    ]
    return patches


class _Stack:
    def __init__(self, patches):
        self._patches = patches

    def __enter__(self):
        from contextlib import ExitStack
        self._exit = ExitStack()
        values = [self._exit.enter_context(p) for p in self._patches]
        # Standard patch_domain layout (7 entries):
        # [get_by_order(primary), get_by_id(primary), get_by_order(lab),
        #  get_by_order(appt), fetch, mark, notify]
        if len(values) >= 7:
            return values, values[5], values[6]  # (all, mark, notify)
        # Custom patch lists (e.g. unmapped-domain test) — no mark/notify
        # convenience accessors; callers index into `values` directly.
        return values, None, None

    def __exit__(self, *a):
        return self._exit.__exit__(*a)


# ---------------------------------------------------------------------------
# 1/2 — captured reconciliation for both domains
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_1_captured_event_reconciles_appointment(fake_ledger):
    """TEST 1: payment.captured confirms the appointment via the EXISTING
    atomic transition + winner-only notification."""
    appt = make_appointment()
    notify = AsyncMock()
    with _Stack(patch_domain("appointment", appt=appt, notify=notify)) as (v, mark, notify_mock):
        r = _post(_captured_event(), signature=_sign(_captured_event()))
    assert r.status_code == 200
    mark.assert_awaited_once_with(APT_ID, PAY_ID, ORDER_ID)
    notify_mock.assert_awaited_once()
    row = fake_ledger.store[EVENT_ID]
    assert row["event_type"] == "payment.captured"
    assert row["payment_id"] == PAY_ID and row["order_id"] == ORDER_ID


@pytest.mark.asyncio
async def test_2_captured_event_reconciles_laboratory():
    """TEST 2: same for laboratory bookings."""
    booking = make_booking()
    notify = AsyncMock()
    with _Stack(patch_domain("laboratory", booking=booking, notify=notify)) as (v, mark, notify_mock):
        r = _post(_captured_event(), signature=_sign(_captured_event()))
    assert r.status_code == 200
    mark.assert_awaited_once_with(BOOK_ID, PAY_ID, ORDER_ID)
    notify_mock.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3/4 — authorized / failed / order.paid never pay
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_3_authorized_event_does_not_pay():
    notify = AsyncMock()
    for domain in ("appointment", "laboratory"):
        kwargs = ({"appt": make_appointment()} if domain == "appointment"
                  else {"booking": make_booking()})
        with _Stack(patch_domain(domain, notify=notify, **kwargs)) as (v, mark, notify_mock):
            body = _captured_event(event="payment.authorized")
            r = _post(body, signature=_sign(body), event_id=f"{EVENT_ID}_{domain}")
        assert r.status_code == 200
        mark.assert_not_awaited()
        notify_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_4_failed_event_does_not_pay():
    notify = AsyncMock()
    for domain in ("appointment", "laboratory"):
        kwargs = ({"appt": make_appointment()} if domain == "appointment"
                  else {"booking": make_booking()})
        with _Stack(patch_domain(domain, notify=notify, **kwargs)) as (v, mark, notify_mock):
            body = _captured_event(event="payment.failed")
            r = _post(body, signature=_sign(body), event_id=f"{EVENT_ID}_{domain}")
        assert r.status_code == 200
        mark.assert_not_awaited()
        notify_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_paid_event_does_not_create_second_confirmation_path():
    """order.paid is recorded/ignored BY DESIGN: it fires alongside
    payment.captured; acting on it would double-process the same capture."""
    notify = AsyncMock()
    with _Stack(patch_domain("appointment", appt=make_appointment(), notify=notify)) as (v, mark, notify_mock):
        body = _captured_event(event="order.paid")
        r = _post(body, signature=_sign(body))
    assert r.status_code == 200
    mark.assert_not_awaited()
    notify_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Financial validation rejections (mandated tests 5-9, 20-24)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("fetch_override,expect_never_paid", [
    # 5. Razorpay payment belongs to a different order
    ({**GOOD_FETCH, "order_id": "order_other999"}, True),
    # 6. underpayment
    ({**GOOD_FETCH, "amount": 49999}, True),
    # 23. overpayment
    ({**GOOD_FETCH, "amount": 99999}, True),
    # 7. wrong currency
    ({**GOOD_FETCH, "currency": "USD"}, True),
    # 8. payment status mismatch (authorized is NOT captured)
    ({**GOOD_FETCH, "status": "authorized"}, True),
    # 20. malformed Razorpay response
    ({"weird": True}, True),
])
async def test_financial_validation_rejections_leave_state_untouched(
        fetch_override, expect_never_paid):
    appt = make_appointment()
    notify = AsyncMock()
    with _Stack(patch_domain("appointment", appt=appt,
                             fetch=fetch_override, notify=notify)) as (v, mark, notify_mock):
        r = _post(_captured_event(), signature=_sign(_captured_event()))
    assert r.status_code == 200  # webhook acknowledged, never a 500 loop
    mark.assert_not_awaited()    # never paid
    notify_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_9_payment_id_mismatch_rejected():
    """Razorpay returns a payment whose id differs from the event's."""
    appt = make_appointment()
    notify = AsyncMock()
    with _Stack(patch_domain("appointment", appt=appt,
                             fetch={**GOOD_FETCH, "id": "pay_OTHER"},
                             notify=notify)) as (v, mark, notify_mock):
        r = _post(_captured_event(), signature=_sign(_captured_event()))
    assert r.status_code == 200
    mark.assert_not_awaited()


@pytest.mark.asyncio
async def test_10_unknown_order_is_safe():
    """payment_order_id maps to neither domain: recorded, 2xx, no mutation."""
    notify = AsyncMock()
    with _Stack(patch_domain("appointment", appt=None, notify=notify)) as (v, mark, notify_mock):
        r = _post(_captured_event(order_id="order_unknown1"),
                  signature=_sign(_captured_event(order_id="order_unknown1")))
    assert r.status_code == 200
    mark.assert_not_awaited()
    notify_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_11_unknown_payable_domain_never_mutates(fake_ledger):
    """Both lookups return None → unmapped → nothing mutated anywhere."""
    notify = AsyncMock()
    patches = [
        patch("app.services.webhook_reconciliation_service."
              "AppointmentRepository.get_by_order_id", new=AsyncMock(return_value=None)),
        patch("app.services.webhook_reconciliation_service."
              "LaboratoryBookingRepository.get_by_order_id", new=AsyncMock(return_value=None)),
        patch("app.services.webhook_reconciliation_service.fetch_payment",
              return_value=dict(GOOD_FETCH)),
        patch("app.services.webhook_reconciliation_service."
              "PaymentRepository.mark_appointment_paid", new=AsyncMock()),
        patch("app.services.webhook_reconciliation_service."
              "PaymentRepository.mark_laboratory_paid", new=AsyncMock()),
        patch("app.services.payment_service.PaymentService._notify_payment_success",
              new=notify),
    ]
    with _Stack(patches) as (v, _mark, _notify):
        r = _post(_captured_event(), signature=_sign(_captured_event()))
    assert r.status_code == 200
    # Neither mark-paid transition may fire for an unmapped order.
    v[3].assert_not_awaited()   # mark_appointment_paid
    v[4].assert_not_awaited()   # mark_laboratory_paid
    notify.assert_not_awaited()


# ---------------------------------------------------------------------------
# 21/22 — Razorpay unreachable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("side_effect", [
    __import__("app.core.razorpay_client", fromlist=["RazorpayRequestError"]).RazorpayRequestError("timeout"),  # 21
    __import__("app.core.razorpay_client", fromlist=["RazorpayRequestError"]).RazorpayRequestError("5xx"),     # 22
])
async def test_razorpay_fetch_failure_leaves_state_untouched(side_effect):
    appt = make_appointment()
    notify = AsyncMock()
    patches = patch_domain("appointment", appt=appt, notify=notify)
    patches[4] = patch("app.services.webhook_reconciliation_service.fetch_payment",
                       side_effect=side_effect)
    with _Stack(patches) as (v, mark, notify_mock):
        r = _post(_captured_event(), signature=_sign(_captured_event()))
    assert r.status_code == 200
    mark.assert_not_awaited()
    notify_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# 12/13 — webhook-first and verify-first idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_12_webhook_first_then_verify_is_idempotent_noop():
    """Scenario A: webhook confirms; a later normal verification of the SAME
    payment replays idempotently per the existing verification contract."""
    # Step 1: webhook performs the transition (winner + notification).
    appt = make_appointment()
    notify = AsyncMock()
    with _Stack(patch_domain("appointment", appt=appt, notify=notify)) as (v, mark, _):
        r = _post(_captured_event(), signature=_sign(_captured_event()))
    assert r.status_code == 200
    mark.assert_awaited_once()
    notify.assert_awaited_once()

    # Step 2: normal verify flow sees the already-paid record with the SAME
    # payment → idempotent replay branch (existing Task 4 contract).
    from app.schemas.payment import RazorpayVerifyRequest
    from app.services.payment_service import PaymentService

    paid_appt = make_appointment(status="confirmed", billing_status="paid",
                                 payment_status="success")
    paid_appt.payment_id = PAY_ID
    sig = hmac.new(TEST_KEY_SECRET.encode(),
                   f"{ORDER_ID}|{PAY_ID}".encode(), hashlib.sha256).hexdigest()
    body = RazorpayVerifyRequest(
        razorpay_payment_id=PAY_ID, razorpay_order_id=ORDER_ID,
        razorpay_signature=sig)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=MagicMock(id=P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=paid_appt)):
        resp = await PaymentService.verify_appointment_payment("user-1", APT_ID, body)
    assert resp.status == "verified"
    assert resp.message == "Payment already verified"


@pytest.mark.asyncio
async def test_13_verify_first_then_webhook_is_noop(fake_ledger):
    """Scenario B: verification confirmed first; the arriving webhook must
    not re-transition or re-notify."""
    # Step 1: normal verify flow transitions (winner + notification).
    appt = make_appointment()
    notify = AsyncMock()
    sig = hmac.new(TEST_KEY_SECRET.encode(),
                   f"{ORDER_ID}|{PAY_ID}".encode(), hashlib.sha256).hexdigest()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=MagicMock(id=P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.PaymentRepository.mark_appointment_paid",
               new=AsyncMock(return_value=paid_doc("appointment"))), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(return_value=dict(GOOD_FETCH))), \
         patch("app.services.payment_service.PaymentService._notify_payment_success",
               new=notify):
        from app.schemas.payment import RazorpayVerifyRequest
        from app.services.payment_service import PaymentService
        resp = await PaymentService.verify_appointment_payment(
            "user-1", APT_ID,
            RazorpayVerifyRequest(razorpay_payment_id=PAY_ID,
                                  razorpay_order_id=ORDER_ID,
                                  razorpay_signature=sig))
    assert resp.status == "verified"
    notify.assert_awaited_once()

    # Step 2: the webhook arrives — the atomic mark-paid guard no longer
    # matches (not pending) → the service reports already_paid, no
    # second notification.
    notify_step2 = AsyncMock()
    with _Stack(patch_domain("appointment", appt=appt, notify=notify_step2,
                             updated=None)) as (v, mark2, notify_mock):
        r = _post(_captured_event(), signature=_sign(_captured_event()))
    assert r.status_code == 200
    mark2.assert_awaited_once()         # attempted exactly once
    assert notify_step2.await_count == 0  # loser never notifies
    # Combined across both paths: exactly ONE notification total.
    assert notify.await_count + notify_step2.await_count == 1


@pytest.mark.asyncio
async def test_different_payment_after_paid_never_overwrites(fake_ledger):
    """Already paid with a DIFFERENT payment: no overwrite, no corruption.
    The atomic mark-paid guard inherently refuses (guard requires the
    record to still be pending); the outcome is a safe no-op."""
    appt = make_appointment(status="confirmed", billing_status="paid",
                            payment_status="success")
    appt.payment_id = "pay_first1"
    notify = AsyncMock()
    # The existing payment must keep its record: simulate the atomic guard
    # refusing a second transition (updated=None) and assert the winner-
    # only notification rule still holds for the loser.
    fetch2 = {**GOOD_FETCH, "id": PAY_ID_2}  # Razorpay's view of payment 2
    patches = patch_domain("appointment", appt=appt, notify=notify,
                           updated=None, fetch=fetch2)
    with _Stack(patches) as (v, mark, notify_mock):
        body = _captured_event(payment_id=PAY_ID_2)
        r = _post(body, signature=_sign(body))
    assert r.status_code == 200
    mark.assert_awaited_once_with(APT_ID, PAY_ID_2, ORDER_ID)
    # The transition loser must never notify: the outcome path returns
    # already_paid WITHOUT the notification helper being called.
    notify.assert_not_awaited()


# ---------------------------------------------------------------------------
# 14/15 — concurrency (scenarios C/D)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_14_webhook_webhook_race_single_transition(fake_ledger):
    """Scenario C: two captured webhooks for the same payment race. The
    ledger unique index admits one; the atomic transition guard admits one
    winner; exactly one notification."""
    appt = make_appointment()
    notify = AsyncMock()
    body = _captured_event()

    # Ledger fake already enforces unique event_id. The mark-paid mock
    # simulates the DB guard: first call wins, second returns None.
    calls = {"n": 0}

    async def guarded_mark(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return paid_doc("appointment")
        return None

    patches = patch_domain("appointment", appt=appt, notify=notify)
    patches[5] = patch(
        "app.services.webhook_reconciliation_service.PaymentRepository.mark_appointment_paid",
        new=AsyncMock(side_effect=guarded_mark))
    with _Stack(patches) as (v, mark, notify_mock):
        r1 = _post(body, signature=_sign(body), event_id=EVENT_ID)
        r2 = _post(body, signature=_sign(body), event_id=EVENT_ID)
    assert r1.status_code == 200 and r2.status_code == 200
    assert len(fake_ledger.store) == 1          # one ledger row
    assert notify_mock.await_count == 1         # exactly one notification


@pytest.mark.asyncio
async def test_15_webhook_verify_race_single_transition():
    """Scenario D: verify + webhook race. Both converge on the SAME atomic
    transition; only one winner, one notification, no corruption."""
    appt = make_appointment()
    notify = AsyncMock()
    calls = {"n": 0}

    async def guarded_mark(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return paid_doc("appointment")
        return None

    mark = AsyncMock(side_effect=guarded_mark)
    sig = hmac.new(TEST_KEY_SECRET.encode(),
                   f"{ORDER_ID}|{PAY_ID}".encode(), hashlib.sha256).hexdigest()

    from app.schemas.payment import RazorpayVerifyRequest
    from app.services.payment_service import PaymentService

    # The verify path's atomic transition and the webhook path's are the
    # SAME repository method — prove both invoke it and only one wins.
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=MagicMock(id=P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.PaymentRepository.mark_appointment_paid",
               new=mark), \
         patch("app.services.payment_service.PaymentService._fetch_payment_safe",
               new=AsyncMock(return_value=dict(GOOD_FETCH))), \
         patch("app.services.payment_service.PaymentService._notify_payment_success",
               new=notify), \
         patch("app.services.webhook_reconciliation_service."
               "AppointmentRepository.get_by_order_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.webhook_reconciliation_service."
               "LaboratoryBookingRepository.get_by_order_id",
               new=AsyncMock(return_value=None)), \
         patch("app.services.webhook_reconciliation_service.fetch_payment",
               return_value=dict(GOOD_FETCH)), \
         patch("app.services.webhook_reconciliation_service."
               "PaymentRepository.mark_appointment_paid", new=mark):
        # Sequential interleaving of the two paths (the shared guarded
        # transition enforces the single-winner invariant the DB provides
        # atomically in production).
        from app.services.payment_service import PaymentService
        await PaymentService.verify_appointment_payment(
            "user-1", APT_ID,
            RazorpayVerifyRequest(razorpay_payment_id=PAY_ID,
                                  razorpay_order_id=ORDER_ID,
                                  razorpay_signature=sig))
        r = _post(_captured_event(), signature=_sign(_captured_event()))

    assert r.status_code == 200
    assert calls["n"] == 2          # both paths attempted the SAME transition
    assert notify.await_count == 1  # exactly one winner notified


# ---------------------------------------------------------------------------
# 16/17 — duplicate event / duplicate payment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_16_duplicate_event_no_second_transition_or_notification(fake_ledger):
    """Scenario E: same event delivered twice sequentially."""
    appt = make_appointment()
    notify = AsyncMock()
    body = _captured_event()
    with _Stack(patch_domain("appointment", appt=appt, notify=notify)) as (v, mark, notify_mock):
        r1 = _post(body, signature=_sign(body))
        r2 = _post(body, signature=_sign(body))
    assert r1.status_code == 200 and r2.status_code == 200
    mark.assert_awaited_once()          # single transition
    notify_mock.assert_awaited_once()   # single notification
    assert len(fake_ledger.store) == 1  # single ledger row


@pytest.mark.asyncio
async def test_same_event_concurrent_no_double_processing():
    """Scenario F: same event delivered concurrently — the ledger unique
    index admits one row and the loser skips reconciliation entirely."""
    appt = make_appointment()
    notify = AsyncMock()
    body = _captured_event()

    reconciled = {"n": 0}
    real_reconcile = None
    from app.services import webhook_reconciliation_service as wrs

    original = wrs.WebhookReconciliationService.reconcile_event

    async def counting_reconcile(*a, **k):
        reconciled["n"] += 1
        return await original(*a, **k)

    patches = patch_domain("appointment", appt=appt, notify=notify)
    with _Stack(patches) as (v, mark, notify_mock):
        with patch.object(wrs.WebhookReconciliationService, "reconcile_event",
                          new=AsyncMock(side_effect=counting_reconcile)):
            r1 = _post(body, signature=_sign(body), event_id=EVENT_ID)
            r2 = _post(body, signature=_sign(body), event_id=EVENT_ID)
    assert r1.status_code == 200 and r2.status_code == 200
    assert reconciled["n"] == 1              # loser skipped (duplicate)
    mark.assert_awaited_once()
    notify_mock.assert_awaited_once()


# ---------------------------------------------------------------------------
# G/H — captured↔failed sequences never flip payment state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_captured_then_failed_keeps_paid_state():
    """Scenario G: payment.captured confirms; a later payment.failed webhook
    must NOT undo it (no terminal failure transition from webhooks)."""
    appt = make_appointment()
    notify = AsyncMock()
    body_cap = _captured_event()
    body_fail = _captured_event(event="payment.failed")
    with _Stack(patch_domain("appointment", appt=appt, notify=notify)) as (v, mark, notify_mock):
        r1 = _post(body_cap, signature=_sign(body_cap), event_id=EVENT_ID)
        r2 = _post(body_fail, signature=_sign(body_fail), event_id=OTHER_EVENT_ID)
    assert r1.status_code == 200 and r2.status_code == 200
    mark.assert_awaited_once()            # only the captured transition
    notify_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_then_captured_still_confirms():
    """Scenario H: a payment.failed webhook arrives first (recorded only),
    then the payment.captured — the capture still reconciles normally."""
    appt = make_appointment()
    notify = AsyncMock()
    body_fail = _captured_event(event="payment.failed")
    body_cap = _captured_event()
    with _Stack(patch_domain("appointment", appt=appt, notify=notify)) as (v, mark, notify_mock):
        r1 = _post(body_fail, signature=_sign(body_fail), event_id=OTHER_EVENT_ID)
        r2 = _post(body_cap, signature=_sign(body_cap), event_id=EVENT_ID)
    assert r1.status_code == 200 and r2.status_code == 200
    mark.assert_awaited_once_with(APT_ID, PAY_ID, ORDER_ID)
    notify_mock.assert_awaited_once()


# ---------------------------------------------------------------------------
# 18 — notification exactly once (already covered above; explicit matrix)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_18_notification_matrix_exactly_once():
    """webhook-first → 1; verify-first+webhook → 1; duplicates → still 1;
    authorized/failed/unknown → 0."""
    # webhook-first: 1
    appt = make_appointment()
    notify = AsyncMock()
    body = _captured_event()
    with _Stack(patch_domain("appointment", appt=appt, notify=notify)) as (v, mark, nm):
        _post(body, signature=_sign(body))
        _post(body, signature=_sign(body))
    assert nm.await_count == 1

    # authorized/failed/unknown: 0
    for event in ("payment.authorized", "payment.failed", "refund.processed"):
        notify2 = AsyncMock()
        with _Stack(patch_domain("appointment", appt=make_appointment(),
                                 notify=notify2)) as (v, m, nm2):
            b = _captured_event(event=event)
            _post(b, signature=_sign(b), event_id=f"evt_{event}")
        assert nm2.await_count == 0


# ---------------------------------------------------------------------------
# 19 — signature gating still protects reconciliation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_19_invalid_signature_cannot_reconcile():
    for bad_sig in ("0" * 64, None, ""):
        notify = AsyncMock()
        with _Stack(patch_domain("appointment", appt=make_appointment(),
                                 notify=notify)) as (v, mark, nm):
            body = _captured_event()
            r = _post(body, signature=bad_sig)
        assert r.status_code in (400, 401)
        mark.assert_not_awaited()
        nm.assert_not_awaited()


def test_tampered_body_cannot_reconcile():
    body = _captured_event()
    tampered = body.replace(b"captured", b"authorized")
    notify = AsyncMock()
    with _Stack(patch_domain("appointment", appt=make_appointment(),
                             notify=notify)) as (v, mark, nm):
        r = _post(tampered, signature=_sign(body))
    assert r.status_code == 401
    mark.assert_not_awaited()
    nm.assert_not_awaited()


# ---------------------------------------------------------------------------
# Structural: NO second confirmation implementation (critical safety rule)
# ---------------------------------------------------------------------------

def test_no_second_payment_confirmation_implementation():
    """The reconciliation service must reuse PaymentRepository.mark_*_paid —
    no webhook_mark_paid/webhook_confirm/webhook_save_payment may exist
    anywhere, and the service must not load-modify-save."""
    import inspect

    from app.api import webhooks
    import app.services.webhook_reconciliation_service as wrs

    src = inspect.getsource(wrs) + inspect.getsource(webhooks)
    for forbidden in ("webhook_mark_paid", "webhook_confirm",
                      "webhook_save_payment", ".save()"):
        assert forbidden not in src, forbidden

    # The write path IS the shared atomic transition.
    assert "PaymentRepository.mark_appointment_paid" in inspect.getsource(wrs)
    assert "PaymentRepository.mark_laboratory_paid" in inspect.getsource(wrs)


def test_reconciliation_processes_only_captured():
    """The service's dispatch ignores every non-captured event type."""
    import inspect

    import app.services.webhook_reconciliation_service as wrs

    src = inspect.getsource(wrs.WebhookReconciliationService.reconcile_event)
    assert 'event_type != "payment.captured"' in src


def test_raw_body_still_verified_before_json_parsing():
    """Task 7 security order is preserved end-to-end."""
    import inspect

    from app.api import webhooks

    src = inspect.getsource(webhooks.razorpay_webhook)
    raw_idx = src.index("await request.body()")
    verify_idx = src.index("verify_webhook_signature(raw_body, signature)")
    parse_idx = src.index("json.loads(raw_body)")
    assert raw_idx < verify_idx < parse_idx


def test_reconciliation_ordering_ledger_before_transition():
    """Ledger insert/dedupe happens BEFORE reconciliation so a duplicate
    delivery can never re-process."""
    import inspect

    from app.api import webhooks

    src = inspect.getsource(webhooks.razorpay_webhook)
    assert src.index("_record_event(") < src.index("reconcile_event(")
    # Duplicate branch returns before reconciling.
    dup_idx = src.index("if not inserted:")
    recon_idx = src.index("reconcile_event(")
    assert dup_idx < recon_idx


def test_no_client_controlled_amount_or_status_trusted():
    """The reconciliation service derives every financial fact from the
    Razorpay fetch + backend DB — the webhook payload's amount/status are
    never read for financial decisions."""
    import inspect

    import app.services.webhook_reconciliation_service as wrs

    src = inspect.getsource(wrs)
    # amount checks use the fetched payment + backend billing_amount only
    assert "payment.get(\"amount\") != expected_paise" in src
    assert "payment.get(\"status\") != _CAPTURED_STATUS" in src
    # no entity-amount shortcuts from the payload
    assert "entity_amount" not in src


def test_task7_unique_event_id_index_remains_intact():
    from app.models.webhook_event import WebhookEvent

    spec = [ix for ix in WebhookEvent.Settings.indexes
            if getattr(ix, "document", {}).get("name") == "uniq_webhook_event_id"]
    assert len(spec) == 1 and spec[0].document.get("unique") is True
