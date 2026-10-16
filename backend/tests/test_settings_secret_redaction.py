"""
Task 21 regression tests — Settings secret redaction in diagnostics.

Root cause proven here: on a pytest assertion failure the live Settings
object is repr'd, and pydantic's default repr included every .env-loaded
field value verbatim (Task 20 exposure). The fix redacts
SECRET_SETTINGS_FIELDS in __repr_args__ (which pydantic v2 routes repr(),
str(), __pretty__ and pytest diagnostics through) and in model_dump /
model_dump_json.

ISOLATION: these tests NEVER read or print real .env values. Every
assertion runs against isolated Settings instances built from FAKE,
deterministic secrets with `_env_file=None` (pydantic-settings init
kwargs outrank both real environment variables and the .env file). The
live-singleton test asserts only on repr SHAPE (the mask marker), never
on values.
"""
import json
import re
from typing import Any, Dict

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import SECRET_SETTINGS_FIELDS, Settings, settings

# Deterministic FAKE secrets — deliberately not real credentials.
FAKE_SECRETS: Dict[str, str] = {
    "MONGODB_URL": "mongodb://fake_user:fake_password_unit_tests_only@fake.mongo.example:27017/fakedb",
    "JWT_SECRET": "fake-jwt-secret-unit-tests-only-0001",
    "JWT_REFRESH_SECRET": "fake-jwt-refresh-secret-unit-tests-only-0002",
    "RAZORPAY_KEY_SECRET": "fake_razorpay_key_secret_unit_tests_only_0003",
    "RAZORPAY_WEBHOOK_SECRET": "fake_razorpay_webhook_secret_unit_tests_only_0004",
}
# RAZORPAY_KEY_ID is public by design (frontend checkout needs it) and
# must stay inspectable; DATABASE_NAME is a plain non-secret.
FAKE_PUBLIC: Dict[str, str] = {
    "DATABASE_NAME": "fake_db_name_for_redaction_tests",
    "RAZORPAY_KEY_ID": "rzp_test_FAKEPUBLICKEYID0000",
}

MASK = "**********"


def make_isolated_settings(**overrides: Any) -> Settings:
    """Isolated Settings: _env_file=None + explicit init kwargs, so no
    real .env value or real environment variable can reach the fields
    under test."""
    return Settings(_env_file=None, **{**FAKE_SECRETS, **FAKE_PUBLIC, **overrides})


def _secret_names_marked(repr_text: str) -> bool:
    return all(
        f"{name}=SecretStr('{MASK}')" in repr_text
        for name in SECRET_SETTINGS_FIELDS
    )


# ---------------------------------------------------------------------------
# Inventory — every secret-bearing field is covered by the redaction set
# ---------------------------------------------------------------------------

def test_secret_field_inventory_is_exact():
    """The redaction set covers exactly the secret-bearing Settings
    fields (Mongo URL w/ embedded credentials, JWT secrets, Razorpay
    backend-only secrets) — and each name is a real Settings field."""
    assert SECRET_SETTINGS_FIELDS == frozenset({
        "MONGODB_URL",
        "JWT_SECRET",
        "JWT_REFRESH_SECRET",
        "RAZORPAY_KEY_SECRET",
        "RAZORPAY_WEBHOOK_SECRET",
    })
    for name in SECRET_SETTINGS_FIELDS:
        assert name in Settings.model_fields


# ---------------------------------------------------------------------------
# repr / str — the Task 20 exposure vectors
# ---------------------------------------------------------------------------

def test_repr_contains_no_fake_secret_values():
    """repr(Settings) shows the pydantic mask marker for every secret
    field and never contains any fake secret value."""
    r = repr(make_isolated_settings())
    for fake in FAKE_SECRETS.values():
        assert fake not in r
    assert _secret_names_marked(r)


def test_str_contains_no_fake_secret_values():
    """str(Settings) routes through the same __repr_args__ hook: no fake
    secret value appears, non-secrets remain inspectable."""
    s = make_isolated_settings()
    text = str(s)
    for fake in FAKE_SECRETS.values():
        assert fake not in text
    assert MASK in text


def test_non_secret_values_remain_inspectable_in_repr():
    """Redaction must not hide useful diagnostics: DATABASE_NAME and the
    public-by-design RAZORPAY_KEY_ID stay visible in repr."""
    r = repr(make_isolated_settings())
    assert f"DATABASE_NAME='{FAKE_PUBLIC['DATABASE_NAME']}'" in r
    assert f"RAZORPAY_KEY_ID='{FAKE_PUBLIC['RAZORPAY_KEY_ID']}'" in r
    assert "ENVIRONMENT='development'" in r


def test_assertion_failure_diagnostic_containing_repr_leaks_nothing():
    """Mirrors the Task 20 exposure shape: a failing assertion whose
    diagnostic embeds repr(settings) must not carry secret values."""
    s = make_isolated_settings()
    try:
        # Deliberately failing pin-style assertion (Task 20 pattern).
        assert s.PAYMENT_PENDING_EXPIRY_MINUTES is not None, f"state: {s!r}"
        pytest.fail("expected AssertionError")
    except AssertionError as exc:
        diagnostic = str(exc)
    for fake in FAKE_SECRETS.values():
        assert fake not in diagnostic
    assert _secret_names_marked(diagnostic)


# ---------------------------------------------------------------------------
# Validation-error diagnostics
# ---------------------------------------------------------------------------

def test_validation_error_output_contains_no_fake_secret_values():
    """A pydantic ValidationError (bad non-secret field) reports only the
    failing field's input — never any secret field value."""
    with pytest.raises(ValidationError) as exc_info:
        make_isolated_settings(ACCESS_TOKEN_EXPIRE_MINUTES="not-an-int")
    err_text = str(exc_info.value)
    errors_json = json.dumps(exc_info.value.errors(), default=str)
    for fake in FAKE_SECRETS.values():
        assert fake not in err_text
        assert fake not in errors_json


# ---------------------------------------------------------------------------
# Serialization diagnostics
# ---------------------------------------------------------------------------

def test_model_dump_masks_secret_values():
    """model_dump replaces every secret value with the fixed placeholder;
    non-secret values pass through unchanged."""
    dumped = make_isolated_settings().model_dump()
    for name in SECRET_SETTINGS_FIELDS:
        assert dumped[name] == MASK
    assert dumped["DATABASE_NAME"] == FAKE_PUBLIC["DATABASE_NAME"]
    assert dumped["RAZORPAY_KEY_ID"] == FAKE_PUBLIC["RAZORPAY_KEY_ID"]


def test_model_dump_and_json_contain_no_fake_secret_values():
    dump_json = make_isolated_settings().model_dump_json()
    dump_json_indented = make_isolated_settings().model_dump_json(indent=2)
    as_json = json.dumps(make_isolated_settings().model_dump())
    for text in (dump_json, dump_json_indented, as_json):
        for fake in FAKE_SECRETS.values():
            assert fake not in text
        assert MASK in text


# ---------------------------------------------------------------------------
# Runtime access — consumers must still receive usable secrets
# ---------------------------------------------------------------------------

def test_runtime_access_returns_plain_usable_strings():
    """Redaction is representation-only: consumers (security.py JWT
    encode/decode, database.py motor client, razorpay_client.py) keep
    reading plain string values. (Fake values compared in-process.)"""
    s = make_isolated_settings()
    for name, fake in FAKE_SECRETS.items():
        value = getattr(s, name)
        assert type(value) is str, name          # not SecretStr, not masked
        assert value == fake, name
        assert value.strip() == fake, name       # razorpay_client strips it
        assert len(value.encode()) > 0, name     # JWT/HMAC consumers encode it


def test_runtime_secret_values_absent_from_their_own_repr():
    """A str's own repr is its content — which is exactly why the masking
    must happen at the Settings representation layer, and why the fields
    must NOT be replaced by masked strings at runtime."""
    s = make_isolated_settings()
    assert repr(s.JWT_SECRET) == f"'{FAKE_SECRETS['JWT_SECRET']}'"


# ---------------------------------------------------------------------------
# Live singleton — shape-only guard, zero real-value reads
# ---------------------------------------------------------------------------

def test_live_singleton_repr_masks_secret_fields():
    """The real application singleton (which loaded backend/.env) must
    repr with every secret field masked. This test reads NO values: it
    checks only that each secret field name is followed by the mask
    marker, and that the Mongo URL scheme can no longer appear at all."""
    r = repr(settings)
    assert _secret_names_marked(r)
    # Masked URL: no URI scheme (://) can appear anywhere in the repr —
    # field names never contain one, so any hit would be a leaked value.
    assert re.search(r"[A-Za-z][A-Za-z0-9+.-]*://", r) is None
    assert f"RAZORPAY_KEY_ID='" in r           # public key id stays visible
    assert f"ENVIRONMENT='{settings.ENVIRONMENT}'" in r
