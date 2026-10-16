from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.laboratory_test import LaboratoryTest
from app.models.laboratory_booking import LaboratoryBooking
from app.models.notification import Notification
from app.models.webhook_event import WebhookEvent
from app.models.payment_refund import PaymentRefund
from app.models.report import Report
from app.models.care_plan import CarePlan, CarePlanHistory
from app.models.exercise import Exercise, ExerciseAssignment, ExerciseProgress

# Custom client subclass to ensure compatibility between Beanie 2.1.0 and Motor 3.6+ / PyMongo 4.9+
# PyMongo 4.9+ removed append_metadata, which Beanie 2.1.0 internally tries to call.
# Subclassing AsyncIOMotorClient avoids runtime monkey patching in production.
class BeanieCompatibleMotorClient(AsyncIOMotorClient):
    def append_metadata(self, *args, **kwargs):
        pass

async def init_db():
    client = BeanieCompatibleMotorClient(settings.MONGODB_URL)
    await init_beanie(
        database=client[settings.DATABASE_NAME],
        document_models=[
            User,
            Patient,
            Doctor,
            Appointment,
            LaboratoryTest,
            LaboratoryBooking,
            Notification,
            Report,
            CarePlan,
            CarePlanHistory,
            Exercise,
            ExerciseAssignment,
            ExerciseProgress,
            WebhookEvent,
            PaymentRefund,
        ]
    )