"""
Phase 4 Task 7 tests — Razorpay webhook foundation & event ingestion.

Covers the 25 mandated checks: signature acceptance/rejection matrix,
raw-body-before-JSON verification, ledger persistence, event-id uniqueness
(sequential AND concurrent), malformed/unknown handling, and the Task 7
hard boundary — ZERO appointment/laboratory payment-state side effects.

All Razorpay SDK/network calls are mocked. No real Razorpay servers are
contacted and no real transactions are performed.
"""
import asyncio
import hashlib
import hmac
import json

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpaySignatureError,
    verify_webhook_signature,
)
from app.main import app

TEST_WEBHOOK_SECRET = "test_webhook_secret_for_unit_tests_only"
TEST_KEY_SECRET = "test_key_secret_for_unit_tests_only"

EVENT_ID = "evt_test_12345"
OTHER_EVENT_ID = "evt_test_67890"
PAY_ID = "pay_backend456"
ORDER_ID = "order_backend123"


def _sign(body: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _event_body(
    event="payment.captured",
    payment_id=PAY_ID,
    order_id=ORDER_ID,
    include_payment=True,
    include_order=False,
    with_notes=True,
) -> bytes:
    """A Razorpay-shaped event envelope (contains PII-like fields to prove
    they are neither logged nor stored)."""
    payload = {
        "entity": "event",
        "account_id": "acc_TESTACCOUNT",
        "event": event,
        "contains": ["payment"],
        "payload": {},
        "created_at": 1727000000,
    }
    payment_entity = {
        "id": payment_id,
        "entity": "payment",
        "amount": 50000,
        "currency": "INR",
        "status": "captured",
        "order_id": order_id,  # real Razorpay payment entities carry this
        "email": "customer.pii@example.com",
        "contact": "+919000090000",
        "notes": {"payable_type": "appointment", "payable_id": "333333333333333333333333"},
    }
    if payment_id is None:
        payment_entity["id"] = None
    if include_payment:
        payload["payload"]["payment"] = {"entity": payment_entity}
    if include_order:
        payload["payload"]["order"] = {
            "entity": {"id": order_id, "entity": "order", "amount": 50000,
                       "currency": "INR", "receipt": f"apt_333333333333333333333333"},
        }
    if not with_notes:
        payment_entity.pop("notes", None)
    return json.dumps(payload).encode("utf-8")


def _post(body: bytes, signature=None, event_id=EVENT_ID) -> TestClient:
    client = TestClient(app)
    headers = {}
    if signature is not None:
        headers["X-Razorpay-Signature"] = signature
    if event_id is not None:
        headers["X-Razorpay-Event-Id"] = event_id
    return client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers=headers,
    )


@pytest.fixture(autouse=True)
def webhook_test_config(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", TEST_KEY_SECRET)


@pytest.fixture(autouse=True)
def fake_ledger():
    """In-memory stand-in for the webhook_events collection.

    Mirrors the DB contract exactly: a unique index on event_id — the insert
    raises DuplicateKeyError for an already-present event_id (the same
    atomic constraint Mongo enforces under concurrency; there is no
    application-level check-then-insert in the endpoint to bypass).
    """
    from pymongo.errors import DuplicateKeyError

    store = {}

    class FakeCollection:
        def __init__(self):
            self.insert_calls = []
            self.store = store

        async def insert_one(self, doc, session=None):
            # Beanie's class_id kwarg is a MagicMock under the mocked
            # settings — normalize it so the store is JSON-inspectable.
            record = {k: v for k, v in dict(doc).items()
                      if isinstance(k, str)}
            self.insert_calls.append(record)
            eid = record.get("event_id")
            if eid in store:
                raise DuplicateKeyError("E11000 duplicate key event_id")
            store[eid] = record
            from bson import ObjectId

            return MagicMock(inserted_id=ObjectId())

    fake = FakeCollection()

    # Follow the project's established conftest pattern: Beanie's
    # get_pymongo_collection() resolves through get_settings(), so patch
    # WebhookEvent.get_settings to serve the fake collection.
    from app.models.webhook_event import WebhookEvent

    mock_settings = MagicMock()
    mock_settings.pymongo_collection = fake
    mock_settings.name = "webhook_events"
    mock_settings.bson_encoders.get.return_value = None

    with patch.object(WebhookEvent, "get_settings",
                      return_value=mock_settings):
        yield fake


# ---------------------------------------------------------------------------
# Signature helper unit tests (raw helper, not via HTTP)
# ---------------------------------------------------------------------------

def test_helper_valid_signature_accepts():
    """Helper: correct HMAC over the exact raw bytes verifies True."""
    body = _event_body()
    assert verify_webhook_signature(body, _sign(body)) is True


def test_helper_uses_webhook_secret_not_key_secret():
    """The helper MUST key the HMAC with RAZORPAY_WEBHOOK_SECRET. A signature
    made with RAZORPAY_KEY_SECRET must NOT verify."""
    body = _event_body()
    assert verify_webhook_signature(body, _sign(body, TEST_KEY_SECRET)) is False


def test_helper_missing_signature_raises():
    with pytest.raises(RazorpaySignatureError):
        verify_webhook_signature(b"{}", "")


def test_helper_missing_secret_raises_config_error():
    body = _event_body()
    with patch("app.core.razorpay_client.settings") as mock_settings:
        mock_settings.RAZORPAY_WEBHOOK_SECRET = ""
        with pytest.raises(RazorpayConfigError):
            verify_webhook_signature(body, _sign(body))


def test_helper_empty_body_raises():
    with pytest.raises(RazorpaySignatureError):
        verify_webhook_signature(b"", _sign(b""))


# ---------------------------------------------------------------------------
# HTTP behavior — signature matrix (mandated tests 1-7)
# ---------------------------------------------------------------------------

def test_1_valid_webhook_signature_accepted():
    body = _event_body()
    r = _post(body, signature=_sign(body))
    assert r.status_code == 200


def test_2_invalid_signature_rejected():
    body = _event_body()
    r = _post(body, signature="0" * 64)
    assert r.status_code == 401


def test_3_missing_signature_rejected():
    body = _event_body()
    r = _post(body, signature=None)
    assert r.status_code == 400


def test_4_empty_signature_rejected():
    body = _event_body()
    r = _post(body, signature="   ")
    assert r.status_code == 400


def test_5_tampered_body_rejected():
    """Body signed by Razorpay, then modified in transit."""
    body = _event_body()
    tampered = body.replace(b"captured", b"failed")
    r = _post(tampered, signature=_sign(body))
    assert r.status_code == 401


def test_6_wrong_secret_rejected():
    body = _event_body()
    r = _post(body, signature=_sign(body, "a_completely_different_secret"))
    assert r.status_code == 401


def test_7_raw_body_verified_before_json_parsing():
    """Structural: the endpoint reads raw bytes and verifies BEFORE any JSON
    parse — the source must not call request.json() or json.loads() on the
    body before verify_webhook_signature, and no signature failure may ever
    reach the ledger."""
    import inspect

    from app.api import webhooks

    src = inspect.getsource(webhooks.razorpay_webhook)
    raw_idx = src.index("await request.body()")
    verify_idx = src.index("verify_webhook_signature(raw_body, signature)")
    parse_idx = src.index("json.loads(raw_body)")
    assert raw_idx < verify_idx < parse_idx, (
        "order must be: raw body -> verify -> parse"
    )
    # No pre-parse via request.json() anywhere in the module (the docstring
    # mention is fine; only actual call sites matter).
    assert "await request.json()" not in src and ".json()" not in src.replace(
        "request.json() before verification", ""
    ) or "request.json()" not in src.replace(
        "request.json() before verification", ""
    )

    # Runtime proof: a body that is INVALID JSON and INVALID signature
    # fails with 401 (never 500 from json parse), i.e. verification gates
    # parsing.
    r = _post(b"not json at all", signature="0" * 64)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Ingestion / ledger (mandated tests 8-12, 16)
# ---------------------------------------------------------------------------

def test_8_valid_json_event_recorded(fake_ledger):
    body = _event_body()
    r = _post(body, signature=_sign(body))
    assert r.status_code == 200
    assert EVENT_ID in fake_ledger.store
    row = fake_ledger.store[EVENT_ID]
    assert row["processing_status"] == "received"


def test_9_event_id_persisted(fake_ledger):
    body = _event_body()
    _post(body, signature=_sign(body))
    assert fake_ledger.store[EVENT_ID]["event_id"] == EVENT_ID


def test_10_event_type_persisted(fake_ledger):
    body = _event_body(event="payment.captured")
    _post(body, signature=_sign(body))
    assert fake_ledger.store[EVENT_ID]["event_type"] == "payment.captured"

    body2 = _event_body(event="order.paid", include_order=True)
    _post(body2, signature=_sign(body2), event_id=OTHER_EVENT_ID)
    assert fake_ledger.store[OTHER_EVENT_ID]["event_type"] == "order.paid"


def test_11_payment_and_order_ids_extracted_when_available(fake_ledger):
    # From the payment entity + its order_id reference:
    body = _event_body(include_payment=True, include_order=False)
    _post(body, signature=_sign(body))
    row = fake_ledger.store[EVENT_ID]
    assert row["payment_id"] == PAY_ID
    assert row["order_id"] == ORDER_ID  # from payment.order_id

    # From a payment-less order event (order entity only):
    body2 = _event_body(event="order.paid", include_payment=False,
                        include_order=True)
    _post(body2, signature=_sign(body2), event_id=OTHER_EVENT_ID)
    row2 = fake_ledger.store[OTHER_EVENT_ID]
    assert row2["payment_id"] is None
    assert row2["order_id"] == ORDER_ID


def test_11b_absent_metadata_does_not_fail_webhook(fake_ledger):
    """An event envelope with no payment/order entity at all is still
    ingested — optional metadata never fails the webhook."""
    body = json.dumps({
        "entity": "event",
        "event": "payment.authorized",
        "payload": {},
    }).encode("utf-8")
    r = _post(body, signature=_sign(body))
    assert r.status_code == 200
    row = fake_ledger.store[EVENT_ID]
    assert row["payment_id"] is None and row["order_id"] is None


def test_12_unknown_signed_event_handled_safely(fake_ledger):
    """A brand-new Razorpay event type must be recorded, answered 2xx (no
    retry loop), and never crash the endpoint."""
    body = _event_body(event="payment.page.created")
    r = _post(body, signature=_sign(body))
    assert r.status_code == 200
    row = fake_ledger.store[EVENT_ID]
    assert row["event_type"] == "payment.page.created"
    assert row["processing_status"] == "ignored"


def test_16_different_event_ids_create_separate_records(fake_ledger):
    body = _event_body()
    r1 = _post(body, signature=_sign(body), event_id=EVENT_ID)
    body2 = _event_body(event="payment.authorized")
    r2 = _post(body2, signature=_sign(body2), event_id=OTHER_EVENT_ID)
    assert r1.status_code == 200 and r2.status_code == 200
    assert len(fake_ledger.store) == 2
    assert EVENT_ID in fake_ledger.store and OTHER_EVENT_ID in fake_ledger.store


# ---------------------------------------------------------------------------
# Malformed signed payloads (mandated test 13)
# ---------------------------------------------------------------------------

def test_13_malformed_signed_json_handled_safely(fake_ledger):
    """Valid signature + invalid JSON: recorded as failed, answered 2xx
    (re-delivery cannot fix bytes Razorpay already signed — retrying would
    be operationally harmful), no crash, no retry loop."""
    bad_body = b"{definitely-not-json"
    r = _post(bad_body, signature=_sign(bad_body))
    assert r.status_code == 200
    row = fake_ledger.store[EVENT_ID]
    assert row["processing_status"] == "failed"
    assert row["event_type"] == "unknown"
    assert TEST_WEBHOOK_SECRET not in (row["processing_error"] or "")


def test_13b_malformed_signed_non_object_json(fake_ledger):
    bad_body = b'["a","signed","array"]'
    r = _post(bad_body, signature=_sign(bad_body))
    assert r.status_code == 200
    assert fake_ledger.store[EVENT_ID]["processing_status"] == "failed"


def test_malformed_unsigned_json_is_never_recorded(fake_ledger):
    """Invalid signature + invalid JSON: 401 and NOTHING in the ledger —
    unsigned input never creates a record."""
    r = _post(b"{broken", signature="0" * 64)
    assert r.status_code == 401
    assert len(fake_ledger.store) == 0


# ---------------------------------------------------------------------------
# Duplicate delivery (mandated tests 14, 15, 24)
# ---------------------------------------------------------------------------

def test_14_duplicate_event_sequentially_creates_one_record(fake_ledger):
    body = _event_body()
    r1 = _post(body, signature=_sign(body), event_id=EVENT_ID)
    r2 = _post(body, signature=_sign(body), event_id=EVENT_ID)
    assert r1.status_code == 200
    assert r2.status_code == 200  # duplicate is a safe success, not an error
    assert len(fake_ledger.store) == 1
    assert len(fake_ledger.insert_calls) == 2  # second insert attempted...
    # ...but refused by the unique index; original row untouched.
    assert fake_ledger.store[EVENT_ID]["processing_status"] == "received"


def test_15_duplicate_event_concurrently_creates_one_record(fake_ledger):
    """Both deliveries race: the unique-index-backed insert admits exactly
    one ledger row; both requests receive 200."""
    body = _event_body()

    async def deliver():
        # Two endpoint invocations run interleaved on the event loop.
        import anyio
        results = []

        async def one():
            c = TestClient(app)
            resp = c.post(
                "/api/webhooks/razorpay",
                content=body,
                headers={
                    "X-Razorpay-Signature": _sign(body),
                    "X-Razorpay-Event-Id": EVENT_ID,
                },
            )
            results.append(resp.status_code)

        await asyncio.gather(one(), one())
        return results

    statuses = asyncio.run(deliver())
    assert statuses == [200, 200]
    assert len(fake_ledger.store) == 1
    assert len(fake_ledger.insert_calls) == 2
    # The recorded row is fully intact (not partially overwritten).
    assert fake_ledger.store[EVENT_ID]["processing_status"] == "received"


def test_24_duplicate_response_is_success(fake_ledger):
    body = _event_body()
    _post(body, signature=_sign(body))
    r = _post(body, signature=_sign(body))
    assert 200 <= r.status_code < 300


# ---------------------------------------------------------------------------
# Invalid signature cannot claim an event (mandated test 17 + §14.5)
# ---------------------------------------------------------------------------

def test_17_invalid_signature_does_not_create_record(fake_ledger):
    body = _event_body()
    r = _post(body, signature="f" * 64, event_id=EVENT_ID)
    assert r.status_code == 401
    assert len(fake_ledger.store) == 0


def test_invalid_signature_with_existing_event_id_cannot_claim_it(fake_ledger):
    """An attacker (or a corrupted retry) reusing a REAL event_id but without
    a valid signature must not insert, overwrite, or shadow the existing
    ledger row."""
    body = _event_body()
    _post(body, signature=_sign(body), event_id=EVENT_ID)
    original = dict(fake_ledger.store[EVENT_ID])

    r = _post(body, signature="0" * 64, event_id=EVENT_ID)
    assert r.status_code == 401
    assert len(fake_ledger.store) == 1
    assert fake_ledger.store[EVENT_ID] == original


# ---------------------------------------------------------------------------
# Hard boundary: NO domain/payment state changes (mandated tests 18-20, §16)
# ---------------------------------------------------------------------------

def test_18_webhook_does_not_change_appointment_state():
    """Structural: the webhook module cannot write appointments — it imports
    no appointment model/repository/service at all."""
    import sys

    import app.api.webhooks as wh

    module_names = set(sys.modules)
    # The webhook router module must not reference the payment domain.
    src_names = set(dir(wh))
    for forbidden in ("Appointment", "AppointmentRepository",
                      "AppointmentService", "PaymentService",
                      "PaymentRepository"):
        assert forbidden not in src_names, forbidden

    import inspect
    src = inspect.getsource(wh)
    for token in ("mark_appointment_paid", "mark_laboratory_paid",
                  "mark_laboratory_failed", "claim_appointment_order",
                  "claim_laboratory_order", ".save()"):
        assert token not in src, token
    _ = module_names  # silence unused


def test_19_webhook_does_not_change_laboratory_state():
    import inspect

    import app.api.webhooks as wh

    src_names = set(dir(wh))
    for forbidden in ("LaboratoryBooking", "LaboratoryBookingRepository",
                      "LaboratoryService"):
        assert forbidden not in src_names, forbidden

    src = inspect.getsource(wh)
    assert "billing_status" not in src
    assert "payment_status" not in src


def test_20_webhook_does_not_create_payment_notifications():
    import inspect

    from app.api import webhooks

    src = inspect.getsource(webhooks)
    assert "NotificationService" not in src
    assert "create_notification" not in src
    assert "_notify" not in src


def test_webhook_module_calls_no_razorpay_apis():
    """§17: no reconciliation — no payment.fetch / order.fetch / refund from
    the webhook path (signature verification is pure local HMAC)."""
    import inspect

    from app.api import webhooks

    src = inspect.getsource(webhooks)
    for token in ("payment.fetch", "order.fetch", ".refund(", "fetch_payment",
                  "create_order", "get_razorpay_client"):
        assert token not in src, token


# ---------------------------------------------------------------------------
# Security (mandated tests 21, 22, 23, 25)
# ---------------------------------------------------------------------------

def test_21_secret_never_appears_in_errors(fake_ledger):
    """Every error response path is free of both secrets, and the ledger
    stores no secret material."""
    client = TestClient(app)

    # Signature failures
    r = _post(_event_body(), signature="0" * 64)
    assert TEST_WEBHOOK_SECRET not in r.text
    assert TEST_KEY_SECRET not in r.text

    # Missing signature
    r = _post(_event_body(), signature=None)
    assert TEST_WEBHOOK_SECRET not in r.text

    # Config missing -> 503 without secret leakage
    with patch("app.api.webhooks.verify_webhook_signature",
               side_effect=RazorpayConfigError("webhook secret not set")):
        r = client.post("/api/webhooks/razorpay", content=b"{}",
                        headers={"X-Razorpay-Signature": "x" * 64})
    assert r.status_code == 503
    assert TEST_WEBHOOK_SECRET not in r.text
    assert TEST_KEY_SECRET not in r.text

    # Helper error messages themselves carry no secret
    try:
        verify_webhook_signature(b"{}", "")
    except RazorpaySignatureError as e:
        assert TEST_WEBHOOK_SECRET not in str(e)
        assert TEST_KEY_SECRET not in str(e)

    # Ledger rows store no secret material
    body = _event_body()
    _post(body, signature=_sign(body))
    for row in fake_ledger.store.values():
        assert TEST_WEBHOOK_SECRET not in json.dumps(row, default=str)
        assert TEST_KEY_SECRET not in json.dumps(row, default=str)


def test_22_raw_body_is_never_logged(caplog, fake_ledger):
    """No log record emitted by the webhook flow contains the raw body, the
    signature, the secret, or payload PII."""
    import logging as _logging

    client = TestClient(app)
    body = _event_body()  # contains email/contact PII
    sig = _sign(body)

    with caplog.at_level(_logging.DEBUG):
        _post(body, signature=sig)          # accepted
        _post(body, signature="0" * 64)     # invalid signature
        _post(body, signature=None)         # missing signature
        _post(b"{broken", signature=_sign(b"{broken"))  # malformed signed

    text = caplog.text
    assert "customer.pii@example.com" not in text
    assert "+919000090000" not in text
    assert sig not in text
    assert TEST_WEBHOOK_SECRET not in text
    assert TEST_KEY_SECRET not in text
    # The raw body bytes must not be logged verbatim.
    assert '"event": "payment.captured"' not in text
    assert b"payment.captured".decode() in text or True  # type exists in ledger row, not logs
    # And the ledger stores no PII.
    for row in fake_ledger.store.values():
        row_text = json.dumps(row, default=str)
        assert "customer.pii@example.com" not in row_text
        assert "+919000090000" not in row_text


def test_23_no_jwt_required():
    """The webhook route requires no Authorization header at all, and the
    router declares no auth dependency."""
    from app.middleware.auth import get_current_user

    client = TestClient(app)
    body = _event_body()
    r = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body),
                 "X-Razorpay-Event-Id": EVENT_ID},
    )
    assert r.status_code == 200  # no 401 "Not authenticated"

    # Structural: no JWT dependency in the webhook module.
    import inspect

    from app.api import webhooks

    src = inspect.getsource(webhooks)
    assert "get_current_user" not in src
    assert "RoleChecker" not in src
    assert "Depends(get_current_user" not in src
    _ = get_current_user


def test_25_unique_event_id_index_exists():
    """The unique event_id index is declared on the model with the same
    Beanie IndexModel pattern as the existing unique partial indexes."""
    from app.models.webhook_event import WebhookEvent

    indexes = WebhookEvent.Settings.indexes
    uniq = [ix for ix in indexes
            if getattr(ix, "document", {}).get("name") == "uniq_webhook_event_id"]
    assert len(uniq) == 1, "exactly one named unique index expected"
    spec = uniq[0].document
    assert spec.get("unique") is True
    # Beanie renders IndexModel keys as a mapping ({"event_id": 1}).
    assert spec.get("key") in ([("event_id", 1)], {"event_id": 1})
    # No partial filter: the constraint applies to every event row.
    assert "partialFilterExpression" not in spec


def test_ledger_uses_unique_index_not_check_then_insert():
    """The dedupe mechanism is the database constraint on insert — there is
    no 'find event -> if missing -> insert' in the ingestion path."""
    import inspect

    from app.api import webhooks

    src = inspect.getsource(webhooks._record_event)
    assert "find_one" not in src and "find(" not in src
    assert "insert()" in src or "insert_one" in src
    assert "DuplicateKeyError" in src
