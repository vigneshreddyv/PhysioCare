from datetime import datetime
from typing import Optional

from pymongo import ReturnDocument

from app.models.auth_session import AuthSession


class AuthSessionRepository:
    @staticmethod
    async def create(session: AuthSession) -> AuthSession:
        return await session.insert()

    @staticmethod
    async def rotate_for_refresh(
        *,
        user_id: str,
        family_id: str,
        jti: str,
        token_hash: str,
        new_jti: str,
        new_token_hash: str,
        new_expires_at: datetime,
        now: datetime,
    ) -> Optional[AuthSession]:
        """Atomically replace the current token in one session-family document."""
        return await AuthSession.get_pymongo_collection().find_one_and_update(
            {
                "user_id": user_id,
                "family_id": family_id,
                "jti": jti,
                "token_hash": token_hash,
                "revoked_at": None,
                "expires_at": {"$gt": now},
            },
            {
                "$set": {
                    "jti": new_jti,
                    "token_hash": new_token_hash,
                    "expires_at": new_expires_at,
                    "rotated_at": now,
                    "replaced_by_jti": None,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    @staticmethod
    async def revoke_family(user_id: str, family_id: str, *, reason: str, now: datetime) -> int:
        result = await AuthSession.get_pymongo_collection().update_many(
            {"user_id": user_id, "family_id": family_id, "revoked_at": None},
            {"$set": {"revoked_at": now, "revocation_reason": reason}},
        )
        return result.modified_count

    @staticmethod
    async def revoke_all_for_user(user_id: str, *, reason: str, now: datetime) -> None:
        await AuthSession.get_pymongo_collection().update_many(
            {"user_id": user_id, "revoked_at": None},
            {"$set": {"revoked_at": now, "revocation_reason": reason}},
        )
