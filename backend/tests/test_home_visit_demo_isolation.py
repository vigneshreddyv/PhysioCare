import pytest
from pydantic import ValidationError

from app.core.config import (
    HOME_VISIT_DEMO_DATABASE_NAME,
    HOME_VISIT_DEMO_FRONTEND_ORIGIN,
    HOME_VISIT_DEMO_MONGODB_URL,
    LAB_DEMO_DATABASE_NAME,
    LAB_DEMO_MONGODB_URL,
    Settings,
    lab_demo_home,
)


def home_demo_values(**overrides):
    values = {
        "MONGODB_URL": HOME_VISIT_DEMO_MONGODB_URL,
        "DATABASE_NAME": HOME_VISIT_DEMO_DATABASE_NAME,
        "HOME_VISIT_DEMO_MODE": True,
        "JWT_SECRET": "h" * 40,
        "JWT_REFRESH_SECRET": "r" * 40,
        "ENVIRONMENT": "development",
        "HOST": "127.0.0.1",
        "PORT": 8002,
        "RAZORPAY_MODE": "disabled",
        "RAZORPAY_KEY_ID": "",
        "RAZORPAY_KEY_SECRET": "",
        "RAZORPAY_WEBHOOK_SECRET": "",
        "PAYMENT_RECONCILIATION_ENABLED": False,
        "CORS_ORIGINS": [HOME_VISIT_DEMO_FRONTEND_ORIGIN],
    }
    values.update(overrides)
    return values


def test_home_visit_demo_configuration_is_accepted():
    configured = Settings(_env_file=None, **home_demo_values())

    assert configured.DATABASE_NAME == HOME_VISIT_DEMO_DATABASE_NAME
    assert configured.MONGODB_URL == HOME_VISIT_DEMO_MONGODB_URL
    assert configured.PORT == 8002
    assert configured.CORS_ORIGINS == [HOME_VISIT_DEMO_FRONTEND_ORIGIN]


@pytest.mark.parametrize(
    "overrides",
    [
        {"DATABASE_NAME": "physiocare"},
        {"MONGODB_URL": "mongodb://127.0.0.1:27018"},
        {"MONGODB_URL": "mongodb://localhost:27019"},
        {"PORT": 8001},
        {"CORS_ORIGINS": ["http://127.0.0.1:5175"]},
        {"ENVIRONMENT": "production"},
        {"RAZORPAY_MODE": "test"},
        {"RAZORPAY_KEY_ID": "test-key"},
        {"PAYMENT_RECONCILIATION_ENABLED": True},
    ],
)
def test_home_visit_demo_rejects_unsafe_configuration(overrides):
    with pytest.raises((ValueError, ValidationError)):
        Settings(_env_file=None, **home_demo_values(**overrides))


def test_missing_home_visit_demo_configuration_does_not_fall_back_to_normal_defaults():
    with pytest.raises((ValueError, ValidationError)):
        Settings(
            _env_file="C:\\path\\that\\does\\not\\exist\\.env",
            HOME_VISIT_DEMO_MODE=True,
            JWT_SECRET="h" * 40,
            JWT_REFRESH_SECRET="r" * 40,
        )


def test_normal_test_configuration_uses_dedicated_development_database():
    configured = Settings(
        _env_file=None,
        JWT_SECRET="n" * 40,
        JWT_REFRESH_SECRET="s" * 40,
    )

    assert configured.DATABASE_NAME == "physiocare_dev"
    assert configured.PORT == 8000
    assert configured.HOME_VISIT_DEMO_MODE is False


def test_lab_demo_configuration_remains_unchanged():
    configured = Settings(
        _env_file=None,
        MONGODB_URL=LAB_DEMO_MONGODB_URL,
        DATABASE_NAME=LAB_DEMO_DATABASE_NAME,
        LAB_DEMO_MODE=True,
        JWT_SECRET="l" * 40,
        JWT_REFRESH_SECRET="m" * 40,
        ENVIRONMENT="development",
        HOST="127.0.0.1",
        PORT=8001,
        RAZORPAY_MODE="disabled",
        RAZORPAY_KEY_ID="",
        RAZORPAY_KEY_SECRET="",
        RAZORPAY_WEBHOOK_SECRET="",
        PAYMENT_RECONCILIATION_ENABLED=False,
        LAB_REPORT_STORAGE_DIR=str(lab_demo_home() / "lab-reports"),
        LAB_REPORT_QUARANTINE_DIR=str(lab_demo_home() / "lab-report-quarantine"),
        CORS_ORIGINS=["http://127.0.0.1:5175"],
    )

    assert configured.LAB_DEMO_MODE is True
    assert configured.HOME_VISIT_DEMO_MODE is False
