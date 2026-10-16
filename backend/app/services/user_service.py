from typing import List, Optional

from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.doctor import DoctorOut
from app.schemas.patient import PatientOut, SavedAddressUpdate
from app.models.user import User


class UserService:

    @staticmethod
    async def list_doctors() -> List[DoctorOut]:
        doctors = await ProfileRepository.list_doctors()

        result = []

        for d in doctors:
            user = await UserRepository.get_by_id(str(d.user_id))

            if not user:
                continue

            result.append(
                DoctorOut(
                    id=str(d.id),
                    full_name=user.full_name,
                    email=user.email,
                    specialization=d.specialization,
                    experience_years=d.experience_years,
                    expertise=d.expertise,
                    profile_image=d.profile_image,
                    bio=d.bio,
                    rating=d.rating,
                    total_reviews=d.total_reviews,
                    consultation_fee=d.consultation_fee,
                    home_visit_available=d.home_visit_available,
                    online_consultation_available=d.online_consultation_available,
                    is_active_today=d.is_active_today,
                )
            )

        return result

    @staticmethod
    async def list_patients() -> List[PatientOut]:
        patients = await ProfileRepository.list_patients()

        result = []

        for p in patients:
            user = await UserRepository.get_by_id(str(p.user_id))

            if not user:
                continue

            result.append(
                PatientOut(
                    id=str(p.id),
                    full_name=user.full_name,
                    email=user.email,
                    phone=p.phone,
                    date_of_birth=p.date_of_birth,
                    subscription_status=p.subscription_status,
                )
            )

        return result

    @staticmethod
    async def get_patient_profile(user_id: str) -> Optional[PatientOut]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)

        if not patient:
            return None

        user = await UserRepository.get_by_id(str(patient.user_id))

        if not user:
            return None

        return PatientOut(
            id=str(patient.id),
            full_name=user.full_name,
            email=user.email,
            phone=patient.phone,
            date_of_birth=patient.date_of_birth,
            subscription_status=patient.subscription_status,
            saved_address=patient.saved_address,
        )

    @staticmethod
    async def update_patient_address(
        user_id: str,
        address: SavedAddressUpdate,
    ) -> Optional[PatientOut]:

        patient = await ProfileRepository.get_patient_by_user_id(user_id)

        if not patient:
            return None

        patient.saved_address = address.model_dump()

        await patient.save()

        return await UserService.get_patient_profile(user_id)

    @staticmethod
    async def get_patient_address(
    user_id: str,
    ):
        patient = await ProfileRepository.get_patient_by_user_id(user_id)

        if not patient:
            return None

        return patient.saved_address

    @staticmethod
    async def get_doctor_profile(user_id: str) -> Optional[DoctorOut]:
        doctor = await ProfileRepository.get_doctor_by_user_id(user_id)

        if not doctor:
            return None

        user = await UserRepository.get_by_id(str(doctor.user_id))

        if not user:
            return None

        return DoctorOut(
            id=str(doctor.id),
            full_name=user.full_name,
            email=user.email,
            specialization=doctor.specialization,
            experience_years=doctor.experience_years,
            expertise=doctor.expertise,
            profile_image=doctor.profile_image,
            bio=doctor.bio,
            rating=doctor.rating,
            total_reviews=doctor.total_reviews,
            consultation_fee=doctor.consultation_fee,
            home_visit_available=doctor.home_visit_available,
            online_consultation_available=doctor.online_consultation_available,
            is_active_today=doctor.is_active_today,
        )

    @staticmethod
    async def list_patients_by_doctor(doctor_user_id: str) -> List[PatientOut]:
        doctor = await ProfileRepository.get_doctor_by_user_id(doctor_user_id)
        if not doctor:
            return []

        patients = await ProfileRepository.list_patients_by_doctor_id(str(doctor.id))

        result = []

        for p in patients:
            user = await UserRepository.get_by_id(str(p.user_id))

            if not user:
                continue

            result.append(
                PatientOut(
                    id=str(p.id),
                    full_name=user.full_name,
                    email=user.email,
                    phone=p.phone,
                    date_of_birth=p.date_of_birth,
                    subscription_status=p.subscription_status,
                )
            )

        return result

    @staticmethod
    async def list_patients_monitoring(current_user: User) -> List[dict]:
        from beanie.operators import In
        from datetime import datetime, timedelta
        from app.models.care_plan import CarePlan
        from app.models.exercise import ExerciseAssignment, ExerciseProgress, Exercise

        if current_user.role == "doctor":
            doctor = await ProfileRepository.get_doctor_by_user_id(str(current_user.id))
            if not doctor:
                return []
            patients = await ProfileRepository.list_patients_by_doctor_id(str(doctor.id))
        else:
            patients = await ProfileRepository.list_patients()

        if not patients:
            return []

        patient_ids = [p.id for p in patients]

        # Fetch active Care Plans
        care_plans = await CarePlan.find(In(CarePlan.patient_id, patient_ids), CarePlan.status == "active").to_list()
        care_plans_by_patient = {str(cp.patient_id): cp for cp in care_plans}

        # Fetch Exercise Assignments
        assignments = await ExerciseAssignment.find(In(ExerciseAssignment.patient_id, patient_ids)).to_list()
        assignments_by_patient = {}
        for a in assignments:
            pid_str = str(a.patient_id)
            if pid_str not in assignments_by_patient:
                assignments_by_patient[pid_str] = []
            assignments_by_patient[pid_str].append(a)

        # Fetch Exercise Progress records
        progress_records = await ExerciseProgress.find(In(ExerciseProgress.patient_id, patient_ids)).to_list()
        progress_by_patient = {}
        for r in progress_records:
            pid_str = str(r.patient_id)
            if pid_str not in progress_by_patient:
                progress_by_patient[pid_str] = []
            progress_by_patient[pid_str].append(r)

        # Fetch Exercise Catalog for titles
        catalog = await Exercise.find_all().to_list()
        exercise_names = {str(ex.id): ex.title for ex in catalog}

        result = []
        for p in patients:
            user = await UserRepository.get_by_id(str(p.user_id))
            if not user:
                continue

            cp = care_plans_by_patient.get(str(p.id))
            active_program = cp.title if cp else None
            current_stage = next((s.title for s in cp.stages if s.status == "active"), cp.stages[0].title if cp.stages else None) if cp else None

            p_assignments = assignments_by_patient.get(str(p.id), [])
            non_cancelled = [a for a in p_assignments if a.status != "cancelled"]
            total_assign = len(non_cancelled)
            completed_assign = sum(1 for a in non_cancelled if a.status == "completed")
            adherence = round((completed_assign / total_assign) * 100) if total_assign > 0 else 100

            p_progress = progress_by_patient.get(str(p.id), [])
            sorted_progress = sorted(p_progress, key=lambda r: r.completed_at, reverse=True)
            last_activity_date = sorted_progress[0].completed_at if sorted_progress else None

            # Observational clinical status rules
            if not last_activity_date:
                status_val = "No recent activity"
            else:
                now_naive = datetime.utcnow()
                days_since_active = (now_naive - last_activity_date).days
                if days_since_active > 7:
                    status_val = "No recent activity"
                elif adherence < 50:
                    status_val = "Low recent activity"
                else:
                    status_val = "Active"

            recent_list = []
            for r in sorted_progress[:5]:
                recent_list.append({
                    "exercise_name": exercise_names.get(str(r.exercise_id), "Unknown Exercise"),
                    "completed_sets": r.completed_sets,
                    "completed_reps": r.completed_reps,
                    "completed_at": r.completed_at.isoformat(),
                    "completion_status": r.completion_status,
                    "notes": r.notes
                })

            result.append({
                "id": str(p.id),
                "full_name": user.full_name,
                "email": user.email,
                "phone": p.phone,
                "active_program": active_program,
                "current_stage": current_stage,
                "adherence_percentage": adherence,
                "last_activity": last_activity_date.isoformat() if last_activity_date else None,
                "status": status_val,
                "recent_activity": recent_list
            })

        return result

    @staticmethod
    async def get_patient_snapshot(patient_id: str) -> Optional[dict]:
        from app.repositories.profile_repository import ProfileRepository
        from app.models.care_plan import CarePlan
        from app.models.exercise import ExerciseAssignment, ExerciseProgress, Exercise
        from app.models.appointment import Appointment
        from datetime import datetime

        patient = await ProfileRepository.get_patient_by_id(patient_id)
        if not patient:
            return None

        user = await UserRepository.get_by_id(str(patient.user_id))
        if not user:
            return None

        # Fetch CarePlan details
        care_plan = await CarePlan.find_one(CarePlan.patient_id == patient.id, CarePlan.status == "active")
        active_program = care_plan.title if care_plan else None
        current_stage = next((s.title for s in care_plan.stages if s.status == "active"), care_plan.stages[0].title if care_plan.stages else None) if care_plan else None
        goals_list = [
            {
                "goal_id": g.goal_id,
                "title": g.title,
                "description": g.description,
                "target_value": g.target_value,
                "unit": g.unit,
                "status": g.status,
                "progress_value": g.progress_value
            } for g in care_plan.goals
        ] if care_plan else []
        stages_list = [
            {
                "title": s.title,
                "status": s.status
            } for s in care_plan.stages
        ] if care_plan else []

        # Fetch Exercise assignments & adherence calculations
        assignments = await ExerciseAssignment.find(ExerciseAssignment.patient_id == patient.id).to_list()
        non_cancelled = [a for a in assignments if a.status != "cancelled"]
        total_assign = len(non_cancelled)
        completed_assign = sum(1 for a in non_cancelled if a.status == "completed")
        adherence = round((completed_assign / total_assign) * 100) if total_assign > 0 else 100

        # Fetch Exercise progress records
        progress_records = await ExerciseProgress.find(ExerciseProgress.patient_id == patient.id).to_list()
        sorted_progress = sorted(progress_records, key=lambda r: r.completed_at, reverse=True)
        last_activity_date = sorted_progress[0].completed_at if sorted_progress else None

        # Clinical status
        if not last_activity_date:
            status_val = "No recent activity"
        else:
            now_naive = datetime.utcnow()
            days_since_active = (now_naive - last_activity_date).days
            if days_since_active > 7:
                status_val = "No recent activity"
            elif adherence < 50:
                status_val = "Low recent activity"
            else:
                status_val = "Active"

        # Exercise Catalog mapping
        catalog = await Exercise.find_all().to_list()
        exercise_names = {str(ex.id): ex.title for ex in catalog}

        recent_list = []
        for r in sorted_progress[:5]:
            recent_list.append({
                "exercise_name": exercise_names.get(str(r.exercise_id), "Unknown Exercise"),
                "completed_sets": r.completed_sets,
                "completed_reps": r.completed_reps,
                "completed_at": r.completed_at.isoformat(),
                "completion_status": r.completion_status,
                "notes": r.notes
            })

        # Fetch next upcoming appointment
        appts = await Appointment.find(Appointment.patient_id == patient.id).to_list()
        candidates = []
        for appt in appts:
            if appt.status not in ["scheduled", "confirmed", "pending_payment", "in_progress"]:
                continue
            try:
                date_str = appt.appointment_date
                time_str = appt.time_slot or ""
                time_part = time_str.split(" ")[0]
                modifier = time_str.split(" ")[1] if " " in time_str else ""
                parts = time_part.split(":")
                hours = int(parts[0])
                minutes = int(parts[1]) if len(parts) > 1 else 0
                if modifier == "PM" and hours != 12:
                    hours += 12
                if modifier == "AM" and hours == 12:
                    hours = 0
                y, m, d = map(int, date_str.split("-"))
                appt_dt = datetime(y, m, d, hours, minutes)
                if appt_dt >= datetime.utcnow():
                    candidates.append((appt, appt_dt))
            except Exception:
                continue

        candidates.sort(key=lambda item: item[1])
        next_appt_obj = None
        if candidates:
            next_appt, _ = candidates[0]
            next_appt_obj = {
                "doctor_name": next_appt.doctor_name or "Physiotherapist",
                "appointment_date": next_appt.appointment_date,
                "time_slot": next_appt.time_slot or "N/A",
                "status": next_appt.status,
                "reason": next_appt.reason
            }

        return {
            "id": str(patient.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": patient.phone,
            "date_of_birth": patient.date_of_birth,
            "subscription_status": patient.subscription_status,
            "active_program": active_program,
            "current_stage": current_stage,
            "adherence_percentage": adherence,
            "status": status_val,
            "recent_activity": recent_list,
            "upcoming_appointment": next_appt_obj,
            "goals": goals_list,
            "stages": stages_list
        }
    