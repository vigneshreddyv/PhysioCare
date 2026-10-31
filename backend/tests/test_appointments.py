import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException
from beanie import PydanticObjectId
from datetime import datetime, timedelta, timezone

from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.appointment_service import AppointmentService
from app.models.appointment import ACTIVE_STATUSES, Appointment, canonical_appointment_date
from app.repositories.appointment_repository import AppointmentRepository
from pymongo.errors import DuplicateKeyError

@pytest.fixture(autouse=True)
def mock_format_repository_calls():
    # Setup mock patient user
    mock_patient_user = MagicMock()
    mock_patient_user.full_name = "Jane Patient"

    # Setup mock doctor user
    mock_doctor_user = MagicMock()
    mock_doctor_user.full_name = "Dr. John Doe"

    # Setup mock patient
    mock_patient = MagicMock()
    mock_patient.user_id = PydanticObjectId("000000000000000000000000")

    # Setup mock doctor
    mock_doctor = MagicMock()
    mock_doctor.id = PydanticObjectId("999999999999999999999999")
    mock_doctor.user_id = PydanticObjectId("999999999999999999999999")
    mock_doctor.specialization = "Physical Therapy"

    with patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_id", return_value=mock_patient), \
         patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_id", return_value=mock_doctor), \
         patch("app.repositories.user_repository.UserRepository.get_by_id", side_effect=lambda uid: mock_patient_user if str(uid) == str(mock_patient.user_id) else mock_doctor_user):
        yield

def create_test_appointment(appointment_id: str, patient_id: str, status: str = "scheduled") -> MagicMock:
    appt = MagicMock()
    appt.id = PydanticObjectId(appointment_id)
    appt.patient_id = PydanticObjectId(patient_id)
    appt.doctor_id = PydanticObjectId("999999999999999999999999")
    appt.service_type = "clinic_consultation"
    appt.appointment_date = datetime.now(timezone.utc) + timedelta(days=2)
    appt.time_slot = "09:00 AM"
    appt.reason = "Knee pain"
    appt.symptoms = "Swelling"
    appt.duration_days = 5
    appt.pain_level = "Medium"
    appt.visit_address = "123 Main St"
    appt.status = status
    appt.billing_status = "pending"
    appt.billing_amount = 120.0
    appt.payment_method = "offline"
    appt.payment_status = "pending"
    appt.payment_id = None
    appt.payment_order_id = None
    appt.meeting_link = None
    appt.feedback_rating = None
    appt.feedback_comment = None
    appt.created_at = datetime.now(timezone.utc)
    appt.save = AsyncMock(return_value=appt)
    return appt


def test_active_slot_indexes_protect_both_patient_and_doctor_capacity():
    indexes = {index.document["name"]: index.document for index in Appointment.Settings.indexes}
    assert indexes["uniq_patient_date_slot"]["unique"] is True
    assert indexes["uniq_doctor_date_slot"]["unique"] is True
    assert indexes["uniq_doctor_date_slot"]["key"] == {
        "doctor_id": 1, "appointment_date": 1, "time_slot": 1
    }
    assert indexes["uniq_doctor_date_slot"]["partialFilterExpression"] == {
        "status": {"$in": ACTIVE_STATUSES}
    }


def test_slot_index_status_semantics_release_terminal_appointments():
    index = next(
        index.document for index in Appointment.Settings.indexes
        if index.document["name"] == "uniq_doctor_date_slot"
    )

    assert set(ACTIVE_STATUSES) == {
        "pending_payment", "confirmed", "in_progress", "scheduled"
    }
    for terminal_status in ("cancelled", "completed", "no_show"):
        assert terminal_status not in index["partialFilterExpression"]["status"]["$in"]


def test_utc_calendar_normalization_handles_offsets_and_legacy_clock_times():
    utc_date = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)
    offset_date = datetime(2026, 1, 15, 23, 30, tzinfo=timezone(timedelta(hours=-5)))

    assert canonical_appointment_date(utc_date) == datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert canonical_appointment_date(offset_date) == datetime(2026, 1, 16, tzinfo=timezone.utc)


def test_unique_index_requires_legacy_timestamp_preflight():
    index = next(
        index.document for index in Appointment.Settings.indexes
        if index.document["name"] == "uniq_doctor_date_slot"
    )
    legacy_a = datetime(2026, 1, 15, 9, 0)
    legacy_b = datetime(2026, 1, 15, 15, 0)

    assert canonical_appointment_date(legacy_a) == canonical_appointment_date(legacy_b)
    assert index["key"] == {"doctor_id": 1, "appointment_date": 1, "time_slot": 1}
    # The index is on the raw stored timestamp, so these legacy values would
    # occupy distinct index keys until a migration normalizes them.
    assert legacy_a != legacy_b


@pytest.mark.asyncio
async def test_create_safely_converts_unique_slot_race_to_conflict_result():
    appointment = MagicMock()
    appointment.insert = AsyncMock(side_effect=DuplicateKeyError("duplicate slot"))
    assert await AppointmentRepository.create_safely(appointment) is None


@pytest.mark.asyncio
async def test_concurrent_insert_attempts_have_one_winner_and_one_conflict():
    winner = MagicMock()
    loser = MagicMock()
    insert = AsyncMock(side_effect=[winner, DuplicateKeyError("duplicate slot")])
    winner.insert = insert
    loser.insert = insert

    results = await asyncio.gather(
        AppointmentRepository.create_safely(winner),
        AppointmentRepository.create_safely(loser),
    )

    assert results == [winner, None]


@pytest.mark.asyncio
async def test_booking_insert_conflict_returns_slot_unavailable():
    from app.services.appointment_service import AppointmentService

    patient = MagicMock(id=PydanticObjectId("111111111111111111111111"))
    doctor = MagicMock(id=PydanticObjectId("999999999999999999999999"), consultation_fee=500)
    schema = AppointmentCreate(
        doctor_id=str(doctor.id),
        service_type="clinic_consultation",
        appointment_date=datetime.now(timezone.utc) + timedelta(days=4),
        time_slot="09:00 AM",
        reason="Knee pain",
    )
    with patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", new=AsyncMock(return_value=patient)), \
         patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_id", new=AsyncMock(return_value=doctor)), \
         patch("app.repositories.appointment_repository.AppointmentRepository.doctor_has_slot", new=AsyncMock(return_value=False)), \
         patch("app.repositories.appointment_repository.AppointmentRepository.patient_has_slot", new=AsyncMock(return_value=False)), \
         patch("app.services.appointment_service.Appointment", new=MagicMock(return_value=MagicMock())), \
         patch("app.repositories.appointment_repository.AppointmentRepository.create_safely", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc_info:
            await AppointmentService.create_appointment("patient-user", schema)

    assert exc_info.value.status_code == 409
    assert "no longer available" in exc_info.value.detail


@pytest.mark.asyncio
async def test_doctor_cannot_update_an_unassigned_appointment():
    appointment = create_test_appointment(
        "222222222222222222222222",
        "111111111111111111111111",
    )
    doctor = MagicMock()
    doctor.id = PydanticObjectId("aaaaaaaaaaaaaaaaaaaaaaaa")

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", new=AsyncMock(return_value=appointment)), \
         patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_user_id", new=AsyncMock(return_value=doctor)):
        with pytest.raises(HTTPException) as exc_info:
            await AppointmentService.update_appointment(
                appointment_id=str(appointment.id),
                schema=AppointmentUpdate(status="completed"),
                current_user_role="doctor",
                current_user_id="bbbbbbbbbbbbbbbbbbbbbbbb",
            )

    assert exc_info.value.status_code == 404
    appointment.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_assigned_doctor_can_update_status_and_meeting_link():
    appointment = create_test_appointment(
        "222222222222222222222222",
        "111111111111111111111111",
    )
    doctor = MagicMock()
    doctor.id = appointment.doctor_id

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", new=AsyncMock(side_effect=[appointment, appointment])), \
         patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_user_id", new=AsyncMock(return_value=doctor)), \
         patch("app.services.notification_service.NotificationService.create_notification", new=AsyncMock()):
        result = await AppointmentService.update_appointment(
            appointment_id=str(appointment.id),
            schema=AppointmentUpdate(status="in_progress", meeting_link="https://example.test/visit"),
            current_user_role="doctor",
            current_user_id="doctor-user",
        )

    assert appointment.status == "in_progress"
    assert appointment.meeting_link == "https://example.test/visit"
    appointment.save.assert_awaited_once()
    assert result.id == str(appointment.id)


@pytest.mark.asyncio
async def test_assigned_doctor_cannot_update_fields_outside_permitted_set():
    appointment = create_test_appointment(
        "222222222222222222222222",
        "111111111111111111111111",
    )
    doctor = MagicMock()
    doctor.id = appointment.doctor_id

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", new=AsyncMock(return_value=appointment)), \
         patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_user_id", new=AsyncMock(return_value=doctor)):
        with pytest.raises(HTTPException) as exc_info:
            await AppointmentService.update_appointment(
                appointment_id=str(appointment.id),
                schema=AppointmentUpdate(billing_amount=1.0),
                current_user_role="doctor",
                current_user_id="doctor-user",
            )

    assert exc_info.value.status_code == 403
    appointment.save.assert_not_awaited()

# --- F.1 Cancellation Tests ---

@pytest.mark.asyncio
async def test_patient_cancels_own_appointment():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("111111111111111111111111")
    mock_patient.user_id = PydanticObjectId("000000000000000000000000")

    mock_appt = create_test_appointment(
        appointment_id="222222222222222222222222",
        patient_id="111111111111111111111111",
        status="scheduled"
    )

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", return_value=mock_appt), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient):
        
        schema = AppointmentUpdate(status="cancelled")
        result = await AppointmentService.update_appointment(
            appointment_id=str(mock_appt.id),
            schema=schema,
            current_user_role="patient",
            current_user_id=str(mock_patient.user_id)
        )
        assert mock_appt.status == "cancelled"
        mock_appt.save.assert_called_once()

@pytest.mark.asyncio
async def test_patient_cannot_cancel_another_patients_appointment():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("111111111111111111111111")
    mock_patient.user_id = PydanticObjectId("000000000000000000000000")

    mock_appt = create_test_appointment(
        appointment_id="222222222222222222222222",
        patient_id="333333333333333333333333",  # Different patient
        status="scheduled"
    )

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", return_value=mock_appt), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient):
        
        schema = AppointmentUpdate(status="cancelled")
        with pytest.raises(HTTPException) as exc_info:
            await AppointmentService.update_appointment(
                appointment_id=str(mock_appt.id),
                schema=schema,
                current_user_role="patient",
                current_user_id=str(mock_patient.user_id)
            )
        assert exc_info.value.status_code == 404
        mock_appt.save.assert_not_called()

# --- F.3 Rescheduling Tests ---

@pytest.mark.asyncio
async def test_patient_reschedules_own_eligible_appointment():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("111111111111111111111111")
    mock_patient.user_id = PydanticObjectId("000000000000000000000000")

    mock_appt = create_test_appointment(
        appointment_id="222222222222222222222222",
        patient_id="111111111111111111111111",
        status="scheduled"
    )

    new_date = datetime.now(timezone.utc) + timedelta(days=5)

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", return_value=mock_appt), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient), \
         patch("app.repositories.appointment_repository.AppointmentRepository.doctor_has_slot", return_value=False) as mock_doc_slot, \
         patch("app.repositories.appointment_repository.AppointmentRepository.patient_has_slot", return_value=False) as mock_pat_slot:
        
        schema = AppointmentUpdate(appointment_date=new_date, time_slot="11:00 AM")
        result = await AppointmentService.update_appointment(
            appointment_id=str(mock_appt.id),
            schema=schema,
            current_user_role="patient",
            current_user_id=str(mock_patient.user_id)
        )
        assert mock_appt.time_slot == "11:00 AM"
        mock_appt.save.assert_called_once()
        mock_doc_slot.assert_called_once_with(str(mock_appt.doctor_id), new_date, "11:00 AM", exclude_appointment_id=str(mock_appt.id))

@pytest.mark.asyncio
async def test_patient_cannot_reschedule_another_patients_appointment():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("111111111111111111111111")
    mock_patient.user_id = PydanticObjectId("000000000000000000000000")

    mock_appt = create_test_appointment(
        appointment_id="222222222222222222222222",
        patient_id="333333333333333333333333",  # Different patient
        status="scheduled"
    )

    new_date = datetime.now(timezone.utc) + timedelta(days=5)

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", return_value=mock_appt), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient):
        
        schema = AppointmentUpdate(appointment_date=new_date, time_slot="11:00 AM")
        with pytest.raises(HTTPException) as exc_info:
            await AppointmentService.update_appointment(
                appointment_id=str(mock_appt.id),
                schema=schema,
                current_user_role="patient",
                current_user_id=str(mock_patient.user_id)
            )
        assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_patient_cannot_modify_unauthorized_fields():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("111111111111111111111111")
    mock_patient.user_id = PydanticObjectId("000000000000000000000000")

    mock_appt = create_test_appointment(
        appointment_id="222222222222222222222222",
        patient_id="111111111111111111111111",
        status="scheduled"
    )

    new_date = datetime.now(timezone.utc) + timedelta(days=5)

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", return_value=mock_appt), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient):
        
        # Trying to update doctor_id or billing_amount along with reschedule
        schema = AppointmentUpdate(appointment_date=new_date, billing_amount=100.0)
        with pytest.raises(HTTPException) as exc_info:
            await AppointmentService.update_appointment(
                appointment_id=str(mock_appt.id),
                schema=schema,
                current_user_role="patient",
                current_user_id=str(mock_patient.user_id)
            )
        assert exc_info.value.status_code == 403

@pytest.mark.asyncio
async def test_terminal_appointment_cannot_be_rescheduled():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("111111111111111111111111")
    mock_patient.user_id = PydanticObjectId("000000000000000000000000")

    mock_appt = create_test_appointment(
        appointment_id="222222222222222222222222",
        patient_id="111111111111111111111111",
        status="completed" # Terminal
    )

    new_date = datetime.now(timezone.utc) + timedelta(days=5)

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", return_value=mock_appt), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient):
        
        schema = AppointmentUpdate(appointment_date=new_date, time_slot="11:00 AM")
        with pytest.raises(HTTPException) as exc_info:
            await AppointmentService.update_appointment(
                appointment_id=str(mock_appt.id),
                schema=schema,
                current_user_role="patient",
                current_user_id=str(mock_patient.user_id)
            )
        assert exc_info.value.status_code == 400

@pytest.mark.asyncio
async def test_past_date_is_rejected():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("111111111111111111111111")
    mock_patient.user_id = PydanticObjectId("000000000000000000000000")

    mock_appt = create_test_appointment(
        appointment_id="222222222222222222222222",
        patient_id="111111111111111111111111",
        status="scheduled"
    )

    past_date = datetime.now(timezone.utc) - timedelta(days=1) # Past date

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", return_value=mock_appt), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient):
        
        schema = AppointmentUpdate(appointment_date=past_date, time_slot="11:00 AM")
        with pytest.raises(HTTPException) as exc_info:
            await AppointmentService.update_appointment(
                appointment_id=str(mock_appt.id),
                schema=schema,
                current_user_role="patient",
                current_user_id=str(mock_patient.user_id)
            )
        assert exc_info.value.status_code == 400

@pytest.mark.asyncio
async def test_occupied_slot_is_rejected():
    mock_patient = MagicMock()
    mock_patient.id = PydanticObjectId("111111111111111111111111")
    mock_patient.user_id = PydanticObjectId("000000000000000000000000")

    mock_appt = create_test_appointment(
        appointment_id="222222222222222222222222",
        patient_id="111111111111111111111111",
        status="scheduled"
    )
    original_date = mock_appt.appointment_date
    original_slot = mock_appt.time_slot

    new_date = datetime.now(timezone.utc) + timedelta(days=5)

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", return_value=mock_appt), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_user_id", return_value=mock_patient), \
         patch("app.repositories.appointment_repository.AppointmentRepository.doctor_has_slot", return_value=True): # Doctor occupied
        
        schema = AppointmentUpdate(appointment_date=new_date, time_slot="11:00 AM")
        with pytest.raises(HTTPException) as exc_info:
            await AppointmentService.update_appointment(
                appointment_id=str(mock_appt.id),
                schema=schema,
                current_user_role="patient",
                current_user_id=str(mock_patient.user_id)
            )
        assert exc_info.value.status_code == 400
        assert mock_appt.appointment_date == original_date
        assert mock_appt.time_slot == original_slot

@pytest.mark.asyncio
async def test_doctor_and_admin_behaviors_preserved():
    mock_appt = create_test_appointment(
        appointment_id="222222222222222222222222",
        patient_id="111111111111111111111111",
        status="scheduled"
    )

    new_date = datetime.now(timezone.utc) + timedelta(days=5)

    with patch("app.repositories.appointment_repository.AppointmentRepository.get_by_id", return_value=mock_appt):
        schema = AppointmentUpdate(appointment_date=new_date, billing_amount=180.0)
        result = await AppointmentService.update_appointment(
            appointment_id=str(mock_appt.id),
            schema=schema,
            current_user_role="admin"
        )
        assert mock_appt.billing_amount == 180.0
        mock_appt.save.assert_called_once()
