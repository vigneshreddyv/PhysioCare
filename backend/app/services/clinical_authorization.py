from beanie import PydanticObjectId

from app.models.patient import Patient
from app.repositories.profile_repository import ProfileRepository


async def require_doctor_patient_access(doctor_user_id: str, patient_id: str):
    """Return the doctor profile when the patient is assigned to that doctor."""
    doctor = await ProfileRepository.get_doctor_by_user_id(doctor_user_id)
    patient = await Patient.get(PydanticObjectId(patient_id))
    if not doctor or not patient or str(patient.primary_doctor_id) != str(doctor.id):
        raise PermissionError("Doctor is not authorized to access this patient.")
    return doctor
