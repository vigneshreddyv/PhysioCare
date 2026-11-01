import logging
from typing import List, Optional
from beanie import PydanticObjectId
from bson.errors import InvalidId
from datetime import datetime
from app.models.report import Report
from app.models.patient import Patient
from app.repositories.laboratory_booking_repository import LaboratoryBookingRepository
from app.repositories.report_repository import BookingClaimFailed, ReportRepository
from app.services.clinical_authorization import require_doctor_patient_access


logger = logging.getLogger(__name__)


class ReportTargetUnavailable(Exception):
    """A patient or booking is missing, malformed, or outside actor scope."""


class ReportBookingConflict(Exception):
    """A booking cannot be used for this report in its current state."""


class ReportService:
    @staticmethod
    async def validate_create_request(
        *,
        patient_id: str,
        booking_id: Optional[str],
        category: str,
        actor_user_id: str,
        actor_role: str,
    ):
        try:
            patient_object_id = PydanticObjectId(patient_id)
        except (InvalidId, ValueError, TypeError):
            raise ReportTargetUnavailable from None

        if actor_role == "doctor":
            try:
                await require_doctor_patient_access(actor_user_id, patient_id)
            except PermissionError:
                raise ReportTargetUnavailable from None
        elif actor_role == "admin":
            if not await Patient.get(patient_object_id):
                raise ReportTargetUnavailable
        else:
            raise ReportTargetUnavailable

        if not booking_id:
            return None
        if category.strip().casefold() != "diagnostic":
            raise ReportBookingConflict("Laboratory bookings may be linked only to diagnostic reports")
        try:
            booking = await LaboratoryBookingRepository.get_by_id(booking_id)
        except (InvalidId, ValueError, TypeError):
            raise ReportTargetUnavailable from None
        if not booking or str(booking.patient_id) != str(patient_object_id):
            raise ReportTargetUnavailable
        if (getattr(booking, "status", None) or "pending_payment") != "confirmed":
            raise ReportBookingConflict("The laboratory booking is not ready for a report")
        return booking

    @staticmethod
    async def create_report(
        patient_id: str,
        booking_id: Optional[str],
        title: str,
        category: str,
        date: datetime,
        description: str,
        therapist: str,
        content: dict,
        file_path: Optional[str] = None,
        *,
        actor_user_id: str,
        actor_role: str,
    ) -> Report:
        booking = await ReportService.validate_create_request(
            patient_id=patient_id,
            booking_id=booking_id,
            category=category,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        report = Report(
            patient_id=PydanticObjectId(patient_id),
            booking_id=PydanticObjectId(booking_id) if booking_id else None,
            title=title,
            category=category,
            date=date,
            description=description,
            therapist=therapist,
            content=content,
            file_path=file_path
        )
        if booking is not None:
            try:
                created_report = await ReportRepository.create_for_confirmed_booking(report)
            except BookingClaimFailed:
                raise ReportBookingConflict(
                    "The laboratory booking changed before report creation"
                ) from None
            booking.status = "completed"
        else:
            created_report = await ReportRepository.create(report)

        if booking is not None:
            from app.services.laboratory_service import LaboratoryService
            try:
                await LaboratoryService.notify_booking_status(booking, "completed")
            except Exception:
                logger.warning(
                    "Clinical report follow-up failed: operation=lab_status_notification"
                )

        # Notify patient
        try:
            patient = await Patient.get(PydanticObjectId(patient_id))
            if patient:
                from app.services.notification_service import NotificationService
                await NotificationService.create_notification(
                    recipient_user_id=str(patient.user_id),
                    title="Clinical Report Ready",
                    message=f"Your clinical report '{title}' is ready to view.",
                    notification_type="clinical",
                    related_entity_id=str(created_report.id)
                )
        except Exception:
            logger.warning(
                "Clinical report follow-up failed: operation=patient_notification"
            )

        return created_report

    @staticmethod
    async def get_reports_by_patient_id(patient_id: str) -> List[Report]:
        return await ReportRepository.get_by_patient_id(patient_id)

    @staticmethod
    async def get_report_by_id(report_id: str, patient_id: str) -> Optional[Report]:
        report = await ReportRepository.get_by_id(report_id)
        if not report:
            return None
        if str(report.patient_id) != patient_id:
            return None
        return report
