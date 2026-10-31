from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.auth_session import AuthSession
from app.models.demo_entitlement import DemoEntitlement
from app.models.home_visit_request import HomeVisitRequest
from app.models.lab_request import LabRequest
from app.models.clinician_schedule import ClinicianSchedule
from app.models.payment_attempt import PaymentAttempt, RazorpayWebhookEvent
from app.models.care_plan import CarePlan, CarePlanHistory
from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress
from app.models.laboratory_booking import LaboratoryBooking
from app.models.laboratory_test import LaboratoryTest
from app.models.report import Report
from app.models.notification import Notification

# Custom client subclass to ensure compatibility between Beanie 2.1.0 and Motor 3.6+ / PyMongo 4.9+
# PyMongo 4.9+ removed append_metadata, which Beanie 2.1.0 internally tries to call.
# Subclassing AsyncIOMotorClient avoids runtime monkey patching in production.
class BeanieCompatibleMotorClient(AsyncIOMotorClient):
    def append_metadata(self, *args, **kwargs):
        pass

async def init_db():
    settings.validate_lab_demo_isolation()
    settings.validate_home_visit_demo_isolation()
    client = BeanieCompatibleMotorClient(settings.MONGODB_URL)
    await init_beanie(
        database=client[settings.DATABASE_NAME],
        document_models=[
            User,
            Patient,
            Doctor,
            Appointment,
            AuthSession,
            DemoEntitlement,
            HomeVisitRequest,
            LabRequest,
            ClinicianSchedule,
            PaymentAttempt,
            RazorpayWebhookEvent,
            CarePlan,
            CarePlanHistory,
            Exercise,
            ExerciseAssignment,
            ExerciseProgress,
            LaboratoryBooking,
            LaboratoryTest,
            Report,
            Notification,
        ]
    )
