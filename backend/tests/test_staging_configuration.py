from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def staging_values(**overrides):
    values = {
        "ENVIRONMENT": "staging",
        "STAGING_INSTANCE_ID": "physiocare-isolated-staging",
        "MONGODB_URL": (
            "mongodb://staging-user:staging-password@staging-db.example.invalid:27017/"
            "physiocare_staging?authSource=admin&tls=true"
        ),
        "DATABASE_NAME": "physiocare_staging",
        "STAGING_DATABASE_HOST": "staging-db.example.invalid",
        "STAGING_DATABASE_NAME": "physiocare_staging",
        "JWT_SECRET": "staging-access-" + "a" * 40,
        "JWT_REFRESH_SECRET": "staging-refresh-" + "b" * 40,
        "AUTH_RATE_LIMIT_ENABLED": True,
        "TRUSTED_PROXY_NETWORKS": ["192.0.2.0/24"],
        "CORS_ORIGINS": ["https://staging.example.invalid"],
        "STAGING_STORAGE_ROOT": "/tmp/physiocare-isolated-staging",
        "LAB_REPORT_STORAGE_DIR": "/tmp/physiocare-isolated-staging/lab-reports",
        "LAB_REPORT_QUARANTINE_DIR": "/tmp/physiocare-isolated-staging/lab-quarantine",
        "CLINICAL_REPORT_STORAGE_DIR": "/tmp/physiocare-isolated-staging/clinical-reports",
        "CLINICAL_REPORT_QUARANTINE_DIR": "/tmp/physiocare-isolated-staging/clinical-quarantine",
        "RAZORPAY_MODE": "disabled",
        "RAZORPAY_KEY_ID": "",
        "RAZORPAY_KEY_SECRET": "",
        "RAZORPAY_WEBHOOK_SECRET": "",
        "APPOINTMENT_BILLING_CURRENCY": "",
        "PAYMENT_RECONCILIATION_ENABLED": False,
        "PDF_SCANNER_MODE": "disabled",
    }
    values.update(overrides)
    return values


def test_explicit_isolated_staging_configuration_is_accepted():
    configured = Settings(_env_file=None, **staging_values())

    assert configured.cookie_secure is True
    configured.validate_runtime_startup()


@pytest.mark.parametrize(
    "query",
    [
        "authSource=admin",
        "authSource=admin&tls=false",
        "authSource=admin&ssl=false",
        "authSource=admin&tls=true&ssl=false",
        "authSource=admin&tls=true&ssl=true",
        "authSource=admin&TLS=true&tls=false",
        "authSource=admin&TLS=TRUE",
        "authSource=admin&tls=true&tlsInsecure=true",
        "authSource=admin&tls=true&tlsAllowInvalidCertificates=true",
        "authSource=admin&tls=true&tlsAllowInvalidHostnames=true",
        "authSource=admin&tls=true&sslAllowInvalidCertificates=true",
        "authSource=admin&tls=true&sslAllowInvalidHostnames=true",
        "authSource=admin&tls=true&ssl_cert_reqs=CERT_NONE",
        "authSource=admin&tls=true&ssl_match_hostname=false",
    ],
)
def test_staging_rejects_missing_or_insecure_mongodb_tls(query):
    uri = (
        "mongodb://staging-user:staging-password@staging-db.example.invalid:27017/"
        f"physiocare_staging?{query}"
    )
    with pytest.raises(ValidationError, match="Staging MongoDB"):
        Settings(_env_file=None, **staging_values(MONGODB_URL=uri))


@pytest.mark.parametrize("tls_option", ["tls=true", "SSL=true"])
def test_staging_accepts_verified_mongodb_tls_aliases(tls_option):
    uri = (
        "mongodb://staging-user:staging-password@staging-db.example.invalid:27017/"
        f"physiocare_staging?authSource=admin&{tls_option}"
    )
    configured = Settings(_env_file=None, **staging_values(MONGODB_URL=uri))
    configured.validate_runtime_startup()


def test_staging_rejects_insecure_mongodb_url_from_environment(monkeypatch):
    monkeypatch.setenv(
        "MONGODB_URL",
        "mongodb://staging-user:staging-password@staging-db.example.invalid:27017/"
        "physiocare_staging?authSource=admin&tls=false",
    )
    values = staging_values()
    values.pop("MONGODB_URL")
    with pytest.raises(ValidationError, match="Staging MongoDB requires explicit TLS"):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"STAGING_INSTANCE_ID": ""},
        {"DATABASE_NAME": "physiocare", "STAGING_DATABASE_NAME": "physiocare"},
        {"DATABASE_NAME": "physiocare_prod_staging", "STAGING_DATABASE_NAME": "physiocare_prod_staging"},
        {"STAGING_DATABASE_NAME": "other_staging"},
        {"MONGODB_URL": "mongodb://user:pass@production-db.example.invalid:27017/physiocare_staging"},
        {"STAGING_DATABASE_HOST": "different-db.example.invalid"},
        {"MONGODB_URL": "mongodb://staging-db.example.invalid:27017/physiocare_staging"},
        {"AUTH_RATE_LIMIT_ENABLED": False},
        {"TRUSTED_PROXY_NETWORKS": []},
        {"CORS_ORIGINS": ["http://staging.example.invalid"]},
        {"CORS_ORIGINS": ["https://staging.example.invalid/path"]},
        {"STAGING_STORAGE_ROOT": "relative/staging"},
        {"LAB_REPORT_STORAGE_DIR": "uploads/lab-reports"},
        {"LAB_REPORT_STORAGE_DIR": "/var/lib/shared/lab-reports"},
        {
            "LAB_REPORT_STORAGE_DIR": "/tmp/physiocare-isolated-staging/shared",
            "LAB_REPORT_QUARANTINE_DIR": "/tmp/physiocare-isolated-staging/shared",
        },
        {"RAZORPAY_MODE": "test"},
        {"RAZORPAY_KEY_ID": "rzp_test_not-permitted-yet"},
        {"PAYMENT_RECONCILIATION_ENABLED": True},
        {"PDF_SCANNER_MODE": "approved"},
        {"PDF_SCANNER_MODE": "clamav_unix", "PDF_SCANNER_SOCKET": "relative/clamd.sock"},
    ],
)
def test_unsafe_staging_configuration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **staging_values(**overrides))


def test_unknown_environment_name_is_rejected():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            JWT_SECRET="a" * 40,
            JWT_REFRESH_SECRET="b" * 40,
            ENVIRONMENT="stagng",
        )


def test_staging_accepts_explicit_private_unix_scanner_configuration():
    configured = Settings(
        _env_file=None,
        **staging_values(
            PDF_SCANNER_MODE="clamav_unix",
            PDF_SCANNER_SOCKET="/run/clamav/physiocare-clamd.sock",
        ),
    )
    assert configured.PDF_SCANNER_MODE == "clamav_unix"


@pytest.mark.asyncio
async def test_lifespan_guard_fails_before_database_or_worker(monkeypatch):
    from app import main as main_module

    guard = Mock()
    guard.validate_runtime_startup.side_effect = ValueError("unsafe staging configuration")
    database_init = AsyncMock()
    worker = Mock()
    monkeypatch.setattr(main_module, "settings", guard)
    monkeypatch.setattr(main_module, "init_db", database_init)
    monkeypatch.setattr(main_module, "PaymentReconciliationWorker", worker)

    with pytest.raises(ValueError, match="unsafe staging configuration"):
        async with main_module.lifespan(SimpleNamespace(state=SimpleNamespace())):
            pass

    database_init.assert_not_awaited()
    worker.assert_not_called()
