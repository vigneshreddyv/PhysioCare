from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from app.core.appointment_time import booking_window, demo_home_schedule_slots, demo_schedule_slots
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.clinician_schedule_repository import ClinicianScheduleRepository
from app.repositories.home_visit_query_repository import HomeVisitQueryRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.appointment import AppointmentCreate
from app.schemas.home_visit import HomeVisitBookingCreate
from app.services.appointment_service import AppointmentService
from app.services.clinician_schedule_service import ClinicianScheduleService
from app.services.home_visit_service import HomeVisitService
from app.models.clinician_schedule import ScheduleBlock


def _date():
    return booking_window()[0] + timedelta(days=2)


def _mode(monkeypatch, environment, *, local=False, lab=False, home=False):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    monkeypatch.setattr(settings, "PHYSIOCARE_LOCAL_DEV", local)
    monkeypatch.setattr(settings, "LAB_DEMO_MODE", lab)
    monkeypatch.setattr(settings, "HOME_VISIT_DEMO_MODE", home)


@pytest.mark.asyncio
@pytest.mark.parametrize("flags", [
    {"local": True},
    {"lab": True},
    {"home": True},
])
async def test_explicit_development_modes_keep_demo_slots(monkeypatch, flags):
    _mode(monkeypatch, "development", **flags)
    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(ClinicianScheduleRepository, "get_by_doctor_id", lookup)

    clinic_slots, clinic_published = await ClinicianScheduleService.effective_slots("doctor", _date(), "clinic")
    home_slots, home_published = await ClinicianScheduleService.effective_slots("doctor", _date(), "home_visit")

    assert clinic_slots == demo_schedule_slots()
    assert home_slots == demo_home_schedule_slots()
    assert clinic_published is False
    assert home_published is False
    starts_at, published = await ClinicianScheduleService.validate_effective_slot(
        "doctor", _date(), clinic_slots[0], "clinic"
    )
    assert starts_at is not None
    assert published is False
    assert lookup.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("environment, flags", [
    ("development", {}),
    ("test", {}),
    ("staging", {}),
    ("production", {}),
    ("staging", {"local": True, "lab": True, "home": True}),
])
async def test_non_demo_modes_expose_no_fallback_and_reject_slot(monkeypatch, environment, flags):
    _mode(monkeypatch, environment, **flags)
    monkeypatch.setattr(ClinicianScheduleRepository, "get_by_doctor_id", AsyncMock(return_value=None))

    slots, published = await ClinicianScheduleService.effective_slots("doctor", _date(), "clinic")
    assert slots == []
    assert published is False
    with pytest.raises(HTTPException) as error:
        await ClinicianScheduleService.validate_effective_slot(
            "doctor", _date(), demo_schedule_slots()[0], "clinic"
        )
    assert error.value.status_code == 409
    assert "No published clinician schedule" in error.value.detail


@pytest.mark.asyncio
async def test_published_schedule_is_available_and_bookable_in_non_demo_mode(monkeypatch):
    _mode(monkeypatch, "staging")
    target = _date()
    schedule = SimpleNamespace(
        published_revision=1,
        slot_minutes=30,
        published_weekly_blocks=[ScheduleBlock(
            day_of_week=target.weekday(), service_mode="clinic", start_time="10:00", end_time="11:00"
        )],
        published_date_exceptions=[],
    )
    monkeypatch.setattr(ClinicianScheduleRepository, "get_by_doctor_id", AsyncMock(return_value=schedule))

    slots, published = await ClinicianScheduleService.effective_slots("doctor", target, "clinic")
    assert (slots, published) == (["10:00 AM", "10:30 AM"], True)
    starts_at, validated_published = await ClinicianScheduleService.validate_effective_slot(
        "doctor", target, "10:00 AM", "clinic"
    )
    assert starts_at is not None
    assert validated_published is True


@pytest.mark.asyncio
async def test_patient_booking_cannot_claim_demo_slot_without_published_schedule(monkeypatch):
    _mode(monkeypatch, "production")
    patient = SimpleNamespace(id=PydanticObjectId())
    doctor = SimpleNamespace(id=PydanticObjectId())
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(ClinicianScheduleRepository, "get_by_doctor_id", AsyncMock(return_value=None))
    insert = AsyncMock()
    monkeypatch.setattr(AppointmentRepository, "create", insert)

    with pytest.raises(HTTPException) as error:
        await AppointmentService.create_appointment("fictional-user", AppointmentCreate(
            doctor_id=str(doctor.id), appointment_date=_date(),
            time_slot=demo_schedule_slots()[0], reason="Fictional mobility consultation",
        ))
    assert error.value.status_code == 409
    insert.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_demo_availability_has_no_demo_slots_or_label(monkeypatch):
    _mode(monkeypatch, "staging")
    doctor = SimpleNamespace(id=PydanticObjectId())
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_active_by_doctor_id", AsyncMock(return_value=[]))
    monkeypatch.setattr(ClinicianScheduleRepository, "get_by_doctor_id", AsyncMock(return_value=None))

    availability = await AppointmentService.get_availability(str(doctor.id), _date())
    assert availability.slots == []
    assert availability.demo_configuration is False
    assert "No published clinician schedule" in availability.configuration_label


@pytest.mark.asyncio
async def test_non_demo_home_visit_availability_has_no_demo_slots(monkeypatch):
    _mode(monkeypatch, "staging")
    doctor = SimpleNamespace(id=PydanticObjectId())
    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=object()))
    async def contexts(_appointment_date):
        yield SimpleNamespace(id=doctor.id, schedule=None, appointments=[])
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", contexts)

    availability = await HomeVisitService.get_booking_availability(
        "fictional-user", HomeVisitService.NO_PREFERENCE_DOCTOR_ID, _date()
    )
    assert availability.slots == []
    assert availability.demo_configuration is False
    assert "No published clinician home-visit schedule" in availability.configuration_label


@pytest.mark.asyncio
async def test_home_visit_booking_cannot_claim_demo_slot_without_published_schedule(monkeypatch):
    from app.core.config import settings

    _mode(monkeypatch, "staging")
    doctor = SimpleNamespace(id=PydanticObjectId())
    patient = SimpleNamespace(id=PydanticObjectId())
    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    async def contexts(_appointment_date):
        yield SimpleNamespace(id=doctor.id, schedule=None, appointments=[])
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", contexts)
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=None))
    insert = AsyncMock()
    monkeypatch.setattr(AppointmentRepository, "create", insert)

    with pytest.raises(HTTPException) as error:
        await HomeVisitService.create_booking("fictional-user", HomeVisitBookingCreate(
            home_address="Fictional test street, unit 12",
            city=settings.DEMO_HOME_SERVICE_CITY,
            body_regions=["Knee"],
            symptoms=["Pain"],
            duration_days=2,
            pain_severity="low",
            appointment_date=_date(),
            time_slot=demo_home_schedule_slots()[0],
            submission_key="fictional-test-claim-0001",
        ))
    assert error.value.status_code == 409
    insert.assert_not_awaited()
