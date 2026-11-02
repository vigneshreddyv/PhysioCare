from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, List, Optional, Literal
from datetime import datetime


CarePlanId = Annotated[str, Field(min_length=1, max_length=128)]
CarePlanTitle = Annotated[str, Field(min_length=1, max_length=200)]
CarePlanText = Annotated[str, Field(max_length=8000)]
CarePlanLabel = Annotated[str, Field(min_length=1, max_length=200)]


class StageSchema(BaseModel):
    stage_id: str
    title: str
    description: str
    status: Literal["upcoming", "active", "completed"]
    progress: float = 0.0
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    focus_areas: List[str] = Field(default_factory=list)


class GoalSchema(BaseModel):
    goal_id: str
    title: str
    description: str
    target_value: float
    unit: str
    status: str
    progress_value: Optional[float] = None


class RecommendationSchema(BaseModel):
    recommendation_id: str
    title: str
    description: str
    priority: str


class StageMutationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_id: CarePlanId
    title: CarePlanTitle
    description: CarePlanText
    status: Literal["upcoming", "active", "completed"]
    progress: float = 0.0
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    focus_areas: List[CarePlanLabel] = Field(default_factory=list, max_length=32)


class GoalMutationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_id: CarePlanId
    title: CarePlanTitle
    description: CarePlanText
    target_value: float
    unit: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=50)
    progress_value: Optional[float] = None


class RecommendationMutationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: CarePlanId
    title: CarePlanTitle
    description: CarePlanText
    priority: str = Field(min_length=1, max_length=50)


class CarePlanResponse(BaseModel):
    id: str
    patient_id: str
    therapist_id: str
    title: str
    description: str
    current_stage: int
    stages: List[StageSchema]
    goals: List[GoalSchema]
    recommendations: List[RecommendationSchema]
    start_date: datetime
    target_date: datetime
    status: Literal["active", "completed", "paused", "cancelled"]
    revision: int = 0
    created_at: datetime
    updated_at: datetime


class CarePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=128)
    title: CarePlanTitle
    description: CarePlanText
    current_stage: int = Field(default=1, ge=1, le=64)
    stages: List[StageMutationSchema] = Field(default_factory=list, max_length=64)
    goals: List[GoalMutationSchema] = Field(default_factory=list, max_length=128)
    recommendations: List[RecommendationMutationSchema] = Field(default_factory=list, max_length=128)
    start_date: datetime
    target_date: datetime
    status: Literal["active", "completed", "paused", "cancelled"] = "active"


class CarePlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    title: Optional[CarePlanTitle] = None
    description: Optional[CarePlanText] = None
    current_stage: Optional[int] = Field(default=None, ge=1, le=64)
    stages: Optional[List[StageMutationSchema]] = Field(default=None, max_length=64)
    goals: Optional[List[GoalMutationSchema]] = Field(default=None, max_length=128)
    recommendations: Optional[List[RecommendationMutationSchema]] = Field(default=None, max_length=128)
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    status: Optional[Literal["active", "completed", "paused", "cancelled"]] = None


class StageStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    status: Literal["active", "completed"]


class GoalProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    progress_value: float
    status: Literal["active", "achieved"]


class CarePlanHistoryResponse(BaseModel):
    action: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime


