from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app.models.user import User
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.exercise import (
    ExerciseResponse,
    ExerciseCreate,
    ExerciseUpdate,
    ExerciseAssignmentResponse,
    ExerciseAssignmentCreate,
    ExerciseAssignmentUpdate,
    ExerciseProgressResponse,
    ExerciseProgressCreate
)
from app.services.exercise_service import ExerciseService
from app.repositories.profile_repository import ProfileRepository

router = APIRouter(tags=["exercises"])

@router.get("/exercises", response_model=List[ExerciseResponse])
async def list_exercises(
    current_user: User = Depends(get_current_user)
):
    """Retrieve all exercises in the catalog. Active only for patients, all for clinician."""
    active_only = current_user.role == "patient"
    exercises = await ExerciseService.list_exercises(active_only=active_only)
    return [
        ExerciseResponse(
            id=str(e.id),
            title=e.title,
            description=e.description,
            category=e.category,
            difficulty=e.difficulty,
            instructions=e.instructions,
            safety_precautions=e.safety_precautions,
            sets=e.sets,
            reps=e.reps,
            duration_seconds=e.duration_seconds,
            target_muscles=e.target_muscles,
            equipment=e.equipment,
            video_url=e.video_url,
            active=e.active,
            created_at=e.created_at,
            updated_at=e.updated_at
        ) for e in exercises
    ]


@router.get("/exercises/{exercise_id}", response_model=ExerciseResponse)
async def get_exercise(
    exercise_id: str,
    current_user: User = Depends(get_current_user)
):
    """Retrieve details of a specific exercise in the catalog."""
    exercise = await ExerciseService.get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found"
        )
    if current_user.role == "patient" and not exercise.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found"
        )
    return ExerciseResponse(
        id=str(exercise.id),
        title=exercise.title,
        description=exercise.description,
        category=exercise.category,
        difficulty=exercise.difficulty,
        instructions=exercise.instructions,
        safety_precautions=exercise.safety_precautions,
        sets=exercise.sets,
        reps=exercise.reps,
        duration_seconds=exercise.duration_seconds,
        target_muscles=exercise.target_muscles,
        equipment=exercise.equipment,
        video_url=exercise.video_url,
        active=exercise.active,
        created_at=exercise.created_at,
        updated_at=exercise.updated_at
    )


@router.get("/exercise-assignments", response_model=List[ExerciseAssignmentResponse])
async def list_assignments(
    patient_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """List exercise assignments. Patients can only fetch their own."""
    if current_user.role == "patient":
        patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found"
            )
        target_patient_id = str(patient.id)
    else:
        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id query parameter is required for clinicians."
            )
        from app.middleware.auth import verify_caseload
        await verify_caseload(patient_id, current_user)
        target_patient_id = patient_id

    assignments = await ExerciseService.list_assignments_for_patient(target_patient_id)
    return [
        ExerciseAssignmentResponse(
            id=str(a.id),
            patient_id=str(a.patient_id),
            care_plan_id=str(a.care_plan_id),
            stage_id=a.stage_id,
            exercise_id=str(a.exercise_id),
            sets=a.sets,
            reps=a.reps,
            duration_seconds=a.duration_seconds,
            frequency=a.frequency,
            status=a.status,
            assigned_by=str(a.assigned_by),
            assigned_at=a.assigned_at,
            updated_at=a.updated_at
        ) for a in assignments
    ]


@router.get("/exercise-assignments/{assignment_id}", response_model=ExerciseAssignmentResponse)
async def get_assignment(
    assignment_id: str,
    current_user: User = Depends(get_current_user)
):
    """Retrieve details of a specific exercise assignment."""
    assignment = await ExerciseService.get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    if current_user.role == "patient":
        patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
        if not patient or str(assignment.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found or unauthorized access"
            )

    return ExerciseAssignmentResponse(
        id=str(assignment.id),
        patient_id=str(assignment.patient_id),
        care_plan_id=str(assignment.care_plan_id),
        stage_id=assignment.stage_id,
        exercise_id=str(assignment.exercise_id),
        sets=assignment.sets,
        reps=assignment.reps,
        duration_seconds=assignment.duration_seconds,
        frequency=assignment.frequency,
        status=assignment.status,
        assigned_by=str(assignment.assigned_by),
        assigned_at=assignment.assigned_at,
        updated_at=assignment.updated_at
    )


@router.post("/exercise-assignments", response_model=ExerciseAssignmentResponse)
async def create_assignment(
    payload: ExerciseAssignmentCreate,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Create a new exercise assignment (Clinicians only)."""
    try:
        assignment = await ExerciseService.create_assignment(payload.model_dump(), str(current_user.id))
        return ExerciseAssignmentResponse(
            id=str(assignment.id),
            patient_id=str(assignment.patient_id),
            care_plan_id=str(assignment.care_plan_id),
            stage_id=assignment.stage_id,
            exercise_id=str(assignment.exercise_id),
            sets=assignment.sets,
            reps=assignment.reps,
            duration_seconds=assignment.duration_seconds,
            frequency=assignment.frequency,
            status=assignment.status,
            assigned_by=str(assignment.assigned_by),
            assigned_at=assignment.assigned_at,
            updated_at=assignment.updated_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/exercise-assignments/{assignment_id}", response_model=ExerciseAssignmentResponse)
async def update_assignment(
    assignment_id: str,
    payload: ExerciseAssignmentUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update progress status (patient) or full prescription (clinicians)."""
    # Authorization checks
    if current_user.role not in ["patient", "doctor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation unauthorized"
        )

    assignment = await ExerciseService.get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    # Verify IDOR ownership if patient
    if current_user.role == "patient":
        patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
        if not patient or str(assignment.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found or unauthorized access"
            )

    try:
        updated = await ExerciseService.update_assignment(
            assignment_id=assignment_id,
            update_data=payload.model_dump(exclude_unset=True),
            user_role=current_user.role,
            actor_user_id=str(current_user.id)
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
        return ExerciseAssignmentResponse(
            id=str(updated.id),
            patient_id=str(updated.patient_id),
            care_plan_id=str(updated.care_plan_id),
            stage_id=updated.stage_id,
            exercise_id=str(updated.exercise_id),
            sets=updated.sets,
            reps=updated.reps,
            duration_seconds=updated.duration_seconds,
            frequency=updated.frequency,
            status=updated.status,
            assigned_by=str(updated.assigned_by),
            assigned_at=updated.assigned_at,
            updated_at=updated.updated_at
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/exercise-progress", response_model=ExerciseProgressResponse)
async def create_progress(
    payload: ExerciseProgressCreate,
    current_user: User = Depends(get_current_user)
):
    """Log an exercise performance/completion event (Patients only)."""
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can submit self-reported exercise progress."
        )
    try:
        progress = await ExerciseService.create_progress_record(payload.model_dump(), str(current_user.id))
        return ExerciseProgressResponse(
            id=str(progress.id),
            patient_id=str(progress.patient_id),
            assignment_id=str(progress.assignment_id),
            exercise_id=str(progress.exercise_id),
            care_plan_id=str(progress.care_plan_id),
            stage_id=progress.stage_id,
            completed_at=progress.completed_at,
            completed_sets=progress.completed_sets,
            completed_reps=progress.completed_reps,
            duration_seconds=progress.duration_seconds,
            completion_status=progress.completion_status,
            notes=progress.notes,
            created_at=progress.created_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/exercise-progress/stats", response_model=dict)
async def get_patient_stats(
    current_user: User = Depends(get_current_user)
):
    """Retrieve adherence statistics for the logged-in patient."""
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can query their own stats directly."
        )
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )
    return await ExerciseService.get_exercise_progress_stats(str(patient.id))


@router.get("/exercise-progress/stats/{patient_id}", response_model=dict)
async def get_patient_stats_for_clinician(
    patient_id: str,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Retrieve adherence statistics for a patient (Clinicians only)."""
    from app.middleware.auth import verify_caseload
    await verify_caseload(patient_id, current_user)
    return await ExerciseService.get_exercise_progress_stats(patient_id)


@router.get("/exercise-progress", response_model=List[ExerciseProgressResponse])
async def list_patient_progress(
    current_user: User = Depends(get_current_user)
):
    """List completion history for the logged-in patient."""
    if current_user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted."
        )
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )
    records = await ExerciseService.list_progress_for_patient(str(patient.id))
    return [
        ExerciseProgressResponse(
            id=str(r.id),
            patient_id=str(r.patient_id),
            assignment_id=str(r.assignment_id),
            exercise_id=str(r.exercise_id),
            care_plan_id=str(r.care_plan_id),
            stage_id=r.stage_id,
            completed_at=r.completed_at,
            completed_sets=r.completed_sets,
            completed_reps=r.completed_reps,
            duration_seconds=r.duration_seconds,
            completion_status=r.completion_status,
            notes=r.notes,
            created_at=r.created_at
        ) for r in records
    ]


@router.get("/exercise-progress/patient/{patient_id}", response_model=List[ExerciseProgressResponse])
async def list_progress_for_clinician(
    patient_id: str,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """List completion history for a patient (Clinicians only)."""
    from app.middleware.auth import verify_caseload
    await verify_caseload(patient_id, current_user)
    records = await ExerciseService.list_progress_for_patient(patient_id)
    return [
        ExerciseProgressResponse(
            id=str(r.id),
            patient_id=str(r.patient_id),
            assignment_id=str(r.assignment_id),
            exercise_id=str(r.exercise_id),
            care_plan_id=str(r.care_plan_id),
            stage_id=r.stage_id,
            completed_at=r.completed_at,
            completed_sets=r.completed_sets,
            completed_reps=r.completed_reps,
            duration_seconds=r.duration_seconds,
            completion_status=r.completion_status,
            notes=r.notes,
            created_at=r.created_at
        ) for r in records
    ]

