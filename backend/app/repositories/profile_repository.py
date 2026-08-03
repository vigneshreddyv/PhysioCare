from typing import List, Optional
from beanie import PydanticObjectId
from app.models.doctor import Doctor
from app.models.patient import Patient

class ProfileRepository:
    @staticmethod
    async def get_doctor_by_user_id(user_id: str) -> Optional[Doctor]:
        return await Doctor.find_one({"user.$id": PydanticObjectId(user_id)}, fetch_links=True)

    @staticmethod
    async def get_patient_by_user_id(user_id: str) -> Optional[Patient]:
        return await Patient.find_one({"user.$id": PydanticObjectId(user_id)}, fetch_links=True)

    @staticmethod
    async def get_doctor_by_id(id: str) -> Optional[Doctor]:
        return await Doctor.get(PydanticObjectId(id), fetch_links=True)

    @staticmethod
    async def get_patient_by_id(id: str) -> Optional[Patient]:
        return await Patient.get(PydanticObjectId(id), fetch_links=True)

    @staticmethod
    async def create_doctor(doctor: Doctor) -> Doctor:
        return await doctor.insert()

    @staticmethod
    async def create_patient(patient: Patient) -> Patient:
        return await patient.insert()

    @staticmethod
    async def list_doctors() -> List[Doctor]:
        return await Doctor.find(fetch_links=True).to_list()

    @staticmethod
    async def list_patients() -> List[Patient]:
        return await Patient.find(fetch_links=True).to_list()
