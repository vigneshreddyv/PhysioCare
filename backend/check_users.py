import asyncio

from app.database import init_db
from app.models.user import User


async def main():
    await init_db()

    users = await User.find_all().to_list()

    print("\nCURRENT USERS")
    print("=" * 60)

    for user in users:
        print(
            f"Name: {user.full_name} | "
            f"Email: {user.email} | "
            f"Role: {user.role}"
        )


asyncio.run(main())