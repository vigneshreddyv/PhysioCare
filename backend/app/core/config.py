from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field, model_validator
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "physiocare"
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
    LAB_REPORT_STORAGE_DIR: str = "uploads/lab-reports"
    LAB_REPORT_MAX_BYTES: int = Field(default=5 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @model_validator(mode="after")
    def validate_jwt_secrets(self):
        if self.JWT_SECRET == self.JWT_REFRESH_SECRET:
            raise ValueError("JWT access and refresh secrets must be different")
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
        clinic_start = datetime.strptime(self.DEMO_SCHEDULE_START, "%H:%M")
        home_start = datetime.strptime(self.DEMO_HOME_SCHEDULE_START, "%H:%M")
        offset_minutes = int((home_start - clinic_start).total_seconds() // 60)
        if offset_minutes % self.DEMO_SLOT_MINUTES != 0:
            raise ValueError("Home demo schedule must align to the shared clinic slot grid")
        self.DEMO_HOME_SERVICE_CITY = " ".join(self.DEMO_HOME_SERVICE_CITY.split())
        if not self.DEMO_HOME_SERVICE_CITY:
            raise ValueError("Demo home-service city is required")
        return self

    @property
    def cookie_secure(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

settings = Settings()
