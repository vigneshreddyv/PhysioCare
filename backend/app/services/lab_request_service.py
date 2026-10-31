import asyncio
import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.lab_demo import LAB_DEMO_REHEARSAL_TAG
from app.core.lab_demo_storage import report_file_path, secure_report_storage
from app.models.lab_request import LabRequest
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.lab_request import (
    LabReportOut,
    LabRequestCreate,
    LabRequestOut,
    LaboratorianLabRequestOut,
)


class LabRequestService:
    @staticmethod
    async def create(user_id: str, schema: LabRequestCreate, submission_key: str | None = None) -> LabRequestOut:
        if schema.demo_rehearsal_tag is not None and (
            not settings.LAB_DEMO_MODE
            or schema.demo_rehearsal_tag != LAB_DEMO_REHEARSAL_TAG
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Demo tagging is available only in the isolated laboratory demo",
            )
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found")
        if (
            schema.demo_rehearsal_tag is not None
            and patient.demo_rehearsal_tag != schema.demo_rehearsal_tag
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the tagged demo patient may create a tagged demo request",
            )
        if schema.mode == "home_collection" and schema.city.casefold() != settings.DEMO_HOME_SERVICE_CITY.casefold():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Home laboratory collection is currently limited to {settings.DEMO_HOME_SERVICE_CITY} city",
            )
        request = await LabRequestRepository.create_idempotent(LabRequest(
            patient_id=patient.id,
            submission_key=submission_key,
            mode=schema.mode,
            selected_tests=schema.selected_tests,
            home_address=schema.home_address,
            city=settings.DEMO_HOME_SERVICE_CITY if schema.mode == "home_collection" else None,
            demo_rehearsal_tag=schema.demo_rehearsal_tag,
        ))
        if schema.mode == "home_collection" and schema.save_address:
            patient.saved_home_address = schema.home_address
            await ProfileRepository.save_patient(patient)
        return await LabRequestService._format(request)

    @staticmethod
    async def list_own(user_id: str) -> list[LabRequestOut]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            return []
        return [await LabRequestService._format(item) for item in await LabRequestRepository.list_for_patient(str(patient.id))]

    @staticmethod
    async def list_admin() -> list[LabRequestOut]:
        return [await LabRequestService._format(item) for item in await LabRequestRepository.list_all()]

    @staticmethod
    async def assign_laboratorian(request_id: str, laboratorian_id: str, admin_id: str) -> LabRequestOut:
        request = await LabRequestRepository.get(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Laboratory request not found")
        laboratorian = await UserRepository.get_by_id(laboratorian_id)
        if not laboratorian or not laboratorian.is_active or laboratorian.role != "laboratorian":
            raise HTTPException(status_code=422, detail="Choose an active Laboratorian account")
        if request.report_status == "released":
            raise HTTPException(status_code=409, detail="A released report cannot be reassigned")
        if request.status != "approved_for_coordination":
            raise HTTPException(status_code=409, detail="Approve the laboratory request before assigning it")
        changed = await LabRequestRepository.assign_laboratorian(request_id, laboratorian_id, admin_id)
        if not changed and str(request.assigned_laboratorian_user_id or "") != laboratorian_id:
            raise HTTPException(status_code=409, detail="The laboratory assignment changed; refresh and try again")
        return await LabRequestService._format(await LabRequestRepository.get(request_id))

    @staticmethod
    async def list_assigned(user_id: str) -> list[LaboratorianLabRequestOut]:
        return [
            await LabRequestService._format_for_laboratorian(item)
            for item in await LabRequestRepository.list_for_laboratorian(user_id)
        ]

    @staticmethod
    async def upload_finalized_report(
        request_id: str,
        laboratorian_id: str,
        content: bytes,
        original_name: str,
    ) -> LaboratorianLabRequestOut:
        request = await LabRequestRepository.get(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Laboratory request not found")
        if str(request.assigned_laboratorian_user_id or "") != laboratorian_id:
            raise HTTPException(status_code=403, detail="You may prepare reports only for orders assigned to you")
        if request.report_status == "released":
            raise HTTPException(status_code=409, detail="A released report cannot be replaced")
        if not content or len(content) > settings.LAB_REPORT_MAX_BYTES:
            raise HTTPException(status_code=422, detail="Choose a PDF within the configured file-size limit")
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="Only PDF laboratory reports are accepted")

        safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(original_name).name).strip(" ._")
        if not safe_name.lower().endswith(".pdf"):
            safe_name = f"{safe_name or 'laboratory-report'}.pdf"
        storage_key = f"{uuid4().hex}.pdf"
        storage_root = secure_report_storage() if settings.LAB_DEMO_MODE else Path(settings.LAB_REPORT_STORAGE_DIR)
        storage_path = report_file_path(storage_key)
        previous_key = request.report_storage_key

        def write_private_file():
            storage_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(storage_root, 0o700)
            storage_path.write_bytes(content)
            os.chmod(storage_path, 0o600)

        await asyncio.to_thread(write_private_file)
        changed = await LabRequestRepository.save_finalized_report(
            request_id,
            laboratorian_id,
            expected_storage_key=previous_key,
            storage_key=storage_key,
            file_name=safe_name,
            content_type="application/pdf",
            size_bytes=len(content),
        )
        if not changed:
            await asyncio.to_thread(storage_path.unlink, missing_ok=True)
            raise HTTPException(status_code=409, detail="The laboratory order changed; refresh and try again")
        if previous_key and previous_key != storage_key:
            previous_path = storage_root / Path(previous_key).name
            try:
                await asyncio.to_thread(previous_path.unlink, missing_ok=True)
            except OSError:
                pass
        return await LabRequestService._format_for_laboratorian(await LabRequestRepository.get(request_id))

    @staticmethod
    async def publish_report(request_id: str, admin_id: str) -> LabRequestOut:
        request = await LabRequestRepository.get(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Laboratory request not found")
        if request.report_status == "released":
            return await LabRequestService._format(request)
        if request.report_status != "awaiting_publication" or not request.report_storage_key:
            raise HTTPException(
                status_code=409,
                detail="A finalized report must be uploaded before it can be published",
            )
        storage_key = Path(request.report_storage_key).name
        if storage_key != request.report_storage_key:
            raise HTTPException(status_code=409, detail="The finalized report file is unavailable")
        try:
            path = report_file_path(storage_key)
        except (RuntimeError, ValueError):
            raise HTTPException(status_code=409, detail="The finalized report file is unavailable") from None
        if not path.is_file():
            raise HTTPException(status_code=409, detail="The finalized report file is unavailable")
        changed = await LabRequestRepository.publish_report(
            request_id,
            admin_id,
            expected_storage_key=storage_key,
        )
        if not changed:
            current = await LabRequestRepository.get(request_id)
            if current and current.report_status == "released":
                return await LabRequestService._format(current)
            raise HTTPException(
                status_code=409,
                detail="The report changed before publication; refresh and review the latest file",
            )
        return await LabRequestService._format(await LabRequestRepository.get(request_id))

    @staticmethod
    async def list_patient_released_reports(user_id: str) -> list[LabReportOut]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            return []
        requests = await LabRequestRepository.list_released_for_patients([str(patient.id)])
        return [await LabRequestService._format_report(item) for item in requests]

    @staticmethod
    async def list_doctor_released_reports(user_id: str) -> list[LabReportOut]:
        doctor = await ProfileRepository.get_doctor_by_user_id(user_id)
        if not doctor:
            return []
        appointments = [
            item for item in await AppointmentRepository.list_by_doctor_id(str(doctor.id))
            if not getattr(item, "doctor_assignment_pending", False)
        ]
        patient_ids = list(dict.fromkeys(str(item.patient_id) for item in appointments))
        requests = await LabRequestRepository.list_released_for_patients(patient_ids)
        return [await LabRequestService._format_report(item, include_patient_name=True) for item in requests]

    @staticmethod
    async def get_report_file(request_id: str, user_id: str, role: str) -> tuple[Path, str]:
        request = await LabRequestRepository.get(request_id)
        if not request or not request.report_storage_key:
            raise HTTPException(status_code=404, detail="Laboratory report not found")
        # Draft existence is private workflow state. Patients and doctors should
        # receive the same response as they would for a missing report rather
        # than being able to infer that an unreleased file exists.
        if role in {"patient", "doctor"} and request.report_status != "released":
            raise HTTPException(status_code=404, detail="Laboratory report not found")
        allowed = False
        if role == "laboratorian":
            allowed = str(request.assigned_laboratorian_user_id or "") == user_id
        elif role == "admin":
            allowed = True
        elif role == "patient" and request.report_status == "released":
            patient = await ProfileRepository.get_patient_by_user_id(user_id)
            allowed = bool(patient and str(request.patient_id) == str(patient.id))
        elif role == "doctor" and request.report_status == "released":
            doctor = await ProfileRepository.get_doctor_by_user_id(user_id)
            if doctor:
                appointments = await AppointmentRepository.list_by_doctor_id(str(doctor.id))
                allowed = any(
                    str(item.patient_id) == str(request.patient_id)
                    and not getattr(item, "doctor_assignment_pending", False)
                    for item in appointments
                )
        if not allowed:
            raise HTTPException(status_code=403, detail="You do not have access to this laboratory report")
        storage_key = Path(request.report_storage_key).name
        if storage_key != request.report_storage_key:
            raise HTTPException(status_code=404, detail="Laboratory report not found")
        try:
            path = report_file_path(storage_key)
        except (RuntimeError, ValueError):
            raise HTTPException(status_code=404, detail="Laboratory report not found") from None
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Laboratory report file is unavailable")
        return path, request.report_file_name or "laboratory-report.pdf"

    @staticmethod
    async def review(request_id: str, admin_id: str, target: str) -> LabRequestOut:
        request = await LabRequestRepository.get(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Laboratory request not found")
        if request.status != target:
            changed = await LabRequestRepository.transition(request_id, ["pending_clinic_confirmation"], target, admin_id)
            if not changed:
                raise HTTPException(status_code=409, detail="Only pending laboratory requests can be reviewed")
            request = await LabRequestRepository.get(request_id)
        return await LabRequestService._format(request)

    @staticmethod
    async def withdraw(request_id: str, user_id: str) -> LabRequestOut:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        request = await LabRequestRepository.get(request_id)
        if not patient or not request:
            raise HTTPException(status_code=404, detail="Laboratory request not found")
        if str(request.patient_id) != str(patient.id):
            raise HTTPException(status_code=403, detail="You may withdraw only your own laboratory requests")
        if request.status != "withdrawn":
            changed = await LabRequestRepository.transition(
                request_id, ["pending_clinic_confirmation", "approved_for_coordination"], "withdrawn"
            )
            if not changed:
                raise HTTPException(status_code=409, detail="This laboratory request can no longer be withdrawn online")
            request = await LabRequestRepository.get(request_id)
        return await LabRequestService._format(request)

    @staticmethod
    def _message(value: str) -> str:
        return {
            "pending_clinic_confirmation": "Request received for clinic review. No collection or clinic visit is confirmed, and no payment has been taken.",
            "approved_for_coordination": "Approved for coordination only. The clinic still needs to confirm timing and availability; no payment has been taken.",
            "declined": "The clinic could not accept this request. No booking or charge was created.",
            "withdrawn": "This request was withdrawn. No booking or charge was created.",
        }.get(value, "This is not a confirmed laboratory booking.")

    @staticmethod
    async def _format(request: LabRequest) -> LabRequestOut:
        patient = await ProfileRepository.get_patient_by_id(str(request.patient_id))
        user = await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        if not patient or not user:
            raise HTTPException(status_code=404, detail="Related patient account not found")
        assigned_user = None
        if request.assigned_laboratorian_user_id:
            assigned_user = await UserRepository.get_by_id(str(request.assigned_laboratorian_user_id))
        return LabRequestOut(
            id=str(request.id), patient_id=str(patient.id), patient_name=user.full_name,
            patient_email=user.email, patient_phone=patient.phone, mode=request.mode,
            selected_tests=request.selected_tests, home_address=request.home_address, city=request.city,
            status=request.status, created_at=request.created_at, updated_at=request.updated_at,
            confirmation_message=LabRequestService._message(request.status),
            assigned_laboratorian_user_id=str(request.assigned_laboratorian_user_id) if request.assigned_laboratorian_user_id else None,
            assigned_laboratorian_name=assigned_user.full_name if assigned_user else None,
            report_status=request.report_status,
            report_file_name=request.report_file_name,
            report_uploaded_at=request.report_uploaded_at,
            report_released_at=request.report_released_at,
        )

    @staticmethod
    async def _format_for_laboratorian(request: LabRequest) -> LaboratorianLabRequestOut:
        patient = await ProfileRepository.get_patient_by_id(str(request.patient_id))
        user = await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        if not patient or not user:
            raise HTTPException(status_code=404, detail="Related patient account not found")
        return LaboratorianLabRequestOut(
            id=str(request.id),
            patient_name=user.full_name,
            patient_phone=patient.phone,
            mode=request.mode,
            selected_tests=request.selected_tests,
            home_address=request.home_address,
            city=request.city,
            status=request.status,
            report_status=request.report_status,
            report_file_name=request.report_file_name,
            report_uploaded_at=request.report_uploaded_at,
            created_at=request.created_at,
        )

    @staticmethod
    async def _format_report(request: LabRequest, include_patient_name: bool = False) -> LabReportOut:
        patient_name = None
        if include_patient_name:
            patient = await ProfileRepository.get_patient_by_id(str(request.patient_id))
            user = await UserRepository.get_by_id(str(patient.user_id)) if patient else None
            patient_name = user.full_name if user else None
        return LabReportOut(
            request_id=str(request.id),
            patient_name=patient_name,
            selected_tests=request.selected_tests,
            report_status=request.report_status,
            report_file_name=request.report_file_name,
            report_uploaded_at=request.report_uploaded_at,
            report_released_at=request.report_released_at,
        )
