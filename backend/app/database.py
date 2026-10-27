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
            AuthSession,
            DemoEntitlement,
            HomeVisitRequest,
            LabRequest,
            ClinicianSchedule,
        ]
    )
