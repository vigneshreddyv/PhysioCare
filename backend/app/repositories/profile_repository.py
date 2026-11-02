from typing import List, Optional
import re
from types import SimpleNamespace

from beanie import PydanticObjectId

from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.core.pagination import PageWindow


class ProfileRepository:

    @staticmethod
    async def search_patients(
        search: str,
        page: PageWindow,
        *,
        doctor_id: str | None = None,
        active_only: bool = False,
        view: str = "admin",
    ) -> list[tuple[Patient, SimpleNamespace]]:
        """Search users before paging; a clinician's assignment is checked in MongoDB."""
        match: dict = {"role": "patient"}
        if active_only:
            match["is_active"] = True
        if search:
            pattern = re.escape(search)
            match["$or"] = [{"full_name": {"$regex": pattern, "$options": "i"}},
                            {"email": {"$regex": pattern, "$options": "i"}}]
        pipeline: list[dict] = [
            {"$match": match},
            {"$lookup": {"from": "patients", "localField": "_id", "foreignField": "user_id", "as": "profile"}},
            {"$unwind": "$profile"},
        ]
        if doctor_id:
            pipeline.extend([
                {"$lookup": {"from": "appointments", "let": {"patient_id": "$profile._id"},
                             "pipeline": [{"$match": {"doctor_id": PydanticObjectId(doctor_id),
                                                      "doctor_assignment_pending": {"$ne": True},
                                                      "$expr": {"$eq": ["$patient_id", "$$patient_id"]}}},
                                          {"$limit": 1}, {"$project": {"_id": 1}}],
                             "as": "assignment"}},
                {"$match": {"assignment.0": {"$exists": True}}},
            ])
        profile_fields = {
            "profile._id": 1,
            "profile.user_id": 1,
            "profile.phone": 1,
        }
        user_fields = {"_id": 1, "full_name": 1}
        if view == "admin":
            profile_fields.update({
                "profile.date_of_birth": 1,
                "profile.gender": 1,
                "profile.subscription_status": 1,
            })
            user_fields["email"] = 1
        elif view == "doctor":
            profile_fields.update({"profile.date_of_birth": 1, "profile.gender": 1})
        elif view == "reception":
            user_fields["email"] = 1
        else:
            raise ValueError(f"Unsupported patient directory view: {view}")
        pipeline.extend([
            {"$sort": {"full_name": 1, "_id": 1}},
            {"$skip": page.offset}, {"$limit": page.size},
            {"$project": {**profile_fields, **user_fields}},
        ])
        rows = await User.get_pymongo_collection().aggregate(pipeline).to_list(length=page.size)
        return [(Patient.model_validate(row["profile"]), SimpleNamespace(**row)) for row in rows]

    @staticmethod
    async def search_doctors(search: str, page: PageWindow, *, active_only: bool = False,
                             home_visits_only: bool = False,
                             include_email_in_search: bool = True) -> list[tuple[Doctor, SimpleNamespace]]:
        match: dict = {"role": "doctor"}
        if active_only:
            match["is_active"] = True
        pipeline = [
            {"$match": match},
            {"$lookup": {"from": "doctors", "localField": "_id", "foreignField": "user_id", "as": "profile"}},
            {"$unwind": "$profile"},
        ]
        if search:
            pattern = re.escape(search)
            predicates = [
                {"full_name": {"$regex": pattern, "$options": "i"}},
                {"profile.specialization": {"$regex": pattern, "$options": "i"}},
                {"profile.qualifications": {"$regex": pattern, "$options": "i"}},
                {"profile.specialties": {"$regex": pattern, "$options": "i"}},
            ]
            if include_email_in_search:
                predicates.insert(1, {"email": {"$regex": pattern, "$options": "i"}})
            pipeline.append({"$match": {"$or": predicates}})
        if home_visits_only:
            pipeline.append({"$match": {"profile.accepts_home_visits": {"$ne": False}}})
        pipeline.extend([
            {"$sort": {"full_name": 1, "_id": 1}},
            {"$skip": page.offset}, {"$limit": page.size},
            {"$project": {
                "_id": 1,
                "email": 1,
                "full_name": 1,
                "profile._id": 1,
                "profile.user_id": 1,
                "profile.specialization": 1,
                "profile.profile_image": 1,
                "profile.bio": 1,
                "profile.qualifications": 1,
                "profile.years_experience": 1,
                "profile.specialties": 1,
                "profile.linkedin_url": 1,
                "profile.website_url": 1,
                "profile.is_active_today": 1,
                "profile.accepts_home_visits": 1,
            }},
        ])
        rows = await User.get_pymongo_collection().aggregate(pipeline).to_list(length=page.size)
        return [(Doctor.model_validate(row["profile"]), SimpleNamespace(**row)) for row in rows]

    @staticmethod
    async def get_doctor_by_user_id(user_id: str) -> Optional[Doctor]:
        return await Doctor.find_one(
            Doctor.user_id == PydanticObjectId(user_id)
        )

    @staticmethod
    async def get_patient_by_user_id(user_id: str) -> Optional[Patient]:
        return await Patient.find_one(
            Patient.user_id == PydanticObjectId(user_id)
        )

    @staticmethod
    async def get_doctor_by_id(id: str) -> Optional[Doctor]:
        try:
            return await Doctor.get(PydanticObjectId(id))
        except (ValueError, TypeError):
            return None

    @staticmethod
    async def get_patient_by_id(id: str) -> Optional[Patient]:
        try:
            return await Patient.get(PydanticObjectId(id))
        except (ValueError, TypeError):
            return None

    @staticmethod
    async def create_doctor(doctor: Doctor) -> Doctor:
        return await doctor.insert()

    @staticmethod
    async def create_patient(patient: Patient) -> Patient:
        return await patient.insert()

    @staticmethod
    async def save_patient(patient: Patient) -> Patient:
        return await patient.save()

    @staticmethod
    async def save_doctor(doctor: Doctor) -> Doctor:
        return await doctor.save()

    @staticmethod
    async def list_doctors() -> List[Doctor]:
        return await Doctor.find().to_list()

    @staticmethod
    async def list_patients() -> List[Patient]:
        return await Patient.find().to_list()

    @staticmethod
    async def list_page_patients(page: PageWindow) -> List[Patient]:
        return await Patient.find().sort("+_id").skip(page.offset).limit(page.size).to_list()
