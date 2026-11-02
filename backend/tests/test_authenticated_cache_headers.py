"""Actual HTTP cache policy for account and clinical JSON responses."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.main import app, protect_private_api_responses
from app.middleware.auth import get_current_user
from app.services.auth_service import AuthService
from app.services.auth_rate_limit_service import auth_rate_limiter
from app.services.user_service import UserService
from app.services.report_service import ReportService
from app.repositories.profile_repository import ProfileRepository


@pytest.fixture(autouse=True)
def clear_overrides():
    previous = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


async def request(method, path, **kwargs):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
    ) as client:
        client.cookies.update(kwargs.pop("cookies", {}))
        return await client.request(method, path, **kwargs)


def as_user(role="patient"):
    user = SimpleNamespace(
        id="fictional-user", role=role, email="fictional@example.com",
        full_name="Fictional User", is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return user


def assert_private(response):
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"


@pytest.mark.asyncio
async def test_me_success_and_unauthorized_are_not_cached():
    as_user("admin")
    allowed = await request("GET", "/api/auth/me")
    assert allowed.status_code == 200
    assert allowed.json()["role"] == "admin"
    assert_private(allowed)

    app.dependency_overrides.clear()
    denied = await request("GET", "/api/auth/me")
    assert denied.status_code == 401
    assert_private(denied)


@pytest.mark.asyncio
async def test_patient_and_doctor_me_profiles_are_private(monkeypatch):
    for role, lookup in (
        ("patient", "get_patient_profile"),
        ("doctor", "get_doctor_profile"),
    ):
        as_user(role)
        monkeypatch.setattr(UserService, lookup, AsyncMock(return_value={
            "id": "fictional-profile", "full_name": "Fictional Person",
        }))
        response = await request("GET", "/api/auth/me")
        assert response.status_code == 200
        assert response.json()["profile"]["id"] == "fictional-profile"
        assert_private(response)


@pytest.mark.asyncio
async def test_login_and_refresh_preserve_cookies_and_private_headers(monkeypatch):
    bundle = SimpleNamespace(
        access_token="synthetic-access", refresh_token="synthetic-refresh",
        csrf_token="synthetic-csrf",
        user=SimpleNamespace(role="patient", full_name="Fictional Patient", email="fictional@example.com"),
    )
    monkeypatch.setattr(auth_rate_limiter, "before_login", AsyncMock())
    monkeypatch.setattr(auth_rate_limiter, "login_succeeded", AsyncMock())
    monkeypatch.setattr(auth_rate_limiter, "refresh", AsyncMock())
    monkeypatch.setattr(AuthService, "login", AsyncMock(return_value=bundle))
    refresh = AsyncMock(return_value=bundle)
    monkeypatch.setattr(AuthService, "refresh_tokens", refresh)

    login = await request("POST", "/api/auth/login", json={
        "email": "fictional@example.com", "password": "fictional-password",
    })
    assert login.status_code == 200
    assert login.json()["csrf_token"] == "synthetic-csrf"
    assert len(login.headers.get_list("set-cookie")) == 3
    assert_private(login)

    refreshed = await request(
        "POST", "/api/auth/refresh",
        cookies={"physiocare_refresh": "synthetic-refresh"},
        headers={"X-CSRF-Token": "synthetic-csrf"},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["role"] == "patient"
    assert len(refreshed.headers.get_list("set-cookie")) == 3
    refresh.assert_awaited_once()
    assert_private(refreshed)


@pytest.mark.asyncio
async def test_patient_profile_and_clinical_json_are_private(monkeypatch):
    as_user("admin")
    monkeypatch.setattr(UserService, "get_admin_patient", AsyncMock(return_value={
        "id": "fictional-patient", "full_name": "Fictional Patient",
        "email": "patient@example.com", "subscription_status": "active",
    }))
    patient = await request("GET", "/api/users/patients/fictional-patient")
    assert patient.status_code == 200
    assert patient.json()["id"] == "fictional-patient"
    assert_private(patient)

    as_user("patient")
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id="fictional-patient"),
    ))
    monkeypatch.setattr(ReportService, "get_reports_by_patient_id", AsyncMock(return_value=[]))
    clinical = await request("GET", "/api/reports")
    assert clinical.status_code == 200
    assert clinical.json() == []
    assert_private(clinical)

    as_user("receptionist")
    denied = await request("GET", "/api/reports")
    assert denied.status_code == 403
    assert_private(denied)


@pytest.mark.asyncio
async def test_missing_authenticated_patient_profile_is_not_cached(monkeypatch):
    as_user("admin")
    monkeypatch.setattr(UserService, "get_admin_patient", AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Patient not found"),
    ))
    response = await request("GET", "/api/users/patients/fictional-missing-patient")
    assert response.status_code == 404
    assert response.json() == {"detail": "Patient not found"}
    assert_private(response)


@pytest.mark.asyncio
async def test_public_non_sensitive_routes_keep_their_existing_cache_policy(monkeypatch):
    monkeypatch.setattr(UserService, "search_public_doctors", AsyncMock(return_value=[]))
    public = await request("GET", "/api/users/public/doctors")
    assert public.status_code == 200
    assert public.json() == []
    assert "cache-control" not in public.headers
    root = await request("GET", "/")
    assert root.status_code == 200
    assert "cache-control" not in root.headers


@pytest.mark.asyncio
async def test_early_unsafe_origin_rejection_is_not_cached():
    response = await request(
        "POST", "/api/auth/login",
        headers={"Origin": "https://untrusted.example"},
        json={},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Origin not allowed"}
    assert_private(response)


@pytest.mark.asyncio
async def test_authentication_policy_replaces_a_weaker_route_cache_header():
    request_scope = {
        "type": "http", "method": "POST", "path": "/api/auth/login",
        "headers": [], "query_string": b"", "scheme": "http",
        "server": ("testserver", 80),
    }

    async def weaker_response(_request):
        return JSONResponse({"role": "patient"}, headers={"Cache-Control": "public, max-age=60"})

    response = await protect_private_api_responses(Request(request_scope), weaker_response)
    assert_private(response)
