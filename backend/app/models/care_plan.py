from datetime import datetime
from typing import List, Optional, Literal

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field

from app.core.time import utc_now


class Stage(BaseModel):
    stage_id: str
    title: str
    description: str
    status: Literal["upcoming", "active", "completed"]
    progress: float = 0.0
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    focus_areas: List[str] = []


class Goal(BaseModel):
    goal_id: str
    title: str
    description: str
    target_value: float
    unit: str
    status: str
    progress_value: Optional[float] = None


class Recommendation(BaseModel):
    recommendation_id: str
    title: str
    description: str
    priority: str


class CarePlan(Document):
    patient_id: PydanticObjectId
    therapist_id: PydanticObjectId
    title: str
    description: str
    current_stage: int = 1
    stages: List[Stage] = []
    goals: List[Goal] = []
    recommendations: List[Recommendation] = []
    start_date: datetime
    target_date: datetime
    status: Literal["active", "completed", "paused", "cancelled"] = "active"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "care_plans"


class CarePlanHistory(Document):
    care_plan_id: PydanticObjectId
    patient_id: PydanticObjectId
    actor_user_id: PydanticObjectId
    action: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "care_plan_histories"
