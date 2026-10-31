from datetime import datetime
from typing import Any, Optional

from beanie import PydanticObjectId
from pymongo import ReturnDocument

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
    async def rotate_for_refresh(
        *,
        session_id: str,
        user_id: PydanticObjectId,
        current_refresh_token_hash: str,
        csrf_token_hash: str,
        new_refresh_token_hash: str,
        new_expires_at: datetime,
        now: datetime,
    ) -> Optional[dict[str, Any]]:
        """Atomically claim and rotate the current refresh token.

        Matching both secret hashes makes this the single winner when the same
        refresh token is submitted concurrently. The service revokes the
        session when a valid pre-check loses this claim, treating it as replay.
        """

        try:
            object_id = PydanticObjectId(session_id)
        except (ValueError, TypeError):
            return None

        return await AuthSession.get_pymongo_collection().find_one_and_update(
            {
                "_id": object_id,
                "user_id": user_id,
                "refresh_token_hash": current_refresh_token_hash,
                "csrf_token_hash": csrf_token_hash,
                "revoked_at": None,
                "expires_at": {"$gt": now},
            },
            {
                "$set": {
                    "refresh_token_hash": new_refresh_token_hash,
                    "expires_at": new_expires_at,
                    "rotated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    @staticmethod
    async def revoke_by_id(
        session_id: str,
        *,
        reason: str,
        now: datetime,
    ) -> int:
        try:
            object_id = PydanticObjectId(session_id)
        except (ValueError, TypeError):
            return 0

        result = await AuthSession.get_pymongo_collection().update_one(
            {"_id": object_id, "revoked_at": None},
            {"$set": {"revoked_at": now, "revocation_reason": reason}},
        )
        return result.modified_count
