from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional


class DoctorProfileFields(BaseModel):
    specialization: str
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    qualifications: Optional[str] = None
    years_experience: Optional[int] = None
    specialties: List[str] = Field(default_factory=list)
    linkedin_url: Optional[str] = None
    website_url: Optional[str] = None
    accepts_home_visits: bool = True


class PublicDoctorOut(DoctorProfileFields):
    id: str
    full_name: str


class DoctorOut(DoctorProfileFields):
    id: str
    full_name: str
    email: str
    is_active_today: bool


class DoctorProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    specialization: Optional[str] = Field(default=None, min_length=2, max_length=120)
    profile_image: Optional[str] = Field(default=None, max_length=500)
    bio: Optional[str] = Field(default=None, max_length=1200)
    qualifications: Optional[str] = Field(default=None, max_length=300)
    years_experience: Optional[int] = Field(default=None, ge=0, le=80)
    specialties: Optional[List[str]] = Field(default=None, max_length=12)
    linkedin_url: Optional[str] = Field(default=None, max_length=500)
    website_url: Optional[str] = Field(default=None, max_length=500)
    accepts_home_visits: Optional[bool] = None

    @field_validator("full_name", "specialization")
    @classmethod
    def normalize_required_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Value must contain at least 2 characters")
        return normalized

    @field_validator("profile_image", "linkedin_url", "website_url")
    @classmethod
    def validate_optional_url(cls, value: Optional[str], info) -> Optional[str]:
        if value is None or not value.strip():
            return None
        parsed = AnyHttpUrl(value.strip())
        host = (parsed.host or "").lower()
        if info.field_name == "linkedin_url" and host not in {"linkedin.com", "www.linkedin.com"}:
            raise ValueError("LinkedIn URL must use linkedin.com")
        return str(parsed)

    @field_validator("bio", "qualifications")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("specialties")
    @classmethod
    def normalize_specialties(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        normalized = []
        for item in value:
            clean = " ".join(item.split())
            if clean and clean not in normalized:
                normalized.append(clean)
        if any(len(item) > 80 for item in normalized):
            raise ValueError("Each specialty must be 80 characters or fewer")
        return normalized
