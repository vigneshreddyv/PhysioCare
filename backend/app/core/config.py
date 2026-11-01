import json
from typing import Any, Iterator, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field, SecretStr, model_validator
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
STAGING_INSTANCE_ID = "physiocare-isolated-staging"
STAGING_DATABASE_ID = "physiocare_staging"
DEVELOPMENT_DATABASE_NAME = "physiocare_dev"


# These settings contain credentials or credential material. Keep their
# runtime types as strings for existing consumers, but never expose their
# values through Settings diagnostics or serialization.
SECRET_SETTINGS_FIELDS = frozenset(
    {
        "MONGODB_URL",
        "JWT_SECRET",
        "JWT_REFRESH_SECRET",
        "RAZORPAY_KEY_SECRET",
        "RAZORPAY_WEBHOOK_SECRET",
    }
)
_REDACTED_REPR = SecretStr("redacted")
_REDACTED_PLACEHOLDER = "**********"


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
    AUTH_RATE_LIMIT_ENABLED: bool = True
    AUTH_LOGIN_IP_LIMIT: int = Field(default=30, ge=1, le=10000)
    AUTH_LOGIN_FAILURE_LIMIT: int = Field(default=5, ge=1, le=1000)
    AUTH_LOGIN_WINDOW_SECONDS: int = Field(default=300, ge=1, le=86400)
    AUTH_REGISTRATION_LIMIT: int = Field(default=5, ge=1, le=1000)
    AUTH_REGISTRATION_WINDOW_SECONDS: int = Field(default=3600, ge=1, le=86400)
    AUTH_REFRESH_IP_LIMIT: int = Field(default=120, ge=1, le=10000)
    AUTH_REFRESH_LIMIT: int = Field(default=30, ge=1, le=10000)
    AUTH_REFRESH_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)
    TRUSTED_PROXY_NETWORKS: list[str] = []
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    PHYSIOCARE_LOCAL_DEV: bool = False
    STAGING_INSTANCE_ID: str = ""
    STAGING_DATABASE_HOST: str = ""
    STAGING_DATABASE_NAME: str = ""
    STAGING_STORAGE_ROOT: str = ""
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
    LAB_REPORT_QUARANTINE_DIR: str = "uploads/lab-report-quarantine"
    LAB_REPORT_MAX_BYTES: int = Field(default=5 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    CLINICAL_REPORT_STORAGE_DIR: str = "uploads/clinical-reports"
    CLINICAL_REPORT_QUARANTINE_DIR: str = "uploads/clinical-report-quarantine"
    CLINICAL_REPORT_MAX_BYTES: int = Field(
        default=5 * 1024 * 1024,
        ge=1024,
        le=20 * 1024 * 1024,
    )
    PDF_SCAN_TIMEOUT_SECONDS: float = Field(default=30.0, ge=0.1, le=300.0)
    PDF_SCANNER_MODE: Literal["disabled", "clamav_unix"] = "disabled"
    PDF_SCANNER_SOCKET: str = ""
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    def __repr_args__(self) -> Iterator[tuple[str, Any]]:
        """Mask credential-bearing settings in repr/str diagnostics."""
        for name, value in super().__repr_args__():
            yield name, _REDACTED_REPR if name in SECRET_SETTINGS_FIELDS else value

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Return a diagnostic-safe settings mapping."""
        dumped = super().model_dump(**kwargs)
        for name in SECRET_SETTINGS_FIELDS:
            if name in dumped:
                dumped[name] = _REDACTED_PLACEHOLDER
        return dumped

    def model_dump_json(self, **kwargs: Any) -> str:
        """Return diagnostic-safe JSON without serializing credential values."""
        indent = kwargs.pop("indent", None)
        return json.dumps(self.model_dump(**kwargs), default=str, indent=indent)

    @model_validator(mode="after")
    def validate_jwt_secrets(self):
        if self.JWT_SECRET == self.JWT_REFRESH_SECRET:
            raise ValueError("JWT access and refresh secrets must be different")
        if self.PHYSIOCARE_LOCAL_DEV and self.ENVIRONMENT != "development":
            raise ValueError("Local development identity cannot select another environment")
        if (
            self.ENVIRONMENT == "development"
            and os.environ.get("PHYSIOCARE_ENV_FILE")
            and os.environ.get("PHYSIOCARE_HOME_VISIT_ENV_FILE")
        ):
            raise ValueError("Development cannot select two environment files")
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
        if self.ENVIRONMENT == "development" and not (
            self.LAB_DEMO_MODE or self.HOME_VISIT_DEMO_MODE
        ):
            self.validate_development_isolation()
        if self.PDF_SCANNER_MODE == "clamav_unix":
            socket_path = Path(self.PDF_SCANNER_SOCKET)
            if not socket_path.is_absolute() or socket_path.is_symlink():
                raise ValueError("ClamAV requires an absolute non-symlinked Unix socket path")
        if self.ENVIRONMENT == "staging":
            self.validate_staging_isolation()
        if not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS:
            raise ValueError("Credentialed CORS requires explicit origins")
        import ipaddress
        try:
            for network in self.TRUSTED_PROXY_NETWORKS:
                ipaddress.ip_network(network, strict=False)
        except ValueError as exc:
            raise ValueError("TRUSTED_PROXY_NETWORKS must contain valid IP networks") from exc
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

    def validate_runtime_startup(self) -> None:
        """Recheck environment isolation before any external connection starts."""
        if self.PHYSIOCARE_LOCAL_DEV and self.ENVIRONMENT != "development":
            raise ValueError("Local development identity cannot select another environment")
        if self.ENVIRONMENT == "staging":
            self.validate_staging_isolation()
        if self.ENVIRONMENT == "development" and not (
            self.LAB_DEMO_MODE or self.HOME_VISIT_DEMO_MODE
        ):
            self.validate_development_isolation()
        self.validate_lab_demo_isolation()
        self.validate_home_visit_demo_isolation()

    def development_mongodb_url(self) -> str:
        """Return a canonical loopback target, avoiding localhost name resolution."""
        if self.DATABASE_NAME != DEVELOPMENT_DATABASE_NAME:
            raise ValueError("Development requires the dedicated physiocare_dev database")
        try:
            parsed = urlsplit(self.MONGODB_URL)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            raise ValueError("Development MongoDB URL is invalid") from None
        if (
            parsed.scheme != "mongodb"
            or hostname not in {"127.0.0.1", "localhost", "::1"}
            or port is None
            or port < 1
            or parsed.netloc not in {
                f"127.0.0.1:{port}",
                f"localhost:{port}",
                f"[::1]:{port}",
            }
            or parsed.path != f"/{DEVELOPMENT_DATABASE_NAME}"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Development MongoDB URL must use one loopback host, an explicit port, "
                "and the physiocare_dev database without options"
            )
        pinned_host = "[::1]" if hostname == "::1" else "127.0.0.1"
        return f"mongodb://{pinned_host}:{port}/{DEVELOPMENT_DATABASE_NAME}"

    def validate_development_isolation(self) -> None:
        """Guard ordinary local development; dedicated demo modes have their own guards."""
        if os.environ.get("PHYSIOCARE_ENV_FILE") or os.environ.get(
            "PHYSIOCARE_HOME_VISIT_ENV_FILE"
        ):
            raise ValueError("Ordinary development cannot use an environment-file override")
        self.development_mongodb_url()
        if (
            self.RAZORPAY_MODE.casefold() != "disabled"
            or self.RAZORPAY_KEY_ID
            or self.RAZORPAY_KEY_SECRET
            or self.RAZORPAY_WEBHOOK_SECRET
            or self.PAYMENT_RECONCILIATION_ENABLED
        ):
            raise ValueError("Development payments and reconciliation must be disabled")
        if self.PDF_SCANNER_MODE != "disabled" or self.PDF_SCANNER_SOCKET:
            raise ValueError("Development PDF scanning requires separate approval")
        if not self.AUTH_RATE_LIMIT_ENABLED or self.TRUSTED_PROXY_NETWORKS:
            raise ValueError("Development requires throttling and no trusted proxy")

    def validate_staging_isolation(self) -> None:
        if self.STAGING_INSTANCE_ID != STAGING_INSTANCE_ID:
            raise ValueError("Staging requires the approved isolated deployment identity")
        if not self.AUTH_RATE_LIMIT_ENABLED:
            raise ValueError("Authentication rate limiting must be enabled in staging")
        if not self.TRUSTED_PROXY_NETWORKS:
            raise ValueError("Staging requires explicit trusted proxy networks")

        if (
            self.STAGING_DATABASE_NAME != STAGING_DATABASE_ID
            or self.DATABASE_NAME != STAGING_DATABASE_ID
        ):
            raise ValueError("Staging requires its approved dedicated database identity")
        if not self.STAGING_DATABASE_HOST:
            raise ValueError("Staging requires an approved database host identity")
        try:
            database_url = urlsplit(self.MONGODB_URL)
            database_path = database_url.path.lstrip("/").split("/", 1)[0]
            database_host = database_url.hostname or ""
        except ValueError as exc:
            raise ValueError("Staging database configuration is invalid") from exc
        if database_url.scheme not in {"mongodb", "mongodb+srv"}:
            raise ValueError("Staging database configuration must use MongoDB")
        if database_host.casefold() != self.STAGING_DATABASE_HOST.casefold():
            raise ValueError("Staging database host does not match the approved identity")
        if database_host.casefold() in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Staging database must use its dedicated non-local host")
        if database_path != self.DATABASE_NAME:
            raise ValueError("Staging database URL must select the approved database")
        if not database_url.username or not database_url.password:
            raise ValueError("Staging database credentials must be supplied securely")
        if any(marker in database_host.casefold() for marker in ("prod", "production")):
            raise ValueError("A production database host is not permitted in staging")

        try:
            uri_options = parse_qsl(
                database_url.query,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=64,
            )
        except ValueError as exc:
            raise ValueError("Staging MongoDB TLS configuration is invalid") from exc
        tls_option_names = {
            "tls", "ssl", "tlsinsecure", "sslinsecure",
            "tlsallowinvalidcertificates", "sslallowinvalidcertificates",
            "tlsallowinvalidhostnames", "sslallowinvalidhostnames",
            "ssl_cert_reqs", "ssl_match_hostname",
        }
        tls_options = {}
        for name, value in uri_options:
            normalized = name.casefold()
            if normalized in tls_option_names:
                if normalized in tls_options:
                    raise ValueError("Staging MongoDB TLS options must not be repeated")
                tls_options[normalized] = value
        enabled = [name for name in ("tls", "ssl") if name in tls_options]
        if len(enabled) != 1 or tls_options[enabled[0]] != "true":
            raise ValueError("Staging MongoDB requires explicit TLS")
        if any(
            value != "false"
            for name, value in tls_options.items()
            if name not in {"tls", "ssl", "ssl_cert_reqs", "ssl_match_hostname"}
        ) or any(name in tls_options for name in ("ssl_cert_reqs", "ssl_match_hostname")):
            raise ValueError("Staging MongoDB certificate verification cannot be disabled")

        if not self.CORS_ORIGINS:
            raise ValueError("Staging requires an explicit HTTPS CORS origin")
        for origin in self.CORS_ORIGINS:
            parsed_origin = urlsplit(origin)
            if (
                parsed_origin.scheme != "https"
                or not parsed_origin.hostname
                or parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}
                or parsed_origin.path not in {"", "/"}
                or parsed_origin.query
                or parsed_origin.fragment
            ):
                raise ValueError("Staging CORS origins must be exact HTTPS origins")

        storage_root = Path(self.STAGING_STORAGE_ROOT).expanduser()
        if not self.STAGING_STORAGE_ROOT or not storage_root.is_absolute() or storage_root.is_symlink():
            raise ValueError("Staging requires an absolute private storage root")
        resolved_root = storage_root.resolve()
        configured_roots = []
        for value in (
            self.LAB_REPORT_STORAGE_DIR,
            self.LAB_REPORT_QUARANTINE_DIR,
            self.CLINICAL_REPORT_STORAGE_DIR,
            self.CLINICAL_REPORT_QUARANTINE_DIR,
        ):
            configured = Path(value).expanduser()
            if not configured.is_absolute() or configured.is_symlink():
                raise ValueError("Staging report storage paths must be absolute and non-symlinked")
            resolved = configured.resolve()
            if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
                raise ValueError("Staging report storage must remain under its dedicated root")
            configured_roots.append(resolved)
        if len(set(configured_roots)) != len(configured_roots):
            raise ValueError("Staging report storage and quarantine paths must be separate")
        for candidate in configured_roots:
            if any(
                candidate != other and candidate.is_relative_to(other)
                for other in configured_roots
            ):
                raise ValueError("Staging report storage paths must not overlap")

        if (
            self.RAZORPAY_MODE.casefold() != "disabled"
            or self.RAZORPAY_KEY_ID
            or self.RAZORPAY_KEY_SECRET
            or self.RAZORPAY_WEBHOOK_SECRET
            or self.APPOINTMENT_BILLING_CURRENCY
            or self.PAYMENT_RECONCILIATION_ENABLED
        ):
            raise ValueError("Payments and reconciliation must remain disabled in staging")

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
        expected_quarantine = (lab_demo_home() / "lab-report-quarantine").resolve()
        configured_storage = Path(self.LAB_REPORT_STORAGE_DIR).expanduser()
        configured_quarantine = Path(self.LAB_REPORT_QUARANTINE_DIR).expanduser()
        if (
            not configured_storage.is_absolute()
            or configured_storage.is_symlink()
            or configured_storage.resolve() != expected_storage
        ):
            raise ValueError("Laboratory demo reports must use the dedicated private storage directory")
        if (
            not configured_quarantine.is_absolute()
            or configured_quarantine.is_symlink()
            or configured_quarantine.resolve() != expected_quarantine
        ):
            raise ValueError("Laboratory demo quarantine must use the dedicated private storage directory")
        demo_home = lab_demo_home()
        if (
            demo_home.is_symlink()
            or expected_storage.is_symlink()
            or expected_quarantine.is_symlink()
        ):
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
        return self.ENVIRONMENT.strip().lower() in {"staging", "production"}

settings = Settings(
    _env_file=(
        os.environ.get("PHYSIOCARE_HOME_VISIT_ENV_FILE")
        or os.environ.get("PHYSIOCARE_ENV_FILE", ".env")
    )
)
