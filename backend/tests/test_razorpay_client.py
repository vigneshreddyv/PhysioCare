"""
Task 1 tests — Razorpay backend foundation.

All Razorpay network/SDK calls are mocked at the integration boundary.
No real network calls, no real payments, no real credentials are used.
"""

import hashlib
import hmac
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.core import razorpay_client
from app.core.config import settings
from app.core.razorpay_client import (
    RazorpayConfigError,
    RazorpayRequestError,
    RazorpaySignatureError,
    create_order,
    get_razorpay_client,
    rupees_to_paise,
    verify_payment_signature,
)

# Deterministic test-only secret. NOT a real credential.
TEST_SECRET = "test_key_secret_for_unit_tests_only"


@pytest.fixture(autouse=True)
def razorpay_test_config(monkeypatch):
    """Deterministic test credentials for every test in this module."""
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_unitkeyid123")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", TEST_SECRET)
    monkeypatch.setattr(settings, "RAZORPAY_TIMEOUT_SECONDS", 30)


def _expected_signature(order_id: str, payment_id: str, secret: str = TEST_SECRET) -> str:
    message = f"{order_id}|{payment_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# MONEY CONVERSION — TEST 1 & TEST 2
# ---------------------------------------------------------------------------

def test_rupees_500_converts_to_50000_paise():
    # TEST 1: Rs.500.00 -> 50000
    assert rupees_to_paise(Decimal("500.00")) == 50000
    # String input (as stored in many DB/API payloads) converts identically.
    assert rupees_to_paise("500.00") == 50000


def test_rupees_950_converts_to_95000_paise():
    # TEST 2: Rs.950.00 -> 95000
    assert rupees_to_paise(Decimal("950.00")) == 95000
    assert rupees_to_paise("950.00") == 95000


def test_float_input_never_goes_through_int_multiplication():
    # Exact 2-dp float input is fine.
    assert rupees_to_paise(500.0) == 50000
    # Floats with >2 dp are rejected instead of being silently rounded
    # (int(2.675 * 100) == 267 with binary floats — the exact trap to avoid).
    with pytest.raises(RazorpayRequestError):
        rupees_to_paise(2.675)


def test_amount_with_more_than_two_decimals_is_rejected():
    with pytest.raises(RazorpayRequestError):
        rupees_to_paise(Decimal("500.001"))


def test_negative_and_non_numeric_amounts_are_rejected():
    with pytest.raises(RazorpayRequestError):
        rupees_to_paise(Decimal("-1.00"))
    with pytest.raises(RazorpayRequestError):
        rupees_to_paise("abc")
    with pytest.raises(RazorpayRequestError):
        rupees_to_paise(None)


# ---------------------------------------------------------------------------
# SIGNATURE VERIFICATION — TEST 3, 4, 5, 6, 7
# ---------------------------------------------------------------------------

def test_signature_verification_succeeds_for_valid_signature():
    # TEST 3
    sig = _expected_signature("order_test123", "pay_test456")
    assert verify_payment_signature("order_test123", "pay_test456", sig) is True


def test_signature_verification_fails_for_modified_payment_id():
    # TEST 4
    sig = _expected_signature("order_test123", "pay_test456")
    assert verify_payment_signature("order_test123", "pay_test999", sig) is False


def test_signature_verification_fails_for_modified_order_id():
    # TEST 5
    sig = _expected_signature("order_test123", "pay_test456")
    assert verify_payment_signature("order_test999", "pay_test456", sig) is False


def test_signature_verification_fails_for_invalid_signature():
    # TEST 6
    assert verify_payment_signature("order_test123", "pay_test456", "deadbeef") is False
    # Wrong-key signature must also fail.
    other = _expected_signature("order_test123", "pay_test456", secret="another-secret")
    assert verify_payment_signature("order_test123", "pay_test456", other) is False


def test_signature_comparison_uses_constant_time_compare():
    # TEST 7: hmac.compare_digest must be used instead of ordinary ==.
    calls = {"count": 0}
    real_compare_digest = hmac.compare_digest

    def spy(a, b):
        calls["count"] += 1
        return real_compare_digest(a, b)

    sig = _expected_signature("order_test123", "pay_test456")
    with patch.object(razorpay_client.hmac, "compare_digest", side_effect=spy):
        result = verify_payment_signature("order_test123", "pay_test456", sig)

    assert calls["count"] == 1
    assert result is True


def test_signature_verification_rejects_missing_inputs():
    with pytest.raises(RazorpaySignatureError):
        verify_payment_signature("", "pay_test456", "sig")
    with pytest.raises(RazorpaySignatureError):
        verify_payment_signature("order_test123", "", "sig")
    with pytest.raises(RazorpaySignatureError):
        verify_payment_signature("order_test123", "pay_test456", "")


def test_signature_error_and_logs_never_contain_secret():
    # The raised errors must never carry the secret.
    try:
        verify_payment_signature("", "", "")
    except RazorpaySignatureError as exc:
        assert TEST_SECRET not in str(exc)


# ---------------------------------------------------------------------------
# ORDER CREATION — TEST 8
# ---------------------------------------------------------------------------

def test_create_order_builds_correct_razorpay_request():
    # TEST 8: correct amount (paise), currency, receipt, notes; no credentials.
    captured = {}

    fake_client = MagicMock()

    def fake_create(data=None, **kwargs):
        captured["data"] = data
        captured["kwargs"] = kwargs
        return {
            "id": "order_fake123",
            "amount": data["amount"],
            "currency": data["currency"],
            "receipt": data["receipt"],
        }

    fake_client.order.create.side_effect = fake_create

    with patch.object(razorpay_client, "get_razorpay_client", return_value=fake_client):
        order = create_order(
            50000, "INR", "appt_42_1759000000", {"appointment_id": "42"}
        )

    assert order["id"] == "order_fake123"
    assert captured["data"] == {
        "amount": 50000,
        "currency": "INR",
        "receipt": "appt_42_1759000000",
        "notes": {"appointment_id": "42"},
    }
    # Explicit timeout forwarded to the SDK/HTTP layer.
    assert captured["kwargs"].get("timeout") == 30
    # Credentials never appear in the API payload.
    payload_str = str(captured)
    assert TEST_SECRET not in payload_str
    assert "rzp_test_unitkeyid123" not in payload_str


def test_create_order_without_notes_omits_notes_key():
    captured = {}
    fake_client = MagicMock()
    fake_client.order.create.side_effect = lambda data=None, **kw: (
        captured.update(data=data) or {"id": "order_fake123"}
    )

    with patch.object(razorpay_client, "get_razorpay_client", return_value=fake_client):
        create_order(95000, "INR", "lab_7_1759000000", None)

    assert "notes" not in captured["data"]


# ---------------------------------------------------------------------------
# CONFIGURATION / ERROR HANDLING
# ---------------------------------------------------------------------------

def test_missing_configuration_raises_safe_config_error(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "")
    with pytest.raises(RazorpayConfigError) as excinfo:
        get_razorpay_client()
    msg = str(excinfo.value)
    assert TEST_SECRET not in msg


def test_missing_secret_on_signature_verification_raises_config_error(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "")
    with pytest.raises(RazorpayConfigError):
        verify_payment_signature("order_1", "pay_1", "sig")


def test_razorpay_api_failure_is_wrapped_in_safe_error():
    from razorpay.errors import BadRequestError

    fake_client = MagicMock()
    fake_client.order.create.side_effect = BadRequestError("Payment processing failed")

    with patch.object(razorpay_client, "get_razorpay_client", return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as excinfo:
            create_order(50000, "INR", "r", None)
    # API-provided description is safe to surface.
    assert "Payment processing failed" in str(excinfo.value)
    assert TEST_SECRET not in str(excinfo.value)


def test_network_and_timeout_errors_become_generic_safe_errors():
    import requests

    fake_client = MagicMock()
    fake_client.order.create.side_effect = requests.exceptions.Timeout("timed out")

    with patch.object(razorpay_client, "get_razorpay_client", return_value=fake_client):
        with pytest.raises(RazorpayRequestError) as excinfo:
            create_order(50000, "INR", "r", None)
    msg = str(excinfo.value)
    assert "network or timeout" in msg
    # Nothing credential-bearing leaks through the wrapped error.
    assert TEST_SECRET not in msg
    assert "rzp_test_unitkeyid123" not in msg


def test_malformed_razorpay_response_raises_safe_error():
    fake_client = MagicMock()
    fake_client.order.create.return_value = {"unexpected": "shape"}

    with patch.object(razorpay_client, "get_razorpay_client", return_value=fake_client):
        with pytest.raises(RazorpayRequestError):
            create_order(50000, "INR", "r", None)

    fake_client = MagicMock()
    fake_client.order.create.return_value = None
    with patch.object(razorpay_client, "get_razorpay_client", return_value=fake_client):
        with pytest.raises(RazorpayRequestError):
            create_order(50000, "INR", "r", None)


def test_invalid_order_params_rejected_before_any_network_call():
    fake_client = MagicMock()
    fake_client.order.create.side_effect = AssertionError("network call must not happen")

    with patch.object(razorpay_client, "get_razorpay_client", return_value=fake_client):
        with pytest.raises(RazorpayRequestError):
            create_order(0, "INR", "r", None)                    # zero amount
        with pytest.raises(RazorpayRequestError):
            create_order(-5, "INR", "r", None)                   # negative
        with pytest.raises(RazorpayRequestError):
            create_order(50000, "USD", "r", None)                # unsupported currency
        with pytest.raises(RazorpayRequestError):
            create_order(50000, "", "r", None)                   # missing currency
        with pytest.raises(RazorpayRequestError):
            create_order(50000, "INR", "r" * 41, None)           # receipt too long
        with pytest.raises(RazorpayRequestError):
            create_order(50000, "INR", "r", {f"k{i}": "v" for i in range(16)})  # >15 notes
