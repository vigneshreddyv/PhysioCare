from beanie import PydanticObjectId
from bson.errors import InvalidId

from app.models.patient import Patient
from app.repositories.profile_repository import ProfileRepository


async def require_doctor_patient_access(doctor_user_id: str, patient_id: str):
    """Return the doctor profile when the patient is assigned to that doctor."""
    doctor = await ProfileRepository.get_doctor_by_user_id(doctor_user_id)
    try:
        patient_object_id = PydanticObjectId(patient_id)
    except (InvalidId, ValueError, TypeError):
        raise PermissionError("Clinical resource is not available.") from None
    patient = await Patient.get(patient_object_id)
    if not doctor or not patient or str(patient.primary_doctor_id) != str(doctor.id):
        raise PermissionError("Clinical resource is not available.")
    return doctor
