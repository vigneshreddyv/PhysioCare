"""FINAL ACCEPTANCE — realistic demo data via the app's own Beanie models.
Idempotent: re-running updates/overwrites only the demo entities it created.
Run from backend/:  ./venv/Scripts/python.exe seed_acceptance_data.py
"""
import asyncio
from datetime import datetime, timedelta

from app.core.security import get_password_hash
from app.database import init_db, BeanieCompatibleMotorClient
from app.core.config import settings
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.care_plan import CarePlan, CarePlanHistory
from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress

PATIENT_EMAIL = "john.doe@gmail.com"
THERAPIST_EMAIL = "sarah.miller@physiocare.com"


async def main():
    await init_db()

    patient_user = await User.find_one(User.email == PATIENT_EMAIL)
    therapist_user = await User.find_one(User.email == THERAPIST_EMAIL)
    assert patient_user, "run backend/seed.py first (creates base users)"
    assert therapist_user, "run backend/seed.py first (creates base users)"

    patient = await Patient.find_one(Patient.user_id == patient_user.id)
    assert patient, "patient profile missing"
    therapist = await Doctor.find_one(Doctor.user_id == therapist_user.id)
    assert therapist, "doctor profile missing"

    now = datetime.utcnow()
    start = now - timedelta(days=26)
    target = now + timedelta(days=34)

    # ---------- CARE PLAN (2 completed + 1 active + 2 upcoming stages) ----------
    plan = await CarePlan.find_one(CarePlan.patient_id == patient.id)
    if plan:
        await plan.delete()

    plan = CarePlan(
        patient_id=patient.id,
        therapist_id=therapist.id,
        title="Post-Surgical Knee Rehabilitation",
        description="Structured 9-week program to restore knee mobility, rebuild strength and return to daily activity.",
        current_stage=3,
        start_date=start,
        target_date=target,
        status="active",
        stages=[
            dict(stage_id="stg-1", title="Initial Recovery",
                 description="Protect the joint, control pain and swelling, restore basic range of motion.",
                 status="completed", progress=100.0,
                 start_date=start, target_date=start + timedelta(days=14),
                 focus_areas=["Pain management", "Gentle mobility", "Swelling control"]),
            dict(stage_id="stg-2", title="Mobility & Movement",
                 description="Regain full passive range of motion and normalize walking pattern.",
                 status="completed", progress=100.0,
                 start_date=start + timedelta(days=14), target_date=start + timedelta(days=35),
                 focus_areas=["Range of motion", "Gait training"]),
            dict(stage_id="stg-3", title="Strength Building",
                 description="Progressive loading to rebuild quad, hip and core strength.",
                 status="active", progress=68.0,
                 start_date=start + timedelta(days=35), target_date=target - timedelta(days=14),
                 focus_areas=["Quad strengthening", "Hip stability", "Core control"]),
            dict(stage_id="stg-4", title="Advanced Activity",
                 description="Dynamic and sport-specific movements with confidence building.",
                 status="upcoming", progress=0.0,
                 start_date=target - timedelta(days=14), target_date=target - timedelta(days=7),
                 focus_areas=["Balance", "Light jogging"]),
            dict(stage_id="stg-5", title="Return to Daily Life",
                 description="Full independence and long-term joint protection habits.",
                 status="upcoming", progress=0.0,
                 start_date=target - timedelta(days=7), target_date=target,
                 focus_areas=["Endurance", "Maintenance plan"]),
        ],
        goals=[
            dict(goal_id="goal-1", title="Achieve 120 degrees of knee flexion",
                 description="Measured passively by the therapist at each review.",
                 target_value=120, unit="deg", status="in_progress", progress_value=95),
            dict(goal_id="goal-2", title="Walk 20 minutes without support",
                 description="Continuous walking on level ground without aids.",
                 target_value=20, unit="min", status="achieved", progress_value=20),
            dict(goal_id="goal-3", title="Climb stairs comfortably",
                 description="Up and down one full flight without handrail support.",
                 target_value=1, unit="flight", status="in_progress", progress_value=0),
        ],
        recommendations=[
            dict(recommendation_id="rec-1", title="Ice after exercise sessions",
                 description="Apply ice pack for 15 minutes after strengthening sessions to limit swelling.",
                 priority="high"),
            dict(recommendation_id="rec-2", title="Avoid deep squats this stage",
                 description="Deep flexion under load can stress the healing graft. Resume in Stage 4.",
                 priority="high"),
            dict(recommendation_id="rec-3", title="Daily short walks",
                 description="A 10-minute flat walk every day helps circulation and knee lubrication.",
                 priority="normal"),
        ],
    )
    await plan.insert()
    print("care plan inserted:", plan.title)

    actor = patient_user.id
    hist = [
        ("plan_created", None, "active", now - timedelta(days=26)),
        ("stage_activated", "upcoming", "active", now - timedelta(days=26)),
        ("stage_completed", "active", "completed", now - timedelta(days=12)),
        ("goal_achieved", "in_progress", "achieved", now - timedelta(days=5)),
    ]
    for action, prev, new, when in hist:
        await CarePlanHistory(
            care_plan_id=plan.id, patient_id=patient.id, actor_user_id=actor,
            action=action, previous_value=prev, new_value=new, created_at=when,
        ).insert()
    print("care plan history inserted:", len(hist), "entries")

    # ---------- EXERCISE CATALOG (only if missing) ----------
    seed_exercises = [
        dict(title="Knee Extensions", description="Straighten the knee fully while seated and hold.",
             category="strength", difficulty="beginner",
             instructions=["Sit upright with thigh supported.", "Straighten knee slowly to full extension.",
                            "Hold 3 seconds, then lower with control."],
             safety_precautions=["Stop if sharp pain occurs"], sets=3, reps=12, duration_seconds=300,
             target_muscles=["Quadriceps"], equipment=[]),
        dict(title="Heel Slides", description="Gently bend and straighten the knee lying down.",
             category="mobility", difficulty="beginner",
             instructions=["Lie on your back, legs extended.", "Slide the heel toward your hip.",
                            "Hold at comfortable bend, then slide back."],
             safety_precautions=["Do not force into pain"], sets=3, reps=10, duration_seconds=240,
             target_muscles=["Hamstrings"], equipment=[]),
        dict(title="Standing Hamstring Stretch", description="Stretch the back of the thigh safely.",
             category="stretching", difficulty="beginner",
             instructions=["Prop heel on a low step.", "Keep knee slightly bent, hinge forward at hips.",
                            "Hold 20 seconds each side."],
             safety_precautions=["Avoid bouncing"], sets=2, reps=4, duration_seconds=180,
             target_muscles=["Hamstrings"], equipment=["Low step"]),
        dict(title="Wall Posture Holds", description="Align spine against a wall to train posture.",
             category="posture", difficulty="beginner",
             instructions=["Stand with back against wall.", "Flatten lower back gently.",
                            "Hold while breathing steadily."],
             safety_precautions=[], sets=3, reps=5, duration_seconds=200,
             target_muscles=["Core"], equipment=["Wall"]),
    ]
    exercises = {}
    for ex_data in seed_exercises:
        ex = await Exercise.find_one(Exercise.title == ex_data["title"])
        if not ex:
            ex = Exercise(**ex_data)
            await ex.insert()
        exercises[ex.title] = ex
    print("exercise catalog ready:", len(exercises))

    # ---------- ASSIGNMENTS for the ACTIVE stage ----------
    old_assignments = await ExerciseAssignment.find(
        ExerciseAssignment.patient_id == patient.id,
        ExerciseAssignment.care_plan_id == plan.id,
    ).to_list()
    for a in old_assignments:
        await a.delete()

    plan_specs = [
        ("Knee Extensions", 3, 12, "daily", "in_progress"),
        ("Heel Slides", 3, 10, "daily", "assigned"),
        ("Standing Hamstring Stretch", 2, 4, "daily", "completed"),
        ("Wall Posture Holds", 3, 5, "daily", "assigned"),
    ]
    assignments = []
    for title, sets, reps, freq, status in plan_specs:
        ex = exercises[title]
        a = ExerciseAssignment(
            patient_id=patient.id, care_plan_id=plan.id, stage_id="stg-3",
            exercise_id=ex.id, sets=sets, reps=reps,
            duration_seconds=ex.duration_seconds, frequency=freq,
            status=status, assigned_by=therapist.id,
        )
        await a.insert()
        assignments.append((a, ex, status))
    print("assignments inserted:", len(assignments))

    # ---------- PROGRESS LOGS: last 7 days, one completion per day ----------
    old_progress = await ExerciseProgress.find(
        ExerciseProgress.patient_id == patient.id,
        ExerciseProgress.care_plan_id == plan.id,
    ).to_list()
    for p in old_progress:
        await p.delete()

    main_assignment, main_ex, _ = assignments[0]
    created = 0
    for days_ago in range(1, 7):
        a, ex, status = assignments[days_ago % len(assignments)]
        full = days_ago % 2 == 0  # alternate complete / partial days
        await ExerciseProgress(
            patient_id=patient.id, assignment_id=a.id, exercise_id=ex.id,
            care_plan_id=plan.id, stage_id="stg-3",
            completed_at=now - timedelta(days=days_ago),
            completed_sets=a.sets if full else max(1, a.sets - 2),
            completed_reps=a.reps, duration_seconds=a.duration_seconds,
            completion_status="completed" if full else "partial",
        ).insert()
        created += 1
    print("progress logs inserted:", created)

    print("\nDemo data ready for", PATIENT_EMAIL)


asyncio.run(main())
