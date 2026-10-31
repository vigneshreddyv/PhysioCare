import json
from typing import Any, Iterator, Optional, Tuple

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, SecretStr, model_validator

# Phase 4 Task 21 — secret redaction in Settings diagnostics.
# The Task 20 pytest failure report exposed the full Settings repr, which
# included the .env-loaded MongoDB connection-string credentials and the
# Razorpay credentials. These are the Settings fields whose VALUES must
# never appear in any diagnostic representation (repr, str, assertion-
# failure output, pretty printers, model dumps). Field names, environment
# variable names, defaults, and runtime behavior are all unchanged: the
# fields remain plain strings for runtime consumers (security.py,
# middleware/auth.py, auth_service.py, database.py, razorpay_client.py);
# only their REPRESENTATION is redacted.
# RAZORPAY_KEY_ID is deliberately NOT in this set: it is a public
# identifier by design (the frontend checkout needs it), unlike
# RAZORPAY_KEY_SECRET which is backend-only.
SECRET_SETTINGS_FIELDS = frozenset({
    "MONGODB_URL",           # contains embedded username/password credentials
    "JWT_SECRET",
    "JWT_REFRESH_SECRET",
    "RAZORPAY_KEY_SECRET",   # backend-only, must never be exposed
    "RAZORPAY_WEBHOOK_SECRET",
})

# Repr'd as SecretStr('**********') — pydantic's own redacted display.
_REDACTED_REPR = SecretStr("redacted")
_REDACTED_PLACEHOLDER = "**********"
_DEVELOPMENT_JWT_SECRET = "supersecretjwtsecretkeyshouldbechangedinproduction123!"
_DEVELOPMENT_REFRESH_SECRET = "supersecretjwtrefreshsecretkeyshouldbechangedinproduction123!"

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "physiocare"
    JWT_SECRET: str = "supersecretjwtsecretkeyshouldbechangedinproduction123!"
    JWT_REFRESH_SECRET: str = "supersecretjwtrefreshsecretkeyshouldbechangedinproduction123!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Phase 4, Task 20 — application logging.
    # Root-logger level for the centralized logging configuration
    # (app/core/logging_config.py). INFO is the baseline that makes the
    # reconciliation observability lines (Task 18) actually visible.
    # Recognized values: DEBUG, INFO, WARNING, ERROR, CRITICAL; an absent
    # or unrecognized value falls back to INFO (never DEBUG, never a
    # crash). This setting carries no secrets and is safe to log.
    LOG_LEVEL: str = "INFO"

    # Razorpay (payment gateway) configuration.
    # RAZORPAY_KEY_SECRET is BACKEND-ONLY: it must never be exposed to the
    # frontend, API responses, logs, or exception messages.
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    # Reserved for a later phase (webhook signature verification). Unused in Task 1.
    RAZORPAY_WEBHOOK_SECRET: str = ""
    # Explicit timeout (seconds) applied to every Razorpay API request.
    RAZORPAY_TIMEOUT_SECONDS: int = 30

    # Phase 4 Task 9 — stale pending-payment reconciliation.
    # Phase 4 Task 9 — stale pending-payment reconciliation.
    # NO product expiry duration has been approved by the product owner, so
    # automatic expiry is DISABLED BY DEFAULT and no default duration is
    # chosen here. The value is intentionally None (meaningless as a
    # duration); when the product owner defines the policy, set both:
    #   PAYMENT_PENDING_EXPIRY_MINUTES=<approved duration>
    #   PAYMENT_RECONCILIATION_ENABLED=true
    # Until then, no booking is ever expired automatically.
    #
    # When enabled (both values set), a pending_payment record younger than
    # this threshold is never considered stale, and reconciliation checks
    # Razorpay BEFORE any expiry decision (fail-closed: uncertainty keeps
    # the booking pending).
    PAYMENT_PENDING_EXPIRY_MINUTES: Optional[int] = None
    # Master switch for stale-payment expiry policy (Task 9). Default OFF:
    # the reconciliation service entry point stays invocable for explicit
    # future activation and its scan/reconcile logic runs, but while this is
    # false the background loop never starts and the atomic expiry
    # transitions are never invoked, so no booking can be expired.
    PAYMENT_RECONCILIATION_ENABLED: bool = False

    # Phase 4 Task 16 — refund reconciliation & recovery.
    # Master switch for the refund reconciliation background loop. Default
    # OFF: no automatic reconciliation policy has been approved by the
    # product owner, so the loop never starts by default and no Razorpay    # lookup is issued automatically. The batch entry point
    # (RefundReconciliationService.reconcile_refundable_refunds) stays
    # invocable as an internal callable regardless of this switch.
    REFUND_RECONCILIATION_ENABLED: bool = False

    # ------------------------------------------------------------------
    # Phase 4 Task 21 — redaction of secret-bearing values in diagnostics.
    #
    # Root cause of the Task 20 exposure: on an assertion failure pytest
    # reprs the live Settings object, and pydantic's default repr includes
    # every field value verbatim — including .env-loaded secrets.
    #
    # Pydantic v2 routes repr(), str(), __pretty__ (devtools) and pytest's
    # assertion diagnostics ALL through __repr_args__(), so overriding that
    # single hook redacts every representation path without touching field
    # types, environment-variable names, or any runtime consumer. Runtime
    # code continues to read plain string values directly (e.g.
    # jwt.encode(..., settings.JWT_SECRET)); only diagnostics are masked.
    # ------------------------------------------------------------------
    def __repr_args__(self) -> Iterator[Tuple[str, Any]]:
        """Redact secret field values in repr/str/diagnostic output."""
        for name, value in super().__repr_args__():
            if name in SECRET_SETTINGS_FIELDS:
                yield name, _REDACTED_REPR
            else:
                yield name, value

    def model_dump(self, **kwargs: Any) -> dict:
        """model_dump with secret values replaced by a fixed placeholder."""
        dumped = super().model_dump(**kwargs)
        for name in SECRET_SETTINGS_FIELDS:
            if name in dumped:
                dumped[name] = _REDACTED_PLACEHOLDER
        return dumped

    def model_dump_json(self, **kwargs: Any) -> str:
        """model_dump_json with secret values replaced by a fixed placeholder."""
        indent = kwargs.pop("indent", None)
        return json.dumps(self.model_dump(**kwargs), default=str, indent=indent)

    @model_validator(mode="after")
    def require_production_jwt_secrets(self):
        if self.JWT_SECRET == self.JWT_REFRESH_SECRET:
            raise ValueError("JWT_SECRET and JWT_REFRESH_SECRET must be different")

        if self.ENVIRONMENT.strip().casefold() in {"prod", "production"}:
            if (
                self.JWT_SECRET == _DEVELOPMENT_JWT_SECRET
                or self.JWT_REFRESH_SECRET == _DEVELOPMENT_REFRESH_SECRET
            ):
                raise ValueError("Production JWT secrets must be explicitly configured")
            if len(self.JWT_SECRET.encode("utf-8")) < 32 or len(self.JWT_REFRESH_SECRET.encode("utf-8")) < 32:
                raise ValueError("Production JWT secrets must be at least 32 bytes")

        return self

settings = Settings()
