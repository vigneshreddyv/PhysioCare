from typing import List, Optional
import re
from beanie import PydanticObjectId
from pymongo import ReturnDocument
from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress
from app.models.care_plan import CarePlan
from app.core.pagination import PageWindow
from app.core.time import utc_now


class ExerciseAssignmentMutationConflict(Exception):
    """The assignment changed after the caller loaded it."""


class ExerciseRepository:
    @staticmethod
    def _assignment_revision_filter(expected_revision: int) -> dict:
        if expected_revision == 0:
            return {"$or": [{"revision": 0}, {"revision": {"$exists": False}}]}
        return {"revision": expected_revision}

    @staticmethod
    async def update_assignment_if_revision(
        assignment_id: str,
        *,
        patient_id,
        expected_revision: int,
        set_fields: dict,
    ) -> ExerciseAssignment:
        row = await ExerciseAssignment.get_pymongo_collection().find_one_and_update(
            {
                "_id": PydanticObjectId(assignment_id),
                "patient_id": patient_id,
                **ExerciseRepository._assignment_revision_filter(expected_revision),
            },
            {"$set": set_fields, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if row is None:
            raise ExerciseAssignmentMutationConflict
        return ExerciseAssignment.model_validate(row)

    @staticmethod
    async def create_progress_with_assignment_transition(
        progress: ExerciseProgress,
        *,
        assignment_id: str,
        patient_id,
        expected_revision: int,
        expected_status: str,
        next_status: str,
    ) -> ExerciseProgress:
        """Atomically claim one assignment revision and insert one progress event."""
        client = ExerciseAssignment.get_pymongo_collection().database.client
        async with client.start_session() as session:
            async def create_in_transaction(active_session):
                row = await ExerciseAssignment.get_pymongo_collection().find_one_and_update(
                    {
                        "_id": PydanticObjectId(assignment_id),
                        "patient_id": patient_id,
                        "status": expected_status,
                        **ExerciseRepository._assignment_revision_filter(expected_revision),
                    },
                    {
                        "$set": {"status": next_status, "updated_at": utc_now()},
                        "$inc": {"revision": 1},
                    },
                    return_document=ReturnDocument.AFTER,
                    session=active_session,
                )
                if row is None:
                    raise ExerciseAssignmentMutationConflict
                return await progress.insert(session=active_session)

            return await session.with_transaction(create_in_transaction)

    @staticmethod
    async def assignment_labels(assignments: list[ExerciseAssignment]) -> tuple[dict, dict]:
        if not assignments:
            return {}, {}
        exercise_ids = list({assignment.exercise_id for assignment in assignments})
        plan_ids = list({assignment.care_plan_id for assignment in assignments})
        exercise_rows = await Exercise.get_pymongo_collection().find(
            {"_id": {"$in": exercise_ids}}, {"title": 1},
        ).to_list(length=len(exercise_ids))
        plan_rows = await CarePlan.get_pymongo_collection().find(
            {"_id": {"$in": plan_ids}}, {"title": 1, "stages.stage_id": 1, "stages.title": 1},
        ).to_list(length=len(plan_ids))
        return ({row["_id"]: row.get("title") for row in exercise_rows},
                {row["_id"]: row for row in plan_rows})
    @staticmethod
    async def aggregate_care_plan_stage_counts(patient_id: str, care_plan_id: str) -> list[dict]:
        return await ExerciseAssignment.get_pymongo_collection().aggregate([
            {"$match": {
                "patient_id": PydanticObjectId(patient_id),
                "care_plan_id": PydanticObjectId(care_plan_id),
            }},
            {"$group": {
                "_id": "$stage_id",
                "prescribed": {"$sum": 1},
                "completed": {"$sum": {
                    "$cond": [{"$eq": ["$status", "completed"]}, 1, 0],
                }},
            }},
            {"$project": {"_id": 0, "stage_id": "$_id", "prescribed": 1, "completed": 1}},
        ]).to_list(length=None)

    @staticmethod
    async def aggregate_assignment_stats(patient_id: str) -> dict:
        rows = await ExerciseAssignment.get_pymongo_collection().aggregate([
            {"$match": {
                "patient_id": PydanticObjectId(patient_id),
                "status": {"$ne": "cancelled"},
            }},
            {"$sort": {"assigned_at": -1, "_id": -1}},
            {"$facet": {
                "summary": [{"$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                }}],
                "stages": [
                    {"$group": {
                        "_id": "$stage_id",
                        "assigned_exercise_count": {"$sum": 1},
                        "latest_assignment": {"$first": "$assigned_at"},
                    }},
                    {"$sort": {"latest_assignment": -1, "_id": 1}},
                ],
                "targets": [{"$group": {
                    "_id": "$exercise_id",
                    "sets": {"$first": "$sets"},
                    "reps": {"$first": "$reps"},
                }}],
            }},
        ]).to_list(length=1)
        return rows[0] if rows else {}

    @staticmethod
    async def aggregate_progress_stats(patient_id: str, start_of_week, next_day) -> dict:
        patient_object_id = PydanticObjectId(patient_id)
        completed_count = {"$sum": {"$cond": [{"$eq": ["$completion_status", "completed"]}, 1, 0]}}
        partial_count = {"$sum": {"$cond": [{"$eq": ["$completion_status", "partial"]}, 1, 0]}}
        rows = await ExerciseProgress.get_pymongo_collection().aggregate([
            {"$match": {"patient_id": patient_object_id}},
            {"$facet": {
                "summary": [{"$group": {
                    "_id": None,
                    "completed_sessions": completed_count,
                    "partial_sessions": partial_count,
                }}],
                "week": [
                    {"$match": {"completed_at": {"$gte": start_of_week, "$lt": next_day}}},
                    {"$group": {"_id": {"$dateToString": {
                        "format": "%Y-%m-%d", "date": "$completed_at", "timezone": "UTC",
                    }}}},
                ],
                "recent": [
                    {"$sort": {"completed_at": -1, "_id": -1}},
                    {"$limit": 5},
                    {"$lookup": {
                        "from": "exercises", "localField": "exercise_id",
                        "foreignField": "_id", "as": "exercise",
                    }},
                    {"$project": {
                        "assignment_id": 1, "exercise_id": 1, "completed_at": 1,
                        "completed_sets": 1, "completed_reps": 1,
                        "duration_seconds": 1, "completion_status": 1, "notes": 1,
                        "exercise_name": {"$ifNull": [
                            {"$arrayElemAt": ["$exercise.title", 0]}, "Unknown Exercise",
                        ]},
                    }},
                ],
                "exercises": [
                    {"$group": {
                        "_id": "$exercise_id", "performance_count": {"$sum": 1},
                        "completed_sessions": completed_count,
                        "partial_sessions": partial_count,
                        "latest_completion": {"$max": "$completed_at"},
                    }},
                    {"$sort": {"latest_completion": -1, "_id": -1}},
                    {"$lookup": {
                        "from": "exercises", "localField": "_id",
                        "foreignField": "_id", "as": "exercise",
                    }},
                    {"$project": {
                        "performance_count": 1, "completed_sessions": 1,
                        "partial_sessions": 1, "latest_completion": 1,
                        "exercise_name": {"$ifNull": [
                            {"$arrayElemAt": ["$exercise.title", 0]}, "Unknown Exercise",
                        ]},
                    }},
                ],
                "stages": [
                    {"$lookup": {
                        "from": "exercise_assignments", "localField": "assignment_id",
                        "foreignField": "_id", "as": "assignment",
                    }},
                    {"$unwind": "$assignment"},
                    {"$match": {
                        "assignment.patient_id": patient_object_id,
                        "assignment.status": {"$ne": "cancelled"},
                    }},
                    {"$group": {
                        "_id": "$assignment.stage_id",
                        "exercises": {"$addToSet": "$exercise_id"},
                        "completed_sessions": completed_count,
                        "latest_completion": {"$max": "$completed_at"},
                    }},
                    {"$project": {
                        "exercises_with_activity": {"$size": "$exercises"},
                        "completed_sessions": 1, "latest_completion": 1,
                    }},
                ],
            }},
        ]).to_list(length=1)
        return rows[0] if rows else {}

    @staticmethod
    async def create_exercise(exercise: Exercise) -> Exercise:
        return await exercise.insert()

    @staticmethod
    async def get_exercise_by_id(id: str) -> Optional[Exercise]:
        if not PydanticObjectId.is_valid(id):
            return None
        return await Exercise.get(PydanticObjectId(id))

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
        if not PydanticObjectId.is_valid(id):
            return None
        return await ExerciseAssignment.get(PydanticObjectId(id))

    @staticmethod
    async def list_assignments_by_patient(patient_id: str) -> List[ExerciseAssignment]:
        if not PydanticObjectId.is_valid(patient_id):
            return []
        return await ExerciseAssignment.find(
            ExerciseAssignment.patient_id == PydanticObjectId(patient_id)
        ).sort(-ExerciseAssignment.assigned_at).to_list()

    @staticmethod
    async def list_assignments_by_care_plan(care_plan_id: str) -> List[ExerciseAssignment]:
        if not PydanticObjectId.is_valid(care_plan_id):
            return []
        return await ExerciseAssignment.find(
            ExerciseAssignment.care_plan_id == PydanticObjectId(care_plan_id)
        ).sort(-ExerciseAssignment.assigned_at).to_list()

    @staticmethod
    async def create_progress(progress: ExerciseProgress) -> ExerciseProgress:
        return await progress.insert()

    @staticmethod
    async def list_progress_by_patient(patient_id: str) -> List[ExerciseProgress]:
        if not PydanticObjectId.is_valid(patient_id):
            return []
        return await ExerciseProgress.find(
            ExerciseProgress.patient_id == PydanticObjectId(patient_id)
        ).sort(-ExerciseProgress.completed_at).to_list()

    @staticmethod
    async def list_progress_by_assignment(assignment_id: str) -> List[ExerciseProgress]:
        if not PydanticObjectId.is_valid(assignment_id):
            return []
        return await ExerciseProgress.find(
            ExerciseProgress.assignment_id == PydanticObjectId(assignment_id)
        ).sort(-ExerciseProgress.completed_at).to_list()

    @staticmethod
    async def list_page_exercises(
        active_only: bool, page: PageWindow, category: str | None = None,
        search: str | None = None,
    ) -> List[Exercise]:
        query = {"active": True} if active_only else {}
        if category:
            query["category"] = category
        if search:
            query["title"] = {"$regex": re.escape(search), "$options": "i"}
        return await Exercise.find(query).sort(
            "+title", "+_id"
        ).skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def list_patient_assignment_details(
        patient_id: str, page: PageWindow, category: str | None = None,
    ) -> list[dict]:
        exercise_match = {"exercise.active": True}
        if category:
            exercise_match["exercise.category"] = category
        return await ExerciseAssignment.get_pymongo_collection().aggregate([
            {"$match": {"patient_id": PydanticObjectId(patient_id)}},
            {"$lookup": {
                "from": "exercises", "localField": "exercise_id",
                "foreignField": "_id", "as": "exercise",
            }},
            {"$unwind": "$exercise"},
            {"$match": exercise_match},
            {"$sort": {"assigned_at": -1, "_id": -1}},
            {"$skip": page.offset},
            {"$limit": page.size},
            {"$project": {
                "exercise_id": 1, "sets": 1, "reps": 1, "duration_seconds": 1,
                "revision": {"$ifNull": ["$revision", 0]},
                "status": 1, "exercise.title": 1, "exercise.category": 1,
                "exercise.description": 1, "exercise.instructions": 1,
                "exercise.safety_precautions": 1,
            }},
        ]).to_list(length=page.size)

    @staticmethod
    async def list_page_assignments_by_patient(
        patient_id: str, page: PageWindow,
    ) -> List[ExerciseAssignment]:
        if not PydanticObjectId.is_valid(patient_id):
            return []
        return await ExerciseAssignment.find({
            "patient_id": PydanticObjectId(patient_id),
        }).sort("-assigned_at", "-_id").skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def list_page_assignments_by_care_plan(
        care_plan_id: str, page: PageWindow,
    ) -> List[ExerciseAssignment]:
        if not PydanticObjectId.is_valid(care_plan_id):
            return []
        return await ExerciseAssignment.find({
            "care_plan_id": PydanticObjectId(care_plan_id),
        }).sort("-assigned_at", "-_id").skip(page.offset).limit(page.size).to_list()

    @staticmethod
    async def list_page_progress_by_patient(
        patient_id: str, page: PageWindow,
    ) -> List[ExerciseProgress]:
        if not PydanticObjectId.is_valid(patient_id):
            return []
        return await ExerciseProgress.find({
            "patient_id": PydanticObjectId(patient_id),
        }).sort("-completed_at", "-_id").skip(page.offset).limit(page.size).to_list()

