import asyncio

from app.database import init_db
from app.models.doctor import Doctor
from app.repositories.user_repository import UserRepository


async def update_doctors():
    print("Connecting to database...")
    await init_db()

    doctors = [
        {
            "email": "sarah.miller@physiocare.com",
            "experience_years": 8,
            "expertise": [
                "Sports Injuries",
                "Back Pain",
                "Mobility Training",
                "Athletic Rehabilitation",
            ],
            "rating": 4.8,
            "total_reviews": 124,
            "consultation_fee": 600.0,
            "home_visit_available": True,
            "online_consultation_available": True,
        },
        {
            "email": "james.chen@physiocare.com",
            "experience_years": 10,
            "expertise": [
                "Post-Surgery Rehabilitation",
                "Joint Recovery",
                "Gait Training",
                "Orthopedic Rehabilitation",
            ],
            "rating": 4.9,
            "total_reviews": 156,
            "consultation_fee": 700.0,
            "home_visit_available": True,
            "online_consultation_available": True,
        },
        {
            "email": "arun.kumar@physiocare.com",
            "experience_years": 7,
            "expertise": [
                "Pain Management",
                "Neck Pain",
                "Back Pain",
                "General Physiotherapy",
            ],
            "rating": 4.7,
            "total_reviews": 98,
            "consultation_fee": 500.0,
            "home_visit_available": True,
            "online_consultation_available": True,
        },
    ]

    for data in doctors:
        user = await UserRepository.get_by_email(data["email"])

        if not user:
            print(f"Doctor user not found: {data['email']}")
            continue

        doctor = await Doctor.find_one(
            Doctor.user_id == user.id
        )

        if not doctor:
            print(f"Doctor profile not found: {data['email']}")
            continue

        doctor.experience_years = data["experience_years"]
        doctor.expertise = data["expertise"]
        doctor.rating = data["rating"]
        doctor.total_reviews = data["total_reviews"]
        doctor.consultation_fee = data["consultation_fee"]
        doctor.home_visit_available = data["home_visit_available"]
        doctor.online_consultation_available = data[
            "online_consultation_available"
        ]

        await doctor.save()

        print(f"Updated doctor: {data['email']}")

    print("Doctor profiles updated successfully.")


if __name__ == "__main__":
    asyncio.run(update_doctors())