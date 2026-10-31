from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from beanie import PydanticObjectId

from app.models.appointment import Appointment
from app.models.payment_attempt import PaymentAttempt
from app.repositories.profile_repository import ProfileRepository
from app.services.payment_service import PaymentService


class FakePaymentQuery:
    def __init__(self, attempts):
        self.attempts = attempts

    def sort(self, *_args):
        return self

    async def to_list(self):
        return self.attempts


@pytest.mark.asyncio
async def test_patient_payment_history_is_owned_and_includes_appointment_context(monkeypatch):
    patient_id = PydanticObjectId("111111111111111111111111")
    appointment_id = PydanticObjectId("222222222222222222222222")
    attempt = SimpleNamespace(
        id=PydanticObjectId("333333333333333333333333"),
        appointment_id=appointment_id,
        patient_id=patient_id,
        amount_paise=12000,
        currency="INR",
        status="success",
        reconciliation_status="reconciled",
        created_at=datetime(2026, 1, 1),
    )
    appointment = SimpleNamespace(
        billing_status="paid",
        payment_status="success",
        appointment_date=datetime(2026, 11, 2),
        time_slot="09:00 AM",
        service_mode="clinic",
    )

    monkeypatch.setattr(
        ProfileRepository,
        "get_patient_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=patient_id)),
    )
    monkeypatch.setattr(PaymentAttempt, "find", lambda _query: FakePaymentQuery([attempt]))
    monkeypatch.setattr(Appointment, "get", AsyncMock(return_value=appointment))

    history = await PaymentService.get_patient_payment_history("444444444444444444444444")

    assert history == [{
        "id": str(attempt.id),
        "appointment_id": str(appointment_id),
        "amount": 120.0,
        "currency": "INR",
        "status": "success",
        "reconciliation_status": "reconciled",
        "billing_status": "paid",
        "payment_status": "success",
        "appointment_date": datetime(2026, 11, 2),
        "time_slot": "09:00 AM",
        "service_mode": "clinic",
    }]
