from typing import List, Optional
from app.repositories.profile_repository import ProfileRepository
from app.schemas.doctor import DoctorOut
from app.schemas.patient import PatientOut

class UserService:
    @staticmethod
    async def list_doctors() -> List[DoctorOut]:
        doctors = await ProfileRepository.list_doctors()
        return [
            DoctorOut(
                id=str(d.id),
                full_name=d.user.full_name,
                email=d.user.email,
                specialization=d.specialization,
                profile_image=d.profile_image,
                bio=d.bio,
                is_active_today=d.is_active_today
            )
            for d in doctors
        ]

    @staticmethod
    async def list_patients() -> List[PatientOut]:
        patients = await ProfileRepository.list_patients()
        return [
            PatientOut(
                id=str(p.id),
                full_name=p.user.full_name,
                email=p.user.email,
                phone=p.phone,
                date_of_birth=p.date_of_birth,
                subscription_status=p.subscription_status
            )
            for p in patients
        ]

    @staticmethod
    async def get_patient_profile(user_id: str) -> Optional[PatientOut]:
        p = await ProfileRepository.get_patient_by_user_id(user_id)
        if not p:
            return None
        return PatientOut(
            id=str(p.id),
            full_name=p.user.full_name,
            email=p.user.email,
            phone=p.phone,
            date_of_birth=p.date_of_birth,
            subscription_status=p.subscription_status
        )

    @staticmethod
    async def get_doctor_profile(user_id: str) -> Optional[DoctorOut]:
        d = await ProfileRepository.get_doctor_by_user_id(user_id)
        if not d:
            return None
        return DoctorOut(
            id=str(d.id),
            full_name=d.user.full_name,
            email=d.user.email,
            specialization=d.specialization,
            profile_image=d.profile_image,
            bio=d.bio,
            is_active_today=d.is_active_today
        )
