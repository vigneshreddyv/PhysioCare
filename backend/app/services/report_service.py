from typing import List, Optional
from beanie import PydanticObjectId
from datetime import datetime
from app.models.report import Report
from app.repositories.report_repository import ReportRepository


class ReportService:
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
        file_path: Optional[str] = None
    ) -> Report:
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
        created_report = await ReportRepository.create(report)

        # Auto transition lab booking to completed on diagnostic report upload
        if booking_id and category.lower() == "diagnostic":
            from app.services.laboratory_service import LaboratoryService
            try:
                await LaboratoryService.update_booking_status(booking_id, "completed")
            except Exception as e:
                print(f"Failed to auto transition lab booking status: {e}")

        # Notify patient
        try:
            from app.models.patient import Patient
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
        except Exception as e:
            print(f"Failed to create report notification: {e}")

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
