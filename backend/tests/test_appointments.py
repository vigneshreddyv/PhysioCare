import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException
from beanie import PydanticObjectId
from datetime import datetime, timedelta, timezone

from app.schemas.appointment import AppointmentUpdate
from app.services.appointment_service import AppointmentService

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
