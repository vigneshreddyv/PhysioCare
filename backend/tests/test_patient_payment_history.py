from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from beanie import PydanticObjectId

from app.core.pagination import PageWindow
from app.repositories.payment_query_repository import PaymentQueryRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.payment_service import PaymentService


@pytest.mark.asyncio
async def test_patient_payment_history_is_owned_and_includes_appointment_context(monkeypatch):
    patient_id = PydanticObjectId("111111111111111111111111")
    appointment_id = PydanticObjectId("222222222222222222222222")
    attempt_id = PydanticObjectId("333333333333333333333333")
    row = {
        "_id": attempt_id,
        "appointment_id": appointment_id,
        "amount_paise": 12000,
        "currency": "INR",
        "status": "success",
        "reconciliation_status": "reconciled",
        "appointment": {
            "billing_status": "paid",
            "payment_status": "success",
            "appointment_date": datetime(2026, 11, 2),
            "time_slot": "09:00 AM",
            "service_mode": "clinic",
        },
    }

    monkeypatch.setattr(
        ProfileRepository,
        "get_patient_by_user_id",
        AsyncMock(return_value=SimpleNamespace(id=patient_id)),
    )
    query = AsyncMock(return_value=[row])
    monkeypatch.setattr(PaymentQueryRepository, "list_patient_history", query)

    history = await PaymentService.get_patient_payment_history(
        "444444444444444444444444", PageWindow(2, 25), payment_status="success",
    )

    assert history == [{
        "id": str(attempt_id),
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
    query.assert_awaited_once_with(
        str(patient_id), PageWindow(2, 25),
        payment_status="success", start_date=None, end_date=None,
    )
