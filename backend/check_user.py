import asyncio

from app.database import init_db
from app.repositories.user_repository import UserRepository


async def main():
    await init_db()

    user = await UserRepository.get_by_email(
        "sarah.miller@physiocare.com"
    )

    print("USER FOUND:")
    print(user)


asyncio.run(main())