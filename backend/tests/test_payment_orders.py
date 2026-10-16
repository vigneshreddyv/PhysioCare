"""
Phase 4 Task 2 tests — server-side Razorpay order creation.

Covers the mandated appointment tests (1-11), laboratory tests (12-22), and
concurrency/repetition behavior (23-24). All Razorpay network calls are
mocked at the payment_service boundary. No real Razorpay servers are
contacted and no real payments are made.

NOTE ON CONCURRENCY: these tests simulate racing requests by controlling
what the atomic claim (PaymentRepository.find_one_and_update wrappers)
returns — the same contract the database enforces atomically. True
multi-connection races against a live MongoDB are outside unit scope; the
race-safety argument is documented in the service/repository docstrings.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import HTTPException

from app.core.config import settings
from app.schemas.payment import RazorpayOrderRequest
from app.services.payment_service import PaymentService

TEST_KEY_ID = "rzp_test_unitkeyid123"
TEST_SECRET = "test_key_secret_for_unit_tests_only"

P1 = "111111111111111111111111"  # owning patient profile id
P2 = "222222222222222222222222"  # other patient profile id
APT = "333333333333333333333333"
BOOK = "444444444444444444444444"

FAKE_ORDER = {"id": "order_fake123", "amount": 50000, "currency": "INR"}


@pytest.fixture(autouse=True)
def razorpay_test_config(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", TEST_KEY_ID)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", TEST_SECRET)


def make_patient(pid):
    p = MagicMock()
    p.id = pid
    return p


def make_appointment(status="pending_payment", amount=500.0, order_id=None,
                     patient_id=P1, appt_id=APT):
    a = MagicMock()
    a.id = appt_id
    a.patient_id = patient_id
    a.status = status
    a.billing_amount = amount
    a.payment_order_id = order_id
    return a


def make_booking(billing_status="pending", status="pending_payment", amount=1050.0,
                 order_id=None, patient_id=P1, booking_id=BOOK):
    b = MagicMock()
    b.id = booking_id
    b.patient_id = patient_id
    b.billing_status = billing_status
    b.status = status
    b.billing_amount = amount
    b.payment_order_id = order_id
    return b


def claim_doc(billing_amount):
    """What find_one_and_update(..., ReturnDocument.AFTER) returns."""
    return {"_id": APT, "billing_amount": billing_amount,
            "payment_order_id": FAKE_ORDER["id"]}


# ---------------------------------------------------------------------------
# APPOINTMENTS (tests 1-11)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_own_appointment_creates_order():
    """TEST 1: own appointment can create a Razorpay order."""
    appt = make_appointment()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)) as mock_create, \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock(return_value=claim_doc(500.0))) as mock_claim:

        resp = await PaymentService.create_appointment_order("user-1", APT)

    assert resp.order_id == "order_fake123"
    assert resp.key_id == TEST_KEY_ID          # public key only
    assert resp.amount == 50000
    assert resp.currency == "INR"
    mock_create.assert_called_once()
    mock_claim.assert_awaited_once_with(APT, "order_fake123")


@pytest.mark.asyncio
async def test_other_patients_appointment_rejected():
    """TEST 2: another patient's appointment is rejected (404, no leak)."""
    appt = make_appointment(patient_id=P2)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)):

        with pytest.raises(HTTPException) as e:
            await PaymentService.create_appointment_order("user-1", APT)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_backend_billing_amount_is_authoritative():
    """TEST 3: amount derives from stored billing_amount (500 -> 50000)."""
    appt = make_appointment(amount=500.0)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)) as mock_create, \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock(return_value=claim_doc(500.0))):

        resp = await PaymentService.create_appointment_order("user-1", APT)

    assert mock_create.call_args[0][0] == 50000  # amount paise
    assert resp.amount == 50000


@pytest.mark.asyncio
async def test_frontend_amount_cannot_override_backend():
    """TEST 4: no request field can influence the order amount.

    The endpoint body schema deliberately has no amount/billing_amount/
    currency/patient_id/payment_order_id fields, and unknown fields are
    ignored — so a client-supplied amount cannot reach the order pipeline.
    """
    body = RazorpayOrderRequest(**{"amount": 99999, "billing_amount": 1.0,
                                   "currency": "USD", "patient_id": P2})
    assert body.model_dump() == {}          # schema carries nothing
    assert not hasattr(body, "amount")

    # And the service itself takes no amount parameter at all:
    import inspect
    sig = inspect.signature(PaymentService.create_appointment_order)
    assert "amount" not in sig.parameters and "billing_amount" not in sig.parameters


@pytest.mark.asyncio
async def test_appointment_inr_paise_conversion():
    """TEST 5: exact Decimal conversion, incl. float-noise lab-style values."""
    for rupees, paise in [(500.0, 50000), (950.0, 95000),
                          (1050.3000000000002, 105030), (120.0, 12000)]:
        appt = make_appointment(amount=rupees)
        with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
                   new=AsyncMock(return_value=make_patient(P1))), \
             patch("app.services.payment_service.AppointmentRepository.get_by_id",
                   new=AsyncMock(return_value=appt)), \
             patch("app.services.payment_service.create_order",
                   return_value={**FAKE_ORDER, "amount": paise}), \
             patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
             patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
                   new=AsyncMock(return_value=claim_doc(rupees))):
            resp = await PaymentService.create_appointment_order("user-1", APT)
        assert resp.amount == paise


@pytest.mark.asyncio
async def test_appointment_order_payload_correct():
    """TEST 6: Razorpay request gets amount/currency/receipt/notes; no creds."""
    appt = make_appointment(amount=500.0)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)) as mock_create, \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock(return_value=claim_doc(500.0))):

        await PaymentService.create_appointment_order("user-1", APT)

    args, kwargs = mock_create.call_args
    amount_paise, currency, receipt, notes = args
    assert amount_paise == 50000
    assert currency == "INR"
    assert receipt == f"apt_{APT}"
    assert notes == {"payable_type": "appointment", "payable_id": APT}
    payload_repr = repr(args) + repr(kwargs)
    assert TEST_SECRET not in payload_repr and TEST_KEY_ID not in payload_repr


@pytest.mark.asyncio
async def test_appointment_payment_order_id_persisted():
    """TEST 7: the created order id is atomically bound to the appointment."""
    appt = make_appointment()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock(return_value=claim_doc(500.0))) as mock_claim:

        await PaymentService.create_appointment_order("user-1", APT)

    # The binding write path is the atomic claim with the Razorpay order id.
    mock_claim.assert_awaited_once_with(APT, FAKE_ORDER["id"])


@pytest.mark.asyncio
async def test_appointment_reuses_existing_order():
    """TEST 8: repeated request returns the existing active order — no new
    Razorpay order is created."""
    appt = make_appointment(order_id="order_existing_1")
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.create_order") as mock_create, \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock()) as mock_claim:

        resp = await PaymentService.create_appointment_order("user-1", APT)

    mock_create.assert_not_called()
    mock_claim.assert_not_called()
    assert resp.order_id == "order_existing_1"


@pytest.mark.asyncio
async def test_non_payable_appointment_rejected():
    """TEST 9: paid/confirmed/cancelled appointments cannot get orders."""
    for status_value in ["confirmed", "in_progress", "completed", "cancelled"]:
        appt = make_appointment(status=status_value)
        with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
                   new=AsyncMock(return_value=make_patient(P1))), \
             patch("app.services.payment_service.AppointmentRepository.get_by_id",
                   new=AsyncMock(return_value=appt)):
            with pytest.raises(HTTPException) as e:
                await PaymentService.create_appointment_order("user-1", APT)
            assert e.value.status_code == 409, status_value


@pytest.mark.asyncio
async def test_razorpay_api_failure_handled_safely():
    """TEST 10: API failure maps to 502 with a safe message."""
    from app.core.razorpay_client import RazorpayRequestError
    appt = make_appointment()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.create_order",
               side_effect=RazorpayRequestError("network or timeout")), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()):

        with pytest.raises(HTTPException) as e:
            await PaymentService.create_appointment_order("user-1", APT)
    assert e.value.status_code == 502
    assert TEST_SECRET not in str(e.value.detail)


@pytest.mark.asyncio
async def test_secret_never_in_appointment_errors_or_responses():
    """TEST 11: the secret never appears in any error path or response."""
    from app.core.razorpay_client import RazorpayConfigError

    # Missing appointment
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as e:
            await PaymentService.create_appointment_order("user-1", APT)
        assert TEST_SECRET not in str(e.value.detail)

    # Missing patient profile
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as e:
            await PaymentService.create_appointment_order("user-1", APT)
        assert TEST_SECRET not in str(e.value.detail)

    # Config missing -> 503
    appt = make_appointment()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.get_razorpay_client",
               side_effect=RazorpayConfigError("config missing")):
        with pytest.raises(HTTPException) as e:
            await PaymentService.create_appointment_order("user-1", APT)
        assert e.value.status_code == 503
        assert TEST_SECRET not in str(e.value.detail)

    # Success response exposes only key_id/order_id/amount/currency
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt)), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock(return_value=claim_doc(500.0))):
        resp = await PaymentService.create_appointment_order("user-1", APT)
        dumped = resp.model_dump()
        assert set(dumped) == {"key_id", "order_id", "amount", "currency",
                               "payable_type", "payable_id"}
        assert TEST_SECRET not in str(dumped)


# ---------------------------------------------------------------------------
# LABORATORY BOOKINGS (tests 12-22)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_own_lab_booking_creates_order():
    """TEST 12: own laboratory booking can create a Razorpay order."""
    booking = make_booking()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_laboratory_order",
               new=AsyncMock(return_value=claim_doc(1050.0))) as mock_claim:

        resp = await PaymentService.create_laboratory_booking_order("user-1", BOOK)

    assert resp.order_id == "order_fake123"
    assert resp.amount == 105000
    assert resp.currency == "INR"
    mock_claim.assert_awaited_once_with(BOOK, "order_fake123")


@pytest.mark.asyncio
async def test_other_patients_lab_booking_rejected():
    """TEST 13: another patient's booking is rejected."""
    booking = make_booking(patient_id=P2)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)):
        with pytest.raises(HTTPException) as e:
            await PaymentService.create_laboratory_booking_order("user-1", BOOK)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_lab_backend_billing_amount_is_authoritative():
    """TEST 14: catalog-derived stored amount is authoritative."""
    booking = make_booking(amount=700.5)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)) as mock_create, \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_laboratory_order",
               new=AsyncMock(return_value=claim_doc(700.5))):

        resp = await PaymentService.create_laboratory_booking_order("user-1", BOOK)

    assert mock_create.call_args[0][0] == 70050
    assert resp.amount == 70050


@pytest.mark.asyncio
async def test_lab_frontend_amount_cannot_override_backend():
    """TEST 15: no request field can influence the lab order amount."""
    body = RazorpayOrderRequest(**{"amount": 1, "billing_amount": 0.01,
                                   "currency": "USD", "payment_order_id": "order_attacker"})
    assert body.model_dump() == {}
    import inspect
    sig = inspect.signature(PaymentService.create_laboratory_booking_order)
    assert "amount" not in sig.parameters and "billing_amount" not in sig.parameters


@pytest.mark.asyncio
async def test_lab_inr_paise_conversion():
    """TEST 16: exact Decimal conversion incl. float-noise totals."""
    for rupees, paise in [(1050.3000000000002, 105030), (350.0, 35000),
                          (700.55, 70055), (1050.0, 105000)]:
        booking = make_booking(amount=rupees)
        with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
                   new=AsyncMock(return_value=make_patient(P1))), \
             patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
                   new=AsyncMock(return_value=booking)), \
             patch("app.services.payment_service.create_order",
                   return_value={**FAKE_ORDER, "amount": paise}), \
             patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
             patch("app.services.payment_service.PaymentRepository.claim_laboratory_order",
                   new=AsyncMock(return_value=claim_doc(rupees))):
            resp = await PaymentService.create_laboratory_booking_order("user-1", BOOK)
        assert resp.amount == paise


@pytest.mark.asyncio
async def test_lab_order_payload_correct():
    """TEST 17: Razorpay request gets amount/currency/receipt/notes; no creds."""
    booking = make_booking(amount=1050.0)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)) as mock_create, \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_laboratory_order",
               new=AsyncMock(return_value=claim_doc(1050.0))):

        await PaymentService.create_laboratory_booking_order("user-1", BOOK)

    amount_paise, currency, receipt, notes = mock_create.call_args[0]
    assert amount_paise == 105000
    assert currency == "INR"
    assert receipt == f"lab_{BOOK}"
    assert notes == {"payable_type": "laboratory_booking", "payable_id": BOOK}
    assert TEST_SECRET not in repr(mock_create.call_args)


@pytest.mark.asyncio
async def test_lab_payment_order_id_persisted():
    """TEST 18: the created order id is atomically bound to the booking."""
    booking = make_booking()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_laboratory_order",
               new=AsyncMock(return_value=claim_doc(1050.0))) as mock_claim:

        await PaymentService.create_laboratory_booking_order("user-1", BOOK)

    mock_claim.assert_awaited_once_with(BOOK, FAKE_ORDER["id"])


@pytest.mark.asyncio
async def test_lab_reuses_existing_order():
    """TEST 19: repeated request returns the existing active order."""
    booking = make_booking(order_id="order_existing_lab")
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.create_order") as mock_create, \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_laboratory_order",
               new=AsyncMock()) as mock_claim:

        resp = await PaymentService.create_laboratory_booking_order("user-1", BOOK)

    mock_create.assert_not_called()
    mock_claim.assert_not_called()
    assert resp.order_id == "order_existing_lab"


@pytest.mark.asyncio
async def test_non_payable_lab_booking_rejected():
    """TEST 20: paid/failed/cancelled/completed bookings cannot get orders."""
    cases = [
        make_booking(billing_status="paid"),
        make_booking(billing_status="failed"),
        make_booking(status="confirmed"),
        make_booking(status="cancelled"),
        make_booking(status="completed"),
    ]
    for booking in cases:
        with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
                   new=AsyncMock(return_value=make_patient(P1))), \
             patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
                   new=AsyncMock(return_value=booking)):
            with pytest.raises(HTTPException) as e:
                await PaymentService.create_laboratory_booking_order("user-1", BOOK)
            assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_lab_razorpay_api_failure_handled_safely():
    """TEST 21: API failure maps to 502 with a safe message."""
    from app.core.razorpay_client import RazorpayRequestError
    booking = make_booking()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=booking)), \
         patch("app.services.payment_service.create_order",
               side_effect=RazorpayRequestError("razorpay down")), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()):
        with pytest.raises(HTTPException) as e:
            await PaymentService.create_laboratory_booking_order("user-1", BOOK)
    assert e.value.status_code == 502
    assert TEST_SECRET not in str(e.value.detail)


@pytest.mark.asyncio
async def test_secret_never_in_lab_errors_or_responses():
    """TEST 22: the secret never appears in any lab error path or response."""
    from app.core.razorpay_client import RazorpayConfigError

    # Other patient's booking
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=make_booking(patient_id=P2))):
        with pytest.raises(HTTPException) as e:
            await PaymentService.create_laboratory_booking_order("user-1", BOOK)
        assert TEST_SECRET not in str(e.value.detail)

    # Booking not found
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as e:
            await PaymentService.create_laboratory_booking_order("user-1", BOOK)
        assert TEST_SECRET not in str(e.value.detail)

    # Config missing -> 503
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=make_booking())), \
         patch("app.services.payment_service.get_razorpay_client",
               side_effect=RazorpayConfigError("config missing")):
        with pytest.raises(HTTPException) as e:
            await PaymentService.create_laboratory_booking_order("user-1", BOOK)
        assert e.value.status_code == 503
        assert TEST_SECRET not in str(e.value.detail)

    # Invalid billing amount -> 409 (no order attempted)
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.LaboratoryBookingRepository.get_by_id",
               new=AsyncMock(return_value=make_booking(amount=0.0))), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()):
        with pytest.raises(HTTPException) as e:
            await PaymentService.create_laboratory_booking_order("user-1", BOOK)
        assert e.value.status_code == 409
        assert TEST_SECRET not in str(e.value.detail)


# ---------------------------------------------------------------------------
# CONCURRENCY / REPEATED ORDER CREATION (tests 23-24)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_racing_requests_do_not_create_two_active_orders():
    """TEST 23: two requests that both pass the 'no order yet' check do NOT
    end up with two active orders.

    Simulation of the real race: A and B both read the appointment with
    payment_order_id=None, both call Razorpay, then both attempt the atomic
    claim. The database-level find_one_and_update guard lets exactly ONE
    bind succeed (A). B's claim returns None; B re-reads, sees A's binding,
    and reuses it. Final state: one active order.
    """
    # --- Request A: claim wins ---
    appt_a = make_appointment()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(return_value=appt_a)), \
         patch("app.services.payment_service.create_order",
               return_value={**FAKE_ORDER, "id": "order_A"}), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock(return_value={**claim_doc(500.0),
                                           "payment_order_id": "order_A"})):
        resp_a = await PaymentService.create_appointment_order("user-1", APT)

    assert resp_a.order_id == "order_A"

    # --- Request B: read stale doc (no order), create, claim LOSES, reuse A's ---
    appt_b = make_appointment(order_id=None)  # stale read: still looks unbound
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(side_effect=[appt_b,
                                          make_appointment(order_id="order_A")])), \
         patch("app.services.payment_service.create_order",
               return_value={**FAKE_ORDER, "id": "order_B"}), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock(return_value=None)) as mock_claim_b:

        resp_b = await PaymentService.create_appointment_order("user-1", APT)

    # B attempted to bind only its own order id, atomically...
    mock_claim_b.assert_awaited_once_with(APT, "order_B")
    # ...the bind was refused, and B returned A's order — the single active one.
    assert resp_b.order_id == "order_A"
    assert resp_a.order_id == resp_b.order_id


@pytest.mark.asyncio
async def test_claim_refuses_binding_after_state_change():
    """TEST 24 (documented limitation boundary): if the appointment leaves the
    payable state while Razorpay was being called, the atomic claim refuses
    the binding and the request is rejected — no orphan binding attaches to a
    paid/cancelled appointment. The Razorpay-side order remains simply
    unattempted (never paid); this is the known, documented limitation: such
    an order lingers on Razorpay unused, which is harmless without checkout.
    """
    from unittest.mock import call

    appt = make_appointment()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(side_effect=[appt,
                                          make_appointment(status="confirmed")])), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock(return_value=None)) as mock_claim:

        with pytest.raises(HTTPException) as e:
            await PaymentService.create_appointment_order("user-1", APT)

    assert e.value.status_code == 409
    # Only one claim attempt was made (no blind retry against a paid state).
    mock_claim.assert_awaited_once_with(APT, FAKE_ORDER["id"])


@pytest.mark.asyncio
async def test_transient_claim_failure_retries_once_then_succeeds():
    """The claim is retried exactly once on a still-payable object when the
    first atomic attempt fails transiently (DB hiccup) — never in a loop."""
    appt = make_appointment()
    with patch("app.services.payment_service.ProfileRepository.get_patient_by_user_id",
               new=AsyncMock(return_value=make_patient(P1))), \
         patch("app.services.payment_service.AppointmentRepository.get_by_id",
               new=AsyncMock(side_effect=[appt, appt])), \
         patch("app.services.payment_service.create_order",
               return_value=dict(FAKE_ORDER)), \
         patch("app.services.payment_service.get_razorpay_client", return_value=MagicMock()), \
         patch("app.services.payment_service.PaymentRepository.claim_appointment_order",
               new=AsyncMock(side_effect=[None, claim_doc(500.0)])) as mock_claim:

        resp = await PaymentService.create_appointment_order("user-1", APT)

    assert mock_claim.await_count == 2
    assert resp.order_id == FAKE_ORDER["id"]
