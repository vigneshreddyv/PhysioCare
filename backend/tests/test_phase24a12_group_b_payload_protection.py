from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.payments import razorpay_webhook
from app.core.request_limits import (
    MAX_JSON_REQUEST_BYTES,
    MAX_RAZORPAY_WEBHOOK_BYTES,
    read_bounded_body,
)
from app.main import app as main_app, limit_json_request_bodies
from app.middleware.auth import get_current_user
from app.schemas.appointment import AppointmentCreate
from app.schemas.auth import UserLogin, UserRegister
from app.schemas.care_plan import CarePlanCreate, CarePlanResponse
from app.schemas.exercise import ExerciseCreate, ExerciseProgressCreate
from app.schemas.laboratory_booking import LaboratoryBookingCreate
from app.schemas.report import ReportCreate, ReportResponse
from app.services.payment_service import PaymentService
from app.services.appointment_service import AppointmentService


def streamed_request(
    chunks: list[bytes],
    *,
    path: str = "/api/webhooks/razorpay",
    content_length: str | None = None,
    content_type: str = "application/json",
):
    headers = [(b"content-type", content_type.encode())]
    if content_length is not None:
        headers.append((b"content-length", content_length.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunks) - 1,
        }
        for index, chunk in enumerate(chunks)
    ] or [{"type": "http.request", "body": b"", "more_body": False}]
    calls = {"receive": 0}

    async def receive():
        calls["receive"] += 1
        return messages.pop(0)

    return Request(scope, receive), calls


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [1, MAX_RAZORPAY_WEBHOOK_BYTES])
async def test_webhook_accepts_bodies_at_or_below_the_limit(monkeypatch, size):
    request, _ = streamed_request([b"x" * size], content_length=str(size))
    service = AsyncMock(return_value={"status": "accepted"})
    monkeypatch.setattr(PaymentService, "handle_webhook", service)

    result = await razorpay_webhook(
        request, signature="synthetic-signature", event_id="evt_synthetic",
    )

    assert result == {"status": "accepted"}
    service.assert_awaited_once_with(
        b"x" * size, "synthetic-signature", "evt_synthetic",
    )


@pytest.mark.asyncio
async def test_webhook_stream_stops_before_retaining_one_byte_over_limit(monkeypatch):
    marker = b"private-body-marker"
    request, calls = streamed_request([b"x" * MAX_RAZORPAY_WEBHOOK_BYTES, marker])
    service = AsyncMock()
    monkeypatch.setattr(PaymentService, "handle_webhook", service)

    with pytest.raises(HTTPException) as error:
        await razorpay_webhook(
            request, signature="synthetic-signature", event_id="evt_synthetic",
        )

    assert error.value.status_code == 413
    assert calls["receive"] == 2
    service.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_and_falsely_small_content_length_still_use_stream_limit(monkeypatch):
    service = AsyncMock(return_value={"status": "accepted"})
    monkeypatch.setattr(PaymentService, "handle_webhook", service)
    missing, _ = streamed_request([b"{}"])
    assert await razorpay_webhook(
        missing, signature="synthetic-signature", event_id="evt_missing_length",
    ) == {"status": "accepted"}

    misleading, _ = streamed_request(
        [b"x" * MAX_RAZORPAY_WEBHOOK_BYTES, b"y"], content_length="2",
    )
    with pytest.raises(HTTPException) as error:
        await razorpay_webhook(
            misleading, signature="synthetic-signature", event_id="evt_small_length",
        )
    assert error.value.status_code == 413
    assert service.await_count == 1


@pytest.mark.asyncio
async def test_large_content_length_and_missing_headers_reject_before_read(monkeypatch):
    service = AsyncMock()
    monkeypatch.setattr(PaymentService, "handle_webhook", service)
    large, calls = streamed_request(
        [b"not-read"], content_length=str(MAX_RAZORPAY_WEBHOOK_BYTES + 1),
    )
    with pytest.raises(HTTPException) as error:
        await razorpay_webhook(
            large, signature="synthetic-signature", event_id="evt_large_length",
        )
    assert error.value.status_code == 413
    assert calls["receive"] == 0

    unsigned, unsigned_calls = streamed_request([b"not-read"])
    with pytest.raises(HTTPException) as error:
        await razorpay_webhook(unsigned, signature=None, event_id=None)
    assert error.value.status_code == 400
    assert unsigned_calls["receive"] == 0
    service.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("signature", "event_id"),
    [("s" * 257, "evt_valid"), ("signature", "e" * 129)],
)
async def test_oversized_webhook_headers_reject_before_body_read(
    monkeypatch, signature, event_id,
):
    request, calls = streamed_request([b"not-read"])
    service = AsyncMock()
    monkeypatch.setattr(PaymentService, "handle_webhook", service)

    with pytest.raises(HTTPException) as error:
        await razorpay_webhook(request, signature=signature, event_id=event_id)

    assert error.value.status_code == 400
    assert calls["receive"] == 0
    service.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("content_length", ["-1", "not-a-number", "1, 2"])
async def test_invalid_content_length_is_rejected_without_processing(
    monkeypatch, content_length,
):
    request, calls = streamed_request([b"{}"], content_length=content_length)
    service = AsyncMock()
    monkeypatch.setattr(PaymentService, "handle_webhook", service)

    with pytest.raises(HTTPException) as error:
        await razorpay_webhook(
            request, signature="synthetic-signature", event_id="evt_invalid_length",
        )
    assert error.value.status_code == 400
    assert calls["receive"] == 0
    service.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_webhook_body_reaches_existing_signature_validation(monkeypatch):
    request, _ = streamed_request([])
    service = AsyncMock(return_value={"status": "existing-validator"})
    monkeypatch.setattr(PaymentService, "handle_webhook", service)

    assert await razorpay_webhook(
        request, signature="synthetic-signature", event_id="evt_empty",
    ) == {"status": "existing-validator"}
    service.assert_awaited_once_with(b"", "synthetic-signature", "evt_empty")


@pytest.mark.asyncio
async def test_bounded_reader_is_single_use_and_does_not_duplicate_buffering():
    request, calls = streamed_request([b"first", b"second"])
    assert await read_bounded_body(request, 100) == b"firstsecond"
    with pytest.raises(RuntimeError, match="Stream consumed"):
        await read_bounded_body(request, 100)
    assert calls["receive"] == 2


@pytest.mark.asyncio
async def test_json_limit_middleware_buffers_once_for_downstream_parser():
    payload = b'{"safe":"payload"}'
    request, calls = streamed_request(
        [payload], path="/api/test-json", content_length=str(len(payload)),
    )

    async def call_next(received):
        assert await received.body() == payload
        return JSONResponse({"ok": True})

    response = await limit_json_request_bodies(request, call_next)
    assert response.status_code == 200
    assert calls["receive"] == 1


@pytest.mark.asyncio
async def test_json_limit_middleware_rejects_before_endpoint_or_parser():
    request, calls = streamed_request(
        [b"not-read"], path="/api/test-json",
        content_length=str(MAX_JSON_REQUEST_BYTES + 1),
    )
    endpoint = AsyncMock()

    response = await limit_json_request_bodies(request, endpoint)

    assert response.status_code == 413
    assert calls["receive"] == 0
    endpoint.assert_not_awaited()
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_mutation_limit_cannot_be_bypassed_with_wrong_content_type():
    request, calls = streamed_request(
        [b"not-read"], path="/api/auth/login",
        content_length=str(MAX_JSON_REQUEST_BYTES + 1),
        content_type="application/octet-stream",
    )
    endpoint = AsyncMock()

    response = await limit_json_request_bodies(request, endpoint)

    assert response.status_code == 413
    assert calls["receive"] == 0
    endpoint.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_app_rejects_oversized_json_before_auth_handler():
    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            content=b"x" * (MAX_JSON_REQUEST_BYTES + 1),
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large"}
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_main_app_chunked_webhook_crossing_cap_never_reaches_service(monkeypatch):
    service = AsyncMock()
    monkeypatch.setattr(PaymentService, "handle_webhook", service)

    async def chunks():
        yield b"x" * MAX_RAZORPAY_WEBHOOK_BYTES
        yield b"y"

    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/razorpay",
            content=chunks(),
            headers={
                "content-type": "application/json",
                "x-razorpay-signature": "synthetic-signature",
                "x-razorpay-event-id": "evt_chunked_oversized",
            },
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large"}
    service.assert_not_awaited()


@pytest.mark.asyncio
async def test_schema_validation_rejects_before_persistent_service_write(monkeypatch):
    create = AsyncMock()
    monkeypatch.setattr(AppointmentService, "create_appointment", create)
    main_app.dependency_overrides[get_current_user] = lambda: type(
        "PatientDouble", (), {"id": "patient-user", "role": "patient"},
    )()
    try:
        transport = httpx.ASGITransport(app=main_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/appointments", json={
                "doctor_id": "doctor-profile-id",
                "appointment_date": "2026-11-03",
                "time_slot": "09:00 AM",
                "reason": "r" * 501,
            })
    finally:
        main_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 422
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_oversized_log_contains_metadata_but_not_body(caplog):
    secret_marker = b"never-log-this-private-payload"
    request, _ = streamed_request(
        [b"x" * MAX_RAZORPAY_WEBHOOK_BYTES, secret_marker],
    )
    with caplog.at_level("WARNING", logger="app.core.request_limits"):
        with pytest.raises(HTTPException):
            await read_bounded_body(request, MAX_RAZORPAY_WEBHOOK_BYTES)

    text = caplog.text
    assert "category=body_too_large" in text
    assert f"max_bytes={MAX_RAZORPAY_WEBHOOK_BYTES}" in text
    assert secret_marker.decode() not in text


def care_plan_payload(**updates):
    payload = {
        "patient_id": "patient-profile-id",
        "title": "Fictional recovery plan",
        "description": "Fictional clinical plan",
        "current_stage": 1,
        "stages": [],
        "goals": [],
        "recommendations": [],
        "start_date": datetime(2026, 11, 2, tzinfo=timezone.utc),
        "target_date": datetime(2026, 12, 2, tzinfo=timezone.utc),
    }
    payload.update(updates)
    return payload


def exercise_payload(**updates):
    payload = {
        "title": "Fictional exercise",
        "description": "Fictional instructions",
        "category": "mobility",
        "difficulty": "easy",
        "instructions": ["Move slowly"],
        "sets": 3,
        "reps": 10,
        "duration_seconds": 60,
    }
    payload.update(updates)
    return payload


def report_payload(**updates):
    payload = {
        "patient_id": "patient-profile-id",
        "title": "Fictional assessment",
        "category": "assessment",
        "date": datetime(2026, 11, 2, tzinfo=timezone.utc),
        "description": "Fictional report",
        "therapist": "Fictional Clinician",
        "content": {
            "symptoms": "Fictional symptom",
            "findings": "Fictional finding",
            "recommendations": "Fictional recommendation",
        },
    }
    payload.update(updates)
    return payload


def test_auth_and_appointment_strings_accept_exact_limit_and_reject_one_over():
    UserRegister(email="patient@example.com", password="x" * 1024, full_name="N" * 100)
    UserLogin(email="patient@example.com", password="x" * 1024)
    AppointmentCreate(
        doctor_id="doctor-profile-id", appointment_date="2026-11-03",
        time_slot="09:00 AM", reason="r" * 500,
    )
    with pytest.raises(ValidationError):
        UserRegister(email="patient@example.com", password="x" * 1025, full_name="Patient")
    with pytest.raises(ValidationError):
        AppointmentCreate(
            doctor_id="doctor-profile-id", appointment_date="2026-11-03",
            time_slot="09:00 AM", reason="r" * 501,
        )


def test_laboratory_booking_bounds_ids_count_and_address():
    LaboratoryBookingCreate(
        test_ids=[f"test-{index}" for index in range(12)],
        appointment_date="2026-11-03", time_slot="09:00 AM",
        visit_type="home", address="a" * 500,
    )
    with pytest.raises(ValidationError):
        LaboratoryBookingCreate(
            test_ids=[f"test-{index}" for index in range(13)],
            appointment_date="2026-11-03", time_slot="09:00 AM",
            visit_type="clinic",
        )
    with pytest.raises(ValidationError):
        LaboratoryBookingCreate(
            test_ids=["x" * 129], appointment_date="2026-11-03",
            time_slot="09:00 AM", visit_type="clinic",
        )


def test_care_plan_bounds_nested_lists_text_and_extra_objects():
    stage = {
        "stage_id": "stage-1", "title": "Stage", "description": "d" * 8000,
        "status": "upcoming", "focus_areas": ["area"] * 32,
    }
    CarePlanCreate(**care_plan_payload(stages=[stage] * 64))
    with pytest.raises(ValidationError):
        CarePlanCreate(**care_plan_payload(stages=[stage] * 65))
    with pytest.raises(ValidationError):
        CarePlanCreate(**care_plan_payload(description="d" * 8001))
    with pytest.raises(ValidationError):
        CarePlanCreate(**care_plan_payload(stages=[{**stage, "unexpected": {"nested": True}}]))


def test_exercise_lists_items_numbers_and_notes_are_bounded():
    ExerciseCreate(**exercise_payload(instructions=["i" * 2000] * 50))
    with pytest.raises(ValidationError):
        ExerciseCreate(**exercise_payload(instructions=["step"] * 51))
    with pytest.raises(ValidationError):
        ExerciseCreate(**exercise_payload(instructions=["i" * 2001]))
    ExerciseProgressCreate(
        assignment_id="assignment-id", expected_assignment_revision=0,
        completed_sets=1, completed_reps=10,
        duration_seconds=60, notes="n" * 8000,
    )
    with pytest.raises(ValidationError):
        ExerciseProgressCreate(
            assignment_id="assignment-id", expected_assignment_revision=0,
            completed_sets=1, completed_reps=10,
            duration_seconds=60, notes="n" * 8001,
        )


def test_report_metadata_and_nested_content_are_bounded():
    ReportCreate(**report_payload(content={
        "symptoms": "s" * 16000,
        "findings": "f" * 16000,
        "recommendations": "r" * 16000,
    }))
    with pytest.raises(ValidationError):
        ReportCreate(**report_payload(content={
            "symptoms": "s" * 16001,
            "findings": "f",
            "recommendations": "r",
        }))


def test_mutation_limits_do_not_reject_legacy_clinical_response_records():
    now = datetime(2026, 11, 2, tzinfo=timezone.utc)
    CarePlanResponse(
        id="plan-id", patient_id="patient-id", therapist_id="therapist-id",
        title="Legacy plan", description="d" * 8001, current_stage=1,
        stages=[{
            "stage_id": "stage-id", "title": "Legacy stage",
            "description": "s" * 8001, "status": "active",
            "focus_areas": ["legacy"],
        }],
        goals=[], recommendations=[], start_date=now, target_date=now,
        status="active", created_at=now, updated_at=now,
    )
    ReportResponse(
        id="report-id", patient_id="patient-id", title="Legacy report",
        category="assessment", date=now, description="d" * 8001,
        therapist="Clinician", content={
            "symptoms": "s" * 16001,
            "findings": "f" * 16001,
            "recommendations": "r" * 16001,
        }, created_at=now,
    )
    with pytest.raises(ValidationError):
        ReportCreate(**report_payload(content={
            "symptoms": "s", "findings": "f", "recommendations": "r",
            "unexpected": ["nested"],
        }))


@pytest.mark.asyncio
async def test_direct_service_guard_rejects_oversized_body_before_signature_or_database(
    monkeypatch,
):
    monkeypatch.setattr(PaymentService, "_require_test_configuration", lambda: None)
    client = AsyncMock()
    monkeypatch.setattr(PaymentService, "_client", client)

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(
            b"x" * (MAX_RAZORPAY_WEBHOOK_BYTES + 1),
            "synthetic-signature",
            "evt_oversized",
        )

    assert error.value.status_code == 413
    client.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_body", [b'{"event":', b"\xff\xfe"])
async def test_signed_malformed_or_invalidly_encoded_body_rejects_before_database(
    monkeypatch, raw_body,
):
    monkeypatch.setattr(PaymentService, "_require_test_configuration", lambda: None)
    provider = MagicMock()
    provider.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=provider))
    event_lookup = AsyncMock()
    monkeypatch.setattr(
        "app.services.payment_service.RazorpayWebhookEvent.find_one", event_lookup,
    )

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(
            raw_body, "synthetic-signature", "evt_invalid_body",
        )

    assert error.value.status_code == 400
    event_lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_signed_oversized_provider_identifier_is_not_persisted(monkeypatch):
    monkeypatch.setattr(PaymentService, "_require_test_configuration", lambda: None)
    provider = MagicMock()
    provider.utility.verify_webhook_signature.return_value = True
    monkeypatch.setattr(PaymentService, "_client", MagicMock(return_value=provider))
    event_lookup = AsyncMock()
    monkeypatch.setattr(
        "app.services.payment_service.RazorpayWebhookEvent.find_one", event_lookup,
    )
    raw_body = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_test", "order_id": "o" * 129,
        }}},
    }).encode()

    with pytest.raises(HTTPException) as error:
        await PaymentService.handle_webhook(
            raw_body, "synthetic-signature", "evt_invalid_provider_id",
        )

    assert error.value.status_code == 400
    event_lookup.assert_not_awaited()

