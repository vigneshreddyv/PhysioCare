"""Atomic creation of accounts that require a role profile."""

from pymongo.errors import DuplicateKeyError

from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User


class DuplicateRegistrationEmail(Exception):
    """The unique user email was claimed by another registration."""


class AccountRegistrationRepository:
    @staticmethod
    async def create_with_profile(
        user: User,
        *,
        role: str,
        demo_rehearsal_tag: str | None = None,
    ) -> User:
        if role not in {"patient", "doctor"}:
            raise ValueError("A role profile is required for transactional registration")

        client = User.get_pymongo_collection().database.client
        async with client.start_session() as session:
            async def create_in_transaction(active_session):
                # The callback can be retried. Keep all writes in this session
                # and construct a fresh profile on each attempt.
                if await User.find_one({"email": user.email}, session=active_session):
                    raise DuplicateRegistrationEmail
                try:
                    saved_user = await user.insert(session=active_session)
                except DuplicateKeyError as exc:
                    raise DuplicateRegistrationEmail from exc

                if role == "patient":
                    profile = Patient(
                        user_id=saved_user.id,
                        demo_rehearsal_tag=demo_rehearsal_tag,
                    )
                else:
                    profile = Doctor(
                        user_id=saved_user.id,
                        specialization="General Physiotherapy",
                    )
                await profile.insert(session=active_session)
                return saved_user

            return await session.with_transaction(create_in_transaction)
