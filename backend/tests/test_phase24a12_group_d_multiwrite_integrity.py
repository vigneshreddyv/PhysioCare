import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import users
from app.models.appointment import Appointment
from app.models.care_plan import CarePlan, CarePlanHistory
from app.models.exercise import ExerciseAssignment, ExerciseProgress
from app.models.notification import Notification
from app.repositories.appointment_repository import (
    AppointmentMutationConflict,
    AppointmentRepository,
)
from app.repositories.care_plan_repository import CarePlanMutationConflict, CarePlanRepository
from app.repositories.exercise_repository import (
    ExerciseAssignmentMutationConflict,
    ExerciseRepository,
)
from app.schemas.appointment import AppointmentUpdate
from app.schemas.care_plan import CarePlanUpdate, GoalProgressUpdate, StageStatusUpdate
from app.schemas.exercise import ExerciseAssignmentUpdate, ExerciseProgressCreate
from app.services.appointment_service import AppointmentService
from app.services.home_visit_service import HomeVisitService


OID_1 = PydanticObjectId("111111111111111111111111")
OID_2 = PydanticObjectId("222222222222222222222222")
OID_3 = PydanticObjectId("333333333333333333333333")


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (AppointmentUpdate, {"status": "completed"}),
        (CarePlanUpdate, {"title": "Updated"}),
        (StageStatusUpdate, {"status": "active"}),
        (GoalProgressUpdate, {"progress_value": 1, "status": "active"}),
        (ExerciseAssignmentUpdate, {"status": "in_progress"}),
        (ExerciseProgressCreate, {
            "assignment_id": str(OID_1), "completed_sets": 1,
            "completed_reps": 1, "duration_seconds": 10,
        }),
    ],
)
def test_mutation_contracts_require_explicit_revision(schema, payload):
    with pytest.raises(ValidationError) as exc:
        schema(**payload)
    assert "revision" in str(exc.value)


def test_legacy_revision_zero_filters_are_compatible_but_later_revisions_are_exact():
    legacy = {"$or": [{"revision": 0}, {"revision": {"$exists": False}}]}
    assert AppointmentRepository._revision_filter(0) == legacy
    assert CarePlanRepository._revision_filter(0) == legacy
    assert ExerciseRepository._assignment_revision_filter(0) == legacy
    assert AppointmentRepository._revision_filter(4) == {"revision": 4}
    assert CarePlanRepository._revision_filter(4) == {"revision": 4}
    assert ExerciseRepository._assignment_revision_filter(4) == {"revision": 4}


@pytest.mark.asyncio
async def test_appointment_repository_rejects_stale_revision_without_model_save(monkeypatch):
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=None)
    monkeypatch.setattr(Appointment, "get_pymongo_collection", lambda: collection)

    with pytest.raises(AppointmentMutationConflict):
        await AppointmentRepository.update_if_revision(
            str(OID_1), patient_id=OID_2, doctor_id=OID_3,
            expected_revision=0, set_fields={"status": "completed"},
        )

    query, update = collection.find_one_and_update.await_args.args
    assert query["patient_id"] == OID_2
    assert query["doctor_id"] == OID_3
    assert query["$or"] == [{"revision": 0}, {"revision": {"$exists": False}}]
    assert update["$inc"] == {"revision": 1}


@pytest.mark.asyncio
async def test_exercise_repository_rejects_stale_revision_before_any_progress_insert(monkeypatch):
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=None)
    monkeypatch.setattr(ExerciseAssignment, "get_pymongo_collection", lambda: collection)

    with pytest.raises(ExerciseAssignmentMutationConflict):
        await ExerciseRepository.update_assignment_if_revision(
            str(OID_1), patient_id=OID_2, expected_revision=3,
            set_fields={"status": "completed"},
        )

    query, update = collection.find_one_and_update.await_args.args
    assert query["revision"] == 3
    assert update["$inc"] == {"revision": 1}


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def with_transaction(self, callback):
        return await callback(self)


class _AtomicRevisionCollection:
    def __init__(self, document, client=None):
        self.document = document
        self.database = SimpleNamespace(client=client)
        self._lock = asyncio.Lock()

    async def find_one_and_update(self, query, update, **_kwargs):
        async with self._lock:
            current = self.document.get("revision")
            if "revision" in query and current != query["revision"]:
                return None
            if "$or" in query and current not in (None, 0):
                return None
            self.document.update(update.get("$set", {}))
            for field in update.get("$unset", {}):
                self.document.pop(field, None)
            self.document["revision"] = (current or 0) + update.get("$inc", {}).get("revision", 0)
            return dict(self.document)


@pytest.mark.asyncio
async def test_two_appointment_writers_with_one_revision_have_exactly_one_winner(monkeypatch):
    collection = _AtomicRevisionCollection({
        "_id": OID_1, "patient_id": OID_2, "doctor_id": OID_3,
        "appointment_date": datetime(2027, 1, 1), "time_slot": "09:00 AM",
        "reason": "Synthetic test", "status": "scheduled", "billing_status": "pending",
        "billing_amount": 0, "revision": 0, "created_at": datetime(2027, 1, 1),
    })
    monkeypatch.setattr(Appointment, "get_pymongo_collection", lambda: collection)
    monkeypatch.setattr(Appointment, "model_validate", staticmethod(lambda row: SimpleNamespace(**row)))

    results = await asyncio.gather(
        AppointmentRepository.update_if_revision(
            str(OID_1), patient_id=OID_2, doctor_id=OID_3,
            expected_revision=0, set_fields={"status": "in_progress"},
        ),
        AppointmentRepository.update_if_revision(
            str(OID_1), patient_id=OID_2, doctor_id=OID_3,
            expected_revision=0, set_fields={"status": "completed"},
        ),
        return_exceptions=True,
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1, repr(results)
    assert sum(isinstance(result, AppointmentMutationConflict) for result in results) == 1
    assert collection.document["revision"] == 1


@pytest.mark.asyncio
async def test_two_care_plan_writers_create_only_one_audit_and_notification(monkeypatch):
    session = _Session()
    client = MagicMock()
    client.start_session.return_value = session
    collection = _AtomicRevisionCollection({
        "_id": OID_1, "patient_id": OID_2, "therapist_id": OID_3,
        "title": "Synthetic plan", "description": "Offline fixture", "current_stage": 1,
        "stages": [], "goals": [], "recommendations": [],
        "start_date": datetime(2027, 1, 1), "target_date": datetime(2027, 2, 1),
        "status": "active", "revision": 0, "created_at": datetime(2027, 1, 1),
        "updated_at": datetime(2027, 1, 1),
    }, client)
    monkeypatch.setattr(CarePlan, "get_pymongo_collection", lambda: collection)
    monkeypatch.setattr(CarePlan, "model_validate", staticmethod(lambda row: SimpleNamespace(**row)))
    monkeypatch.setattr(Notification, "get_pymongo_collection", lambda *_args: MagicMock())
    history_insert = AsyncMock()
    notification_insert = AsyncMock()
    monkeypatch.setattr(CarePlanHistory, "insert", history_insert)
    monkeypatch.setattr(Notification, "insert", notification_insert)
    kwargs = dict(
        expected_revision=0, patient_id=OID_2, therapist_id=OID_3,
        set_fields={"status": "paused", "updated_at": datetime(2027, 1, 2)},
        history_data={"actor_user_id": OID_3, "action": "plan_paused"},
        notification_data={
            "recipient_user_id": OID_2, "title": "Changed", "message": "Changed",
            "notification_type": "care_plan", "related_entity_id": str(OID_1),
        },
    )
    results = await asyncio.gather(
        CarePlanRepository.update_with_side_effects(str(OID_1), **kwargs),
        CarePlanRepository.update_with_side_effects(str(OID_1), **kwargs),
        return_exceptions=True,
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1, repr(results)
    assert sum(isinstance(result, CarePlanMutationConflict) for result in results) == 1
    assert history_insert.await_count == 1
    assert notification_insert.await_count == 1


@pytest.mark.asyncio
async def test_two_progress_retries_insert_exactly_one_event(monkeypatch):
    session = _Session()
    client = MagicMock()
    client.start_session.return_value = session
    collection = _AtomicRevisionCollection({
        "_id": OID_1, "patient_id": OID_2, "status": "assigned", "revision": 0,
    }, client)
    monkeypatch.setattr(ExerciseAssignment, "get_pymongo_collection", lambda: collection)
    insert = AsyncMock(return_value=SimpleNamespace(id=OID_3))
    monkeypatch.setattr(ExerciseProgress, "insert", insert)

    def progress(identifier):
        return ExerciseProgress(
            id=identifier, patient_id=OID_2, assignment_id=OID_1, exercise_id=OID_3,
            care_plan_id=OID_1, stage_id="stage-1", completed_sets=1,
            completed_reps=5, duration_seconds=30, completion_status="partial",
        )

    calls = [ExerciseRepository.create_progress_with_assignment_transition(
        progress(identifier), assignment_id=str(OID_1), patient_id=OID_2,
        expected_revision=0, expected_status="assigned", next_status="in_progress",
    ) for identifier in (OID_2, OID_3)]
    results = await asyncio.gather(*calls, return_exceptions=True)
    assert sum(isinstance(result, ExerciseAssignmentMutationConflict) for result in results) == 1
    assert insert.await_count == 1
    assert collection.document["revision"] == 1


@pytest.mark.asyncio
async def test_progress_and_assignment_transition_share_one_transaction_session(monkeypatch):
    session = _Session()
    client = MagicMock()
    client.start_session.return_value = session
    collection = MagicMock()
    collection.database.client = client
    collection.find_one_and_update = AsyncMock(return_value={"_id": OID_1})
    monkeypatch.setattr(ExerciseAssignment, "get_pymongo_collection", lambda: collection)

    progress = ExerciseProgress(
        id=OID_3, patient_id=OID_2, assignment_id=OID_1, exercise_id=OID_3,
        care_plan_id=OID_1, stage_id="stage-1", completed_sets=1,
        completed_reps=5, duration_seconds=30, completion_status="partial",
    )
    insert = AsyncMock(return_value=progress)
    monkeypatch.setattr(ExerciseProgress, "insert", insert)

    saved = await ExerciseRepository.create_progress_with_assignment_transition(
        progress, assignment_id=str(OID_1), patient_id=OID_2,
        expected_revision=0, expected_status="assigned", next_status="in_progress",
    )

    assert saved is progress
    assert collection.find_one_and_update.await_args.kwargs["session"] is session
    assert insert.await_args.kwargs["session"] is session


@pytest.mark.asyncio
async def test_progress_transaction_fails_closed_when_sessions_are_unavailable(monkeypatch):
    client = MagicMock()
    client.start_session.side_effect = RuntimeError("transactions unavailable")
    collection = MagicMock()
    collection.database.client = client
    collection.find_one_and_update = AsyncMock()
    monkeypatch.setattr(ExerciseAssignment, "get_pymongo_collection", lambda: collection)
    progress = ExerciseProgress(
        patient_id=OID_2, assignment_id=OID_1, exercise_id=OID_3,
        care_plan_id=OID_1, stage_id="stage-1", completed_sets=1,
        completed_reps=5, duration_seconds=30, completion_status="partial",
    )
    insert = AsyncMock()
    monkeypatch.setattr(ExerciseProgress, "insert", insert)

    with pytest.raises(RuntimeError, match="transactions unavailable"):
        await ExerciseRepository.create_progress_with_assignment_transition(
            progress, assignment_id=str(OID_1), patient_id=OID_2,
            expected_revision=0, expected_status="assigned", next_status="in_progress",
        )
    collection.find_one_and_update.assert_not_awaited()
    insert.assert_not_awaited()


@pytest.mark.asyncio
async def test_care_plan_transaction_fails_closed_before_primary_write(monkeypatch):
    client = MagicMock()
    client.start_session.side_effect = RuntimeError("transactions unavailable")
    collection = MagicMock()
    collection.database.client = client
    collection.find_one_and_update = AsyncMock()
    monkeypatch.setattr(CarePlan, "get_pymongo_collection", lambda: collection)

    with pytest.raises(RuntimeError, match="transactions unavailable"):
        await CarePlanRepository.update_with_side_effects(
            str(OID_1), expected_revision=0, patient_id=OID_2,
            therapist_id=OID_3, set_fields={"status": "paused"},
            history_data={"actor_user_id": OID_3, "action": "plan_paused"},
        )
    collection.find_one_and_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_appointment_service_maps_stale_revision_to_explicit_409(monkeypatch):
    appointment = SimpleNamespace(
        id=OID_1, patient_id=OID_2, doctor_id=OID_3, status="in_progress",
        billing_status="pending", billing_amount=0,
    )
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(
        AppointmentRepository, "update_if_revision",
        AsyncMock(side_effect=AppointmentMutationConflict),
    )

    with pytest.raises(HTTPException) as exc:
        await AppointmentService.update_appointment(
            str(OID_1), AppointmentUpdate(status="completed", expected_revision=2),
            actor_user_id="admin", actor_role="admin",
        )
    assert exc.value.status_code == 409
    assert "Reload" in exc.value.detail


@pytest.mark.asyncio
async def test_home_visit_retry_repairs_optional_saved_address(monkeypatch):
    patient = SimpleNamespace(saved_home_address="Old address")
    save = AsyncMock()
    monkeypatch.setattr(
        "app.services.home_visit_service.ProfileRepository.save_patient", save
    )
    schema = SimpleNamespace(save_address=True, home_address="New address, Bengaluru")

    await HomeVisitService._persist_requested_address(patient, schema)
    await HomeVisitService._persist_requested_address(patient, schema)

    assert patient.saved_home_address == "New address, Bengaluru"
    save.assert_awaited_once_with(patient)


def test_backend_exposes_no_admin_patient_creation_contract():
    methods_by_path = {
        route.path: set(route.methods or set())
        for route in users.router.routes
    }
    assert "POST" not in methods_by_path.get("/patients", set())
