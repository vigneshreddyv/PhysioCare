from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class ExerciseResponse(BaseModel):
    id: str
    title: str
    description: str
    category: Literal["mobility", "posture", "strength", "stretching"]
    difficulty: str
    instructions: List[str]
    safety_precautions: List[str] = []
    sets: int
    reps: int
    duration_seconds: int
    target_muscles: List[str] = []
    equipment: List[str] = []
    video_url: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime


class ExerciseCreate(BaseModel):
    title: str
    description: str
    category: Literal["mobility", "posture", "strength", "stretching"]
    difficulty: str
    instructions: List[str]
    safety_precautions: List[str] = []
    sets: int
    reps: int
    duration_seconds: int
    target_muscles: List[str] = []
    equipment: List[str] = []
    video_url: Optional[str] = None
    active: bool = True


class ExerciseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[Literal["mobility", "posture", "strength", "stretching"]] = None
    difficulty: Optional[str] = None
    instructions: Optional[List[str]] = None
    safety_precautions: Optional[List[str]] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    duration_seconds: Optional[int] = None
    target_muscles: Optional[List[str]] = None
    equipment: Optional[List[str]] = None
    video_url: Optional[str] = None
    active: Optional[bool] = None


class ExerciseAssignmentResponse(BaseModel):
    id: str
    patient_id: str
    care_plan_id: str
    stage_id: str
    exercise_id: str
    sets: int
    reps: int
    duration_seconds: int
    frequency: str
    status: Literal["assigned", "in_progress", "completed", "cancelled"]
    assigned_by: str
    assigned_at: datetime
    updated_at: datetime


class ExerciseAssignmentCreate(BaseModel):
    patient_id: str
    care_plan_id: str
    stage_id: str
    exercise_id: str
    sets: int
    reps: int
    duration_seconds: int
    frequency: str


class ExerciseAssignmentUpdate(BaseModel):
    sets: Optional[int] = None
    reps: Optional[int] = None
    duration_seconds: Optional[int] = None
    frequency: Optional[str] = None
    status: Optional[Literal["assigned", "in_progress", "completed", "cancelled"]] = None


class ExerciseProgressResponse(BaseModel):
    id: str
    patient_id: str
    assignment_id: str
    exercise_id: str
    care_plan_id: str
    stage_id: str
    completed_at: datetime
    completed_sets: int
    completed_reps: int
    duration_seconds: int
    completion_status: Literal["completed", "partial"]
    notes: Optional[str] = None
    created_at: datetime


class ExerciseProgressCreate(BaseModel):
    assignment_id: str
    completed_sets: int
    completed_reps: int
    duration_seconds: int
    completion_status: Literal["completed", "partial"] = "completed"
    notes: Optional[str] = None

