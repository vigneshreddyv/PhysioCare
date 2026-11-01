"""Offline contracts for the ordinary local-development database boundary."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def development_values(**overrides):
    values = {
        "ENVIRONMENT": "development",
        "PHYSIOCARE_LOCAL_DEV": True,
        "MONGODB_URL": "mongodb://127.0.0.1:27017/physiocare_dev",
        "DATABASE_NAME": "physiocare_dev",
        "JWT_SECRET": "development-access-" + "a" * 40,
        "JWT_REFRESH_SECRET": "development-refresh-" + "b" * 40,
        "RAZORPAY_MODE": "disabled",
        "PAYMENT_RECONCILIATION_ENABLED": False,
        "PDF_SCANNER_MODE": "disabled",
        "AUTH_RATE_LIMIT_ENABLED": True,
        "TRUSTED_PROXY_NETWORKS": [],
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("uri", "canonical"),
    [
        (
            "mongodb://127.0.0.1:27017/physiocare_dev",
            "mongodb://127.0.0.1:27017/physiocare_dev",
        ),
        (
            "mongodb://localhost:27017/physiocare_dev",
            "mongodb://127.0.0.1:27017/physiocare_dev",
        ),
        (
            "mongodb://[::1]:27017/physiocare_dev",
            "mongodb://[::1]:27017/physiocare_dev",
        ),
    ],
)
def test_development_accepts_only_canonical_loopback_targets(uri, canonical, monkeypatch):
    monkeypatch.delenv("PHYSIOCARE_ENV_FILE", raising=False)
    monkeypatch.delenv("PHYSIOCARE_HOME_VISIT_ENV_FILE", raising=False)
    configured = Settings(_env_file=None, **development_values(MONGODB_URL=uri))
    assert configured.development_mongodb_url() == canonical
    configured.validate_runtime_startup()


@pytest.mark.parametrize(
    "overrides",
    [
        {"DATABASE_NAME": "physiocare"},
        {"DATABASE_NAME": ""},
        {"DATABASE_NAME": "other_dev"},
        {"MONGODB_URL": "mongodb://127.0.0.1:27017/physiocare"},
        {"MONGODB_URL": "mongodb://127.0.0.1:27017/other_dev"},
        {"MONGODB_URL": "mongodb://127.0.0.1:27017"},
        {"MONGODB_URL": "mongodb://127.0.0.1:27017/"},
        {"MONGODB_URL": ""},
        {"MONGODB_URL": "not-a-mongodb-uri"},
        {"MONGODB_URL": "mongodb+srv://cluster.example.invalid/physiocare_dev"},
        {"MONGODB_URL": "mongodb://db.example.invalid:27017/physiocare_dev"},
        {"MONGODB_URL": "mongodb://localhost.evil.invalid:27017/physiocare_dev"},
        {"MONGODB_URL": "mongodb://192.0.2.9:27017/physiocare_dev"},
        {"MONGODB_URL": "mongodb://127.0.0.1:27017,192.0.2.9:27017/physiocare_dev"},
        {"MONGODB_URL": "mongodb://127.0.0.1/physiocare_dev"},
        {"MONGODB_URL": "mongodb://127.0.0.1:99999/physiocare_dev"},
        {"MONGODB_URL": "mongodb://127.0.0.1:27017/physiocare_dev?directConnection=false"},
        {"MONGODB_URL": "mongodb://user:password@127.0.0.1:27017/physiocare_dev"},
        {"RAZORPAY_MODE": "test"},
        {"RAZORPAY_KEY_SECRET": "synthetic-key"},
        {"PAYMENT_RECONCILIATION_ENABLED": True},
        {"PDF_SCANNER_MODE": "clamav_unix", "PDF_SCANNER_SOCKET": "/tmp/fake-clamd.sock"},
        {"PDF_SCANNER_SOCKET": "/tmp/fake-clamd.sock"},
        {"AUTH_RATE_LIMIT_ENABLED": False},
        {"TRUSTED_PROXY_NETWORKS": ["127.0.0.1/32"]},
    ],
)
def test_development_rejects_unsafe_identity_and_services(overrides, monkeypatch):
    monkeypatch.delenv("PHYSIOCARE_ENV_FILE", raising=False)
    monkeypatch.delenv("PHYSIOCARE_HOME_VISIT_ENV_FILE", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **development_values(**overrides))


@pytest.mark.parametrize(
    "selector", ["PHYSIOCARE_ENV_FILE", "PHYSIOCARE_HOME_VISIT_ENV_FILE"]
)
def test_development_rejects_environment_file_override(selector, monkeypatch, tmp_path):
    monkeypatch.setenv(selector, str(tmp_path / "unexpected.env"))
    with pytest.raises(ValidationError, match="environment-file override"):
        Settings(_env_file=None, **development_values())


def test_development_rejects_two_selected_environment_files(monkeypatch, tmp_path):
    monkeypatch.setenv("PHYSIOCARE_ENV_FILE", str(tmp_path / "one.env"))
    monkeypatch.setenv("PHYSIOCARE_HOME_VISIT_ENV_FILE", str(tmp_path / "two.env"))
    with pytest.raises(ValidationError, match="two environment files"):
        Settings(_env_file=None, **development_values())


@pytest.mark.parametrize(
    ("name", "unsafe_value"),
    [
        ("DATABASE_NAME", "physiocare"),
        ("MONGODB_URL", "mongodb://db.example.invalid:27017/physiocare_dev"),
        ("RAZORPAY_MODE", "test"),
        ("PAYMENT_RECONCILIATION_ENABLED", "true"),
    ],
)
def test_development_rejects_unsafe_inherited_values(monkeypatch, name, unsafe_value):
    monkeypatch.setenv(name, unsafe_value)
    values = development_values()
    values.pop(name)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_local_identity_rejects_inherited_environment_switch(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    values = development_values()
    values.pop("ENVIRONMENT")
    with pytest.raises(ValidationError, match="Local development identity"):
        Settings(_env_file=None, **values)


def test_local_identity_rejects_environment_file_switch(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("ENVIRONMENT=production\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    values = development_values()
    values.pop("ENVIRONMENT")
    with pytest.raises(ValidationError, match="Local development identity"):
        Settings(**values)


def test_local_identity_rejects_selected_environment_file_switch(monkeypatch, tmp_path):
    selected = tmp_path / "selected.env"
    selected.write_text("ENVIRONMENT=production\n", encoding="utf-8")
    monkeypatch.setenv("PHYSIOCARE_ENV_FILE", str(selected))
    values = development_values()
    values.pop("ENVIRONMENT")
    with pytest.raises(ValidationError, match="Local development identity"):
        Settings(_env_file=selected, **values)


def test_rejected_uri_does_not_appear_in_error():
    marker = "synthetic-password-marker"
    uri = f"mongodb://user:{marker}@remote.example.invalid:27017/physiocare_dev"
    with pytest.raises(ValidationError) as captured:
        Settings(_env_file=None, **development_values(MONGODB_URL=uri))
    assert marker not in str(captured.value)
    assert uri not in str(captured.value)


def test_production_without_local_identity_keeps_existing_behavior():
    configured = Settings(
        _env_file=None,
        **development_values(
            ENVIRONMENT="production",
            PHYSIOCARE_LOCAL_DEV=False,
            MONGODB_URL="mongodb://production.example.invalid:27017/physiocare",
            DATABASE_NAME="physiocare",
            PAYMENT_RECONCILIATION_ENABLED=True,
        ),
    )
    assert configured.ENVIRONMENT == "production"
    configured.validate_runtime_startup()


def test_development_rejects_unsafe_working_directory_env_file(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("DATABASE_NAME=physiocare\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_NAME", raising=False)
    values = development_values()
    values.pop("DATABASE_NAME")
    with pytest.raises(ValidationError, match="physiocare_dev"):
        Settings(**values)


def test_runtime_rechecks_mutated_development_target_before_client(monkeypatch):
    from app import database

    configured = Settings(_env_file=None, **development_values())
    configured.MONGODB_URL = "mongodb://remote.example.invalid:27017/physiocare_dev"
    client_constructor = Mock()
    initialize = AsyncMock()
    monkeypatch.setattr(database, "settings", configured)
    monkeypatch.setattr(database, "BeanieCompatibleMotorClient", client_constructor)
    monkeypatch.setattr(database, "init_beanie", initialize)

    with pytest.raises(ValueError, match="Development MongoDB URL"):
        asyncio.run(database.init_db())

    client_constructor.assert_not_called()
    initialize.assert_not_awaited()


def test_runtime_rejects_mutated_environment_before_client(monkeypatch):
    from app import database

    configured = Settings(_env_file=None, **development_values())
    configured.ENVIRONMENT = "production"
    client_constructor = Mock()
    initialize = AsyncMock()
    monkeypatch.setattr(database, "settings", configured)
    monkeypatch.setattr(database, "BeanieCompatibleMotorClient", client_constructor)
    monkeypatch.setattr(database, "init_beanie", initialize)

    with pytest.raises(ValueError, match="Local development identity"):
        asyncio.run(database.init_db())

    client_constructor.assert_not_called()
    initialize.assert_not_awaited()


def test_valid_development_client_is_pinned_before_beanie(monkeypatch):
    from app import database

    configured = Settings(
        _env_file=None,
        **development_values(MONGODB_URL="mongodb://localhost:27017/physiocare_dev"),
    )
    client = MagicMock()
    client_constructor = Mock(return_value=client)
    initialize = AsyncMock()
    monkeypatch.setattr(database, "settings", configured)
    monkeypatch.setattr(database, "BeanieCompatibleMotorClient", client_constructor)
    monkeypatch.setattr(database, "init_beanie", initialize)

    asyncio.run(database.init_db())

    client_constructor.assert_called_once_with(
        "mongodb://127.0.0.1:27017/physiocare_dev", directConnection=True
    )
    initialize.assert_awaited_once()
    assert initialize.await_args.kwargs["database"] is client["physiocare_dev"]


@pytest.mark.asyncio
async def test_unsafe_development_lifespan_stops_before_database_and_worker(monkeypatch):
    from app import main

    configured = Settings(_env_file=None, **development_values())
    configured.DATABASE_NAME = "physiocare"
    database_init = AsyncMock()
    worker = Mock()
    scanner = Mock()
    monkeypatch.setattr(main, "settings", configured)
    monkeypatch.setattr(main, "init_db", database_init)
    monkeypatch.setattr(main, "PaymentReconciliationWorker", worker)
    monkeypatch.setattr(main, "UnavailablePdfMalwareScanner", scanner)

    with pytest.raises(ValueError, match="physiocare_dev"):
        async with main.lifespan(SimpleNamespace(state=SimpleNamespace())):
            pass

    database_init.assert_not_awaited()
    worker.assert_not_called()
    scanner.assert_not_called()
