import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_refresh_token
from app.core.config import settings
from app.services import auth_service
from app.services.auth_service import AuthService
from app.main import app
from app.middleware.auth import get_current_user


USER_ID = "507f1f77bcf86cd799439011"


def make_user(*, active=True):
    return SimpleNamespace(
        id=USER_ID,
        role="doctor",
        email="doctor@example.com",
        full_name="Test Doctor",
        hashed_password="hashed",
        is_active=active,
    )


@pytest.mark.asyncio
async def test_login_persists_a_hashed_refresh_session(monkeypatch):
    user = make_user()
    create = AsyncMock()
    monkeypatch.setattr(auth_service.UserRepository, "get_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service, "verify_password", lambda *_: True)
    monkeypatch.setattr(auth_service.AuthSessionRepository, "create", create)

    result = await AuthService.login(user.email, "password")

    assert result.refresh_token
    create.assert_awaited_once()
    session = create.await_args.args[0]
    assert session.user_id == USER_ID
    assert session.token_hash != result.refresh_token


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_keeps_family(monkeypatch):
    user = make_user()
    old = create_refresh_token(USER_ID, user.role)
    old_payload = auth_service.decode_token(old, secret=settings.JWT_REFRESH_SECRET)
    rotate = AsyncMock(return_value=object())
    create = AsyncMock()
    monkeypatch.setattr(auth_service.UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service.AuthSessionRepository, "rotate_for_refresh", rotate)

    result = await AuthService.refresh_tokens(old)
    new_payload = auth_service.decode_token(result.refresh_token, secret=settings.JWT_REFRESH_SECRET)

    assert result.refresh_token != old
    assert new_payload["family_id"] == old_payload["family_id"]
    assert new_payload["jti"] != old_payload["jti"]
    rotate.assert_awaited_once()
    assert rotate.await_args.kwargs["user_id"] == USER_ID
    assert rotate.await_args.kwargs["family_id"] == old_payload["family_id"]


@pytest.mark.asyncio
async def test_reuse_of_rotated_token_revokes_family(monkeypatch):
    user = make_user()
    old = create_refresh_token(USER_ID, user.role)
    payload = auth_service.decode_token(old, secret=settings.JWT_REFRESH_SECRET)
    monkeypatch.setattr(auth_service.UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service.AuthSessionRepository, "rotate_for_refresh", AsyncMock(return_value=None))
    revoke = AsyncMock()
    monkeypatch.setattr(auth_service.AuthSessionRepository, "revoke_family", revoke)

    with pytest.raises(HTTPException) as exc:
        await AuthService.refresh_tokens(old)

    assert exc.value.status_code == 401
    revoke.assert_awaited_once()
    assert revoke.await_args.args[:2] == (USER_ID, payload["family_id"])


@pytest.mark.asyncio
async def test_logout_revokes_all_user_sessions(monkeypatch):
    revoke = AsyncMock()
    monkeypatch.setattr(auth_service.AuthSessionRepository, "revoke_all_for_user", revoke)

    await AuthService.logout(make_user())

    revoke.assert_awaited_once()
    assert revoke.await_args.args[0] == USER_ID


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user_before_rotation(monkeypatch):
    old = create_refresh_token(USER_ID, "doctor")
    rotate = AsyncMock()
    monkeypatch.setattr(auth_service.UserRepository, "get_by_id", AsyncMock(return_value=make_user(active=False)))
    monkeypatch.setattr(auth_service.AuthSessionRepository, "rotate_for_refresh", rotate)

    with pytest.raises(HTTPException) as exc:
        await AuthService.refresh_tokens(old)

    assert exc.value.status_code == 401
    rotate.assert_not_awaited()


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        create_access_token(USER_ID, "doctor"),
        create_refresh_token(USER_ID, "doctor", expires_delta=timedelta(seconds=-1)),
    ],
)
@pytest.mark.asyncio
async def test_invalid_expired_and_wrong_type_tokens_are_rejected(token):
    with pytest.raises(HTTPException) as exc:
        await AuthService.refresh_tokens(token)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_persistence_failure_does_not_return_tokens(monkeypatch):
    user = make_user()
    monkeypatch.setattr(auth_service.UserRepository, "get_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service, "verify_password", lambda *_: True)
    monkeypatch.setattr(
        auth_service.AuthSessionRepository,
        "create",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    )

    with pytest.raises(HTTPException) as exc:
        await AuthService.login(user.email, "password")

    assert exc.value.status_code == 503
    assert "database unavailable" not in exc.value.detail


@pytest.mark.asyncio
async def test_family_revocation_failure_returns_service_unavailable(monkeypatch):
    user = make_user()
    old = create_refresh_token(USER_ID, user.role)
    revoke = AsyncMock()
    monkeypatch.setattr(auth_service.UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service.AuthSessionRepository, "rotate_for_refresh", AsyncMock(return_value=None))
    revoke.side_effect = RuntimeError("db")
    monkeypatch.setattr(auth_service.AuthSessionRepository, "revoke_family", revoke)

    with pytest.raises(HTTPException) as exc:
        await AuthService.refresh_tokens(old)

    assert exc.value.status_code == 503
    revoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_only_one_mocked_atomic_claim_wins_concurrent_refresh(monkeypatch):
    user = make_user()
    old = create_refresh_token(USER_ID, user.role)
    rotate = AsyncMock(side_effect=[object(), None])
    revoke = AsyncMock()
    monkeypatch.setattr(auth_service.UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service.AuthSessionRepository, "rotate_for_refresh", rotate)
    monkeypatch.setattr(auth_service.AuthSessionRepository, "revoke_family", revoke)

    results = await asyncio.gather(
        AuthService.refresh_tokens(old),
        AuthService.refresh_tokens(old),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, HTTPException) and result.status_code == 401 for result in results) == 1
    revoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_atomic_family_race_cannot_leave_replacement_active(monkeypatch):
    user = make_user()
    old = create_refresh_token(USER_ID, user.role)
    old_payload = auth_service.decode_token(old, secret=settings.JWT_REFRESH_SECRET)

    class AtomicFamily:
        def __init__(self):
            self.lock = asyncio.Lock()
            self.active = True
            self.jti = old_payload["jti"]

        async def rotate(self, **kwargs):
            async with self.lock:
                if not self.active or kwargs["jti"] != self.jti:
                    return None
                self.jti = kwargs["new_jti"]
                return object()

        async def revoke(self, user_id, family_id, **kwargs):
            async with self.lock:
                if user_id == USER_ID and family_id == old_payload["family_id"] and self.active:
                    self.active = False
                    return 1
                return 0

    family = AtomicFamily()
    monkeypatch.setattr(auth_service.UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service.AuthSessionRepository, "rotate_for_refresh", family.rotate)
    monkeypatch.setattr(auth_service.AuthSessionRepository, "revoke_family", family.revoke)

    results = await asyncio.gather(
        AuthService.refresh_tokens(old),
        AuthService.refresh_tokens(old),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert family.active is False


@pytest.mark.asyncio
async def test_token_creation_failure_happens_before_rotation_claim(monkeypatch):
    user = make_user()
    old = create_refresh_token(USER_ID, user.role)
    rotate = AsyncMock()
    monkeypatch.setattr(auth_service.UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service, "create_access_token", lambda *_: (_ for _ in ()).throw(RuntimeError("signing")))
    monkeypatch.setattr(auth_service.AuthSessionRepository, "rotate_for_refresh", rotate)

    with pytest.raises(HTTPException) as exc:
        await AuthService.refresh_tokens(old)

    assert exc.value.status_code == 503
    rotate.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_token_creation_failure_happens_before_rotation_claim(monkeypatch):
    user = make_user()
    old = create_refresh_token(USER_ID, user.role)
    rotate = AsyncMock()
    monkeypatch.setattr(auth_service.UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service, "create_refresh_token", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("signing")))
    monkeypatch.setattr(auth_service.AuthSessionRepository, "rotate_for_refresh", rotate)

    with pytest.raises(HTTPException) as exc:
        await AuthService.refresh_tokens(old)

    assert exc.value.status_code == 503
    rotate.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_then_refresh_is_rejected(monkeypatch):
    user = make_user()
    old = create_refresh_token(USER_ID, user.role)
    monkeypatch.setattr(auth_service.UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service.AuthSessionRepository, "revoke_all_for_user", AsyncMock())
    rotate = AsyncMock(return_value=None)
    revoke = AsyncMock(return_value=0)
    monkeypatch.setattr(auth_service.AuthSessionRepository, "rotate_for_refresh", rotate)
    monkeypatch.setattr(auth_service.AuthSessionRepository, "revoke_family", revoke)

    await AuthService.logout(user)
    with pytest.raises(HTTPException) as exc:
        await AuthService.refresh_tokens(old)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_pre_upgrade_refresh_token_without_session_claims_is_rejected(monkeypatch):
    from jose import jwt
    from app.core.security import ALGORITHM

    old = jwt.encode(
        {"sub": USER_ID, "role": "doctor", "type": "refresh"},
        settings.JWT_REFRESH_SECRET,
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc:
        await AuthService.refresh_tokens(old)

    assert exc.value.status_code == 401


def test_logout_http_route_uses_authenticated_principal(monkeypatch):
    user = make_user()
    logout = AsyncMock()
    monkeypatch.setattr(auth_service.AuthService, "logout", logout)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = TestClient(app).post("/api/auth/logout")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 204
    logout.assert_awaited_once_with(user)
