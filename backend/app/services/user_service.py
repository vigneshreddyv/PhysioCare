from typing import List, Optional

from beanie import PydanticObjectId

from app.core.time import utc_now
from app.core.pagination import DEFAULT_PAGE_SIZE, PageWindow
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.doctor import DoctorOut, DoctorProfileUpdate, PublicDoctorOut
from app.schemas.patient import (
    DoctorPatientOut,
    AdminPatientUpdate,
    PatientOut,
    PatientProfileUpdate,
    ReceptionPatientOut,
    ReceptionPatientUpdate,
)
from app.models.patient import PatientAdminEditAudit
from app.schemas.lab_request import LaboratorianSummary
from app.schemas.auth import StaffOut
from fastapi import HTTPException, status


class UserService:

    @staticmethod
    async def search_patients(search: str, page: PageWindow, *, doctor_user_id: str | None = None,
                              reception: bool = False):
        doctor_id = None
        if doctor_user_id:
            doctor = await ProfileRepository.get_doctor_by_user_id(doctor_user_id)
            if not doctor:
                return []
            doctor_id = str(doctor.id)
        pairs = await ProfileRepository.search_patients(
            search,
            page,
            doctor_id=doctor_id,
            active_only=reception,
            view="reception" if reception else "doctor" if doctor_user_id else "admin",
        )
        if reception:
            return [ReceptionPatientOut(id=str(patient.id), full_name=user.full_name,
                                        email=user.email, phone=patient.phone)
                    for patient, user in pairs]
        if doctor_user_id:
            return [DoctorPatientOut(id=str(patient.id), full_name=user.full_name,
                                     phone=patient.phone, date_of_birth=patient.date_of_birth,
                                     gender=getattr(patient, "gender", None))
                    for patient, user in pairs]
        return [UserService._patient_out(patient, user) for patient, user in pairs]

    @staticmethod
    async def search_doctors(search: str, page: PageWindow, *, reception: bool = False,
                             home_visits_only: bool = False):
        pairs = await ProfileRepository.search_doctors(
            search, page, active_only=reception, home_visits_only=home_visits_only,
        )
        if reception:
            return [PublicDoctorOut(id=str(doctor.id), full_name=user.full_name,
                                    **UserService._doctor_profile_fields(doctor))
                    for doctor, user in pairs]
        return [DoctorOut(id=str(doctor.id), full_name=user.full_name, email=user.email,
                          is_active_today=doctor.is_active_today,
                          **UserService._doctor_profile_fields(doctor))
                for doctor, user in pairs]

    @staticmethod
    async def search_public_doctors(
        search: str, page: PageWindow, *, home_visits_only: bool = False,
    ) -> list[PublicDoctorOut]:
        pairs = await ProfileRepository.search_doctors(
            search,
            page,
            active_only=True,
            home_visits_only=home_visits_only,
            include_email_in_search=False,
        )
        return [
            PublicDoctorOut(
                id=str(doctor.id),
                full_name=user.full_name,
                **UserService._doctor_profile_fields(doctor),
            )
            for doctor, user in pairs
        ]

    @staticmethod
    def _patient_out(patient, user) -> PatientOut:
        return PatientOut(
            id=str(patient.id),
            full_name=user.full_name,
            email=user.email,
            phone=patient.phone,
            date_of_birth=patient.date_of_birth,
            gender=getattr(patient, "gender", None),
            subscription_status=patient.subscription_status,
        )

    @staticmethod
    async def list_staff(
        page: PageWindow = PageWindow(1, DEFAULT_PAGE_SIZE),
        *,
        search: str = "",
        role: str | None = None,
        is_active: bool | None = None,
    ) -> list[StaffOut]:
        return [
            StaffOut(
                id=str(user.id),
                full_name=user.full_name,
                email=user.email,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
            )
            for user in await UserRepository.list_staff(
                page, search=search, role=role, is_active=is_active,
            )
        ]

    @staticmethod
    async def list_laboratorians() -> list[LaboratorianSummary]:
        return [
            LaboratorianSummary(id=str(user.id), full_name=user.full_name)
            for user in await UserRepository.list_by_role("laboratorian")
        ]

    @staticmethod
    async def search_laboratorians(search: str, page: PageWindow) -> list[LaboratorianSummary]:
        return [
            LaboratorianSummary(id=str(user.id), full_name=user.full_name)
            for user in await UserRepository.search_by_role("laboratorian", search, page)
        ]

    @staticmethod
    def _doctor_profile_fields(doctor):
        return {
            "specialization": doctor.specialization,
            "profile_image": getattr(doctor, "profile_image", None),
            "bio": getattr(doctor, "bio", None),
            "qualifications": getattr(doctor, "qualifications", None),
            "years_experience": getattr(doctor, "years_experience", None),
            "specialties": getattr(doctor, "specialties", []) or [],
            "linkedin_url": getattr(doctor, "linkedin_url", None),
            "website_url": getattr(doctor, "website_url", None),
            "accepts_home_visits": getattr(doctor, "accepts_home_visits", True),
        }

    @staticmethod
    async def update_patient_profile(user_id: str, schema: PatientProfileUpdate) -> PatientOut:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        user = await UserRepository.get_by_id(user_id)
        if not patient or not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        updates = schema.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide a name, phone number, or gender to update",
            )
        if "full_name" in updates:
            if updates["full_name"] is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Full name cannot be empty",
                )
            user.full_name = updates["full_name"]
            await UserRepository.save(user)
        patient_changed = False
        if "phone" in updates:
            patient.phone = updates["phone"]
            patient_changed = True
        if "gender" in updates:
            patient.gender = updates["gender"]
            patient_changed = True
        if patient_changed:
            await ProfileRepository.save_patient(patient)

        return await UserService.get_patient_profile(user_id)

    @staticmethod
    async def update_doctor_profile(doctor_id: str, schema: DoctorProfileUpdate) -> DoctorOut:
        doctor = await ProfileRepository.get_doctor_by_id(doctor_id)
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found")
        user = await UserRepository.get_by_id(str(doctor.user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor account not found")

        updates = schema.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide at least one profile field to update",
            )
        if "full_name" in updates:
            user.full_name = updates.pop("full_name")
            await UserRepository.save(user)
        for field, value in updates.items():
            setattr(doctor, field, value)
        if updates:
            await ProfileRepository.save_doctor(doctor)

        return DoctorOut(
            id=str(doctor.id),
            full_name=user.full_name,
            email=user.email,
            is_active_today=doctor.is_active_today,
            **UserService._doctor_profile_fields(doctor),
        )

    @staticmethod
    async def list_patients(page: PageWindow | None = None) -> List[PatientOut]:
        patients = (
            await ProfileRepository.list_page_patients(page)
            if page else await ProfileRepository.list_patients()
        )

        result = []

        for p in patients:
            user = await UserRepository.get_by_id(str(p.user_id))

            if not user:
                continue

            result.append(UserService._patient_out(p, user))

        return result

    @staticmethod
    async def list_reception_patients(
        page: PageWindow | None = None,
    ) -> List[ReceptionPatientOut]:
        patients = (
            await ProfileRepository.list_page_patients(page)
            if page else await ProfileRepository.list_patients()
        )
        result = []

        for patient in patients:
            user = await UserRepository.get_by_id(str(patient.user_id))
            if not user or not user.is_active:
                continue
            result.append(
                ReceptionPatientOut(
                    id=str(patient.id),
                    full_name=user.full_name,
                    email=user.email,
                    phone=patient.phone,
                )
            )

        return result

    @staticmethod
    async def get_admin_patient(patient_id: str) -> PatientOut:
        patient = await ProfileRepository.get_patient_by_id(patient_id)
        user = await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        if not patient or not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )
        return UserService._patient_out(patient, user)

    @staticmethod
    async def get_doctor_patient(doctor_user_id: str, patient_id: str) -> DoctorPatientOut:
        doctor = await ProfileRepository.get_doctor_by_user_id(doctor_user_id)
        if not doctor or not await AppointmentRepository.has_assigned_patient(str(doctor.id), patient_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        patient = await ProfileRepository.get_patient_by_id(patient_id)
        user = await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        if not patient or not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return DoctorPatientOut(id=str(patient.id), full_name=user.full_name,
                                phone=patient.phone, date_of_birth=patient.date_of_birth,
                                gender=getattr(patient, "gender", None))

    @staticmethod
    async def update_admin_patient(
        patient_id: str,
        schema: AdminPatientUpdate,
        actor_user_id: str,
    ) -> PatientOut:
        patient = await ProfileRepository.get_patient_by_id(patient_id)
        user = await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        if not patient or not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        updates = schema.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide at least one patient field to update",
            )

        changed_fields = sorted(updates)
        if "full_name" in updates:
            user.full_name = updates.pop("full_name")
            await UserRepository.save(user)
        if "date_of_birth" in updates:
            birth_date = updates.pop("date_of_birth")
            patient.date_of_birth = birth_date.isoformat() if birth_date else None
        for field, value in updates.items():
            setattr(patient, field, value)

        patient.admin_edit_audit = [
            *getattr(patient, "admin_edit_audit", [])[-49:],
            PatientAdminEditAudit(
                actor_user_id=PydanticObjectId(actor_user_id),
                changed_fields=changed_fields,
                changed_at=utc_now(),
            ),
        ]
        await ProfileRepository.save_patient(patient)
        return UserService._patient_out(patient, user)

    @staticmethod
    async def update_reception_patient(
        patient_id: str,
        schema: ReceptionPatientUpdate,
    ) -> ReceptionPatientOut:
        patient = await ProfileRepository.get_patient_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        user = await UserRepository.get_by_id(str(patient.user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient account not found")

        updates = schema.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide a name or phone number to update",
            )
        if "full_name" in updates:
            if updates["full_name"] is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Full name cannot be empty",
                )
            user.full_name = updates["full_name"]
            await UserRepository.save(user)
        if "phone" in updates:
            patient.phone = updates["phone"]
            await ProfileRepository.save_patient(patient)

        return ReceptionPatientOut(
            id=str(patient.id),
            full_name=user.full_name,
            email=user.email,
            phone=patient.phone,
        )

    @staticmethod
    async def list_assigned_patients(
        user_id: str, page: PageWindow | None = None,
    ) -> List[DoctorPatientOut]:
        doctor = await ProfileRepository.get_doctor_by_user_id(user_id)
        if not doctor:
            return []

        if page:
            patient_ids = await AppointmentRepository.page_assigned_patient_ids(
                str(doctor.id), page,
            )
        else:
            appointments = [
                appointment
                for appointment in await AppointmentRepository.list_by_doctor_id(str(doctor.id))
                if not getattr(appointment, "doctor_assignment_pending", False)
            ]
            patient_ids = list(dict.fromkeys(str(appointment.patient_id) for appointment in appointments))
        result = []

        for patient_id in patient_ids:
            patient = await ProfileRepository.get_patient_by_id(patient_id)
            if not patient:
                continue
            user = await UserRepository.get_by_id(str(patient.user_id))
            if not user:
                continue
            result.append(
                DoctorPatientOut(
                    id=str(patient.id),
                    full_name=user.full_name,
                    phone=patient.phone,
                    date_of_birth=patient.date_of_birth,
                    gender=getattr(patient, "gender", None),
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

        return UserService._patient_out(patient, user)

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
            is_active_today=doctor.is_active_today,
            **UserService._doctor_profile_fields(doctor),
        )
