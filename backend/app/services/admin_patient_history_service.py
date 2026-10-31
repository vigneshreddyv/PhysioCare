from fastapi import HTTPException, status

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.doctor_history import (
    AdminPatientHistoryOut,
    PatientAdminEditAuditOut,
)
from app.services.appointment_service import AppointmentService
from app.services.lab_request_service import LabRequestService
from app.services.user_service import UserService


class AdminPatientHistoryService:
    @staticmethod
    async def get_patient_history(patient_id: str) -> AdminPatientHistoryOut:
        patient = await ProfileRepository.get_patient_by_id(patient_id)
        user = await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        if not patient or not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient history not found",
            )

        appointments = [
            await AppointmentService._format_appointment(appointment)
            for appointment in await AppointmentRepository.list_by_patient_id(patient_id)
        ]
        reports = [
            await LabRequestService._format_report(report, include_patient_name=True)
            for report in await LabRequestRepository.list_released_for_patients([patient_id])
        ]
        audit = [
            PatientAdminEditAuditOut(
                actor_user_id=str(event.actor_user_id),
                changed_fields=list(event.changed_fields),
                changed_at=event.changed_at,
            )
            for event in reversed(getattr(patient, "admin_edit_audit", []))
        ]

        return AdminPatientHistoryOut(
            patient=UserService._patient_out(patient, user),
            appointments=appointments,
            reports=reports,
            profile_audit=audit,
        )
