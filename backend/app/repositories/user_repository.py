from typing import Optional

from beanie import PydanticObjectId

from app.models.user import User
from app.schemas.auth import STAFF_ROLES


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
    async def list_staff() -> list[User]:
        return await User.find({"role": {"$in": list(STAFF_ROLES)}}).sort(User.full_name).to_list()
