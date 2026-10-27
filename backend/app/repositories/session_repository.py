from typing import Optional

from beanie import PydanticObjectId

from app.models.auth_session import AuthSession


class SessionRepository:
    @staticmethod
    async def get_by_id(session_id: str) -> Optional[AuthSession]:
        try:
            return await AuthSession.get(PydanticObjectId(session_id))
        except (ValueError, TypeError):
            return None

    @staticmethod
    async def create(session: AuthSession) -> AuthSession:
        return await session.insert()

    @staticmethod
    async def save(session: AuthSession) -> AuthSession:
        await session.save()
        return session
