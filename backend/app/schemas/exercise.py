from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, List, Optional, Literal
from datetime import datetime

ExerciseId = Annotated[str, Field(min_length=1, max_length=128)]
ExerciseTitle = Annotated[str, Field(min_length=1, max_length=200)]
ExerciseText = Annotated[str, Field(max_length=8000)]
ExerciseListText = Annotated[str, Field(min_length=1, max_length=2000)]
ExerciseLabel = Annotated[str, Field(min_length=1, max_length=200)]


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
    model_config = ConfigDict(extra="forbid")

    title: ExerciseTitle
    description: ExerciseText
    category: Literal["mobility", "posture", "strength", "stretching"]
    difficulty: str = Field(min_length=1, max_length=100)
    instructions: List[ExerciseListText] = Field(min_length=1, max_length=50)
    safety_precautions: List[ExerciseListText] = Field(default_factory=list, max_length=50)
    sets: int = Field(ge=1, le=1000)
    reps: int = Field(ge=1, le=10000)
    duration_seconds: int = Field(ge=0, le=86400)
    target_muscles: List[ExerciseLabel] = Field(default_factory=list, max_length=50)
    equipment: List[ExerciseLabel] = Field(default_factory=list, max_length=50)
    video_url: Optional[str] = Field(default=None, max_length=500)
    active: bool = True


class ExerciseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[ExerciseTitle] = None
    description: Optional[ExerciseText] = None
    category: Optional[Literal["mobility", "posture", "strength", "stretching"]] = None
    difficulty: Optional[str] = Field(default=None, min_length=1, max_length=100)
    instructions: Optional[List[ExerciseListText]] = Field(default=None, min_length=1, max_length=50)
    safety_precautions: Optional[List[ExerciseListText]] = Field(default=None, max_length=50)
    sets: Optional[int] = Field(default=None, ge=1, le=1000)
    reps: Optional[int] = Field(default=None, ge=1, le=10000)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    target_muscles: Optional[List[ExerciseLabel]] = Field(default=None, max_length=50)
    equipment: Optional[List[ExerciseLabel]] = Field(default=None, max_length=50)
    video_url: Optional[str] = Field(default=None, max_length=500)
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
    revision: int = 0
    exercise_title: Optional[str] = None
    care_plan_title: Optional[str] = None
    stage_title: Optional[str] = None


class PatientExerciseAssignmentDetail(BaseModel):
    id: str
    exercise_id: str
    title: str
    category: Literal["mobility", "posture", "strength", "stretching"]
    description: str
    instructions: List[str]
    safety_precautions: List[str]
    sets: int
    reps: int
    duration_seconds: int
    status: Literal["assigned", "in_progress", "completed", "cancelled"]
    revision: int = 0


class ExerciseAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=128)
    care_plan_id: str = Field(min_length=1, max_length=128)
    stage_id: ExerciseId
    exercise_id: str = Field(min_length=1, max_length=128)
    sets: int = Field(ge=1, le=1000)
    reps: int = Field(ge=1, le=10000)
    duration_seconds: int = Field(ge=0, le=86400)
    frequency: str = Field(min_length=1, max_length=200)


class ExerciseAssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    sets: Optional[int] = Field(default=None, ge=1, le=1000)
    reps: Optional[int] = Field(default=None, ge=1, le=10000)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    frequency: Optional[str] = Field(default=None, min_length=1, max_length=200)
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
    model_config = ConfigDict(extra="forbid")

    assignment_id: str = Field(min_length=1, max_length=128)
    expected_assignment_revision: int = Field(ge=0)
    completed_sets: int = Field(ge=0, le=1000)
    completed_reps: int = Field(ge=0, le=10000)
    duration_seconds: int = Field(ge=0, le=86400)
    completion_status: Literal["completed", "partial"] = "completed"
    notes: Optional[str] = Field(default=None, max_length=8000)

