"""Offline contracts for the production startup boundary."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from run_production import main as run_production
from run_production import production_settings


def production_values(**overrides):
    root = "/var/lib/physiocare-production-synthetic"
    values = {
        "ENVIRONMENT": "production",
        "MONGODB_URL": (
            "mongodb://synthetic-user:synthetic-password@prod-db.example.invalid:27017/"
            "physiocare?replicaSet=physiocareProdRs&tls=true"
        ),
        "DATABASE_NAME": "physiocare",
        "PRODUCTION_DATABASE_HOST": "prod-db.example.invalid",
        "PRODUCTION_DATABASE_NAME": "physiocare",
        "PRODUCTION_STORAGE_ROOT": root,
        "LAB_REPORT_STORAGE_DIR": f"{root}/lab-reports",
        "LAB_REPORT_QUARANTINE_DIR": f"{root}/lab-quarantine",
        "CLINICAL_REPORT_STORAGE_DIR": f"{root}/clinical-reports",
        "CLINICAL_REPORT_QUARANTINE_DIR": f"{root}/clinical-quarantine",
        "JWT_SECRET": "synthetic-production-access-" + "a" * 40,
        "JWT_REFRESH_SECRET": "synthetic-production-refresh-" + "b" * 40,
        "AUTH_RATE_LIMIT_ENABLED": True,
        "TRUSTED_PROXY_NETWORKS": ["192.0.2.0/24"],
        "CORS_ORIGINS": ["https://portal.example.invalid"],
        "PDF_SCANNER_MODE": "clamav_unix",
        "PDF_SCANNER_SOCKET": "/run/clamav/physiocare-clamd.sock",
        "DEMO_HOME_VISIT_REQUESTS_ENABLED": False,
        "PAYMENT_RECONCILIATION_ENABLED": False,
        "RAZORPAY_MODE": "disabled",
    }
    values.update(overrides)
    return values


def set_process_production(monkeypatch, **overrides):
    for name, value in production_values(HOST="127.0.0.1", **overrides).items():
        monkeypatch.setenv(name, json.dumps(value) if isinstance(value, list) else str(value))
    monkeypatch.delenv("PHYSIOCARE_ENV_FILE", raising=False)
    monkeypatch.delenv("PHYSIOCARE_HOME_VISIT_ENV_FILE", raising=False)


def test_production_launcher_requires_process_environment(monkeypatch, tmp_path):
    from run_production import uvicorn

    (tmp_path / ".env").write_text("ENVIRONMENT=production\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    run = Mock()
    monkeypatch.setattr(uvicorn, "run", run)

    with pytest.raises(SystemExit, match="explicit ENVIRONMENT=production"):
        run_production()

    run.assert_not_called()


def test_production_launcher_rejects_other_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(SystemExit, match="explicit ENVIRONMENT=production"):
        production_settings()


def test_misspelled_required_production_process_key_fails_closed(monkeypatch):
    set_process_production(monkeypatch)
    monkeypatch.delenv("PRODUCTION_DATABASE_NAME")
    monkeypatch.setenv("PRODUCTION_DATABASE_NMAE", "physiocare")

    with pytest.raises(ValidationError, match="PRODUCTION_DATABASE_NMAE"):
        production_settings()


def test_production_launcher_uses_validated_process_settings(monkeypatch, tmp_path):
    from run_production import uvicorn

    (tmp_path / ".env").write_text("DATABASE_NAME=physiocare_dev\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    set_process_production(monkeypatch)
    run = Mock()
    monkeypatch.setattr(uvicorn, "run", run)

    run_production()

    run.assert_called_once_with(
        "app.main:app", host="127.0.0.1", port=8000, reload=False
    )


def test_production_app_import_cannot_fill_missing_secret_from_dotenv(
    monkeypatch, tmp_path
):
    marker = "synthetic-local-only-" + "x" * 40
    (tmp_path / ".env").write_text(
        f"JWT_SECRET={marker}\nJWT_REFRESH_SECRET=synthetic-local-only-{'y' * 40}\n",
        encoding="utf-8",
    )
    set_process_production(monkeypatch)
    env = {
        name: value
        for name, value in os.environ.items()
        if name in production_values() or name in {"HOME", "PATH", "PYTHONPATH"}
    }
    env.pop("JWT_SECRET")
    env.pop("JWT_REFRESH_SECRET")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-c", "from app.core.config import settings"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "JWT_SECRET" in result.stderr
    assert marker not in result.stderr


def test_direct_asgi_import_rejects_production_selected_only_by_dotenv(tmp_path):
    values = production_values()
    (tmp_path / ".env").write_text(
        "\n".join(
            f"{name}={json.dumps(value) if isinstance(value, list) else value}"
            for name, value in values.items()
        ) + "\n",
        encoding="utf-8",
    )
    env = {
        name: value for name, value in os.environ.items()
        if name in {"HOME", "PATH"}
    }
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "process ENVIRONMENT=production" in result.stderr


def test_valid_production_configuration_reaches_runtime_guard(monkeypatch):
    monkeypatch.delenv("PHYSIOCARE_ENV_FILE", raising=False)
    monkeypatch.delenv("PHYSIOCARE_HOME_VISIT_ENV_FILE", raising=False)
    configured = Settings(_env_file=None, **production_values())
    assert configured.cookie_secure is True
    configured.validate_runtime_startup()


def test_valid_production_srv_uri_is_structurally_accepted():
    configured = Settings(
        _env_file=None,
        **production_values(
            MONGODB_URL=(
                "mongodb+srv://synthetic-user:synthetic-password@prod-db.example.invalid/"
                "physiocare?TLS=TRUE"
            )
        ),
    )
    configured.validate_runtime_startup()


def test_valid_production_ssl_alias_is_structurally_accepted():
    uri = (
        "mongodb://synthetic-user:synthetic-password@prod-db.example.invalid:27017/"
        "physiocare?replicaSet=physiocareProdRs&SSL=true"
    )
    configured = Settings(_env_file=None, **production_values(MONGODB_URL=uri))
    configured.validate_runtime_startup()


@pytest.mark.parametrize(
    "query",
    [
        "replicaSet=physiocareProdRs",
        "replicaSet=physiocareProdRs&tls=false",
        "replicaSet=physiocareProdRs&ssl=false",
        "replicaSet=physiocareProdRs&tls=true&ssl=false",
        "replicaSet=physiocareProdRs&tls=true&ssl=true",
        "replicaSet=physiocareProdRs&TLS=true&tls=false",
        "replicaSet=physiocareProdRs&tls=true&tlsInsecure=true",
        "replicaSet=physiocareProdRs&tls=true&tlsAllowInvalidCertificates=true",
        "replicaSet=physiocareProdRs&tls=true&tlsAllowInvalidHostnames=true",
        "replicaSet=physiocareProdRs&tls=true&sslAllowInvalidCertificates=true",
        "replicaSet=physiocareProdRs&tls=true&sslAllowInvalidHostnames=true",
        "replicaSet=physiocareProdRs&tls=true&ssl_cert_reqs=CERT_NONE",
        "replicaSet=physiocareProdRs&tls=true&ssl_match_hostname=false",
        "replicaSet=physiocareProdRs&tls=true&tlsDisableOCSPEndpointCheck=true",
        "replicaSet=physiocareProdRs&tls=true&sslUnknownBypass=true",
        "tls=true",
        "replicaSet=physiocareProdRs&tls=true&replicaSet=other",
    ],
)
def test_production_rejects_missing_or_insecure_tls_and_ambiguous_options(query):
    uri = (
        "mongodb://synthetic-user:synthetic-password@prod-db.example.invalid:27017/"
        f"physiocare?{query}"
    )
    with pytest.raises(ValidationError, match="Production MongoDB"):
        Settings(_env_file=None, **production_values(MONGODB_URL=uri))


@pytest.mark.parametrize(
    "overrides",
    [
        {"DATABASE_NAME": "physiocare_dev", "PRODUCTION_DATABASE_NAME": "physiocare_dev"},
        {"DATABASE_NAME": "physiocare_staging", "PRODUCTION_DATABASE_NAME": "physiocare_staging"},
        {"DATABASE_NAME": "physiocare_lab_demo", "PRODUCTION_DATABASE_NAME": "physiocare_lab_demo"},
        {"PRODUCTION_DATABASE_NAME": ""},
        {"PRODUCTION_DATABASE_HOST": ""},
        {"MONGODB_URL": "mongodb://synthetic-user:synthetic-password@127.0.0.1:27017/physiocare?replicaSet=rs&tls=true", "PRODUCTION_DATABASE_HOST": "127.0.0.1"},
        {"MONGODB_URL": "mongodb://synthetic-user:synthetic-password@127.0.0.2:27017/physiocare?replicaSet=rs&tls=true", "PRODUCTION_DATABASE_HOST": "127.0.0.2"},
        {"MONGODB_URL": "mongodb://synthetic-user:synthetic-password@[::1]:27017/physiocare?replicaSet=rs&tls=true", "PRODUCTION_DATABASE_HOST": "::1"},
        {"MONGODB_URL": "mongodb://synthetic-user:synthetic-password@[::ffff:127.0.0.1]:27017/physiocare?replicaSet=rs&tls=true", "PRODUCTION_DATABASE_HOST": "::ffff:127.0.0.1"},
        {"MONGODB_URL": "mongodb://synthetic-user:synthetic-password@localhost:27017/physiocare?replicaSet=rs&tls=true", "PRODUCTION_DATABASE_HOST": "localhost"},
        {"MONGODB_URL": "mongodb://synthetic-user:synthetic-password@127.1:27017/physiocare?replicaSet=rs&tls=true", "PRODUCTION_DATABASE_HOST": "127.1"},
        {"MONGODB_URL": "mongodb://synthetic-user:synthetic-password@prod-db.example.invalid:27017,other.example.invalid:27017/physiocare?replicaSet=rs&tls=true"},
        {"MONGODB_URL": "mongodb://prod-db.example.invalid:27017/physiocare?replicaSet=rs&tls=true"},
        {"MONGODB_URL": "mongodb://synthetic-user:synthetic-password@prod-db.example.invalid:27017/physiocare_dev?replicaSet=rs&tls=true"},
        {"AUTH_RATE_LIMIT_ENABLED": False},
        {"TRUSTED_PROXY_NETWORKS": []},
        {"TRUSTED_PROXY_NETWORKS": ["0.0.0.0/0"]},
        {"PDF_SCANNER_MODE": "disabled"},
        {"PDF_SCANNER_SOCKET": ""},
        {"LAB_DEMO_MODE": True},
        {"HOME_VISIT_DEMO_MODE": True},
        {"PHYSIOCARE_LOCAL_DEV": True},
        {"DEMO_HOME_VISIT_REQUESTS_ENABLED": True},
        {"CORS_ORIGINS": ["http://portal.example.invalid"]},
        {"CORS_ORIGINS": ["https://127.0.0.1"]},
        {"CORS_ORIGINS": ["https://portal.example.invalid/path"]},
        {"PRODUCTION_STORAGE_ROOT": ""},
        {"LAB_REPORT_STORAGE_DIR": "uploads/lab-reports"},
        {"LAB_REPORT_QUARANTINE_DIR": "/var/lib/physiocare-production-synthetic/lab-reports"},
    ],
)
def test_production_rejects_unsafe_or_incomplete_configuration(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **production_values(**overrides))


def test_production_rejects_unsafe_mongodb_uri_from_environment(monkeypatch):
    monkeypatch.setenv(
        "MONGODB_URL",
        "mongodb://synthetic-user:synthetic-password@prod-db.example.invalid:27017/"
        "physiocare?replicaSet=physiocareProdRs&tls=false",
    )
    values = production_values()
    values.pop("MONGODB_URL")
    with pytest.raises(ValidationError, match="Production MongoDB requires explicit verified TLS"):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize("selector", ["PHYSIOCARE_ENV_FILE", "PHYSIOCARE_HOME_VISIT_ENV_FILE"])
def test_production_rejects_demo_environment_selectors(monkeypatch, selector):
    monkeypatch.setenv(selector, "/tmp/synthetic-demo.env")
    with pytest.raises(ValidationError, match="local or demo"):
        Settings(_env_file=None, **production_values())


def test_rejected_production_uri_is_not_echoed_in_error():
    marker = "synthetic-password-marker"
    uri = (
        f"mongodb://synthetic-user:{marker}@prod-db.example.invalid:27017/"
        "physiocare?replicaSet=rs&tls=false"
    )
    with pytest.raises(ValidationError) as captured:
        Settings(_env_file=None, **production_values(MONGODB_URL=uri))
    assert marker not in str(captured.value)
    assert uri not in str(captured.value)


@pytest.mark.asyncio
async def test_production_lifespan_rejects_runtime_mutation_before_scanner_or_database(monkeypatch):
    from app import main

    configured = Settings(_env_file=None, **production_values())
    configured.MONGODB_URL = "mongodb://127.0.0.1:27017/physiocare_dev"
    database_init = AsyncMock()
    scanner = Mock()
    worker = Mock()
    monkeypatch.setattr(main, "settings", configured)
    monkeypatch.setattr(main, "init_db", database_init)
    monkeypatch.setattr(main, "ClamAvUnixScanner", scanner)
    monkeypatch.setattr(main, "PaymentReconciliationWorker", worker)

    with pytest.raises(ValueError, match="Production"):
        async with main.lifespan(SimpleNamespace(state=SimpleNamespace())):
            pass

    database_init.assert_not_awaited()
    scanner.assert_not_called()
    worker.assert_not_called()


@pytest.mark.asyncio
async def test_valid_production_lifespan_reaches_scanner_and_database_with_mocks(monkeypatch):
    from app import main

    configured = Settings(_env_file=None, **production_values())
    database_init = AsyncMock()
    scanner_ready = AsyncMock(return_value=True)
    worker = Mock()
    monkeypatch.setattr(main, "settings", configured)
    monkeypatch.setattr(main, "init_db", database_init)
    monkeypatch.setattr(main.ClamAvUnixScanner, "ready", scanner_ready)
    monkeypatch.setattr(main.ClinicalReportStorage, "scanner", None)
    monkeypatch.setattr(main.LabReportStorage, "scanner", None)
    monkeypatch.setattr(main, "PaymentReconciliationWorker", worker)

    async with main.lifespan(SimpleNamespace(state=SimpleNamespace())):
        pass

    scanner_ready.assert_awaited_once()
    database_init.assert_awaited_once()
    worker.assert_not_called()


def test_production_database_guard_rechecks_before_client(monkeypatch):
    import asyncio
    from app import database

    configured = Settings(_env_file=None, **production_values())
    configured.DATABASE_NAME = "physiocare_dev"
    client_constructor = Mock()
    initialize = AsyncMock()
    monkeypatch.setattr(database, "settings", configured)
    monkeypatch.setattr(database, "BeanieCompatibleMotorClient", client_constructor)
    monkeypatch.setattr(database, "init_beanie", initialize)

    with pytest.raises(ValueError, match="Production"):
        asyncio.run(database.init_db())

    client_constructor.assert_not_called()
    initialize.assert_not_awaited()
