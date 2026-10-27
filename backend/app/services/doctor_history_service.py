from fastapi import HTTPException, status

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointment import DoctorAppointmentOut
from app.schemas.doctor_history import DoctorPatientHistoryOut
from app.schemas.patient import DoctorPatientOut
from app.services.appointment_service import AppointmentService
from app.services.lab_request_service import LabRequestService


class DoctorHistoryService:
    @staticmethod
    async def get_assigned_patient_history(
        doctor_user_id: str,
        patient_id: str,
    ) -> DoctorPatientHistoryOut:
        doctor = await ProfileRepository.get_doctor_by_user_id(doctor_user_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned patient history not found",
            )

        appointments = [
            appointment
            for appointment in await AppointmentRepository.list_by_doctor_id(str(doctor.id))
            if str(appointment.patient_id) == patient_id
            and not getattr(appointment, "doctor_assignment_pending", False)
        ]
        if not appointments:
            # Use the same response for missing and unassigned records so the
            # route cannot disclose whether an unrelated patient exists.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned patient history not found",
            )

        patient = await ProfileRepository.get_patient_by_id(patient_id)
        user = await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        if not patient or not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned patient history not found",
            )

        formatted_appointments = []
        for appointment in appointments:
            formatted = await AppointmentService._format_appointment(appointment)
            formatted_appointments.append(DoctorAppointmentOut(**formatted.model_dump()))

        reports = [
            await LabRequestService._format_report(report, include_patient_name=True)
            for report in await LabRequestRepository.list_released_for_patients([patient_id])
        ]

        return DoctorPatientHistoryOut(
            patient=DoctorPatientOut(
                id=str(patient.id),
                full_name=user.full_name,
                phone=patient.phone,
                date_of_birth=patient.date_of_birth,
                gender=getattr(patient, "gender", None),
            ),
            appointments=formatted_appointments,
            reports=reports,
        )
