from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models.user import User
from app.middleware.auth import get_current_user, RoleChecker
from app.schemas.exercise import ExerciseAssignmentResponse

from app.schemas.care_plan import (
    CarePlanResponse,
    CarePlanCreate,
    CarePlanUpdate,
    StageSchema,
    GoalSchema,
    RecommendationSchema,
    StageStatusUpdate,
    GoalProgressUpdate,
    CarePlanHistoryResponse
)
from app.services.care_plan_service import CarePlanService

router = APIRouter(prefix="/care-plans", tags=["care-plans"])


def _scoped_denial(current_user: User, detail: str) -> HTTPException:
    if current_user.role == "doctor":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Operation not permitted for this role",
    )


@router.get("", response_model=List[CarePlanResponse])
async def list_care_plans(
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """List all Care Plans belonging to the authenticated patient."""
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )
    care_plans = await CarePlanService.get_care_plans_by_patient(str(patient.id))
    return [
        CarePlanResponse(
            id=str(cp.id),
            patient_id=str(cp.patient_id),
            therapist_id=str(cp.therapist_id),
            title=cp.title,
            description=cp.description,
            current_stage=cp.current_stage,
            stages=[StageSchema(**s.model_dump()) for s in cp.stages],
            goals=[GoalSchema(**g.model_dump()) for g in cp.goals],
            recommendations=[RecommendationSchema(**r.model_dump()) for r in cp.recommendations],
            start_date=cp.start_date,
            target_date=cp.target_date,
            status=cp.status,
            created_at=cp.created_at,
            updated_at=cp.updated_at
        ) for cp in care_plans
    ]


@router.get("/{care_plan_id}", response_model=CarePlanResponse)
async def get_care_plan(
    care_plan_id: str,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """Get a specific Care Plan belonging to the authenticated patient."""
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )
    care_plan = await CarePlanService.get_care_plan_for_patient(care_plan_id, str(patient.id))
    if not care_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care Plan not found or access denied"
        )
    return CarePlanResponse(
        id=str(care_plan.id),
        patient_id=str(care_plan.patient_id),
        therapist_id=str(care_plan.therapist_id),
        title=care_plan.title,
        description=care_plan.description,
        current_stage=care_plan.current_stage,
        stages=[StageSchema(**s.model_dump()) for s in care_plan.stages],
        goals=[GoalSchema(**g.model_dump()) for g in care_plan.goals],
        recommendations=[RecommendationSchema(**r.model_dump()) for r in care_plan.recommendations],
        start_date=care_plan.start_date,
        target_date=care_plan.target_date,
        status=care_plan.status,
        created_at=care_plan.created_at,
        updated_at=care_plan.updated_at
    )


@router.post("", response_model=CarePlanResponse, status_code=status.HTTP_201_CREATED)
async def create_care_plan(
    payload: CarePlanCreate,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Create a new Care Plan. Restricted to doctor/admin."""
    therapist_id = str(current_user.id)
    if current_user.role == "doctor":
        from app.repositories.profile_repository import ProfileRepository
        doctor = await ProfileRepository.get_doctor_by_user_id(str(current_user.id))
        if doctor:
            therapist_id = str(doctor.id)

    try:
        cp = await CarePlanService.create_care_plan(
            patient_id=payload.patient_id,
            therapist_id=therapist_id,
            title=payload.title,
            description=payload.description,
            current_stage=payload.current_stage,
            stages=[s.model_dump() for s in payload.stages],
            goals=[g.model_dump() for g in payload.goals],
            recommendations=[r.model_dump() for r in payload.recommendations],
            start_date=payload.start_date,
            target_date=payload.target_date,
            status=payload.status,
            actor_user_id=str(current_user.id),
            actor_role=current_user.role
        )
    except PermissionError:
        raise _scoped_denial(current_user, "Patient not found") from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return CarePlanResponse(
        id=str(cp.id),
        patient_id=str(cp.patient_id),
        therapist_id=str(cp.therapist_id),
        title=cp.title,
        description=cp.description,
        current_stage=cp.current_stage,
        stages=[StageSchema(**s.model_dump()) for s in cp.stages],
        goals=[GoalSchema(**g.model_dump()) for g in cp.goals],
        recommendations=[RecommendationSchema(**r.model_dump()) for r in cp.recommendations],
        start_date=cp.start_date,
        target_date=cp.target_date,
        status=cp.status,
        created_at=cp.created_at,
        updated_at=cp.updated_at
    )


@router.patch("/{care_plan_id}", response_model=CarePlanResponse)
async def update_care_plan(
    care_plan_id: str,
    payload: CarePlanUpdate,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Update an existing Care Plan. Restricted to doctor/admin."""
    update_data = payload.model_dump(exclude_unset=True)

    try:
        cp = await CarePlanService.update_care_plan(
            care_plan_id,
            update_data,
            actor_user_id=str(current_user.id),
            actor_role=current_user.role
        )
    except PermissionError:
        raise _scoped_denial(current_user, "Care Plan not found") from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not cp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care Plan not found"
        )

    return CarePlanResponse(
        id=str(cp.id),
        patient_id=str(cp.patient_id),
        therapist_id=str(cp.therapist_id),
        title=cp.title,
        description=cp.description,
        current_stage=cp.current_stage,
        stages=[StageSchema(**s.model_dump()) for s in cp.stages],
        goals=[GoalSchema(**g.model_dump()) for g in cp.goals],
        recommendations=[RecommendationSchema(**r.model_dump()) for r in cp.recommendations],
        start_date=cp.start_date,
        target_date=cp.target_date,
        status=cp.status,
        created_at=cp.created_at,
        updated_at=cp.updated_at
    )


@router.get("/patient/{patient_id}", response_model=List[CarePlanResponse])
async def get_patient_care_plans_by_clinician(
    patient_id: str,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Retrieve all Care Plans for a specific patient. Restricted to doctor/admin."""
    if current_user.role == "doctor":
        from app.services.clinical_authorization import require_doctor_patient_access
        try:
            await require_doctor_patient_access(str(current_user.id), patient_id)
        except PermissionError:
            raise _scoped_denial(current_user, "Patient not found") from None
    care_plans = await CarePlanService.get_care_plans_by_patient(patient_id)
    return [
        CarePlanResponse(
            id=str(cp.id),
            patient_id=str(cp.patient_id),
            therapist_id=str(cp.therapist_id),
            title=cp.title,
            description=cp.description,
            current_stage=cp.current_stage,
            stages=[StageSchema(**s.model_dump()) for s in cp.stages],
            goals=[GoalSchema(**g.model_dump()) for g in cp.goals],
            recommendations=[RecommendationSchema(**r.model_dump()) for r in cp.recommendations],
            start_date=cp.start_date,
            target_date=cp.target_date,
            status=cp.status,
            created_at=cp.created_at,
            updated_at=cp.updated_at
        ) for cp in care_plans
    ]


@router.patch("/{care_plan_id}/stages/{stage_id}", response_model=CarePlanResponse)
async def update_stage_status_endpoint(
    care_plan_id: str,
    stage_id: str,
    payload: StageStatusUpdate,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Update clinical status of a treatment stage."""
    try:
        cp = await CarePlanService.update_stage_status(
            care_plan_id=care_plan_id,
            stage_id=stage_id,
            new_status=payload.status,
            actor_user_id=str(current_user.id),
            actor_role=current_user.role
        )
    except PermissionError:
        raise _scoped_denial(current_user, "Care Plan not found") from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not cp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care Plan or treatment stage not found"
        )

    return CarePlanResponse(
        id=str(cp.id),
        patient_id=str(cp.patient_id),
        therapist_id=str(cp.therapist_id),
        title=cp.title,
        description=cp.description,
        current_stage=cp.current_stage,
        stages=[StageSchema(**s.model_dump()) for s in cp.stages],
        goals=[GoalSchema(**g.model_dump()) for g in cp.goals],
        recommendations=[RecommendationSchema(**r.model_dump()) for r in cp.recommendations],
        start_date=cp.start_date,
        target_date=cp.target_date,
        status=cp.status,
        created_at=cp.created_at,
        updated_at=cp.updated_at
    )


@router.patch("/{care_plan_id}/goals/{goal_id}", response_model=CarePlanResponse)
async def update_goal_progress_endpoint(
    care_plan_id: str,
    goal_id: str,
    payload: GoalProgressUpdate,
    current_user: User = Depends(RoleChecker(["admin", "doctor"]))
):
    """Update clinical progress and status of a recovery goal."""
    try:
        cp = await CarePlanService.update_goal_progress(
            care_plan_id=care_plan_id,
            goal_id=goal_id,
            progress_value=payload.progress_value,
            new_status=payload.status,
            actor_user_id=str(current_user.id),
            actor_role=current_user.role
        )
    except PermissionError:
        raise _scoped_denial(current_user, "Care Plan not found") from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not cp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care Plan or recovery goal not found"
        )

    return CarePlanResponse(
        id=str(cp.id),
        patient_id=str(cp.patient_id),
        therapist_id=str(cp.therapist_id),
        title=cp.title,
        description=cp.description,
        current_stage=cp.current_stage,
        stages=[StageSchema(**s.model_dump()) for s in cp.stages],
        goals=[GoalSchema(**g.model_dump()) for g in cp.goals],
        recommendations=[RecommendationSchema(**r.model_dump()) for r in cp.recommendations],
        start_date=cp.start_date,
        target_date=cp.target_date,
        status=cp.status,
        created_at=cp.created_at,
        updated_at=cp.updated_at
    )


@router.get("/{care_plan_id}/history", response_model=List[CarePlanHistoryResponse])
async def get_care_plan_history(
    care_plan_id: str,
    current_user: User = Depends(RoleChecker(["patient"]))
):
    """Retrieve patient-safe Care Plan event history log."""
    from app.repositories.profile_repository import ProfileRepository
    patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found"
        )

    history = await CarePlanService.get_care_plan_history_for_patient(
        care_plan_id=care_plan_id,
        patient_id=str(patient.id)
    )

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care Plan not found or unauthorized access"
        )

    return [
        CarePlanHistoryResponse(
            action=h.action,
            previous_value=h.previous_value,
            new_value=h.new_value,
            created_at=h.created_at
        ) for h in history
    ]


@router.get("/{care_plan_id}/exercises", response_model=List[ExerciseAssignmentResponse])
async def get_care_plan_exercises(
    care_plan_id: str,
    current_user: User = Depends(get_current_user)
):
    """Retrieve exercises assigned to a specific Care Plan, validating ownership."""
    from app.repositories.profile_repository import ProfileRepository
    from app.repositories.care_plan_repository import CarePlanRepository
    from app.schemas.exercise import ExerciseAssignmentResponse
    from app.services.exercise_service import ExerciseService

    if current_user.role not in ["patient", "doctor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access care-plan exercises."
        )

    care_plan = await CarePlanRepository.get_by_id(care_plan_id)
    if not care_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care plan not found"
        )

    if current_user.role == "patient":
        patient = await ProfileRepository.get_patient_by_user_id(str(current_user.id))
        if not patient or str(care_plan.patient_id) != str(patient.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care plan not found or unauthorized access"
            )
    elif current_user.role == "doctor":
        from app.services.clinical_authorization import require_doctor_patient_access
        try:
            await require_doctor_patient_access(
                str(current_user.id), str(care_plan.patient_id)
            )
        except PermissionError:
            raise _scoped_denial(current_user, "Care plan not found") from None

    assignments = await ExerciseService.list_assignments_for_care_plan(care_plan_id)
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
