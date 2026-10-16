"""
Phase 4 Task 12 tests — refund data foundation & recovery state machine.

Covers the mandated areas: model/index definition, creation, duplicate and
concurrent-create protection (unique partial index is the authority),
atomic guarded state transitions (claim/completed/failed/cancel with
expected-state filters), invalid transitions, ownership for both domains,
cross-patient rejection, payment/order mismatch protection, authoritative
amount validation (over-refund / zero / negative / non-numeric),
INR-only, idempotent reuse, terminal-state immutability, domain-state
non-mutation, zero Razorpay calls, secret-free errors, and the absence of
any patient- or admin-reachable HTTP refund surface.

All Razorpay SDK/network calls are mocked (and asserted UNCALLED). No real
Razorpay servers are contacted and no real transactions are performed.
"""
import asyncio
import inspect
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.models.payment_refund import (
    PaymentRefund,
    REFUND_CURRENCY,
    REFUND_STATUSES,
    REFUNDABLE_PAYABLE_TYPES,
    TERMINAL_REFUND_STATUSES,
)
from app.repositories.payment_refund_repository import PaymentRefundRepository
from app.services.payment_refund_service import PaymentRefundService

TEST_KEY_ID = "rzp_test_unitkeyid123"
TEST_SECRET = "test_key_secret_for_unit_tests_only"

P1 = "111111111111111111111111"  # owning patient profile id
P2 = "222222222222222222222222"  # other patient profile id
APT = "333333333333333333333333"
BOOK = "444444444444444444444444"
ADMIN = "aaaaaaaaaaaaaaaaaaaaaaaa"
ORDER = "order_backend123"
PAY = "pay_backend456"


@pytest.fixture(autouse=True)
def razorpay_test_config(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", TEST_KEY_ID)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", TEST_SECRET)
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "whsec_test_only")


@pytest.fixture(autouse=True)
def mock_payment_refund_collection():
    """Local counterpart to the shared conftest Beanie mock (conftest
    predates the PaymentRefund model, and file discipline keeps this
    fixture here): make get_settings() resolvable so document construction
    works without a live database, following the established pattern from
    the webhook ingestion tests."""
    mock_settings = MagicMock()
    mock_settings.pymongo_collection = "payment_refunds"
    mock_settings.name = "payment_refunds"
    mock_settings.bson_encoders.get.return_value = None
    with patch.object(PaymentRefund, "get_settings", return_value=mock_settings):
        yield


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_appointment(**kw):
    defaults = dict(
        patient_id=P1,
        payment_id=PAY,
        payment_order_id=ORDER,
        billing_amount=500.0,
        billing_status="paid",
        payment_status="success",
        status="confirmed",
    )
    defaults.update(kw)
    a = MagicMock()
    a.id = APT
    for k, v in defaults.items():
        setattr(a, k, v)
    return a


def make_booking(**kw):
    defaults = dict(
        patient_id=P1,
        payment_id=PAY,
        payment_order_id=ORDER,
        billing_amount=1050.0,
        billing_status="paid",
        payment_status="success",
        status="confirmed",
    )
    defaults.update(kw)
    b = MagicMock()
    b.id = BOOK
    for k, v in defaults.items():
        setattr(b, k, v)
    return b


def make_refund(status="requested", payment_id=PAY, **kw):
    r = MagicMock()
    r.id = kw.get("id", "dddddddddddddddddddddddd")
    r.payable_type = kw.get("payable_type", "appointment")
    r.payable_id = kw.get("payable_id", APT)
    r.payment_id = payment_id
    r.payment_order_id = kw.get("payment_order_id", ORDER)
    r.amount = kw.get("amount", 50000)
    r.currency = REFUND_CURRENCY
    r.status = status
    r.reason = kw.get("reason", "refund_requested")
    r.requested_by = ADMIN
    r.created_at = datetime(2026, 9, 1, 12, 0)
    r.updated_at = datetime(2026, 9, 1, 12, 0)
    return r


def owned(domain, obj):
    """Patch domain loading so `obj` belongs to the requesting patient."""
    target = (
        "app.services.payment_refund_service.Appointment.get"
        if domain == "appointment"
        else "app.services.payment_refund_service.LaboratoryBooking.get"
    )
    return patch(target, new=AsyncMock(return_value=obj))


class _Stack:
    """Multi-patch context manager — same pattern as the stale-payment
    reconciliation test suite."""

    def __init__(self, patches):
        self._patches = patches

    def __enter__(self):
        from contextlib import ExitStack
        self._exit = ExitStack()
        return [self._exit.enter_context(p) for p in self._patches]

    def __exit__(self, *a):
        return self._exit.__exit__(*a)


def repo_lookups(completed=None, active=None, active_side_effect=None):
    """Patch the two repository lookup methods request_refund uses, so no
    real Beanie query machinery runs. The unique-index idempotency itself
    is proven separately (repository-level + index-definition tests)."""
    if active_side_effect is not None:
        active_mock = AsyncMock(side_effect=active_side_effect)
    else:
        active_mock = AsyncMock(return_value=active)
    return _Stack([
        patch(
            "app.repositories.payment_refund_repository."
            "PaymentRefundRepository.get_completed_by_payment_id",
            new=AsyncMock(return_value=completed),
        ),
        patch(
            "app.repositories.payment_refund_repository."
            "PaymentRefundRepository.get_active_by_payment_id",
            new=active_mock,
        ),
    ])


def insert_spy(return_value, raise_exc=None):
    """A bound insert replacement that captures the document being
    inserted (`self`) — functions set as class attributes bind self, so
    the spy receives the PaymentRefund instance the service built."""
    captured = {}

    async def _spy(self):
        captured["doc"] = self
        if raise_exc is not None:
            raise raise_exc
        return return_value

    return captured, patch.object(PaymentRefund, "insert", new=_spy)


async def _noop():
    return None


# ---------------------------------------------------------------------------
# 1 — Model / index definition
# ---------------------------------------------------------------------------

def test_1_model_index_definition():
    """CHECK 1: the unique partial idempotency index is declared with the
    codebase's IndexModel convention."""
    indexes = PaymentRefund.Settings.indexes
    uniq = [
        ix
        for ix in indexes
        if getattr(ix, "document", {}).get("name") == "uniq_active_refund_per_payment"
    ]
    assert len(uniq) == 1
    spec = uniq[0].document
    assert spec.get("unique") is True
    assert spec.get("key") in ([("payment_id", 1)], {"payment_id": 1})
    # Partial: terminal statuses are excluded so a failed/cancelled refund
    # does not permanently block a legitimate future retry...
    assert spec.get("partialFilterExpression") == {
        "status": {"$in": ["requested", "processing"]}
    }
    # ...and `completed` is excluded from the partial filter too — but a
    # completed refund can never yield a SECOND record because the service's
    # anti-double-refund gate blocks any new record for that payment.
    assert "completed" not in spec["partialFilterExpression"]["status"]["$in"]

    # Collection name follows project conventions.
    assert PaymentRefund.Settings.name == "payment_refunds"

    # No secrets/payload fields exist on the model.
    fields = set(PaymentRefund.model_fields.keys())
    for banned in (
        "raw_payload",
        "signature",
        "webhook_secret",
        "notes",
        "metadata",
    ):
        assert banned not in fields, banned


def test_1b_model_status_vocabulary_is_constrained():
    """CHECK 1b: exactly the five mandated statuses, three terminal."""
    assert REFUND_STATUSES == (
        "requested",
        "processing",
        "completed",
        "failed",
        "cancelled",
    )
    assert TERMINAL_REFUND_STATUSES == ("completed", "failed", "cancelled")
    assert REFUNDABLE_PAYABLE_TYPES == ("appointment", "laboratory")
    assert REFUND_CURRENCY == "INR"


def test_1c_model_default_status_is_requested():
    r = PaymentRefund(
        payable_type="appointment",
        payable_id=APT,
        payment_id=PAY,
        payment_order_id=ORDER,
        amount=50000,
        currency="INR",
        reason="test",
        requested_by=ADMIN,
    )
    assert r.status == "requested"
    assert r.currency == "INR"
    # Timestamps auto-populate server-side.
    assert isinstance(r.created_at, datetime)
    assert isinstance(r.updated_at, datetime)


# ---------------------------------------------------------------------------
# 2/3/18 — creation, duplicate protection, idempotent reuse
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_2_refund_creation_appointment():
    """CHECK 2: a paid appointment yields a requested refund with
    backend-authoritative facts."""
    appt = make_appointment()
    created = make_refund()
    captured, insert_patch = insert_spy(created)
    with repo_lookups(), owned("appointment", appt), insert_patch:
        refund = await PaymentRefundService.request_refund(
            "appointment", APT, ADMIN, P1
        )
    assert refund is created
    doc = captured["doc"]
    # Amount derives from the stored billing amount (500.0 -> 50000 paise).
    assert doc.amount == 50000
    assert doc.payment_id == PAY and doc.payment_order_id == ORDER
    assert doc.currency == "INR"
    assert doc.status == "requested"
    assert doc.requested_by == ADMIN


@pytest.mark.asyncio
async def test_2b_refund_creation_laboratory():
    """CHECK 2b: a paid laboratory booking yields a requested refund
    (1050.3000000000002 -> 105030 paise, exact Decimal path)."""
    booking = make_booking(billing_amount=1050.3000000000002)
    created = make_refund(amount=105030)
    captured, insert_patch = insert_spy(created)
    with repo_lookups(), owned("laboratory", booking), insert_patch:
        refund = await PaymentRefundService.request_refund(
            "laboratory", BOOK, ADMIN, P1
        )
    assert refund is created
    assert captured["doc"].amount == 105030
    assert refund.amount == 105030


@pytest.mark.asyncio
async def test_3_and_18_duplicate_and_repeated_request_reuses_existing():
    """CHECKS 3/18: repeated request for the same payment returns the
    EXISTING record; no second insert is attempted."""
    existing = make_refund()
    appt = make_appointment()
    captured, insert_patch = insert_spy(None)
    with repo_lookups(completed=None, active=existing), owned("appointment", appt), insert_patch:
        refund = await PaymentRefundService.request_refund(
            "appointment", APT, ADMIN, P1
        )
    assert refund is existing
    # No creation happened.
    assert "doc" not in captured


@pytest.mark.asyncio
async def test_3b_duplicate_protection_via_unique_index_lost_race():
    """CHECK 3b: two racing creates — the unique index (simulated by the
    repository's DuplicateKeyError path) admits exactly one record and the
    loser reuses the winner's record. The repository has NO application-
    level check-then-insert as its creation guard (structurally verified
    below)."""
    winner = make_refund()
    appt = make_appointment()
    captured, insert_patch = insert_spy(None, raise_exc=DuplicateKeyError("E11000"))
    # First active lookup (fast path) -> None; second (after lost race) -> winner.
    with repo_lookups(active_side_effect=[None, winner]), owned("appointment", appt), insert_patch:
        refund = await PaymentRefundService.request_refund(
            "appointment", APT, ADMIN, P1
        )
    assert refund is winner

    # Structural: the repository's create path is a bare insert whose
    # duplicate protection comes from the unique index (DuplicateKeyError
    # handling), never a find-then-insert.
    import app.repositories.payment_refund_repository as repo_mod
    src = inspect.getsource(repo_mod.PaymentRefundRepository.create_refund)
    assert "find_one" not in src
    assert "insert()" in src
    assert "DuplicateKeyError" in src or "PyMongoError" in src


# ---------------------------------------------------------------------------
# 4 — concurrent claim protection (repository-level atomicity)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_4_concurrent_claim_protection():
    """CHECK 4: two concurrent claims of the same refund — the guarded
    find_one_and_update admits exactly one; the loser gets None."""
    fake_coll = MagicMock()
    calls = {"n": 0}

    async def guarded(*a, **k):
        calls["n"] += 1
        return {"_id": "x", "status": "processing"} if calls["n"] == 1 else None

    fake_coll.find_one_and_update = AsyncMock(side_effect=guarded)
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        results = await asyncio.gather(
            PaymentRefundRepository.claim_for_processing("dddddddddddddddddddddddd"),
            PaymentRefundRepository.claim_for_processing("dddddddddddddddddddddddd"),
        )
    assert results[0] is not None
    assert results[1] is None
    # Every attempt carried the expected-state filter.
    for call in fake_coll.find_one_and_update.await_args_list:
        query = call.args[0]
        assert query["status"] == "requested"


@pytest.mark.asyncio
async def test_4b_claim_filter_only_matches_requested():
    """CHECK 4b: the claim's update filter includes the expected current
    state — structurally, the DB guard is the concurrency authority."""
    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(return_value={"_id": "x"})
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        await PaymentRefundRepository.claim_for_processing("dddddddddddddddddddddddd")
    query, update = fake_coll.find_one_and_update.await_args.args
    assert query["status"] == "requested"
    assert "_id" in query
    assert update["$set"]["status"] == "processing"
    assert "updated_at" in update["$set"]


# ---------------------------------------------------------------------------
# 5/6/7 — requested → processing → completed / failed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_5_requested_to_processing():
    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(
        return_value={"_id": "x", "status": "processing"}
    )
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        updated = await PaymentRefundRepository.claim_for_processing(
            "dddddddddddddddddddddddd"
        )
    assert updated["status"] == "processing"


@pytest.mark.asyncio
async def test_6_processing_to_completed():
    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(
        return_value={"_id": "x", "status": "completed"}
    )
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        updated = await PaymentRefundRepository.mark_completed(
            "dddddddddddddddddddddddd"
        )
    query, update = fake_coll.find_one_and_update.await_args.args
    assert query["status"] == "processing"
    assert update["$set"]["status"] == "completed"
    assert updated["status"] == "completed"


@pytest.mark.asyncio
async def test_7_processing_to_failed():
    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(
        return_value={"_id": "x", "status": "failed"}
    )
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        updated = await PaymentRefundRepository.mark_failed(
            "dddddddddddddddddddddddd"
        )
    query, update = fake_coll.find_one_and_update.await_args.args
    assert query["status"] == "processing"
    assert update["$set"]["status"] == "failed"


@pytest.mark.asyncio
async def test_7b_cancel_only_from_requested():
    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(
        return_value={"_id": "x", "status": "cancelled"}
    )
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        updated = await PaymentRefundRepository.cancel_if_requested(
            "dddddddddddddddddddddddd"
        )
    query, update = fake_coll.find_one_and_update.await_args.args
    assert query["status"] == "requested"
    assert update["$set"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_7c_terminal_states_match_no_transition():
    """A refund already in a terminal (or claimed) state never matches any
    transition filter — the DB refuses the write."""
    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(return_value=None)
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        rid = "dddddddddddddddddddddddd"
        assert await PaymentRefundRepository.claim_for_processing(rid) is None
        assert await PaymentRefundRepository.mark_completed(rid) is None
        assert await PaymentRefundRepository.mark_failed(rid) is None
        assert await PaymentRefundRepository.cancel_if_requested(rid) is None
    # Four guarded attempts, none matched.
    assert fake_coll.find_one_and_update.await_count == 4


# ---------------------------------------------------------------------------
# 8 — invalid state transitions rejected (state machine helper)
# ---------------------------------------------------------------------------

def test_8_invalid_state_transitions_rejected():
    """CHECK 8: the transition matrix forbids every non-machine edge."""
    allowed = {
        ("requested", "processing"),
        ("requested", "cancelled"),
        ("processing", "completed"),
        ("processing", "failed"),
    }
    for current in REFUND_STATUSES:
        for target in REFUND_STATUSES:
            result = PaymentRefundRepository.validate_status_transition(
                current, target
            )
            if (current, target) in allowed:
                assert result, f"{current} -> {target} must be allowed"
            else:
                assert not result, f"{current} -> {target} must be forbidden"
    # Terminal states can never start a transition.
    for terminal in TERMINAL_REFUND_STATUSES:
        for target in REFUND_STATUSES:
            assert not PaymentRefundRepository.validate_status_transition(
                terminal, target
            )


# ---------------------------------------------------------------------------
# 9/10 — ownership for both domains
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_9_appointment_payment_ownership():
    """CHECK 9: a paid appointment owned by the requesting patient passes
    the gate; a mismatched owner is 404."""
    appt = make_appointment()
    created = make_refund()
    captured, insert_patch = insert_spy(created)
    with repo_lookups(), owned("appointment", appt), insert_patch:
        refund = await PaymentRefundService.request_refund(
            "appointment", APT, ADMIN, P1
        )
    assert refund is created


@pytest.mark.asyncio
async def test_9b_appointment_cross_owner_rejected():
    appt = make_appointment(patient_id=P2)
    with owned("appointment", appt):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    assert e.value.status_code == 404
    # Existence is not leaked: same message as a missing record.
    assert e.value.detail == "Record not found"


@pytest.mark.asyncio
async def test_10_laboratory_payment_ownership():
    booking = make_booking()
    created = make_refund()
    captured, insert_patch = insert_spy(created)
    with repo_lookups(), owned("laboratory", booking), insert_patch:
        refund = await PaymentRefundService.request_refund(
            "laboratory", BOOK, ADMIN, P1
        )
    assert refund is created


@pytest.mark.asyncio
async def test_10b_laboratory_cross_owner_rejected():
    booking = make_booking(patient_id=P2)
    with owned("laboratory", booking):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("laboratory", BOOK, ADMIN, P1)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_10c_missing_ownership_scope_fails_closed():
    """No ownership scope -> 404 without even loading the record."""
    with patch(
        "app.services.payment_refund_service.Appointment.get", new=AsyncMock()
    ) as mock_get:
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, "")
    assert e.value.status_code == 404
    mock_get.assert_not_awaited()


# ---------------------------------------------------------------------------
# 11 — cross-patient rejection (no existence leak)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_11_cross_patient_rejection_is_indistinguishable_from_missing():
    """CHECK 11: another patient's record and a nonexistent record produce
    byte-identical 404s."""
    # Cross-patient
    with owned("appointment", make_appointment(patient_id=P2)):
        with pytest.raises(HTTPException) as e_cross:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    # Nonexistent
    with patch(
        "app.services.payment_refund_service.Appointment.get",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as e_missing:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    assert e_cross.value.status_code == e_missing.value.status_code == 404
    assert e_cross.value.detail == e_missing.value.detail == "Record not found"


# ---------------------------------------------------------------------------
# 12 — payment/order mismatch protection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_12_payment_order_ids_taken_from_domain_record_not_caller():
    """CHECK 12: the refund stores the payment/order ids from the backend
    domain record. The service accepts no payment/order parameters at all —
    a caller cannot fabricate either."""
    appt = make_appointment(
        payment_id="pay_real12345", payment_order_id="order_real123"
    )
    created = make_refund(payment_id="pay_real12345")
    captured, insert_patch = insert_spy(created)
    with repo_lookups(), owned("appointment", appt), insert_patch:
        refund = await PaymentRefundService.request_refund(
            "appointment", APT, ADMIN, P1
        )
    assert refund.payment_id == "pay_real12345"
    # The BUILT document carries the domain record's authoritative ids.
    assert captured["doc"].payment_id == "pay_real12345"
    assert captured["doc"].payment_order_id == "order_real123"

    # Structural: no fabrication surface exists.
    sig = inspect.signature(PaymentRefundService.request_refund)
    for banned in ("payment_id", "payment_order_id", "amount", "currency"):
        assert banned not in sig.parameters, banned


@pytest.mark.asyncio
async def test_12b_mismatched_stored_payment_is_not_refundable():
    """A record whose stored payment identity is incomplete/absent is
    rejected before anything is created."""
    for kwargs in (
        {"payment_id": None, "payment_order_id": ORDER},
        {"payment_id": PAY, "payment_order_id": None},
        {"payment_id": None, "payment_order_id": None},
    ):
        appt = make_appointment(**kwargs)
        with owned("appointment", appt):
            with pytest.raises(HTTPException) as e:
                await PaymentRefundService.request_refund(
                    "appointment", APT, ADMIN, P1
                )
        assert e.value.status_code == 409


# ---------------------------------------------------------------------------
# 13/14/15/16/17 — authoritative amount + currency validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_13_authoritative_amount_validation():
    """CHECK 13: refund amount always derives from stored billing_amount
    (never from any client value — none exists in the signature)."""
    for rupees, paise in [(500.0, 50000), (950.0, 95000), (1050.55, 105055)]:
        appt = make_appointment(billing_amount=rupees)
        created = make_refund(amount=paise)
        captured, insert_patch = insert_spy(created)
        with repo_lookups(), owned("appointment", appt), insert_patch:
            refund = await PaymentRefundService.request_refund(
                "appointment", APT, ADMIN, P1
            )
        assert refund.amount == paise


@pytest.mark.asyncio
async def test_14_over_refund_rejected():
    """CHECK 14: the over-refund invariant — a requested amount above the
    authoritative amount is invalid; and the service structurally cannot
    issue one because no amount parameter exists."""
    assert PaymentRefundService.validate_refund_amount(50001, 50000) is False
    assert PaymentRefundService.validate_refund_amount(50000, 50000) is True
    assert PaymentRefundService.validate_refund_amount(1, 50000) is True
    sig = inspect.signature(PaymentRefundService.request_refund)
    assert "amount" not in sig.parameters


@pytest.mark.asyncio
async def test_15_zero_amount_rejected():
    """CHECK 15: zero stored amount fails closed."""
    appt = make_appointment(billing_amount=0.0)
    with repo_lookups(), owned("appointment", appt):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_16_negative_amount_rejected():
    """CHECK 16: negative stored amount fails closed."""
    appt = make_appointment(billing_amount=-500.0)
    with repo_lookups(), owned("appointment", appt):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_17_inr_only_validation():
    """CHECK 17: INR is the only valid refund currency; records are always
    created INR."""
    assert PaymentRefundService.validate_currency("INR") is True
    for bad in ("USD", "EUR", "usd", "inr", "", None):
        assert PaymentRefundService.validate_currency(bad) is False

    appt = make_appointment()
    created = make_refund()
    captured, insert_patch = insert_spy(created)
    with repo_lookups(), owned("appointment", appt), insert_patch:
        refund = await PaymentRefundService.request_refund(
            "appointment", APT, ADMIN, P1
        )
    assert refund.currency == "INR"
    assert captured["doc"].currency == "INR"


# ---------------------------------------------------------------------------
# 19/20 — terminal refunds cannot be overwritten or revived
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_19_completed_refund_cannot_be_overwritten():
    """CHECKS 19/20: a completed refund blocks any new refund record for
    the same payment (anti-double-refund gate), and no repository
    transition can start from a terminal state (test_7c proves the
    filters). Here: the completed gate rejects with 409."""
    appt = make_appointment()
    completed = make_refund(status="completed")
    completed_lookup = AsyncMock(return_value=completed)
    with owned("appointment", appt), patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefundRepository.get_completed_by_payment_id",
        new=completed_lookup,
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    assert e.value.status_code == 409
    assert "already been refunded" in e.value.detail
    completed_lookup.assert_awaited_once_with(PAY)


@pytest.mark.asyncio
async def test_20_failed_refund_cannot_silently_become_completed():
    """CHECK 20 (state machine level): failed → completed is not a legal
    edge; the atomic filter can never match a failed record."""
    assert (
        PaymentRefundRepository.validate_status_transition("failed", "completed")
        is False
    )
    assert (
        PaymentRefundRepository.validate_status_transition("failed", "processing")
        is False
    )
    # And the repository transition itself refuses (guard mismatch).
    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(return_value=None)
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        assert (
            await PaymentRefundRepository.mark_completed("dddddddddddddddddddddddd")
            is None
        )
    query = fake_coll.find_one_and_update.await_args.args[0]
    assert query["status"] == "processing"  # never matches "failed"


# ---------------------------------------------------------------------------
# 21 — refund creation does not mutate payment state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_21_refund_creation_does_not_mutate_payment_state():
    """CHECK 21: creating a refund record performs NO write on the
    appointment/booking — no save, no atomic transition, no field change."""
    appt = make_appointment()
    appt.save = AsyncMock()
    created = make_refund()
    captured, insert_patch = insert_spy(created)
    with repo_lookups(), owned("appointment", appt), insert_patch:
        await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    # The domain object was never written to.
    appt.save.assert_not_awaited()
    assert appt.billing_status == "paid"
    assert appt.payment_status == "success"
    assert appt.status == "confirmed"
    assert appt.payment_id == PAY
    assert appt.payment_order_id == ORDER

    # Structural: the refund service imports no write path for the domain
    # objects — check IMPORT STATEMENTS only (docstrings may legitimately
    # reference conventions by name).
    import app.services.payment_refund_service as mod
    import_lines = [
        line.strip()
        for line in inspect.getsource(mod).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    joined = "\n".join(import_lines)
    for banned in (
        "payment_repository",
        "appointment_service",
        "laboratory_service",
        "AppointmentRepository",
        "LaboratoryBookingRepository",
    ):
        assert banned not in joined, banned
    # And no repository-level payment write helper is referenced anywhere
    # in executable lines (non-comment, non-docstring approximation).
    code_lines = [
        line for line in inspect.getsource(mod).splitlines()
        if not line.strip().startswith(("#", '"', "'"))
    ]
    code_text = "\n".join(code_lines)
    for banned in (
        "mark_appointment_paid",
        "mark_laboratory_paid",
        "mark_laboratory_failed",
        "expire_appointment_pending_payment",
        "expire_laboratory_pending_payment",
    ):
        assert banned not in code_text, banned


# ---------------------------------------------------------------------------
# 22 — no Razorpay network calls
# ---------------------------------------------------------------------------

def test_22_no_razorpay_refund_calls_anywhere():
    """CHECK 22: no raw Razorpay refund/network surface in the refund
    foundation — source-level proof across all three refund modules.

    Task 13 update: the execution service is ALLOWED to import exactly
    the two sanctioned client-boundary helpers (create_refund /
    fetch_refund) plus the safe error taxonomy; every raw SDK/HTTP
    interaction remains confined to razorpay_client.py (pinned by the
    Task 13 suite, CHECK 30). The model and repository still reference
    the Razorpay layer not at all.
    """
    import app.models.payment_refund as m
    import app.repositories.payment_refund_repository as r
    import app.services.payment_refund_service as s

    # Model + repository: nothing from the Razorpay layer, ever.
    for mod in (m, r):
        src = inspect.getsource(mod)
        for token in (
            "refund.create",
            ".refund(",
            "payment.fetch",
            "order.fetch",
            "order.payments",
            "create_order",
            "fetch_payment",
            "fetch_order",
            "fetch_order_payments",
            "get_razorpay_client",
            "verify_payment_signature",
            "verify_webhook_signature",
            "Client(",
            "httpx",
            "requests.",
            "urllib",
            "razorpay_client",
            "import razorpay",
        ):
            assert token not in src, f"{mod.__name__} references {token}"

    # Service: raw SDK/HTTP tokens forbidden; only the sanctioned client
    # helper imports may appear.
    src = inspect.getsource(s)
    for token in (
        "refund.create",
        ".refund(",
        "payment.fetch",
        "order.fetch",
        "order.payments",
        "create_order",
        "fetch_payment",
        "fetch_order",
        "fetch_order_payments",
        "get_razorpay_client",
        "verify_payment_signature",
        "verify_webhook_signature",
        "Client(",
        "httpx",
        "requests.",
        "urllib",
        "import razorpay",
    ):
        assert token not in src, f"{s.__name__} references {token}"
    allowed_helpers = {
        "RazorpayConfigError,",
        "RazorpayRefundOutcome,",
        "RazorpayRequestError,",
        "create_refund,",
        "fetch_refund,",
    }
    helper_import_lines = [
        line.strip()
        for line in src.splitlines()
        if line.strip().startswith(("Razorpay", "create_refund", "fetch_refund"))
        and line.strip().endswith(",")
    ]
    assert set(helper_import_lines) <= allowed_helpers, helper_import_lines
    # The import comes from the sanctioned client module boundary.
    assert "from app.core.razorpay_client import (" in src


@pytest.mark.asyncio
async def test_22b_no_razorpay_module_loads_during_refund_flow():
    """CHECK 22b (runtime): executing the refund flow never invokes any
    Razorpay helper — every network-touching symbol is asserted UNCALLED."""
    appt = make_appointment()
    created = make_refund()
    captured, insert_patch = insert_spy(created)
    with repo_lookups(), owned("appointment", appt), insert_patch, patch(
        "app.core.razorpay_client.get_razorpay_client"
    ) as mock_client, patch(
        "app.core.razorpay_client.create_order"
    ) as mock_order, patch(
        "app.core.razorpay_client.fetch_payment"
    ) as mock_fetch, patch(
        "app.core.razorpay_client.fetch_order"
    ) as mock_forder, patch(
        "app.core.razorpay_client.fetch_order_payments"
    ) as mock_opay:
        await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    mock_client.assert_not_called()
    mock_order.assert_not_called()
    mock_fetch.assert_not_called()
    mock_forder.assert_not_called()
    mock_opay.assert_not_called()


# ---------------------------------------------------------------------------
# 23 — no secrets in errors/logs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_23_no_secrets_in_errors_or_logs(caplog):
    """CHECK 23: every failure path carries a safe detail; neither the key
    secret nor the webhook secret ever appears in error details, including
    when the repository's lost-race resolution cannot find a winner."""
    import logging as _logging

    appt = make_appointment()
    captured, insert_patch = insert_spy(None, raise_exc=DuplicateKeyError("E11000"))
    # Lost race AND the re-read finds no winner -> safe 503.
    with repo_lookups(active_side_effect=[None, None]), owned("appointment", appt), insert_patch:
        with caplog.at_level(_logging.ERROR):
            with pytest.raises(HTTPException) as e:
                await PaymentRefundService.request_refund(
                    "appointment", APT, ADMIN, P1
                )
    assert e.value.status_code == 503
    assert "secret" not in e.value.detail.lower()
    assert "E11000" not in e.value.detail
    # The service never logs credential material.
    assert TEST_SECRET not in caplog.text

    # Static details in the module contain no credential-like content and
    # the module never interpolates settings into error messages.
    import app.services.payment_refund_service as mod
    src = inspect.getsource(mod)
    for banned in ("RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"):
        assert banned not in src, banned
    for detail in (
        "Invalid refundable type",
        "A requesting user is required",
        "Record not found",
        "This record has no online payment to refund",
        "This record is not in a refundable paid state",
        "This payment has already been refunded",
        "Could not record the refund request. Please try again.",
    ):
        assert TEST_SECRET not in detail and "secret" not in detail.lower()


# ---------------------------------------------------------------------------
# 24 — no frontend-accessible arbitrary refund mutation (no HTTP surface)
# ---------------------------------------------------------------------------

def test_24_no_http_refund_surface_exists():
    """CHECK 24: no refund route exists anywhere in the app — patients (or
    anyone) cannot reach a refund mutation over HTTP. Pins the Task 11
    invariant test_no_refund_surface_exists and the §7 'internal only'
    decision."""
    from app.main import app as fastapi_app

    routes = [getattr(r, "path", "") for r in fastapi_app.routes]
    assert not any("refund" in p.lower() for p in routes), routes

    # Structural: no api module references the refund service or model —
    # nothing over HTTP can reach the refund foundation at all.
    import os
    api_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app",
        "api",
    )
    for fname in os.listdir(api_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(api_dir, fname), encoding="utf-8") as f:
            api_src = f.read()
        assert "PaymentRefund" not in api_src, fname
        assert "payment_refund" not in api_src, fname


def test_24b_patient_cannot_mutate_refund_state_via_existing_endpoints():
    """CHECK 24b: the refund foundation is not reachable through the
    frontend service layer either — it contains no refund calls."""
    import os
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    api_js = os.path.join(root, "frontend", "src", "services", "api.js")
    with open(api_js, encoding="utf-8") as f:
        src = f.read()
    assert "refund" not in src.lower()


# ---------------------------------------------------------------------------
# 25 — regression guards for Tasks 1–11 invariants
# ---------------------------------------------------------------------------

def test_25_existing_payment_transitions_untouched():
    """CHECK 25: Task 12 adds no transitions and changes no existing
    payment/expiry behavior — the Task 1-11 write paths are intact and the
    refund modules are entirely additive."""
    import app.repositories.payment_repository as pr

    src = inspect.getsource(pr)
    for marker in (
        "mark_appointment_paid",
        "mark_laboratory_paid",
        "mark_laboratory_failed",
        "expire_appointment_pending_payment",
        "expire_laboratory_pending_payment",
    ):
        assert marker in src

    # Expiry policy defaults unchanged (Task 9/11 invariant).
    assert settings.PAYMENT_RECONCILIATION_ENABLED is False
    assert settings.PAYMENT_PENDING_EXPIRY_MINUTES is None

    # Existing appointment/laboratory indexes untouched (untouched files).
    from app.models.appointment import Appointment
    from app.models.laboratory_booking import LaboratoryBooking

    apt_index_names = [
        getattr(ix, "document", {}).get("name")
        for ix in Appointment.Settings.indexes
    ]
    lab_index_names = [
        getattr(ix, "document", {}).get("name")
        for ix in LaboratoryBooking.Settings.indexes
    ]
    assert "uniq_patient_date_slot" in apt_index_names
    assert "uniq_patient_date_slot" in lab_index_names

    # Registration: PaymentRefund is registered through init_beanie only.
    import app.database as db
    db_src = inspect.getsource(db)
    assert "PaymentRefund" in db_src


def test_25b_webhook_and_verification_flows_unmodified():
    """The webhook ingestion/reconciliation and verification modules carry
    no refund code — Task 12 is purely additive."""
    import app.api.webhooks as wh
    import app.services.payment_service as ps
    import app.services.webhook_reconciliation_service as wrs

    for mod in (wh, ps, wrs):
        src = inspect.getsource(mod)
        # No code tokens (docstring prose explaining "no refund API is
        # called" is tolerable; executable references are not).
        assert "refund.create" not in src
        assert ".refund(" not in src
        assert "PaymentRefund" not in src
        assert "payment_refund_service" not in src


# ---------------------------------------------------------------------------
# §9 — remaining failure semantics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_9c_nonexistent_appointment():
    with patch(
        "app.services.payment_refund_service.Appointment.get",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_9d_nonexistent_laboratory_booking():
    with patch(
        "app.services.payment_refund_service.LaboratoryBooking.get",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("laboratory", BOOK, ADMIN, P1)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_9e_invalid_payable_type_rejected():
    for bad in ("care_plan", "", "APPOINTMENT", "laboratory_booking"):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund(bad, APT, ADMIN, P1)
        assert e.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"billing_status": "pending", "payment_status": "pending",
         "status": "pending_payment"},
        {"billing_status": "failed", "payment_status": "failed",
         "status": "failed"},
        {"billing_status": "paid", "payment_status": "expired",
         "status": "cancelled"},
        {"billing_status": "paid", "payment_status": "success",
         "status": "cancelled"},
        {"billing_status": "paid", "payment_status": "success",
         "status": "completed"},
    ],
)
async def test_9f_non_refundable_domain_states_rejected(kwargs):
    """Unpaid / failed / expired / cancelled / completed records are never
    refundable — the refundable-state gate rejects them all."""
    appt = make_appointment(**kwargs)
    with owned("appointment", appt):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_9g_offline_paid_record_is_not_refundable():
    """An offline record marked paid carries no online payment reference —
    the payment-identity gate rejects it before state checks."""
    appt = make_appointment(payment_id=None, payment_order_id=None)
    with owned("appointment", appt):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_9h_transient_create_failure_resolves_safely():
    """A transient insert failure with no winner resolves to a safe 503
    (fail closed, no raw database error)."""
    appt = make_appointment()
    captured, insert_patch = insert_spy(None)  # insert returns None (transient)
    with repo_lookups(), owned("appointment", appt), insert_patch:
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.request_refund("appointment", APT, ADMIN, P1)
    assert e.value.status_code == 503
    assert "try again" in e.value.detail.lower()


@pytest.mark.asyncio
async def test_9i_reason_is_bounded_and_safe():
    """The audit reason is truncated; an empty reason falls back to the
    default."""
    appt = make_appointment()
    created = make_refund()
    captured = {}

    async def spy(self):
        captured["reason"] = self.reason
        return created

    with repo_lookups(), owned("appointment", appt), \
            patch.object(PaymentRefund, "insert", new=spy):
        await PaymentRefundService.request_refund(
            "appointment", APT, ADMIN, P1, reason="x" * 5000
        )
    assert len(captured["reason"]) == 256

    with repo_lookups(), owned("appointment", appt), \
            patch.object(PaymentRefund, "insert", new=spy):
        await PaymentRefundService.request_refund(
            "appointment", APT, ADMIN, P1, reason="   "
        )
    assert captured["reason"] == "refund_requested"


def test_amount_helpers_reject_bad_input():
    """The exact-money helper rejects None/non-numeric input (fail
    closed), mirroring the PaymentService conversion discipline."""
    with pytest.raises(HTTPException) as e:
        PaymentRefundService._authoritative_refund_amount_paise(
            None, "appointment"
        )
    assert e.value.status_code == 409

    with pytest.raises(HTTPException) as e:
        PaymentRefundService._authoritative_refund_amount_paise(
            "abc", "laboratory"
        )
    assert e.value.status_code == 409

    # Float-noise values convert exactly.
    assert (
        PaymentRefundService._authoritative_refund_amount_paise(
            1050.3000000000002, "laboratory"
        )
        == 105030
    )
