from typing import Optional
import re
from types import SimpleNamespace

from beanie import PydanticObjectId

from app.models.user import User
from app.schemas.auth import STAFF_ROLES
from app.core.pagination import PageWindow


class UserRepository:

    @staticmethod
    async def get_by_email(email: str) -> Optional[User]:
        return await User.find_one(User.email == email)

    @staticmethod
    async def get_by_id(id: str) -> Optional[User]:
        return await User.get(PydanticObjectId(id))

    @staticmethod
    async def create(user: User) -> User:
        return await user.insert()

    @staticmethod
    async def save(user: User) -> User:
        return await user.save()

    @staticmethod
    async def list_by_role(role: str) -> list[User]:
        return await User.find({"role": role, "is_active": True}).sort(User.full_name).to_list()

    @staticmethod
    async def search_by_role(role: str, search: str, page: PageWindow) -> list[User]:
        query: dict = {"role": role, "is_active": True}
        if search:
            query["full_name"] = {"$regex": re.escape(search), "$options": "i"}
        return await User.find(query).sort("+full_name", "+_id").skip(
            page.offset
        ).limit(page.size).to_list()

    @staticmethod
    async def list_staff(
        page: PageWindow,
        *,
        search: str = "",
        role: str | None = None,
        is_active: bool | None = None,
    ) -> list[SimpleNamespace]:
        query: dict = {"role": role or {"$in": list(STAFF_ROLES)}}
        if is_active is not None:
            query["is_active"] = is_active
        if search:
            pattern = re.escape(search)
            query["$or"] = [
                {"full_name": {"$regex": pattern, "$options": "i"}},
                {"email": {"$regex": pattern, "$options": "i"}},
            ]
        rows = await User.get_pymongo_collection().find(
            query,
            {
                "full_name": 1,
                "email": 1,
                "role": 1,
                "is_active": 1,
                "created_at": 1,
            },
        ).sort([("full_name", 1), ("_id", 1)]).skip(
            page.offset
        ).limit(page.size).to_list(length=page.size)
        return [SimpleNamespace(
            id=row["_id"],
            full_name=row["full_name"],
            email=row["email"],
            role=row["role"],
            is_active=row.get("is_active", True),
            created_at=row.get("created_at"),
        ) for row in rows]
