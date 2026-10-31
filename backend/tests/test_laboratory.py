import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from fastapi import HTTPException

from app.core.config import settings
from app.models.laboratory_test import LaboratoryTest
from app.models.laboratory_booking import LaboratoryBooking, EmbeddedTest
from app.services.laboratory_service import LaboratoryService
from app.repositories.laboratory_booking_repository import LaboratoryBookingRepository
from app.api.laboratory import update_laboratory_booking_status
from app.schemas.laboratory_booking import LaboratoryBookingStatusUpdate


# Override the database name for testing
settings.DATABASE_NAME = "test_physiocare"


@pytest.mark.asyncio
async def test_unassigned_doctor_cannot_update_laboratory_booking_status(
    monkeypatch,
):
    booking = MagicMock()
    booking.patient_id = "000000000000000000000000"
    monkeypatch.setattr(
        "app.api.laboratory.LaboratoryBookingRepository.get_by_id",
        AsyncMock(return_value=booking),
    )
    monkeypatch.setattr(
        "app.api.laboratory.require_doctor_patient_access",
        AsyncMock(side_effect=PermissionError("not assigned")),
    )
    update = AsyncMock()
    monkeypatch.setattr(LaboratoryService, "update_booking_status", update)

    with pytest.raises(HTTPException) as error:
        await update_laboratory_booking_status(
            "booking-id",
            LaboratoryBookingStatusUpdate(status="completed"),
            MagicMock(role="doctor", id="doctor-user-id"),
        )

    assert error.value.status_code == 403
    update.assert_not_awaited()


def test_laboratory_test_creation():
    test_data = {
        "test_id": "cbc",
        "name": "CBC (Complete Blood Count)",
        "category": "Hematology",
        "sample": "Blood sample",
        "price": 350.0,
        "active": True
    }
    test = LaboratoryTest.model_validate(test_data)
    assert test.test_id == "cbc"
    assert test.name == "CBC (Complete Blood Count)"
    assert test.category == "Hematology"
    assert test.sample == "Blood sample"
    assert test.price == 350.0
    assert test.active is True
    assert test.created_at is not None


def test_laboratory_booking_creation():
    embedded_tests_data = [
        {
            "test_id": "cbc",
            "name": "CBC",
            "sample": "Blood sample",
            "price": 350.0
        },
        {
            "test_id": "d-dimer",
            "name": "D-Dimer",
            "sample": "Blood sample",
            "price": 700.0
        }
    ]
    booking_data = {
        "patient_id": "000000000000000000000000",  # Valid ObjectId string (24 hex chars)
        "selected_tests": embedded_tests_data,
        "visit_type": "home",
        "appointment_date": datetime.utcnow() + timedelta(days=1),
        "time_slot": "08:00 AM",
        "address": "Test Address",
        "billing_amount": 1050.0
    }
    booking = LaboratoryBooking.model_validate(booking_data)
    assert str(booking.patient_id) == "000000000000000000000000"
    assert len(booking.selected_tests) == 2
    assert booking.visit_type == "home"
    assert booking.time_slot == "08:00 AM"
    assert booking.address == "Test Address"
    assert booking.billing_amount == 1050.0
    assert booking.billing_status == "pending"
    assert booking.payment_status is None
    assert booking.created_at is not None


@pytest.mark.asyncio
async def test_validate_and_create_booking_success():
    # Mock test repository to return active tests
    mock_test1 = MagicMock()
    mock_test1.test_id = "cbc"
    mock_test1.name = "CBC (Complete Blood Count)"
    mock_test1.category = "Hematology"
    mock_test1.sample = "Blood sample"
    mock_test1.price = 350.0
    mock_test1.active = True

    mock_test2 = MagicMock()
    mock_test2.test_id = "d-dimer"
    mock_test2.name = "D-Dimer"
    mock_test2.category = "Hematology"
    mock_test2.sample = "Blood sample"
    mock_test2.price = 700.0
    mock_test2.active = True

    # Create a mock booking object
    mock_booking = MagicMock()
    mock_booking.id = "booking123"
    mock_booking.patient_id = "000000000000000000000000"  # Valid ObjectId string (24 hex chars)
    mock_booking.selected_tests = []
    mock_booking.visit_type = "home"
    mock_booking.time_slot = "08:00 AM"
    mock_booking.address = "Test Address"
    mock_booking.billing_status = "pending"
    mock_booking.billing_amount = 1050.0
    mock_booking.payment_method = None
    mock_booking.payment_status = None
    mock_booking.payment_id = None
    mock_booking.payment_order_id = None
    mock_booking.created_at = datetime.utcnow()

    with patch("app.services.laboratory_service.LaboratoryTestRepository") as mock_test_repo, \
         patch("app.services.laboratory_service.LaboratoryBookingRepository") as mock_booking_repo, \
         patch("app.services.laboratory_service.LaboratoryBooking") as mock_booking_constructor, \
         patch("app.services.laboratory_service.EmbeddedTest") as mock_embedded_test_constructor:

        # Mock async methods to return values
        mock_test_repo.get_by_test_ids = AsyncMock(return_value=[mock_test1, mock_test2])
        mock_test_repo.get_active_tests = AsyncMock(return_value=[mock_test1, mock_test2])
        mock_booking_repo.find_conflicting_booking = AsyncMock(return_value=None)
        mock_booking_repo.create = AsyncMock(return_value=mock_booking)

        # Mock the EmbeddedTest constructor to return mock objects
        mock_embedded_test_constructor.side_effect = lambda test_id, name, sample, price: MagicMock(
            test_id=test_id,
            name=name,
            sample=sample,
            price=price
        )

        # Mock the LaboratoryBooking constructor to return our mock booking
        mock_booking_constructor.return_value = mock_booking

        # Call the service method
        booking = await LaboratoryService.validate_and_create_booking(
            patient_id="000000000000000000000000",  # Valid ObjectId string (24 hex chars)
            test_ids=["cbc", "d-dimer"],
            appointment_date_str=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
            time_slot="08:00 AM",
            visit_type="home",
            address="Test Address"
        )

        # Assertions
        assert booking is not None
        assert booking.id == "booking123"
        assert str(booking.patient_id) == "000000000000000000000000"
        assert booking.visit_type == "home"
        assert booking.time_slot == "08:00 AM"
        assert booking.address == "Test Address"
        assert booking.billing_amount == 1050.0
        assert booking.billing_status == "pending"

        # Verify repository calls
        mock_test_repo.get_by_test_ids.assert_called_once_with(["cbc", "d-dimer"])
        mock_booking_repo.find_conflicting_booking.assert_called_once()
        mock_booking_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_validate_and_create_booking_empty_test_list():
    with pytest.raises(ValueError) as exc_info:
        await LaboratoryService.validate_and_create_booking(
            patient_id="000000000000000000000000",
            test_ids=[],
            appointment_date_str=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
            time_slot="08:00 AM",
            visit_type="home",
            address="Test Address"
        )
    assert "At least one test must be selected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_and_create_booking_duplicate_test_ids():
    with pytest.raises(ValueError) as exc_info:
        await LaboratoryService.validate_and_create_booking(
            patient_id="000000000000000000000000",
            test_ids=["cbc", "cbc"],
            appointment_date_str=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
            time_slot="08:00 AM",
            visit_type="home",
            address="Test Address"
        )
    assert "Duplicate test IDs are not allowed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_and_create_booking_invalid_test_id():
    with patch("app.services.laboratory_service.LaboratoryTestRepository") as mock_test_repo:
        mock_test_repo.get_by_test_ids = AsyncMock(return_value=[])  # No tests found
        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.validate_and_create_booking(
                patient_id="patient123",
                test_ids=["invalid"],
                appointment_date_str=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
                time_slot="08:00 AM",
                visit_type="home",
                address="Test Address"
            )
        assert "Test with ID 'invalid' not found or inactive" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_and_create_booking_past_date():
    mock_test = MagicMock(test_id="cbc", name="CBC", category="Hematology", sample="Blood sample", price=350.0, active=True)
    with patch("app.services.laboratory_service.LaboratoryTestRepository") as mock_test_repo:
        mock_test_repo.get_by_test_ids = AsyncMock(return_value=[mock_test])
        past_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.validate_and_create_booking(
                patient_id="patient123",
                test_ids=["cbc"],
                appointment_date_str=past_date,
                time_slot="08:00 AM",
                visit_type="home",
                address="Test Address"
            )
        assert "Appointment date must be in the future" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_and_create_booking_invalid_time_slot():
    mock_test = MagicMock(test_id="cbc", name="CBC", category="Hematology", sample="Blood sample", price=350.0, active=True)
    with patch("app.services.laboratory_service.LaboratoryTestRepository") as mock_test_repo:
        mock_test_repo.get_by_test_ids = AsyncMock(return_value=[mock_test])
        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.validate_and_create_booking(
                patient_id="patient123",
                test_ids=["cbc"],
                appointment_date_str=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
                time_slot="Invalid Slot",
                visit_type="home",
                address="Test Address"
            )
        assert "Invalid time slot" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_and_create_booking_invalid_visit_type():
    mock_test = MagicMock(test_id="cbc", name="CBC", category="Hematology", sample="Blood sample", price=350.0, active=True)
    with patch("app.services.laboratory_service.LaboratoryTestRepository") as mock_test_repo:
        mock_test_repo.get_by_test_ids = AsyncMock(return_value=[mock_test])
        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.validate_and_create_booking(
                patient_id="patient123",
                test_ids=["cbc"],
                appointment_date_str=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
                time_slot="08:00 AM",
                visit_type="invalid",
                address="Test Address"
            )
        assert "Visit type must be either 'home' or 'clinic'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_and_create_booking_home_no_address():
    mock_test = MagicMock(test_id="cbc", name="CBC", category="Hematology", sample="Blood sample", price=350.0, active=True)
    with patch("app.services.laboratory_service.LaboratoryTestRepository") as mock_test_repo:
        mock_test_repo.get_by_test_ids = AsyncMock(return_value=[mock_test])
        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.validate_and_create_booking(
                patient_id="patient123",
                test_ids=["cbc"],
                appointment_date_str=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
                time_slot="08:00 AM",
                visit_type="home",
                address=""  # Empty address
            )
        assert "Address is required for home visits" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_and_create_booking_conflict():
    mock_test = MagicMock(test_id="cbc", name="CBC", category="Hematology", sample="Blood sample", price=350.0, active=True)
    with patch("app.services.laboratory_service.LaboratoryTestRepository") as mock_test_repo, \
         patch("app.services.laboratory_service.LaboratoryBookingRepository") as mock_booking_repo:

        mock_test_repo.get_by_test_ids = AsyncMock(return_value=[mock_test])
        # Mock existing booking
        mock_existing_booking = MagicMock()
        mock_booking_repo.find_conflicting_booking = AsyncMock(return_value=mock_existing_booking)

        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.validate_and_create_booking(
                patient_id="patient123",
                test_ids=["cbc"],
                appointment_date_str=(datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
                time_slot="08:00 AM",
                visit_type="home",
                address="Test Address"
            )
        assert "You already have a pending or confirmed booking at this date and time" in str(exc_info.value)


def test_new_booking_defaults_to_pending_payment():
    booking = LaboratoryBooking(
        patient_id="000000000000000000000000",
        selected_tests=[],
        visit_type="clinic",
        appointment_date=datetime.utcnow(),
        time_slot="09:00 AM",
        billing_amount=100.0
    )
    assert booking.status == "pending_payment"


@pytest.mark.asyncio
async def test_update_payment_confirmed_status():
    mock_booking = MagicMock()
    mock_booking.status = "pending_payment"
    mock_booking.billing_status = "pending"

    with patch("app.repositories.laboratory_booking_repository.LaboratoryBooking.get") as mock_get:
        mock_get.return_value = mock_booking
        mock_booking.save = AsyncMock()

        updated = await LaboratoryBookingRepository.update_payment(
            booking_id="60d5ec4b1234567890abcdef",
            payment_method="upi",
            payment_id="pay_1",
            payment_order_id="ord_1",
            payment_status="success",
            billing_status="paid"
        )
        assert updated.status == "confirmed"
        assert updated.billing_status == "paid"
        assert updated.payment_status == "success"


@pytest.mark.asyncio
async def test_update_payment_failed_status():
    mock_booking = MagicMock()
    mock_booking.status = "pending_payment"
    mock_booking.billing_status = "pending"

    with patch("app.repositories.laboratory_booking_repository.LaboratoryBooking.get") as mock_get:
        mock_get.return_value = mock_booking
        mock_booking.save = AsyncMock()

        updated = await LaboratoryBookingRepository.update_payment(
            booking_id="60d5ec4b1234567890abcdef",
            payment_method="upi",
            payment_id="pay_1",
            payment_order_id="ord_1",
            payment_status="failed",
            billing_status="failed"
        )
        assert updated.status == "failed"
        assert updated.billing_status == "failed"
        assert updated.payment_status == "failed"


@pytest.mark.asyncio
async def test_legacy_payment_rejects_client_supplied_success():
    with patch(
        "app.services.laboratory_service.LaboratoryBookingRepository.update_payment",
        new_callable=AsyncMock,
    ) as mock_update:
        with pytest.raises(HTTPException) as exc_info:
            await LaboratoryService.update_payment(
                booking_id="booking123",
                patient_id="patient123",
                payment_method="upi",
                payment_id="pay_fabricated",
                payment_order_id="ord_fabricated",
                payment_status="success",
            )

    assert exc_info.value.status_code == 410
    assert "server-side verification" in exc_info.value.detail
    mock_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_booking_status_admin_doctor_transitions():
    mock_booking = MagicMock()
    mock_booking.patient_id = "000000000000000000000000"
    mock_booking.id = "booking123"
    mock_booking.status = "confirmed"

    with patch("app.services.laboratory_service.LaboratoryBookingRepository.get_by_id") as mock_get_by_id, \
         patch("app.services.laboratory_service.Patient.get") as mock_patient_get:

        mock_get_by_id.return_value = mock_booking
        mock_booking.save = AsyncMock()
        mock_patient_get.return_value = None  # No notification side-effects

        # confirmed -> completed
        updated = await LaboratoryService.update_booking_status("booking123", "completed")
        assert updated.status == "completed"

        # Reset status to confirmed for cancellation test
        mock_booking.status = "confirmed"
        # confirmed -> cancelled
        updated = await LaboratoryService.update_booking_status("booking123", "cancelled")
        assert updated.status == "cancelled"


@pytest.mark.asyncio
async def test_update_booking_status_invalid_transitions():
    mock_booking = MagicMock()
    mock_booking.status = "pending_payment"

    with patch("app.services.laboratory_service.LaboratoryBookingRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = mock_booking

        # pending_payment -> completed (fails)
        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.update_booking_status("booking123", "completed")
        assert "Transition from 'pending_payment' to 'completed' is not allowed" in str(exc_info.value)

        # completed -> cancelled (fails)
        mock_booking.status = "completed"
        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.update_booking_status("booking123", "cancelled")
        assert "Transition from 'completed' to 'cancelled' is not allowed" in str(exc_info.value)

        # cancelled -> confirmed (fails)
        mock_booking.status = "cancelled"
        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.update_booking_status("booking123", "confirmed")
        assert "Transition from 'cancelled' to 'confirmed' is not allowed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_booking_status_not_found():
    with patch("app.services.laboratory_service.LaboratoryBookingRepository.get_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = None
        res = await LaboratoryService.update_booking_status("nonexistent", "completed")
        assert res is None
