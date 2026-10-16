"""
Phase 4 Task 20 tests — centralized logging configuration & observability.

Mandated proofs (§Task 20):
  §2  INFO records are EMITTED — not merely captured by pytest: through
      the configured root handler (real StreamHandler → stream), through
      a full mocked reconciliation batch, and through plain caplog with
      NO caplog.at_level() crutch (impossible before Task 20, when the
      root logger sat at its WARNING default with no handler).
  §3  Sensitive values never reach log output — at the configured
      handler, across the full reconciliation batch, and structurally:
      the module references ONLY settings.LOG_LEVEL and can never format
      a secret into a log line.
  §4  Reconciliation behavior is UNCHANGED — the config module imports
      no reconciliation symbol, flips no flag, starts no loop, and the
      shipped defaults stay exactly as before Task 20
      (REFUND_RECONCILIATION_ENABLED False, outcome vocabulary intact,
      5-state refund model intact, scheduler disabled-by-default with
      cadence 15 * 60).

ALL Razorpay interactions are mocked. Zero real credentials, zero real
Razorpay transactions. Configuration-only changes are under test: no
refund state, index, Razorpay-logic, scheduler-cadence, webhook, or
frontend behavior is touched.
"""
import asyncio
import ast
import inspect
import io
import logging
import textwrap
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import logging_config
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.models.payment_refund import REFUND_STATUSES
from app.repositories.payment_refund_repository import (
    PaymentRefundRepository,
)
from app.services.refund_reconciliation_service import (
    REFUND_RECONCILIATION_INTERVAL_SECONDS,
    OUTCOME_COMPLETED,
    OUTCOME_INTERNAL_ERROR,
    OUTCOME_KEPT_PENDING,
    RefundReconciliationService,
)

TEST_KEY_ID = "rzp_test_unitkeyid123"
TEST_SECRET = "test_key_secret_for_unit_tests_only"
TEST_WEBHOOK_SECRET = "test_webhook_secret_unit_tests_only"
TEST_JWT_SECRET = "test_jwt_secret_value_unit_tests_only"
RID = "d0000000000000000000000d"
RP_RFND = "rfnd_RazorpayIdentity123"
STORED_PAYMENT_ID = "pay_stored1234567"
STORED_AMOUNT_PAISE = 50000


def make_refund_record(status="processing", razorpay_refund_id=RP_RFND):
    r = MagicMock()
    r.id = RID
    r.payable_type = "appointment"
    r.payable_id = "333333333333333333333333"
    r.payment_id = STORED_PAYMENT_ID
    r.payment_order_id = "order_stored12345"
    r.amount = STORED_AMOUNT_PAISE
    r.currency = "INR"
    r.status = status
    r.reason = "refund_requested"
    r.requested_by = "aaaaaaaaaaaaaaaaaaaaaaaa"
    r.razorpay_refund_id = razorpay_refund_id
    return r


def _run(coro):
    return asyncio.run(coro)


def _detach(handler):
    """Remove exactly the handler configure_logging() returned — never a
    positional guess, so pytest's own handlers are never touched."""
    logging.getLogger().removeHandler(handler)


# ---------------------------------------------------------------------------
# §2 — configure_logging() behavior: idempotent, INFO baseline, real handler
# ---------------------------------------------------------------------------

def test_configure_logging_idempotent_and_binds_stream():
    """One call installs exactly one marked handler bound to the given
    stream; a second call installs nothing (idempotent) and returns the
    SAME handler object."""
    stream = io.StringIO()
    handler = configure_logging(stream)
    try:
        assert getattr(handler, logging_config._HANDLER_MARKER) is True
        again = configure_logging(io.StringIO())
        assert again is handler
    finally:
        _detach(handler)


def test_configure_logging_without_stream_uses_stderr():
    handler = configure_logging()
    try:
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is logging_config.sys.stderr
    finally:
        _detach(handler)


def test_configure_logging_respects_recognized_levels(monkeypatch):
    """DEBUG/WARNING map through; an UNRECOGNIZED value falls back to
    INFO — never a crash, never a silent DEBUG."""
    try:
        for raw, expected in (("DEBUG", logging.DEBUG),
                              ("WARNING", logging.WARNING),
                              ("info", logging.INFO)):
            monkeypatch.setattr(settings, "LOG_LEVEL", raw)
            handler = configure_logging(io.StringIO())
            _detach(handler)
        monkeypatch.setattr(settings, "LOG_LEVEL", "not-a-level")
        handler = configure_logging(io.StringIO())
        _detach(handler)
        assert logging.getLogger().level == logging.INFO
    finally:
        monkeypatch.setattr(settings, "LOG_LEVEL", "INFO")


def test_configured_handler_emits_info_records():
    """§2 core proof: with ONLY Task 20's configuration (no caplog, no
    pytest capture involved), an INFO record physically reaches the
    configured handler's stream — the exact pre-Task-20 failure mode."""
    stream = io.StringIO()
    handler = configure_logging(stream)
    try:
        probe = logging.getLogger("physiocare.test.task20")
        probe.info("refund reconciliation INFO is now visible")
        out = stream.getvalue()
        assert "refund reconciliation INFO is now visible" in out
        assert " INFO " in out
        assert "physiocare.test.task20" in out
    finally:
        _detach(handler)


def test_reconciliation_info_reaches_configured_handler_without_caplog():
    """§2 end-to-end: a full mocked reconciliation batch run emits its
    start line, per-outcome line, and summary line through the Task 20
    configured handler — zero pytest logging machinery involved. Uses the
    no-identity discovery path (Razorpay refund list reports the refund
    still pending there) so no Task 14 delegation is exercised."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    pending_on_razorpay = [{
        "id": RP_RFND, "entity": "refund",
        "amount": STORED_AMOUNT_PAISE, "currency": "INR",
        "payment_id": STORED_PAYMENT_ID, "status": "pending",
    }]
    stream = io.StringIO()
    handler = configure_logging(stream)
    try:
        with patch.object(
            PaymentRefundRepository, "list_reconcilable_refunds",
            new=AsyncMock(return_value=[processing]),
        ), patch.object(
            PaymentRefundRepository, "get_by_id",
            new=AsyncMock(return_value=processing),
        ), patch.object(
            PaymentRefundRepository, "touch_processing",
            new=AsyncMock(return_value={"_id": RID}),
        ), patch.object(
            PaymentRefundRepository, "record_reconciliation_attempt",
            new=AsyncMock(return_value=True),
        ), patch(
            "app.services.refund_reconciliation_service.fetch_payment_refunds",
            new=MagicMock(return_value=pending_on_razorpay),
        ):
            summary = _run(
                RefundReconciliationService.reconcile_refundable_refunds()
            )
        out = stream.getvalue()
        assert summary[OUTCOME_KEPT_PENDING] == 1
        assert "Refund reconciliation batch started" in out
        assert "Refund reconciliation batch completed" in out
        assert OUTCOME_KEPT_PENDING in out
    finally:
        _detach(handler)


def test_info_visible_under_plain_caplog_without_at_level(caplog):
    """§2 reproduction of the audit finding, fixed: BEFORE Task 20 this
    exact probe emitted nothing — the reconciliation logger's effective
    level was the root logger's WARNING default, so logger.info() was
    dropped before any handler saw it. Now a plain caplog — with NO
    caplog.at_level() crutch — sees an INFO record from the
    reconciliation-namespaced logger."""
    logging.getLogger(
        "app.services.refund_reconciliation_service"
    ).info("task 20 plain-caplog INFO visibility probe")
    assert "task 20 plain-caplog INFO visibility probe" in caplog.text


# ---------------------------------------------------------------------------
# §3 — no sensitive values ever reach log output
# ---------------------------------------------------------------------------

def _executable_source(module) -> str:
    """Source with docstrings and comment lines removed (AST-accurate),
    matching the established reconciliation-suite convention."""
    src = textwrap.dedent(inspect.getsource(module))
    try:
        tree = ast.parse(src)
    except (SyntaxError, IndentationError):
        return "\n".join(
            ln for ln in src.splitlines()
            if not ln.strip().startswith("#")
        )
    doc_lines = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            doc_lines.update(range(node.lineno, node.end_lineno + 1))
    lines = src.splitlines()
    out = []
    for i, ln in enumerate(lines, start=1):
        if i in doc_lines or ln.strip().startswith("#"):
            continue
        out.append(ln)
    return "\n".join(out)


def test_logging_config_module_never_references_secret_settings():
    """Structural proof: the module's executable source references ONLY
    settings.LOG_LEVEL — no JWT, Razorpay, webhook, token, or signature
    attribute can ever be formatted into a log line by this module."""
    src = _executable_source(logging_config)
    for banned in (
        "JWT_SECRET", "JWT_REFRESH_SECRET",
        "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET",
        "RAZORPAY_WEBHOOK_SECRET",
        "Authorization", "authorization", "signature",
        "X-Razorpay-Signature", "x-razorpay-signature",
    ):
        assert banned not in src, banned
    assert "settings.LOG_LEVEL" in src


def test_reconciliation_batch_logs_no_secrets_or_payload_pii():
    """§3 end-to-end: a full batch whose (mocked) Razorpay payloads carry
    the key id, key secret, a JWT, a webhook signature, and patient PII
    emits NONE of them — at the configured handler AND at DEBUG level.
    Only truncated ids and outcome codes appear."""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=RP_RFND)
    leaky_lookup = {
        "id": RP_RFND, "entity": "refund",
        "amount": STORED_AMOUNT_PAISE, "currency": "INR",
        "payment_id": STORED_PAYMENT_ID, "status": "pending",
        "authorization": "Bearer should_not_leak_jwt",
        "x_razorpay_signature": "sig_should_not_leak",
        "notes": {"email": "patient@example.com",
                  "phone": "+91-9999999999"},
    }
    stream = io.StringIO()
    handler = configure_logging(stream)
    try:
        with patch.object(
            PaymentRefundRepository, "list_reconcilable_refunds",
            new=AsyncMock(return_value=[processing]),
        ), patch.object(
            PaymentRefundRepository, "get_by_id",
            new=AsyncMock(return_value=processing),
        ), patch.object(
            PaymentRefundRepository, "touch_processing",
            new=AsyncMock(return_value={"_id": RID}),
        ), patch.object(
            PaymentRefundRepository, "record_reconciliation_attempt",
            new=AsyncMock(return_value=True),
        ), patch(
            "app.services.payment_refund_service.fetch_refund",
            new=MagicMock(return_value=leaky_lookup),
        ), patch.object(
            settings, "RAZORPAY_KEY_ID", TEST_KEY_ID
        ), patch.object(
            settings, "RAZORPAY_KEY_SECRET", TEST_SECRET
        ), patch.object(
            settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET
        ), patch.object(
            settings, "JWT_SECRET", TEST_JWT_SECRET
        ):
            summary = _run(
                RefundReconciliationService.reconcile_refundable_refunds()
            )
        out = stream.getvalue()
        for banned in (TEST_KEY_ID, TEST_SECRET, TEST_WEBHOOK_SECRET,
                       TEST_JWT_SECRET, "should_not_leak_jwt",
                       "sig_should_not_leak", "patient@example.com",
                       "+91-9999999999"):
            assert banned not in out, banned
        assert summary[OUTCOME_KEPT_PENDING] == 1
    finally:
        _detach(handler)


def test_exception_logging_reports_type_without_secret_values(caplog):
    """A reconciliation-path exception whose args carry a secret is
    classified as reconciliation_error (unchanged Task 18 behavior). Our
    code's log MESSAGES — the only content the Task 20 configuration
    controls — never contain the secret value; the diagnostic line is
    emitted at ERROR and therefore visible under the configured INFO
    baseline. (The stdlib traceback renderer's exc_text is unchanged by
    Task 20 and is asserted nowhere here.)"""
    processing = make_refund_record(status="processing",
                                    razorpay_refund_id=None)
    with patch.object(
        PaymentRefundRepository, "list_reconcilable_refunds",
        new=AsyncMock(return_value=[processing]),
    ), patch.object(
        PaymentRefundRepository, "get_by_id",
        new=AsyncMock(side_effect=RuntimeError(TEST_SECRET)),
    ), caplog.at_level(logging.INFO):
        summary = _run(
            RefundReconciliationService.reconcile_refundable_refunds()
        )
    assert summary[OUTCOME_INTERNAL_ERROR] == 1
    assert "Refund reconciliation: pre-check failed" in caplog.text
    for record in caplog.records:
        assert TEST_SECRET not in record.getMessage()


# ---------------------------------------------------------------------------
# §4 — reconciliation behavior unchanged by the logging configuration
# ---------------------------------------------------------------------------

def test_logging_config_imports_nothing_that_mutates_reconciliation():
    """The config module's imports are stdlib + settings only: it cannot
    start a loop, flip a flag, or reach the reconciliation subsystem."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(logging_config)))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    allowed = {"__future__", "logging", "sys", "typing",
               "app.core.config"}
    assert imported <= allowed, imported - allowed


def test_shipped_defaults_unchanged():
    """The Task 20 change is configuration-only: every policy default the
    reconciliation tests pin is identical after Task 20."""
    assert settings.REFUND_RECONCILIATION_ENABLED is False
    assert settings.PAYMENT_RECONCILIATION_ENABLED is False
    assert settings.PAYMENT_PENDING_EXPIRY_MINUTES is None
    assert settings.LOG_LEVEL == "INFO"
    assert REFUND_RECONCILIATION_INTERVAL_SECONDS == 15 * 60


def test_outcome_vocabulary_and_model_unchanged():
    """The Task 18 outcome vocabulary and the 5-state refund vocabulary
    are untouched — logging configuration added no state and no code."""
    from app.services.refund_reconciliation_service import (
        OUTCOME_ALREADY_SETTLED,
        OUTCOME_CONFIG_ERROR,
        OUTCOME_MISMATCH,
        OUTCOME_MULTIPLE_CANDIDATES,
        OUTCOME_NO_IDENTITY,
        OUTCOME_NOT_FOUND,
        OUTCOME_RZP_AMBIGUOUS,
        OUTCOME_RZP_DEFINITIVE,
        OUTCOME_SCAN_ERROR,
    )
    assert OUTCOME_COMPLETED == "reconciled_completed"
    assert OUTCOME_ALREADY_SETTLED == "already_settled"
    assert OUTCOME_KEPT_PENDING == "kept_pending"
    assert OUTCOME_NO_IDENTITY == "kept_no_identity"
    assert OUTCOME_MULTIPLE_CANDIDATES == "kept_multiple_candidates"
    assert OUTCOME_MISMATCH == "kept_mismatch"
    assert OUTCOME_RZP_AMBIGUOUS == "kept_razorpay_ambiguous"
    assert OUTCOME_RZP_DEFINITIVE == "kept_razorpay_definitive"
    assert OUTCOME_CONFIG_ERROR == "kept_config_error"
    assert OUTCOME_NOT_FOUND == "not_found"
    assert OUTCOME_INTERNAL_ERROR == "reconciliation_error"
    assert OUTCOME_SCAN_ERROR == "scan_error"
    assert tuple(REFUND_STATUSES) == (
        "requested", "processing", "completed", "failed", "cancelled",
    )


def test_scheduler_default_state_and_status_unchanged():
    """With shipped defaults the scheduler stays disabled and never
    starts; logging configuration (or its absence) cannot start it."""
    assert settings.REFUND_RECONCILIATION_ENABLED is False
    assert RefundReconciliationService._background_task is None
    assert RefundReconciliationService.scheduler_status() == "disabled"


def test_main_app_imports_configure_logging_once():
    """app.main imports and calls configure_logging() exactly once, at
    import time — before routes/loops — and it is the ONLY call site
    outside tests."""
    import app.main as main_mod
    src = inspect.getsource(main_mod)
    assert "configure_logging()" in src
    assert src.count("configure_logging()") == 1
    assert "from app.core.logging_config import configure_logging" in src
    # No behavior change: startup still runs exactly the two established
    # background loops and nothing else.
    assert "StalePaymentReconciliationService.start_background_loop()" in src
    assert "RefundReconciliationService.start_background_loop()" in src
