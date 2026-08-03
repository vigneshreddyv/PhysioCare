from typing import Optional
from app.models.user import User

class UserRepository:
    @staticmethod
    async def get_by_email(email: str) -> Optional[User]:
        return await User.find_one(User.email == email)

    @staticmethod
    async def get_by_id(id: str) -> Optional[User]:
        return await User.get(id)

    @staticmethod
    async def create(user: User) -> User:
        return await user.insert()
