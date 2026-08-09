from datetime import datetime
from fastapi import HTTPException, status
from typing import List

from app.models.appointment import Appointment
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentOut,
)


class AppointmentService:

    @staticmethod
    async def create_appointment(
        user_id: str,
        schema: AppointmentCreate,
    ) -> AppointmentOut:

        patient = await ProfileRepository.get_patient_by_user_id(user_id)

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found",
            )

        doctor = await ProfileRepository.get_doctor_by_id(schema.doctor_id)

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found",
            )

    # Prevent booking appointments in the past
        if schema.appointment_date < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment date must be in the future",
            )

    # Doctor availability
        doctor_busy = await AppointmentRepository.doctor_has_slot(
            str(doctor.id),
            schema.appointment_date,
            schema.time_slot,
        )

        if doctor_busy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is not available for the selected time slot",
            )

    # Patient availability
        patient_busy = await AppointmentRepository.patient_has_slot(
            str(patient.id),
            schema.appointment_date,
            schema.time_slot,
        )

        if patient_busy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an appointment at this time",
            )

        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            service_type=schema.service_type,
            appointment_date=schema.appointment_date,
            time_slot=schema.time_slot,
            reason=schema.reason,
            symptoms=schema.symptoms,
            duration_days=schema.duration_days,
            pain_level=schema.pain_level,
            visit_address=schema.visit_address,
            status="approved",
            billing_status="pending",
            billing_amount=120.0,
            payment_method=schema.payment_method,
            payment_status="pending",
        )

        saved = await AppointmentRepository.create(appointment)

        return await AppointmentService._format_appointment(saved)

    @staticmethod
    async def list_appointments(user_id: str, role: str) -> List[AppointmentOut]:

        if role == "admin":
            appointments = await AppointmentRepository.list_all()

        elif role == "doctor":
            doctor = await ProfileRepository.get_doctor_by_user_id(user_id)

            if not doctor:
                return []

            appointments = await AppointmentRepository.list_by_doctor_id(str(doctor.id))

        elif role == "patient":
            patient = await ProfileRepository.get_patient_by_user_id(user_id)

            if not patient:
                return []

            appointments = await AppointmentRepository.list_by_patient_id(str(patient.id))

        else:
            appointments = []

        result = []

        for appointment in appointments:
            result.append(await AppointmentService._format_appointment(appointment))

        return result

    @staticmethod
    async def update_appointment(
        appointment_id: str,
        schema: AppointmentUpdate,
    ) -> AppointmentOut:

        appointment = await AppointmentRepository.get_by_id(appointment_id)

        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        if schema.status is not None:
            appointment.status = schema.status

        if schema.billing_status is not None:
            appointment.billing_status = schema.billing_status

        if schema.billing_amount is not None:
            appointment.billing_amount = schema.billing_amount

        await appointment.save()

        updated = await AppointmentRepository.get_by_id(appointment_id)

        return await AppointmentService._format_appointment(updated)

    @staticmethod
    async def _format_appointment(a: Appointment) -> AppointmentOut:

        patient = await ProfileRepository.get_patient_by_id(str(a.patient_id))
        doctor = await ProfileRepository.get_doctor_by_id(str(a.doctor_id))

        if not patient or not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Related patient or doctor not found",
            )

        patient_user = await UserRepository.get_by_id(str(patient.user_id))
        doctor_user = await UserRepository.get_by_id(str(doctor.user_id))

        if not patient_user or not doctor_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Related user not found",
            )

        return AppointmentOut(
            id=str(a.id),

            patient_id=str(patient.id),
            patient_name=patient_user.full_name,

            doctor_id=str(doctor.id),
            doctor_name=doctor_user.full_name,
            specialization=doctor.specialization,

            service_type=a.service_type,

            appointment_date=a.appointment_date,
            time_slot=a.time_slot,

            reason=a.reason,
            symptoms=a.symptoms,
            duration_days=a.duration_days,
            pain_level=a.pain_level,

            visit_address=a.visit_address,

            status=a.status,

            billing_status=a.billing_status,
            billing_amount=a.billing_amount,

            payment_method=a.payment_method,
            payment_status=a.payment_status,
            payment_id=a.payment_id,

            feedback_rating=a.feedback_rating,
            feedback_comment=a.feedback_comment,

            created_at=a.created_at,
        )