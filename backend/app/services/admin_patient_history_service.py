from fastapi import HTTPException, status
from datetime import date
from types import SimpleNamespace

from app.models.doctor import Doctor
from app.models.user import User

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
from app.core.pagination import PageWindow


class AdminPatientHistoryService:
    @staticmethod
    async def get_patient_history(
        patient_id: str, page: PageWindow | None = None,
        start_date: date | None = None, end_date: date | None = None,
    ) -> AdminPatientHistoryOut:
        patient = await ProfileRepository.get_patient_by_id(patient_id)
        user = await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        if not patient or not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient history not found",
            )

        appointment_rows = (
            await AppointmentRepository.list_page_by_patient_id(
                patient_id, page, start_date=start_date, end_date=end_date,
            ) if page else await AppointmentRepository.list_by_patient_id(patient_id)
        )
        if page and appointment_rows:
            doctor_ids = list({appointment.doctor_id for appointment in appointment_rows})
            doctor_rows = await Doctor.get_pymongo_collection().find(
                {"_id": {"$in": doctor_ids}}, {"user_id": 1},
            ).to_list(length=len(doctor_ids))
            doctor_map = {row["_id"]: SimpleNamespace(id=row["_id"], user_id=row["user_id"])
                          for row in doctor_rows}
            doctor_user_ids = list({row["user_id"] for row in doctor_rows})
            doctor_user_rows = await User.get_pymongo_collection().find(
                {"_id": {"$in": doctor_user_ids}}, {"full_name": 1},
            ).to_list(length=len(doctor_user_ids)) if doctor_user_ids else []
            doctor_user_map = {row["_id"]: SimpleNamespace(full_name=row["full_name"])
                               for row in doctor_user_rows}
            appointments = []
            for appointment in appointment_rows:
                doctor = doctor_map.get(appointment.doctor_id)
                if not doctor:
                    raise HTTPException(status_code=404, detail="Related patient or doctor not found")
                doctor_user = doctor_user_map.get(doctor.user_id)
                if not doctor_user:
                    raise HTTPException(status_code=404, detail="Related user not found")
                appointments.append(await AppointmentService._format_appointment(
                    appointment, patient=patient, doctor=doctor,
                    patient_user=user, doctor_user=doctor_user,
                ))
        else:
            appointments = [await AppointmentService._format_appointment(appointment)
                            for appointment in appointment_rows]

        report_rows = (
            await LabRequestRepository.list_page_released_for_patients(
                [patient_id], page, start_date=start_date, end_date=end_date,
            ) if page else await LabRequestRepository.list_released_for_patients([patient_id])
        )
        reports = [
            (await LabRequestService._format_report(report, include_patient_name=False)).model_copy(
                update={"patient_name": user.full_name},
            ) if page else await LabRequestService._format_report(report, include_patient_name=True)
            for report in report_rows
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
