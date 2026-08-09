from typing import List, Optional

from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.doctor import DoctorOut
from app.schemas.patient import PatientOut, SavedAddressUpdate


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
    