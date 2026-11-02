import re
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException, UploadFile, status
from starlette.datastructures import Headers

from app.core.config import settings
from app.core.pagination import PageWindow
from app.core.lab_demo import LAB_DEMO_REHEARSAL_TAG
from app.models.lab_request import LabRequest
from app.models.patient import Patient
from app.models.user import User
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
from app.services.clinical_report_storage import LabReportStorage


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
    async def list_own(
        user_id: str, page: PageWindow | None = None, recent_updates: bool = False,
    ) -> list[LabRequestOut]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            return []
        requests = (
            await LabRequestRepository.list_page_for_patient(
                str(patient.id), page, recent_updates=recent_updates,
            ) if recent_updates else await LabRequestRepository.list_page_for_patient(str(patient.id), page)
            if page is not None else await LabRequestRepository.list_for_patient(str(patient.id))
        )
        if page is not None:
            return await LabRequestService._format_page(requests)
        return [await LabRequestService._format(item) for item in requests]

    @staticmethod
    async def list_admin(page: PageWindow | None = None) -> list[LabRequestOut]:
        requests = (
            await LabRequestRepository.list_page_all(page)
            if page is not None else await LabRequestRepository.list_all()
        )
        if page is not None:
            return await LabRequestService._format_page(requests)
        return [await LabRequestService._format(item) for item in requests]

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
    async def list_assigned(
        user_id: str, page: PageWindow | None = None,
    ) -> list[LaboratorianLabRequestOut]:
        requests = (
            await LabRequestRepository.list_page_for_laboratorian(user_id, page)
            if page is not None else await LabRequestRepository.list_for_laboratorian(user_id)
        )
        if page is not None:
            patients, patient_users, _assigned_users = await LabRequestService._page_identity_maps(
                requests, include_patient_email=False, include_assignee=False,
            )
            result = []
            for request in requests:
                patient = patients.get(request.patient_id)
                patient_user = patient_users.get(patient.user_id) if patient else None
                if not patient or not patient_user:
                    raise HTTPException(status_code=404, detail="Related patient account not found")
                result.append(await LabRequestService._format_for_laboratorian(
                    request, patient=patient, patient_user=patient_user,
                ))
            return result
        return [await LabRequestService._format_for_laboratorian(item) for item in requests]

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
        if Path(original_name).suffix.casefold() != ".pdf":
            raise HTTPException(status_code=415, detail="Only PDF laboratory reports are accepted")

        safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(original_name).name).strip(" ._")
        if not safe_name:
            safe_name = "laboratory-report.pdf"
        previous_key = request.report_storage_key
        upload = UploadFile(
            BytesIO(content),
            size=len(content),
            filename=safe_name,
            headers=Headers({"content-type": "application/pdf"}),
        )
        storage_key = await LabReportStorage.store_pdf(
            upload,
            uploaded_by_user_id=laboratorian_id,
        )
        try:
            changed = await LabRequestRepository.save_finalized_report(
                request_id,
                laboratorian_id,
                expected_storage_key=previous_key,
                storage_key=storage_key,
                file_name=safe_name,
                content_type="application/pdf",
                size_bytes=len(content),
            )
        except Exception:
            LabReportStorage.delete(storage_key)
            raise
        if not changed:
            LabReportStorage.delete(storage_key, reason_code="concurrent_database_change")
            raise HTTPException(status_code=409, detail="The laboratory order changed; refresh and try again")
        if previous_key and previous_key != storage_key:
            LabReportStorage.delete(previous_key, reason_code="superseded")
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
            path = LabReportStorage.resolve(storage_key)
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
    async def list_patient_released_reports(
        user_id: str, page: PageWindow | None = None,
    ) -> list[LabReportOut]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            return []
        requests = (
            await LabRequestRepository.list_page_released_for_patients([str(patient.id)], page)
            if page is not None else await LabRequestRepository.list_released_for_patients([str(patient.id)])
        )
        return [await LabRequestService._format_report(item) for item in requests]

    @staticmethod
    async def list_doctor_released_reports(
        user_id: str, page: PageWindow | None = None,
    ) -> list[LabReportOut]:
        doctor = await ProfileRepository.get_doctor_by_user_id(user_id)
        if not doctor:
            return []
        if page is not None:
            requests = await LabRequestRepository.list_page_released_for_doctor(
                str(doctor.id), page,
            )
        else:
            appointments = [
                item for item in await AppointmentRepository.list_by_doctor_id(str(doctor.id))
                if not getattr(item, "doctor_assignment_pending", False)
            ]
            patient_ids = list(dict.fromkeys(str(item.patient_id) for item in appointments))
            requests = await LabRequestRepository.list_released_for_patients(patient_ids)
        if page is None or not requests:
            return [await LabRequestService._format_report(item, include_patient_name=True) for item in requests]
        patient_ids = list({item.patient_id for item in requests})
        patients = await Patient.get_pymongo_collection().find(
            {"_id": {"$in": patient_ids}}, {"user_id": 1},
        ).to_list(length=len(patient_ids))
        user_ids = list({row["user_id"] for row in patients})
        users = await User.get_pymongo_collection().find(
            {"_id": {"$in": user_ids}}, {"full_name": 1},
        ).to_list(length=len(user_ids)) if user_ids else []
        patient_users = {row["_id"]: row["user_id"] for row in patients}
        names = {row["_id"]: row["full_name"] for row in users}
        return [
            (await LabRequestService._format_report(item)).model_copy(
                update={"patient_name": names.get(patient_users.get(item.patient_id))},
            ) for item in requests
        ]

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
                allowed = await AppointmentRepository.has_assigned_patient(
                    str(doctor.id), str(request.patient_id),
                )
        if not allowed:
            raise HTTPException(status_code=404, detail="Laboratory report not found")
        storage_key = Path(request.report_storage_key).name
        if storage_key != request.report_storage_key:
            raise HTTPException(status_code=404, detail="Laboratory report not found")
        try:
            path = LabReportStorage.resolve(storage_key)
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
            raise HTTPException(status_code=404, detail="Laboratory request not found")
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
    async def _page_identity_maps(
        requests: list,
        *,
        include_patient_email: bool,
        include_assignee: bool,
    ):
        """Fetch the minimum identities needed to format one authorized lab page."""
        if not requests:
            return {}, {}, {}
        patient_ids = list({request.patient_id for request in requests})
        patients = await Patient.get_pymongo_collection().find(
            {"_id": {"$in": patient_ids}}, {"user_id": 1, "phone": 1},
        ).to_list(length=len(patient_ids))
        patient_user_ids = list({row["user_id"] for row in patients})
        patient_user_projection = {"full_name": 1}
        if include_patient_email:
            patient_user_projection["email"] = 1
        patient_users = await User.get_pymongo_collection().find(
            {"_id": {"$in": patient_user_ids}}, patient_user_projection,
        ).to_list(length=len(patient_user_ids)) if patient_user_ids else []
        assigned_ids = list({
            request.assigned_laboratorian_user_id
            for request in requests
            if include_assignee and request.assigned_laboratorian_user_id
        })
        assigned_users = await User.get_pymongo_collection().find(
            {"_id": {"$in": assigned_ids}}, {"full_name": 1},
        ).to_list(length=len(assigned_ids)) if assigned_ids else []
        return (
            {row["_id"]: SimpleNamespace(
                id=row["_id"], user_id=row["user_id"], phone=row.get("phone"),
            ) for row in patients},
            {row["_id"]: SimpleNamespace(
                id=row["_id"], full_name=row["full_name"], email=row.get("email"),
            ) for row in patient_users},
            {row["_id"]: SimpleNamespace(id=row["_id"], full_name=row["full_name"])
             for row in assigned_users},
        )

    @staticmethod
    async def _format_page(requests: list) -> list[LabRequestOut]:
        if not requests:
            return []
        patients, patient_users, assigned_users = await LabRequestService._page_identity_maps(
            requests, include_patient_email=True, include_assignee=True,
        )
        result = []
        for request in requests:
            patient = patients.get(request.patient_id)
            patient_user = patient_users.get(patient.user_id) if patient else None
            if not patient or not patient_user:
                raise HTTPException(status_code=404, detail="Related patient account not found")
            assigned_user = assigned_users.get(request.assigned_laboratorian_user_id)
            result.append(await LabRequestService._format(
                request,
                patient=patient,
                user=patient_user,
                assigned_user=assigned_user,
                assigned_user_loaded=True,
            ))
        return result

    @staticmethod
    async def _format(
        request: LabRequest,
        *,
        patient=None,
        user=None,
        assigned_user=None,
        assigned_user_loaded: bool = False,
    ) -> LabRequestOut:
        patient = patient if patient is not None else await ProfileRepository.get_patient_by_id(str(request.patient_id))
        user = user if user is not None else await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        if not patient or not user:
            raise HTTPException(status_code=404, detail="Related patient account not found")
        if request.assigned_laboratorian_user_id and not assigned_user_loaded:
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
    async def _format_for_laboratorian(
        request: LabRequest, *, patient=None, patient_user=None,
    ) -> LaboratorianLabRequestOut:
        patient = patient if patient is not None else await ProfileRepository.get_patient_by_id(str(request.patient_id))
        patient_user = (
            patient_user if patient_user is not None
            else await UserRepository.get_by_id(str(patient.user_id)) if patient else None
        )
        if not patient or not patient_user:
            raise HTTPException(status_code=404, detail="Related patient account not found")
        return LaboratorianLabRequestOut(
            id=str(request.id),
            patient_name=patient_user.full_name,
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
