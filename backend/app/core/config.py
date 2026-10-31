from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field, model_validator
from datetime import datetime
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


LAB_DEMO_DATABASE_NAME = "physiocare_lab_demo"
LAB_DEMO_MONGODB_URL = "mongodb://127.0.0.1:27018"
HOME_VISIT_DEMO_DATABASE_NAME = "physiocare_home_visit_demo"
HOME_VISIT_DEMO_MONGODB_URL = "mongodb://127.0.0.1:27019"
HOME_VISIT_DEMO_BACKEND_PORT = 8002
HOME_VISIT_DEMO_FRONTEND_ORIGIN = "http://127.0.0.1:5176"


def lab_demo_home() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "PhysioCareLabDemo"


def is_lab_demo_environment_file(value: str | os.PathLike[str] | None) -> bool:
    if not value:
        return False
    try:
        return Path(value).expanduser().resolve() == (lab_demo_home() / ".env").resolve()
    except OSError:
        return False


def home_visit_demo_home() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "PhysioCareHomeVisitDemo"


def is_home_visit_demo_environment_file(value: str | os.PathLike[str] | None) -> bool:
    if not value:
        return False
    try:
        return Path(value).expanduser().resolve() == (home_visit_demo_home() / ".env").resolve()
    except OSError:
        return False


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )
    
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "physiocare"
    LAB_DEMO_MODE: bool = False
    HOME_VISIT_DEMO_MODE: bool = False
    JWT_SECRET: str = Field(min_length=32)
    JWT_REFRESH_SECRET: str = Field(min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CLINIC_TIMEZONE: str = "Asia/Kolkata"
    BOOKING_HORIZON_DAYS: int = Field(default=30, ge=1, le=365)
    DEMO_SCHEDULE_START: str = "09:00"
    DEMO_SCHEDULE_END: str = "18:00"
    DEMO_SLOT_MINUTES: int = Field(default=30, ge=5, le=240)
    DEMO_HOME_VISIT_REQUESTS_ENABLED: bool = True
    DEMO_HOME_SERVICE_CITY: str = "Nellore"
    DEMO_HOME_SCHEDULE_START: str = "09:00"
    DEMO_HOME_SCHEDULE_END: str = "18:00"
    DEMO_HOME_SLOT_MINUTES: int = Field(default=30, ge=5, le=240)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAY_MODE: str = "disabled"
    APPOINTMENT_BILLING_CURRENCY: str = ""
    PAYMENT_RECONCILIATION_ENABLED: bool = True
    PAYMENT_RECONCILIATION_INTERVAL_SECONDS: int = Field(default=30, ge=5, le=3600)
    PAYMENT_RECONCILIATION_BATCH_SIZE: int = Field(default=50, ge=1, le=500)
    PAYMENT_RECONCILIATION_LEASE_SECONDS: int = Field(default=120, ge=15, le=3600)
    LAB_REPORT_STORAGE_DIR: str = "uploads/lab-reports"
    LAB_REPORT_MAX_BYTES: int = Field(default=5 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    CLINICAL_REPORT_STORAGE_DIR: str = "uploads/clinical-reports"
    CLINICAL_REPORT_MAX_BYTES: int = Field(
        default=5 * 1024 * 1024,
        ge=1024,
        le=20 * 1024 * 1024,
    )
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @model_validator(mode="after")
    def validate_jwt_secrets(self):
        if self.JWT_SECRET == self.JWT_REFRESH_SECRET:
            raise ValueError("JWT access and refresh secrets must be different")
        demo_config_selected = is_lab_demo_environment_file(
            os.environ.get("PHYSIOCARE_ENV_FILE")
        )
        home_visit_demo_config_selected = is_home_visit_demo_environment_file(
            os.environ.get("PHYSIOCARE_HOME_VISIT_ENV_FILE")
        )
        if demo_config_selected and not self.LAB_DEMO_MODE:
            raise ValueError("The isolated laboratory demo configuration requires LAB_DEMO_MODE=true")
        if home_visit_demo_config_selected and not self.HOME_VISIT_DEMO_MODE:
            raise ValueError("The isolated home-visit demo configuration requires HOME_VISIT_DEMO_MODE=true")
        if self.LAB_DEMO_MODE or demo_config_selected:
            self.validate_lab_demo_isolation()
        if self.HOME_VISIT_DEMO_MODE or home_visit_demo_config_selected:
            self.validate_home_visit_demo_isolation()
        if not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS:
            raise ValueError("Credentialed CORS requires explicit origins")
        try:
            ZoneInfo(self.CLINIC_TIMEZONE)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("CLINIC_TIMEZONE must be a valid IANA timezone") from exc
        schedules = (
            ("clinic", self.DEMO_SCHEDULE_START, self.DEMO_SCHEDULE_END, self.DEMO_SLOT_MINUTES),
            ("home-visit", self.DEMO_HOME_SCHEDULE_START, self.DEMO_HOME_SCHEDULE_END, self.DEMO_HOME_SLOT_MINUTES),
        )
        for label, start_value, end_value, slot_minutes in schedules:
            try:
                start = datetime.strptime(start_value, "%H:%M")
                end = datetime.strptime(end_value, "%H:%M")
            except ValueError as exc:
                raise ValueError(f"Demo {label} schedule times must use 24-hour HH:MM format") from exc
            total_minutes = int((end - start).total_seconds() // 60)
            if total_minutes <= 0 or total_minutes % slot_minutes != 0:
                raise ValueError(f"Demo {label} schedule window must be positive and divide evenly into slot minutes")
        if self.DEMO_HOME_SLOT_MINUTES != self.DEMO_SLOT_MINUTES:
            raise ValueError("Clinic and home demo slots must use the same duration to share atomic clinician capacity")
        if self.PAYMENT_RECONCILIATION_LEASE_SECONDS < self.PAYMENT_RECONCILIATION_INTERVAL_SECONDS * 2:
            raise ValueError("Payment reconciliation lease must be at least twice the poll interval")
        clinic_start = datetime.strptime(self.DEMO_SCHEDULE_START, "%H:%M")
        home_start = datetime.strptime(self.DEMO_HOME_SCHEDULE_START, "%H:%M")
        offset_minutes = int((home_start - clinic_start).total_seconds() // 60)
        if offset_minutes % self.DEMO_SLOT_MINUTES != 0:
            raise ValueError("Home demo schedule must align to the shared clinic slot grid")
        self.DEMO_HOME_SERVICE_CITY = " ".join(self.DEMO_HOME_SERVICE_CITY.split())
        if not self.DEMO_HOME_SERVICE_CITY:
            raise ValueError("Demo home-service city is required")
        return self

    def validate_lab_demo_isolation(self) -> None:
        if not self.LAB_DEMO_MODE:
            return
        if self.DATABASE_NAME != LAB_DEMO_DATABASE_NAME:
            raise ValueError("Laboratory demo mode may only use the dedicated demo database")
        if self.MONGODB_URL != LAB_DEMO_MONGODB_URL:
            raise ValueError("Laboratory demo mode requires the dedicated loopback MongoDB listener")
        if self.HOST != "127.0.0.1" or self.PORT != 8001:
            raise ValueError("Laboratory demo mode must bind only to 127.0.0.1:8001")
        if self.ENVIRONMENT.strip().lower() != "development":
            raise ValueError("Laboratory demo mode is restricted to development")
        if self.RAZORPAY_MODE.strip().lower() != "disabled":
            raise ValueError("Payments must be disabled in the laboratory demo environment")
        if self.RAZORPAY_KEY_ID or self.RAZORPAY_KEY_SECRET or self.RAZORPAY_WEBHOOK_SECRET:
            raise ValueError("Payment credentials are not permitted in the laboratory demo environment")
        if self.PAYMENT_RECONCILIATION_ENABLED:
            raise ValueError("Payment reconciliation must be disabled in the laboratory demo environment")
        if self.CORS_ORIGINS != ["http://127.0.0.1:5175"]:
            raise ValueError("Laboratory demo mode must allow only its dedicated frontend origin")

        expected_storage = (lab_demo_home() / "lab-reports").resolve()
        configured_storage = Path(self.LAB_REPORT_STORAGE_DIR).expanduser()
        if (
            not configured_storage.is_absolute()
            or configured_storage.is_symlink()
            or configured_storage.resolve() != expected_storage
        ):
            raise ValueError("Laboratory demo reports must use the dedicated private storage directory")
        demo_home = lab_demo_home()
        if demo_home.is_symlink() or expected_storage.is_symlink():
            raise ValueError("Laboratory demo configuration cannot use a symbolic-link storage path")

    def validate_home_visit_demo_isolation(self) -> None:
        if not self.HOME_VISIT_DEMO_MODE:
            return
        if self.DATABASE_NAME != HOME_VISIT_DEMO_DATABASE_NAME:
            raise ValueError("Home-visit demo mode may only use the dedicated demo database")
        if self.MONGODB_URL != HOME_VISIT_DEMO_MONGODB_URL:
            raise ValueError("Home-visit demo mode requires the dedicated loopback MongoDB listener")
        if self.HOST != "127.0.0.1" or self.PORT != HOME_VISIT_DEMO_BACKEND_PORT:
            raise ValueError("Home-visit demo mode must bind only to 127.0.0.1:8002")
        if self.ENVIRONMENT.strip().lower() != "development":
            raise ValueError("Home-visit demo mode is restricted to development")
        if self.RAZORPAY_MODE.strip().lower() != "disabled":
            raise ValueError("Payments must be disabled in the home-visit demo environment")
        if self.RAZORPAY_KEY_ID or self.RAZORPAY_KEY_SECRET or self.RAZORPAY_WEBHOOK_SECRET:
            raise ValueError("Payment credentials are not permitted in the home-visit demo environment")
        if self.PAYMENT_RECONCILIATION_ENABLED:
            raise ValueError("Payment reconciliation must be disabled in the home-visit demo environment")
        if self.CORS_ORIGINS != [HOME_VISIT_DEMO_FRONTEND_ORIGIN]:
            raise ValueError("Home-visit demo mode must allow only its dedicated frontend origin")

    @property
    def cookie_secure(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

settings = Settings(
    _env_file=(
        os.environ.get("PHYSIOCARE_HOME_VISIT_ENV_FILE")
        or os.environ.get("PHYSIOCARE_ENV_FILE", ".env")
    )
)
