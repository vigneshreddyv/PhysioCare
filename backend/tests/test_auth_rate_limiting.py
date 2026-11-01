import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError

from app.api import auth as auth_api
from app.core.config import settings
from app.schemas.auth import UserLogin, UserRegister
from app.services.auth_rate_limit_service import (
    AuthRateLimiter,
    InMemoryRateLimitStore,
    MongoRateLimitStore,
    client_ip,
)
from app.models.auth_rate_limit import AuthRateLimitBucket
from app.services.auth_service import AuthService
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository


def request_for(peer: str, forwarded: str | None = None) -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": headers,
            "client": (peer, 12345),
        }
    )


@pytest.fixture
def limiter(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_LOGIN_IP_LIMIT", 20)
    monkeypatch.setattr(settings, "AUTH_LOGIN_FAILURE_LIMIT", 2)
    monkeypatch.setattr(settings, "AUTH_LOGIN_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "AUTH_REGISTRATION_LIMIT", 2)
    monkeypatch.setattr(settings, "AUTH_REGISTRATION_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "AUTH_REFRESH_IP_LIMIT", 10)
    monkeypatch.setattr(settings, "AUTH_REFRESH_LIMIT", 2)
    monkeypatch.setattr(settings, "AUTH_REFRESH_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_NETWORKS", [])
    return AuthRateLimiter(InMemoryRateLimitStore())


@pytest.mark.asyncio
async def test_repeated_login_failures_are_limited_without_storing_raw_identity(limiter):
    now = datetime(2026, 10, 31, 12, 0, 1)
    request = request_for("198.51.100.14")
    await limiter.before_login(request, "patient@example.com", now=now)
    await limiter.before_login(request, "patient@example.com", now=now)
    with pytest.raises(HTTPException) as error:
        await limiter.before_login(request, "patient@example.com", now=now)

    assert error.value.status_code == 429
    assert error.value.detail == "Too many requests. Try again later."
    assert int(error.value.headers["Retry-After"]) > 0
    keys = limiter.store.bucket_keys
    assert keys
    assert all("patient" not in key and "example" not in key for key in keys)


@pytest.mark.asyncio
async def test_successful_login_clears_current_account_failure_bucket(limiter):
    now = datetime(2026, 10, 31, 12, 0, 1)
    request = request_for("198.51.100.15")
    await limiter.before_login(request, "patient@example.com", now=now)
    await limiter.login_succeeded("patient@example.com", now=now)
    await limiter.before_login(request, "patient@example.com", now=now)
    await limiter.before_login(request, "patient@example.com", now=now)


@pytest.mark.asyncio
async def test_account_failure_limit_is_checked_before_more_password_work(limiter):
    now = datetime(2026, 10, 31, 12, 0, 1)
    request = request_for("198.51.100.15")
    await limiter.before_login(request, "patient@example.com", now=now)
    await limiter.before_login(request, "patient@example.com", now=now)

    with pytest.raises(HTTPException) as error:
        await limiter.before_login(request, "patient@example.com", now=now)

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "59"


@pytest.mark.asyncio
async def test_fixed_window_expires_and_allows_new_attempts(limiter):
    first = datetime(2026, 10, 31, 12, 0, 1)
    await limiter.registration(request_for("198.51.100.10"), now=first)
    await limiter.registration(request_for("198.51.100.10"), now=first)
    with pytest.raises(HTTPException):
        await limiter.registration(request_for("198.51.100.10"), now=first)

    await limiter.registration(
        request_for("198.51.100.10"),
        now=first + timedelta(seconds=60),
    )


@pytest.mark.asyncio
async def test_registration_and_refresh_have_independent_limits(limiter):
    now = datetime(2026, 10, 31, 12, 0, 1)
    request = request_for("198.51.100.11")
    await limiter.registration(request, now=now)
    await limiter.registration(request, now=now)
    with pytest.raises(HTTPException) as registration_error:
        await limiter.registration(request, now=now)
    assert registration_error.value.status_code == 429

    await limiter.refresh(request, "opaque-refresh-token", now=now)
    await limiter.refresh(request, "opaque-refresh-token", now=now)
    with pytest.raises(HTTPException) as refresh_error:
        await limiter.refresh(request, "opaque-refresh-token", now=now)
    assert refresh_error.value.status_code == 429
    assert all("opaque-refresh-token" not in key for key in limiter.store.bucket_keys)


def test_forwarded_address_is_used_only_from_configured_trusted_proxy(monkeypatch):
    forwarded = "203.0.113.20, 192.0.2.4"
    request = request_for("10.0.0.5", forwarded)

    monkeypatch.setattr(settings, "TRUSTED_PROXY_NETWORKS", [])
    assert client_ip(request) == "10.0.0.5"

    monkeypatch.setattr(settings, "TRUSTED_PROXY_NETWORKS", ["10.0.0.0/8", "192.0.2.0/24"])
    assert client_ip(request) == "203.0.113.20"

    malformed = request_for("10.0.0.5", "not-an-ip")
    assert client_ip(malformed) == "10.0.0.5"


@pytest.mark.asyncio
async def test_concurrent_consumers_share_one_atomic_limit():
    store = InMemoryRateLimitStore()
    now = datetime(2026, 10, 31, 12, 0, 1)
    decisions = await asyncio.gather(
        *(
            store.consume("opaque", limit=3, window_seconds=60, now=now)
            for _ in range(12)
        )
    )
    assert sum(decision.allowed for decision in decisions) == 3


@pytest.mark.asyncio
async def test_concurrent_login_prechecks_reserve_only_the_allowed_account_attempts(limiter):
    now = datetime(2026, 10, 31, 12, 0, 1)

    async def attempt(index):
        try:
            await limiter.before_login(
                request_for(f"198.51.100.{index + 20}"),
                "patient@example.com",
                now=now,
            )
            return "allowed"
        except HTTPException as exc:
            assert exc.status_code == 429
            return "limited"

    results = await asyncio.gather(*(attempt(index) for index in range(12)))
    assert results.count("allowed") == 2
    assert results.count("limited") == 10


@pytest.mark.asyncio
async def test_mongo_counter_retries_first_window_unique_key_race(monkeypatch):
    collection = SimpleNamespace(
        find_one_and_update=AsyncMock(
            side_effect=[
                DuplicateKeyError("concurrent upsert"),
                {"attempt_count": 2},
            ]
        )
    )
    monkeypatch.setattr(
        AuthRateLimitBucket,
        "get_pymongo_collection",
        lambda: collection,
    )

    result = await MongoRateLimitStore().consume(
        "opaque",
        limit=2,
        window_seconds=60,
        now=datetime(2026, 10, 31, 12, 0, 1),
    )

    assert result.allowed is True
    assert collection.find_one_and_update.await_count == 2


@pytest.mark.asyncio
async def test_public_registration_response_does_not_enumerate_existing_email(monkeypatch):
    monkeypatch.setattr(auth_api.auth_rate_limiter, "registration", AsyncMock())
    request = request_for("198.51.100.12")
    schema = UserRegister(
        email="existing@example.com",
        password="fictional-password",
        full_name="Fictional Patient",
    )

    monkeypatch.setattr(AuthService, "register", AsyncMock(return_value=None))
    duplicate = await auth_api.register(schema, request)
    monkeypatch.setattr(AuthService, "register", AsyncMock(return_value=object()))
    created = await auth_api.register(schema, request)

    assert duplicate == created
    assert "email" not in duplicate


@pytest.mark.asyncio
async def test_public_duplicate_registration_hashes_password_and_returns_no_signal(monkeypatch):
    hashed = []
    monkeypatch.setattr(
        "app.services.auth_service.get_password_hash",
        lambda value: hashed.append(value) or "safe-hash",
    )
    monkeypatch.setattr(UserRepository, "get_by_email", AsyncMock(return_value=object()))
    create = AsyncMock()
    monkeypatch.setattr(UserRepository, "create", create)
    schema = UserRegister(
        email="existing@example.com",
        password="fictional-password",
        full_name="Fictional Patient",
    )

    result = await AuthService.register(schema)

    assert result is None
    assert hashed == ["fictional-password"]
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_registration_race_returns_same_nondisclosing_result(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.get_password_hash", lambda _value: "safe-hash")
    monkeypatch.setattr(UserRepository, "get_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(UserRepository, "create", AsyncMock(side_effect=DuplicateKeyError("duplicate")))
    monkeypatch.setattr(
        "app.services.auth_service.User",
        lambda **values: SimpleNamespace(**values),
    )
    create_patient = AsyncMock()
    monkeypatch.setattr(ProfileRepository, "create_patient", create_patient)

    result = await AuthService.register(
        UserRegister(
                email="race@example.com",
            password="fictional-password",
            full_name="Fictional Patient",
        )
    )

    assert result is None
    create_patient.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_route_records_failures_and_preserves_success(monkeypatch):
    before = AsyncMock()
    succeeded = AsyncMock()
    monkeypatch.setattr(auth_api.auth_rate_limiter, "before_login", before)
    monkeypatch.setattr(auth_api.auth_rate_limiter, "login_succeeded", succeeded)
    schema = UserLogin(email="patient@example.com", password="fictional-password")
    request = request_for("198.51.100.13")

    monkeypatch.setattr(
        AuthService,
        "login",
        AsyncMock(side_effect=HTTPException(status_code=401, detail="Incorrect email or password")),
    )
    with pytest.raises(HTTPException):
        await auth_api.login(schema, Response(), request)
    before.assert_awaited_once()
    succeeded.assert_not_awaited()

    bundle = SimpleNamespace(
        user=SimpleNamespace(role="patient", full_name="Fictional", email=str(schema.email)),
        access_token="access",
        refresh_token="refresh",
        csrf_token="csrf",
    )
    monkeypatch.setattr(AuthService, "login", AsyncMock(return_value=bundle))
    response = Response()
    result = await auth_api.login(schema, response, request)
    assert result.role == "patient"
    succeeded.assert_awaited_once()
    assert any(cookie.startswith("physiocare_access=") for cookie in response.headers.getlist("set-cookie"))
