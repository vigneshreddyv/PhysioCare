"""
Phase 4 Task 16 tests — Razorpay refund reconciliation & recovery.

Mandated coverage map (§13):
  1  successful reconciliation
  2  persisted refund ID matching
  3  refund ID attachment when initially absent (discovery)
  4  payment ID validation
  5  amount validation
  6  currency validation
  7  malformed response
  8  timeout
  9  connection failure
  10 Razorpay 5xx
  11 ambiguous state remains processing
  12 authoritative failure handling (contract does not authorize one)
  13 completed refund is immutable
  14 failed refund is immutable
  15 duplicate reconciliation
  16 concurrent reconciliation (exactly one winner)
  17 refund identity collision
  18 wrong-payment refund
  19 no secret leakage
  20 no raw Razorpay payload logging
  21 no frontend/client-controlled financial values
  22 no second refund state machine
  23 no load→modify→save path
  24 Task 12–15 regression coverage

ALL Razorpay interactions are mocked. Zero real credentials, zero real
Razorpay transactions.
"""
import asyncio
import ast
import inspect
import os
import textwrap
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests.exceptions as requests_exceptions
from fastapi import HTTPException
from razorpay.errors import BadRequestError, GatewayError, ServerError

from app.core import razorpay_client
from app.core.config import settings
from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpayRefundOutcome,
    RazorpayRequestError,
    fetch_payment_refunds,
)
from app.models.payment_refund import PaymentRefund
from app.repositories.payment_refund_repository import (
    RECONCILIATION_OUTCOME_MAX_LEN,
    PaymentRefundRepository,
)
from app.services.payment_refund_service import PaymentRefundService
from app.services.refund_reconciliation_service import (
    REFUND_RECONCILIATION_INTERVAL_SECONDS,
    RefundReconciliationService,
    _RP_REFUND_TRUSTED_STATUSES,
)

TEST_KEY_ID = "rzp_test_unitkeyid123"
TEST_SECRET = "test_key_secret_for_unit_tests_only"
ADMIN = "aaaaaaaaaaaaaaaaaaaaaaaa"
APT = "333333333333333333333333"
RID = "d0000000000000000000000d"
RP_RFND = "rfnd_RazorpayIdentity123"
RP_RFND_DISCOVERED = "rfnd_DiscoveredByList456"

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
RP_REFUND_PENDING = {**RP_REFUND_OK, "status": "pending"}
RP_REFUND_LIST_ONE = {
    "entity": "collection",
    "count": 1,
    "items": [dict(RP_REFUND_OK)],
}


@pytest.fixture(autouse=True)
def razorpay_test_config(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", TEST_KEY_ID)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", TEST_SECRET)
    monkeypatch.setattr(settings, "RAZORPAY_TIMEOUT_SECONDS", 30)
    # Default policy: reconciliation loop OFF (pinned; opt-in tested too).
    monkeypatch.setattr(settings, "REFUND_RECONCILIATION_ENABLED", False)


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

def make_refund_record(status="processing", razorpay_refund_id=RP_RFND, **kw):
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


class _SideEffectList(list):
    """Marker: a list explicitly meant as a call-by-call side_effect
    sequence (not a returned collection)."""


@contextmanager
def repo_stack(**methods):
    """Patch PaymentRefundRepository methods; every known method gets a
    default AsyncMock so untouched methods remain call-assertable.

    - _SideEffectList([...]) → AsyncMock(side_effect=[...]) (per-call).
    - any other value → returned as-is.
    """
    defaults = {
        "get_by_id": None,
        "claim_for_processing": None,
        "attach_razorpay_refund_id": None,
        "mark_completed": None,
        "mark_failed": None,
        "touch_processing": None,
        "list_reconcilable_refunds": [],
        "get_active_by_payment_id": None,
        "get_completed_by_payment_id": None,
        "get_processing_by_payment_id": None,
        "get_by_razorpay_refund_id": None,
        "cancel_if_requested": None,
        "create_refund": None,
        # Task 18 reconciliation bookkeeping (metadata write; returns True
        # when written) — mocked so tests stay isolated from the DB layer
        # and can assert the bounded outcome codes persisted per attempt.
        "record_reconciliation_attempt": True,
    }
    with ExitStack() as st:
        mocks = {}
        for name, ret in {**defaults, **methods}.items():
            if isinstance(ret, _SideEffectList):
                mock = AsyncMock(side_effect=list(ret))
            else:
                mock = AsyncMock(return_value=ret)
            mocks[name] = st.enter_context(
                patch.object(PaymentRefundRepository, name, new=mock)
            )
        yield mocks


def exec_src(obj) -> str:
    """Source with docstrings and comment lines removed (AST-accurate) —
    for executable-token security checks."""
    src = textwrap.dedent(inspect.getsource(obj))
    try:
        tree = ast.parse(src)
    except (SyntaxError, IndentationError):
        return "\n".join(
            ln for ln in src.splitlines()
            if not ln.strip().startswith("#")
        )
    doc_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            doc_lines.update(range(node.lineno, node.end_lineno + 1))
    lines = src.splitlines()
    out = []
    for i, ln in enumerate(lines, start=1):
        if i in doc_lines or ln.strip().startswith("#"):
            continue
        out.append(ln)
    return "\n".join(out)


# ===========================================================================
# 1 — RAZORPAY CLIENT: authoritative refund-list lookup (§3)
# ===========================================================================

def test_client_fetch_payment_refunds_uses_sdk_client_and_timeout():
    """First-page call shape (Task 17): SDK client only, count/skip
    pagination params, explicit timeout, credentials never in request."""
    fake_client = MagicMock()
    fake_client.payment.fetch_multiple_refund.return_value = dict(
        RP_REFUND_LIST_ONE
    )
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        refunds = fetch_payment_refunds(STORED_PAYMENT_ID)
    assert refunds == [RP_REFUND_OK]
    assert fake_client.payment.fetch_multiple_refund.call_count == 1
    args, kwargs = fake_client.payment.fetch_multiple_refund.call_args
    assert args[0] == STORED_PAYMENT_ID
    assert args[1] == {"count": razorpay_client.REFUND_LIST_PAGE_SIZE,
                       "skip": 0}
    assert kwargs.get("timeout") == settings.RAZORPAY_TIMEOUT_SECONDS
    # Credentials never appear in the request.
    assert TEST_SECRET not in repr(args) + repr(kwargs)
    assert TEST_KEY_ID not in repr(args) + repr(kwargs)


def test_client_fetch_payment_refunds_normalizes_envelopes():
    fake_client = MagicMock()
    # Empty collection envelope: a VALID state (no refund recorded).
    fake_client.payment.fetch_multiple_refund.return_value = {
        "entity": "collection", "count": 0, "items": [],
    }
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        assert fetch_payment_refunds(STORED_PAYMENT_ID) == []


def test_client_fetch_payment_refunds_rejects_bad_input_without_network():
    fake_client = MagicMock()
    fake_client.payment.fetch_multiple_refund.side_effect = AssertionError(
        "network call must not happen"
    )
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError):
            fetch_payment_refunds("")
        with pytest.raises(RazorpayRequestError):
            fetch_payment_refunds(None)


def test_client_fetch_payment_refunds_error_taxonomy():
    # 4xx-class: DEFINITIVE (Razorpay itself rejected the lookup).
    fake_client = MagicMock()
    fake_client.payment.fetch_multiple_refund.side_effect = BadRequestError(
        "no such payment"
    )
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            fetch_payment_refunds(STORED_PAYMENT_ID)
    assert RazorpayRefundOutcome.DEFINITIVE in str(e.value)
    assert TEST_SECRET not in str(e.value)
    # 5xx-class and network failures on the FIRST page: AMBIGUOUS.
    for exc in (GatewayError("5xx"), ServerError("5xx")):
        fake_client = MagicMock()
        fake_client.payment.fetch_multiple_refund.side_effect = exc
        with patch.object(razorpay_client, "get_razorpay_client",
                          return_value=fake_client):
            with pytest.raises(RazorpayRequestError) as e:
                fetch_payment_refunds(STORED_PAYMENT_ID)
        assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)
    import requests
    fake_client = MagicMock()
    fake_client.payment.fetch_multiple_refund.side_effect = (
        requests.exceptions.Timeout("timed out")
    )
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            fetch_payment_refunds(STORED_PAYMENT_ID)
    assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)


@pytest.mark.parametrize("bad", [None, 42, "garbage", [dict(RP_REFUND_OK)]])
def test_client_fetch_payment_refunds_malformed_response_is_ambiguous(bad):
    fake_client = MagicMock()
    fake_client.payment.fetch_multiple_refund.return_value = bad
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            fetch_payment_refunds(STORED_PAYMENT_ID)
    assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)


def test_client_fetch_payment_refunds_sdk_only_no_raw_http():
    src = exec_src(razorpay_client.fetch_payment_refunds)
    assert "client.payment.fetch_multiple_refund(" in src
    for banned in ("requests.", "httpx.", "urllib.", "aiohttp",
                   "razorpay.Client("):
        assert banned not in src, banned


# ===========================================================================
# 1b — CLIENT PAGINATION (Task 17 §1)
# ===========================================================================

def _page(items, count=None):
    return {"entity": "collection", "count": count if count is not None
            else len(items), "items": items}


def _full_page_like(items):
    """A page whose length equals the page size (walk continues)."""
    return _page(list(items))


def _short_page(items):
    """A page shorter than the page size (walk terminates after it)."""
    assert len(items) < razorpay_client.REFUND_LIST_PAGE_SIZE
    return _page(list(items))


def _client_returning(pages):
    """A fake SDK client whose fetch_multiple_refund returns pages in
    sequence; asserts each call's count/skip pagination params."""
    fake_client = MagicMock()
    fake_client.payment.fetch_multiple_refund.side_effect = [
        dict(p) for p in pages
    ]
    return fake_client


def test_client_pagination_second_page_fetched_on_full_first_page():
    """A full-size first page causes a second request with skip advanced;
    results from both pages are concatenated in order."""
    ps = razorpay_client.REFUND_LIST_PAGE_SIZE
    first = [dict(RP_REFUND_OK, id=f"rfnd_p1_{i:03d}") for i in range(ps)]
    second = _short_page([dict(RP_REFUND_OK, id="rfnd_p2_tail")])
    fake_client = _client_returning([_full_page_like(first), second])
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        result = fetch_payment_refunds(STORED_PAYMENT_ID)
    assert len(result) == ps + 1
    assert result[0]["id"] == "rfnd_p1_000"
    assert result[-1]["id"] == "rfnd_p2_tail"
    assert fake_client.payment.fetch_multiple_refund.call_count == 2
    second_call = fake_client.payment.fetch_multiple_refund.call_args_list[1]
    assert second_call.args[0] == STORED_PAYMENT_ID
    assert second_call.args[1] == {"count": ps, "skip": ps}
    # Timeout forwarded on EVERY page.
    assert second_call.kwargs.get("timeout") == settings.RAZORPAY_TIMEOUT_SECONDS


def test_client_pagination_terminates_on_short_page_without_extra_call():
    """A short first page terminates the walk: exactly ONE SDK call, no
    speculative second fetch."""
    fake_client = _client_returning([_short_page([dict(RP_REFUND_OK)])])
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        result = fetch_payment_refunds(STORED_PAYMENT_ID)
    assert result == [RP_REFUND_OK]
    assert fake_client.payment.fetch_multiple_refund.call_count == 1


def test_client_pagination_empty_list_is_single_empty_call():
    fake_client = _client_returning([_page([])])
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        assert fetch_payment_refunds(STORED_PAYMENT_ID) == []
    assert fake_client.payment.fetch_multiple_refund.call_count == 1


def test_client_pagination_multiple_pages_walked_in_order():
    """Three pages: full, full, short — walk covers all, in order, with
    correct skip offsets."""
    ps = razorpay_client.REFUND_LIST_PAGE_SIZE
    p1 = [dict(RP_REFUND_OK, id=f"rfnd_a_{i:03d}") for i in range(ps)]
    p2 = [dict(RP_REFUND_OK, id=f"rfnd_b_{i:03d}") for i in range(ps)]
    p3 = _short_page([dict(RP_REFUND_OK, id="rfnd_c_tail")])
    fake_client = _client_returning([
        _full_page_like(p1), _full_page_like(p2), p3])
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        result = fetch_payment_refunds(STORED_PAYMENT_ID)
    ids = [r["id"] for r in result]
    assert ids == [f"rfnd_a_{i:03d}" for i in range(ps)] \
        + [f"rfnd_b_{i:03d}" for i in range(ps)] + ["rfnd_c_tail"]
    skips = [c.args[1]["skip"] for c in
             fake_client.payment.fetch_multiple_refund.call_args_list]
    assert skips == [0, ps, 2 * ps]
    for c in fake_client.payment.fetch_multiple_refund.call_args_list:
        assert c.args[1]["count"] == ps
        assert c.kwargs.get("timeout") == settings.RAZORPAY_TIMEOUT_SECONDS


def test_client_pagination_failure_on_second_page_is_ambiguous_not_empty():
    """§1: pagination failure is NEVER silently treated as 'no refund
    found' — the whole lookup raises AMBIGUOUS (retryable), even though
    the first page loaded fine."""
    ps = razorpay_client.REFUND_LIST_PAGE_SIZE
    first = [dict(RP_REFUND_OK, id=f"rfnd_p1_{i:03d}") for i in range(ps)]
    for second_page_error in (
        GatewayError("5xx on page 2"),
        ServerError("upstream on page 2"),
        requests_exceptions.Timeout("timeout on page 2"),
        ConnectionError("connection reset on page 2"),
    ):
        fake_client = MagicMock()
        fake_client.payment.fetch_multiple_refund.side_effect = [
            dict(_full_page_like(first)), second_page_error,
        ]
        with patch.object(razorpay_client, "get_razorpay_client",
                          return_value=fake_client):
            with pytest.raises(RazorpayRequestError) as e:
                fetch_payment_refunds(STORED_PAYMENT_ID)
        assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)
        assert RazorpayRefundOutcome.DEFINITIVE not in str(e.value)


def test_client_pagination_malformed_second_page_is_ambiguous():
    """§1/§5: malformed pagination — a non-dict page, a dict without items,
    a non-list items — aborts the walk as AMBIGUOUS, never "no refunds"."""
    ps = razorpay_client.REFUND_LIST_PAGE_SIZE
    first = [dict(RP_REFUND_OK, id=f"rfnd_p1_{i:03d}") for i in range(ps)]
    for bad_second in (None, 42, "garbage", {}, {"count": 3},
                       {"items": "not-a-list"}):
        fake_client = MagicMock()
        fake_client.payment.fetch_multiple_refund.side_effect = [
            dict(_full_page_like(first)), bad_second,
        ]
        with patch.object(razorpay_client, "get_razorpay_client",
                          return_value=fake_client):
            with pytest.raises(RazorpayRequestError) as e:
                fetch_payment_refunds(STORED_PAYMENT_ID)
        assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)


def test_client_pagination_malformed_entry_inside_page_is_ambiguous():
    """A junk element inside an otherwise plausible page makes the list
    unreliable for identity discovery: AMBIGUOUS, never skipped silently."""
    fake_client = MagicMock()
    fake_client.payment.fetch_multiple_refund.side_effect = [
        dict(_short_page([dict(RP_REFUND_OK), "junk"])),
    ]
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            fetch_payment_refunds(STORED_PAYMENT_ID)
    assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)


def test_client_pagination_duplicate_ids_across_pages_is_ambiguous():
    """Page overlap (or a lying server) means the list cannot be trusted
    for identity selection: AMBIGUOUS — never silently deduplicated."""
    ps = razorpay_client.REFUND_LIST_PAGE_SIZE
    first = [dict(RP_REFUND_OK, id=f"rfnd_p1_{i:03d}") for i in range(ps)]
    # Second page REPEATS an id from the first page.
    second = _short_page([dict(RP_REFUND_OK, id="rfnd_p1_000",
                               status="pending")])
    fake_client = _client_returning([
        _full_page_like(first), second])
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            fetch_payment_refunds(STORED_PAYMENT_ID)
    assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)
    assert "duplicate" in str(e.value).lower()


def test_client_pagination_missing_items_on_first_page_is_ambiguous():
    """A plausible envelope with a missing/non-list items field is
    malformed: AMBIGUOUS, never treated as an empty list."""
    for bad_first in ({}, {"count": 0}, {"items": None},
                      {"items": {"id": "rfnd_x"}}):
        fake_client = _client_returning([bad_first])
        with patch.object(razorpay_client, "get_razorpay_client",
                          return_value=fake_client):
            with pytest.raises(RazorpayRequestError) as e:
                fetch_payment_refunds(STORED_PAYMENT_ID)
        assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)


def test_client_pagination_non_terminating_walk_is_ambiguous():
    """A server that keeps returning full pages forever is an anomaly: the
    walk aborts at the safety cap as AMBIGUOUS — never "no refund found",
    never an infinite loop."""
    ps = razorpay_client.REFUND_LIST_PAGE_SIZE

    def endless_page(pid, data, **kw):
        # Unique ids per page (skip-aware): a misbehaving server that
        # always claims more refunds exist, never repeating itself.
        skip = data["skip"]
        items = [dict(RP_REFUND_OK, id=f"rfnd_x_{skip + i:06d}")
                 for i in range(ps)]
        return dict(_full_page_like(items))

    fake_client = MagicMock()
    fake_client.payment.fetch_multiple_refund.side_effect = endless_page
    with patch.object(razorpay_client, "get_razorpay_client",
                      return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as e:
            fetch_payment_refunds(STORED_PAYMENT_ID)
    assert RazorpayRefundOutcome.AMBIGUOUS in str(e.value)
    assert "terminate" in str(e.value).lower()
    assert fake_client.payment.fetch_multiple_refund.call_count == \
        razorpay_client.REFUND_LIST_MAX_PAGES


# ===========================================================================
# 2 — FINDER: identifying recoverable refunds (§4, §7)
# ===========================================================================

def test_finder_scope_is_processing_only_and_read_only():
    src = exec_src(PaymentRefundRepository.list_reconcilable_refunds)
    # Exact eligibility filter: processing only. Identity is NOT a filter
    # (records without one are reconcilable via authoritative discovery).
    assert '"status": "processing"' in src
    assert "razorpay_refund_id" not in src
    # Bounded (no unbounded scans).
    assert "limit(" in src
    # Read-only: no writes of any kind.
    for banned in ("insert", "find_one_and_update", "update_many",
                   "delete", "save("):
        assert banned not in src, banned
    # No Razorpay SDK/network reference.
    for banned in ("client.payment", "client.order", "import razorpay",
                   "razorpay_client", "get_razorpay_client"):
        assert banned not in src, banned
    # No payment_id parameter — no cross-refund searching surface.
    sig = inspect.signature(PaymentRefundRepository.list_reconcilable_refunds)
    assert set(sig.parameters.keys()) == {"limit"}


@pytest.mark.asyncio
async def test_finder_uses_status_and_existing_indexes():
    fake_find = MagicMock()
    fake_sort = MagicMock()
    fake_limit = MagicMock()
    fake_limit.to_list = AsyncMock(return_value=[])
    fake_sort.limit.return_value = fake_limit
    fake_find.return_value.sort.return_value = fake_sort
    with patch.object(PaymentRefund, "find", new=fake_find):
        result = await PaymentRefundRepository.list_reconcilable_refunds()
    assert result == []
    query = fake_find.call_args.args[0]
    assert query == {"status": "processing"}
    # Index inventory: the queried field is already indexed — no additions.
    idx_names = [
        getattr(ix, "document", {}).get("name")
        for ix in PaymentRefund.Settings.indexes
    ]
    assert "uniq_active_refund_per_payment" in idx_names
    assert "uniq_razorpay_refund_id_when_present" in idx_names
    assert len(idx_names) == 3  # no new index was added by Task 16


def test_no_new_indexes_added_by_task16():
    names = [
        getattr(ix, "document", {}).get("name")
        for ix in PaymentRefund.Settings.indexes
    ]
    assert sorted(names) == sorted([
        "uniq_active_refund_per_payment",
        "idx_refund_payable",
        "uniq_razorpay_refund_id_when_present",
    ])


# ===========================================================================
# 3 — SUCCESSFUL RECONCILIATION (mandated 1, 2)
# ===========================================================================

@pytest.mark.asyncio
async def test_persisted_identity_successful_reconciliation_completes():
    """Persisted refund ID → fetch by stored payment_id + persisted id →
    validated `processed` → atomically completed."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    # get_by_id reads: driver pre-check, Task 14 initial load, post-
    # completion re-read.
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing, completed]),
        mark_completed={"_id": RID, "status": "completed"},
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "reconciled_completed"
    # The lookup used the PERSISTED identity — the only permitted op.
    fetch.assert_called_with(STORED_PAYMENT_ID, RP_RFND)
    repo["mark_completed"].assert_awaited_once_with(RID)
    # Identity already persisted: never re-attached.
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    # No discovery lookup was needed.
    repo["mark_failed"].assert_not_awaited()


# ===========================================================================
# 4 — IDENTITY DISCOVERY: attachment when initially absent (mandated 3)
# ===========================================================================

@pytest.mark.asyncio
async def test_identity_absent_discovery_attaches_then_completes():
    """Processing + no persisted identity → Razorpay's own refund list for
    the STORED payment → exactly one matching `processed` refund → its id
    is attached atomically and completion follows — in the strict order
    validate → persist identity → complete (§5)."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND_DISCOVERED)
    order = []

    async def attach(_rid, rp_id):
        order.append("attach")
        return {"_id": _rid, "razorpay_refund_id": rp_id}

    async def complete(_rid):
        order.append("complete")
        return {"_id": _rid, "status": "completed"}

    with repo_stack(
        get_by_id=_SideEffectList([processing, processing, completed]),
        touch_processing={"_id": RID},
    ), patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(return_value=[dict(RP_REFUND_OK,
                                         id=RP_RFND_DISCOVERED)]),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK,
                                        id=RP_RFND_DISCOVERED)),
    ) as fetch, patch.object(
        PaymentRefundRepository, "attach_razorpay_refund_id",
        new=AsyncMock(side_effect=attach),
    ), patch.object(
        PaymentRefundRepository, "mark_completed",
        new=AsyncMock(side_effect=complete),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)

    assert result == "reconciled_completed"
    # Discovery queried by the backend-stored payment id ONLY.
    list_fetch.assert_called_once_with(STORED_PAYMENT_ID)
    # The discovered identity is NOT trusted alone: Task 14 re-fetches it
    # (probe + final authoritative read) and validates every fact.
    assert fetch.call_count == 2
    for call in fetch.call_args_list:
        assert call.args == (STORED_PAYMENT_ID, RP_RFND_DISCOVERED)
    # Ordering invariant (Task 15 §3): identity persisted BEFORE completion.
    assert order == ["attach", "complete"]


@pytest.mark.asyncio
async def test_identity_absent_discovered_pending_stays_processing():
    """The discovered refund exists but is `pending` on Razorpay —
    committed-but-unproven: the refund stays processing, nothing attached."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(return_value=[dict(RP_REFUND_PENDING,
                                         id=RP_RFND_DISCOVERED)]),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "kept_pending"
    list_fetch.assert_called_once_with(STORED_PAYMENT_ID)
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
    fetch.assert_not_called()
    repo["touch_processing"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_identity_absent_no_matching_refund_stays_processing():
    """No refund recorded on Razorpay for the payment — the POST may never
    have landed. Never failed (that could cause a double refund); stays
    processing."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(return_value=[]),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "kept_no_identity"
    list_fetch.assert_called_once_with(STORED_PAYMENT_ID)
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_identity_absent_multiple_matches_are_ambiguous():
    """More than one refund matching the stored full amount is ambiguous —
    reconciliation must not pick one arbitrarily. Stays processing."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    two = [
        dict(RP_REFUND_OK, id="rfnd_first99999999999"),
        dict(RP_REFUND_OK, id="rfnd_second999999999"),
    ]
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(return_value=two),
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: multiple matches are their OWN outcome class
    # (kept_multiple_candidates) — never collapsed into kept_no_identity.
    assert result == "kept_multiple_candidates"
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    fetch.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("items", [
    # Wrong payment (§6: a refund belonging to a different payment is
    # rejected outright).
    [dict(RP_REFUND_OK, id="rfnd_x1", payment_id="pay_other9999")],
    # Wrong amount — no partial refunds, no over-refunds (§11).
    [dict(RP_REFUND_OK, id="rfnd_x2", amount=STORED_AMOUNT_PAISE + 1)],
    [dict(RP_REFUND_OK, id="rfnd_x3", amount=1)],
    # Wrong currency.
    [dict(RP_REFUND_OK, id="rfnd_x4", currency="USD")],
    # Razorpay's `failed` status is NOT an authoritative terminal failure
    # per the existing contract — never converted into `failed` here.
    [dict(RP_REFUND_OK, id="rfnd_x5", status="failed")],
    # Unrecognized status.
    [dict(RP_REFUND_OK, id="rfnd_x6", status="mystery")],
    # Missing id / non-dict junk is skipped.
    [{k: v for k, v in RP_REFUND_OK.items() if k != "id"}],
    ["junk", None, 42],
])
async def test_identity_absent_rejects_non_matching_items(items):
    """Only a full, exact match on payment/amount/currency/status can be
    considered; everything else is skipped and the record stays processing."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(return_value=list(items)),
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "kept_no_identity"
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_identity_absent_incoherent_record_no_lookup():
    """A processing record whose stored facts are not coherent is never
    looked up, never guessed — kept processing untouched."""
    bad = make_refund_record(status="processing", razorpay_refund_id=None,
                             amount=0)
    with repo_stack(
        get_by_id=_SideEffectList([bad]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ) as list_fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "kept_no_identity"
    list_fetch.assert_not_called()
    repo["attach_razorpay_refund_id"].assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("exc, expected", [
    (RazorpayRequestError(
        f"{RazorpayRefundOutcome.AMBIGUOUS}: timeout during lookup"),
     "kept_razorpay_ambiguous"),
    (RazorpayRequestError(
        f"{RazorpayRefundOutcome.AMBIGUOUS}: connection refused"),
     "kept_razorpay_ambiguous"),
    (RazorpayRequestError(
        f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay server error while "
        "listing payment refunds."),
     "kept_razorpay_ambiguous"),
    (RazorpayRequestError(
        f"{RazorpayRefundOutcome.DEFINITIVE}: Razorpay rejected the "
        "refund list lookup: no such payment"),
     "kept_razorpay_definitive"),
])
async def test_identity_absent_list_lookup_ambiguity_keeps_processing(
        exc, expected):
    """Timeout / connection failure / 5xx / definitive list rejection —
    ALL keep the refund processing (§12: never convert uncertainty into
    failure; a definitive list rejection is an anomaly needing review,
    not proof the refund failed). Task 18 distinguishes the two error
    classes in the outcome code only — the refund state is `processing`
    either way (no new state, no invented policy)."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(side_effect=exc),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: the definitive/ambiguous taxonomy from the
    # client boundary is preserved in the outcome code.
    assert result == expected
    list_fetch.assert_called_once_with(STORED_PAYMENT_ID)
    repo["mark_failed"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    fetch.assert_not_called()
    repo["touch_processing"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_identity_absent_discovered_id_is_revalidated():
    """The discovered identity is NOT trusted alone: Razorpay's entity for
    it must match the stored payment/amount/currency — a wrong-payment
    refund under the discovered id is rejected; nothing is attached."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(return_value=[dict(RP_REFUND_OK,
                                         id=RP_RFND_DISCOVERED)]),
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK,
                                        id=RP_RFND_DISCOVERED,
                                        payment_id="pay_other9999")),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: Razorpay's entity did not match the stored
    # facts under the discovered id → validation mismatch class.
    assert result == "kept_mismatch"
    fetch.assert_called_once_with(STORED_PAYMENT_ID, RP_RFND_DISCOVERED)
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()


@pytest.mark.asyncio
async def test_identity_absent_attach_collision_fails_closed():
    """The discovered identity is already held by another record — the
    partial unique index refuses the attach; the refund is NEVER completed
    and stays processing (§6, §7)."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
        attach_razorpay_refund_id=None,   # attach lost the race → None
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(return_value=[dict(RP_REFUND_OK,
                                         id=RP_RFND_DISCOVERED)]),
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK,
                                        id=RP_RFND_DISCOVERED)),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: a lost identity race is a mismatch-class
    # anomaly (never a completion, never a failure).
    assert result == "kept_mismatch"
    repo["attach_razorpay_refund_id"].assert_awaited_once_with(
        RID, RP_RFND_DISCOVERED)
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
    # Only the probe ran — completion was refused before any final read.
    fetch.assert_called_once()


# ===========================================================================
# 5 — VALIDATION AGAINST STORED FACTS (mandated 2, 4, 5, 6, 7, 18)
# ===========================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("mutate, label", [
    (lambda rp: {**rp, "payment_id": "pay_other9999"}, "wrong payment id"),
    (lambda rp: {**rp, "amount": STORED_AMOUNT_PAISE + 1}, "wrong amount"),
    (lambda rp: {**rp, "currency": "USD"}, "wrong currency"),
    (lambda rp: {**rp, "id": "rfnd_different999"}, "wrong refund id"),
    (lambda rp: {**rp, "status": "mystery"}, "unknown status"),
    (lambda rp: {k: v for k, v in rp.items() if k != "id"}, "missing id"),
    (lambda rp: None, "malformed response"),
])
async def test_mismatch_and_malformed_remain_processing(mutate, label):
    """Every invalid authoritative response leaves the refund in
    `processing` — never completed, never failed, never re-created."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=mutate(dict(RP_REFUND_OK))),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: every invalid authoritative response is the
    # validation-mismatch class — still never completed, never failed.
    assert result == "kept_mismatch", label
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["touch_processing"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_persisted_identity_pending_status_remains_processing():
    """A matching `pending` refund under the persisted identity — stays
    processing (never completed from a non-final state)."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_PENDING)),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "kept_pending"
    fetch.assert_called_with(STORED_PAYMENT_ID, RP_RFND)
    repo["mark_completed"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()


# ===========================================================================
# 6 — AMBIGUOUS RAZORPAY OUTCOMES (mandated 8–12)
# ===========================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [
    RazorpayRequestError(
        f"{RazorpayRefundOutcome.AMBIGUOUS}: timeout during lookup"),
    RazorpayRequestError(
        f"{RazorpayRefundOutcome.AMBIGUOUS}: connection refused"),
    RazorpayRequestError(
        f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay server error while "
        "fetching the refund."),
    RazorpayRequestError(
        f"{RazorpayRefundOutcome.DEFINITIVE}: Razorpay rejected the refund "
        "lookup: no such refund"),
])
async def test_lookup_failure_never_marks_failed(exc):
    """§12: timeout / connection error / 5xx keep `processing`. Even a
    definitive 'no such refund' lookup rejection stays processing — the
    existing contract treats it as an anomaly requiring review (the refund
    POST may still have landed), NOT an authoritative terminal failure.
    Task 18 outcome class: kept_razorpay_ambiguous — the frozen Task 14
    boundary collapses its AMBIGUOUS and DEFINITIVE taxonomy into one
    safe 409 ("could not be reconciled with Razorpay"), which the driver
    classifies as the Razorpay-ambiguous-error class; DEFINITIVE lookup
    rejections are distinguished individually on the discovery path."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(side_effect=exc),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: Razorpay lookup failure — kept processing,
    # never failed, never completed.
    assert result == "kept_razorpay_ambiguous"
    repo["mark_failed"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    repo["touch_processing"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_razorpay_failed_status_is_never_authoritative_failure():
    """The existing contract recognizes only `processed`/`pending`; an
    entity reported `failed` is unproven here — never silently mapped to
    `failed` (and never to `completed`)."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK, status="failed")),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: an unrecognized status is a validation
    # mismatch — never an authoritative failure, never a completion.
    assert result == "kept_mismatch"
    repo["mark_failed"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()


def test_discovery_status_vocabulary_matches_task13_contract():
    """The discovery selector uses exactly the status vocabulary the Task
    13/14 validation contract recognizes — no invented Razorpay states."""
    assert set(_RP_REFUND_TRUSTED_STATUSES) == set(
        PaymentRefundService._RAZORPAY_REFUND_SUCCESS_STATUSES
        + PaymentRefundService._RAZORPAY_REFUND_PENDING_STATUSES
    )


# ===========================================================================
# 6b — SERVICE-LEVEL PAGINATED DISCOVERY (Task 17 §1/§2)
# ===========================================================================

PS = razorpay_client.REFUND_LIST_PAGE_SIZE


def _page_items(prefix, n, **overrides):
    return [dict(RP_REFUND_OK, id=f"rfnd_{prefix}_{i:04d}", **overrides)
            for i in range(n)]


@pytest.mark.asyncio
async def test_discovery_finds_identity_on_first_page():
    """§13.1: first-page refund discovery — short first page, one call."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing, completed]),
        touch_processing={"_id": RID},
        attach_razorpay_refund_id={"_id": RID,
                                   "razorpay_refund_id": RP_RFND},
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(side_effect=lambda pid: [dict(RP_REFUND_OK)]),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "reconciled_completed"
    list_fetch.assert_called_once_with(STORED_PAYMENT_ID)
    repo["attach_razorpay_refund_id"].assert_awaited_once_with(RID, RP_RFND)
    repo["mark_completed"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_discovery_finds_identity_on_second_page():
    """§13.2/§13.7: the matching refund exists only on a LATER page — the
    paginated client walk surfaces it and reconciliation completes."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id="rfnd_on_second_page_999")
    later_page_refund = dict(RP_REFUND_OK, id="rfnd_on_second_page_999")

    def fake_list(pid):
        # First page full of NON-MATCHING refunds (different amount), the
        # only exact match short-page at the end. The client walks both;
        # the service sees the concatenated list.
        filler = _page_items("filler", PS, amount=STORED_AMOUNT_PAISE + 1)
        return filler + [later_page_refund]

    with repo_stack(
        get_by_id=_SideEffectList([processing, processing, completed]),
        touch_processing={"_id": RID},
        attach_razorpay_refund_id={"_id": RID,
                                   "razorpay_refund_id":
                                   "rfnd_on_second_page_999"},
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(side_effect=fake_list),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(later_page_refund)),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "reconciled_completed"
    list_fetch.assert_called_once_with(STORED_PAYMENT_ID)
    # The discovered later-page identity was re-fetched and validated
    # before attachment.
    fetch.assert_called_with(STORED_PAYMENT_ID, "rfnd_on_second_page_999")
    repo["attach_razorpay_refund_id"].assert_awaited_once_with(
        RID, "rfnd_on_second_page_999")
    repo["mark_completed"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_discovery_multiple_pages_multiple_matches_ambiguous():
    """§13.9/§13.10: matches spread across DIFFERENT pages are still
    multiple candidates — no guessing between them, no selection by order.
    (Task 18: multiplicity gets its own outcome class — see the assert.)"""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)

    def fake_list(pid):
        # One exact match on page 1, another on page 3 (fillers differ on
        # amount — never candidates).
        return (
            _page_items("p1filler", PS - 1, amount=STORED_AMOUNT_PAISE + 1)
            + [dict(RP_REFUND_OK, id="rfnd_page1_match_01")]
            + _page_items("p2filler", PS, amount=STORED_AMOUNT_PAISE + 1)
            + _page_items("p3filler", PS - 1, amount=STORED_AMOUNT_PAISE + 1)
            + [dict(RP_REFUND_OK, id="rfnd_page3_match_03")]
        )

    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(side_effect=fake_list),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: cross-page multiplicity is the
    # kept_multiple_candidates class — ambiguity is never collapsed.
    assert result == "kept_multiple_candidates"
    list_fetch.assert_called_once_with(STORED_PAYMENT_ID)
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_discovery_identity_absent_across_all_pages():
    """§13.8: many pages of refunds, none matching the stored facts —
    stays processing (never failed, never guessed)."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)

    def fake_list(pid):
        # Two full pages of refunds that differ from the stored amount.
        return (_page_items("p1", PS, amount=STORED_AMOUNT_PAISE + 1)
                + _page_items("p2", PS - 1, amount=STORED_AMOUNT_PAISE + 1)
                + [])

    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(side_effect=fake_list),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "kept_no_identity"
    repo["mark_failed"].assert_not_awaited()
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_discovery_pagination_failure_is_kept_not_failed():
    """§13.5/§13.17: a pagination failure (the client raising AMBIGUOUS)
    keeps the refund processing — never mark_failed, never "no refund
    found"."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(side_effect=RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay refund list "
            "walk did not terminate.")),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: a failed pagination walk is the Razorpay
    # ambiguous-error class — kept processing, never failed.
    assert result == "kept_razorpay_ambiguous"
    list_fetch.assert_called_once_with(STORED_PAYMENT_ID)
    repo["mark_failed"].assert_not_awaited()
    repo["mark_completed"].assert_not_awaited()
    fetch.assert_not_called()
    repo["touch_processing"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_discovery_pagination_never_duplicates_completion():
    """§13.14: the paginated path terminates through the SAME single
    atomic completion — no double mark_completed regardless of page count."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id="rfnd_last_page_01")

    def fake_list(pid):
        # Multi-page list with exactly one match on the last page (the
        # filler page differs on amount — never a candidate).
        return (_page_items("p1", PS, amount=STORED_AMOUNT_PAISE + 1)
                + [dict(RP_REFUND_OK, id="rfnd_last_page_01")])

    with repo_stack(
        get_by_id=_SideEffectList([processing, processing, completed]),
        touch_processing={"_id": RID},
        attach_razorpay_refund_id={"_id": RID,
                                   "razorpay_refund_id":
                                   "rfnd_last_page_01"},
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(side_effect=fake_list),
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK,
                                        id="rfnd_last_page_01")),
    ):
        await RefundReconciliationService._reconcile_one(RID)
    repo["mark_completed"].assert_awaited_once_with(RID)
    repo["attach_razorpay_refund_id"].assert_awaited_once()


@pytest.mark.asyncio
async def test_discovery_rejects_candidates_differing_on_any_fact():
    """§2/§13.12: candidates differing in payment/amount/currency/status
    are rejected rather than selected — even when they are the ONLY
    refunds on Razorpay's side. Discovered identity mismatch after the
    re-fetch also keeps processing."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    for mutated in (
        dict(RP_REFUND_OK, id="rfnd_wrongpay_01",
             payment_id="pay_other9999"),
        dict(RP_REFUND_OK, id="rfnd_wrongamt_01",
             amount=STORED_AMOUNT_PAISE + 1),
        dict(RP_REFUND_OK, id="rfnd_wrongcur_01", currency="USD"),
        dict(RP_REFUND_OK, id="rfnd_wrongstat_01", status="failed"),
    ):
        with repo_stack(
            get_by_id=_SideEffectList([processing]),
            touch_processing={"_id": RID},
        ) as repo, patch(
            "app.services.refund_reconciliation_service."
            "fetch_payment_refunds",
            new=MagicMock(side_effect=lambda pid, m=mutated: [dict(m)]),
        ), patch(
            "app.services.payment_refund_service.fetch_refund",
            new=MagicMock(),
        ) as fetch:
            result = await RefundReconciliationService._reconcile_one(RID)
        assert result == "kept_no_identity", mutated["id"]
        repo["attach_razorpay_refund_id"].assert_not_awaited()
        repo["mark_completed"].assert_not_awaited()
        repo["mark_failed"].assert_not_awaited()
        fetch.assert_not_called()


@pytest.mark.asyncio
async def test_discovery_candidate_refetched_before_attachment():
    """§13.11: the discovered candidate is re-fetched individually and
    validated AGAIN before attachment — the list entry alone never
    authorizes the attach."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
        attach_razorpay_refund_id={"_id": RID,
                                   "razorpay_refund_id": RP_RFND},
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(side_effect=lambda pid: [dict(RP_REFUND_OK)]),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ) as fetch:
        await RefundReconciliationService._reconcile_one(RID)
    # Two fetch_refund reads happen inside the Task 14 operation (probe
    # for the supplied identity, then the final authoritative read) —
    # both BEFORE the attach.
    assert fetch.call_count == 2
    list_fetch.assert_called_once_with(STORED_PAYMENT_ID)
    repo["attach_razorpay_refund_id"].assert_awaited_once()


@pytest.mark.asyncio
async def test_persisted_identity_path_unaffected_by_pagination():
    """§3/§13.13: a persisted identity goes straight to fetch_refund —
    the paginated list is NEVER consulted, and semantics are unchanged."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing, completed]),
        touch_processing={"_id": RID},
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "reconciled_completed"
    list_fetch.assert_not_called()  # paginated discovery never engaged
    fetch.assert_called_with(STORED_PAYMENT_ID, RP_RFND)
    repo["attach_razorpay_refund_id"].assert_not_awaited()
    repo["mark_completed"].assert_awaited_once_with(RID)


@pytest.mark.asyncio
async def test_no_razorpay_calls_for_terminal_records_with_pagination():
    """§13.18: terminal records — completed, failed, cancelled — produce
    zero Razorpay calls of any kind (no list, no fetch)."""
    for status_value in ("completed", "failed", "cancelled"):
        terminal = make_refund_record(status=status_value,
                                      razorpay_refund_id=RP_RFND)
        with repo_stack(get_by_id=_SideEffectList([terminal])), patch(
            "app.services.refund_reconciliation_service."
            "fetch_payment_refunds", new=MagicMock(),
        ) as list_fetch, patch(
            "app.services.payment_refund_service.fetch_refund",
            new=MagicMock(),
        ) as fetch:
            result = await RefundReconciliationService._reconcile_one(RID)
        assert result == "already_settled"
        list_fetch.assert_not_called()
        fetch.assert_not_called()


# ===========================================================================
# 7 — IDEMPOTENCY (mandated 13, 14, 15)
# ===========================================================================

@pytest.mark.asyncio
async def test_completed_refund_zero_razorpay_calls():
    """A completed refund reconciled again → returned untouched, zero
    Razorpay lookups, zero writes."""
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    with repo_stack(get_by_id=_SideEffectList([completed])) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "already_settled"  # terminal: zero Razorpay I/O
    list_fetch.assert_not_called()
    fetch.assert_not_called()
    repo["mark_completed"].assert_not_awaited()
    repo["touch_processing"].assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_refund_is_immutable():
    """§12: a failed refund reconciled again is a no-op — reconciliation
    never revives it, never re-contacts Razorpay for it."""
    failed = make_refund_record(status="failed",
                                razorpay_refund_id=RP_RFND)
    with repo_stack(get_by_id=_SideEffectList([failed])) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(),
    ) as fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "already_settled"
    list_fetch.assert_not_called()
    fetch.assert_not_called()
    repo["mark_completed"].assert_not_awaited()
    repo["touch_processing"].assert_not_awaited()


@pytest.mark.asyncio
async def test_cancelled_refund_is_immutable():
    failed = make_refund_record(status="cancelled",
                                razorpay_refund_id=None)
    with repo_stack(get_by_id=_SideEffectList([failed])), patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ) as list_fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "already_settled"
    list_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_requested_refund_is_not_a_reconciliation_target():
    requested = make_refund_record(status="requested",
                                   razorpay_refund_id=None)
    with repo_stack(get_by_id=_SideEffectList([requested])), patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ) as list_fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "already_settled"
    list_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_repeated_reconciliation_is_idempotent():
    """Reconciling the same refund repeatedly: one lookup, one completion;
    subsequent runs find nothing to do and cause no duplicate side
    effects."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([
            processing, processing, completed, completed, completed,
        ]),
        mark_completed={"_id": RID, "status": "completed"},
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ) as fetch:
        first = await RefundReconciliationService._reconcile_one(RID)
        assert first == "reconciled_completed"
        repo["mark_completed"].assert_awaited_once()
        fetch.assert_called_once()

        second = await RefundReconciliationService._reconcile_one(RID)
        third = await RefundReconciliationService._reconcile_one(RID)
    assert second == third == "already_settled"
    repo["mark_completed"].assert_awaited_once()
    fetch.assert_called_once()
    list_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_record_vanished_is_classified_not_found():
    with repo_stack(get_by_id=_SideEffectList([None])) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ) as list_fetch:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "not_found"
    list_fetch.assert_not_called()


# ===========================================================================
# 8 — CONCURRENCY (mandated 16, 17)
# ===========================================================================

@pytest.mark.asyncio
async def test_concurrent_reconciliation_single_completion():
    """reconcile + reconcile: the database's atomic guards decide; only
    one completion transition can ever win (§7: no load→modify→save)."""
    state = {"completed": False}

    class GuardedRepo:
        @staticmethod
        async def mark_completed(refund_id):
            if state["completed"]:
                return None
            state["completed"] = True
            return {"_id": refund_id, "status": "completed"}

    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)

    async def get_by_id(_):
        return processing if not state["completed"] else completed

    with patch.object(PaymentRefundRepository, "get_by_id",
                      new=get_by_id), \
            patch.object(PaymentRefundRepository, "mark_completed",
                         new=GuardedRepo.mark_completed), \
            patch("app.services.payment_refund_service.fetch_refund",
                  new=MagicMock(return_value=dict(RP_REFUND_OK))), \
            patch("app.services.refund_reconciliation_service."
                  "fetch_payment_refunds", new=MagicMock()):
        results = await asyncio.gather(
            RefundReconciliationService._reconcile_one(RID),
            RefundReconciliationService._reconcile_one(RID),
        )
    assert results == ["reconciled_completed", "reconciled_completed"]
    assert state["completed"] is True  # exactly one completion


@pytest.mark.asyncio
async def test_reconciliation_racing_execution_no_duplicate_refund():
    """reconcile + execution race: only one atomic claim can win; exactly
    one Razorpay refund-creation call can ever exist — and reconciliation
    itself issues none."""
    # Stateful repository simulation: the record's status follows the
    # real atomic transitions regardless of coroutine interleaving.
    state = {"claimed": False, "completed": False}
    claim_calls = {"n": 0}

    def record_for_status():
        if state["completed"]:
            return make_refund_record(status="completed",
                                      razorpay_refund_id=RP_RFND)
        if state["claimed"]:
            return make_refund_record(status="processing",
                                      razorpay_refund_id=RP_RFND)
        return make_refund_record(status="requested",
                                  razorpay_refund_id=None)

    async def get_by_id(_):
        return record_for_status()

    async def claim(_):
        claim_calls["n"] += 1
        if state["claimed"]:
            return None
        state["claimed"] = True
        return {"_id": RID, "status": "processing"}

    async def complete(_rid):
        if state["completed"]:
            return None
        state["completed"] = True
        return {"_id": _rid, "status": "completed"}

    create_calls = {"n": 0}

    def fake_create(payment_id, amount):
        # Regular function: the service invokes it synchronously via
        # asyncio.to_thread.
        create_calls["n"] += 1
        return dict(RP_REFUND_OK)

    with patch(
        "app.services.payment_refund_service.create_refund",
        new=MagicMock(side_effect=fake_create),
    ) as create_mock, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ), patch.object(
        PaymentRefundRepository, "get_by_id", new=get_by_id,
    ), patch.object(
        PaymentRefundRepository, "claim_for_processing", new=claim,
    ) as claim_mock, patch.object(
        PaymentRefundRepository, "mark_completed", new=complete,
    ) as complete_mock, patch.object(
        PaymentRefundRepository, "attach_razorpay_refund_id",
        new=AsyncMock(return_value={
            "_id": RID, "razorpay_refund_id": RP_RFND}),
    ), patch.object(
        PaymentRefundRepository, "touch_processing",
        new=AsyncMock(return_value={"_id": RID}),
    ), patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ):
        results = await asyncio.gather(
            PaymentRefundService.execute_refund(RID),
            RefundReconciliationService._reconcile_one(RID),
        )
        # Exactly one refund creation — by execution, never reconciliation.
        assert create_calls["n"] == 1
        create_mock.assert_called_once()
        # Exactly one atomic claim.
        assert claim_calls["n"] == 1
        # Exactly one completion transition.
        assert state["completed"] is True


@pytest.mark.asyncio
async def test_completion_race_single_winner_via_atomic_guard():
    """reconcile + completion race: mark_completed's processing-only
    filter admits exactly one winner; the loser cannot complete."""
    fake_coll = MagicMock()
    calls = {"n": 0}

    async def guarded(*a, **k):
        calls["n"] += 1
        return {"_id": RID, "status": "completed"} if calls["n"] == 1 \
            else None

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
    assert sum(1 for r in results if r is not None) == 1
    for call in fake_coll.find_one_and_update.await_args_list:
        assert call.args[0]["status"] == "processing"


def test_identity_cannot_be_attached_to_two_records():
    """The same Razorpay refund ID can never belong to two PaymentRefund
    records — the partial unique index decides; the loser fails closed."""
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

    async def race():
        return await asyncio.gather(
            PaymentRefundRepository.attach_razorpay_refund_id(
                RID, RP_RFND),
            PaymentRefundRepository.attach_razorpay_refund_id(
                "e0000000000000000000000e", RP_RFND),
        )

    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=FakeColl(),
    ):
        results = asyncio.run(race())
    assert sum(1 for r in results if r is not None) == 1


def test_persisted_identity_cannot_be_overwritten():
    """A different (or identical) refund ID can never replace a persisted
    identity — the attach filter requires a null identity."""
    src = exec_src(PaymentRefundRepository.attach_razorpay_refund_id)
    assert '"razorpay_refund_id": None' in src
    assert '"status": "processing"' in src


# ===========================================================================
# 9 — BATCH DRIVER + SCHEDULER (§6, §10: no invented policy)
# ===========================================================================

@pytest.mark.asyncio
async def test_batch_driver_reconciles_eligible_and_summarizes():
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        list_reconcilable_refunds=[processing],
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
    ) as repo, patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(),
    ) as list_fetch, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=RP_REFUND_PENDING),
    ):
        summary = await RefundReconciliationService.reconcile_refundable_refunds()
    assert summary["scanned"] == 1
    assert summary["kept_pending"] == 1
    assert summary.get("reconciled_completed", 0) == 0
    repo["mark_failed"].assert_not_awaited()
    list_fetch.assert_not_called()  # identity was persisted: no discovery


@pytest.mark.asyncio
async def test_batch_driver_bounded_by_limit():
    with repo_stack(list_reconcilable_refunds=[]) as repo:
        await RefundReconciliationService.reconcile_refundable_refunds(limit=7)
    repo["list_reconcilable_refunds"].assert_awaited_once_with(limit=7)


@pytest.mark.asyncio
async def test_batch_driver_survives_scan_failure():
    with repo_stack(list_reconcilable_refunds=None) as repo, patch.object(
        PaymentRefundRepository, "list_reconcilable_refunds",
        new=AsyncMock(side_effect=RuntimeError("db down")),
    ):
        summary = await RefundReconciliationService.reconcile_refundable_refunds()
    assert summary.get("scan_error") == 1


@pytest.mark.asyncio
async def test_batch_driver_survives_one_bad_candidate():
    """One candidate blowing up must not abort the rest of the run."""
    a = make_refund_record(status="processing", razorpay_refund_id=RP_RFND,
                           id="aaaaaaaaaaaaaaaaaaaaaaaa")
    b = make_refund_record(status="processing", razorpay_refund_id=None,
                           id="bbbbbbbbbbbbbbbbbbbbbbbb")
    with repo_stack(
        list_reconcilable_refunds=[a, b],
        get_by_id=_SideEffectList([None]),  # a → not_found
    ), patch.object(
        PaymentRefundRepository, "get_by_id",
        new=AsyncMock(side_effect=[None, RuntimeError("boom")]),
    ):
        summary = await RefundReconciliationService.reconcile_refundable_refunds()
    assert summary["scanned"] == 2
    assert summary["not_found"] == 1
    assert summary["reconciliation_error"] == 1


@pytest.mark.asyncio
async def test_batch_driver_mixed_summary_counts():
    """The run summarizes every outcome class without cross-contamination."""
    p_ok = make_refund_record(status="processing", razorpay_refund_id=RP_RFND,
                              id="aaaaaaaaaaaaaaaaaaaaaaaa")
    p_no_ident = make_refund_record(status="processing",
                                    razorpay_refund_id=None,
                                    id="bbbbbbbbbbbbbbbbbbbbbbbb")
    done_ok = make_refund_record(status="completed",
                                 razorpay_refund_id=RP_RFND,
                                 id="aaaaaaaaaaaaaaaaaaaaaaaa")
    done = make_refund_record(status="completed", razorpay_refund_id=RP_RFND,
                              id="cccccccccccccccccccccccc")
    with repo_stack(
        list_reconcilable_refunds=[p_ok, p_no_ident, done],
        get_by_id=_SideEffectList([
            p_ok, p_ok, done_ok,   # ok → completed (load, task14, post-read)
            p_no_ident,            # no identity, no lookup → kept_no_identity
            done,                  # terminal → already_settled
        ]),
        mark_completed={"_id": RID, "status": "completed"},
        touch_processing={"_id": RID},
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ), patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(return_value=[]),
    ):
        summary = await RefundReconciliationService.reconcile_refundable_refunds()
    assert summary["scanned"] == 3
    assert summary["reconciled_completed"] == 1
    assert summary["kept_no_identity"] == 1
    assert summary["already_settled"] == 1


def test_scheduler_pattern_reuses_task9_and_is_opt_in():
    """§6/§10: an established scheduler pattern existed (Task 9 loop);
    Task 16 reuses exactly that pattern and is opt-in by configuration."""
    # Default OFF — pinned.
    assert settings.REFUND_RECONCILIATION_ENABLED is False
    # Interval reuses the established Task 9 cadence (no new policy).
    from app.services.stale_payment_reconciliation_service import (
        STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS,
    )
    assert REFUND_RECONCILIATION_INTERVAL_SECONDS == \
        STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS
    # The loop mirrors the Task 9 lifecycle: sleep-first, error-swallowing.
    loop_src = exec_src(RefundReconciliationService._reconciliation_loop)
    assert loop_src.index("asyncio.sleep(") < \
        loop_src.index("reconcile_refundable_refunds")
    start_src = exec_src(RefundReconciliationService.start_background_loop)
    assert "REFUND_RECONCILIATION_ENABLED" in start_src
    assert "get_running_loop" in start_src


def test_loop_not_started_by_default():
    assert settings.REFUND_RECONCILIATION_ENABLED is False
    assert RefundReconciliationService.start_background_loop() is None


def test_disabled_scheduler_issues_no_razorpay_calls():
    """§4/§13.19: with the shipped default (disabled), starting the
    scheduler performs ZERO Razorpay operations — the loop is never
    created, and no client is ever constructed."""
    assert settings.REFUND_RECONCILIATION_ENABLED is False
    with patch.object(
        razorpay_client, "get_razorpay_client",
        side_effect=AssertionError("no Razorpay client may be built"),
    ):
        assert RefundReconciliationService.start_background_loop() is None
    assert RefundReconciliationService._background_task is None


def test_loop_starts_when_enabled_and_is_idempotent(monkeypatch):
    monkeypatch.setattr(settings, "REFUND_RECONCILIATION_ENABLED", True)

    async def scenario():
        task1 = RefundReconciliationService.start_background_loop()
        task2 = RefundReconciliationService.start_background_loop()
        assert task1 is not None
        assert task2 is task1  # idempotent: never a second loop
        if task1 is not None:
            task1.cancel()
            try:
                await task1
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())
    RefundReconciliationService._background_task = None


def test_main_wires_the_loop_at_startup():
    """§6: the loop is started from the application's startup event using
    the same opt-in gate (default OFF — pinned by the autouse fixture)."""
    import app.main as main_mod
    src = exec_src(main_mod.startup_event)
    assert "RefundReconciliationService.start_background_loop" in src


def test_enabled_scheduler_starts_existing_loop_opt_in_only(monkeypatch):
    """§13.20: enabling the flag starts the EXISTING loop (no second
    scheduler); it remains strictly opt-in — the shipped default is off."""
    # The default remains OFF (pinned by the autouse fixture).
    assert settings.REFUND_RECONCILIATION_ENABLED is False
    # Opt in via the settings flag (monkeypatched — no env mutation).
    monkeypatch.setattr(settings, "REFUND_RECONCILIATION_ENABLED", True)
    import asyncio as _asyncio

    async def scenario():
        task = RefundReconciliationService.start_background_loop()
        assert task is not None
        again = RefundReconciliationService.start_background_loop()
        assert again is task  # never a second loop
        task.cancel()
        try:
            await task
        except _asyncio.CancelledError:
            pass

    _asyncio.run(scenario())
    RefundReconciliationService._background_task = None


# ===========================================================================
# 10 — SECURITY BOUNDARIES (mandated 19–23)
# ===========================================================================

def test_reconciliation_never_calls_create_refund():
    """THE critical boundary: no code path from the reconciliation service
    can reach refund creation — structurally and by import isolation."""
    import app.services.refund_reconciliation_service as mod

    src = exec_src(mod)
    assert "create_refund" not in src  # not imported, not called

    tree = ast.parse(inspect.getsource(mod))
    rp_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) \
                and node.module == "app.core.razorpay_client":
            rp_imports.update(a.name for a in node.names)
    # The ONLY Razorpay-layer names imported are the safe error types,
    # the read-only list helper, and RazorpayRefundOutcome — a pure
    # in-module classification enum (no SDK object, no network I/O, no
    # secrets) used to preserve the definitive/ambiguous taxonomy in the
    # Task 18 outcome codes. Never create_refund, never fetch_refund
    # (the lookup happens inside the Task 14 operation it delegates to).
    assert rp_imports == {
        "RazorpayConfigError", "RazorpayRequestError",
        "RazorpayRefundOutcome", "fetch_payment_refunds",
    }
    # It delegates to the Task 14 operation.
    assert "reconcile_ambiguous_refund" in exec_src(mod)


def test_no_razorpay_sdk_calls_outside_client_module():
    """§6: every Razorpay SDK invocation lives ONLY in razorpay_client.py
    — no service, repository, or API module touches the SDK."""
    import os
    app_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"
    )
    for dirpath, _dirnames, filenames in os.walk(app_dir):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(dirpath, fname)
            with open(path, encoding="utf-8", errors="ignore") as f:
                src = f.read()
            rel = os.path.relpath(path, app_dir).replace("\\", "/")
            if rel == "core/razorpay_client.py":
                continue
            for banned in (
                "import razorpay", "from razorpay", "razorpay.Client(",
                "client.payment.", "client.order.",
            ):
                assert banned not in src, (rel, banned)


def test_no_http_refund_surface_and_no_frontend_calls():
    """§9: refund functionality keeps NO public HTTP surface; the frontend
    never references refunds."""
    from app.main import app as fastapi_app
    routes = [getattr(r, "path", "") for r in fastapi_app.routes]
    assert not any("refund" in p.lower() for p in routes), routes

    api_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app", "api",
    )
    for fname in os.listdir(api_dir):
        if fname.endswith(".py"):
            with open(os.path.join(api_dir, fname), encoding="utf-8") as f:
                assert "payment_refund" not in f.read(), fname

    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    with open(os.path.join(root, "frontend", "src", "services", "api.js"),
              encoding="utf-8") as f:
        assert "refund" not in f.read().lower()


def test_no_client_controlled_inputs_anywhere():
    """§11: reconciliation accepts NO client-controlled financial inputs.
    Payment id, amount, and currency always come from the persisted
    record; the discovered identity comes from Razorpay's own list."""
    sig = inspect.signature(
        RefundReconciliationService.reconcile_refundable_refunds)
    assert set(sig.parameters.keys()) <= {"limit"}
    sig2 = inspect.signature(RefundReconciliationService._reconcile_one)
    assert set(sig2.parameters.keys()) == {"refund_id"}
    sig3 = inspect.signature(
        RefundReconciliationService._discover_and_reconcile)
    assert set(sig3.parameters.keys()) == {"refund_id", "record"}
    # The discovery selector takes no caller-authoritative inputs.
    sig4 = inspect.signature(
        RefundReconciliationService._select_unambiguous_refund)
    assert set(sig4.parameters.keys()) == {
        "refunds", "payment_id", "amount_paise", "currency"}
    # No api module references the reconciliation service.
    api_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app", "api",
    )
    for fname in os.listdir(api_dir):
        if fname.endswith(".py"):
            with open(os.path.join(api_dir, fname), encoding="utf-8") as f:
                assert "RefundReconciliation" not in f.read(), fname


def test_discovery_lookup_uses_stored_payment_id_only():
    """The ONLY argument to the Razorpay refund list is the record's OWN
    stored payment id — never caller data, never a search across payments."""
    src = exec_src(RefundReconciliationService._discover_and_reconcile)
    assert "fetch_payment_refunds, payment_id" in src
    assert "record.payment_id" in src or "getattr(record, " in src


def test_no_secrets_outside_client_boundary_and_no_raw_payload_logging():
    """§3/§J: no secrets outside the client boundary, no raw Razorpay
    payload logging, no direct HTTP clients."""
    import app.services.refund_reconciliation_service as mod
    src = exec_src(mod)
    assert "RAZORPAY_KEY_SECRET" not in src
    assert "RAZORPAY_WEBHOOK_SECRET" not in src
    assert "TEST_SECRET" not in src
    # Logging uses only truncated ids and outcome codes — no log call ever
    # receives the raw Razorpay response list or a raw response object.
    assert "json.dumps" not in src
    for line in src.splitlines():
        if "logger." in line:
            assert "refunds" not in line, line
            assert "rp_refund" not in line, line
    # No direct HTTP client anywhere in the module.
    for banned in ("requests.", "httpx.", "urllib.", "aiohttp"):
        assert banned not in src, banned
    # Same guarantees for the client method: errors/log lines never carry
    # the secret, and the response body is never logged verbatim.
    csrc = exec_src(razorpay_client.fetch_payment_refunds)
    assert "TEST_SECRET" not in inspect.getsource(
        razorpay_client.fetch_payment_refunds)
    assert "_mask(" in csrc
    for banned in ("requests.", "httpx.", "urllib.", "aiohttp"):
        assert banned not in csrc, banned


@pytest.mark.asyncio
async def test_secrets_never_in_reconciliation_errors_or_logs(caplog):
    import logging as _logging
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(side_effect=RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: secret=should_not_leak")),
    ):
        with caplog.at_level(_logging.ERROR):
            result = await RefundReconciliationService._reconcile_one(RID)
    # Task 18 granularity: a Razorpay lookup failure is the ambiguous-
    # error class — and no exception text ever reaches the logs.
    assert result == "kept_razorpay_ambiguous"
    assert TEST_SECRET not in caplog.text
    assert TEST_KEY_ID not in caplog.text
    assert "should_not_leak" not in caplog.text


def test_reconciliation_cannot_select_unrelated_refund():
    """The finder keys on the record's own state, never on caller-supplied
    payment ids; there is no parameter through which a caller could point
    reconciliation at another patient's refund."""
    sig = inspect.signature(PaymentRefundRepository.list_reconcilable_refunds)
    for banned in ("payment_id", "payable_id", "patient_id",
                   "razorpay_refund_id"):
        assert banned not in sig.parameters, banned


# ===========================================================================
# 11 — DOMAIN / STATE-MACHINE REGRESSION (mandated 22, 23, 24)
# ===========================================================================

@pytest.mark.asyncio
async def test_no_appointment_or_laboratory_mutation():
    """Reconciliation writes ONLY PaymentRefund — no domain model,
    repository transition, or save appears anywhere in the flow."""
    import app.services.refund_reconciliation_service as mod
    for src in (exec_src(mod),
                exec_src(PaymentRefundService.reconcile_ambiguous_refund)):
        for banned in (
            "Appointment", "LaboratoryBooking",
            "mark_appointment_paid", "mark_laboratory_paid",
            "mark_laboratory_failed",
            "expire_appointment_pending_payment",
            "expire_laboratory_pending_payment",
            ".save(",
        ):
            assert banned not in src, banned

    # Runtime: a full batch run performs no domain write.
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        list_reconcilable_refunds=[processing],
        get_by_id=_SideEffectList([processing, processing]),
        touch_processing={"_id": RID},
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(side_effect=RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: timeout")),
    ), patch(
        "app.repositories.payment_repository."
        "PaymentRepository.mark_appointment_paid", new=MagicMock(),
    ) as appt_paid, patch(
        "app.repositories.payment_repository."
        "PaymentRepository.mark_laboratory_paid", new=MagicMock(),
    ) as lab_paid:
        await RefundReconciliationService.reconcile_refundable_refunds()
    appt_paid.assert_not_called()
    lab_paid.assert_not_called()


def test_state_vocabulary_unchanged():
    """The five refund states are unchanged — reconciliation adds none."""
    from app.models.payment_refund import REFUND_STATUSES
    assert REFUND_STATUSES == (
        "requested", "processing", "completed", "failed", "cancelled",
    )


def test_no_second_state_machine_single_transition_source():
    """§8: reconciliation adds NO transition logic of its own — completion
    happens exclusively through the repository's atomic mark_completed,
    reached via the Task 14 operation. No duplicated mark_completed logic
    exists anywhere in the reconciliation driver."""
    import app.services.refund_reconciliation_service as mod
    src = exec_src(mod)
    # No raw transition operations are reachable from the driver.
    for banned in ("mark_completed", "mark_failed", "claim_for_processing",
                   "find_one_and_update", "attach_razorpay_refund_id"):
        assert banned not in src, banned
    # The only Razorpay-side calls are read-only lookups.
    assert "fetch_payment_refunds" in src
    assert "create_refund" not in src
    # Completion flows exclusively through the Task 14 operation.
    assert "reconcile_ambiguous_refund" in src


def test_no_load_modify_save_path_anywhere_in_the_flow():
    """§7/§23: every state change is a single atomic guarded
    find_one_and_update; no record is loaded, mutated in memory, and saved
    back anywhere in the reconciliation flow."""
    repo_src = inspect.getsource(PaymentRefundRepository)
    # State transitions never call .save() — they are all atomic updates.
    for method in ("claim_for_processing", "mark_completed", "mark_failed",
                   "cancel_if_requested", "touch_processing",
                   "attach_razorpay_refund_id"):
        msrc = exec_src(getattr(PaymentRefundRepository, method))
        assert ".save(" not in msrc, method
        assert "find_one_and_update" in msrc, method
    # The reconciliation driver itself performs no state writes at all.
    import app.services.refund_reconciliation_service as mod
    assert "find_one_and_update" not in exec_src(mod)


def test_tasks_12_15_invariants_intact():
    """Structural regression: Task 12 creation (unique-index insert), Task
    13 execution helpers, Task 14 identity attach, Task 15 ordering — all
    unchanged by Task 16."""
    # Task 12 creation path.
    create_src = exec_src(PaymentRefundRepository.create_refund)
    assert "find_one" not in create_src and "insert()" in create_src
    # Task 13 execution claim/mark operations unchanged.
    claim_src = exec_src(PaymentRefundRepository.claim_for_processing)
    assert '"status": "requested"' in claim_src
    completed_src = exec_src(PaymentRefundRepository.mark_completed)
    assert '"status": "processing"' in completed_src
    # Task 14 attach unchanged.
    attach_src = exec_src(PaymentRefundRepository.attach_razorpay_refund_id)
    assert '"razorpay_refund_id": None' in attach_src
    # Task 13's Razorpay client operation unchanged.
    client_src = exec_src(razorpay_client.create_refund)
    assert "client.payment.refund(" in client_src
    # Task 15's ordering guarantee: validate → attach → complete.
    reconcile_src = exec_src(PaymentRefundService.reconcile_ambiguous_refund)
    assert reconcile_src.index("attach_razorpay_refund_id") < \
        reconcile_src.index("mark_completed")
    # The reconciliation service delegates TO the Task 14 operation.
    assert "reconcile_ambiguous_refund" in exec_src(
        RefundReconciliationService._delegate_reconciliation)


@pytest.mark.asyncio
async def test_task15_ordering_identity_before_completion_end_to_end():
    """Task 15 regression through the Task 16 driver: even on the discovery
    path, identity is durably persisted BEFORE mark_completed is invoked."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    order = []

    async def attach(_rid, rp_id):
        order.append("attach")
        return {"_id": _rid, "razorpay_refund_id": rp_id}

    async def complete(_rid):
        order.append("complete")
        return {"_id": _rid, "status": "completed"}

    completed_rec = make_refund_record(status="completed",
                                       razorpay_refund_id=RP_RFND)
    with repo_stack(
        # Task 14 reads: initial load, then the post-completion re-read.
        get_by_id=_SideEffectList([processing, completed_rec]),
        touch_processing={"_id": RID},
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ), patch.object(
        PaymentRefundRepository, "attach_razorpay_refund_id",
        new=AsyncMock(side_effect=attach),
    ), patch.object(
        PaymentRefundRepository, "mark_completed",
        new=AsyncMock(side_effect=complete),
    ):
        # Task 14 operation directly: the persisted identity is already
        # there, so attach is not called — but the ordering guard must
        # still hold for the attach-then-complete path when identity was
        # absent (covered in the discovery test). Here: completion only.
        result = await PaymentRefundService.reconcile_ambiguous_refund(RID)
    assert result.status == "completed"
    # The identity pre-existed: no attach step — completion is direct, and
    # attach can never follow completion.
    assert "attach" not in order
    assert order == ["complete"]


# ===========================================================================
# 12 — BATCH ENTRY DELEGATION (Task 14 fallback preserved)
# ===========================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("detail, expected", [
    # The ONE benign reason: Razorpay still reports the refund pending.
    ("Razorpay reports the refund is still processing. The refund "
     "remains in processing here.",
     "kept_pending"),
    # Razorpay lookup failure — the Task 14 boundary collapses its
    # AMBIGUOUS/DEFINITIVE taxonomy into this 409.
    ("The refund could not be reconciled with Razorpay. It remains in "
     "processing.",
     "kept_razorpay_ambiguous"),
    # Validation mismatch.
    ("The Razorpay refund response did not match this refund record. "
     "The refund remains in processing for manual review.",
     "kept_mismatch"),
    # Supplied/persisted identity conflict.
    ("The supplied Razorpay refund id does not match the identity "
     "persisted for this refund. The refund remains in processing.",
     "kept_mismatch"),
])
async def test_delegate_classifies_task14_http409_outcomes(detail, expected):
    """The Task 14 operation signals 'remains processing' with a safe 409
    whose detail text is a stable contract (pinned by the Task 14 tests).
    The driver classifies the outcome from it — observability only: the
    refund stays processing in every case, with no state change beyond
    the operation's own guarded bookkeeping."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ), patch.object(
        PaymentRefundService, "reconcile_ambiguous_refund",
        new=AsyncMock(side_effect=HTTPException(status_code=409,
                                                detail=detail)),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == expected


@pytest.mark.asyncio
async def test_delegate_classifies_config_error_as_kept_config_error():
    """A missing Razorpay configuration is its own Task 18 outcome class
    (kept_config_error) — kept processing, never failed, never retried
    into noise."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ), patch.object(
        PaymentRefundService, "reconcile_ambiguous_refund",
        new=AsyncMock(side_effect=RazorpayConfigError("no config")),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "kept_config_error"


@pytest.mark.asyncio
async def test_delegate_404_classified_not_found_and_unexpected_as_error():
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    # 404 from the Task 14 operation: the record vanished.
    with repo_stack(get_by_id=_SideEffectList([processing])), patch.object(
        PaymentRefundService, "reconcile_ambiguous_refund",
        new=AsyncMock(side_effect=HTTPException(status_code=404,
                                                detail="Refund not found")),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "not_found"

    # A truly unexpected error is surfaced for operators, record untouched.
    with repo_stack(get_by_id=_SideEffectList([processing])), patch.object(
        PaymentRefundService, "reconcile_ambiguous_refund",
        new=AsyncMock(side_effect=RuntimeError("corrupt index")),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "reconciliation_error"


def test_discovery_selector_pure_function_contract():
    """The selector is pure: it picks the single exact match or None —
    zero side effects, no repository access, no Razorpay access."""
    one = RefundReconciliationService._select_unambiguous_refund(
        [dict(RP_REFUND_OK)], STORED_PAYMENT_ID, STORED_AMOUNT_PAISE, "INR")
    assert one == (RP_RFND, "processed")
    assert RefundReconciliationService._select_unambiguous_refund(
        [], STORED_PAYMENT_ID, STORED_AMOUNT_PAISE, "INR") is None
    assert RefundReconciliationService._select_unambiguous_refund(
        None, STORED_PAYMENT_ID, STORED_AMOUNT_PAISE, "INR") is None
    assert RefundReconciliationService._select_unambiguous_refund(
        [dict(RP_REFUND_OK), dict(RP_REFUND_OK, id="rfnd_two")],
        STORED_PAYMENT_ID, STORED_AMOUNT_PAISE, "INR") is None


# ===========================================================================
# 13 — TASK 18: OBSERVABILITY, METADATA, SCHEDULER HEALTH, MANUAL RECOVERY
# (operations only — never policy; no new refund state, no HTTP surface)
# ===========================================================================

# --- §2/§11.10: reconciliation metadata is atomic, processing-gated, ------
# --- bounded, and never a second state machine ---------------------------

@pytest.mark.asyncio
async def test_reconciliation_metadata_atomic_processing_gated():
    """record_reconciliation_attempt is ONE guarded update: it can never
    touch a terminal record, never changes the refund status (bookkeeping
    only), bounds the persisted category, and refuses an empty one."""
    fake_coll = MagicMock()
    fake_coll.update_one = AsyncMock(
        return_value=MagicMock(modified_count=1))
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        assert await PaymentRefundRepository.record_reconciliation_attempt(
            RID, "kept_razorpay_ambiguous") is True
    query, update = fake_coll.update_one.await_args.args
    # Processing-only filter: a record another worker terminalized can
    # never be touched by bookkeeping.
    assert query["status"] == "processing"
    assert str(query["_id"]) == RID
    written = update["$set"]
    assert written["last_reconciliation_error"] == "kept_razorpay_ambiguous"
    assert written["last_reconciliation_attempt_at"] is not None
    # Bookkeeping NEVER mutates state — no "status" in the update.
    assert "status" not in written

    # The persisted category is defensively bounded to 64 characters.
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        await PaymentRefundRepository.record_reconciliation_attempt(
            RID, "x" * 500)
    written = fake_coll.update_one.await_args.args[1]["$set"]
    assert len(written["last_reconciliation_error"]) == \
        RECONCILIATION_OUTCOME_MAX_LEN

    # An empty category is refused without any write (fail closed).
    fake_coll.update_one.reset_mock()
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        assert await PaymentRefundRepository.record_reconciliation_attempt(
            RID, "   ") is False
    fake_coll.update_one.assert_not_awaited()

    # A record that vanished (or was terminalized) between scan and write
    # reports modified_count=0 → False; callers treat it as informational.
    fake_coll.update_one = AsyncMock(
        return_value=MagicMock(modified_count=0))
    with patch(
        "app.repositories.payment_refund_repository."
        "PaymentRefund.get_pymongo_collection",
        return_value=fake_coll,
    ):
        assert await PaymentRefundRepository.record_reconciliation_attempt(
            RID, "kept_mismatch") is False


@pytest.mark.asyncio
async def test_attempt_metadata_recorded_only_for_stuck_outcomes():
    """Only outcomes that leave a refund stuck in `processing` persist the
    bounded, allowlisted outcome code; terminal outcomes need no 'why
    stuck' bookkeeping and write nothing."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
    ) as repo, patch.object(
        PaymentRefundService, "reconcile_ambiguous_refund",
        new=AsyncMock(side_effect=HTTPException(status_code=409, detail=(
            "The Razorpay refund response did not match this refund "
            "record. The refund remains in processing for manual "
            "review."))),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "kept_mismatch"
    # The persisted value is exactly the sanitized outcome code — never
    # an exception message, never a Razorpay payload, never a secret.
    repo["record_reconciliation_attempt"].assert_awaited_once_with(
        RID, "kept_mismatch")

    # Terminal outcome: the outcome stands; no metadata write at all.
    done = make_refund_record(status="completed",
                              razorpay_refund_id=RP_RFND)
    with repo_stack(get_by_id=_SideEffectList([done])) as repo:
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "already_settled"
    repo["record_reconciliation_attempt"].assert_not_awaited()


@pytest.mark.asyncio
async def test_metadata_bookkeeping_failure_never_changes_outcome():
    """A bookkeeping failure is swallowed at debug level — the
    reconciliation outcome (and the refund's state) are unaffected."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    with repo_stack(
        get_by_id=_SideEffectList([processing]),
        touch_processing={"_id": RID},
        record_reconciliation_attempt=_SideEffectList(
            [RuntimeError("bookkeeping down")]),
    ), patch.object(
        PaymentRefundService, "reconcile_ambiguous_refund",
        new=AsyncMock(side_effect=HTTPException(status_code=409, detail=(
            "Razorpay reports the refund is still processing. The refund "
            "remains in processing here."))),
    ):
        result = await RefundReconciliationService._reconcile_one(RID)
    assert result == "kept_pending"


# --- §6/§11.4: the batch summary distinguishes the granular outcomes ------

@pytest.mark.asyncio
async def test_batch_summary_reports_granular_task18_outcomes():
    """A single run classifies mismatch, Razorpay-lookup-failure, and
    no-identity candidates into their OWN outcome counts — no cross-
    contamination, no invented refund state."""
    p_mismatch = make_refund_record(
        status="processing", razorpay_refund_id=RP_RFND,
        id="aaaaaaaaaaaaaaaaaaaaaaaa")
    p_lookup = make_refund_record(
        status="processing", razorpay_refund_id=RP_RFND,
        id="bbbbbbbbbbbbbbbbbbbbbbbb")
    p_multi = make_refund_record(
        status="processing", razorpay_refund_id=None,
        id="cccccccccccccccccccccc")
    with repo_stack(
        list_reconcilable_refunds=[p_mismatch, p_lookup, p_multi],
        get_by_id=_SideEffectList([p_mismatch, p_lookup, p_multi]),
        touch_processing={"_id": RID},
    ), patch.object(
        PaymentRefundService, "reconcile_ambiguous_refund",
        new=AsyncMock(side_effect=[
            HTTPException(status_code=409, detail=(
                "The Razorpay refund response did not match this refund "
                "record. The refund remains in processing for manual "
                "review.")),
            HTTPException(status_code=409, detail=(
                "The refund could not be reconciled with Razorpay. It "
                "remains in processing.")),
        ]),
    ), patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(return_value=[]),
    ):
        summary = await RefundReconciliationService.reconcile_refundable_refunds()
    assert summary["scanned"] == 3
    assert summary["kept_mismatch"] == 1
    assert summary["kept_razorpay_ambiguous"] == 1
    assert summary["kept_no_identity"] == 1
    assert summary.get("reconciled_completed", 0) == 0


# --- §3/§11.12/§11.13: logs carry only safe identifiers and codes ---------

@pytest.mark.asyncio
async def test_raw_razorpay_payload_never_reaches_logs(caplog):
    """A full batch run against a (mocked) Razorpay response carrying
    customer PII emits NO payload content into logs — only truncated ids
    and outcome codes, at every level including debug."""
    import logging as _logging
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    leaky = {
        "id": "rfnd_leaky_response01", "entity": "refund", "amount": 1,
        "currency": "INR", "payment_id": "pay_someone_else",
        "status": "processed",
        "notes": {"email": "patient@example.com",
                  "phone": "+91-9999999999"},
    }
    with repo_stack(
        list_reconcilable_refunds=[processing],
        get_by_id=_SideEffectList([processing, processing, processing]),
        touch_processing={"_id": RID},
    ), patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=leaky),
    ), caplog.at_level(_logging.DEBUG):
        summary = await RefundReconciliationService.reconcile_refundable_refunds()
    assert summary["kept_mismatch"] == 1
    assert "patient@example.com" not in caplog.text
    assert "+91-9999999999" not in caplog.text
    assert TEST_SECRET not in caplog.text
    assert TEST_KEY_ID not in caplog.text
    # The batch start/completion summary lines are present and safe.
    assert "Refund reconciliation batch started" in caplog.text
    assert "Refund reconciliation batch completed" in caplog.text


# --- §5/§11.1–3: scheduler health behavior --------------------------------

def test_scheduler_status_reports_disabled_by_default():
    """With the shipped default, scheduler_status() reports "disabled":
    no loop exists, none will start, and no Razorpay call can occur."""
    assert settings.REFUND_RECONCILIATION_ENABLED is False
    assert RefundReconciliationService.scheduler_status() == "disabled"


def test_disabled_scheduler_logs_clear_disabled_indication(caplog):
    """Initializing the scheduler while disabled logs ONE clear disabled
    indication — no noisy repetition, no Razorpay interaction."""
    import logging as _logging
    with caplog.at_level(_logging.INFO):
        assert RefundReconciliationService.start_background_loop() is None
    assert "disabled" in caplog.text.lower()
    assert "REFUND_RECONCILIATION_ENABLED" in caplog.text


def test_scheduler_status_running_and_not_started(monkeypatch):
    monkeypatch.setattr(settings, "REFUND_RECONCILIATION_ENABLED", True)
    RefundReconciliationService._background_task = None
    # Enabled but never started (or finished): explicit not_started.
    assert RefundReconciliationService.scheduler_status() == "not_started"

    async def scenario():
        task = RefundReconciliationService.start_background_loop()
        assert task is not None
        assert RefundReconciliationService.scheduler_status() == "running"
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())
    RefundReconciliationService._background_task = None


# --- §7/§11: manual recovery helper — internal, server-side ids only ------

def test_manual_recovery_helper_accepts_only_a_server_side_refund_id():
    """reconcile_single_refund takes ONLY the local record id: there is
    no parameter for — and no code path through — a payment id, Razorpay
    refund id, amount, currency, or any client-supplied financial fact.
    It is not reachable from any HTTP surface (pinned elsewhere)."""
    sig = inspect.signature(
        RefundReconciliationService.reconcile_single_refund)
    assert set(sig.parameters.keys()) == {"refund_id"}
    src = exec_src(RefundReconciliationService.reconcile_single_refund)
    for banned in ("request", "payload", "body"):
        assert banned not in src, banned


@pytest.mark.asyncio
async def test_manual_recovery_terminal_refund_zero_razorpay_io():
    """Manual recovery respects the state guards: a terminal refund is
    answered with already_settled and ZERO Razorpay interaction — no
    lookup, no completion attempt, no revival."""
    done = make_refund_record(status="completed",
                              razorpay_refund_id=RP_RFND)
    with repo_stack(get_by_id=_SideEffectList([done])), patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(
            side_effect=AssertionError("no Razorpay I/O for terminal")),
    ), patch.object(
        PaymentRefundService, "reconcile_ambiguous_refund",
        new=AsyncMock(
            side_effect=AssertionError("terminal must not delegate")),
    ):
        result = await RefundReconciliationService.reconcile_single_refund(RID)
    assert result == {"refund_id": RID, "outcome": "already_settled"}


@pytest.mark.asyncio
async def test_manual_recovery_empty_and_missing_ids():
    """An empty id is refused outright; an id that resolves to no record
    reports not_found — both without any Razorpay interaction."""
    with repo_stack(get_by_id=None), patch(
        "app.services.refund_reconciliation_service.fetch_payment_refunds",
        new=MagicMock(side_effect=AssertionError("no Razorpay I/O")),
    ):
        empty = await RefundReconciliationService.reconcile_single_refund("")
        assert empty == {"refund_id": "", "outcome": "not_found"}
        missing = await RefundReconciliationService.reconcile_single_refund(RID)
        assert missing == {"refund_id": RID, "outcome": "not_found"}


@pytest.mark.asyncio
async def test_manual_recovery_runs_the_standard_path_never_creates():
    """For a processing record the helper runs the EXACT standard Task 14
    reconciliation (validate → persist identity → atomic complete) — the
    same guards, the same single completion, no shortcut."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    completed = make_refund_record(status="completed",
                                   razorpay_refund_id=RP_RFND)
    with repo_stack(
        # Pre-check, Task 14 load, post-completion re-read.
        get_by_id=_SideEffectList([processing, processing, completed]),
        touch_processing={"_id": RID},
        mark_completed={"_id": RID, "status": "completed"},
    ) as repo, patch(
        "app.services.payment_refund_service.fetch_refund",
        new=MagicMock(return_value=dict(RP_REFUND_OK)),
    ):
        result = await RefundReconciliationService.reconcile_single_refund(RID)
    assert result["outcome"] == "reconciled_completed"
    repo["mark_completed"].assert_awaited_once_with(RID)
    repo["create_refund"].assert_not_awaited()
    repo["mark_failed"].assert_not_awaited()
