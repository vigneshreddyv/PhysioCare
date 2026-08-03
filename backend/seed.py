import asyncio
from datetime import datetime, timedelta
from app.core.security import get_password_hash
from app.database import init_db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment

async def seed():
    print("Connecting to database...")
    await init_db()
    
    print("Clearing database...")
    await User.find_all().delete()
    await Doctor.find_all().delete()
    await Patient.find_all().delete()
    await Appointment.find_all().delete()
    
    print("Seeding Admin...")
    admin_user = User(
        email="admin@physiocare.com",
        hashed_password=get_password_hash("admin123"),
        role="admin",
        full_name="Dr. Jane Smith"
    )
    await admin_user.insert()
    
    print("Seeding Doctors...")
    doc1_user = User(
        email="sarah.miller@physiocare.com",
        hashed_password=get_password_hash("password123"),
        role="doctor",
        full_name="Dr. Sarah Miller"
    )
    await doc1_user.insert()
    
    doc1_profile = Doctor(
        user=doc1_user,
        specialization="Sports Therapy",
        profile_image="https://lh3.googleusercontent.com/aida-public/AB6AXuDFn5Hei2SRFOwq8VfxOjEJ1rwnbl99DQdqSoIyafjmP98BmyxyVwwHz9lpRd2ndIJKltdXwOPRQ94BNRWN1aVR2P2H6iSxNak7fSL-3uAv9_at3PU8wH6uofYyuw_IlF00M1kbDdCvVEAqj_IUOOK0bCWyvS31V1rESgSBE6QboywWshpbbSg4ys1gtY-0bQsOa6xic8By3d1gRId_Abxh5agY429_-O8JNDjiSfDd67m10ZDpujiX",
        bio="Dr. Miller specializes in athletic injury rehabilitation, functional movement analysis, and targeted strength conditioning.",
        is_active_today=True
    )
    await doc1_profile.insert()
    
    doc2_user = User(
        email="james.chen@physiocare.com",
        hashed_password=get_password_hash("password123"),
        role="doctor",
        full_name="Dr. James Chen"
    )
    await doc2_user.insert()
    
    doc2_profile = Doctor(
        user=doc2_user,
        specialization="Post-Op Rehabilitation",
        profile_image="https://lh3.googleusercontent.com/aida-public/AB6AXuBvqQHgrPEhGHUgyHqCfpjeMAIpnYcW26-41UgGLhUw1QxONI4Iisxwlo3w1Mlx4uJBott3GZHmwNjNnAJSGo9OGbjN5xUTKYrUKPeyXo0yd02zVDV9Nf4iea2ZHO4ITfBQ4VcHN86rRt6wb98ouM6G_vlKt0NWCyyhViYV0cDat4uOKHh-VAYT3hKI81CxElRLnxKOltpeV5kVQrr7MPQ80-8ppZui1SBGdnI4IzHmsk36ISJ6zE4T",
        bio="Dr. Chen is an expert in orthopedic surgery recovery, gait mechanics, and joints flexibility restoration.",
        is_active_today=True
    )
    await doc2_profile.insert()
    
    print("Seeding Patients...")
    pat1_user = User(
        email="john.doe@gmail.com",
        hashed_password=get_password_hash("password123"),
        role="patient",
        full_name="John Doe"
    )
    await pat1_user.insert()
    pat1_profile = Patient(
        user=pat1_user,
        phone="+1555123456",
        date_of_birth="1988-05-12",
        subscription_status="active",
        primary_doctor=doc1_profile
    )
    await pat1_profile.insert()
    
    pat2_user = User(
        email="alice.smith@gmail.com",
        hashed_password=get_password_hash("password123"),
        role="patient",
        full_name="Alice Smith"
    )
    await pat2_user.insert()
    pat2_profile = Patient(
        user=pat2_user,
        phone="+1555654321",
        date_of_birth="1992-09-24",
        subscription_status="active",
        primary_doctor=doc2_profile
    )
    await pat2_profile.insert()
    
    print("Seeding Appointments...")
    today = datetime.utcnow()
    
    appt1 = Appointment(
        patient=pat1_profile,
        doctor=doc1_profile,
        appointment_date=today,
        time_slot="10:00 AM",
        reason="Physiotherapy - Knee Rehab",
        status="completed",
        billing_status="paid",
        billing_amount=150.0
    )
    await appt1.insert()
    
    appt2 = Appointment(
        patient=pat2_profile,
        doctor=doc2_profile,
        appointment_date=today,
        time_slot="11:30 AM",
        reason="Initial Consultation - Back Stiffness",
        status="in_progress",
        billing_status="pending",
        billing_amount=120.0
    )
    await appt2.insert()
    
    appt3 = Appointment(
        patient=pat1_profile,
        doctor=doc1_profile,
        appointment_date=today + timedelta(days=2),
        time_slot="02:30 PM",
        reason="Follow up shoulder review",
        status="scheduled",
        billing_status="pending",
        billing_amount=120.0
    )
    await appt3.insert()
    
    print("Seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed())
