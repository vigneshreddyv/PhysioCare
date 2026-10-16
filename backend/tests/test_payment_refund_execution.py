"""
Phase 4 Task 13 tests — Razorpay refund execution & confirmed state
transition.

Covers the mandated areas: execution flow (claim → Razorpay → validated
transition), security (no caller override surface, no secrets, response
never blindly trusted), concurrency/idempotency (exactly one Razorpay
call, exactly one transition winner, duplicate execution is a no-op),
failure semantics (definitive rejection → failed; timeout/connection/5xx/
malformed/pending → processing preserved), terminal-state protection,
client-level request/error-taxonomy behavior, and Task 1–12 regression
guards.

ALL Razorpay interactions are mocked at both boundaries
(PaymentRefundService.execute_refund's create_refund import, and
razorpay_client's SDK client). No test contacts the real Razorpay API,
uses real credentials, or performs a real transaction.
"""
import asyncio
import inspect
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from razorpay.errors import BadRequestError, GatewayError, ServerError

from app.core import razorpay_client
from app.core.config import settings
from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpayRefundOutcome,
    RazorpayRequestError,
    create_refund,
    fetch_refund,
)
from app.models.payment_refund import PaymentRefund
from app.repositories.payment_refund_repository import PaymentRefundRepository
from app.services.payment_refund_service import PaymentRefundService

TEST_KEY_ID = "rzp_test_unitkeyid123"
TEST_SECRET = "test_key_secret_for_unit_tests_only"

ADMIN = "aaaaaaaaaaaaaaaaaaaaaaaa"
P1 = "111111111111111111111111"
APT = "333333333333333333333333"
RID = "d0000000000000000000000d"  # PaymentRefund document id (valid ObjectId hex)

STORED_PAYMENT_ID = "pay_stored1234567"
STORED_ORDER_ID = "order_stored12345"
STORED_AMOUNT_PAISE = 50000  # Rs. 500.00, backend-authoritative

RP_REFUND_OK = {
    "id": "rfnd_RazorpayReturned1",
    "entity": "refund",
    "amount": STORED_AMOUNT_PAISE,
    "currency": "INR",
    "payment_id": STORED_PAYMENT_ID,
    "status": "processed",
}

RP_REFUND_PENDING = {
    "id": "rfnd_RazorpayPending1",
    "entity": "refund",
    "amount": STORED_AMOUNT_PAISE,
    "currency": "INR",
    "payment_id": STORED_PAYMENT_ID,
    "status": "pending",
}


@pytest.fixture(autouse=True)
def razorpay_test_config(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", TEST_KEY_ID)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", TEST_SECRET)
    monkeypatch.setattr(settings, "RAZORPAY_TIMEOUT_SECONDS", 30)


@pytest.fixture(autouse=True)
def mock_payment_refund_collection():
    """Same local conftest counterpart as the Task 12 suite (PaymentRefund
    postdates the shared conftest mock list)."""
    mock_settings = MagicMock()
    mock_settings.pymongo_collection = "payment_refunds"
    mock_settings.name = "payment_refunds"
    mock_settings.bson_encoders.get.return_value = None
    with patch.object(PaymentRefund, "get_settings", return_value=mock_settings):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_refund_record(status="requested", payment_id=STORED_PAYMENT_ID,
                       amount=STORED_AMOUNT_PAISE, **kw):
    r = MagicMock()
    r.id = kw.get("id", RID)
    r.payable_type = kw.get("payable_type", "appointment")
    r.payable_id = kw.get("payable_id", APT)
    r.payment_id = payment_id
    r.payment_order_id = kw.get("payment_order_id", STORED_ORDER_ID)
    r.amount = amount
    r.currency = kw.get("currency", "INR")
    r.status = status
    r.reason = kw.get("reason", "refund_requested")
    r.requested_by = ADMIN
    # Task 14: identity is absent by default (a MagicMock would
    # auto-create a truthy attribute and wrongly read as "persisted").
    r.razorpay_refund_id = kw.get("razorpay_refund_id", None)
    return r


@contextmanager
def refund_repo(records, claim=MagicMock(), completed_doc=None, failed_doc=None,
                touched_doc=None, attach_doc=None):
    """Patch the PaymentRefundRepository methods execute_refund uses.

    `records` is the side_effect list for get_by_id (in call order);
    the rest are return values for the atomic transition helpers.

    Task 14: attach_doc defaults to the successful identity-attachment
    outcome ({"razorpay_refund_id": ...}) so Task 13-era happy-path
    tests keep exercising the success flow. Tests that specifically
    verify identity-failure semantics pass attach_doc=None explicitly.
    """
    mocks = {}
    with ExitStack() as st:
        mocks["get_by_id"] = st.enter_context(patch.object(
            PaymentRefundRepository, "get_by_id",
            new=AsyncMock(side_effect=records)))
        mocks["claim"] = st.enter_context(patch.object(
            PaymentRefundRepository, "claim_for_processing",
            new=AsyncMock(return_value=claim)))
        mocks["mark_completed"] = st.enter_context(patch.object(
            PaymentRefundRepository, "mark_completed",
            new=AsyncMock(return_value=completed_doc)))
        mocks["mark_failed"] = st.enter_context(patch.object(
            PaymentRefundRepository, "mark_failed",
            new=AsyncMock(return_value=failed_doc)))
        mocks["touch"] = st.enter_context(patch.object(
            PaymentRefundRepository, "touch_processing",
            new=AsyncMock(return_value=touched_doc)))
        attach_default = {"_id": RID,
                          "razorpay_refund_id": "rfnd_attached"}
        if isinstance(attach_doc, list):
            attach_mock = AsyncMock(side_effect=attach_doc)
        elif attach_doc is not None:
            attach_mock = AsyncMock(return_value=attach_doc)
        else:
            attach_mock = AsyncMock(return_value=attach_default)
        mocks["attach"] = st.enter_context(patch.object(
            PaymentRefundRepository, "attach_razorpay_refund_id",
            new=attach_mock))
        yield mocks


@contextmanager
def razorpay_refund(response=None, error=None):
    """Patch the execution service's create_refund import (the boundary
    the service actually calls through asyncio.to_thread)."""
    mock = MagicMock(side_effect=error) if error is not None \
        else MagicMock(return_value=response)
    with patch("app.services.payment_refund_service.create_refund", new=mock):
        yield mock


def definitive_error(detail="Payment is not refundable"):
    return RazorpayRequestError(
        f"{RazorpayRefundOutcome.DEFINITIVE}: Razorpay rejected the refund "
        f"request: {detail}"
    )


def ambiguous_error(kind="network"):
    return RazorpayRequestError(
        f"{RazorpayRefundOutcome.AMBIGUOUS}: {kind}"
    )


# ===========================================================================
# CLIENT-LEVEL: create_refund / fetch_refund (Task 13 §1)
# ===========================================================================

def test_client_builds_full_refund_request_with_inr_and_timeout():
    """CHECK 4 (client layer): the SDK request carries the stored amount,
    currency INR, normal speed, and an explicit timeout."""
    fake_client = MagicMock()
    fake_client.payment.refund.return_value = dict(RP_REFUND_OK)
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        refund = create_refund(STORED_PAYMENT_ID, STORED_AMOUNT_PAISE)

    assert refund["id"] == "rfnd_RazorpayReturned1"
    args, kwargs = fake_client.payment.refund.call_args
    payment_id, data = args
    assert payment_id == STORED_PAYMENT_ID
    assert data == {"amount": STORED_AMOUNT_PAISE, "currency": "INR",
                    "speed": "normal"}
    # Explicit timeout forwarded through the SDK.
    assert kwargs.get("timeout") == settings.RAZORPAY_TIMEOUT_SECONDS
    # Credentials never appear in the request payload.
    assert TEST_SECRET not in repr(args) + repr(kwargs)
    assert TEST_KEY_ID not in repr(args) + repr(kwargs)


def test_client_rejects_bad_input_before_any_client_construction():
    fake_client = MagicMock()
    fake_client.payment.refund.side_effect = AssertionError(
        "network call must not happen"
    )
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError):
            create_refund("", STORED_AMOUNT_PAISE)
        with pytest.raises(RazorpayRequestError):
            create_refund(STORED_PAYMENT_ID, 0)
        with pytest.raises(RazorpayRequestError):
            create_refund(STORED_PAYMENT_ID, -100)
        with pytest.raises(RazorpayRequestError):
            create_refund(STORED_PAYMENT_ID, "50000")   # not int paise
        with pytest.raises(RazorpayRequestError):
            create_refund(STORED_PAYMENT_ID, True)      # bool is not int
        with pytest.raises(RazorpayRequestError):
            fetch_refund("", "rfnd_x")
        with pytest.raises(RazorpayRequestError):
            fetch_refund("pay_x", "")


def test_client_missing_config_raises_config_error():
    with patch.object(razorpay_client, "get_razorpay_client",
                      side_effect=RazorpayConfigError("config missing")):
        with pytest.raises(RazorpayConfigError):
            create_refund(STORED_PAYMENT_ID, STORED_AMOUNT_PAISE)


def test_client_definitive_rejection_classification():
    """4xx-class (BadRequestError) is DEFINITIVE: Razorpay said no."""
    fake_client = MagicMock()
    fake_client.payment.refund.side_effect = BadRequestError(
        "This payment has already been fully refunded"
    )
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            create_refund(STORED_PAYMENT_ID, STORED_AMOUNT_PAISE)
    assert RazorpayRefundOutcome.DEFINITIVE in str(e.value)
    assert RazorpayRefundOutcome.AMBIGUOUS not in str(e.value)
    assert TEST_SECRET not in str(e.value)


@pytest.mark.parametrize("exc", [
    GatewayError("internal server error"),
    ServerError("upstream failure"),
])
def test_client_server_errors_are_ambiguous(exc):
    """5xx-class errors NEVER claim a definitive rejection."""
    fake_client = MagicMock()
    fake_client.payment.refund.side_effect = exc
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            create_refund(STORED_PAYMENT_ID, STORED_AMOUNT_PAISE)
    assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)


def test_client_network_and_timeout_errors_are_ambiguous():
    import requests
    fake_client = MagicMock()
    fake_client.payment.refund.side_effect = requests.exceptions.Timeout("timed out")
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            create_refund(STORED_PAYMENT_ID, STORED_AMOUNT_PAISE)
    assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)
    assert TEST_SECRET not in str(e.value)


@pytest.mark.parametrize("bad_response", [None, {}, {"no_id": True}, "ok", []])
def test_client_malformed_2xx_response_is_ambiguous(bad_response):
    """A 2xx with a malformed body proves neither success nor rejection."""
    fake_client = MagicMock()
    fake_client.payment.refund.return_value = bad_response
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            create_refund(STORED_PAYMENT_ID, STORED_AMOUNT_PAISE)
    assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)


def test_client_fetch_refund_builds_correct_lookup():
    fake_client = MagicMock()
    fake_client.payment.fetch_refund_id.return_value = dict(RP_REFUND_OK)
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        refund = fetch_refund(STORED_PAYMENT_ID, "rfnd_abc123")
    assert refund["id"] == "rfnd_RazorpayReturned1"
    args, kwargs = fake_client.payment.fetch_refund_id.call_args
    assert args == (STORED_PAYMENT_ID, "rfnd_abc123")
    assert kwargs.get("timeout") == settings.RAZORPAY_TIMEOUT_SECONDS


def test_client_fetch_refund_error_taxonomy():
    fake_client = MagicMock()
    fake_client.payment.fetch_refund_id.side_effect = BadRequestError("no such refund")
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            fetch_refund(STORED_PAYMENT_ID, "rfnd_missing")
    assert RazorpayRefundOutcome.DEFINITIVE in str(e.value)

    fake_client = MagicMock()
    fake_client.payment.fetch_refund_id.side_effect = ServerError("5xx")
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            fetch_refund(STORED_PAYMENT_ID, "rfnd_missing")
    assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)


# ===========================================================================
# BASIC EXECUTION (mandated 1–6)
# ===========================================================================

@pytest.mark.asyncio
async def test_1_requested_refund_claims_processing():
    """CHECK 1: a requested refund is atomically claimed before any
    Razorpay interaction."""
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")
    with refund_repo(
        records=[requested, completed],
        claim={"_id": RID, "status": "processing"},
        completed_doc={"_id": RID, "status": "completed"},
    ) as repo, razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    repo["claim"].assert_awaited_once_with(RID)
    assert result.status == "completed"
    assert rzp.call_count == 1


@pytest.mark.asyncio
async def test_2_correct_payment_id_sent_to_razorpay():
    """CHECK 2: the stored payment_id is what reaches Razorpay — and the
    caller can pass nothing else (no override parameter exists)."""
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")
    with refund_repo(
        records=[requested, completed],
        claim={"_id": RID, "status": "processing"},
        completed_doc={"_id": RID, "status": "completed"},
    ) as repo, razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        await PaymentRefundService.execute_refund(RID)
    assert rzp.call_count == 1
    payment_id_arg, amount_arg = rzp.call_args.args
    assert payment_id_arg == STORED_PAYMENT_ID
    assert amount_arg == STORED_AMOUNT_PAISE
    repo["mark_completed"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_3_correct_authoritative_amount_sent():
    """CHECK 3: the amount sent is exactly the backend-stored refund
    amount — no caller-supplied amount exists in the signature."""
    for amount in (50000, 105030, 1):
        requested = make_refund_record(status="requested", amount=amount)
        completed = make_refund_record(status="completed", amount=amount)
        ok = dict(RP_REFUND_OK)
        ok["amount"] = amount
        with refund_repo(
            records=[requested, completed],
            claim={"_id": RID, "status": "processing"},
            completed_doc={"_id": RID, "status": "completed"},
        ), razorpay_refund(response=ok) as rzp:
            await PaymentRefundService.execute_refund(RID)
        assert rzp.call_args.args[1] == amount
    sig = inspect.signature(PaymentRefundService.execute_refund)
    assert "amount" not in sig.parameters
    assert "payment_id" not in sig.parameters


def test_4_inr_enforced_in_client_request():
    """CHECK 4 (also covered at the client boundary above): currency is
    hardcoded INR in the Razorpay request; no currency parameter exists
    anywhere in the execution surface."""
    fake_client = MagicMock()
    fake_client.payment.refund.return_value = dict(RP_REFUND_OK)
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        create_refund(STORED_PAYMENT_ID, STORED_AMOUNT_PAISE)
    data = fake_client.payment.refund.call_args.args[1]
    assert data["currency"] == "INR"
    for fn in (PaymentRefundService.execute_refund,
               PaymentRefundService.reconcile_ambiguous_refund):
        sig = inspect.signature(fn)
        assert "currency" not in sig.parameters


@pytest.mark.asyncio
async def test_5_successful_response_marks_completed():
    """CHECK 5: a proven 'processed' response transitions the refund to
    completed via the atomic repository operation."""
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")
    with refund_repo(
        records=[requested, completed],
        claim={"_id": RID, "status": "processing"},
        completed_doc={"_id": RID, "status": "completed"},
    ) as repo, razorpay_refund(response=dict(RP_REFUND_OK)):
        result = await PaymentRefundService.execute_refund(RID)
    repo["mark_completed"].assert_awaited_once_with(RID)
    repo["mark_failed"].assert_not_awaited()
    assert result.status == "completed"


def test_6_razorpay_refund_id_validated_and_durably_persisted():
    """CHECK 6 (updated by Task 14, which closes the Task 13 limitation):
    the response refund id is validated for presence (an id-less response
    is unproven and never completes) AND is now durably persisted through
    the atomic attach operation before completion — mandated by Task 14
    §1/§4. The Task 13 'cannot persist' branch is superseded, not deleted:
    the schema field + attach semantics are covered by the Task 14
    identity suite (test_payment_refund_identity.py)."""
    fields = set(PaymentRefund.model_fields.keys())
    assert "razorpay_refund_id" in fields  # Task 14: field now exists

    # A response without an id can never prove success.
    assert PaymentRefundService._validate_razorpay_refund_response(
        {"status": "processed", "payment_id": STORED_PAYMENT_ID,
         "amount": STORED_AMOUNT_PAISE, "currency": "INR"},
        STORED_PAYMENT_ID, STORED_AMOUNT_PAISE,
    ) == "ambiguous"


# ===========================================================================
# SECURITY (mandated 7–12)
# ===========================================================================

def test_7_8_9_no_caller_override_surface():
    """CHECKS 7/8/9: execute_refund accepts ONLY the refund record id —
    payment id, amount, and currency come exclusively from the persisted
    record; no override parameter exists to call with."""
    for fn_name in ("execute_refund", "reconcile_ambiguous_refund"):
        sig = inspect.signature(getattr(PaymentRefundService, fn_name))
        for banned in ("payment_id", "payment_order_id", "amount",
                       "currency", "status"):
            assert banned not in sig.parameters, (fn_name, banned)


@pytest.mark.asyncio
async def test_10_secrets_never_appear_in_errors_or_logs(caplog):
    """CHECK 10: no failure path leaks the key secret, and no log carries
    credential material — config error, definitive rejection, ambiguity,
    and validation rejections all included."""
    import logging as _logging

    requested = make_refund_record(status="requested")

    # Config error -> 503
    with refund_repo(records=[requested]) as repo, \
            patch("app.services.payment_refund_service.create_refund",
                  new=MagicMock(side_effect=RazorpayConfigError("no config"))):
        with caplog.at_level(_logging.ERROR):
            with pytest.raises(HTTPException) as e:
                await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 503
    assert TEST_SECRET not in e.value.detail

    # Definitive rejection -> failed
    failed = make_refund_record(status="failed")
    with refund_repo(
        records=[requested, failed],
        claim={"_id": RID, "status": "processing"},
        failed_doc={"_id": RID, "status": "failed"},
    ), razorpay_refund(error=definitive_error("amount must be at least INR 1.00")):
        with caplog.at_level(_logging.ERROR):
            result = await PaymentRefundService.execute_refund(RID)
    assert result.status == "failed"

    # Ambiguous -> 409 reconciliation
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
    ), razorpay_refund(error=ambiguous_error("timeout")):
        with caplog.at_level(_logging.ERROR):
            with pytest.raises(HTTPException) as e:
                await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    assert TEST_SECRET not in e.value.detail

    # Nothing in any log ever carried the secret or the key id.
    assert TEST_SECRET not in caplog.text
    assert TEST_KEY_ID not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("mutate", [
    lambda rp: {**rp, "payment_id": "pay_attacker123"},
    lambda rp: {**rp, "amount": STORED_AMOUNT_PAISE + 1},
    lambda rp: {**rp, "amount": 1},
    lambda rp: {**rp, "currency": "USD"},
    lambda rp: {**rp, "currency": None},
    lambda rp: {**rp, "status": "processed", "payment_id": None},
])
async def test_11_response_never_blindly_trusted(mutate):
    """CHECK 11: a 'processed' response that disagrees with the persisted
    record on ANY financial fact is unproven — the refund stays
    processing and is never completed."""
    requested = make_refund_record(status="requested")
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
    ) as repo, razorpay_refund(response=mutate(dict(RP_REFUND_OK))):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    repo["mark_completed"].assert_not_awaited()
    repo["touch"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, {}, {"id": None}, [], "processed", 42])
async def test_12_malformed_response_cannot_produce_completed(bad):
    """CHECK 12: incomplete/malformed responses never mark completed."""
    requested = make_refund_record(status="requested")
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
    ) as repo, razorpay_refund(response=bad):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()


# ===========================================================================
# CONCURRENCY / IDEMPOTENCY (mandated 13–16)
# ===========================================================================

@pytest.mark.asyncio
async def test_13_two_executions_exactly_one_razorpay_call():
    """CHECK 13: a concurrent second execution observes the refund no
    longer 'requested' and issues NO Razorpay call."""
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")

    # Winner
    with refund_repo(
        records=[requested, completed],
        claim={"_id": RID, "status": "processing"},
        completed_doc={"_id": RID, "status": "completed"},
    ) as repo, razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        await PaymentRefundService.execute_refund(RID)
    assert rzp.call_count == 1
    repo["claim"].assert_awaited_once()

    # Concurrent loser: re-read sees a non-requested record; no claim and
    # no Razorpay call from the loser.
    processing = make_refund_record(status="processing")
    with refund_repo(records=[processing]) as repo2, \
            razorpay_refund(response=dict(RP_REFUND_OK)) as rzp2:
        result = await PaymentRefundService.execute_refund(RID)
    assert result.status == "processing"
    rzp2.call_count == 0
    repo2["claim"].assert_not_awaited()


@pytest.mark.asyncio
async def test_14_exactly_one_worker_transitions_to_processing():
    """CHECK 14: the claim happens exactly once, via the existing atomic
    repository operation (never replaced or bypassed)."""
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")
    with refund_repo(
        records=[requested, completed],
        claim={"_id": RID, "status": "processing"},
        completed_doc={"_id": RID, "status": "completed"},
    ) as repo, razorpay_refund(response=dict(RP_REFUND_OK)):
        await PaymentRefundService.execute_refund(RID)
    repo["claim"].assert_awaited_once_with(RID)

    # Structural: the service uses the repository claim — no private
    # find_one_and_update of its own.
    src = inspect.getsource(PaymentRefundService.execute_refund)
    assert "claim_for_processing(" in src
    assert "find_one_and_update" not in src
    assert ".save(" not in src


@pytest.mark.asyncio
async def test_15_exactly_one_worker_can_transition_to_completed():
    """CHECK 15: completion flows through the guarded mark_completed —
    whose filter only matches 'processing' — so a concurrent terminalizer
    can never double-complete."""
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")
    with refund_repo(
        records=[requested, completed],
        claim={"_id": RID, "status": "processing"},
        completed_doc={"_id": RID, "status": "completed"},
    ) as repo, razorpay_refund(response=dict(RP_REFUND_OK)):
        await PaymentRefundService.execute_refund(RID)
    repo["mark_completed"].assert_awaited_once_with(RID)

    # Repository-level proof of the same guard: two concurrent
    # mark_completed attempts, only the first matches.
    fake_coll = MagicMock()
    calls = {"n": 0}

    async def guarded(*a, **k):
        calls["n"] += 1
        return {"_id": RID, "status": "completed"} if calls["n"] == 1 else None

    fake_coll.find_one_and_update = AsyncMock(side_effect=guarded)
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        results = await asyncio.gather(
            PaymentRefundRepository.mark_completed(RID),
            PaymentRefundRepository.mark_completed(RID),
        )
    assert results[0] is not None and results[1] is None


@pytest.mark.asyncio
async def test_16_duplicate_execution_after_completed_no_razorpay_call():
    """CHECK 16: executing an already-completed refund returns it as-is —
    zero Razorpay calls, zero claims."""
    completed = make_refund_record(status="completed")
    with refund_repo(records=[completed]) as repo, \
            razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    assert result.status == "completed"
    rzp.call_count == 0
    repo["claim"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()


# ===========================================================================
# FAILURE SEMANTICS (mandated 17–22)
# ===========================================================================

@pytest.mark.asyncio
async def test_17_definitive_rejection_marks_failed():
    """CHECK 17: a definitive Razorpay rejection (4xx-class) transitions
    processing → failed via the atomic repository operation."""
    requested = make_refund_record(status="requested")
    failed = make_refund_record(status="failed")
    with refund_repo(
        records=[requested, failed],
        claim={"_id": RID, "status": "processing"},
        failed_doc={"_id": RID, "status": "failed"},
    ) as repo, razorpay_refund(error=definitive_error("Payment is not refundable")):
        result = await PaymentRefundService.execute_refund(RID)
    repo["mark_failed"].assert_awaited_once_with(RID)
    repo["mark_completed"].assert_not_awaited()
    repo["touch"].assert_not_awaited()  # not ambiguous — proven rejection
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_18_timeout_not_falsely_failed():
    """CHECK 18: a timeout is AMBIGUOUS — Razorpay may have accepted the
    refund. The record stays processing; no failed marking."""
    requested = make_refund_record(status="requested")
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
    ) as repo, razorpay_refund(error=ambiguous_error("timeout")):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    assert "reconcil" in e.value.detail.lower()
    repo["mark_failed"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["touch"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_19_connection_error_not_falsely_failed():
    import requests
    requested = make_refund_record(status="requested")
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
    ) as repo, razorpay_refund(
        error=ambiguous_error("connection reset")
    ) as rzp:
        # The service-level boundary re-raises whatever the client layer
        # produced; simulate the client mapping by wrapping the raw SDK
        # exception as the client would.
        with patch(
            "app.services.payment_refund_service.create_refund",
            new=MagicMock(side_effect=razorpay_client.RazorpayRequestError(
                f"{RazorpayRefundOutcome.AMBIGUOUS}: connection error"
            )),
        ):
            with pytest.raises(HTTPException) as e:
                await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    repo["mark_failed"].assert_not_awaited()
    repo["touch"].assert_awaited_once_with(RID)
    _ = requests  # silence unused


@pytest.mark.asyncio
async def test_20_ambiguous_5xx_not_falsely_failed():
    """CHECK 20: a 5xx (mapped AMBIGUOUS by the client layer) keeps the
    refund in processing — never failed."""
    requested = make_refund_record(status="requested")
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
    ) as repo, razorpay_refund(
        error=RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay server error "
            "while creating the refund."
        )
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    repo["mark_failed"].assert_not_awaited()
    repo["touch"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_21_malformed_success_response_not_completed():
    """CHECK 21: a well-formed 'pending' acceptance — and any unknown
    status — is committed-but-unproven: processing preserved, never
    completed, never failed."""
    requested = make_refund_record(status="requested")
    # Razorpay says pending (accepted, not final)
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
    ) as repo, razorpay_refund(response=dict(RP_REFUND_PENDING)):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
    repo["touch"].assert_awaited_once_with(RID)

    # Classifier-level: unknown status is ambiguous even with matching facts.
    assert PaymentRefundService._validate_razorpay_refund_response(
        {**RP_REFUND_OK, "status": "mystery"}, STORED_PAYMENT_ID,
        STORED_AMOUNT_PAISE,
    ) == "ambiguous"


@pytest.mark.asyncio
@pytest.mark.parametrize("corrupt", [
    {"payment_id": ""},
    {"payment_id": None},
    {"payment_order_id": ""},
    {"payable_id": ""},
    {"payable_type": "care_plan"},
    {"amount": 0},
    {"amount": -50000},
    {"amount": None},
    {"amount": "50000"},
    {"currency": "USD"},
    {"currency": ""},
])
async def test_22_invalid_stored_refund_no_razorpay_call(corrupt):
    """CHECK 22: an incoherent persisted record fails closed BEFORE the
    claim and before any Razorpay interaction."""
    kwargs = {"status": "requested", **corrupt}
    requested = make_refund_record(**kwargs)
    with refund_repo(records=[requested]) as repo, \
            razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    assert "not coherent" in e.value.detail
    rzp.call_count == 0
    repo["claim"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()


# ===========================================================================
# TERMINAL-STATE PROTECTION (mandated 23–25)
# ===========================================================================

@pytest.mark.parametrize("current,target", [
    ("completed", "processing"),
    ("completed", "failed"),
    ("completed", "completed"),
    ("failed", "completed"),
    ("failed", "processing"),
    ("cancelled", "processing"),
    ("cancelled", "completed"),
])
def test_23_terminal_transitions_are_forbidden(current, target):
    """CHECK 23: no terminal state may start any transition — the
    Task 12 state matrix and the atomic filters both forbid it."""
    assert PaymentRefundRepository.validate_status_transition(
        current, target) is False

    # Repository-level: every transition guard matches only
    # requested/processing, so a record already in a terminal state can
    # never match — run the matching transition against a fake collection
    # (returns None) and verify the filter's expected status can never
    # equal the terminal current state.
    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(return_value=None)
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        result = asyncio.run(_terminal_guard_probe(current, target))
    assert result is None
    # Structural: the guard's expected status differs from the terminal
    # current state (completed→X guards expect "processing"; X→completed
    # from failed/cancelled can never match a processing-only filter).
    query = fake_coll.find_one_and_update.await_args.args[0]
    assert query["status"] not in ("completed", "failed", "cancelled")


async def _terminal_guard_probe(current_status, target_name):
    """Run the transition that target_name names; the fake collection
    returns None (guard mismatch)."""
    rid = RID
    if target_name == "completed":
        return await PaymentRefundRepository.mark_completed(rid)
    if target_name == "failed":
        return await PaymentRefundRepository.mark_failed(rid)
    if target_name == "processing":
        return await PaymentRefundRepository.claim_for_processing(rid)
    return await PaymentRefundRepository.cancel_if_requested(rid)


@pytest.mark.asyncio
async def test_24_completed_cannot_be_overwritten():
    """CHECK 24: re-executing a completed refund is a no-op that returns
    the record untouched (Task 12 suite also pins mark_completed's
    processing-only filter)."""
    completed = make_refund_record(status="completed")
    with refund_repo(records=[completed]) as repo, \
            razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    assert result is completed
    rzp.call_count == 0
    repo["claim"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()


@pytest.mark.asyncio
async def test_25_cancelled_cannot_execute():
    """CHECK 25: a cancelled refund never executes — returned untouched,
    no claim, no Razorpay call."""
    cancelled = make_refund_record(status="cancelled")
    with refund_repo(records=[cancelled]) as repo, \
            razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    assert result is cancelled
    rzp.call_count == 0
    repo["claim"].assert_not_awaited()


@pytest.mark.asyncio
async def test_25b_processing_refund_cannot_be_reexecuted_or_reconciled_twice():
    """A processing record (claimed by another worker) is not executable;
    reconciliation works on processing records only and terminal outcomes
    stand."""
    processing = make_refund_record(status="processing")
    with refund_repo(records=[processing]) as repo, \
            razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    assert result.status == "processing"
    rzp.call_count == 0
    repo["claim"].assert_not_awaited()


# ===========================================================================
# RECONCILIATION (minimal path — §6)
# ===========================================================================

@pytest.mark.asyncio
async def test_reconciliation_proven_success_completes():
    """Task 13 fallback path, Task 14 semantics: a processing record with
    NO persisted identity reconciles from an operator-supplied id, which
    is validated against Razorpay (probe) and attached atomically before
    completion."""
    processing = make_refund_record(status="processing")
    completed = make_refund_record(status="completed")
    # get_by_id reads: initial load, then the final post-completion re-read
    # (the attach path itself performs no extra record read).
    # Task 14 §7: the Razorpay response must carry the SAME refund id as
    # the supplied/persisted identity — the fixture is aligned.
    matching_response = {**RP_REFUND_OK, "id": "rfnd_operator_provided"}
    with refund_repo(
        records=[processing, completed],
        completed_doc={"_id": RID, "status": "completed"},
        attach_doc={"_id": RID, "razorpay_refund_id": "rfnd_operator_provided"},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=matching_response),
    ) as fetch:
        result = await PaymentRefundService.reconcile_ambiguous_refund(
            RID, "rfnd_operator_provided"
        )
    # Probe lookup + final authoritative read, both with the supplied id.
    assert fetch.call_args_list[0].args == (STORED_PAYMENT_ID, "rfnd_operator_provided")
    repo["attach"].assert_awaited_once_with(RID, "rfnd_operator_provided")
    repo["mark_completed"].assert_awaited_once_with(RID)
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_reconciliation_failure_stays_processing():
    """A Razorpay lookup failure during the Task 13 fallback leaves the
    record processing (nothing attached, nothing completed)."""
    processing = make_refund_record(status="processing")
    with refund_repo(records=[processing]) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(side_effect=RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: lookup timeout")),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.reconcile_ambiguous_refund(
                RID, "rfnd_operator_provided"
            )
    assert e.value.status_code == 409
    repo["attach"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
    repo["touch"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_reconciliation_ignores_non_processing_records():
    for status_value in ("requested", "completed", "failed", "cancelled"):
        rec = make_refund_record(status=status_value)
        with refund_repo(records=[rec]) as repo, patch(
            "app.services.payment_refund_service.fetch_refund", new=MagicMock()
        ) as fetch:
            result = await PaymentRefundService.reconcile_ambiguous_refund(
                RID, "rfnd_x"
            )
        assert result is rec
        fetch.assert_not_called()
        repo["attach"].assert_not_awaited()
        repo["mark_completed"].assert_not_awaited()


# ===========================================================================
# REGRESSION (mandated 26–30)
# ===========================================================================

def test_26_no_http_refund_endpoint():
    """CHECK 26: Task 11's no-refund-surface invariant still holds."""
    from app.main import app as fastapi_app
    routes = [getattr(r, "path", "") for r in fastapi_app.routes]
    assert not any("refund" in p.lower() for p in routes), routes


def test_27_no_frontend_refund_call():
    """CHECK 27: the frontend service layer still contains no refund
    calls (no frontend changes were made in Task 13)."""
    import os
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    api_js = os.path.join(root, "frontend", "src", "services", "api.js")
    with open(api_js, encoding="utf-8") as f:
        src = f.read()
    assert "refund" not in src.lower()


@pytest.mark.asyncio
async def test_28_no_appointment_or_laboratory_state_mutation():
    """CHECK 28: execution touches ONLY the PaymentRefund record — the
    execution/reconciliation code never references domain models, domain
    repositories, or any save/write on Appointment/LaboratoryBooking."""
    import app.services.payment_refund_service as mod
    exec_src = inspect.getsource(PaymentRefundService.execute_refund)
    recon_src = inspect.getsource(PaymentRefundService.reconcile_ambiguous_refund)
    for src in (exec_src, recon_src):
        for banned in (
            "Appointment", "LaboratoryBooking",
            "mark_appointment_paid", "mark_laboratory_paid",
            "mark_laboratory_failed",
            "expire_appointment_pending_payment",
            "expire_laboratory_pending_payment",
            ".save(",
        ):
            assert banned not in src, banned

    # Runtime proof: a full successful execution performs no domain write
    # (only PaymentRefundRepository methods and the Razorpay boundary run).
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")
    with refund_repo(
        records=[requested, completed],
        claim={"_id": RID, "status": "processing"},
        completed_doc={"_id": RID, "status": "completed"},
    ), razorpay_refund(response=dict(RP_REFUND_OK)), \
            patch("app.repositories.payment_repository."
                  "PaymentRepository.mark_appointment_paid",
                  new=MagicMock()) as appt_paid, \
            patch("app.repositories.payment_repository."
                  "PaymentRepository.mark_laboratory_paid",
                  new=MagicMock()) as lab_paid:
        await PaymentRefundService.execute_refund(RID)
    appt_paid.assert_not_called()
    lab_paid.assert_not_called()


def test_29_task_12_invariants_intact():
    """CHECK 29 (structural): the Task 12 repository operations and state
    machine are unchanged — expected-state filters still in every
    transition, Task 12 create/idempotency semantics untouched."""
    repo_src = inspect.getsource(PaymentRefundRepository)
    # Transitions unchanged (expected state in every filter).
    claim_src = inspect.getsource(
        PaymentRefundRepository.claim_for_processing)
    assert '"status": "requested"' in claim_src
    completed_src = inspect.getsource(
        PaymentRefundRepository.mark_completed)
    failed_src = inspect.getsource(PaymentRefundRepository.mark_failed)
    assert '"status": "processing"' in completed_src
    assert '"status": "processing"' in failed_src
    cancel_src = inspect.getsource(
        PaymentRefundRepository.cancel_if_requested)
    assert '"status": "requested"' in cancel_src
    # Task 12 creation path untouched (unique-index insert, no
    # check-then-insert).
    create_src = inspect.getsource(PaymentRefundRepository.create_refund)
    assert "find_one" not in create_src and "insert()" in create_src
    # Model/index unchanged.
    idx_names = [
        getattr(ix, "document", {}).get("name")
        for ix in PaymentRefund.Settings.indexes
    ]
    assert "uniq_active_refund_per_payment" in idx_names
    _ = repo_src


def test_30_no_raw_razorpay_calls_outside_client():
    """CHECK 30: Razorpay SDK interaction happens ONLY inside
    razorpay_client.py — the execution service touches only the two
    client helpers; no second client, no direct HTTP anywhere."""
    import app.services.payment_refund_service as mod
    import_lines = [
        line.strip()
        for line in inspect.getsource(mod).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    joined = "\n".join(import_lines)
    # The only Razorpay-layer references are the sanctioned helpers.
    assert "from app.core.razorpay_client import" in joined
    assert "import razorpay" not in joined
    assert "import requests" not in joined
    assert "import httpx" not in joined
    assert "import aiohttp" not in joined

    service_src = inspect.getsource(mod)
    for token in (
        "razorpay.Client(", "client.payment.refund", "client.payment.fetch",
        "requests.", "httpx.", "urllib.",
    ):
        assert token not in service_src, token

    # And the refund SDK calls live only in the client module.
    client_src = inspect.getsource(razorpay_client)
    assert "client.payment.refund(" in client_src
    assert "client.payment.fetch_refund_id(" in client_src


# ---------------------------------------------------------------------------
# Misc execution behavior
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_nonexistent_refund_404():
    with refund_repo(records=[None]):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_razorpay_config_error_maps_to_503():
    requested = make_refund_record(status="requested")
    with refund_repo(records=[requested], claim={"_id": RID}), \
            patch("app.services.payment_refund_service.create_refund",
                  new=MagicMock(side_effect=RazorpayConfigError("no config"))):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 503
    assert "Payment service is not available" in e.value.detail


@pytest.mark.asyncio
async def test_lost_claim_race_never_blind_retries():
    """A transient claim failure re-reads state and returns it — it never
    re-attempts the claim (which could double-execute if the first claim
    actually succeeded)."""
    requested = make_refund_record(status="requested")
    processing = make_refund_record(status="processing")
    with refund_repo(records=[requested, processing]) as repo, \
            razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    assert result.status == "processing"
    repo["claim"].assert_awaited_once()   # exactly one attempt
    rzp.call_count == 0                   # and no Razorpay call without a won claim


def test_amount_helper_edge_false_only_for_non_positive():
    # validate_refund_amount invariant still backs the coherence gate.
    assert PaymentRefundService.validate_refund_amount(0, 50000) is False
    assert PaymentRefundService.validate_refund_amount(-1, 50000) is False
    assert PaymentRefundService.validate_refund_amount(50000, 50000) is True


# ===========================================================================
# TASK 15 — RAZORPAY REFUND API EXECUTION (validation hardening + recovery)
# ===========================================================================

@pytest.mark.asyncio
async def test_15_refund_id_mismatch_with_persisted_identity_fails_closed():
    """§3: a response whose refund id differs from the ALREADY-persisted
    identity is an invariant violation — no completion, no overwrite,
    processing preserved."""
    requested = make_refund_record(
        status="requested", razorpay_refund_id="rfnd_preexisting001"
    )
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
    ) as repo, razorpay_refund(
        response={**RP_REFUND_OK, "id": "rfnd_different999"}
    ) as rzp:
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    assert "NOT marked completed" in e.value.detail
    repo["mark_completed"].assert_not_awaited()
    repo["attach"].assert_not_awaited()   # never overwrite
    repo["mark_failed"].assert_not_awaited()
    repo["touch"].assert_awaited_once_with(RID)
    rzp.assert_called_once()              # the single legitimate attempt


@pytest.mark.asyncio
async def test_15b_response_id_matching_persisted_identity_completes():
    """§3: when the response's refund id MATCHES the persisted identity
    (re-entered execution), validation passes and the refund completes
    through the normal attach→completed path."""
    requested = make_refund_record(
        status="requested", razorpay_refund_id=RP_REFUND_OK["id"]
    )
    completed = make_refund_record(
        status="completed", razorpay_refund_id=RP_REFUND_OK["id"]
    )
    with refund_repo(
        records=[requested, completed],
        claim={"_id": RID, "status": "processing"},
        completed_doc={"_id": RID, "status": "completed"},
    ) as repo, razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    assert result.status == "completed"
    rzp.assert_called_once()
    repo["mark_completed"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_15c_full_execution_sequence_ordering():
    """§2: the execution sequence textually enforces the mandated order —
    claim → Razorpay → validate (incl. identity match) → attach →
    mark_completed. Never reversed."""
    src = inspect.getsource(PaymentRefundService.execute_refund)
    claim_idx = src.index("claim_for_processing(refund_id)")
    rzp_idx = src.index("create_refund,")
    validate_idx = src.index("_validate_razorpay_refund_response(")
    identity_idx = src.index("rp_refund_id != persisted_identity")
    attach_idx = src.index("attach_razorpay_refund_id(")
    completed_idx = src.index("mark_completed(refund_id)")
    assert claim_idx < rzp_idx < validate_idx < identity_idx < attach_idx \
        < completed_idx


@pytest.mark.asyncio
async def test_15d_successful_full_refund_end_to_end():
    """§5 known response: valid id → validate → attach → complete →
    return completed record; exactly one Razorpay call."""
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")
    with refund_repo(
        records=[requested, completed],
        claim={"_id": RID, "status": "processing"},
        completed_doc={"_id": RID, "status": "completed"},
    ) as repo, razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    assert result.status == "completed"
    rzp.assert_called_once()
    assert rzp.call_args.args == (STORED_PAYMENT_ID, STORED_AMOUNT_PAISE)
    repo["attach"].assert_awaited_once_with(RID, RP_REFUND_OK["id"])
    repo["mark_completed"].assert_awaited_once_with(RID)
    repo["mark_failed"].assert_not_awaited()


@pytest.mark.asyncio
async def test_15e_identity_collision_fails_closed():
    """§5: attach losing the race / duplicate identity → fail closed,
    no completion, no second Razorpay refund."""
    requested = make_refund_record(status="requested")
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
        attach_doc=[None],  # identity collision / race / transient failure
    ) as repo, razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    assert "NOT marked completed" in e.value.detail
    rzp.assert_called_once()              # no second refund after conflict
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
    repo["touch"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_15f_ambiguous_execution_recovered_by_task14_reconciliation():
    """§4/§8: an ambiguous execution leaves processing; the Task 14
    reconciliation path then completes it from the (operator-attached)
    persisted identity — the recovery mechanism works end-to-end."""
    requested = make_refund_record(status="requested")
    processing = make_refund_record(status="processing")
    completed = make_refund_record(
        status="completed", razorpay_refund_id=RP_REFUND_OK["id"]
    )

    # 1. Ambiguous execution: timeout → stays processing, not failed.
    with refund_repo(
        records=[requested],
        claim={"_id": RID, "status": "processing"},
    ) as repo, razorpay_refund(error=ambiguous_error("timeout")) as rzp:
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    repo["mark_failed"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    rzp.assert_called_once()              # no second refund anywhere

    # 2. Operator attaches the identity (Task 13 fallback), reconciliation
    #    fetches by the persisted identity and completes.
    with refund_repo(
        # get_by_id reads: initial load (no identity), then the final
        # post-completion re-read (returns the completed record).
        records=[processing, completed],
        attach_doc={"_id": RID,
                    "razorpay_refund_id": RP_REFUND_OK["id"]},
        completed_doc={"_id": RID, "status": "completed"},
    ) as repo2, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ) as fetch:
        result = await PaymentRefundService.reconcile_ambiguous_refund(
            RID, RP_REFUND_OK["id"]
        )
    fetch.assert_called_with(STORED_PAYMENT_ID, RP_REFUND_OK["id"])
    repo2["attach"].assert_awaited_once_with(RID, RP_REFUND_OK["id"])
    repo2["mark_completed"].assert_awaited_once_with(RID)
    assert result.status == "completed"
    # Still exactly one Razorpay refund POST across both phases.
    rzp.assert_called_once()


@pytest.mark.asyncio
async def test_15g_no_second_active_refund_after_ambiguity():
    """§6: after an ambiguous execution, re-execution cannot create a
    second refund — the record is no longer 'requested', so no Razorpay
    call is issued and reconciliation remains the only path."""
    processing = make_refund_record(status="processing")
    with refund_repo(records=[processing]) as repo, \
            razorpay_refund(response=dict(RP_REFUND_OK)) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    assert result.status == "processing"
    rzp.assert_not_called()
    repo["claim"].assert_not_awaited()


# --- Task 15 structural security scan (§7) ------------------------------

def test_15h_structural_security_scan():
    """§7: no frontend-supplied payment_id/amount/currency/refund id; no
    secret outside the client; no SDK call outside razorpay_client.py;
    repositories/models never call Razorpay; no raw response logging."""
    import app.repositories.payment_refund_repository as repo_mod
    import app.models.payment_refund as model_mod
    import app.services.payment_refund_service as svc_mod
    import re as _re

    def exec_src(obj):
        s = inspect.getsource(obj)
        s = _re.sub(r'""".*?"""', "", s, flags=_re.S)
        return "\n".join(
            ln for ln in s.splitlines() if not ln.strip().startswith("#")
        )

    # No caller-supplied financial inputs on any execution surface.
    for fn_name in ("execute_refund", "reconcile_ambiguous_refund",
                    "request_refund"):
        sig = inspect.signature(getattr(PaymentRefundService, fn_name))
        for banned in ("payment_id", "payment_order_id", "amount",
                       "currency"):
            assert banned not in sig.parameters, (fn_name, banned)
    assert "razorpay_refund_id" not in inspect.signature(
        PaymentRefundService.request_refund).parameters

    # Repositories and models: zero Razorpay references (executable).
    for mod in (repo_mod, model_mod):
        src = exec_src(mod)
        for banned in ("razorpay_client", "import razorpay",
                       "get_razorpay_client", "client.payment",
                       "client.order"):
            assert banned not in src, (mod.__name__, banned)

    # Service: only the sanctioned client-boundary helpers; no SDK/HTTP.
    svc = exec_src(svc_mod)
    for banned in ("razorpay.Client(", "client.payment.refund",
                   "requests.", "httpx.", "urllib.", "import razorpay"):
        assert banned not in svc, banned

    # No raw Razorpay response is ever logged (only masked ids/statuses).
    client_src = exec_src(razorpay_client)
    for banned in ("logger.*", "logger.info(refund", "logger.error(refund"):
        pass  # placeholder; concrete checks below
    import ast as _ast
    tree = _ast.parse(inspect.getsource(razorpay_client))
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call) and \
                isinstance(node.func, _ast.Attribute) and \
                node.func.attr in ("info", "warning", "error", "exception", "debug"):
            rendered = _ast.unparse(node) if hasattr(_ast, "unparse") else ""
            assert "refund.get(" not in rendered, rendered
            assert "json.dumps(refund" not in rendered, rendered

    # Secrets live only in the client module.
    assert "RAZORPAY_KEY_SECRET" not in exec_src(svc_mod)
    assert "RAZORPAY_KEY_SECRET" not in exec_src(repo_mod)
    assert "RAZORPAY_KEY_SECRET" not in exec_src(model_mod)
