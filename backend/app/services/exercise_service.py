from typing import List, Optional, Literal

from beanie import PydanticObjectId

from app.core.time import utc_now
from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress
from app.repositories.exercise_repository import ExerciseRepository
from app.core.pagination import PageWindow
from app.repositories.care_plan_repository import CarePlanRepository
from app.repositories.profile_repository import ProfileRepository
from app.models.patient import Patient


def to_object_id(val) -> PydanticObjectId:
    if isinstance(val, PydanticObjectId):
        return val
    try:
        return PydanticObjectId(str(val))
    except Exception:
        raise ValueError(f"Invalid ObjectId: {val}")

class ExerciseService:
    @staticmethod
    async def _authorize_doctor(patient_id: str, actor_user_id: str, actor_role: str | None):
        if actor_role == "admin" and actor_user_id:
            return None
        if actor_role != "doctor" or not actor_user_id:
            raise PermissionError("Explicit clinical actor context is required.")
        from app.services.clinical_authorization import require_doctor_patient_access
        return await require_doctor_patient_access(actor_user_id, patient_id)

    @staticmethod
    async def create_exercise(exercise_data: dict) -> Exercise:
        category = exercise_data.get("category")
        if category not in ["mobility", "posture", "strength", "stretching"]:
            raise ValueError(f"Invalid exercise category: {category}")
        
        sets = exercise_data.get("sets", 0)
        reps = exercise_data.get("reps", 0)
        duration_seconds = exercise_data.get("duration_seconds", 0)
        
        if sets <= 0 or reps <= 0 or duration_seconds < 0:
            raise ValueError("Sets, reps, and duration must be positive/non-negative values.")

        exercise = Exercise(**exercise_data)
        return await ExerciseRepository.create_exercise(exercise)

    @staticmethod
    async def get_exercise(exercise_id: str) -> Optional[Exercise]:
        return await ExerciseRepository.get_exercise_by_id(exercise_id)

    @staticmethod
    async def list_exercises(
        active_only: bool = False, page: PageWindow | None = None,
        category: str | None = None, search: str | None = None,
    ) -> List[Exercise]:
        if page is not None:
            if search is not None:
                return await ExerciseRepository.list_page_exercises(active_only, page, category, search)
            if category:
                return await ExerciseRepository.list_page_exercises(active_only, page, category)
            return await ExerciseRepository.list_page_exercises(active_only, page)
        return await ExerciseRepository.list_exercises(active_only)

    @staticmethod
    async def create_assignment(
        assignment_data: dict,
        assigned_by_user_id: str,
        assigned_by_role: str,
    ) -> ExerciseAssignment:
        patient_id = assignment_data.get("patient_id")
        care_plan_id = assignment_data.get("care_plan_id")
        stage_id = assignment_data.get("stage_id")
        exercise_id = assignment_data.get("exercise_id")

        # Resolve clinician scope before exposing whether the supplied patient
        # exists. Admin callers retain the detailed validation path below.
        doctor = await ExerciseService._authorize_doctor(
            str(patient_id), assigned_by_user_id, assigned_by_role
        )

        # 1. Validate patient existence
        patient = await Patient.get(to_object_id(patient_id))
        if not patient:
            raise ValueError("Patient does not exist.")

        # 2. Validate care plan existence and ownership
        care_plan = await CarePlanRepository.get_by_id(str(care_plan_id))
        if not care_plan:
            raise ValueError("Care plan does not exist.")
        if str(care_plan.patient_id) != str(patient_id):
            raise ValueError("Care plan does not belong to the specified patient.")
        if doctor and str(care_plan.therapist_id) != str(doctor.id):
            raise PermissionError("Doctor can only assign exercises within their care plans.")

        # 3. Validate stage existence inside care plan
        stage = next((s for s in care_plan.stages if s.stage_id == stage_id), None)
        if not stage:
            raise ValueError("Specified stage does not exist inside the care plan.")

        # 4. Validate exercise existence and active status
        exercise = await ExerciseRepository.get_exercise_by_id(str(exercise_id))
        if not exercise:
            raise ValueError("Exercise does not exist.")
        if not exercise.active:
            raise ValueError("Cannot assign an inactive exercise.")

        # 5. Validate prescription metrics
        sets = assignment_data.get("sets", 0)
        reps = assignment_data.get("reps", 0)
        duration_seconds = assignment_data.get("duration_seconds", 0)
        if sets <= 0 or reps <= 0 or duration_seconds < 0:
            raise ValueError("Invalid prescription values. Sets, reps and duration must be valid positive/non-negative numbers.")

        # Enforce clinician ID assignment
        assigned_by = to_object_id(assigned_by_user_id)

        assignment = ExerciseAssignment(
            patient_id=to_object_id(patient_id),
            care_plan_id=to_object_id(care_plan_id),
            stage_id=stage_id,
            exercise_id=to_object_id(exercise_id),
            sets=sets,
            reps=reps,
            duration_seconds=duration_seconds,
            frequency=assignment_data.get("frequency", "daily"),
            assigned_by=assigned_by
        )
        return await ExerciseRepository.create_assignment(assignment)

    @staticmethod
    async def get_assignment(assignment_id: str) -> Optional[ExerciseAssignment]:
        return await ExerciseRepository.get_assignment_by_id(assignment_id)

    @staticmethod
    async def list_assignments_for_patient(
        patient_id: str, page: PageWindow | None = None,
    ) -> List[ExerciseAssignment]:
        if page is not None:
            return await ExerciseRepository.list_page_assignments_by_patient(patient_id, page)
        return await ExerciseRepository.list_assignments_by_patient(patient_id)

    @staticmethod
    async def list_assignments_for_care_plan(
        care_plan_id: str, page: PageWindow | None = None,
    ) -> List[ExerciseAssignment]:
        if page is not None:
            return await ExerciseRepository.list_page_assignments_by_care_plan(care_plan_id, page)
        return await ExerciseRepository.list_assignments_by_care_plan(care_plan_id)

    @staticmethod
    async def update_assignment(
        assignment_id: str,
        update_data: dict,
        user_role: str,
        actor_user_id: str
    ) -> Optional[ExerciseAssignment]:
        assignment = await ExerciseRepository.get_assignment_by_id(assignment_id)
        if not assignment:
            return None
        if user_role == "patient":
            patient = await ProfileRepository.get_patient_by_user_id(actor_user_id)
            if not patient or str(patient.id) != str(assignment.patient_id):
                raise PermissionError("Assignment is not available")
        else:
            await ExerciseService._authorize_doctor(
                str(assignment.patient_id), actor_user_id, user_role
            )

        expected_revision = update_data.pop("expected_revision", getattr(assignment, "revision", 0))

        # If user is a patient, enforce read-only on prescription parameters
        if user_role == "patient":
            # Patients can only update status
            allowed_fields = {"status"}
            incoming_keys = set(update_data.keys())
            if not incoming_keys.issubset(allowed_fields):
                raise PermissionError("Patients are only authorized to update the completion status of their exercises.")

        # Verify status transitions
        if "status" in update_data:
            old_status = assignment.status
            new_status = update_data["status"]
            if old_status != new_status:
                # Terminal status check
                if old_status in ["completed", "cancelled"]:
                    raise ValueError(f"Cannot transition out of terminal state: {old_status}")
                # Matrix checks
                if old_status == "assigned" and new_status not in ["in_progress", "cancelled"]:
                    raise ValueError(f"Invalid transition from assigned to {new_status}")
                if old_status == "in_progress" and new_status not in ["completed", "cancelled"]:
                    raise ValueError(f"Invalid transition from in_progress to {new_status}")

        # Validate updating prescription values if updated by clinician
        set_fields = {}
        if "sets" in update_data:
            if update_data["sets"] <= 0:
                raise ValueError("Sets must be a positive integer.")
            set_fields["sets"] = update_data["sets"]

        if "reps" in update_data:
            if update_data["reps"] <= 0:
                raise ValueError("Reps must be a positive integer.")
            set_fields["reps"] = update_data["reps"]

        if "duration_seconds" in update_data:
            if update_data["duration_seconds"] < 0:
                raise ValueError("Duration seconds must be a non-negative integer.")
            set_fields["duration_seconds"] = update_data["duration_seconds"]

        if "frequency" in update_data:
            set_fields["frequency"] = update_data["frequency"]

        if "status" in update_data:
            set_fields["status"] = update_data["status"]

        set_fields["updated_at"] = utc_now()
        return await ExerciseRepository.update_assignment_if_revision(
            assignment_id,
            patient_id=assignment.patient_id,
            expected_revision=expected_revision,
            set_fields=set_fields,
        )

    @staticmethod
    async def create_progress_record(progress_data: dict, patient_user_id: str) -> ExerciseProgress:
        patient = await ProfileRepository.get_patient_by_user_id(patient_user_id)
        if not patient:
            raise ValueError("Patient profile not found.")

        assignment_id = progress_data.get("assignment_id")
        assignment = await ExerciseRepository.get_assignment_by_id(str(assignment_id))
        if not assignment:
            raise ValueError("Assignment not found.")
        expected_revision = progress_data.pop(
            "expected_assignment_revision", getattr(assignment, "revision", 0)
        )

        if str(assignment.patient_id) != str(patient.id):
            raise PermissionError("Assignment does not belong to the patient.")

        if assignment.status == "cancelled":
            raise ValueError("Cannot record progress against a cancelled assignment.")

        completed_sets = progress_data.get("completed_sets", 0)
        completed_reps = progress_data.get("completed_reps", 0)
        duration_seconds = progress_data.get("duration_seconds", 0)

        if completed_sets < 0 or completed_reps < 0 or duration_seconds < 0:
            raise ValueError("Sets, reps, and duration must be non-negative values.")

        # Expose relationship integrity fields
        progress = ExerciseProgress(
            id=PydanticObjectId(),
            patient_id=assignment.patient_id,
            assignment_id=assignment.id,
            exercise_id=assignment.exercise_id,
            care_plan_id=assignment.care_plan_id,
            stage_id=assignment.stage_id,
            completed_sets=completed_sets,
            completed_reps=completed_reps,
            duration_seconds=duration_seconds,
            completion_status=progress_data.get("completion_status", "completed"),
            notes=progress_data.get("notes")
        )

        next_status = assignment.status
        if progress.completion_status == "completed":
            next_status = "completed"
        elif assignment.status == "assigned":
            next_status = "in_progress"
        return await ExerciseRepository.create_progress_with_assignment_transition(
            progress,
            assignment_id=str(assignment.id),
            patient_id=assignment.patient_id,
            expected_revision=expected_revision,
            expected_status=assignment.status,
            next_status=next_status,
        )

    @staticmethod
    async def list_progress_for_patient(
        patient_id: str, page: PageWindow | None = None,
    ) -> List[ExerciseProgress]:
        if page is not None:
            return await ExerciseRepository.list_page_progress_by_patient(patient_id, page)
        return await ExerciseRepository.list_progress_by_patient(patient_id)

    @staticmethod
    async def list_progress_for_assignment(assignment_id: str) -> List[ExerciseProgress]:
        return await ExerciseRepository.list_progress_by_assignment(assignment_id)

    @staticmethod
    async def get_exercise_progress_stats(patient_id: str) -> dict:
        """Return patient-scoped summaries without materializing lifetime documents."""
        from datetime import datetime, timedelta

        today = utc_now().date()
        start_of_week = today - timedelta(days=today.weekday())
        week_start = datetime.combine(start_of_week, datetime.min.time())
        next_day = datetime.combine(today + timedelta(days=1), datetime.min.time())

        assignment_data = await ExerciseRepository.aggregate_assignment_stats(patient_id)
        progress_data = await ExerciseRepository.aggregate_progress_stats(
            patient_id, week_start, next_day,
        )
        stage_titles = await CarePlanRepository.get_active_stage_titles(patient_id)

        assignment_summary = (assignment_data.get("summary") or [{}])[0]
        progress_summary = (progress_data.get("summary") or [{}])[0]
        total = assignment_summary.get("total", 0)
        completed = assignment_summary.get("completed", 0)
        percentage = round(completed / total * 100) if total else 100
        week_dates = {row["_id"] for row in progress_data.get("week", [])}
        log = []
        for offset, day_name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            day = start_of_week + timedelta(days=offset)
            log.append({
                "day": day_name,
                "completed": None if day > today else day.isoformat() in week_dates,
            })

        targets = {
            str(row["_id"]): f'{row["sets"]} sets x {row["reps"]} reps'
            for row in assignment_data.get("targets", [])
        }
        recent_activity = [
            {
                "assignment_id": str(row["assignment_id"]),
                "exercise_id": str(row["exercise_id"]),
                "exercise_name": row["exercise_name"],
                "completed_at": row["completed_at"].isoformat(),
                "completed_sets": row["completed_sets"],
                "completed_reps": row["completed_reps"],
                "duration_seconds": row["duration_seconds"],
                "completion_status": row["completion_status"],
                "notes": row.get("notes"),
            }
            for row in progress_data.get("recent", [])
        ]
        exercise_breakdown = [
            {
                "exercise_id": str(row["_id"]),
                "exercise_name": row["exercise_name"],
                "performance_count": row["performance_count"],
                "completed_sessions": row["completed_sessions"],
                "partial_sessions": row["partial_sessions"],
                "latest_completion": row["latest_completion"].isoformat(),
                "prescribed_target": targets.get(str(row["_id"]), ""),
            }
            for row in progress_data.get("exercises", [])
        ]
        stage_progress = {row["_id"]: row for row in progress_data.get("stages", [])}
        stage_breakdown = []
        for row in assignment_data.get("stages", []):
            stage_id = row["_id"]
            activity = stage_progress.get(stage_id, {})
            latest = activity.get("latest_completion")
            stage_breakdown.append({
                "stage_id": stage_id,
                "stage_title": stage_titles.get(stage_id, f"Stage {stage_id}"),
                "assigned_exercise_count": row["assigned_exercise_count"],
                "exercises_with_activity": activity.get("exercises_with_activity", 0),
                "completed_sessions": activity.get("completed_sessions", 0),
                "latest_completion": latest.isoformat() if latest else None,
            })

        return {
            "percentage": percentage,
            "completed": completed,
            "total": total,
            "log": log,
            "period": "current_week",
            "completed_sessions": progress_summary.get("completed_sessions", 0),
            "partial_sessions": progress_summary.get("partial_sessions", 0),
            "active_assignments": total,
            "completion_percentage": percentage,
            "recent_activity": recent_activity,
            "exercise_breakdown": exercise_breakdown,
            "stage_breakdown": stage_breakdown,
        }

