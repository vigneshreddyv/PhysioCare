from typing import List, Optional
from beanie import PydanticObjectId
from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress


class ExerciseRepository:
    @staticmethod
    async def create_exercise(exercise: Exercise) -> Exercise:
        return await exercise.insert()

    @staticmethod
    async def get_exercise_by_id(id: str) -> Optional[Exercise]:
        try:
            return await Exercise.get(PydanticObjectId(id))
        except Exception:
            return None

    @staticmethod
    async def list_exercises(active_only: bool = False) -> List[Exercise]:
        if active_only:
            return await Exercise.find(Exercise.active == True).to_list()
        return await Exercise.find_all().to_list()

    @staticmethod
    async def create_assignment(assignment: ExerciseAssignment) -> ExerciseAssignment:
        return await assignment.insert()

    @staticmethod
    async def get_assignment_by_id(id: str) -> Optional[ExerciseAssignment]:
        try:
            return await ExerciseAssignment.get(PydanticObjectId(id))
        except Exception:
            return None

    @staticmethod
    async def list_assignments_by_patient(patient_id: str) -> List[ExerciseAssignment]:
        try:
            parsed = PydanticObjectId(patient_id)
            return await ExerciseAssignment.find(
                ExerciseAssignment.patient_id == parsed
            ).sort(-ExerciseAssignment.assigned_at).to_list()
        except Exception:
            return []

    @staticmethod
    async def list_assignments_by_care_plan(care_plan_id: str) -> List[ExerciseAssignment]:
        try:
            parsed = PydanticObjectId(care_plan_id)
            return await ExerciseAssignment.find(
                ExerciseAssignment.care_plan_id == parsed
            ).sort(-ExerciseAssignment.assigned_at).to_list()
        except Exception:
            return []

    @staticmethod
    async def create_progress(progress: ExerciseProgress) -> ExerciseProgress:
        return await progress.insert()

    @staticmethod
    async def list_progress_by_patient(patient_id: str) -> List[ExerciseProgress]:
        try:
            parsed = PydanticObjectId(patient_id)
            return await ExerciseProgress.find(
                ExerciseProgress.patient_id == parsed
            ).sort(-ExerciseProgress.completed_at).to_list()
        except Exception:
            return []

    @staticmethod
    async def list_progress_by_assignment(assignment_id: str) -> List[ExerciseProgress]:
        try:
            parsed = PydanticObjectId(assignment_id)
            return await ExerciseProgress.find(
                ExerciseProgress.assignment_id == parsed
            ).sort(-ExerciseProgress.completed_at).to_list()
        except Exception:
            return []

