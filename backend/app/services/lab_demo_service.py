from app.core.lab_demo import LAB_DEMO_REHEARSAL_TAG
from app.core.config import settings
from app.models.auth_session import AuthSession
from app.models.lab_request import LabRequest
from app.models.patient import Patient
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import StaffCreate, UserRegister
from app.services.auth_service import AuthService


class LabDemoService:
    @staticmethod
    def require_isolated_mode() -> None:
        settings.validate_lab_demo_isolation()
        if not settings.LAB_DEMO_MODE:
            raise RuntimeError("This operation requires the isolated laboratory demo configuration")

    @staticmethod
    async def ensure_account(
        *,
        role: str,
        email: str,
        password: str,
        full_name: str,
    ) -> User:
        LabDemoService.require_isolated_mode()
        existing = await UserRepository.get_by_email(email)
        if existing:
            if (
                existing.demo_rehearsal_tag != LAB_DEMO_REHEARSAL_TAG
                or existing.role != role
                or not existing.is_active
                or existing.full_name != full_name
            ):
                raise RuntimeError("A reserved demo account conflicts with an untagged or unexpected account")
            return existing

        if role == "patient":
            user = await AuthService.register(
                UserRegister(
                    email=email,
                    password=password,
                    full_name=full_name,
                ),
                demo_rehearsal_tag=LAB_DEMO_REHEARSAL_TAG,
            )
        else:
            user = await AuthService.register_staff(
                StaffCreate(
                    email=email,
                    password=password,
                    full_name=full_name,
                    role=role,
                    demo_rehearsal_tag=LAB_DEMO_REHEARSAL_TAG,
                )
            )
        return user

    @staticmethod
    async def remove_temporary_laboratorian(user_id: str) -> None:
        LabDemoService.require_isolated_mode()
        user = await UserRepository.get_by_id(user_id)
        if (
            not user
            or user.role != "laboratorian"
            or user.demo_rehearsal_tag != LAB_DEMO_REHEARSAL_TAG
        ):
            raise RuntimeError("Refusing to remove a user not tagged for the laboratory rehearsal")
        sessions = await AuthSession.find({
            "user_id": user.id,
            "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
        }).to_list()
        for session in sessions:
            await session.delete()
        await user.delete()

    @staticmethod
    async def delete_tagged_records() -> tuple[int, int, int, int]:
        LabDemoService.require_isolated_mode()
        sessions = await AuthSession.find({
            "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
        }).to_list()
        requests = await LabRequest.find({
            "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
        }).to_list()
        patients = await Patient.find({
            "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
        }).to_list()
        users = await User.find({
            "demo_rehearsal_tag": LAB_DEMO_REHEARSAL_TAG,
        }).to_list()

        for session in sessions:
            await session.delete()
        for request in requests:
            await request.delete()
        for patient in patients:
            await patient.delete()
        for user in users:
            await user.delete()

        return len(users), len(patients), len(requests), len(sessions)
