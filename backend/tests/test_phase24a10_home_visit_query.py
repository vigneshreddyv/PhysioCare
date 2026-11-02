"""Phase 24A.10 no-preference home-visit query regression contracts."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from beanie import PydanticObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
import pytest

from app.core.appointment_time import active_slot_claim, booking_window, clinic_start_to_utc_naive
from app.models.clinician_schedule import ScheduleBlock
from app.models.user import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.clinician_schedule_repository import ClinicianScheduleRepository
from app.repositories.home_visit_query_repository import HomeVisitQueryRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.home_visit import HomeVisitBookingCreate
from app.services.appointment_service import AppointmentService
from app.services.clinician_schedule_service import ClinicianScheduleService
from app.services.home_visit_service import HomeVisitService


def target_date():
    return booking_window()[0] + timedelta(days=2)


def schedule(doctor_id, *times):
    blocks = [ScheduleBlock(
        day_of_week=target_date().weekday(),
        service_mode="home_visit",
        start_time=start,
        end_time=end,
    ) for start, end in times]
    return SimpleNamespace(
        doctor_id=doctor_id,
        slot_minutes=30,
        published_revision=1,
        published_weekly_blocks=blocks,
        published_date_exceptions=[],
    )


class AppointmentDouble:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, value)


def schema(**overrides):
    values = {
        "preferred_doctor_id": None,
        "appointment_date": target_date(),
        "time_slot": "09:00 AM",
        "submission_key": "x" * 16,
        "home_address": "12 Fictional Road, Nellore",
        "reason": "Fictional mobility support",
        "city": "Nellore",
        "body_regions": ["Knee"],
        "symptoms": ["Pain"],
        "duration_days": 2,
        "pain_severity": "low",
    }
    values.update(overrides)
    return HomeVisitBookingCreate(**values)


class AsyncCursor:
    def __init__(self, rows):
        self.rows = rows

    def __aiter__(self):
        self.iterator = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self.iterator)
        except StopIteration:
            raise StopAsyncIteration


class AggregateCollection:
    def __init__(self, rows):
        self.rows = rows
        self.pipelines = []

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        return AsyncCursor(self.rows)


async def collect(iterator):
    return [item async for item in iterator]


@pytest.mark.asyncio
async def test_repository_uses_one_streamed_eligibility_schedule_and_conflict_aggregation(monkeypatch):
    doctor_id = PydanticObjectId()
    appointment_id = PydanticObjectId()
    collection = AggregateCollection([{
        "doctor_id": doctor_id,
        "schedule": {
            "doctor_id": doctor_id,
            "published_revision": 1,
            "published_weekly_blocks": [],
            "published_date_exceptions": [],
        },
        "appointments": [{
            "_id": appointment_id,
            "starts_at": clinic_start_to_utc_naive(target_date(), "09:00 AM"),
            "appointment_date": datetime.combine(target_date(), datetime.min.time()),
            "time_slot": "09:00 AM",
            "service_mode": "home_visit",
        }],
    }])
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)

    contexts = await collect(HomeVisitQueryRepository.iter_clinician_contexts(target_date()))

    assert len(contexts) == 1
    assert contexts[0].id == doctor_id
    assert contexts[0].schedule.doctor_id == doctor_id
    assert contexts[0].appointments[0].id == appointment_id
    assert len(collection.pipelines) == 1
    pipeline = collection.pipelines[0]
    assert pipeline[0] == {"$match": {"role": "doctor", "is_active": True}}
    assert pipeline[-2] == {"$sort": {"doctor._id": 1}}
    lookup_names = [stage["$lookup"]["from"] for stage in pipeline if "$lookup" in stage]
    assert lookup_names == ["doctors", "clinician_schedules", "appointments"]
    doctor_lookup = next(stage["$lookup"] for stage in pipeline
                         if stage.get("$lookup", {}).get("from") == "doctors")
    eligibility = doctor_lookup["pipeline"][0]["$match"]["$expr"]["$and"]
    assert {"$ne": [{"$ifNull": ["$accepts_home_visits", True]}, False]} in eligibility
    appointment_lookup = next(stage["$lookup"] for stage in pipeline
                              if stage.get("$lookup", {}).get("from") == "appointments")
    appointment_match = appointment_lookup["pipeline"][0]["$match"]["$expr"]["$and"]
    assert {"$in": ["$status", ["scheduled", "in_progress"]]} in appointment_match
    rendered = repr(pipeline)
    assert "accepts_home_visits" in rendered
    assert "scheduled" in rendered and "in_progress" in rendered
    assert "hashed_password" not in rendered
    assert "email" not in rendered and "full_name" not in rendered


@pytest.mark.asyncio
async def test_query_projects_only_allocation_fields(monkeypatch):
    collection = AggregateCollection([])
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)

    assert await collect(HomeVisitQueryRepository.iter_clinician_contexts(target_date())) == []
    pipeline = collection.pipelines[0]
    assert [stage["$lookup"]["from"] for stage in pipeline if "$lookup" in stage] == [
        "doctors", "clinician_schedules", "appointments",
    ]
    assert pipeline[-1]["$project"] == {
        "_id": 0,
        "doctor_id": "$doctor._id",
        "schedule": {"$arrayElemAt": ["$schedule", 0]},
        "appointments": 1,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 250])
async def test_repository_query_count_is_constant_for_large_clinician_sets(monkeypatch, count):
    rows = [{"doctor_id": PydanticObjectId()} for _ in range(count)]
    collection = AggregateCollection(rows)
    monkeypatch.setattr(User, "get_pymongo_collection", lambda: collection)

    contexts = await collect(HomeVisitQueryRepository.iter_clinician_contexts(target_date()))

    assert len(contexts) == count
    assert len(collection.pipelines) == 1


@pytest.mark.asyncio
async def test_availability_merges_multiple_clinicians_and_preserves_conflicts(monkeypatch):
    first_id, second_id = PydanticObjectId(), PydanticObjectId()
    occupied = SimpleNamespace(
        id=PydanticObjectId(),
        starts_at=clinic_start_to_utc_naive(target_date(), "09:00 AM"),
        appointment_date=datetime.combine(target_date(), datetime.min.time()),
        time_slot="09:00 AM",
    )

    async def contexts(_date):
        yield SimpleNamespace(
            id=first_id, schedule=schedule(first_id, ("09:00", "10:00")), appointments=[occupied],
        )
        yield SimpleNamespace(
            id=second_id, schedule=schedule(second_id, ("09:00", "10:30")), appointments=[],
        )

    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=object()))
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", contexts)
    result = await HomeVisitService.get_booking_availability(
        "fictional-patient-user", HomeVisitService.NO_PREFERENCE_DOCTOR_ID, target_date(),
    )

    by_time = {slot.time_slot: slot for slot in result.slots}
    assert list(by_time) == ["09:00 AM", "09:30 AM", "10:00 AM"]
    assert by_time["09:00 AM"].available is True
    assert result.doctor_id == HomeVisitService.NO_PREFERENCE_DOCTOR_ID


@pytest.mark.asyncio
async def test_availability_marks_a_slot_occupied_when_every_candidate_conflicts(monkeypatch):
    doctor_id = PydanticObjectId()
    occupied = SimpleNamespace(
        id=PydanticObjectId(),
        starts_at=clinic_start_to_utc_naive(target_date(), "09:00 AM"),
        appointment_date=datetime.combine(target_date(), datetime.min.time()),
        time_slot="09:00 AM",
    )

    async def contexts(_date):
        yield SimpleNamespace(
            id=doctor_id, schedule=schedule(doctor_id, ("09:00", "09:30")), appointments=[occupied],
        )

    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=object()))
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", contexts)
    result = await HomeVisitService.get_booking_availability(
        "fictional-patient-user", HomeVisitService.NO_PREFERENCE_DOCTOR_ID, target_date(),
    )

    assert result.slots[0].availability_state == "occupied"
    assert result.slots[0].available is False


@pytest.mark.asyncio
async def test_no_preference_path_never_calls_legacy_per_clinician_repositories(monkeypatch):
    doctor_id = PydanticObjectId()
    calls = []

    async def contexts(_date):
        calls.append(_date)
        yield SimpleNamespace(id=doctor_id, schedule=schedule(doctor_id, ("09:00", "09:30")), appointments=[])

    async def forbidden(*_args, **_kwargs):
        raise AssertionError("per-clinician repository call")

    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=SimpleNamespace(id=PydanticObjectId())))
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", contexts)
    monkeypatch.setattr(ProfileRepository, "list_doctors", forbidden)
    monkeypatch.setattr(UserRepository, "get_by_id", forbidden)
    monkeypatch.setattr(AppointmentRepository, "list_active_by_doctor_id", forbidden)
    monkeypatch.setattr(ClinicianScheduleRepository, "get_by_doctor_id", forbidden)

    result = await HomeVisitService.get_booking_availability(
        "fictional-patient-user", HomeVisitService.NO_PREFERENCE_DOCTOR_ID, target_date(),
    )
    assert result.slots[0].available is True
    assert calls == [target_date()]


@pytest.mark.asyncio
async def test_no_eligible_clinician_returns_empty_availability_and_booking_conflict(monkeypatch):
    async def contexts(_date):
        if False:
            yield _date

    patient = SimpleNamespace(id=PydanticObjectId(), saved_home_address=None)
    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", contexts)
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=None))

    availability = await HomeVisitService.get_booking_availability(
        "fictional-patient-user", HomeVisitService.NO_PREFERENCE_DOCTOR_ID, target_date(),
    )
    assert availability.slots == []
    with pytest.raises(HTTPException) as error:
        await HomeVisitService.create_booking("fictional-patient-user", schema())
    assert error.value.status_code == 409
    assert "No home-visit clinician is available" in error.value.detail


@pytest.mark.asyncio
async def test_no_preference_booking_streams_candidates_and_preserves_unique_claim_retry(monkeypatch):
    first_id, second_id = PydanticObjectId(), PydanticObjectId()
    patient = SimpleNamespace(id=PydanticObjectId(), saved_home_address=None)
    attempts = []

    async def contexts(_date):
        yield SimpleNamespace(id=first_id, schedule=schedule(first_id, ("09:00", "09:30")), appointments=[])
        yield SimpleNamespace(id=second_id, schedule=schedule(second_id, ("09:00", "09:30")), appointments=[])

    async def create(appointment):
        attempts.append(appointment)
        if len(attempts) == 1:
            raise DuplicateKeyError("synthetic occupied slot")
        appointment.id = PydanticObjectId()
        return appointment

    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", contexts)
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=None))
    monkeypatch.setattr(AppointmentRepository, "create", create)
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="confirmed"))
    monkeypatch.setattr("app.services.home_visit_service.Appointment", AppointmentDouble)

    assert await HomeVisitService.create_booking("fictional-patient-user", schema()) == "confirmed"
    assert [item.doctor_id for item in attempts] == [first_id, second_id]
    assert all(item.doctor_assignment_pending for item in attempts)
    assert attempts[1].slot_claim == active_slot_claim(
        str(second_id), clinic_start_to_utc_naive(target_date(), "09:00 AM"),
    )


@pytest.mark.asyncio
async def test_no_preference_booking_skips_existing_conflict_before_atomic_insert(monkeypatch):
    first_id, second_id = PydanticObjectId(), PydanticObjectId()
    patient = SimpleNamespace(id=PydanticObjectId(), saved_home_address=None)
    starts_at = clinic_start_to_utc_naive(target_date(), "09:00 AM")
    occupied = SimpleNamespace(
        id=PydanticObjectId(), starts_at=starts_at,
        appointment_date=datetime.combine(target_date(), datetime.min.time()),
        time_slot="09:00 AM",
    )

    async def contexts(_date):
        yield SimpleNamespace(
            id=first_id, schedule=schedule(first_id, ("09:00", "09:30")), appointments=[occupied],
        )
        yield SimpleNamespace(
            id=second_id, schedule=schedule(second_id, ("09:00", "09:30")), appointments=[],
        )

    async def create(appointment):
        appointment.id = PydanticObjectId()
        return appointment

    create_mock = AsyncMock(side_effect=create)
    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", contexts)
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=None))
    monkeypatch.setattr(AppointmentRepository, "create", create_mock)
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="confirmed"))
    monkeypatch.setattr("app.services.home_visit_service.Appointment", AppointmentDouble)

    assert await HomeVisitService.create_booking("fictional-patient-user", schema()) == "confirmed"
    assert create_mock.await_count == 1
    assert create_mock.await_args.args[0].doctor_id == second_id


@pytest.mark.asyncio
async def test_no_preference_booking_rejects_when_no_streamed_schedule_contains_slot(monkeypatch):
    doctor_id = PydanticObjectId()
    patient = SimpleNamespace(id=PydanticObjectId(), saved_home_address=None)

    async def contexts(_date):
        yield SimpleNamespace(id=doctor_id, schedule=schedule(doctor_id, ("10:00", "10:30")), appointments=[])

    create = AsyncMock()
    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", contexts)
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=None))
    monkeypatch.setattr(AppointmentRepository, "create", create)

    with pytest.raises(HTTPException) as error:
        await HomeVisitService.create_booking("fictional-patient-user", schema())
    assert error.value.status_code == 409
    assert "No home-visit clinician is scheduled" in error.value.detail
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_specific_clinician_path_keeps_existing_validation_and_skips_bulk_query(monkeypatch):
    doctor_id, user_id = PydanticObjectId(), PydanticObjectId()
    doctor = SimpleNamespace(id=doctor_id, user_id=user_id, accepts_home_visits=True)
    patient = SimpleNamespace(id=PydanticObjectId(), saved_home_address=None)
    starts_at = clinic_start_to_utc_naive(target_date(), "09:00 AM")
    aggregate = AsyncMock()

    async def create(appointment):
        appointment.id = PydanticObjectId()
        return appointment

    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=SimpleNamespace(is_active=True)))
    monkeypatch.setattr(ClinicianScheduleService, "validate_effective_slot", AsyncMock(return_value=(starts_at, True)))
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", aggregate)
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=None))
    monkeypatch.setattr(AppointmentRepository, "create", create)
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="confirmed-specific"))
    monkeypatch.setattr("app.services.home_visit_service.Appointment", AppointmentDouble)

    result = await HomeVisitService.create_booking(
        "fictional-patient-user", schema(preferred_doctor_id=str(doctor_id)),
    )
    assert result == "confirmed-specific"
    aggregate.assert_not_called()
    ClinicianScheduleService.validate_effective_slot.assert_awaited_once()


@pytest.mark.asyncio
async def test_entitlement_ownership_gate_runs_before_no_preference_query(monkeypatch):
    gate = AsyncMock(side_effect=HTTPException(status_code=403, detail="not entitled"))
    aggregate = AsyncMock()
    monkeypatch.setattr(HomeVisitService, "_entitled_patient", gate)
    monkeypatch.setattr(HomeVisitQueryRepository, "iter_clinician_contexts", aggregate)

    with pytest.raises(HTTPException) as error:
        await HomeVisitService.get_booking_availability(
            "fictional-patient-user", HomeVisitService.NO_PREFERENCE_DOCTOR_ID, target_date(),
        )
    assert error.value.status_code == 403
    gate.assert_awaited_once_with("fictional-patient-user")
    aggregate.assert_not_called()
