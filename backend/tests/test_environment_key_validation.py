"""Unknown dotenv and direct settings keys must fail without a database connection."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def asgi_import_environment(**overrides):
    names = {"HOME", "PATH"}
    env = {name: value for name, value in os.environ.items() if name in names}
    env.update({
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        "PYTHONDONTWRITEBYTECODE": "1",
        "JWT_SECRET": "synthetic-access-" + "a" * 40,
        "JWT_REFRESH_SECRET": "synthetic-refresh-" + "b" * 40,
        "MONGODB_URL": "mongodb://127.0.0.1:1/physiocare_dev",
        "DATABASE_NAME": "physiocare_dev",
        "PAYMENT_RECONCILIATION_ENABLED": "false",
    })
    env.update(overrides)
    return env


def test_direct_asgi_import_rejects_missing_environment(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app"],
        cwd=tmp_path,
        env=asgi_import_environment(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "ENVIRONMENT" in result.stderr


def test_direct_asgi_import_accepts_explicit_local_development(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app; assert app is not None"],
        cwd=tmp_path,
        env=asgi_import_environment(
            ENVIRONMENT="development", PHYSIOCARE_LOCAL_DEV="true"
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_direct_asgi_import_rejects_development_without_local_identity(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app"],
        cwd=tmp_path,
        env=asgi_import_environment(ENVIRONMENT="development"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "explicit local identity" in result.stderr


def test_reload_launcher_rejects_production_before_dotenv(monkeypatch):
    import run

    monkeypatch.setenv("ENVIRONMENT", "production")
    dotenv = Mock()
    launch = Mock()
    monkeypatch.setattr(run, "load_dotenv", dotenv)
    monkeypatch.setattr(run.uvicorn, "run", launch)

    with pytest.raises(SystemExit, match="ENVIRONMENT=development"):
        run.main()

    dotenv.assert_not_called()
    launch.assert_not_called()


def test_reload_launcher_preserves_explicit_development(monkeypatch):
    import run

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8000")
    monkeypatch.setattr(run, "load_dotenv", Mock())
    launch = Mock()
    monkeypatch.setattr(run.uvicorn, "run", launch)

    run.main()

    launch.assert_called_once_with(
        "app.main:app", host="127.0.0.1", port=8000, reload=True
    )


@pytest.mark.parametrize("name", ["BOOKING_HORIZON_DYS", "RAZORPAY_KEY_SECRETT"])
def test_unknown_application_process_key_is_rejected_without_value(monkeypatch, name):
    marker = "synthetic-value-not-for-errors"
    monkeypatch.setenv(name, marker)

    with pytest.raises(ValidationError) as captured:
        Settings(
            _env_file=None,
            ENVIRONMENT="test",
            JWT_SECRET="synthetic-access-" + "a" * 40,
            JWT_REFRESH_SECRET="synthetic-refresh-" + "b" * 40,
        )

    assert name in str(captured.value)
    assert marker not in str(captured.value)


def test_unrelated_platform_process_keys_are_accepted(monkeypatch):
    monkeypatch.setenv("HOSTING_PLATFORM_REGION", "synthetic-region")
    monkeypatch.setenv("DATABASE_URL", "synthetic-unused-platform-setting")

    configured = Settings(
        _env_file=None,
        ENVIRONMENT="test",
        JWT_SECRET="synthetic-access-" + "a" * 40,
        JWT_REFRESH_SECRET="synthetic-refresh-" + "b" * 40,
    )

    assert configured.ENVIRONMENT == "test"


def test_misspelled_dotenv_setting_is_rejected(tmp_path):
    selected = tmp_path / ".env"
    selected.write_text("BOOKING_HORIZON_DYS=30\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="booking_horizon_dys"):
        Settings(
            _env_file=selected,
            ENVIRONMENT="test",
            JWT_SECRET="synthetic-access-" + "a" * 40,
            JWT_REFRESH_SECRET="synthetic-refresh-" + "b" * 40,
        )


def test_misspelled_direct_setting_is_rejected():
    with pytest.raises(ValidationError, match="BOOKING_HORIZON_DYS"):
        Settings(
            _env_file=None,
            ENVIRONMENT="test",
            JWT_SECRET="synthetic-access-" + "a" * 40,
            JWT_REFRESH_SECRET="synthetic-refresh-" + "b" * 40,
            BOOKING_HORIZON_DYS=30,
        )
