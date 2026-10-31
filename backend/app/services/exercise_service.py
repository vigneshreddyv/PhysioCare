from datetime import datetime
from typing import List, Optional, Literal
from beanie import PydanticObjectId
from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress
from app.repositories.exercise_repository import ExerciseRepository
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
    async def _authorize_doctor(patient_id: str, actor_user_id: str, actor_role: str):
        if actor_role != "doctor":
            return None
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
    async def list_exercises(active_only: bool = False) -> List[Exercise]:
        return await ExerciseRepository.list_exercises(active_only)

    @staticmethod
    async def create_assignment(
        assignment_data: dict,
        assigned_by_user_id: str,
        assigned_by_role: str = "admin"
    ) -> ExerciseAssignment:
        patient_id = assignment_data.get("patient_id")
        care_plan_id = assignment_data.get("care_plan_id")
        stage_id = assignment_data.get("stage_id")
        exercise_id = assignment_data.get("exercise_id")

        # 1. Validate patient existence
        patient = await Patient.get(to_object_id(patient_id))
        if not patient:
            raise ValueError("Patient does not exist.")
        doctor = await ExerciseService._authorize_doctor(
            str(patient.id), assigned_by_user_id, assigned_by_role
        )

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
    async def list_assignments_for_patient(patient_id: str) -> List[ExerciseAssignment]:
        return await ExerciseRepository.list_assignments_by_patient(patient_id)

    @staticmethod
    async def list_assignments_for_care_plan(care_plan_id: str) -> List[ExerciseAssignment]:
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
        await ExerciseService._authorize_doctor(
            str(assignment.patient_id), actor_user_id, user_role
        )

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
        if "sets" in update_data:
            if update_data["sets"] <= 0:
                raise ValueError("Sets must be a positive integer.")
            assignment.sets = update_data["sets"]

        if "reps" in update_data:
            if update_data["reps"] <= 0:
                raise ValueError("Reps must be a positive integer.")
            assignment.reps = update_data["reps"]

        if "duration_seconds" in update_data:
            if update_data["duration_seconds"] < 0:
                raise ValueError("Duration seconds must be a non-negative integer.")
            assignment.duration_seconds = update_data["duration_seconds"]

        if "frequency" in update_data:
            assignment.frequency = update_data["frequency"]

        if "status" in update_data:
            assignment.status = update_data["status"]

        assignment.updated_at = datetime.utcnow()
        await assignment.save()
        return assignment

    @staticmethod
    async def create_progress_record(progress_data: dict, patient_user_id: str) -> ExerciseProgress:
        patient = await ProfileRepository.get_patient_by_user_id(patient_user_id)
        if not patient:
            raise ValueError("Patient profile not found.")

        assignment_id = progress_data.get("assignment_id")
        assignment = await ExerciseRepository.get_assignment_by_id(str(assignment_id))
        if not assignment:
            raise ValueError("Assignment not found.")

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

        saved_progress = await ExerciseRepository.create_progress(progress)

        # Update assignment lifecycle status if needed
        if assignment.status == "assigned":
            assignment.status = "in_progress"
            await assignment.save()

        if saved_progress.completion_status == "completed" and assignment.status == "in_progress":
            assignment.status = "completed"
            await assignment.save()

        return saved_progress

    @staticmethod
    async def list_progress_for_patient(patient_id: str) -> List[ExerciseProgress]:
        return await ExerciseRepository.list_progress_by_patient(patient_id)

    @staticmethod
    async def list_progress_for_assignment(assignment_id: str) -> List[ExerciseProgress]:
        return await ExerciseRepository.list_progress_by_assignment(assignment_id)

    @staticmethod
    async def get_exercise_progress_stats(patient_id: str) -> dict:
        active_assignments = await ExerciseRepository.list_assignments_by_patient(patient_id)
        progress_records = await ExerciseRepository.list_progress_by_patient(patient_id)

        # Get active care plan to obtain stage titles
        from app.repositories.care_plan_repository import CarePlanRepository
        care_plans = await CarePlanRepository.get_by_patient_id(patient_id)
        active_plan = next((cp for cp in care_plans if cp.status == "active"), None)
        stages_dict = {}
        if active_plan:
            stages_dict = {s.stage_id: s.title for s in active_plan.stages}

        # Get catalog exercise titles
        catalog = await ExerciseRepository.list_exercises()
        exercise_names = {str(ex.id): ex.title for ex in catalog}

        # Filter out cancelled assignments for active prescriptions calculation
        non_cancelled_assignments = [a for a in active_assignments if a.status != "cancelled"]
        total = len(non_cancelled_assignments)
        completed = sum(1 for a in non_cancelled_assignments if a.status == "completed")
        percentage = round((completed / total) * 100) if total > 0 else 100

        # Construct weekly adherence log (Mon-Sun) of current week
        from datetime import date, timedelta
        today = datetime.utcnow().date()
        start_of_week = today - timedelta(days=today.weekday())
        days_mapping = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        log = []

        for i in range(7):
            target_date = start_of_week + timedelta(days=i)
            if target_date > today:
                completed_val = None
            else:
                has_record = any(
                    r.completed_at.date() == target_date 
                    for r in progress_records
                )
                completed_val = has_record
            log.append({"day": days_mapping[i], "completed": completed_val})

        # Recent activity (5 most recent logs)
        recent_activity = []
        sorted_progress = sorted(progress_records, key=lambda r: r.completed_at, reverse=True)
        for r in sorted_progress[:5]:
            ex_name = exercise_names.get(str(r.exercise_id), "Unknown Exercise")
            recent_activity.append({
                "assignment_id": str(r.assignment_id),
                "exercise_id": str(r.exercise_id),
                "exercise_name": ex_name,
                "completed_at": r.completed_at.isoformat(),
                "completed_sets": r.completed_sets,
                "completed_reps": r.completed_reps,
                "duration_seconds": r.duration_seconds,
                "completion_status": r.completion_status,
                "notes": r.notes
            })

        # Exercise breakdown (grouped by exercise ID)
        exercise_breakdown = []
        exercise_groups = {}
        for r in progress_records:
            eid = str(r.exercise_id)
            if eid not in exercise_groups:
                exercise_groups[eid] = []
            exercise_groups[eid].append(r)

        for eid, records in exercise_groups.items():
            ex_name = exercise_names.get(eid, "Unknown Exercise")
            comp_count = sum(1 for r in records if r.completion_status == "completed")
            part_count = sum(1 for r in records if r.completion_status == "partial")

            matching_assign = next((a for a in non_cancelled_assignments if str(a.exercise_id) == eid), None)
            target_str = ""
            if matching_assign:
                target_str = f"{matching_assign.sets} sets x {matching_assign.reps} reps"

            exercise_breakdown.append({
                "exercise_id": eid,
                "exercise_name": ex_name,
                "performance_count": len(records),
                "completed_sessions": comp_count,
                "partial_sessions": part_count,
                "latest_completion": max(r.completed_at for r in records).isoformat() if records else None,
                "prescribed_target": target_str
            })

        # Stage breakdown
        stage_breakdown = []
        stage_assignments = {}
        for a in non_cancelled_assignments:
            sid = a.stage_id
            if sid not in stage_assignments:
                stage_assignments[sid] = []
            stage_assignments[sid].append(a)

        for sid, assigns in stage_assignments.items():
            stage_title = stages_dict.get(sid, f"Stage {sid}")
            assign_ids = {str(a.id) for a in assigns}
            stage_records = [r for r in progress_records if str(r.assignment_id) in assign_ids]

            comp_count = sum(1 for r in stage_records if r.completion_status == "completed")
            recent_act = sorted(stage_records, key=lambda r: r.completed_at, reverse=True)
            latest_time = recent_act[0].completed_at.isoformat() if recent_act else None

            stage_breakdown.append({
                "stage_id": sid,
                "stage_title": stage_title,
                "assigned_exercise_count": len(assigns),
                "exercises_with_activity": len({str(r.exercise_id) for r in stage_records}),
                "completed_sessions": comp_count,
                "latest_completion": latest_time
            })

        completed_sessions = sum(1 for r in progress_records if r.completion_status == "completed")
        partial_sessions = sum(1 for r in progress_records if r.completion_status == "partial")

        return {
            "percentage": percentage,
            "completed": completed,
            "total": total,
            "log": log,
            "period": "current_week",
            "completed_sessions": completed_sessions,
            "partial_sessions": partial_sessions,
            "active_assignments": len(non_cancelled_assignments),
            "completion_percentage": percentage,
            "recent_activity": recent_activity,
            "exercise_breakdown": exercise_breakdown,
            "stage_breakdown": stage_breakdown
        }

