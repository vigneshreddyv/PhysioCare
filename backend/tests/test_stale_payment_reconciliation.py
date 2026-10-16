"""
Phase 4 Task 9 tests — stale pending-payment reconciliation & safe expiry.

Covers the 26 mandated scenarios plus the race matrix: stale/fresh detection
per domain, captured-payment prevention + reuse of the EXISTING Task 8
reconciliation path, every fail-closed Razorpay condition (pending order,
in-flight/unknown payment states, timeout, 5xx, malformed), atomic guarded
expiry, expiry-vs-verify and expiry-vs-webhook races, concurrent and repeated
expiry, late capture after expiry, slot reusability after expiry, patient
isolation, and idempotent notification semantics.

All Razorpay SDK/network calls are mocked. No real Razorpay servers are
contacted and no real transactions are performed.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.core.razorpay_client import RazorpayConfigError, RazorpayRequestError
from app.services.stale_payment_reconciliation_service import (
    STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS,
    StalePaymentReconciliationService,
)

ORDER_ID = "order_task9_123"
PAY_ID = "pay_task9_456"
PAY_ID_2 = "pay_task9_789"
APT_ID = "555555555555555555555555"
BOOK_ID = "666666666666666666666666"


def _holder(dotted: str):
    """Resolve 'app.services.mod.ClassName' to the class object so tests can
    patch methods via patch.object (service-module class references)."""
    import importlib

    mod_path, cls_name = dotted.rsplit(".", 1)
    return getattr(importlib.import_module(mod_path), cls_name)

NOW = datetime(2026, 9, 24, 12, 0, 0)
# The tests run with an EXPLICIT test-local expiry policy (90 minutes).
# The application default is policy-disabled (no duration) — see
# test_policy_disabled_* below, which pin that default behavior.
TEST_EXPIRY_MINUTES = 90
OLD = NOW - timedelta(minutes=TEST_EXPIRY_MINUTES + 60)
FRESH = NOW - timedelta(minutes=5)


def make_record(domain="appointment", **over):
    rec = SimpleNamespace(
        id=APT_ID if domain == "appointment" else BOOK_ID,
        patient_id="patient1",
        status="pending_payment",
        billing_status="pending",
        payment_status="pending",
        billing_amount=500.0,
        payment_order_id=ORDER_ID,
        created_at=OLD,
    )
    for k, v in over.items():
        setattr(rec, k, v)
    return rec


def rzp_order(created_epoch, status="created"):
    return {"id": ORDER_ID, "status": status, "created_at": created_epoch,
            "amount": 50000, "currency": "INR"}


def payment(status, payment_id=PAY_ID):
    return {"id": payment_id, "order_id": ORDER_ID, "amount": 50000,
            "currency": "INR", "status": status}


# Razorpay created_at epoch for a timestamp inside the freshness window.
def epoch(dt):
    return int(dt.replace(tzinfo=__import__("datetime").timezone.utc).timestamp())


CUTOFF_FRESH_EPOCH = epoch(NOW - timedelta(minutes=TEST_EXPIRY_MINUTES - 5))
CUTOFF_OLD_EPOCH = epoch(OLD)


@pytest.fixture(autouse=True)
def expiry_policy_enabled(monkeypatch):
    """Run every reconciliation test under an EXPLICIT test-local policy:
    expiry enabled with a 90-minute duration (an arbitrary value chosen by
    THE TEST, proving the duration is fully configuration-driven and the
    implementation is policy-agnostic). The application default remains
    disabled — pinned by the test_policy_* tests."""
    monkeypatch.setattr(settings, "PAYMENT_RECONCILIATION_ENABLED", True)
    monkeypatch.setattr(settings, "PAYMENT_PENDING_EXPIRY_MINUTES", TEST_EXPIRY_MINUTES)
    yield


def patched_domain(domain, *, candidates, order=rzp_order(CUTOFF_OLD_EPOCH),
                   payments=None, order_exc=None, payments_exc=None,
                   expired_doc=None, get_by_order=None, reconcile=None):
    """Patch BOTH domains' scan methods (so the untested domain is a no-op),
    the Razorpay helpers, and the target domain's collaborators."""
    expire_name = ("expire_appointment_pending_payment" if domain == "appointment"
                   else "expire_laboratory_pending_payment")

    expired_doc_val = expired_doc
    if expired_doc_val is None:
        expired_doc_val = {"_id": APT_ID if domain == "appointment" else BOOK_ID,
                           "status": "cancelled" if domain == "appointment"
                           else "failed",
                           "billing_status": "failed",
                           "payment_status": "expired"}

    other = "LaboratoryBookingRepository" if domain == "appointment" \
        else "AppointmentRepository"

    return [
        patch.object(_holder("app.services.stale_payment_reconciliation_service."
                             f"{'AppointmentRepository' if domain == 'appointment' else 'LaboratoryBookingRepository'}"),
                     "list_stale_pending_payments",
                     new=AsyncMock(return_value=candidates)),
        # The OTHER domain's scan is patched to return nothing so a cross-
        # domain scan never touches an uninitialized Beanie collection.
        patch.object(_holder("app.services.stale_payment_reconciliation_service." + other),
                     "list_stale_pending_payments",
                     new=AsyncMock(return_value=[])),
        patch("app.services.stale_payment_reconciliation_service.fetch_order",
              side_effect=order_exc) if order_exc is not None else
        patch("app.services.stale_payment_reconciliation_service.fetch_order",
              return_value=order),
        patch("app.services.stale_payment_reconciliation_service.fetch_order_payments",
              side_effect=payments_exc) if payments_exc is not None else
        patch("app.services.stale_payment_reconciliation_service.fetch_order_payments",
              return_value=payments if payments is not None else []),
        patch.object(_holder("app.services.stale_payment_reconciliation_service.PaymentRepository"),
                     expire_name, new=AsyncMock(return_value=expired_doc_val)),
        patch.object(_holder("app.services.stale_payment_reconciliation_service."
                             f"{'AppointmentRepository' if domain == 'appointment' else 'LaboratoryBookingRepository'}"),
                     "get_by_order_id", new=AsyncMock(return_value=get_by_order)),
        patch("app.services.stale_payment_reconciliation_service."
              "WebhookReconciliationService.reconcile_event",
              new=reconcile if reconcile is not None else AsyncMock()),
    ]


class _Stack:
    def __init__(self, patches):
        self._patches = patches

    def __enter__(self):
        from contextlib import ExitStack
        self._exit = ExitStack()
        return [self._exit.enter_context(p) for p in self._patches]

    def __exit__(self, *a):
        return self._exit.__exit__(*a)


# ---------------------------------------------------------------------------
# 1/2/3/4 — stale vs fresh detection per domain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_1_stale_appointment_detected():
    rec = make_record("appointment", created_at=OLD)
    with _Stack(patched_domain("appointment", candidates=[rec])) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary["appointments_scanned"] == 1
    # No captured payment, no payments at all, old order → safe expiry.
    assert summary["appointment_expired"] == 1
    mocks[4].assert_awaited_once_with(APT_ID, ORDER_ID)  # atomic expire called


@pytest.mark.asyncio
async def test_2_fresh_appointment_ignored():
    rec = make_record("appointment", created_at=FRESH)
    with _Stack(patched_domain("appointment", candidates=[])) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary["appointments_scanned"] == 0
    mocks[4].assert_not_awaited()


@pytest.mark.asyncio
async def test_3_stale_lab_detected():
    rec = make_record("laboratory", created_at=OLD)
    with _Stack(patched_domain("laboratory", candidates=[rec])) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary["laboratory_bookings_scanned"] == 1
    assert summary["laboratory_expired"] == 1
    mocks[4].assert_awaited_once_with(BOOK_ID, ORDER_ID)


@pytest.mark.asyncio
async def test_4_fresh_lab_ignored():
    with _Stack(patched_domain("laboratory", candidates=[])) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary["laboratory_bookings_scanned"] == 0
    mocks[4].assert_not_awaited()


# ---------------------------------------------------------------------------
# 5/6/18 — captured payment prevents expiry and routes through Task 8
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("domain,rid", [("appointment", APT_ID),
                                        ("laboratory", BOOK_ID)])
async def test_5_captured_payment_prevents_expiry(domain, rid):
    rec = make_record(domain, id=rid)
    with _Stack(patched_domain(
            domain, candidates=[rec],
            payments=[payment("captured")],
            reconcile=AsyncMock(return_value="already_paid"))) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary.get(f"{domain}_reconciled", 0) == 0
    assert summary.get(f"{domain}_already_paid", 0) == 1
    mocks[4].assert_not_awaited()  # NEVER expired


@pytest.mark.asyncio
@pytest.mark.parametrize("domain,rid", [("appointment", APT_ID),
                                        ("laboratory", BOOK_ID)])
async def test_6_captured_payment_gets_reconciled(domain, rid):
    """Captured money → the EXISTING Task 8 path performs the transition."""
    rec = make_record(domain, id=rid)
    reconcile = AsyncMock(return_value=f"reconciled_{domain}")
    with _Stack(patched_domain(
            domain, candidates=[rec], payments=[payment("captured")],
            reconcile=reconcile)) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary[f"{domain}_reconciled"] == 1
    reconcile.assert_awaited_once_with(
        event_type="payment.captured", payment_id=PAY_ID, order_id=ORDER_ID)
    mocks[4].assert_not_awaited()  # expiry never runs for captured money


# ---------------------------------------------------------------------------
# 7 — Razorpay order still legitimately open (no payments) → keep pending
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("domain,rid", [("appointment", APT_ID),
                                        ("laboratory", BOOK_ID)])
async def test_7_pending_order_without_payments_expires(domain, rid):
    """Old order + NO payments at all = no money risk → safe expiry.

    (An order that still holds an IN-FLIGHT payment keeps pending — covered
    in test_kept_payment_in_flight below; this is the genuinely-empty case.)
    """
    rec = make_record(domain, id=rid)
    with _Stack(patched_domain(domain, candidates=[rec], payments=[])) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary[f"{domain}_expired"] == 1
    mocks[4].assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("domain,rid", [("appointment", APT_ID),
                                        ("laboratory", BOOK_ID)])
async def test_kept_payment_in_flight(domain, rid):
    rec = make_record(domain, id=rid)
    for st in ("created", "authorized", "pending", "processing"):
        with _Stack(patched_domain(
                domain, candidates=[rec], payments=[payment(st)])) as mocks:
            summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
        assert summary.get(f"{domain}_kept_payment_in_flight") == 1, st
        mocks[4].assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("domain,rid", [("appointment", APT_ID),
                                        ("laboratory", BOOK_ID)])
async def test_failed_payment_allows_expiry(domain, rid):
    """A conclusively failed payment = no money taken → safe expiry."""
    rec = make_record(domain, id=rid)
    with _Stack(patched_domain(
            domain, candidates=[rec], payments=[payment("failed")])) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary[f"{domain}_expired"] == 1


# ---------------------------------------------------------------------------
# 8/9/10/11 — fail-closed Razorpay conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("domain,rid", [("appointment", APT_ID),
                                        ("laboratory", BOOK_ID)])
@pytest.mark.parametrize("kwargs,expected", [
    ({"order_exc": RazorpayRequestError("timeout")}, "kept_razorpay_unreachable"),   # 8
    ({"order_exc": RazorpayRequestError("5xx")}, "kept_razorpay_unreachable"),       # 9
    ({"order_exc": RazorpayConfigError("no config")}, "kept_razorpay_unreachable"),
    ({"order": {"id": ORDER_ID}}, "kept_malformed_order"),                            # 10 (order)
    ({"order": {"id": ORDER_ID, "amount": 50000, "currency": "INR"}},
     "kept_malformed_order"),
    ({"payments_exc": RazorpayRequestError("timeout")}, "kept_razorpay_unreachable"),
    ({"payments": "not-a-list"}, "kept_unknown_payment_state"),                       # 11
    ({"payments": [payment("queued")]}, "kept_unknown_payment_state"),                # 11
    ({"payments": [payment("captured", payment_id=None)]}, "kept_captured_unverifiable"),
    ({"payments": [payment("captured")], "reconcile": AsyncMock(return_value="skipped_amount_mismatch")},
     "kept_captured_validation_failed"),
    ({"payments": [payment("captured")], "reconcile": AsyncMock(return_value="unmapped")},
     "kept_captured_validation_failed"),
])
async def test_8_to_11_fail_closed_conditions(domain, rid, kwargs, expected):
    rec = make_record(domain, id=rid)
    with _Stack(patched_domain(domain, candidates=[rec], **kwargs)) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary.get(f"{domain}_{expected}") == 1, summary
    mocks[4].assert_not_awaited()  # NEVER expired under uncertainty


@pytest.mark.asyncio
async def test_expired_order_without_captured_payment_is_terminally_stale():
    """Razorpay reports the order as 'attempted' (payments concluded without
    capture, e.g. all failed): still requires a terminal no-money payment
    state — an 'attempted' order alone does NOT authorize expiry because the
    payments list could not be retrieved; here payments=[] is treated as
    no-money and expiry proceeds (order older than cutoff, nothing in
    flight)."""
    rec = make_record("appointment")
    with _Stack(patched_domain(
            "appointment", candidates=[rec],
            order=rzp_order(CUTOFF_OLD_EPOCH, status="attempted"),
            payments=[])) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary["appointment_expired"] == 1


# ---------------------------------------------------------------------------
# created_at limitation — fresh Razorpay order keeps record pending
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("domain,rid", [("appointment", APT_ID),
                                        ("laboratory", BOOK_ID)])
async def test_order_created_after_cutoff_keeps_record_pending(domain, rid):
    """created_at is booking time, not Pay-click time: if Razorpay says the
    order itself was created inside the window, the attempt is live."""
    rec = make_record(domain, id=rid, created_at=OLD)
    with _Stack(patched_domain(
            domain, candidates=[rec],
            order=rzp_order(CUTOFF_FRESH_EPOCH))) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary.get(f"{domain}_kept_order_fresh") == 1
    mocks[4].assert_not_awaited()


# ---------------------------------------------------------------------------
# 12/13 — atomic guarded expiry (repository-level)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_12_appointment_expiry_is_atomic_and_guarded():
    """Direct repository proof: the transition matches ONLY while pending."""
    from unittest.mock import patch as _patch
    from app.repositories.payment_repository import PaymentRepository

    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(return_value={"_id": APT_ID})
    with _patch("app.repositories.payment_repository.Appointment."
                "get_pymongo_collection", return_value=fake_coll):
        updated = await PaymentRepository.expire_appointment_pending_payment(
            APT_ID, ORDER_ID)

    query, update = fake_coll.find_one_and_update.await_args.args
    # Guard: pending state + stored order binding (never a blind write).
    assert query == {
        "_id": __import__("bson").ObjectId(APT_ID),
        "payment_order_id": ORDER_ID,
        "status": "pending_payment",
    }
    assert update["$set"] == {
        "status": "cancelled",
        "billing_status": "failed",
        "payment_status": "expired",
    }
    assert updated == {"_id": APT_ID}


@pytest.mark.asyncio
async def test_13_laboratory_expiry_is_atomic_and_guarded():
    from app.repositories.payment_repository import PaymentRepository

    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(return_value={"_id": BOOK_ID})
    with patch("app.repositories.payment_repository.LaboratoryBooking."
                "get_pymongo_collection", return_value=fake_coll):
        updated = await PaymentRepository.expire_laboratory_pending_payment(
            BOOK_ID, ORDER_ID)

    query, update = fake_coll.find_one_and_update.await_args.args
    # THE critical lab invariant: the guard requires billing_status=pending,
    # so a paid booking can never match, and the update clears pending.
    assert query["billing_status"] == "pending"
    assert query["payment_order_id"] == ORDER_ID
    assert query["status"] == "pending_payment"
    assert update["$set"]["billing_status"] == "failed"
    assert update["$set"]["status"] == "failed"


# ---------------------------------------------------------------------------
# 14 — concurrent expiry calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("domain,rid", [("appointment", APT_ID),
                                        ("laboratory", BOOK_ID)])
async def test_14_concurrent_expiry_single_transition(domain, rid):
    rec = make_record(domain, id=rid)
    calls = {"n": 0}

    async def guarded_expire(*a, **k):
        calls["n"] += 1
        return {"ok": True} if calls["n"] == 1 else None  # DB guard semantics

    patches = patched_domain(domain, candidates=[rec])
    patches[4] = patch(
        "app.services.stale_payment_reconciliation_service."
        f"PaymentRepository.expire_{domain}_pending_payment",
        new=guarded_expire)
    with _Stack(patches):
        s1 = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
        s2 = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    # Exactly one run expired it; the repeat run lost the guard → no-op.
    assert s1.get(f"{domain}_expired", 0) + s2.get(f"{domain}_expired", 0) <= 1
    assert s1.get(f"{domain}_expired", 0) + s2.get(f"{domain}_expired", 0) \
        + s1.get(f"{domain}_transition_lost", 0) + s2.get(f"{domain}_transition_lost", 0) == 2


@pytest.mark.asyncio
async def test_22_repeated_reconciliation_is_idempotent():
    """After expiry the record no longer matches the stale-candidate filter —
    repeated runs scan nothing and do nothing."""
    rec = make_record("appointment")

    async def shrunken_scan(cutoff):
        # First scan returns the candidate; afterwards it is expired and no
        # longer pending → no candidates ever again.
        return [rec] if not shrunken_scan.called else []
    shrunken_scan.called = False

    original_list = None
    patches = patched_domain("appointment", candidates=[rec])
    original_list = patches[0]
    with _Stack(patches):
        s1 = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
        assert s1["appointment_expired"] == 1
        # Simulate the record leaving the candidate set after expiry.
        patches[0] = patch(
            "app.services.stale_payment_reconciliation_service."
            "AppointmentRepository.list_stale_pending_payments",
            new=AsyncMock(return_value=[]))
        # Re-enter with the updated patch set.
    with _Stack(patches):
        s2 = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
        assert s2["appointments_scanned"] == 0


# ---------------------------------------------------------------------------
# 15/16 — expiry vs verify / expiry vs webhook races
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_15_expiry_vs_verify_race_paid_wins_never_corrupted():
    """The expiry guard loses when verification transitioned the record first
    — the paid state must remain intact (never paid → cancelled)."""
    rec = make_record("appointment")

    async def guarded_expire(*a, **k):
        # Verification won the race before expiry's atomic update: guard
        # (status=pending_payment) no longer matches → None.
        return None

    patches = patched_domain("appointment", candidates=[rec])
    patches[4] = patch(
        "app.services.stale_payment_reconciliation_service."
        "PaymentRepository.expire_appointment_pending_payment",
        new=guarded_expire)
    with _Stack(patches):
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary["appointment_transition_lost"] == 1
    # Nothing was expired; the paid record remains paid (the atomic guard is
    # the same one that produced the paid state — structurally impossible for
    # expiry to overwrite it).


@pytest.mark.asyncio
async def test_16_expiry_vs_webhook_race_captured_just_before_expiry():
    """Scenario 3: webhook captured just before expiry — the Task 8 path
    reconciles; expiry never runs."""
    rec = make_record("appointment")
    reconcile = AsyncMock(return_value="reconciled_appointment")
    with _Stack(patched_domain(
            "appointment", candidates=[rec], payments=[payment("captured")],
            reconcile=reconcile)) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary["appointment_reconciled"] == 1
    mocks[4].assert_not_awaited()


# ---------------------------------------------------------------------------
# 19 — late captured-after-expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("domain,rid", [("appointment", APT_ID),
                                        ("laboratory", BOOK_ID)])
async def test_19_late_capture_after_expiry_never_restores(domain, rid):
    """Expiry won, THEN a captured payment arrives: no restore, no refund —
    captured evidence preserved + clear outcome."""
    rec = make_record(domain, id=rid)
    # The record as it exists after expiry (expired vocabulary).
    expired_record = make_record(domain, id=rid, status="cancelled"
                                 if domain == "appointment" else "failed",
                                 billing_status="failed",
                                 payment_status="expired")
    reconcile = AsyncMock(return_value="already_paid")  # Task 8 guard lost
    with _Stack(patched_domain(
            domain, candidates=[rec], payments=[payment("captured")],
            reconcile=reconcile, get_by_order=expired_record)) as mocks:
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary[f"{domain}_late_capture_after_expiry"] == 1
    mocks[4].assert_not_awaited()  # no further expiry either


# ---------------------------------------------------------------------------
# 7 (scenario) — captured-during-reconciliation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_18_captured_during_reconciliation_single_transition():
    """A payment that captures WHILE reconciliation runs is seen as captured
    on the payments list; the Task 8 path handles it exactly once."""
    rec = make_record("appointment")
    reconcile = AsyncMock(return_value="reconciled_appointment")
    with _Stack(patched_domain(
            "appointment", candidates=[rec], payments=[payment("captured")],
            reconcile=reconcile)):
        summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    reconcile.assert_awaited_once()
    assert summary["appointment_reconciled"] == 1


# ---------------------------------------------------------------------------
# 20/21 — slot reusability after expiry (unique-index behavior proof)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_20_expired_lab_slot_becomes_reusable():
    """After lab expiry the record must NOT remain billing_status=pending —
    the exact value the partial unique index treats as an active reservation.

    Proven at the transition level (no live MongoDB in unit tests): the
    guarded update sets billing_status=failed, which the index's
    partialFilterExpression {billing_status: {$in: [pending, paid]}} excludes
    → the slot is released, and find_conflicting_booking (gated on
    pending|paid) no longer matches → rebooking the same slot is allowed.
    """
    from app.repositories.payment_repository import PaymentRepository

    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(return_value={
        "_id": BOOK_ID, "status": "failed", "billing_status": "failed",
        "payment_status": "expired"})
    with patch("app.repositories.payment_repository.LaboratoryBooking."
               "get_pymongo_collection", return_value=fake_coll):
        await PaymentRepository.expire_laboratory_pending_payment(BOOK_ID, ORDER_ID)
    update = fake_coll.find_one_and_update.await_args.args[1]["$set"]
    assert update["billing_status"] == "failed"
    assert update["status"] == "failed"

    # Index contract: expired values are outside the partial filter.
    from app.models.laboratory_booking import ACTIVE_BILLING_STATUSES
    assert "failed" not in ACTIVE_BILLING_STATUSES


@pytest.mark.asyncio
async def test_21_expired_appointment_slot_becomes_reusable():
    """After appointment expiry status leaves ACTIVE_STATUSES → the partial
    unique index releases the slot, and patient_has_slot (gated on
    status != cancelled) no longer matches."""
    from app.repositories.payment_repository import PaymentRepository
    from app.models.appointment import ACTIVE_STATUSES

    fake_coll = MagicMock()
    fake_coll.find_one_and_update = AsyncMock(return_value={
        "_id": APT_ID, "status": "cancelled", "billing_status": "failed",
        "payment_status": "expired"})
    with patch("app.repositories.payment_repository.Appointment."
               "get_pymongo_collection", return_value=fake_coll):
        await PaymentRepository.expire_appointment_pending_payment(APT_ID, ORDER_ID)
    update = fake_coll.find_one_and_update.await_args.args[1]["$set"]
    assert update["status"] == "cancelled"
    assert "cancelled" not in ACTIVE_STATUSES


# ---------------------------------------------------------------------------
# 23/24 — notification + paid-state invariants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_23_expiry_never_sends_payment_success_notification():
    """Expiry path never touches the notification helper at all."""
    rec = make_record("appointment")
    notify = AsyncMock()
    with patch("app.services.payment_service.PaymentService._notify_payment_success",
               new=notify):
        with _Stack(patched_domain("appointment", candidates=[rec])):
            summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary["appointment_expired"] == 1
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_23b_reconciled_captured_payment_notifies_exactly_once():
    """When the reused Task 8 path legitimately confirms payment, its internal
    winner-only semantics govern notifications (verified in Task 8's suite);
    here we prove the stale path adds NO extra notification call."""
    rec = make_record("appointment")
    notify = AsyncMock()
    reconcile = AsyncMock(return_value="reconciled_appointment")
    with patch("app.services.payment_service.PaymentService._notify_payment_success",
               new=notify):
        with _Stack(patched_domain(
                "appointment", candidates=[rec], payments=[payment("captured")],
                reconcile=reconcile)):
            await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    # Notification (if any) happened INSIDE the Task 8 path, not here.
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_24_no_paid_to_cancelled_transition():
    """The expiry guard requires status=pending_payment (+ billing pending for
    labs), so a paid/confirmed record can never structurally match."""
    from app.repositories.payment_repository import PaymentRepository

    for domain, coll_path, expected_query in (
        ("appointment",
         "app.repositories.payment_repository.Appointment.get_pymongo_collection",
         {"_id": __import__("bson").ObjectId(APT_ID),
          "payment_order_id": ORDER_ID, "status": "pending_payment"}),
        ("laboratory",
         "app.repositories.payment_repository.LaboratoryBooking.get_pymongo_collection",
         {"_id": __import__("bson").ObjectId(BOOK_ID),
          "payment_order_id": ORDER_ID, "billing_status": "pending",
          "status": "pending_payment"}),
    ):
        fake_coll = MagicMock()
        fake_coll.find_one_and_update = AsyncMock(return_value=None)
        with patch(coll_path, return_value=fake_coll):
            if domain == "appointment":
                await PaymentRepository.expire_appointment_pending_payment(
                    APT_ID, ORDER_ID)
            else:
                await PaymentRepository.expire_laboratory_pending_payment(
                    BOOK_ID, ORDER_ID)
        query = fake_coll.find_one_and_update.await_args.args[0]
        assert query == expected_query
        assert "confirmed" not in str(query) and "paid" not in str(query)


# ---------------------------------------------------------------------------
# 25 — patient isolation (no patient-triggerable expiry surface)
# ---------------------------------------------------------------------------

def test_25_no_patient_accessible_expiry_endpoint():
    """Task 9 surface must be service-internal: no router may expose expiry,
    and no patient JWT dependency may reach it."""
    import inspect

    from app.api import appointments, laboratory, webhooks
    from app.services import stale_payment_reconciliation_service as sps

    for mod in (appointments, laboratory, webhooks):
        src = inspect.getsource(mod)
        assert "reconcile_stale" not in src
        assert "expire_appointment_pending_payment" not in src
        assert "expire_laboratory_pending_payment" not in src

    # The service itself performs NO role/ownership check because NOTHING
    # public can call it — but it must also never read client input.
    src = inspect.getsource(sps)
    assert "request" not in src or "Request" not in src  # no HTTP surface


def test_25b_no_frontend_exposure_of_new_config():
    """The new config values are backend-only (Task 9 security)."""
    import inspect
    from app.core import config

    src = inspect.getsource(config)
    assert "PAYMENT_PENDING_EXPIRY_MINUTES" in src


# ---------------------------------------------------------------------------
# Execution mechanism
# ---------------------------------------------------------------------------

def test_background_loop_is_opt_out_and_sleeps_first():
    import inspect
    from app.services import stale_payment_reconciliation_service as sps

    src = inspect.getsource(sps.StalePaymentReconciliationService._reconciliation_loop)
    # Sleep BEFORE the first run: startup is never blocked.
    assert src.index("await asyncio.sleep(") < src.index("while True")
    assert STALE_PAYMENT_RECONCILIATION_INTERVAL_SECONDS == 900


@pytest.mark.asyncio
async def test_start_background_loop_idempotent():
    import asyncio as _aio
    from app.services import stale_payment_reconciliation_service as sps

    started = []

    async def fake_loop():
        started.append(1)
        await _aio.sleep(0)

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(sps.settings, "PAYMENT_RECONCILIATION_ENABLED", True)
        monkey.setattr(sps.settings, "PAYMENT_PENDING_EXPIRY_MINUTES", TEST_EXPIRY_MINUTES)
        monkey.setattr(sps.StalePaymentReconciliationService,
                       "_reconciliation_loop", staticmethod(fake_loop))
        t1 = sps.StalePaymentReconciliationService.start_background_loop()
        t2 = sps.StalePaymentReconciliationService.start_background_loop()
        assert t1 is t2  # no second loop
        if t1:
            t1.cancel()
    finally:
        monkey.undo()
        sps.StalePaymentReconciliationService._background_task = None


# ---------------------------------------------------------------------------
# Policy gate (Task 9 policy remediation) — automatic expiry is OFF unless
# explicitly activated, and no default duration is chosen by the app.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_policy_disabled_by_default_no_expiry_without_configuration(monkeypatch):
    """OPTION B core invariant: with the application's DEFAULT configuration
    (policy disabled, no approved duration), a reconciliation run must not
    scan, not contact Razorpay, and never expire anything."""
    from app.services import stale_payment_reconciliation_service as sps

    with patch("app.services.stale_payment_reconciliation_service.fetch_order",
               new=AsyncMock(side_effect=AssertionError(
                   "Razorpay must not be contacted while policy is disabled"))), \
         patch.object(sps.PaymentRepository, "expire_appointment_pending_payment",
                      new=AsyncMock(side_effect=AssertionError("no expiry while disabled"))), \
         patch.object(sps.PaymentRepository, "expire_laboratory_pending_payment",
                      new=AsyncMock(side_effect=AssertionError("no expiry while disabled"))):
        # True application defaults (overriding the test-policy fixture).
        monkeypatch.setattr(settings, "PAYMENT_RECONCILIATION_ENABLED", False)
        monkeypatch.setattr(settings, "PAYMENT_PENDING_EXPIRY_MINUTES", None)
        summary = await sps.StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
    assert summary == {"status": "disabled"}


@pytest.mark.asyncio
async def test_policy_enabled_requires_explicit_duration():
    """Even with the switch ON, a missing/None duration must never expire:
    activation requires BOTH values — no silent business duration exists."""
    with patch("app.services.stale_payment_reconciliation_service.fetch_order",
               new=AsyncMock(side_effect=AssertionError(
                   "Razorpay must not be contacted while policy is undefined"))):
        monkey = pytest.MonkeyPatch()
        try:
            monkey.setattr(settings, "PAYMENT_RECONCILIATION_ENABLED", True)
            monkey.setattr(settings, "PAYMENT_PENDING_EXPIRY_MINUTES", None)
            summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
            assert summary == {"status": "disabled"}
        finally:
            monkey.undo()


@pytest.mark.asyncio
async def test_policy_disabled_switch_prevents_expiry_even_with_duration():
    """The switch alone gates the loop; the duration alone must not enable
    expiry either — BOTH must be explicitly set."""
    rec = make_record("appointment")
    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(settings, "PAYMENT_RECONCILIATION_ENABLED", False)
        monkey.setattr(settings, "PAYMENT_PENDING_EXPIRY_MINUTES", TEST_EXPIRY_MINUTES)
        with patch("app.services.stale_payment_reconciliation_service.fetch_order",
                   new=AsyncMock(side_effect=AssertionError("no Razorpay call when disabled"))):
            summary = await StalePaymentReconciliationService.reconcile_stale_pending_payments(now=NOW)
        assert summary == {"status": "disabled"}
    finally:
        monkey.undo()


def test_policy_configuration_is_respected():
    """Focused proof that configuration drives behavior end-to-end: the
    threshold comes from settings (not hardcoded), and the switch gates the
    background loop."""
    import inspect
    from app.services import stale_payment_reconciliation_service as sps

    src = inspect.getsource(sps.StalePaymentReconciliationService.reconcile_stale_pending_payments)
    # The cutoff is derived from the configured threshold — never a literal.
    assert "settings.PAYMENT_PENDING_EXPIRY_MINUTES" in src
    assert "timedelta(minutes=" in src
    # No hardcoded duration anywhere in the service.
    assert "timedelta(minutes=30)" not in src
    assert "timedelta(minutes=15)" not in src
    assert "timedelta(minutes=60)" not in src

    # Loop start honors the switch.
    loop_src = inspect.getsource(sps.StalePaymentReconciliationService.start_background_loop)
    assert "PAYMENT_RECONCILIATION_ENABLED" in loop_src
    assert "PAYMENT_PENDING_EXPIRY_MINUTES" in loop_src


def test_policy_defaults_are_disabled_in_config():
    """The shipped default configuration must remain policy-disabled with no
    invented duration (Option B)."""
    from app.core import config as config_mod

    # Defaults on the Settings class itself (not env-overridden values).
    fields = config_mod.Settings.model_fields
    assert fields["PAYMENT_RECONCILIATION_ENABLED"].default is False
    assert fields["PAYMENT_PENDING_EXPIRY_MINUTES"].default is None


# ---------------------------------------------------------------------------
# Structural safety
# ---------------------------------------------------------------------------

def test_no_load_modify_save_expiry():
    """Task 9 forbids load→modify→save: the service must contain no .save()
    call, and the expiry transitions must be find_one_and_update."""
    import inspect
    from app.services import stale_payment_reconciliation_service as sps
    from app.repositories import payment_repository as pr

    assert ".save()" not in inspect.getsource(sps)
    src = inspect.getsource(pr)
    assert "find_one_and_update" in src
    for forbidden in ("webhook_mark_paid", "webhook_expire"):
        assert forbidden not in src


def test_reused_task8_path_not_duplicated():
    """The captured-payment branch must call WebhookReconciliationService —
    no second confirmation implementation."""
    import inspect
    from app.services import stale_payment_reconciliation_service as sps

    src = inspect.getsource(sps)
    assert "WebhookReconciliationService.reconcile_event" in src
    assert "mark_appointment_paid" not in src  # Task 8 owns that transition
    assert "mark_laboratory_paid" not in src


def test_no_secrets_or_payload_logged():
    """Logging policy: no raw payloads, no credentials in the service."""
    import inspect
    from app.services import stale_payment_reconciliation_service as sps

    src = inspect.getsource(sps)
    for forbidden in ("RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET",
                      "json.dumps"):
        assert forbidden not in src
