from datetime import datetime
from typing import List, Optional, Literal
from beanie import Document, PydanticObjectId
from pydantic import Field

class Exercise(Document):
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "exercises"


class ExerciseAssignment(Document):
    patient_id: PydanticObjectId
    care_plan_id: PydanticObjectId
    stage_id: str
    exercise_id: PydanticObjectId
    sets: int
    reps: int
    duration_seconds: int
    frequency: str
    status: Literal["assigned", "in_progress", "completed", "cancelled"] = "assigned"
    assigned_by: PydanticObjectId
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "exercise_assignments"


class ExerciseProgress(Document):
    patient_id: PydanticObjectId
    assignment_id: PydanticObjectId
    exercise_id: PydanticObjectId
    care_plan_id: PydanticObjectId
    stage_id: str
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    completed_sets: int
    completed_reps: int
    duration_seconds: int
    completion_status: Literal["completed", "partial"] = "completed"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "exercise_progress"

