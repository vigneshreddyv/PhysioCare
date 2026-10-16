import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from beanie import PydanticObjectId
from pymongo import IndexModel
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.models.laboratory_test import LaboratoryTest
from app.models.laboratory_booking import LaboratoryBooking, EmbeddedTest
from app.services.laboratory_service import LaboratoryService
from app.repositories.laboratory_booking_repository import LaboratoryBookingRepository


# Override the database name for testing
settings.DATABASE_NAME = "test_physiocare"


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


# ---------------------------------------------------------------------------
# Regression tests for LaboratoryBookingRepository.find_conflicting_booking
#
# The method must look up the conflict via the Motor-compatible find path.
# In Beanie 2.1.0, AggregationQuery has no first_or_none() AND the aggregation
# path fails on this app's Motor client ("object AsyncIOMotorLatentCommandCursor
# can't be used in 'await' expression") — production raised before this was
# fixed. The repository now uses find_one() with the same conditions; these
# tests run the real repository method and pin the conflict-filter semantics.
# ---------------------------------------------------------------------------

PATIENT_OID = "000000000000000000000000"
CONFLICT_DATE = datetime(2026, 10, 1)


@pytest.mark.asyncio
async def test_find_conflicting_booking_returns_document():
    doc = MagicMock()
    with patch(
        "app.repositories.laboratory_booking_repository.LaboratoryBooking.find_one",
        new_callable=AsyncMock,
        return_value=doc,
    ) as mock_find_one:
        result = await LaboratoryBookingRepository.find_conflicting_booking(
            patient_id=PATIENT_OID,
            appointment_date=CONFLICT_DATE,
            time_slot="09:00 AM",
        )

        assert result is doc
        mock_find_one.assert_awaited_once()

        # Preserve existing conflict semantics: patient + date + slot + active billing status
        query = mock_find_one.await_args[0][0]
        assert str(query["patient_id"]) == PATIENT_OID
        assert query["appointment_date"] == CONFLICT_DATE
        assert query["time_slot"] == "09:00 AM"
        assert query["billing_status"] == {"$in": ["pending", "paid"]}
        assert "_id" not in query  # no exclusion by default


@pytest.mark.asyncio
async def test_find_conflicting_booking_returns_none_when_no_match():
    with patch(
        "app.repositories.laboratory_booking_repository.LaboratoryBooking.find_one",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await LaboratoryBookingRepository.find_conflicting_booking(
            patient_id=PATIENT_OID,
            appointment_date=CONFLICT_DATE,
            time_slot="09:00 AM",
        )
        assert result is None


@pytest.mark.asyncio
async def test_find_conflicting_booking_exclude_booking_id_appends_ne_match():
    with patch(
        "app.repositories.laboratory_booking_repository.LaboratoryBooking.find_one",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_find_one:
        await LaboratoryBookingRepository.find_conflicting_booking(
            patient_id=PATIENT_OID,
            appointment_date=CONFLICT_DATE,
            time_slot="09:00 AM",
            exclude_booking_id="0000000000000000000000aa",
        )

        query = mock_find_one.await_args[0][0]
        assert query["_id"] == {"$ne": PydanticObjectId("0000000000000000000000aa")}


# ---------------------------------------------------------------------------
# Concurrency-hardening regression tests: the database must be the final
# enforcement layer for the laboratory booking slot invariant.
# ---------------------------------------------------------------------------


def test_lab_booking_unique_index_definition():
    """The model must declare the partial unique slot index that mirrors the
    application-level conflict check (billing_status pending|paid)."""
    indexes = LaboratoryBooking.Settings.indexes
    assert any(isinstance(i, IndexModel) for i in indexes)
    idx = next(i for i in indexes if isinstance(i, IndexModel))
    assert idx.document["name"] == "uniq_patient_date_slot"
    assert idx.document["unique"] is True
    key = idx.document["key"]
    assert list(key.keys()) == ["patient_id", "appointment_date", "time_slot"]
    assert all(v == 1 for v in key.values())
    # Must gate on the SAME field/values the conflict check uses — not status
    assert idx.document["partialFilterExpression"] == {
        "billing_status": {"$in": ["pending", "paid"]}
    }


@pytest.mark.asyncio
async def test_validate_and_create_maps_duplicate_key_to_conflict():
    """TEST E — when a concurrent insert triggers the unique index, the loser
    must receive the application's conflict error, never a raw DB exception."""
    mock_test = MagicMock()
    mock_test.test_id = "cbc"
    mock_test.name = "CBC (Complete Blood Count)"
    mock_test.category = "Hematology"
    mock_test.sample = "Blood sample"
    mock_test.price = 350.0
    mock_test.active = True

    future_date = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")

    with patch("app.repositories.laboratory_test_repository.LaboratoryTestRepository.get_by_test_ids") as mock_get_tests, \
         patch("app.repositories.laboratory_booking_repository.LaboratoryBookingRepository.find_conflicting_booking", new_callable=AsyncMock) as mock_conflict, \
         patch("app.repositories.laboratory_booking_repository.LaboratoryBookingRepository.create", new_callable=AsyncMock) as mock_create:
        mock_get_tests.return_value = [mock_test]
        mock_conflict.return_value = None  # passes the app-level check (the race)
        mock_create.side_effect = DuplicateKeyError("E11000 duplicate key error")

        with pytest.raises(ValueError) as exc_info:
            await LaboratoryService.validate_and_create_booking(
                patient_id=PATIENT_OID,
                test_ids=["cbc"],
                appointment_date_str=future_date,
                time_slot="09:00 AM",
                visit_type="clinic",
                address=None,
            )

        # Same patient-facing message as the pre-insert conflict check
        assert "already have a pending or confirmed booking" in str(exc_info.value)
        mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_released_booking_billing_failed_stops_matching_conflict():
    """TEST D — the conflict query must not match a released booking
    (billing_status='failed' is the application's slot-release path), and the
    partial index filters identically."""
    from app.models.laboratory_booking import ACTIVE_BILLING_STATUSES

    with patch(
        "app.repositories.laboratory_booking_repository.LaboratoryBooking.find_one",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_find_one:
        await LaboratoryBookingRepository.find_conflicting_booking(
            patient_id=PATIENT_OID,
            appointment_date=CONFLICT_DATE,
            time_slot="09:00 AM",
        )
        query = mock_find_one.await_args[0][0]
        assert query["billing_status"] == {"$in": ACTIVE_BILLING_STATUSES}
        assert "failed" not in ACTIVE_BILLING_STATUSES