"""
Razorpay backend infrastructure helpers (Phase 4, Task 1).

This module is a GENERIC Razorpay integration layer. It deliberately knows
nothing about Appointments, LaboratoryBookings, Patients, or any database
model — that mapping belongs to a later task's payment services.

Security invariants (must hold for every change to this file):
- RAZORPAY_KEY_SECRET is backend-only. It is never logged, never returned,
  and never included in exception messages.
- Errors raised from here are application-defined types carrying only safe,
  non-credential information.

No HTTP routes, webhooks, or checkout logic live here (later tasks).
"""

from __future__ import annotations

import hmac
import hashlib
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from razorpay import Client
from razorpay.errors import (
    BadRequestError,
    GatewayError,
    ServerError,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# Razorpay Orders API constraints (https://razorpay.com/docs/api/orders/)
MAX_AMOUNT_PAISE = 10_00_00_000  # 1 crore rupees in paise
MAX_NOTES_COUNT = 15             # max notes entries per order
MAX_NOTES_VALUE_CHARS = 256      # max length of a notes value
MAX_RECEIPT_LENGTH = 40          # max length of the receipt field

# Canonical currency for PhysioCare bookings (INR only for now).
SUPPORTED_CURRENCIES = ("INR",)


class RazorpayRefundOutcome:
    """Refund-attempt outcome classification for Task 13 execution.

    Prefixed into RazorpayRequestError messages by the refund client
    helpers so callers can distinguish WITHOUT stringly-typed guessing:

    - DEFINITIVE: Razorpay itself rejected the refund (4xx-class). No
      money moved; a retry of the same request cannot succeed. Safe to
      mark the refund `failed`.
    - AMBIGUOUS: network/timeout/5xx/malformed response. Razorpay MAY
      have accepted the refund. NEVER safe to mark `failed` or
      `completed` from this alone — the refund stays `processing` for
      reconciliation.
    """

    DEFINITIVE = "DEFINITIVE_REJECTION"
    AMBIGUOUS = "AMBIGUOUS_OUTCOME"


class RazorpayConfigError(Exception):
    """Raised when Razorpay configuration is missing or invalid.

    Message is safe for operator display and contains no credentials.
    """


class RazorpayRequestError(Exception):
    """Raised when the Razorpay API call fails (network, timeout, API error,
    or malformed response).

    The original SDK/network exception is intentionally NOT chained
    (`from None`) so no credential-bearing context can leak through
    tracebacks. Carries a safe, human-readable message only.
    """


class RazorpaySignatureError(Exception):
    """Raised when payment signature verification fails.

    Deliberately does not include the signature, the secret, or any
    credential material — only which check failed.
    """


def _mask(key: str) -> str:
    """Return a short, non-reversible key fingerprint safe for logs.

    Never return enough characters to reconstruct the key.
    """
    if not key:
        return "<empty>"
    return f"***{key[-4:]}"


def get_razorpay_client() -> Client:
    """Build and return an authenticated Razorpay SDK client.

    Validates configuration first so misconfiguration is detected at the
    boundary rather than mid-request. Raises RazorpayConfigError (safe)
    when the key id/secret are missing.

    Raises:
        RazorpayConfigError: if key id or key secret is not configured.
    """
    key_id = (settings.RAZORPAY_KEY_ID or "").strip()
    key_secret = (settings.RAZORPAY_KEY_SECRET or "").strip()

    if not key_id or not key_secret:
        raise RazorpayConfigError(
            "Razorpay configuration is missing: RAZORPAY_KEY_ID and/or "
            "RAZORPAY_KEY_SECRET are not set. "
            f"(key id: {_mask(key_id)})"
        )

    return Client(auth=(key_id, key_secret))


def rupees_to_paise(amount: Any) -> int:
    """Convert an authoritative backend rupee amount to integer paise.

    Rounding policy (documented, deterministic):
    - Inputs are first normalized to Decimal via str() (never binary float
      arithmetic).
    - Values with more than 2 decimal places are REJECTED regardless of input
      type. This includes float artifacts like 2.675: silently rounding a
      mis-scaled amount could charge the wrong price, so callers must pass
      exact money, e.g. Decimal("500.00"), "500.00", or 500.0.
    - A value with <=2 dp is converted exactly, e.g.
        Decimal("500.00") -> 50000
        Decimal("950.00") -> 95000
      ROUND_HALF_UP is used only for values like 1.005 that need quantizing
      (kept for completeness; 2-dp inputs are exact and unaffected).

    This helper performs no database or booking lookups — the caller passes
    an already-authoritative backend amount.

    Raises:
        RazorpayRequestError: on invalid (non-numeric, negative, or
            mis-scaled) amounts.
    """
    if isinstance(amount, bool) or amount is None:
        raise RazorpayRequestError("Invalid amount: must be a numeric rupee value.")

    try:
        d = Decimal(str(amount))
    except Exception:
        raise RazorpayRequestError("Invalid amount: must be a numeric rupee value.")

    if not d.is_finite():
        raise RazorpayRequestError("Invalid amount: must be finite.")

    if d < 0:
        raise RazorpayRequestError("Invalid amount: must be non-negative.")

    if -d.as_tuple().exponent > 2:
        raise RazorpayRequestError(
            "Invalid amount: more than 2 decimal places are not allowed."
        )

    paise = int(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)
    return paise


def validate_order_params(
    amount_paise: int,
    currency: str,
    receipt: str,
    notes: Mapping[str, Any] | None,
) -> None:
    """Validate order parameters against Razorpay Orders API constraints.

    Raises:
        RazorpayRequestError: with a safe message on the first violated
            constraint.
    """
    if not isinstance(amount_paise, int) or isinstance(amount_paise, bool):
        raise RazorpayRequestError("Invalid order amount: must be integer paise.")
    if amount_paise < 1:
        raise RazorpayRequestError("Invalid order amount: must be at least 1 paise.")
    if amount_paise > MAX_AMOUNT_PAISE:
        raise RazorpayRequestError(
            f"Invalid order amount: exceeds maximum of {MAX_AMOUNT_PAISE} paise."
        )

    if not currency or not isinstance(currency, str):
        raise RazorpayRequestError("Invalid order currency: currency is required.")
    if currency not in SUPPORTED_CURRENCIES:
        raise RazorpayRequestError(
            f"Invalid order currency: {currency} is not supported."
            f" Supported: {', '.join(SUPPORTED_CURRENCIES)}."
        )

    if not receipt or not isinstance(receipt, str):
        raise RazorpayRequestError("Invalid order receipt: receipt is required.")
    if len(receipt) > MAX_RECEIPT_LENGTH:
        raise RazorpayRequestError(
            f"Invalid order receipt: exceeds {MAX_RECEIPT_LENGTH} characters."
        )
    if "\n" in receipt or "\r" in receipt:
        raise RazorpayRequestError("Invalid order receipt: newline characters are not allowed.")

    if notes is None:
        return
    if not isinstance(notes, Mapping):
        raise RazorpayRequestError("Invalid order notes: must be a mapping of strings.")
    if len(notes) > MAX_NOTES_COUNT:
        raise RazorpayRequestError(
            f"Invalid order notes: exceeds {MAX_NOTES_COUNT} entries."
        )
    for k, v in notes.items():
        if not isinstance(k, str) or not k.strip():
            raise RazorpayRequestError("Invalid order notes: keys must be non-empty strings.")
        if not isinstance(v, str):
            raise RazorpayRequestError("Invalid order notes: values must be strings.")
        if len(k) > MAX_NOTES_VALUE_CHARS or len(v) > MAX_NOTES_VALUE_CHARS:
            raise RazorpayRequestError(
                f"Invalid order notes: keys/values must be at most "
                f"{MAX_NOTES_VALUE_CHARS} characters."
            )


def create_order(
    amount_paise: int,
    currency: str,
    receipt: str,
    notes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a Razorpay order via the official Orders API.

    Generic infrastructure helper: knows nothing about bookings, patients,
    or database models. Callers supply an authoritative backend amount
    (already in paise) — this function never accepts or derives an amount
    from client input.

    Args:
        amount_paise: Integer paise (use rupees_to_paise() to convert).
        currency: ISO currency code, e.g. "INR".
        receipt: Merchant-side receipt id (<= 40 chars).
        notes: Optional mapping of string->string metadata (<= 15 entries).

    Returns:
        The Razorpay order dict as returned by the Orders API, e.g.:
            {"id": "order_...", "amount": 50000, "currency": "INR", ...}

    Raises:
        RazorpayConfigError: missing/invalid Razorpay configuration.
        RazorpayRequestError: invalid parameters, API failure, timeout, or
            malformed response. Never carries credential material.
    """
    validate_order_params(amount_paise, currency, receipt, notes)

    client = get_razorpay_client()

    payload: dict[str, Any] = {
        "amount": int(amount_paise),
        "currency": currency,
        "receipt": receipt,
    }
    if notes:
        payload["notes"] = {str(k): str(v) for k, v in notes.items()}

    try:
        order = client.order.create(
            data=payload,
            # Explicit timeout forwarded through the SDK to requests.Session.post.
            timeout=settings.RAZORPAY_TIMEOUT_SECONDS,
        )
    except RazorpayConfigError:
        raise
    except BadRequestError as exc:
        # SDK errors carry API 'description' strings, not credentials.
        raise RazorpayRequestError(f"Razorpay rejected the order request: {exc}") from None
    except (GatewayError, ServerError) as exc:
        raise RazorpayRequestError(
            f"Razorpay API error while creating order: {exc}"
        ) from None
    except Exception:
        # Network, timeout, and any unexpected SDK failure: log server-side
        # WITHOUT the secret, and raise a safe, generic application error.
        logger.exception(
            "Razorpay order creation failed (receipt=%s, currency=%s, "
            "key=%s, timeout=%ss)",
            receipt,
            currency,
            _mask(settings.RAZORPAY_KEY_ID),
            settings.RAZORPAY_TIMEOUT_SECONDS,
        )
        raise RazorpayRequestError(
            "Razorpay order creation failed due to a network or timeout error."
        ) from None

    if not isinstance(order, dict) or not order.get("id"):
        raise RazorpayRequestError(
            "Razorpay returned a malformed response while creating the order."
        )

    return order


def fetch_payment(payment_id: str) -> dict[str, Any]:
    """Fetch a payment's authoritative details from the Razorpay Payments API.

    Used by the verification phase to confirm — from Razorpay itself, not
    from the frontend — that a payment exists, belongs to the expected order,
    was captured for the expected amount/currency, and is in a captured
    state. This module stays the ONLY place that talks to Razorpay.

    Args:
        payment_id: Razorpay payment id (pay_...).

    Returns:
        The Razorpay payment dict, e.g.:
            {"id": "pay_...", "order_id": "order_...", "amount": 50000,
             "currency": "INR", "status": "captured", ...}

    Raises:
        RazorpayConfigError: missing/invalid Razorpay configuration.
        RazorpayRequestError: invalid input, API failure, timeout, or
            malformed response. Never carries credential material.
    """
    pid = (payment_id or "").strip()
    if not pid:
        raise RazorpayRequestError("Invalid payment reference: payment id is required.")

    client = get_razorpay_client()

    try:
        payment = client.payment.fetch(
            pid,
            # Explicit timeout forwarded through the SDK to requests.
            timeout=settings.RAZORPAY_TIMEOUT_SECONDS,
        )
    except RazorpayConfigError:
        raise
    except BadRequestError as exc:
        # Unknown payment id or rejected lookup: API description is safe.
        raise RazorpayRequestError(f"Razorpay rejected the payment lookup: {exc}") from None
    except (GatewayError, ServerError) as exc:
        raise RazorpayRequestError(
            f"Razorpay API error while fetching the payment: {exc}"
        ) from None
    except Exception:
        # Network/timeout/unexpected SDK failure: log WITHOUT credentials.
        logger.exception(
            "Razorpay payment lookup failed (payment=%s, key=%s)",
            pid[:8],
            _mask(settings.RAZORPAY_KEY_ID),
        )
        raise RazorpayRequestError(
            "Razorpay payment lookup failed due to a network or timeout error."
        ) from None

    if not isinstance(payment, dict) or not payment.get("id"):
        raise RazorpayRequestError(
            "Razorpay returned a malformed response while fetching the payment."
        )

    return payment


def fetch_order(order_id: str) -> dict[str, Any]:
    """Fetch an order's authoritative details from the Razorpay Orders API
    (Phase 4, Task 9 — stale-payment reconciliation).

    Used ONLY by stale-payment reconciliation to determine, from Razorpay
    itself, whether a stored order is still legitimately open ("created" =
    attemptable) or has moved past the point where a fresh payment attempt
    is possible ("attempted" = at least one payment was made against it).
    It is NEVER used to decide payment success — captured-amount truth comes
    exclusively from fetch_payment() per payment.

    Args:
        order_id: Razorpay order id (order_...).

    Returns:
        The Razorpay order dict, e.g.:
            {"id": "order_...", "status": "created"|"attempted", "amount":
             50000, "currency": "INR", ...}

    Raises:
        RazorpayConfigError: missing/invalid Razorpay configuration.
        RazorpayRequestError: invalid input, API failure, timeout, or
            malformed response. Never carries credential material.
    """
    oid = (order_id or "").strip()
    if not oid:
        raise RazorpayRequestError("Invalid order reference: order id is required.")

    client = get_razorpay_client()

    try:
        order = client.order.fetch(
            oid,
            # Explicit timeout forwarded through the SDK to requests.
            timeout=settings.RAZORPAY_TIMEOUT_SECONDS,
        )
    except RazorpayConfigError:
        raise
    except BadRequestError as exc:
        raise RazorpayRequestError(f"Razorpay rejected the order lookup: {exc}") from None
    except (GatewayError, ServerError) as exc:
        raise RazorpayRequestError(
            f"Razorpay API error while fetching the order: {exc}"
        ) from None
    except Exception:
        # Network/timeout/unexpected SDK failure: log WITHOUT credentials.
        logger.exception(
            "Razorpay order lookup failed (order=%s, key=%s)",
            oid[:8],
            _mask(settings.RAZORPAY_KEY_ID),
        )
        raise RazorpayRequestError(
            "Razorpay order lookup failed due to a network or timeout error."
        ) from None

    if not isinstance(order, dict) or not order.get("id"):
        raise RazorpayRequestError(
            "Razorpay returned a malformed response while fetching the order."
        )

    return order


def fetch_order_payments(order_id: str) -> list[dict[str, Any]]:
    """Fetch all payments associated with a Razorpay order.

    Razorpay Orders API: GET /orders/{order_id}/payments returns the full
    payment history for the order. Stale-payment reconciliation uses this to
    answer exactly one question: does ANY payment on this order have
    status == "captured"? Individual captured payments are then re-validated
    through fetch_payment() (the single authoritative payment fetch) before
    any confirmation, so no financial decision is ever based on this list
    alone.

    Args:
        order_id: Razorpay order id (order_...).

    Returns:
        List of Razorpay payment dicts (possibly empty — a valid state
        meaning no payment attempt was ever completed on the order).

    Raises:
        RazorpayConfigError / RazorpayRequestError: same safe-error contract
            as every other function in this module.
    """
    oid = (order_id or "").strip()
    if not oid:
        raise RazorpayRequestError("Invalid order reference: order id is required.")

    client = get_razorpay_client()

    try:
        payments = client.order.payments(
            oid,
            # Explicit timeout forwarded through the SDK to requests.
            timeout=settings.RAZORPAY_TIMEOUT_SECONDS,
        )
    except RazorpayConfigError:
        raise
    except BadRequestError as exc:
        raise RazorpayRequestError(
            f"Razorpay rejected the order payments lookup: {exc}"
        ) from None
    except (GatewayError, ServerError) as exc:
        raise RazorpayRequestError(
            f"Razorpay API error while listing order payments: {exc}"
        ) from None
    except Exception:
        logger.exception(
            "Razorpay order-payments lookup failed (order=%s, key=%s)",
            oid[:8],
            _mask(settings.RAZORPAY_KEY_ID),
        )
        raise RazorpayRequestError(
            "Razorpay order-payments lookup failed due to a network or "
            "timeout error."
        ) from None

    # Razorpay wraps the list in an items envelope (and older SDK versions
    # returned a bare collection object). Normalize defensively: any shape
    # that is not a list is treated as malformed by the caller, and empty
    # envelopes are normalized to [].
    if isinstance(payments, dict):
        payments = payments.get("items", [])
    elif not isinstance(payments, list):
        raise RazorpayRequestError(
            "Razorpay returned a malformed response while listing order "
            "payments."
        )

    if not isinstance(payments, list):
        raise RazorpayRequestError(
            "Razorpay returned a malformed response while listing order "
            "payments."
        )

    return payments


def verify_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    """Verify a Razorpay payment signature server-side.

    Computes HMAC-SHA256 over `order_id|payment_id` keyed with
    RAZORPAY_KEY_SECRET and compares it to `razorpay_signature` in constant
    time (hmac.compare_digest). Client-provided amounts are never part of
    the signed message.

    Args:
        razorpay_order_id: Order id returned by Razorpay.
        razorpay_payment_id: Payment id returned by Razorpay.
        razorpay_signature: Signature returned to the frontend by Razorpay.

    Returns:
        True if the signature is valid, False otherwise. Never raises for
        signature mismatch; only raises RazorpayConfigError if the secret is
        not configured. Future services map False to their own error
        responses; this module creates no HTTP routes.

    Raises:
        RazorpayConfigError: if RAZORPAY_KEY_SECRET is missing.
        RazorpaySignatureError: if the inputs are missing/malformed.
    """
    order_id = (razorpay_order_id or "").strip()
    payment_id = (razorpay_payment_id or "").strip()
    signature = (razorpay_signature or "").strip()

    if not order_id or not payment_id or not signature:
        raise RazorpaySignatureError(
            "Signature verification failed: order id, payment id, and "
            "signature are all required."
        )

    secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
    if not secret:
        raise RazorpayConfigError(
            "Razorpay configuration is missing: RAZORPAY_KEY_SECRET is not set."
        )

    message = f"{order_id}|{payment_id}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    # Constant-time comparison — never use ordinary == on signature bytes.
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: str) -> None:
    """Verify a Razorpay WEBHOOK signature server-side (Phase 4, Task 7).

    This is a DIFFERENT trust mechanism from verify_payment_signature():

      - Payment signature (Task 4): HMAC-SHA256 over `order_id|payment_id`
        keyed with RAZORPAY_KEY_SECRET — authenticates the Checkout
        client-side response.

      - Webhook signature (here): HMAC-SHA256 over the EXACT raw HTTP
        request body, keyed with RAZORPAY_WEBHOOK_SECRET — authenticates a
        server-to-server event notification from Razorpay
        (https://razorpay.com/docs/webhooks/validate-test). The two secrets
        are distinct values and must never be interchanged.

    Security properties (must hold for every change to this function):
    - The message is the raw request BYTES exactly as received. The body
      MUST NOT be parsed, decoded, re-serialized, or normalized before this
      function runs.
    - Constant-time comparison (hmac.compare_digest) — never `==` on
      signature bytes.
    - The secret is never included in any raised error, return value, or
      log; the expected signature is never logged.
    - A mismatch returns False silently (like verify_payment_signature);
      callers decide the HTTP outcome. Only configuration/input problems
      raise.

    Args:
        raw_body: The exact raw webhook request body bytes.
        signature: The X-Razorpay-Signature header value (hex digest).

    Returns:
        True if the signature is valid, False on mismatch.

    Raises:
        RazorpayConfigError: if RAZORPAY_WEBHOOK_SECRET is not configured.
        RazorpaySignatureError: if raw_body or the signature is missing or
            empty (nothing to verify — reject before doing any crypto).
    """
    sig = (signature or "").strip()
    if not sig:
        raise RazorpaySignatureError(
            "Webhook signature verification failed: signature is required."
        )

    if raw_body is None or len(raw_body) == 0:
        raise RazorpaySignatureError(
            "Webhook signature verification failed: request body is empty."
        )

    secret = (settings.RAZORPAY_WEBHOOK_SECRET or "").strip()
    if not secret:
        raise RazorpayConfigError(
            "Razorpay configuration is missing: RAZORPAY_WEBHOOK_SECRET is not set."
        )

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    # Constant-time comparison — never use ordinary == on signature bytes.
    return hmac.compare_digest(expected, sig)


# =====================================================================
# Refunds (Phase 4, Task 13)
# =====================================================================

def create_refund(payment_id: str, amount_paise: int) -> dict[str, Any]:
    """Create a full normal refund for a captured Razorpay payment.

    Task 13 execution-layer helper. Called ONLY by the refund execution
    service with the backend-persisted payment_id and the backend-
    persisted integer-paise amount — never client input. A full refund
    is requested by sending the exact payment amount (Razorpay treats an
    amount equal to the payment amount as a full refund; the amount
    parameter is always sent explicitly so the request is
    self-describing and auditable).

    Error taxonomy (same contract as every other function in this
    module):

    - RazorpayConfigError: configuration missing/invalid.
    - RazorpayRequestError carrying RazorpayRefundOutcome.DEFINITIVE:
      Razorpay itself definitively REJECTED the refund (HTTP 4xx-class
      `BAD_REQUEST_ERROR`: invalid payment id, refund not possible,
      validation failure). Retrying the same request cannot succeed —
      callers may safely mark the refund failed.
    - RazorpayRequestError carrying RazorpayRefundOutcome.AMBIGUOUS:
      network/timeout, 5xx-class GATEWAY_ERROR/SERVER_ERROR, or a
      malformed/absent response. Razorpay MAY have accepted the refund
      even though no usable response arrived — callers MUST NOT treat
      this as a definitive failure; the refund stays in `processing`
      for reconciliation.

    The SDK error message (Razorpay's own API description) is safe to
    surface; secrets, signatures, and raw HTTP internals never enter
    any raised error or log.

    Args:
        payment_id: The Razorpay payment id to refund (backend-stored).
        amount_paise: The refund amount in integer paise (backend-stored).

    Returns:
        The Razorpay refund entity dict on a usable response:
            {"id": "rfnd_...", "status": "processed"|"pending",
             "amount": ..., "currency": "INR", "payment_id": ...}

    Raises:
        RazorpayConfigError / RazorpayRequestError as above.
    """
    pid = (payment_id or "").strip()
    if not pid:
        raise RazorpayRequestError("Invalid payment reference: payment id is required.")
    if not isinstance(amount_paise, int) or isinstance(amount_paise, bool):
        raise RazorpayRequestError("Invalid refund amount: must be integer paise.")
    if amount_paise < 1:
        raise RazorpayRequestError("Invalid refund amount: must be at least 1 paise.")

    client = get_razorpay_client()

    try:
        refund = client.payment.refund(
            pid,
            {"amount": int(amount_paise), "currency": "INR", "speed": "normal"},
            # Explicit timeout forwarded through the SDK to requests.
            timeout=settings.RAZORPAY_TIMEOUT_SECONDS,
        )
    except RazorpayConfigError:
        raise
    except BadRequestError as exc:
        # Razorpay definitively rejected the refund (4xx-class). The SDK
        # message is Razorpay's own API description — safe, credential-free.
        raise RazorpayRequestError(
            f"{RazorpayRefundOutcome.DEFINITIVE}: Razorpay rejected the "
            f"refund request: {exc}"
        ) from None
    except (GatewayError, ServerError) as exc:
        # 5xx-class: Razorpay may or may not have accepted the refund —
        # the response was never received. AMBIGUOUS by definition.
        logger.exception(
            "Razorpay refund attempt got a server/gateway error "
            "(payment=%s, key=%s)",
            pid[:8],
            _mask(settings.RAZORPAY_KEY_ID),
        )
        raise RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay server error "
            "while creating the refund."
        ) from None
    except Exception:
        # Network/timeout/unexpected SDK failure: log WITHOUT credentials
        # or raw response bodies, raise AMBIGUOUS (never claim failure —
        # Razorpay may have accepted the refund).
        logger.exception(
            "Razorpay refund attempt failed due to a network or timeout "
            "error (payment=%s, key=%s)",
            pid[:8],
            _mask(settings.RAZORPAY_KEY_ID),
        )
        raise RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay refund attempt "
            "failed due to a network or timeout error."
        ) from None

    if not isinstance(refund, dict) or not refund.get("id"):
        # A 2xx response with a malformed/absent body is not evidence of
        # success — and not evidence of rejection either. AMBIGUOUS.
        logger.error(
            "Razorpay returned a malformed refund response (payment=%s)",
            pid[:8],
        )
        raise RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay returned a "
            "malformed response while creating the refund."
        )

    return refund


def fetch_refund(payment_id: str, refund_id: str) -> dict[str, Any]:
    """Fetch a specific refund entity for a payment (reconciliation).

    GET /v1/payments/{payment_id}/refunds/{refund_id}. This is the
    minimal Razorpay-side lookup the ambiguous-outcome reconciliation
    path needs: a refund that timed out mid-flight can be resolved by
    re-reading THIS refund from Razorpay — never by blind re-request.

    Callers (Task 14 identity reconciliation, Task 16 refund
    reconciliation) pass the persisted razorpay_refund_id and the
    backend-stored payment_id; the returned entity is never trusted by
    itself — every financial fact is re-validated against the stored
    refund record before any state transition.

    Error taxonomy identical to create_refund (DEFINITIVE only for a
    Razorpay "no such refund" 4xx; everything else AMBIGUOUS).
    """
    pid = (payment_id or "").strip()
    rid = (refund_id or "").strip()
    if not pid or not rid:
        raise RazorpayRequestError(
            "Invalid refund reference: payment id and refund id are required."
        )

    client = get_razorpay_client()

    try:
        refund = client.payment.fetch_refund_id(
            pid,
            rid,
            # Explicit timeout forwarded through the SDK to requests.
            timeout=settings.RAZORPAY_TIMEOUT_SECONDS,
        )
    except RazorpayConfigError:
        raise
    except BadRequestError as exc:
        raise RazorpayRequestError(
            f"{RazorpayRefundOutcome.DEFINITIVE}: Razorpay rejected the "
            f"refund lookup: {exc}"
        ) from None
    except (GatewayError, ServerError) as exc:
        logger.exception(
            "Razorpay refund lookup got a server/gateway error (payment=%s, key=%s)",
            pid[:8],
            _mask(settings.RAZORPAY_KEY_ID),
        )
        raise RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay server error "
            "while fetching the refund."
        ) from None
    except Exception:
        logger.exception(
            "Razorpay refund lookup failed due to a network or timeout "
            "error (payment=%s, key=%s)",
            pid[:8],
            _mask(settings.RAZORPAY_KEY_ID),
        )        
        raise RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay refund lookup "
            "failed due to a network or timeout error."
        ) from None

    if not isinstance(refund, dict) or not refund.get("id"):
        logger.error(
            "Razorpay returned a malformed refund lookup response (payment=%s)",
            pid[:8],
        )
        raise RazorpayRequestError(
            f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay returned a "
            "malformed response while fetching the refund."
        )

    return refund


# Razorpay refund-list pagination (Task 17).
#
# Page size for the refund-list lookup: a deliberately SMALL bounded value
# so one reconciliation pass cannot stream an unbounded refund list into
# memory, while still covering any realistic refund history for a single
# payment. This is a transport parameter, not a business policy — it caps
# how much of Razorpay's list is READ, never what the product will refund.
REFUND_LIST_PAGE_SIZE = 50

# Hard cap on pages per lookup. A payment's refund count is bounded by the
# product's full-refund semantics (one captured payment → at most one
# successful refund), so this cap is generous safety headroom against a
# misbehaving/malicious server that keeps returning full pages forever —
# NOT a policy about how many refunds may exist. Reaching the cap without
# termination is treated as AMBIGUOUS (fail-closed), never as "no refund
# found".
REFUND_LIST_MAX_PAGES = 100


def fetch_payment_refunds(payment_id: str) -> list[dict[str, Any]]:
    """List refunds Razorpay has recorded for a payment, across pages.

    (Task 16, pagination-hardened in Task 17.) GET
    /v1/payments/{payment_id}/refunds — the authoritative refund list for
    a payment. Reconciliation uses this ONLY for a processing refund whose
    Razorpay refund identity was never persisted (the identity was lost
    with the response): Razorpay's own list is the authoritative way to
    re-discover it. The result is NEVER trusted by itself — a candidate
    must match the backend-stored payment id, amount, and currency
    exactly, and any completion goes through the same validate → persist
    identity → complete path as every other refund outcome. This function
    only reads; it can never create or modify a refund.

    Pagination (Task 17): the SDK's fetch_multiple_refund accepts query
    parameters (`count`/`skip` per the Razorpay list API). Pages are
    fetched until a short page terminates the walk. The explicit timeout
    is preserved on EVERY page request.

    Fail-closed pagination anomalies (Task 17): a pagination failure is
    NEVER silently treated as "no refund found" —
      - a page that fails to load (network/timeout/5xx/4xx) aborts the
        whole lookup: AMBIGUOUS, retryable, the refund stays processing;
      - a malformed page body aborts the whole lookup: AMBIGUOUS;
      - a page whose shape is plausible but whose `items` is missing or
        non-list is malformed: AMBIGUOUS;
      - a duplicate refund id across pages (page overlap or a lying
        server) makes the list unreliable for identity discovery:
        AMBIGUOUS;
      - exhausting REFUND_LIST_MAX_PAGES without a short page: AMBIGUOUS.
    In every anomalous case the caller sees an AMBIGUOUS-class
    RazorpayRequestError and keeps the refund in `processing`.

    Error taxonomy identical to create_refund/fetch_refund: DEFINITIVE
    for a Razorpay 4xx-class rejection, AMBIGUOUS for network/timeout/
    5xx/malformed responses (including every pagination anomaly above).

    Args:
        payment_id: The Razorpay payment id (backend-stored, never client
            input).

    Returns:
        The refund list: a list of Razorpay refund dicts (possibly empty —
        a valid state meaning Razorpay has no refund recorded for this
        payment).

    Raises:
        RazorpayConfigError / RazorpayRequestError: same safe-error
            contract as every other function in this module.
    """
    pid = (payment_id or "").strip()
    if not pid:
        raise RazorpayRequestError("Invalid payment reference: payment id is required.")

    client = get_razorpay_client()

    # ------------------------------------------------------------------
    # Paginated walk (Task 17)
    # ------------------------------------------------------------------

    def _fetch_page(skip: int):
        """Fetch one page of the payment's refund list.

        Error mapping (identical taxonomy to every operation in this
        module) happens here, per page: a 4xx is DEFINITIVE, everything
        else ambiguous. `timeout` is forwarded on every page.
        """
        try:
            return client.payment.fetch_multiple_refund(
                pid,
                # Razorpay list-API pagination: page size + offset. The
                # SDK forwards `data` as GET query params.
                {"count": REFUND_LIST_PAGE_SIZE, "skip": skip},
                # Explicit timeout forwarded through the SDK to requests.
                timeout=settings.RAZORPAY_TIMEOUT_SECONDS,
            )
        except RazorpayConfigError:
            raise
        except BadRequestError as exc:
            # 4xx-class (e.g. unknown payment id): Razorpay's own API
            # description is safe and credential-free.
            raise RazorpayRequestError(
                f"{RazorpayRefundOutcome.DEFINITIVE}: Razorpay rejected the "
                f"refund list lookup: {exc}"
            ) from None
        except (GatewayError, ServerError) as exc:
            logger.exception(
                "Razorpay refund list lookup got a server/gateway error "
                "(payment=%s, page=%s, key=%s)",
                pid[:8],
                skip // REFUND_LIST_PAGE_SIZE,
                _mask(settings.RAZORPAY_KEY_ID),
            )
            raise RazorpayRequestError(
                f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay server error "
                "while listing payment refunds."
            ) from None
        except Exception:
            # Network/timeout/unexpected SDK failure: log WITHOUT
            # credentials or raw response bodies.
            logger.exception(
                "Razorpay refund list lookup failed due to a network or "
                "timeout error (payment=%s, page=%s, key=%s)",
                pid[:8],
                skip // REFUND_LIST_PAGE_SIZE,
                _mask(settings.RAZORPAY_KEY_ID),
            )
            raise RazorpayRequestError(
                f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay refund list "
                "lookup failed due to a network or timeout error."
            ) from None

    def _require_page_dict(page, skip: int) -> dict:
        """Fail-closed page-shape validation: a malformed page body aborts
        the whole lookup as AMBIGUOUS — it is never silently treated as an
        empty list."""
        if not isinstance(page, dict):
            logger.error(
                "Razorpay returned a malformed refund list page "
                "(payment=%s, page=%s)",
                pid[:8],
                skip // REFUND_LIST_PAGE_SIZE,
            )
            raise RazorpayRequestError(
                f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay returned a "
                "malformed response while listing payment refunds."
            )
        return page

    # Sanity guard: a payment id whose refund list could not be walked to
    # completion is unreliable input for identity discovery.
    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    skip = 0
    while True:
        if skip // REFUND_LIST_PAGE_SIZE >= REFUND_LIST_MAX_PAGES:
            # A non-terminating walk means we could NOT see the whole
            # list — uncertainty, never evidence of absence. The refund
            # must stay processing rather than risk a wrong "no refund
            # found" conclusion.
            logger.error(
                "Razorpay refund list walk did not terminate within %s "
                "pages (payment=%s)",
                REFUND_LIST_MAX_PAGES,
                pid[:8],
            )
            raise RazorpayRequestError(
                f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay refund list "
                "walk did not terminate."
            )

        page = _require_page_dict(_fetch_page(skip), skip)

        items = page.get("items", None)
        if not isinstance(items, list):
            # A plausible-looking envelope with a missing/non-list items
            # field is malformed: fail closed (never "no refunds").
            logger.error(
                "Razorpay refund list page is missing its items list "
                "(payment=%s, page=%s)",
                pid[:8],
                skip // REFUND_LIST_PAGE_SIZE,
            )
            raise RazorpayRequestError(
                f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay returned a "
                "malformed response while listing payment refunds."
            )

        for item in items:
            if not isinstance(item, dict):
                # A junk element inside an otherwise plausible page makes
                # the whole list unreliable for identity discovery.
                logger.error(
                    "Razorpay refund list page contains a malformed "
                    "refund entry (payment=%s, page=%s)",
                    pid[:8],
                    skip // REFUND_LIST_PAGE_SIZE,
                )
                raise RazorpayRequestError(
                    f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay returned "
                    "a malformed response while listing payment refunds."
                )
            rid = str(item.get("id") or "").strip()
            if rid and rid in seen_ids:
                # Duplicate id across pages: overlap or a lying server —
                # the list cannot be trusted for identity selection.
                # Fail closed as ambiguous rather than risk selecting a
                # duplicate representative of a list we cannot trust.
                logger.error(
                    "Razorpay refund list contains a duplicate refund id "
                    "across pages (payment=%s)",
                    pid[:8],
                )
                raise RazorpayRequestError(
                    f"{RazorpayRefundOutcome.AMBIGUOUS}: Razorpay refund "
                    "list is inconsistent (duplicate refund id across "
                    "pages)."
                )
            if rid:
                seen_ids.add(rid)

        collected.extend(items)

        if len(items) < REFUND_LIST_PAGE_SIZE:
            # Short (or empty) page: the authoritative end of the list.
            break
        skip += REFUND_LIST_PAGE_SIZE

    return collected
