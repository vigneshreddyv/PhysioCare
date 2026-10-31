from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime


class StageSchema(BaseModel):
    stage_id: str
    title: str
    description: str
    status: Literal["upcoming", "active", "completed"]
    progress: float = 0.0
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    focus_areas: List[str] = []


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
    created_at: datetime
    updated_at: datetime


class CarePlanCreate(BaseModel):
    patient_id: str
    title: str
    description: str
    current_stage: int = 1
    stages: List[StageSchema] = []
    goals: List[GoalSchema] = []
    recommendations: List[RecommendationSchema] = []
    start_date: datetime
    target_date: datetime
    status: Literal["active", "completed", "paused", "cancelled"] = "active"


class CarePlanUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    current_stage: Optional[int] = None
    stages: Optional[List[StageSchema]] = None
    goals: Optional[List[GoalSchema]] = None
    recommendations: Optional[List[RecommendationSchema]] = None
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    status: Optional[Literal["active", "completed", "paused", "cancelled"]] = None


class StageStatusUpdate(BaseModel):
    status: Literal["active", "completed"]


class GoalProgressUpdate(BaseModel):
    progress_value: float
    status: Literal["active", "achieved"]


class CarePlanHistoryResponse(BaseModel):
    action: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime


