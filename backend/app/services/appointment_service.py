from datetime import datetime
from fastapi import HTTPException, status
from typing import List, Optional
from app.models.appointment import Appointment
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentOut

class AppointmentService:
    @staticmethod
    async def create_appointment(user_id: str, schema: AppointmentCreate) -> AppointmentOut:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found for current user"
            )
            
        doctor = await ProfileRepository.get_doctor_by_id(schema.doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )
            
        appointment = Appointment(
            patient=patient,
            doctor=doctor,
            appointment_date=schema.appointment_date,
            time_slot=schema.time_slot,
            reason=schema.reason
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
            
        return [await AppointmentService._format_appointment(a) for a in appointments]

    @staticmethod
    async def update_appointment(appointment_id: str, schema: AppointmentUpdate) -> AppointmentOut:
        appointment = await AppointmentRepository.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
            
        if schema.status is not None:
            appointment.status = schema.status
        if schema.billing_status is not None:
            appointment.billing_status = schema.billing_status
        if schema.billing_amount is not None:
            appointment.billing_amount = schema.billing_amount
            
        await appointment.save()
        # Refetch to ensure links are loaded
        updated = await AppointmentRepository.get_by_id(appointment_id)
        return await AppointmentService._format_appointment(updated)

    @staticmethod
    async def _format_appointment(a: Appointment) -> AppointmentOut:
        return AppointmentOut(
            id=str(a.id),
            patient_id=str(a.patient.id),
            patient_name=a.patient.user.full_name,
            doctor_id=str(a.doctor.id),
            doctor_name=a.doctor.user.full_name,
            appointment_date=a.appointment_date,
            time_slot=a.time_slot,
            reason=a.reason,
            status=a.status,
            billing_status=a.billing_status,
            billing_amount=a.billing_amount,
            created_at=a.created_at
        )
