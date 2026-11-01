from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import DEVELOPMENT_DATABASE_NAME, settings
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.auth_session import AuthSession
from app.models.auth_rate_limit import AuthRateLimitBucket
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
    settings.validate_runtime_startup()
    ordinary_development = settings.ENVIRONMENT == "development" and not (
        settings.LAB_DEMO_MODE or settings.HOME_VISIT_DEMO_MODE
    )
    client = (
        BeanieCompatibleMotorClient(
            settings.development_mongodb_url(), directConnection=True
        )
        if ordinary_development
        else BeanieCompatibleMotorClient(settings.MONGODB_URL)
    )
    await init_beanie(
        database=client[
            DEVELOPMENT_DATABASE_NAME if ordinary_development else settings.DATABASE_NAME
        ],
        document_models=[
            User,
            Patient,
            Doctor,
            Appointment,
            AuthSession,
            AuthRateLimitBucket,
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
