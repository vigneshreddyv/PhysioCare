import asyncio

from app.database import init_db
from app.core.security import get_password_hash
from app.models.user import User
from app.models.doctor import Doctor


async def add_doctors():
    print("Connecting to database...")
    await init_db()

    doctors = [
        {
            "email": "sarah.miller@physiocare.com",
            "password": "password123",
            "full_name": "Dr. Sarah Miller",
            "specialization": "Sports Therapy",
            "bio": "Specialist in athletic injury rehabilitation, functional movement analysis, and strength conditioning.",
        },
        {
            "email": "james.chen@physiocare.com",
            "password": "password123",
            "full_name": "Dr. James Chen",
            "specialization": "Post-Op Rehabilitation",
            "bio": "Expert in orthopedic recovery, gait mechanics, and joint mobility restoration.",
        },
        {
            "email": "arun.kumar@physiocare.com",
            "password": "doctor0123",
            "full_name": "Dr. Arun Kumar",
            "specialization": "General Physiotherapy",
            "bio": "Experienced physiotherapist specializing in pain management and rehabilitation.",
        },
    ]

    for doctor in doctors:
        existing = await User.find_one(
            User.email == doctor["email"]
        )

        if existing:
            print(f"Already exists: {doctor['email']}")
            continue

        user = User(
            email=doctor["email"],
            hashed_password=get_password_hash(doctor["password"]),
            role="doctor",
            full_name=doctor["full_name"],
        )

        await user.insert()

        profile = Doctor(
            user_id=user.id,
            specialization=doctor["specialization"],
            bio=doctor["bio"],
            is_active_today=True,
        )

        await profile.insert()

        print(f"Created doctor: {doctor['email']}")

    print("Doctor setup completed.")


if __name__ == "__main__":
    asyncio.run(add_doctors())