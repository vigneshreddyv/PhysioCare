"""READ-ONLY DIAGNOSIS — trace John Doe patient link through every layer.
Prints actual IDs so we can see where the chain breaks. No writes.
Run: ./venv/Scripts/python.exe diagnose_patient_link.py
"""
import asyncio
from app.database import init_db
from app.models.user import User
from app.models.patient import Patient
from app.models.care_plan import CarePlan
from app.models.exercise import ExerciseAssignment, ExerciseProgress


def mask_oid(oid):
    return str(oid)


async def main():
    await init_db()

    print("=" * 70)
    print("CHECK 1/2 — USER + PATIENT RECORDS FOR john.doe@gmail.com")
    print("=" * 70)
    users = await User.find_all().to_list()
    jd_users = [u for u in users if "john.doe" in str(u.email).lower()]
    for u in jd_users:
        print(f"USER  email={u.email}  id={u.id}  role={u.role}  active={u.is_active}  created={u.created_at}")
    print(f"(total users in DB: {len(users)})")

    for u in jd_users:
        patients = await Patient.find_all().to_list()
        linked = [p for p in patients if str(p.user_id) == str(u.id)]
        print(f"  -> patient records for user {u.id}: {len(linked)}")
        for p in linked:
            print(f"     PATIENT id={p.id}  user_id={p.user_id}  primary_doctor={p.primary_doctor_id}")
    total_patients = await Patient.find_all().count()
    print(f"(total patients in DB: {total_patients})")

    print()
    print("=" * 70)
    print("CHECK 3/4 — ALL CARE PLANS IN DATABASE")
    print("=" * 70)
    plans = await CarePlan.find_all().to_list()
    print(f"care plans: {len(plans)}")
    for pl in plans:
        stages = pl.stages or []
        statuses = [(s.status, s.progress) for s in stages]
        print(f"  PLAN id={pl.id}")
        print(f"        patient_id={pl.patient_id}  therapist_id={pl.therapist_id}")
        print(f"        title='{pl.title}'  status={pl.status}")
        print(f"        stages ({len(stages)}): {statuses}")
        print(f"        goals={len(pl.goals or [])}  recs={len(pl.recommendations or [])}")

    print()
    print("=" * 70)
    print("CHECK 5 — ALL EXERCISE ASSIGNMENTS")
    print("=" * 70)
    assigns = await ExerciseAssignment.find_all().to_list()
    print(f"assignments: {len(assigns)}")
    for a in assigns:
        print(f"  ASSIGN id={a.id}")
        print(f"         patient_id={a.patient_id}  care_plan_id={a.care_plan_id}  stage_id={a.stage_id}")
        print(f"         exercise_id={a.exercise_id}  status={a.status}")

    print()
    print("=" * 70)
    print("CHECK 6 — ALL PROGRESS LOGS")
    print("=" * 70)
    logs = await ExerciseProgress.find_all().to_list()
    print(f"progress logs: {len(logs)}")
    for l in logs[:8]:
        print(f"  LOG id={l.id}  patient_id={l.patient_id}  care_plan_id={l.care_plan_id}  completed_at={l.completed_at}")

    print()
    print("=" * 70)
    print("CHAIN MATCH ANALYSIS")
    print("=" * 70)
    if jd_users:
        u = jd_users[0]
        patient = None
        patients = await Patient.find_all().to_list()
        for p in patients:
            if str(p.user_id) == str(u.id):
                patient = p
                break
        if patient:
            print(f"patient of record: {patient.id}")
            my_plans = [pl for pl in plans if str(pl.patient_id) == str(patient.id)]
            print(f"care plans pointing at THIS patient: {len(my_plans)}")
            orphan_plans = [pl for pl in plans if str(pl.patient_id) != str(patient.id)]
            print(f"care plans pointing ELSEWHERE: {len(orphan_plans)}")
            for pl in orphan_plans:
                pid = pl.patient_id
                exists = any(str(p.id) == str(pid) for p in patients)
                print(f"  ORPHAN plan '{pl.title}' -> patient_id={pid} (patient record exists: {exists})")
            if patient:
                my_assigns = [a for a in assigns if str(a.patient_id) == str(patient.id)]
                my_logs = [l for l in logs if str(l.patient_id) == str(patient.id)]
                print(f"assignments for THIS patient: {len(my_assigns)}")
                print(f"progress logs for THIS patient: {len(my_logs)}")
        else:
            print("NO PATIENT RECORD LINKED TO THIS USER")


asyncio.run(main())
