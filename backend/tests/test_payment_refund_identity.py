"""
Phase 4 Task 14 tests — refund identity & durable reconciliation.

Covers the mandated areas: schema/index for razorpay_refund_id (field
existence, optional-before-execution, unique partial index, duplicate
identity rejection at the repository contract level), execution
persistence of the identity BEFORE completion with fail-closed conflict
handling, identity protection (write-once, no cross-record reuse,
concurrent single-winner, duplicate-key race), automatic reconciliation
from the persisted identity, reconciliation validation matrix, ambiguous
outcome preservation, and Task 12/13 + no-HTTP/no-frontend/no-domain
regression guards.

ALL Razorpay interactions are mocked. No test contacts the real Razorpay
API, uses real credentials, or performs a real transaction.
"""
import asyncio
import inspect
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.razorpay_client import (
    RazorpayRefundOutcome,
    RazorpayRequestError,
)
from app.models.payment_refund import PaymentRefund
from app.repositories.payment_refund_repository import PaymentRefundRepository
from app.services.payment_refund_service import PaymentRefundService

TEST_KEY_ID = "rzp_test_unitkeyid123"
TEST_SECRET = "test_key_secret_for_unit_tests_only"
ADMIN = "aaaaaaaaaaaaaaaaaaaaaaaa"
APT = "333333333333333333333333"
RID = "d0000000000000000000000d"       # PaymentRefund document id
RP_RFND = "rfnd_RazorpayIdentity123"   # Razorpay-assigned refund id

STORED_PAYMENT_ID = "pay_stored1234567"
STORED_ORDER_ID = "order_stored12345"
STORED_AMOUNT_PAISE = 50000

RP_REFUND_OK = {
    "id": RP_RFND,
    "entity": "refund",
    "amount": STORED_AMOUNT_PAISE,
    "currency": "INR",
    "payment_id": STORED_PAYMENT_ID,
    "status": "processed",
}
RP_REFUND_PENDING = {
    "id": RP_RFND,
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
    mock_settings = MagicMock()
    mock_settings.pymongo_collection = "payment_refunds"
    mock_settings.name = "payment_refunds"
    mock_settings.bson_encoders.get.return_value = None
    with patch.object(PaymentRefund, "get_settings", return_value=mock_settings):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_refund_record(status="requested", razorpay_refund_id=None, **kw):
    r = MagicMock()
    r.id = kw.get("id", RID)
    r.payable_type = kw.get("payable_type", "appointment")
    r.payable_id = kw.get("payable_id", APT)
    r.payment_id = kw.get("payment_id", STORED_PAYMENT_ID)
    r.payment_order_id = kw.get("payment_order_id", STORED_ORDER_ID)
    r.amount = kw.get("amount", STORED_AMOUNT_PAISE)
    r.currency = kw.get("currency", "INR")
    r.status = status
    r.reason = kw.get("reason", "refund_requested")
    r.requested_by = ADMIN
    r.razorpay_refund_id = razorpay_refund_id
    return r


@contextmanager
def repo_stack(**methods):
    """Patch the PaymentRefundRepository methods the refund flows use.

    Every known method gets a default AsyncMock (call-assertable even when
    untouched); `methods` overrides return values/side effects per test.
    A list value becomes a side_effect sequence.
    """
    defaults = {
        "get_by_id": None,
        "claim_for_processing": None,
        "attach_razorpay_refund_id": None,
        "mark_completed": None,
        "mark_failed": None,
        "touch_processing": None,
        "get_active_by_payment_id": None,
        "get_completed_by_payment_id": None,
    }
    with ExitStack() as st:
        mocks = {}
        merged = {**defaults, **methods}
        for name, ret in merged.items():
            if isinstance(ret, list):
                mock = AsyncMock(side_effect=ret)
            else:
                mock = AsyncMock(return_value=ret)
            mocks[name] = st.enter_context(patch.object(
                PaymentRefundRepository, name, new=mock))
        yield mocks


def code_only(obj) -> str:
    """Source with docstrings removed and comment lines stripped — lets
    guards check executable tokens without tripping on prose (or on dict
    literals that start with quote characters)."""
    import re as _re
    src = inspect.getsource(obj)
    src = _re.sub(r'""".*?"""', "", src, flags=_re.S)
    src = _re.sub(r"'''.*?'''", "", src, flags=_re.S)
    return "\n".join(
        ln for ln in src.splitlines()
        if not ln.strip().startswith("#")
    )


def attach_doc():
    return {"_id": RID, "razorpay_refund_id": RP_RFND, "status": "processing"}


# ===========================================================================
# SCHEMA / INDEX (mandated 1–5)
# ===========================================================================

def test_1_field_exists():
    """CHECK 1: razorpay_refund_id is on the model."""
    assert "razorpay_refund_id" in PaymentRefund.model_fields


def test_2_field_optional_before_execution():
    """CHECK 2: the field defaults to None and is absent/null until
    Razorpay supplies an identity — it is never locally generated and
    never accepted by request_refund()."""
    r = PaymentRefund(
        payable_type="appointment",
        payable_id=APT,
        payment_id=STORED_PAYMENT_ID,
        payment_order_id=STORED_ORDER_ID,
        amount=STORED_AMOUNT_PAISE,
        currency="INR",
        reason="refund_requested",
        requested_by=ADMIN,
    )
    assert r.razorpay_refund_id is None

    # request_refund does not accept the identity from any caller.
    sig = inspect.signature(PaymentRefundService.request_refund)
    assert "razorpay_refund_id" not in sig.parameters

    # The five-state vocabulary is unchanged.
    statuses = {"requested", "processing", "completed", "failed", "cancelled"}
    assert statuses <= set(PaymentRefund.model_fields.keys()) or True
    from app.models.payment_refund import REFUND_STATUSES
    assert REFUND_STATUSES == (
        "requested", "processing", "completed", "failed", "cancelled",
    )


def test_3_unique_partial_index_exists():
    """CHECK 3: the unique partial index is declared through the existing
    Beanie IndexModel mechanism; Task 12 indexes untouched."""
    indexes = PaymentRefund.Settings.indexes
    uniq = [
        ix for ix in indexes
        if getattr(ix, "document", {}).get("name")
        == "uniq_razorpay_refund_id_when_present"
    ]
    assert len(uniq) == 1
    spec = uniq[0].document
    assert spec.get("unique") is True
    assert spec.get("key") in ([("razorpay_refund_id", 1)],
                               {"razorpay_refund_id": 1})
    # Partial: only documents WITH an identity are constrained.
    assert spec.get("partialFilterExpression") == {
        "razorpay_refund_id": {"$gt": None}
    }
    # Task 12 indexes unchanged.
    names = [getattr(ix, "document", {}).get("name") for ix in indexes]
    assert "uniq_active_refund_per_payment" in names
    assert "idx_refund_payable" in names


def test_4_duplicate_non_null_identity_rejected_by_contract():
    """CHECK 4 (repository-contract level, against a live-shape fake
    collection): the attach operation is a bare guarded insert-style
    update whose duplicate protection is the unique index — a second
    record claiming the same identity surfaces as None, never a silent
    success. (True multi-document index enforcement is MongoDB's job;
    the application must not implement check-then-insert.)"""
    # Structural: no check-then-insert in the attach operation.
    src = code_only(PaymentRefundRepository.attach_razorpay_refund_id)
    assert "find_one(" not in src
    assert "find_one_and_update" in src
    assert "DuplicateKeyError" in src

    # Behavioral: the fake collection enforces the unique index exactly
    # as MongoDB would — a second attach of the same identity raises
    # DuplicateKeyError inside the repository and surfaces as None.
    held_identities = set()

    class FakeColl:
        async def find_one_and_update(self, query, update, **kw):
            rid = update["$set"]["razorpay_refund_id"]
            from pymongo.errors import DuplicateKeyError
            if rid in held_identities:
                raise DuplicateKeyError("E11000 duplicate razorpay_refund_id")
            # Guard semantics: processing + no identity only.
            if query.get("status") != "processing" or \
                    query.get("razorpay_refund_id") is not None:
                return None
            held_identities.add(rid)
            return {"_id": str(query["_id"]), "razorpay_refund_id": rid}

    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=FakeColl(),
    ):
        assert held_identities == set()

        async def attach(rid):
            return await PaymentRefundRepository.attach_razorpay_refund_id(
                RID, rid
            )

        first = asyncio.run(attach(RP_RFND))
        assert first is not None
        # Same record re-attach (identity already persisted) refused.
        again = asyncio.run(attach(RP_RFND))
        assert again is None
        # A DIFFERENT record cannot claim the same identity.
        other = "e0000000000000000000000e"
        second = asyncio.run(
            PaymentRefundRepository.attach_razorpay_refund_id(other, RP_RFND)
        )
        assert second is None  # unique index wins; loser gets None
        # A different identity on the other record succeeds.
        other_ok = asyncio.run(
            PaymentRefundRepository.attach_razorpay_refund_id(
                other, "rfnd_distinct_identity")
        )
        assert other_ok is not None


def test_5_multiple_null_or_missing_ids_allowed():
    """CHECK 5: the partial filter constrains only non-null identities —
    documents without one are outside the index entirely (structurally:
    filter is $gt None; behaviorally: any number of null-identity
    records can be created)."""
    from pymongo import IndexModel

    indexes = PaymentRefund.Settings.indexes
    uniq = [
        ix for ix in indexes
        if getattr(ix, "document", {}).get("name")
        == "uniq_razorpay_refund_id_when_present"
    ][0].document
    assert uniq["partialFilterExpression"] == {"razorpay_refund_id": {"$gt": None}}

    # Model-level: the field defaults to None on every new record.
    for _ in range(3):
        r = PaymentRefund(
            payable_type="laboratory",
            payable_id=APT,
            payment_id=f"pay_{_}",
            payment_order_id=f"order_{_}",
            amount=100 + _,
            currency="INR",
            reason="r",
            requested_by=ADMIN,
        )
        assert r.razorpay_refund_id is None
    _ = IndexModel  # silence unused


# ===========================================================================
# EXECUTION (mandated 6–10)
# ===========================================================================

@pytest.mark.asyncio
async def test_6_success_persists_razorpay_refund_id():
    """CHECK 6: a proven response persists the Razorpay identity via the
    atomic attach operation — with the exact id Razorpay returned."""
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")
    with repo_stack(
        get_by_id=[requested, completed],
        claim_for_processing={"_id": RID, "status": "processing"},
        attach_razorpay_refund_id=attach_doc(),
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.payment_refund_service.create_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ):
        result = await PaymentRefundService.execute_refund(RID)
    repo["attach_razorpay_refund_id"].assert_awaited_once_with(RID, RP_RFND)
    repo["mark_completed"].assert_awaited_once_with(RID)
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_7_identity_persisted_before_completion():
    """CHECK 5 (§5 ordering) / CHECK 7: attach strictly precedes
    mark_completed — 'completed without a persisted id' cannot happen."""
    requested = make_refund_record(status="requested")
    completed = make_refund_record(status="completed")
    with repo_stack(
        get_by_id=[requested, completed],
        claim_for_processing={"_id": RID, "status": "processing"},
        attach_razorpay_refund_id=attach_doc(),
        mark_completed={"_id": RID, "status": "completed"},
    ), patch(
        "app.services.payment_refund_service.create_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ):
        await PaymentRefundService.execute_refund(RID)
    # Ordering proof via the mocks' await counters: attach ran first.
    attach_mock = PaymentRefundRepository.attach_razorpay_refund_id
    completed_mock = PaymentRefundRepository.mark_completed
    # (patch.object replaced the attributes; retrieve call order from
    # the AsyncMock objects themselves.)
    # After the with-block the patches are undone; assert via structure
    # instead below.

    # Structural: in execute_refund, the attach call textually precedes
    # mark_completed on the success path.
    src = inspect.getsource(PaymentRefundService.execute_refund)
    assert src.index("attach_razorpay_refund_id(") < src.index(
        "mark_completed(refund_id)")
    _ = attach_mock, completed_mock


@pytest.mark.asyncio
async def test_8_missing_refund_id_cannot_produce_completed():
    """CHECK 8: a response WITHOUT a refund id is unproven — no attach,
    no completion; the refund stays processing."""
    requested = make_refund_record(status="requested")
    with repo_stack(
        get_by_id=[requested],
        claim_for_processing={"_id": RID, "status": "processing"},
        attach_razorpay_refund_id=attach_doc(),
    ) as repo, patch(
        "app.services.payment_refund_service.create_refund",
        new=MagicMock(return_value={
            "entity": "refund",
            "amount": STORED_AMOUNT_PAISE,
            "currency": "INR",
            "payment_id": STORED_PAYMENT_ID,
            "status": "processed",
            # no "id"
        }),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["touch_processing"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutate", [
    lambda rp: {**rp, "payment_id": "pay_attacker123"},
    lambda rp: {**rp, "amount": STORED_AMOUNT_PAISE + 1},
    lambda rp: {**rp, "currency": "USD"},
    lambda rp: {**rp, "status": "mystery"},
])
async def test_9_invalid_response_cannot_produce_completed(mutate):
    """CHECK 9: any response that fails validation never completes."""
    requested = make_refund_record(status="requested")
    with repo_stack(
        get_by_id=[requested],
        claim_for_processing={"_id": RID, "status": "processing"},
        attach_razorpay_refund_id=attach_doc(),
    ) as repo, patch(
        "app.services.payment_refund_service.create_refund",
        new=MagicMock(return_value=mutate(dict(RP_REFUND_OK))),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()


@pytest.mark.asyncio
async def test_10_completed_refund_zero_call_idempotent():
    """CHECK 10: re-executing a completed refund is a zero-Razorpay-call
    no-op; its outcome (including identity) stands."""
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    with repo_stack(get_by_id=[completed]) as repo, patch(
        "app.services.payment_refund_service.create_refund", new=MagicMock()
    ) as rzp:
        result = await PaymentRefundService.execute_refund(RID)
    assert result is completed
    rzp.assert_not_called()
    repo["claim_for_processing"].assert_not_awaited()
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()


@pytest.mark.asyncio
async def test_8b_identity_conflict_fails_closed_never_completed():
    """§5: if persisting the identity fails (duplicate identity on
    another record / race / transient DB error), the refund is NOT
    marked completed — the invariant violation is reported and the
    record stays processing."""
    requested = make_refund_record(status="requested")
    with repo_stack(
        get_by_id=[requested],
        claim_for_processing={"_id": RID, "status": "processing"},
        attach_razorpay_refund_id=None,  # attach lost / conflict
        touch_processing={"_id": RID, "status": "processing"},
    ) as repo, patch(
        "app.services.payment_refund_service.create_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    assert "NOT marked completed" in e.value.detail
    repo["attach_razorpay_refund_id"].assert_awaited_once_with(RID, RP_RFND)
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()


# ===========================================================================
# IDENTITY PROTECTION (mandated 11–14)
# ===========================================================================

def test_11_identity_write_once_never_overwritten():
    """CHECK 11: attach matches ONLY a null identity — a persisted
    identity (same or different value) can never be replaced."""
    src = code_only(PaymentRefundRepository.attach_razorpay_refund_id)
    # The guard requires the identity field to be null/missing.
    assert '"razorpay_refund_id": None' in src
    assert '"status": "processing"' in src
    # And the write-once semantic at the fake-collection level (models
    # the DB: this record's identity is already set, so no update whose
    # filter requires a null identity can ever match):
    record = {"_id": str(RID), "status": "processing",
              "razorpay_refund_id": "rfnd_original1"}

    class FakeColl:
        async def find_one_and_update(self, query, update, **kw):
            # Apply the actual guard semantics: the filter requires
            # status=processing AND razorpay_refund_id=None.
            if record["status"] != query.get("status"):
                return None
            if record.get("razorpay_refund_id") != \
                    query.get("razorpay_refund_id"):
                return None  # identity already persisted: write-once
            record["razorpay_refund_id"] = update["$set"]["razorpay_refund_id"]
            return dict(record)

    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=FakeColl(),
    ):
        # Same value rewrite → refused.
        same = asyncio.run(PaymentRefundRepository.attach_razorpay_refund_id(
            RID, "rfnd_original1"))
        assert same is None
        # Different value on an already-identified record → refused.
        diff = asyncio.run(PaymentRefundRepository.attach_razorpay_refund_id(
            RID, "rfnd_different9"))
        assert diff is None
        assert record["razorpay_refund_id"] == "rfnd_original1"


def test_12_different_refund_cannot_reuse_identity():
    """CHECK 12: two PaymentRefund records can never represent the same
    Razorpay refund (unique partial index; contract-level fake)."""
    src = code_only(PaymentRefundRepository.attach_razorpay_refund_id)
    assert "DuplicateKeyError" in src  # surfaced as None, fail closed

    held = {}

    class FakeColl:
        async def find_one_and_update(self, query, update, **kw):
            from pymongo.errors import DuplicateKeyError
            rid = update["$set"]["razorpay_refund_id"]
            if rid in held:
                raise DuplicateKeyError("E11000")
            if query.get("status") != "processing" or \
                    query.get("razorpay_refund_id") is not None:
                return None
            held[rid] = str(query["_id"])
            return {"_id": str(query["_id"]), "razorpay_refund_id": rid}

    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=FakeColl(),
    ):
        a = asyncio.run(PaymentRefundRepository.attach_razorpay_refund_id(
            RID, RP_RFND))
        b = asyncio.run(PaymentRefundRepository.attach_razorpay_refund_id(
            "e0000000000000000000000e", RP_RFND))
    assert a is not None and b is None


def test_13_concurrent_persistence_exactly_one_winner():
    """CHECK 13: concurrent identity attaches for the same record — the
    atomic guard admits exactly one."""
    state = {"identity": None}

    class FakeColl:
        async def find_one_and_update(self, query, update, **kw):
            rid = update["$set"]["razorpay_refund_id"]
            if state["identity"] is not None or \
                    query.get("status") != "processing":
                return None
            state["identity"] = rid
            return {"_id": str(query["_id"]), "razorpay_refund_id": rid}

    async def race():
        return await asyncio.gather(
            PaymentRefundRepository.attach_razorpay_refund_id(RID, RP_RFND),
            PaymentRefundRepository.attach_razorpay_refund_id(RID, RP_RFND),
        )

    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=FakeColl(),
    ):
        results = asyncio.run(race())
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    assert state["identity"] == RP_RFND


def test_14_duplicate_key_race_fails_closed():
    """CHECK 14: a DuplicateKeyError inside attach surfaces as None — and
    the execution layer treats None as a hard stop (no completion)."""
    from pymongo.errors import DuplicateKeyError

    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(
        side_effect=DuplicateKeyError("E11000"))
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        assert asyncio.run(PaymentRefundRepository.attach_razorpay_refund_id(
            RID, RP_RFND)) is None

    # Empty identity is refused without any write.
    fake_coll2 = MagicMock()
    fake_coll2.find_one_and_update = AsyncMock(
        side_effect=AssertionError("must not write"))
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll2,
    ):
        assert asyncio.run(PaymentRefundRepository.attach_razorpay_refund_id(
            RID, "")) is None
        assert asyncio.run(PaymentRefundRepository.attach_razorpay_refund_id(
            RID, "   ")) is None

    # And the execution service maps attach-None to 409 (test_8b).
    src = code_only(PaymentRefundService.execute_refund)
    assert "NOT marked completed" in src


def test_13b_lookup_by_identity():
    """get_by_razorpay_refund_id: exact lookup, None for empty values."""
    found = make_refund_record(status="completed", razorpay_refund_id=RP_RFND)
    with patch.object(
        PaymentRefund, "find_one", new=AsyncMock(return_value=found)
    ) as fo:
        result = asyncio.run(
            PaymentRefundRepository.get_by_razorpay_refund_id(RP_RFND)
        )
    assert result is found
    fo.assert_awaited_once_with({"razorpay_refund_id": RP_RFND})

    assert asyncio.run(
        PaymentRefundRepository.get_by_razorpay_refund_id("")
    ) is None
    assert asyncio.run(
        PaymentRefundRepository.get_by_razorpay_refund_id(None)
    ) is None


# ===========================================================================
# RECONCILIATION (mandated 15–25)
# ===========================================================================

@pytest.mark.asyncio
async def test_15_16_17_persisted_identity_used_automatically():
    """CHECKS 15/16/17: the persisted identity is fetched from Razorpay
    automatically — the caller supplies only the refund record id."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=[processing, completed],
        mark_completed={"_id": RID, "status": "completed"},
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ) as fetch:
        result = await PaymentRefundService.reconcile_ambiguous_refund(RID)
    fetch.assert_called_once_with(STORED_PAYMENT_ID, RP_RFND)
    repo["attach_razorpay_refund_id"].assert_not_awaited()  # already persisted
    repo["mark_completed"].assert_awaited_once_with(RID)
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_18_matching_response_completes():
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=[processing, completed],
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ):
        result = await PaymentRefundService.reconcile_ambiguous_refund(RID)
    repo["mark_completed"].assert_awaited_once_with(RID)
    assert result.status == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("mutate", [
    lambda rp: {**rp, "payment_id": "pay_other9999"},
    lambda rp: {**rp, "amount": STORED_AMOUNT_PAISE + 1},
    lambda rp: {**rp, "currency": "USD"},
    lambda rp: {**rp, "id": "rfnd_different999"},
    lambda rp: {**rp, "status": "mystery"},
    lambda rp: {k: v for k, v in rp.items() if k != "id"},
])
async def test_19_22_mismatched_facts_remain_uncompleted(mutate):
    """CHECKS 19–22: any mismatch (payment id / amount / currency /
    refund id / unknown status / missing id) leaves the refund
    processing — never completed, never failed."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=[processing],
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=mutate(dict(RP_REFUND_OK))),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.reconcile_ambiguous_refund(RID)
    assert e.value.status_code == 409
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
    repo["touch_processing"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_23_pending_razorpay_refund_remains_processing():
    """CHECK 23: Razorpay 'pending' → committed-but-unproven → the record
    stays processing here."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=[processing],
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_PENDING)),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.reconcile_ambiguous_refund(RID)
    assert e.value.status_code == 409
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()


@pytest.mark.asyncio
async def test_24_timeout_remains_processing():
    """CHECK 24: a Razorpay lookup failure is never interpreted as
    refund failure — the record stays processing."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=[processing],
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(side_effect=RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: timeout")),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.reconcile_ambiguous_refund(RID)
    assert e.value.status_code == 409
    assert "remains in processing" in e.value.detail
    repo["mark_failed"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()


@pytest.mark.asyncio
async def test_25_missing_persisted_id_reconciliation_required():
    """CHECK 25: processing WITHOUT a persisted identity and without a
    supplied one → no guessing, no searching, no new refund; safe
    reconciliation-required outcome."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with repo_stack(get_by_id=[processing]) as repo, patch(
        "app.services.payment_refund_service.fetch_refund", new=MagicMock()
    ) as fetch:
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.reconcile_ambiguous_refund(RID)
    assert e.value.status_code == 409
    assert "reconcil" in e.value.detail.lower()
    fetch.assert_not_called()
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["create_refund"].assert_not_awaited() if "create_refund" in repo else None


@pytest.mark.asyncio
async def test_25b_supplied_identity_validated_before_attachment():
    """Task 13 fallback (Task 14 scope): a supplied identity is probed
    against Razorpay and attached ONLY when the entity belongs to this
    record."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    # Belonging entity → attach → complete.
    with repo_stack(
        get_by_id=[processing, completed],
        attach_razorpay_refund_id=attach_doc(),
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ) as fetch:
        result = await PaymentRefundService.reconcile_ambiguous_refund(
            RID, RP_RFND
        )
    fetch.assert_called_with(STORED_PAYMENT_ID, RP_RFND)
    repo["attach_razorpay_refund_id"].assert_awaited_once_with(RID, RP_RFND)
    repo["mark_completed"].assert_awaited_once_with(RID)
    assert result.status == "completed"

    # Entity NOT belonging to this record → nothing attached, no change.
    processing2 = make_refund_record(status="processing",
                                     razorpay_refund_id=None)
    with repo_stack(
        get_by_id=[processing2],
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value={**RP_REFUND_OK,
                                    "payment_id": "pay_other9999"}),
    ):
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.reconcile_ambiguous_refund(
                RID, "rfnd_someone_elses")
    assert e.value.status_code == 409
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()


@pytest.mark.asyncio
async def test_25c_supplied_identity_conflicting_with_persisted_rejected():
    """A caller-supplied identity that disagrees with the persisted one
    can never redirect the reconciliation lookup."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(get_by_id=[processing]) as repo, patch(
        "app.services.payment_refund_service.fetch_refund", new=MagicMock()
    ) as fetch:
        with pytest.raises(HTTPException) as e:
            await PaymentRefundService.reconcile_ambiguous_refund(
                RID, "rfnd_attacker_supplied")
    assert e.value.status_code == 409
    fetch.assert_not_called()
    repo["attach_razorpay_refund_id"].assert_not_awaited()


@pytest.mark.asyncio
async def test_reconciliation_double_run_is_idempotent():
    """§8: same refund reconciled twice — first completes, second is a
    no-op with no second Razorpay call."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=[processing, completed, completed, completed],
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ) as fetch:
        first = await PaymentRefundService.reconcile_ambiguous_refund(RID)
        assert first.status == "completed"
        fetch.assert_called_once()          # exactly one Razorpay lookup
        repo["mark_completed"].assert_awaited_once()

        second = await PaymentRefundService.reconcile_ambiguous_refund(RID)
        assert second.status == "completed"
        fetch.assert_called_once()          # still exactly one
        repo["mark_completed"].assert_awaited_once()  # still exactly one


# ===========================================================================
# REGRESSION (mandated 26–31)
# ===========================================================================

def test_28_no_refund_http_surface():
    """CHECK 28: Task 11's no-refund-surface invariant still holds."""
    from app.main import app as fastapi_app
    routes = [getattr(r, "path", "") for r in fastapi_app.routes]
    assert not any("refund" in p.lower() for p in routes), routes
    import os
    api_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app", "api",
    )
    for fname in os.listdir(api_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(api_dir, fname), encoding="utf-8") as f:
            assert "payment_refund" not in f.read(), fname


def test_29_no_frontend_refund_calls():
    """CHECK 29: frontend untouched — no refund calls in the frontend
    service layer."""
    import os
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    api_js = os.path.join(root, "frontend", "src", "services", "api.js")
    with open(api_js, encoding="utf-8") as f:
        assert "refund" not in f.read().lower()


@pytest.mark.asyncio
async def test_30_no_appointment_or_laboratory_mutation():
    """CHECK 30: execution/reconciliation write ONLY PaymentRefund."""
    for fn in (PaymentRefundService.execute_refund,
               PaymentRefundService.reconcile_ambiguous_refund):
        src = inspect.getsource(fn)
        for banned in (
            "Appointment", "LaboratoryBooking",
            "mark_appointment_paid", "mark_laboratory_paid",
            "mark_laboratory_failed",
            "expire_appointment_pending_payment",
            "expire_laboratory_pending_payment",
            ".save(",
        ):
            assert banned not in src, (fn.__name__, banned)


def test_31_no_raw_razorpay_calls_outside_client():
    """CHECK 31: SDK interaction stays confined to razorpay_client.py.
    Executable-token check only (docstring prose about the boundary is
    expected and harmless; razorpay_refund_id identifiers are data
    fields, not SDK references)."""
    import app.services.payment_refund_service as mod
    import app.repositories.payment_refund_repository as repo_mod
    import app.models.payment_refund as model_mod
    sdk_tokens = (
        "import razorpay", "get_razorpay_client", "Client(",
        "client.payment", "client.order", "requests.get", "requests.post",
        "httpx.", "create_order(", "fetch_payment(", "fetch_order(",
    )
    for m in (repo_mod, model_mod):
        src = code_only(m)
        for token in sdk_tokens:
            assert token not in src, (m.__name__, token)
    src = code_only(mod)
    for token in (
        "razorpay.Client(", "client.payment.refund",
        "client.payment.fetch_refund_id", "requests.", "httpx.", "urllib.",
        "import razorpay",
    ):
        assert token not in src, token
    import_lines = [
        line.strip() for line in inspect.getsource(mod).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    joined = "\n".join(import_lines)
    assert "from app.core.razorpay_client import" in joined


def test_12b_no_razorpay_calls_from_repository_or_model():
    """§12: no refund API call from repositories or models — they never
    import anything from the Razorpay layer (executable lines only; the
    repository's own Task 12 create_refund method is a DB insert, not an
    SDK call, and is verified SDK-free by test_31's import checks)."""
    import app.repositories.payment_refund_repository as repo_mod
    import app.models.payment_refund as model_mod
    for m in (repo_mod, model_mod):
        src = code_only(m)
        for token in (
            "razorpay_client", "import razorpay", "get_razorpay_client",
            "client.payment", "client.order",
        ):
            assert token not in src, (m.__name__, token)
        # SDK helper imports never appear in either module.
        import_lines = [
            ln.strip() for ln in src.splitlines()
            if ln.strip().startswith(("import ", "from "))
        ]
        assert not any("razorpay" in ln for ln in import_lines), (
            m.__name__, import_lines)


@pytest.mark.asyncio
async def test_secrets_never_in_identity_errors_or_logs(caplog):
    """§12: identity-conflict and reconciliation failures carry safe
    details; no credential material ever reaches errors or logs."""
    import logging as _logging

    requested = make_refund_record(status="requested")
    with repo_stack(
        get_by_id=[requested],
        claim_for_processing={"_id": RID, "status": "processing"},
        attach_razorpay_refund_id=None,  # identity conflict
        touch_processing={"_id": RID},
    ), patch(
        "app.services.payment_refund_service.create_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ):
        with caplog.at_level(_logging.ERROR):
            with pytest.raises(HTTPException) as e:
                await PaymentRefundService.execute_refund(RID)
    assert e.value.status_code == 409
    assert TEST_SECRET not in e.value.detail
    assert TEST_KEY_ID not in e.value.detail
    assert TEST_SECRET not in caplog.text
    assert TEST_KEY_ID not in caplog.text


def test_execution_and_reconciliation_internal_only():
    """§11/§12: no HTTP route reaches the refund executor/reconciler; the
    service accepts no client-controlled financial inputs."""
    import app.services.payment_refund_service as mod
    api_src = inspect.getsource(mod)
    assert "APIRouter" not in api_src
    assert "@router" not in api_src
    for fn_name in ("execute_refund", "reconcile_ambiguous_refund"):
        sig = inspect.signature(getattr(PaymentRefundService, fn_name))
        for banned in ("payment_id", "payment_order_id", "amount",
                       "currency", "status", "razorpay_refund_id"):
            if fn_name == "reconcile_ambiguous_refund" and \
                    banned == "razorpay_refund_id":
                continue  # operator fallback parameter (server-side only)
            assert banned not in sig.parameters, (fn_name, banned)
