import asyncio
import json
import threading
from datetime import datetime
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.api.payments import router as payments_router
from app.middleware.auth import get_current_user
from app.models.payment_attempt import PaymentAttempt, RazorpayWebhookEvent
from app.models.appointment import Appointment
from app.models.user import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.payment_service import PaymentService
from app.services.payment_reconciliation_worker import PaymentReconciliationWorker
from app.services.appointment_service import AppointmentService
from app.schemas.appointment import AppointmentUpdate
from app.main import app as main_app


def payment_attempt(status="pending", order_id="order_test_1"):
    return SimpleNamespace(
        id=PydanticObjectId("111111111111111111111111"),
        appointment_id=PydanticObjectId("222222222222222222222222"),
        patient_id=PydanticObjectId("333333333333333333333333"),
        provider_order_id=order_id,
        provider_payment_id=None,
        amount_paise=12000,
        currency="INR",
        status=status,
        reconciliation_status="pending",
        reconciliation_checked_at=None,
        processed_event_ids=[],
        updated_at=None,
        save=AsyncMock(),
    )


def configured_test_mode(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAZORPAY_MODE", "test")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_unit")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "unit-test-secret")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "unit-webhook-secret")
    monkeypatch.setattr(settings, "APPOINTMENT_BILLING_CURRENCY", "INR")


def configured_worker_test_mode(monkeypatch):
    configured_test_mode(monkeypatch)
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENT_RECONCILIATION_ENABLED", True)


class InMemoryCollection:
    """Tiny atomic-update fake for the appointment/payment transition tests."""

    def __init__(self, document):
        self.document = document

    @staticmethod
    def _matches(actual, expected):
        if isinstance(expected, dict):
            for operator, value in expected.items():
                if operator == "$ne" and actual == value:
                    return False
                if operator == "$nin" and actual in value:
                    return False
                if operator == "$exists" and value != (actual is not None):
                    return False
            return True
        return actual == expected

    def _query_matches(self, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._query_matches(part) for part in expected):
                    return False
            elif key == "$and":
                if not all(self._query_matches(part) for part in expected):
                    return False
            elif not self._matches(self.document.get(key), expected):
                return False
        return True

    async def update_one(self, query, update):
        if not self._query_matches(query):
            return SimpleNamespace(matched_count=0, modified_count=0)
        self.document.update(update.get("$set", {}))
        for key in update.get("$unset", {}):
            self.document.pop(key, None)
        return SimpleNamespace(matched_count=1, modified_count=1)


def captured_payment():
    return {
        "id": "pay_test_1",
        "order_id": "order_test_1",
        "amount": 12000,
        "currency": "INR",
        "status": "captured",
    }


def captured_webhook_body():
    return json.dumps({
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_1",
                    "order_id": "order_test_1",
                }
            }
        },
    }).encode()


def test_payment_indexes_have_distinct_names_and_reconciliation_keys():
    indexes = [
        *PaymentAttempt.Settings.indexes,
        *RazorpayWebhookEvent.Settings.indexes,
    ]
    names = [index.document["name"] for index in indexes]

    assert len(names) == len(set(names))
    reconciliation_index = next(
        index for index in PaymentAttempt.Settings.indexes
        if index.document["name"] == "payment_reconciliation_status_updated_at"
    )
    assert list(reconciliation_index.document["key"].items()) == [
        ("status", 1),
        ("reconciliation_status", 1),
        ("updated_at", 1),
    ]
    body_index = next(
        index for index in RazorpayWebhookEvent.Settings.indexes
        if index.document["name"] == "unique_razorpay_webhook_body_digest"
    )
    assert body_index.document["unique"] is True
    assert body_index.document["partialFilterExpression"] == {
        "body_digest": {"$type": "string"}
    }



def install_transition_fakes(monkeypatch, status="scheduled", billing_status="pending"):
    appointment_id = PydanticObjectId("222222222222222222222222")
    appointment_doc = {
        "_id": appointment_id,
        "patient_id": PydanticObjectId("333333333333333333333333"),
        "status": status,
        "billing_status": billing_status,
        "payment_status": "pending",
        "payment_order_id": "order_test_1",
        "payment_id": None,
        "billing_currency": "INR",
        "slot_claim": "doctor:slot",
    }
    appointment_collection = InMemoryCollection(appointment_doc)
    attempt = payment_attempt(status="pending")
    attempt_doc = {"_id": attempt.id, "status": "pending"}
    attempt_collection = InMemoryCollection(attempt_doc)
    monkeypatch.setattr(Appointment, "get_pymongo_collection", MagicMock(return_value=appointment_collection))
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", MagicMock(return_value=attempt_collection))
    monkeypatch.setattr(
        AppointmentRepository,
        "get_by_id",
        AsyncMock(side_effect=lambda _id: SimpleNamespace(**appointment_doc)),
    )
    return appointment_doc, attempt_doc, attempt, appointment_collection, attempt_collection


def configure_reconciliation_fakes(monkeypatch, appointment_doc, attempt):
    appointment_collection = InMemoryCollection(appointment_doc)
    monkeypatch.setattr(Appointment, "get_pymongo_collection", MagicMock(return_value=appointment_collection))
    monkeypatch.setattr(
        AppointmentRepository,
        "get_by_id",
        AsyncMock(side_effect=lambda _id: SimpleNamespace(**appointment_doc)),
    )
    attempt_doc = {
        "_id": attempt.id,
        "status": attempt.status,
        "provider_order_id": attempt.provider_order_id,
        "provider_payment_id": attempt.provider_payment_id,
        "reconciliation_status": attempt.reconciliation_status,
    }
    attempt_collection = InMemoryCollection(attempt_doc)
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", MagicMock(return_value=attempt_collection))
    query = MagicMock()
    query.sort.return_value = query
    selected_limit = {"value": 100}
    query.limit.side_effect = lambda value: (selected_limit.update(value=value), query)[1]
    query_filter_ref = {}

    async def fetch_selected_attempts():
        include_review = any(
            branch == {"reconciliation_status": "clinic_review"}
            for branch in query_filter_ref["filter"]["$or"]
        )
        stored_status = attempt_collection.document.get("reconciliation_status")
        eligible = attempt_collection.document.get("status") == "success" and (
            stored_status in {"pending", "clinic_review" if include_review else "pending"}
            or stored_status is None
        )
        if not eligible:
            return []
        stored_attempt = SimpleNamespace(
            id=attempt_collection.document["_id"],
            appointment_id=attempt.appointment_id,
            patient_id=attempt.patient_id,
            amount_paise=attempt.amount_paise,
            currency=attempt.currency,
            provider_order_id=attempt_collection.document.get("provider_order_id"),
            provider_payment_id=attempt_collection.document.get("provider_payment_id"),
            status=attempt_collection.document["status"],
            reconciliation_status=stored_status or "pending",
            reconciliation_checked_at=attempt_collection.document.get("reconciliation_checked_at"),
            processed_event_ids=[],
        )
        return [stored_attempt][:selected_limit["value"]]

    query.to_list = AsyncMock(side_effect=fetch_selected_attempts)
    def payment_attempt_find(filter):
        query_filter_ref["filter"] = filter
        return query

    monkeypatch.setattr(PaymentAttempt, "find", MagicMock(side_effect=payment_attempt_find))
    return appointment_collection, query, attempt_collection


def install_order_creation_fakes(monkeypatch, appointment_status="scheduled"):
    configured_test_mode(monkeypatch)
    appointment_id = PydanticObjectId("222222222222222222222222")
    patient_id = PydanticObjectId("333333333333333333333333")
    appointment_doc = {
        "_id": appointment_id,
        "patient_id": patient_id,
        "status": appointment_status,
        "billing_status": "pending",
        "payment_status": "not_started",
        "billing_currency": None,
        "payment_order_id": None,
    }
    appointment = SimpleNamespace(
        id=appointment_id,
        patient_id=patient_id,
        status=appointment_status,
        service_mode="clinic",
        billing_status="pending",
        billing_amount=120,
        billing_currency=None,
    )
    appointment_collection = InMemoryCollection(appointment_doc)
    monkeypatch.setattr(
        Appointment, "get_pymongo_collection", MagicMock(return_value=appointment_collection)
    )
    monkeypatch.setattr(
        PaymentService, "_get_owned_appointment", AsyncMock(return_value=appointment)
    )
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(PaymentAttempt, "insert", AsyncMock())
    saved_attempts = []

    async def save_attempt(attempt):
        saved_attempts.append(attempt)

    monkeypatch.setattr(PaymentAttempt, "save", save_attempt)
    provider_client = MagicMock()
    provider_client.order.create.return_value = {
        "id": "order_test_new",
        "amount": 12000,
        "currency": "INR",
    }
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=provider_client))
    return appointment, appointment_doc, appointment_collection, saved_attempts, provider_client


def test_amount_conversion_uses_exact_inr_paise_and_rejects_invalid_amounts():
    assert PaymentService.amount_to_paise(120) == 12000
    assert PaymentService.amount_to_paise("120.50") == 12050
    for amount in (0, -1, "1.001", "NaN", "not-an-amount"):
        with pytest.raises(HTTPException) as error:
            PaymentService.amount_to_paise(amount)
        assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_patient_cannot_create_payment_for_another_patients_appointment(monkeypatch):
    appointment = SimpleNamespace(
        id=PydanticObjectId("222222222222222222222222"),
        patient_id=PydanticObjectId("444444444444444444444444"),
    )
    patient_profile = SimpleNamespace(id=PydanticObjectId("333333333333333333333333"))
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient_profile))

    with pytest.raises(HTTPException) as error:
        await PaymentService._get_owned_appointment(str(appointment.id), "patient-user")

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_checkout_signature_must_verify_and_payment_must_be_captured(monkeypatch):
    configured_test_mode(monkeypatch)
    appointment = SimpleNamespace(id="appointment-1")
    attempt = payment_attempt()
    collection = MagicMock()
    collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", MagicMock(return_value=collection))
    appointment_collection = MagicMock()
    appointment_collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(Appointment, "get_pymongo_collection", MagicMock(return_value=appointment_collection))
    monkeypatch.setattr(
        AppointmentRepository,
        "get_by_id",
        AsyncMock(return_value=SimpleNamespace(billing_status="paid")),
    )
    monkeypatch.setattr(PaymentService, "_get_owned_appointment", AsyncMock(return_value=appointment))
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=attempt))
    verified = MagicMock()
    verified.utility.verify_payment_signature = MagicMock(return_value=True)
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=verified))
    monkeypatch.setattr(PaymentService, "_verify_provider_payment", AsyncMock(return_value={
        "id": "pay_test_1", "order_id": "order_test_1", "amount": 12000, "currency": "INR", "status": "captured",
    }))
    monkeypatch.setattr(PaymentService, "_update_appointment", AsyncMock())

    result = await PaymentService.verify_checkout("appointment-1", "patient-user", {
        "razorpay_order_id": "order_test_1",
        "razorpay_payment_id": "pay_test_1",
        "razorpay_signature": "signature",
    })

    assert result["status"] == "success"
    assert result["billing_status"] == "paid"
    assert attempt.status == "success"
    assert collection.update_one.await_count == 1


@pytest.mark.asyncio
async def test_invalid_checkout_signature_does_not_change_payment_or_appointment(monkeypatch):
    configured_test_mode(monkeypatch)
    monkeypatch.setattr(PaymentService, "_get_owned_appointment", AsyncMock(return_value=SimpleNamespace(id="appointment-1")))
    attempt = payment_attempt()
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=attempt))
    bad_signature = MagicMock()
    bad_signature.utility.verify_payment_signature = MagicMock(side_effect=ValueError("bad signature"))
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=bad_signature))
    update = AsyncMock()
    monkeypatch.setattr(PaymentService, "_update_appointment", update)

    with pytest.raises(HTTPException) as error:
        await PaymentService.verify_checkout("appointment-1", "patient-user", {
            "razorpay_order_id": "order_test_1",
            "razorpay_payment_id": "pay_test_1",
            "razorpay_signature": "invalid",
        })

    assert error.value.status_code == 400
    assert attempt.status == "pending"
    attempt.save.assert_not_awaited()
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_provider_payment_keeps_appointment_unpaid(monkeypatch):
    attempt = payment_attempt()
    collection = MagicMock()
    collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", MagicMock(return_value=collection))
    update = AsyncMock()
    monkeypatch.setattr(PaymentService, "_update_appointment", update)

    result = await PaymentService._apply_provider_payment(attempt, {
        "id": "pay_failed", "order_id": "order_test_1", "amount": 12000, "currency": "INR", "status": "failed",
    })

    assert result == "failed"
    assert attempt.status == "failed"
    assert "billing_status" not in update.await_args.args[1]
    assert update.await_args.args[1]["payment_status"] == "failed"
    assert collection.update_one.call_args.args[0]["status"] == {"$ne": "success"}


@pytest.mark.asyncio
async def test_capture_after_cancellation_is_recorded_for_reconciliation(monkeypatch):
    appointment_doc, attempt_doc, attempt, appointment_collection, _ = install_transition_fakes(
        monkeypatch, status="scheduled", billing_status="pending"
    )
    cancelled = await AppointmentRepository.cancel_scheduled(str(attempt.appointment_id), datetime.now())
    assert cancelled
    assert appointment_doc["status"] == "cancelled"

    result = await PaymentService._apply_provider_payment(attempt, captured_payment())

    assert result == "reconciliation_required"
    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["billing_status"] == "pending"
    assert appointment_doc["payment_status"] == "reconciliation_required"
    assert appointment_doc["payment_id"] == "pay_test_1"
    assert attempt_doc["status"] == "success"  # provider capture remains recorded


@pytest.mark.asyncio
async def test_payment_then_cancellation_preserves_capture_as_reconciliation(monkeypatch):
    appointment_doc, attempt_doc, attempt, _, _ = install_transition_fakes(monkeypatch)

    assert await PaymentService._apply_provider_payment(attempt, captured_payment()) == "success"
    assert appointment_doc["billing_status"] == "paid"
    assert appointment_doc["payment_status"] == "success"
    assert await AppointmentRepository.cancel_scheduled(str(attempt.appointment_id), datetime.now())

    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["billing_status"] == "paid"
    assert appointment_doc["payment_status"] == "reconciliation_required"
    assert appointment_doc["payment_id"] == "pay_test_1"
    assert attempt_doc["status"] == "success"


@pytest.mark.asyncio
async def test_legacy_paid_status_without_provider_success_is_not_flagged_as_capture(monkeypatch):
    appointment_doc, _, attempt, _, _ = install_transition_fakes(
        monkeypatch, status="scheduled", billing_status="paid"
    )

    assert await AppointmentRepository.cancel_scheduled(str(attempt.appointment_id), datetime.now())

    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["payment_status"] == "pending"


@pytest.mark.asyncio
async def test_duplicate_capture_finalization_is_idempotent(monkeypatch):
    appointment_doc, attempt_doc, attempt, _, _ = install_transition_fakes(monkeypatch)

    first = await PaymentService._apply_provider_payment(attempt, captured_payment())
    second = await PaymentService._apply_provider_payment(attempt, captured_payment())

    assert first == second == "success"
    assert appointment_doc["billing_status"] == "paid"
    assert appointment_doc["payment_id"] == "pay_test_1"
    assert attempt_doc["status"] == "success"


@pytest.mark.asyncio
async def test_admin_reconciliation_repairs_a_capture_after_interrupted_appointment_write(monkeypatch):
    configured_worker_test_mode(monkeypatch)
    appointment_doc, attempt_doc, attempt, appointment_collection, _ = install_transition_fakes(monkeypatch)
    appointment_collection.update_one = AsyncMock(side_effect=RuntimeError("simulated process interruption"))

    with pytest.raises(RuntimeError, match="simulated process interruption"):
        await PaymentService._apply_provider_payment(attempt, captured_payment())

    # Simulate the process stopping after the trusted attempt write but before
    # the appointment write, then retry from the authorized reconciliation path.
    assert attempt_doc["status"] == "success"
    assert attempt_doc["provider_payment_id"] == "pay_test_1"
    assert appointment_doc["billing_status"] == "pending"
    _, query, attempt_collection = configure_reconciliation_fakes(monkeypatch, appointment_doc, attempt)

    worker = PaymentReconciliationWorker()
    monkeypatch.setattr(worker, "_acquire_lease", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_release_lease", AsyncMock())
    result = await worker.run_once()

    assert result == {"examined": 1, "recovered": 1, "clinic_review": [], "failed": []}
    assert attempt_collection.document["reconciliation_status"] == "reconciled"
    assert appointment_doc["billing_status"] == "paid"
    assert appointment_doc["payment_status"] == "success"
    assert appointment_doc["payment_id"] == "pay_test_1"
    query.to_list.assert_awaited_once()

    restarted_worker = PaymentReconciliationWorker()
    monkeypatch.setattr(restarted_worker, "_acquire_lease", AsyncMock(return_value=True))
    monkeypatch.setattr(restarted_worker, "_release_lease", AsyncMock())
    restarted_result = await restarted_worker.run_once()
    assert restarted_result == {"examined": 0, "recovered": 0, "clinic_review": [], "failed": []}


@pytest.mark.asyncio
async def test_reconciliation_is_idempotent_and_does_not_overwrite_newer_payment(monkeypatch):
    appointment_doc = {
        "_id": PydanticObjectId("222222222222222222222222"),
        "patient_id": PydanticObjectId("333333333333333333333333"),
        "status": "scheduled",
        "billing_status": "paid",
        "payment_status": "success",
        "payment_order_id": "order_test_1",
        "payment_id": "pay_test_1",
    }
    attempt = payment_attempt(status="success")
    attempt.provider_payment_id = "pay_test_1"
    collection, _, attempt_collection = configure_reconciliation_fakes(monkeypatch, appointment_doc, attempt)

    first = await PaymentService.reconcile_captured_payments()
    second = await PaymentService.reconcile_captured_payments()

    assert first["recovered"] == second["recovered"] == 0
    assert first["clinic_review"] == second["clinic_review"] == []
    assert collection.document["payment_id"] == "pay_test_1"

    attempt_collection.document["reconciliation_status"] = "pending"
    appointment_doc.update({"payment_order_id": "order_newer", "payment_id": "pay_newer"})
    conflict = await PaymentService.reconcile_captured_payments()
    assert conflict["recovered"] == 0
    assert conflict["clinic_review"][0]["reason"] == "The appointment has a newer or conflicting payment state."
    assert appointment_doc["payment_id"] == "pay_newer"


@pytest.mark.asyncio
async def test_reconciliation_preserves_cancelled_appointment_and_surfaces_capture(monkeypatch):
    appointment_doc = {
        "_id": PydanticObjectId("222222222222222222222222"),
        "patient_id": PydanticObjectId("333333333333333333333333"),
        "status": "cancelled",
        "billing_status": "pending",
        "payment_status": "pending",
        "payment_order_id": "order_test_1",
        "payment_id": None,
    }
    attempt = payment_attempt(status="success")
    attempt.provider_payment_id = "pay_test_1"
    configure_reconciliation_fakes(monkeypatch, appointment_doc, attempt)

    result = await PaymentService.reconcile_captured_payments()

    assert result["recovered"] == 0
    assert result["clinic_review"][0]["reason"].startswith("Captured funds for this cancelled appointment")
    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["billing_status"] == "pending"
    assert appointment_doc["payment_status"] == "reconciliation_required"
    assert appointment_doc["payment_id"] == "pay_test_1"


@pytest.mark.asyncio
async def test_reconciliation_ignores_pending_and_failed_attempts(monkeypatch):
    pending = payment_attempt(status="pending")
    failed = payment_attempt(status="failed")
    query = MagicMock()
    query.sort.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    find = MagicMock(return_value=query)
    monkeypatch.setattr(PaymentAttempt, "find", find)

    result = await PaymentService.reconcile_captured_payments(batch_size=7)

    assert result == {"examined": 0, "recovered": 0, "clinic_review": [], "failed": []}
    assert find.call_args.args[0]["status"] == "success"
    query.sort.assert_called_once_with("updated_at")
    query.limit.assert_called_once_with(7)
    assert pending.status != "success" and failed.status != "success"


@pytest.mark.asyncio
async def test_reconciliation_stops_before_next_record_when_lease_is_lost(monkeypatch):
    first = payment_attempt(status="success", order_id="order_first")
    first.provider_payment_id = "pay_first"
    second = payment_attempt(status="success", order_id="order_second")
    second.id = PydanticObjectId("444444444444444444444444")
    second.appointment_id = PydanticObjectId("555555555555555555555555")
    second.provider_payment_id = "pay_second"
    appointment = SimpleNamespace(
        patient_id=first.patient_id,
        status="cancelled",
        payment_status="reconciliation_required",
        payment_order_id=first.provider_order_id,
        payment_id=first.provider_payment_id,
    )
    monkeypatch.setattr(
        AppointmentRepository,
        "get_by_id",
        AsyncMock(return_value=appointment),
    )
    attempt_collection = MagicMock()
    attempt_collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", MagicMock(return_value=attempt_collection))
    query = MagicMock()
    query.sort.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[first, second])
    monkeypatch.setattr(PaymentAttempt, "find", MagicMock(return_value=query))
    checks = 0

    def still_owns_lease():
        nonlocal checks
        checks += 1
        return checks == 1

    result = await PaymentService.reconcile_captured_payments(
        include_clinic_review=False,
        should_continue=still_owns_lease,
    )

    assert result["examined"] == 1
    assert len(result["clinic_review"]) == 1
    AppointmentRepository.get_by_id.assert_awaited_once_with(str(first.appointment_id))


@pytest.mark.asyncio
async def test_manual_and_worker_reconciliation_can_overlap_safely(monkeypatch):
    configured_worker_test_mode(monkeypatch)
    appointment_doc, _, attempt, _, _ = install_transition_fakes(monkeypatch)
    attempt.status = "success"
    attempt.provider_payment_id = "pay_test_1"
    configure_reconciliation_fakes(monkeypatch, appointment_doc, attempt)
    first_two_reads_complete = asyncio.Event()
    read_count = 0

    async def synchronized_appointment_read(_appointment_id):
        nonlocal read_count
        read_count += 1
        snapshot = SimpleNamespace(**appointment_doc)
        if read_count <= 2:
            if read_count == 2:
                first_two_reads_complete.set()
            await first_two_reads_complete.wait()
        return snapshot

    monkeypatch.setattr(AppointmentRepository, "get_by_id", synchronized_appointment_read)
    worker = PaymentReconciliationWorker()
    monkeypatch.setattr(worker, "_acquire_lease", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_release_lease", AsyncMock())

    manual_task = asyncio.create_task(
        PaymentService.reconcile_captured_payments(include_clinic_review=True)
    )
    worker_task = asyncio.create_task(worker.run_once())
    manual_result, worker_result = await asyncio.gather(manual_task, worker_task)

    assert manual_result["failed"] == worker_result["failed"] == []
    assert manual_result["clinic_review"] == worker_result["clinic_review"] == []
    assert manual_result["recovered"] + worker_result["recovered"] == 1
    assert appointment_doc["billing_status"] == "paid"
    assert appointment_doc["payment_id"] == "pay_test_1"


@pytest.mark.asyncio
async def test_reconciliation_continues_after_one_record_fails(monkeypatch):
    failed_attempt = payment_attempt(status="success", order_id="order_failed_record")
    failed_attempt.id = PydanticObjectId("111111111111111111111111")
    failed_attempt.provider_payment_id = "pay_failed_record"
    review_attempt = payment_attempt(status="success", order_id="order_cancelled_record")
    review_attempt.id = PydanticObjectId("444444444444444444444444")
    review_attempt.appointment_id = PydanticObjectId("555555555555555555555555")
    review_attempt.provider_payment_id = "pay_cancelled_record"
    cancelled_appointment = SimpleNamespace(
        id=review_attempt.appointment_id,
        patient_id=review_attempt.patient_id,
        status="cancelled",
        payment_status="reconciliation_required",
        payment_order_id=review_attempt.provider_order_id,
        payment_id=review_attempt.provider_payment_id,
    )
    async def get_appointment(appointment_id):
        if appointment_id == str(failed_attempt.appointment_id):
            raise RuntimeError("isolated database read failure")
        return cancelled_appointment

    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(side_effect=get_appointment))
    attempt_collection = MagicMock()
    attempt_collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", MagicMock(return_value=attempt_collection))
    query = MagicMock()
    query.sort.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[failed_attempt, review_attempt])
    monkeypatch.setattr(PaymentAttempt, "find", MagicMock(return_value=query))

    result = await PaymentService.reconcile_captured_payments()

    assert result["examined"] == 2
    assert len(result["failed"]) == 1
    assert result["failed"][0]["appointment_id"] == str(failed_attempt.appointment_id)
    assert len(result["clinic_review"]) == 1
    assert result["clinic_review"][0]["appointment_id"] == str(review_attempt.appointment_id)


@pytest.mark.asyncio
async def test_worker_retries_temporary_failure_for_cancelled_capture(monkeypatch):
    configured_worker_test_mode(monkeypatch)
    appointment_doc, _, attempt, _, _ = install_transition_fakes(
        monkeypatch, status="cancelled", billing_status="pending"
    )
    attempt.status = "success"
    attempt.provider_payment_id = "pay_test_1"
    appointment_doc.update({
        "payment_status": "reconciliation_required",
        "payment_id": "pay_test_1",
    })
    _, _, attempt_collection = configure_reconciliation_fakes(
        monkeypatch, appointment_doc, attempt
    )
    monkeypatch.setattr(
        AppointmentRepository,
        "get_by_id",
        AsyncMock(side_effect=[
            RuntimeError("temporary database read failure"),
            SimpleNamespace(**appointment_doc),
        ]),
    )
    worker = PaymentReconciliationWorker()
    monkeypatch.setattr(worker, "_acquire_lease", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "_release_lease", AsyncMock())

    first = await worker.run_once()
    second = await worker.run_once()

    assert len(first["failed"]) == 1
    assert first["clinic_review"] == []
    assert second["failed"] == []
    assert len(second["clinic_review"]) == 1
    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["payment_status"] == "reconciliation_required"
    assert attempt_collection.document["status"] == "success"
    assert attempt_collection.document["reconciliation_status"] == "clinic_review"


@pytest.mark.asyncio
async def test_admin_reconciliation_route_requires_admin_role(monkeypatch):
    app = FastAPI()
    app.include_router(payments_router, prefix="/api")
    operation = AsyncMock(return_value={"examined": 0, "recovered": 0, "clinic_review": [], "failed": []})
    review_list = AsyncMock(return_value={"clinic_review": []})
    monkeypatch.setattr(PaymentService, "reconcile_captured_payments", operation)
    monkeypatch.setattr(PaymentService, "list_captured_payment_reviews", review_list)
    monkeypatch.setattr(User, "get_pymongo_collection", MagicMock(return_value=MagicMock()))
    user = User(email="admin@example.com", hashed_password="unused", role="admin", full_name="Demo Admin")
    app.dependency_overrides[get_current_user] = lambda: user
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        allowed = await client.post("/api/payments/admin/reconcile-captured")
        assert allowed.status_code == 200
        assert allowed.json() == {"examined": 0, "recovered": 0, "clinic_review": [], "failed": []}
        review = await client.get("/api/payments/admin/captured-review")
        assert review.status_code == 200
        assert review.json() == {"clinic_review": []}

        app.dependency_overrides[get_current_user] = lambda: User(
            email="patient@example.com", hashed_password="unused", role="patient", full_name="Demo Patient"
        )
        denied = await client.post("/api/payments/admin/reconcile-captured")
        assert denied.status_code == 403
        denied_review = await client.get("/api/payments/admin/captured-review")
        assert denied_review.status_code == 403

    operation.assert_awaited_once()


@pytest.mark.asyncio
async def test_capture_webhook_after_cancellation_keeps_booking_cancelled(monkeypatch):
    configured_test_mode(monkeypatch)
    appointment_doc, attempt_doc, attempt, _, _ = install_transition_fakes(
        monkeypatch, status="cancelled", billing_status="pending"
    )
    event = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_test_1", "order_id": "order_test_1"}}},
    }
    utility = MagicMock()
    utility.utility.verify_webhook_signature = MagicMock(return_value=True)
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "find_one",
        AsyncMock(side_effect=[None, SimpleNamespace(status="processed")]),
    )
    monkeypatch.setattr(RazorpayWebhookEvent, "insert", AsyncMock())
    monkeypatch.setattr(RazorpayWebhookEvent, "get_pymongo_collection", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=attempt))
    monkeypatch.setattr(PaymentService, "_verify_provider_payment", AsyncMock(return_value=captured_payment()))
    webhook_save = AsyncMock()
    monkeypatch.setattr(RazorpayWebhookEvent, "save", webhook_save)

    response = await PaymentService.handle_webhook(
        json.dumps(event).encode(), "valid-test-signature", "evt_race_test"
    )
    duplicate = await PaymentService.handle_webhook(
        json.dumps(event).encode(), "valid-test-signature", "evt_race_test"
    )

    assert response == {"status": "reconciliation_required"}
    assert duplicate == {"status": "duplicate"}
    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["billing_status"] == "pending"
    assert appointment_doc["payment_status"] == "reconciliation_required"
    assert attempt_doc["status"] == "success"
    assert attempt_doc.get("reconciliation_status", "pending") == "pending"
    PaymentService._verify_provider_payment.assert_awaited_once()
    webhook_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_checkout_api_capture_after_cancellation_reconciles_to_clinic_review(monkeypatch):
    configured_test_mode(monkeypatch)
    appointment_doc, _, attempt, _, _ = install_transition_fakes(
        monkeypatch, status="cancelled", billing_status="pending"
    )
    monkeypatch.setattr(
        PaymentService,
        "_get_owned_appointment",
        AsyncMock(return_value=SimpleNamespace(id=attempt.appointment_id)),
    )
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=attempt))
    monkeypatch.setattr(
        AppointmentRepository,
        "get_by_id",
        AsyncMock(side_effect=lambda _id: SimpleNamespace(**appointment_doc)),
    )
    provider_client = MagicMock()
    provider_client.utility.verify_payment_signature.return_value = True
    provider_client.payment.fetch.return_value = captured_payment()
    provider_client.payment.refund.create = MagicMock()
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=provider_client))

    app = FastAPI()
    app.include_router(payments_router, prefix="/api")
    patient = SimpleNamespace(role="patient", id=attempt.patient_id)
    app.dependency_overrides[get_current_user] = lambda: patient
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/appointments/{attempt.appointment_id}/payments/verify",
            json={
                "razorpay_order_id": attempt.provider_order_id,
                "razorpay_payment_id": "pay_test_1",
                "razorpay_signature": "mocked-provider-signature",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "reconciliation_required"
    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["payment_status"] == "reconciliation_required"
    assert attempt.status == "success"
    assert attempt.provider_payment_id == "pay_test_1"

    _, _, attempt_collection = configure_reconciliation_fakes(
        monkeypatch, appointment_doc, attempt
    )
    reconciliation = await PaymentService.reconcile_captured_payments(
        include_clinic_review=True
    )
    assert reconciliation["recovered"] == 0
    assert len(reconciliation["clinic_review"]) == 1
    assert attempt_collection.document["reconciliation_status"] == "clinic_review"

    review_query = MagicMock()
    review_query.sort.return_value = review_query
    review_query.limit.return_value = review_query
    review_query.to_list = AsyncMock(return_value=[
        SimpleNamespace(
            id=attempt.id,
            appointment_id=attempt.appointment_id,
            patient_id=attempt.patient_id,
            amount_paise=attempt.amount_paise,
            currency=attempt.currency,
            provider_order_id=attempt.provider_order_id,
            provider_payment_id=attempt.provider_payment_id,
            status="success",
            reconciliation_status=attempt_collection.document["reconciliation_status"],
        )
    ])
    monkeypatch.setattr(PaymentAttempt, "find", MagicMock(return_value=review_query))

    admin = SimpleNamespace(role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        review_response = await client.get("/api/payments/admin/captured-review")

    assert review_response.status_code == 200
    assert review_response.json()["clinic_review"] == [{
        "appointment_id": str(attempt.appointment_id),
        "amount_paise": 12000,
        "currency": "INR",
        "appointment_status": "cancelled",
        "payment_status": "reconciliation_required",
        "reason": "Captured funds for this cancelled appointment require clinic reconciliation.",
    }]
    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["payment_status"] == "reconciliation_required"
    assert attempt_collection.document["status"] == "success"
    assert attempt_collection.document["reconciliation_status"] == "clinic_review"
    provider_client.payment.refund.create.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_signature_is_checked_against_original_body(monkeypatch):
    configured_test_mode(monkeypatch)
    monkeypatch.setattr(RazorpayWebhookEvent, "get_pymongo_collection", MagicMock(return_value=MagicMock()))
    raw = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_test_1", "order_id": "order_test_1"}}}}).encode()
    utility = MagicMock()
    utility.utility.verify_webhook_signature = MagicMock(return_value=True)
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    attempt = payment_attempt()
    monkeypatch.setattr(RazorpayWebhookEvent, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(RazorpayWebhookEvent, "insert", AsyncMock())
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=attempt))
    monkeypatch.setattr(PaymentService, "_verify_provider_payment", AsyncMock(return_value={
        "id": "pay_test_1", "order_id": "order_test_1", "amount": 12000, "currency": "INR", "status": "captured",
    }))
    monkeypatch.setattr(PaymentService, "_apply_provider_payment", AsyncMock(return_value="success"))
    monkeypatch.setattr(RazorpayWebhookEvent, "save", AsyncMock())

    result = await PaymentService.handle_webhook(raw, "provider-signature", "evt_test_1")

    assert result == {"status": "success"}
    assert utility.utility.verify_webhook_signature.call_args.args[0] == raw.decode("utf-8")


@pytest.mark.asyncio
async def test_invalid_webhook_signature_is_rejected_before_database_access(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature = MagicMock(side_effect=ValueError("bad signature"))
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    event_lookup = AsyncMock()
    monkeypatch.setattr(RazorpayWebhookEvent, "find_one", event_lookup)

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(b"{}", "invalid", "evt_test_bad")

    assert error.value.status_code == 400
    event_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_processed_webhook_event_is_idempotent(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature = MagicMock(return_value=True)
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    monkeypatch.setattr(RazorpayWebhookEvent, "find_one", AsyncMock(return_value=SimpleNamespace(status="processed")))
    attempt_lookup = AsyncMock()
    monkeypatch.setattr(PaymentAttempt, "find_one", attempt_lookup)

    result = await PaymentService.handle_webhook(b"{}", "signature", "evt_duplicate")

    assert result == {"status": "duplicate"}
    attempt_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_replayed_signed_body_with_changed_header_creates_one_ledger_entry(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    monkeypatch.setattr(RazorpayWebhookEvent, "get_pymongo_collection", MagicMock(return_value=MagicMock()))
    ledger = {}

    async def find_event(query):
        return ledger.get(query["body_digest"])

    async def insert_event(self):
        ledger[self.body_digest] = self

    async def save_event(self):
        return self

    monkeypatch.setattr(RazorpayWebhookEvent, "find_one", AsyncMock(side_effect=find_event))
    monkeypatch.setattr(RazorpayWebhookEvent, "insert", insert_event)
    monkeypatch.setattr(RazorpayWebhookEvent, "save", save_event)
    attempt_lookup = AsyncMock(return_value=payment_attempt())
    monkeypatch.setattr(PaymentAttempt, "find_one", attempt_lookup)
    monkeypatch.setattr(PaymentService, "_verify_provider_payment", AsyncMock(return_value=captured_payment()))
    apply_payment = AsyncMock(return_value="success")
    monkeypatch.setattr(PaymentService, "_apply_provider_payment", apply_payment)

    raw_body = captured_webhook_body()
    first = await PaymentService.handle_webhook(raw_body, "synthetic-signature", "evt_original")
    replay = await PaymentService.handle_webhook(raw_body, "synthetic-signature", "evt_changed")

    assert first == {"status": "success"}
    assert replay == {"status": "duplicate"}
    assert list(ledger) == [sha256(raw_body).hexdigest()]
    assert next(iter(ledger.values())).event_id == "evt_original"
    attempt_lookup.assert_awaited_once()
    apply_payment.assert_awaited_once()


@pytest.mark.asyncio
async def test_same_header_for_different_signed_body_is_rejected(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    monkeypatch.setattr(RazorpayWebhookEvent, "get_pymongo_collection", MagicMock(return_value=MagicMock()))
    existing = SimpleNamespace(event_id="evt_original", body_digest="different-digest", status="processed")

    async def find_event(query):
        return existing if query == {"event_id": "evt_original"} else None

    monkeypatch.setattr(RazorpayWebhookEvent, "find_one", AsyncMock(side_effect=find_event))
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "insert",
        AsyncMock(side_effect=DuplicateKeyError("synthetic unique event ID collision")),
    )
    attempt_lookup = AsyncMock()
    monkeypatch.setattr(PaymentAttempt, "find_one", attempt_lookup)

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(
            captured_webhook_body(), "synthetic-signature", "evt_original"
        )

    assert error.value.status_code == 409
    attempt_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_header_replay_losing_digest_insert_is_duplicate(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    monkeypatch.setattr(RazorpayWebhookEvent, "get_pymongo_collection", MagicMock(return_value=MagicMock()))
    processed = SimpleNamespace(status="processed")
    lookup = AsyncMock(side_effect=[None, processed])
    monkeypatch.setattr(RazorpayWebhookEvent, "find_one", lookup)
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "insert",
        AsyncMock(side_effect=DuplicateKeyError("synthetic body digest collision")),
    )
    attempt_lookup = AsyncMock()
    monkeypatch.setattr(PaymentAttempt, "find_one", attempt_lookup)

    raw_body = captured_webhook_body()
    result = await PaymentService.handle_webhook(raw_body, "synthetic-signature", "evt_changed")

    assert result == {"status": "duplicate"}
    expected = {"body_digest": sha256(raw_body).hexdigest()}
    assert lookup.await_args_list[0].args[0] == expected
    assert lookup.await_args_list[1].args[0] == expected
    attempt_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_signed_non_object_webhook_is_rejected_before_database_access(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    lookup = AsyncMock()
    monkeypatch.setattr(RazorpayWebhookEvent, "find_one", lookup)

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(b"[]", "synthetic-signature", "evt_malformed")

    assert error.value.status_code == 400
    lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_ledger_lookup_failure_returns_retryable_response(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "find_one",
        AsyncMock(side_effect=RuntimeError("database details")),
    )
    attempt_lookup = AsyncMock()
    monkeypatch.setattr(PaymentAttempt, "find_one", attempt_lookup)

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(
            captured_webhook_body(),
            "signature",
            "evt_ledger_unavailable",
        )

    assert error.value.status_code == 503
    assert "database details" not in error.value.detail
    attempt_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_ledger_insert_failure_returns_retryable_response(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "get_pymongo_collection",
        MagicMock(return_value=MagicMock()),
    )
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "find_one",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "insert",
        AsyncMock(side_effect=RuntimeError("database details")),
    )

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(
            captured_webhook_body(),
            "signature",
            "evt_insert_unavailable",
        )

    assert error.value.status_code == 503
    assert "database details" not in error.value.detail


@pytest.mark.asyncio
async def test_webhook_missing_local_order_is_retryable(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "get_pymongo_collection",
        MagicMock(return_value=MagicMock()),
    )
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "find_one",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(RazorpayWebhookEvent, "insert", AsyncMock())
    webhook_save = AsyncMock()
    monkeypatch.setattr(RazorpayWebhookEvent, "save", webhook_save)
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(
            captured_webhook_body(),
            "signature",
            "evt_order_not_visible_yet",
        )

    assert error.value.status_code == 503
    webhook_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_processed_marker_failure_requests_provider_retry(monkeypatch):
    configured_test_mode(monkeypatch)
    utility = MagicMock()
    utility.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=utility))
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "get_pymongo_collection",
        MagicMock(return_value=MagicMock()),
    )
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "find_one",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(RazorpayWebhookEvent, "insert", AsyncMock())
    monkeypatch.setattr(
        RazorpayWebhookEvent,
        "save",
        AsyncMock(side_effect=RuntimeError("database details")),
    )
    monkeypatch.setattr(
        PaymentAttempt,
        "find_one",
        AsyncMock(return_value=payment_attempt()),
    )
    monkeypatch.setattr(
        PaymentService,
        "_verify_provider_payment",
        AsyncMock(return_value=captured_payment()),
    )
    apply_payment = AsyncMock(return_value="success")
    monkeypatch.setattr(PaymentService, "_apply_provider_payment", apply_payment)

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(
            captured_webhook_body(),
            "signature",
            "evt_marker_unavailable",
        )

    assert error.value.status_code == 503
    assert "database details" not in error.value.detail
    apply_payment.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_reuses_the_existing_order_instead_of_creating_another(monkeypatch):
    configured_test_mode(monkeypatch)
    appointment = SimpleNamespace(
        id=PydanticObjectId("222222222222222222222222"),
        patient_id=PydanticObjectId("333333333333333333333333"),
        status="scheduled",
        service_mode="clinic",
        billing_status="pending",
        billing_amount=120,
        billing_currency="INR",
    )
    attempt = payment_attempt(status="failed")
    monkeypatch.setattr(PaymentService, "_get_owned_appointment", AsyncMock(return_value=appointment))
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=attempt))
    appointment_collection = MagicMock()
    appointment_collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(Appointment, "get_pymongo_collection", MagicMock(return_value=appointment_collection))
    collection = MagicMock()
    collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", MagicMock(return_value=collection))
    provider_client = MagicMock()
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=provider_client))

    first = await PaymentService.create_order(str(appointment.id), "patient-user")
    second = await PaymentService.create_order(str(appointment.id), "patient-user")

    assert first["order_id"] == second["order_id"] == "order_test_1"
    assert attempt.status == "pending"
    provider_client.order.create.assert_not_called()
    assert appointment_collection.update_one.await_count == 2
    assert appointment_collection.update_one.await_args.args[0]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_retry_reuses_failed_attempt_when_provider_order_was_never_created(monkeypatch):
    configured_test_mode(monkeypatch)
    appointment = SimpleNamespace(
        id=PydanticObjectId("222222222222222222222222"),
        patient_id=PydanticObjectId("333333333333333333333333"),
        status="scheduled",
        service_mode="clinic",
        billing_status="pending",
        billing_amount=120,
        billing_currency="INR",
    )
    attempt = payment_attempt(status="failed", order_id=None)
    attempt.provider_order_id = None
    attempt.save = AsyncMock()
    monkeypatch.setattr(PaymentService, "_get_owned_appointment", AsyncMock(return_value=appointment))
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=attempt))
    appointment_collection = MagicMock()
    appointment_collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(Appointment, "get_pymongo_collection", MagicMock(return_value=appointment_collection))
    provider_client = MagicMock()
    provider_client.order.create.return_value = {"id": "order_retry", "amount": 12000, "currency": "INR"}
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=provider_client))

    result = await PaymentService.create_order(str(appointment.id), "patient-user")

    assert result["order_id"] == "order_retry"
    assert attempt.status == "pending"
    attempt.save.assert_awaited()
    provider_client.order.create.assert_called_once()


@pytest.mark.asyncio
async def test_new_order_uses_server_amount_in_paise_and_the_configured_currency(monkeypatch):
    configured_test_mode(monkeypatch)
    monkeypatch.setattr(PaymentAttempt, "get_pymongo_collection", MagicMock(return_value=MagicMock()))
    appointment = SimpleNamespace(
        id=PydanticObjectId("222222222222222222222222"),
        patient_id=PydanticObjectId("333333333333333333333333"),
        status="scheduled",
        service_mode="clinic",
        billing_status="pending",
        billing_amount=120.5,
        billing_currency=None,
    )
    monkeypatch.setattr(PaymentService, "_get_owned_appointment", AsyncMock(return_value=appointment))
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(PaymentAttempt, "insert", AsyncMock())
    monkeypatch.setattr(PaymentAttempt, "save", AsyncMock())
    appointment_collection = MagicMock()
    appointment_collection.update_one = AsyncMock(return_value=SimpleNamespace(matched_count=1))
    monkeypatch.setattr(Appointment, "get_pymongo_collection", MagicMock(return_value=appointment_collection))
    provider_client = MagicMock()
    provider_client.order.create.return_value = {"id": "order_test_new", "amount": 12050, "currency": "INR"}
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=provider_client))

    result = await PaymentService.create_order(str(appointment.id), "patient-user")

    assert result["amount"] == 12050
    assert result["currency"] == "INR"
    assert provider_client.order.create.call_args.args[0]["amount"] == 12050
    assert provider_client.order.create.call_args.args[0]["currency"] == "INR"
    assert appointment_collection.update_one.await_args.args[0]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_order_creation_rejects_cancelled_appointment_before_provider_call(monkeypatch):
    appointment, _, _, _, provider_client = install_order_creation_fakes(
        monkeypatch, appointment_status="cancelled"
    )

    with pytest.raises(HTTPException) as error:
        await PaymentService.create_order(str(appointment.id), "patient-user")

    assert error.value.status_code == 409
    provider_client.order.create.assert_not_called()
    PaymentAttempt.insert.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_during_provider_call_records_order_but_never_returns_it(monkeypatch):
    appointment, appointment_doc, _, saved_attempts, provider_client = install_order_creation_fakes(
        monkeypatch
    )
    provider_entered = threading.Event()
    allow_provider_return = threading.Event()

    def create_provider_order(_payload):
        provider_entered.set()
        assert allow_provider_return.wait(timeout=5)
        return {
            "id": "order_created_during_cancel",
            "amount": 12000,
            "currency": "INR",
        }

    provider_client.order.create.side_effect = create_provider_order
    create_task = asyncio.create_task(
        PaymentService.create_order(str(appointment.id), "patient-user")
    )
    try:
        assert await asyncio.to_thread(provider_entered.wait, 2)
        assert await AppointmentRepository.cancel_scheduled(
            str(appointment.id), datetime.now()
        )
    finally:
        allow_provider_return.set()

    with pytest.raises(HTTPException) as error:
        await create_task

    assert error.value.status_code == 409
    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["payment_order_id"] is None
    assert saved_attempts[0].provider_order_id == "order_created_during_cancel"
    assert "provider order was recorded" in error.value.detail


@pytest.mark.asyncio
async def test_cancellation_after_provider_order_creation_prevents_order_attachment(monkeypatch):
    appointment, appointment_doc, _, saved_attempts, provider_client = install_order_creation_fakes(
        monkeypatch
    )

    async def cancel_after_provider_order_is_created(attempt):
        saved_attempts.append(attempt)
        assert await AppointmentRepository.cancel_scheduled(
            str(appointment.id), datetime.now()
        )

    monkeypatch.setattr(PaymentAttempt, "save", cancel_after_provider_order_is_created)

    with pytest.raises(HTTPException) as error:
        await PaymentService.create_order(str(appointment.id), "patient-user")

    assert error.value.status_code == 409
    assert provider_client.order.create.call_count == 1
    assert saved_attempts[0].provider_order_id == "order_test_new"
    assert appointment_doc["status"] == "cancelled"
    assert appointment_doc["payment_order_id"] is None


@pytest.mark.asyncio
async def test_failed_appointment_attachment_keeps_created_provider_order_recorded(monkeypatch):
    appointment, _, appointment_collection, saved_attempts, provider_client = install_order_creation_fakes(
        monkeypatch
    )
    appointment_collection.update_one = AsyncMock(
        side_effect=RuntimeError("simulated appointment update failure")
    )

    with pytest.raises(RuntimeError, match="simulated appointment update failure"):
        await PaymentService.create_order(str(appointment.id), "patient-user")

    assert provider_client.order.create.call_count == 1
    assert saved_attempts[0].provider_order_id == "order_test_new"
    assert saved_attempts[0].status == "pending"


@pytest.mark.asyncio
async def test_order_creation_attaches_and_returns_order_when_appointment_stays_scheduled(monkeypatch):
    appointment, appointment_doc, _, saved_attempts, provider_client = install_order_creation_fakes(
        monkeypatch
    )

    result = await PaymentService.create_order(str(appointment.id), "patient-user")

    assert result["order_id"] == "order_test_new"
    assert appointment_doc["status"] == "scheduled"
    assert appointment_doc["payment_order_id"] == "order_test_new"
    assert appointment_doc["payment_status"] == "pending"
    assert saved_attempts[0].provider_order_id == "order_test_new"
    provider_client.order.create.assert_called_once()


@pytest.mark.asyncio
async def test_concurrent_duplicate_order_requests_reuse_single_provider_order(monkeypatch):
    _, _, _, _, provider_client = install_order_creation_fakes(monkeypatch)
    initial_lookups = 0
    initial_lookups_ready = asyncio.Event()
    attempt_saved = asyncio.Event()
    created_attempts = []
    insert_count = 0

    async def find_attempt(_query):
        nonlocal initial_lookups
        initial_lookups += 1
        if initial_lookups <= 2:
            if initial_lookups == 2:
                initial_lookups_ready.set()
            await initial_lookups_ready.wait()
            return None
        await attempt_saved.wait()
        return created_attempts[0]

    async def insert_attempt(attempt):
        nonlocal insert_count
        insert_count += 1
        if insert_count == 1:
            created_attempts.append(attempt)
            return
        raise DuplicateKeyError("unique_payment_per_appointment")

    async def save_attempt(attempt):
        attempt_saved.set()

    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(side_effect=find_attempt))
    monkeypatch.setattr(PaymentAttempt, "insert", insert_attempt)
    monkeypatch.setattr(PaymentAttempt, "save", save_attempt)

    first, second = await asyncio.gather(
        PaymentService.create_order("222222222222222222222222", "patient-user"),
        PaymentService.create_order("222222222222222222222222", "patient-user"),
    )

    assert first["order_id"] == second["order_id"] == "order_test_new"
    provider_client.order.create.assert_called_once()


@pytest.mark.asyncio
async def test_missing_test_mode_or_currency_configuration_fails_closed(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAZORPAY_MODE", "disabled")
    monkeypatch.setattr(settings, "APPOINTMENT_BILLING_CURRENCY", "")
    with pytest.raises(HTTPException) as error:
        PaymentService._require_test_configuration()
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_admin_cannot_mark_appointment_paid_without_verified_attempt(monkeypatch):
    appointment = SimpleNamespace(
        id=PydanticObjectId("222222222222222222222222"),
        billing_status="pending",
        billing_amount=120,
        payment_order_id=None,
        save=AsyncMock(),
    )
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as error:
        await AppointmentService.update_appointment(
            str(appointment.id), AppointmentUpdate(billing_status="paid"), "admin-user", "admin"
        )

    assert error.value.status_code == 403
    appointment.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_status_cancellation_uses_atomic_repository_transition(monkeypatch):
    appointment = SimpleNamespace(
        id=PydanticObjectId("222222222222222222222222"),
        status="scheduled",
        billing_status="pending",
        billing_amount=120,
    )
    cancelled = SimpleNamespace(
        id=appointment.id,
        status="cancelled",
        billing_status="pending",
        billing_amount=120,
    )
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(side_effect=[appointment, cancelled]))
    cancel_transition = AsyncMock(return_value=True)
    monkeypatch.setattr(AppointmentRepository, "cancel_from_status", cancel_transition)
    reconcile = AsyncMock()
    monkeypatch.setattr(AppointmentService, "_mark_cancelled_capture_for_reconciliation", reconcile)
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="formatted"))

    result = await AppointmentService.update_appointment(
        str(appointment.id), AppointmentUpdate(status="cancelled"), "admin-user", "admin"
    )

    assert result == "formatted"
    assert cancel_transition.await_args.args[0:2] == (str(appointment.id), "scheduled")
    reconcile.assert_awaited_once_with(cancelled)


@pytest.mark.asyncio
async def test_verified_attempt_allows_paid_status_to_be_reflected(monkeypatch):
    appointment = SimpleNamespace(
        id=PydanticObjectId("222222222222222222222222"),
        billing_status="pending",
        billing_amount=120,
        payment_order_id="order_test_1",
        save=AsyncMock(),
    )
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(PaymentAttempt, "find_one", AsyncMock(return_value=payment_attempt(status="success")))
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(side_effect=[appointment, appointment]))
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="formatted"))

    result = await AppointmentService.update_appointment(
        str(appointment.id), AppointmentUpdate(billing_status="paid"), "admin-user", "admin"
    )

    assert result == "formatted"
    assert appointment.billing_status == "paid"
    appointment.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_payment_routes_require_patient_role_and_authentication(monkeypatch):
    app = FastAPI()
    app.include_router(payments_router, prefix="/api")
    monkeypatch.setattr(User, "get_pymongo_collection", MagicMock(return_value=MagicMock()))
    user = User(email="patient@example.com", hashed_password="unused", role="patient", full_name="Fictional Patient")
    user.id = PydanticObjectId("333333333333333333333333")
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(PaymentService, "create_order", AsyncMock(return_value={
        "appointment_id": "appointment-1", "order_id": "order_test_1", "amount": 12000,
        "currency": "INR", "key_id": "rzp_test_unit", "status": "pending",
    }))
    monkeypatch.setattr(PaymentService, "readiness", MagicMock(return_value={"available": False, "mode": "test", "currency": None}))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        allowed = await client.post("/api/appointments/appointment-1/payments/order")
        assert allowed.status_code == 200
        readiness = await client.get("/api/payments/readiness")
        assert readiness.status_code == 200
        assert readiness.json() == {"available": False, "mode": "test", "currency": None}

        app.dependency_overrides[get_current_user] = lambda: User(
            email="doctor@example.com", hashed_password="unused", role="doctor", full_name="Fictional Doctor"
        )
        denied = await client.post("/api/appointments/appointment-1/payments/order")
        assert denied.status_code == 403

        app.dependency_overrides.clear()
        unauthenticated = await client.post("/api/appointments/appointment-1/payments/order")
        assert unauthenticated.status_code == 401


@pytest.mark.asyncio
async def test_main_app_payment_readiness_url_and_safe_missing_configuration(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAZORPAY_MODE", "disabled")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
    monkeypatch.setattr(settings, "APPOINTMENT_BILLING_CURRENCY", "")
    monkeypatch.setattr(User, "get_pymongo_collection", MagicMock(return_value=MagicMock()))

    patient = User(
        email="readiness-patient@example.com",
        hashed_password="unused",
        role="patient",
        full_name="Fictional Patient",
    )
    main_app.dependency_overrides[get_current_user] = lambda: patient
    try:
        assert "/api/payments/readiness" in main_app.openapi()["paths"]
        transport = httpx.ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/payments/readiness")
    finally:
        main_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == {"available": False, "mode": "test", "currency": None}
    assert not {"key_id", "key_secret", "webhook_secret", "secret"}.intersection(response.json())
