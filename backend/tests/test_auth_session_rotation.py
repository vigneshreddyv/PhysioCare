import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from beanie import PydanticObjectId
from fastapi import HTTPException
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_csrf_token,
    create_refresh_token,
    decode_token,
    hash_session_secret,
)
from app.repositories.session_repository import SessionRepository
from app.services import auth_service
from app.services.auth_service import AuthService


USER_ID = PydanticObjectId("507f1f77bcf86cd799439011")
SESSION_ID = PydanticObjectId("507f1f77bcf86cd799439012")


def make_user(*, active=True):
    return SimpleNamespace(
        id=USER_ID,
        role="doctor",
        email="doctor@example.test",
        full_name="Test Doctor",
        hashed_password="hashed",
        is_active=active,
        demo_rehearsal_tag=None,
    )


def make_refresh_context():
    refresh_token = create_refresh_token(USER_ID, "doctor", str(SESSION_ID))
    csrf_token = create_csrf_token(str(SESSION_ID))
    session = SimpleNamespace(
        id=SESSION_ID,
        user_id=USER_ID,
        refresh_token_hash=hash_session_secret(refresh_token),
        csrf_token_hash=hash_session_secret(csrf_token),
        expires_at=datetime.utcnow() + timedelta(days=1),
        revoked_at=None,
    )
    return refresh_token, csrf_token, session


def install_refresh_context(monkeypatch, session, user=None):
    monkeypatch.setattr(
        auth_service.SessionRepository,
        "get_by_id",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(
        auth_service.UserRepository,
        "get_by_id",
        AsyncMock(return_value=user or make_user()),
    )


@pytest.mark.asyncio
async def test_login_persists_complete_hashed_session_before_returning_tokens(
    monkeypatch,
):
    user = make_user()
    create = AsyncMock()
    monkeypatch.setattr(
        auth_service.UserRepository,
        "get_by_email",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr(auth_service, "verify_password", lambda *_args: True)
    monkeypatch.setattr(auth_service.SessionRepository, "create", create)

    result = await AuthService.login(user.email, "password")

    create.assert_awaited_once()
    session = create.await_args.args[0]
    assert session.refresh_token_hash == hash_session_secret(result.refresh_token)
    assert session.csrf_token_hash == hash_session_secret(result.csrf_token)
    assert session.refresh_token_hash != "pending"
    assert session.csrf_token_hash != "pending"


@pytest.mark.asyncio
async def test_login_persistence_failure_returns_no_session_bundle(monkeypatch):
    user = make_user()
    monkeypatch.setattr(
        auth_service.UserRepository,
        "get_by_email",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr(auth_service, "verify_password", lambda *_args: True)
    monkeypatch.setattr(
        auth_service.SessionRepository,
        "create",
        AsyncMock(side_effect=RuntimeError("database details")),
    )

    with pytest.raises(HTTPException) as error:
        await AuthService.login(user.email, "password")

    assert error.value.status_code == 503
    assert "database details" not in error.value.detail


@pytest.mark.asyncio
async def test_refresh_atomically_rotates_hash_and_preserves_cookie_contract(
    monkeypatch,
):
    old_refresh, csrf_token, session = make_refresh_context()
    rotate = AsyncMock(return_value={"_id": SESSION_ID})
    install_refresh_context(monkeypatch, session)
    monkeypatch.setattr(auth_service.SessionRepository, "rotate_for_refresh", rotate)

    result = await AuthService.refresh_tokens(old_refresh, csrf_token)

    assert result.refresh_token != old_refresh
    assert result.csrf_token == csrf_token
    old_payload = decode_token(old_refresh, secret=settings.JWT_REFRESH_SECRET)
    new_payload = decode_token(
        result.refresh_token,
        secret=settings.JWT_REFRESH_SECRET,
    )
    assert new_payload["sid"] == old_payload["sid"] == str(SESSION_ID)
    assert new_payload["jti"] != old_payload["jti"]
    rotate.assert_awaited_once()
    values = rotate.await_args.kwargs
    assert values["current_refresh_token_hash"] == hash_session_secret(old_refresh)
    assert values["new_refresh_token_hash"] == hash_session_secret(
        result.refresh_token
    )


@pytest.mark.asyncio
async def test_invalid_csrf_never_claims_or_revokes_refresh_session(monkeypatch):
    old_refresh, _csrf_token, session = make_refresh_context()
    rotate = AsyncMock()
    revoke = AsyncMock()
    install_refresh_context(monkeypatch, session)
    monkeypatch.setattr(auth_service.SessionRepository, "rotate_for_refresh", rotate)
    monkeypatch.setattr(auth_service.SessionRepository, "revoke_by_id", revoke)

    with pytest.raises(HTTPException) as error:
        await AuthService.refresh_tokens(old_refresh, "wrong-csrf")

    assert error.value.status_code == 403
    rotate.assert_not_awaited()
    revoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_reuse_of_stale_refresh_token_revokes_session(monkeypatch):
    old_refresh, csrf_token, session = make_refresh_context()
    session.refresh_token_hash = hash_session_secret("newer-refresh-token")
    revoke = AsyncMock(return_value=1)
    install_refresh_context(monkeypatch, session)
    monkeypatch.setattr(auth_service.SessionRepository, "revoke_by_id", revoke)

    with pytest.raises(HTTPException) as error:
        await AuthService.refresh_tokens(old_refresh, csrf_token)

    assert error.value.status_code == 401
    revoke.assert_awaited_once()
    assert revoke.await_args.kwargs["reason"] == "refresh_token_reuse_detected"


@pytest.mark.asyncio
async def test_only_one_mocked_atomic_refresh_claim_wins(monkeypatch):
    old_refresh, csrf_token, session = make_refresh_context()
    rotate = AsyncMock(side_effect=[{"_id": SESSION_ID}, None])
    revoke = AsyncMock(return_value=1)
    install_refresh_context(monkeypatch, session)
    monkeypatch.setattr(auth_service.SessionRepository, "rotate_for_refresh", rotate)
    monkeypatch.setattr(auth_service.SessionRepository, "revoke_by_id", revoke)

    results = await asyncio.gather(
        AuthService.refresh_tokens(old_refresh, csrf_token),
        AuthService.refresh_tokens(old_refresh, csrf_token),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(
        isinstance(result, HTTPException) and result.status_code == 401
        for result in results
    ) == 1
    revoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_atomic_refresh_race_cannot_leave_replacement_active(monkeypatch):
    old_refresh, csrf_token, session = make_refresh_context()

    class AtomicSession:
        def __init__(self):
            self.lock = asyncio.Lock()
            self.active = True
            self.token_hash = hash_session_secret(old_refresh)

        async def rotate(self, **values):
            async with self.lock:
                if (
                    not self.active
                    or values["current_refresh_token_hash"] != self.token_hash
                ):
                    return None
                self.token_hash = values["new_refresh_token_hash"]
                return {"_id": SESSION_ID}

        async def revoke(self, _session_id, **_values):
            async with self.lock:
                if not self.active:
                    return 0
                self.active = False
                return 1

    state = AtomicSession()
    install_refresh_context(monkeypatch, session)
    monkeypatch.setattr(
        auth_service.SessionRepository,
        "rotate_for_refresh",
        state.rotate,
    )
    monkeypatch.setattr(
        auth_service.SessionRepository,
        "revoke_by_id",
        state.revoke,
    )

    results = await asyncio.gather(
        AuthService.refresh_tokens(old_refresh, csrf_token),
        AuthService.refresh_tokens(old_refresh, csrf_token),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert state.active is False


@pytest.mark.asyncio
async def test_token_signing_failure_happens_before_atomic_claim(monkeypatch):
    old_refresh, csrf_token, session = make_refresh_context()
    rotate = AsyncMock()
    install_refresh_context(monkeypatch, session)
    monkeypatch.setattr(auth_service.SessionRepository, "rotate_for_refresh", rotate)
    monkeypatch.setattr(
        auth_service,
        "create_access_token",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("signing details")),
    )

    with pytest.raises(HTTPException) as error:
        await AuthService.refresh_tokens(old_refresh, csrf_token)

    assert error.value.status_code == 503
    assert "signing details" not in error.value.detail
    rotate.assert_not_awaited()


@pytest.mark.asyncio
async def test_atomic_rotation_failure_is_service_unavailable(monkeypatch):
    old_refresh, csrf_token, session = make_refresh_context()
    revoke = AsyncMock()
    install_refresh_context(monkeypatch, session)
    monkeypatch.setattr(
        auth_service.SessionRepository,
        "rotate_for_refresh",
        AsyncMock(side_effect=RuntimeError("database details")),
    )
    monkeypatch.setattr(auth_service.SessionRepository, "revoke_by_id", revoke)

    with pytest.raises(HTTPException) as error:
        await AuthService.refresh_tokens(old_refresh, csrf_token)

    assert error.value.status_code == 503
    assert "database details" not in error.value.detail
    revoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_revocation_failure_is_service_unavailable(monkeypatch):
    old_refresh, csrf_token, session = make_refresh_context()
    install_refresh_context(monkeypatch, session)
    monkeypatch.setattr(
        auth_service.SessionRepository,
        "rotate_for_refresh",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        auth_service.SessionRepository,
        "revoke_by_id",
        AsyncMock(side_effect=RuntimeError("database details")),
    )

    with pytest.raises(HTTPException) as error:
        await AuthService.refresh_tokens(old_refresh, csrf_token)

    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_logout_revokes_the_server_session(monkeypatch):
    access_token = create_access_token(USER_ID, "doctor", str(SESSION_ID))
    revoke = AsyncMock(return_value=1)
    monkeypatch.setattr(auth_service.SessionRepository, "revoke_by_id", revoke)

    await AuthService.revoke_session(access_token, None)

    revoke.assert_awaited_once()
    assert revoke.await_args.args[0] == str(SESSION_ID)
    assert revoke.await_args.kwargs["reason"] == "logout"


@pytest.mark.asyncio
async def test_inactive_user_is_rejected_before_atomic_claim(monkeypatch):
    old_refresh, csrf_token, session = make_refresh_context()
    rotate = AsyncMock()
    install_refresh_context(monkeypatch, session, make_user(active=False))
    monkeypatch.setattr(auth_service.SessionRepository, "rotate_for_refresh", rotate)

    with pytest.raises(HTTPException) as error:
        await AuthService.refresh_tokens(old_refresh, csrf_token)

    assert error.value.status_code == 401
    rotate.assert_not_awaited()


@pytest.mark.asyncio
async def test_repository_rotation_filter_is_an_atomic_secret_claim(monkeypatch):
    collection = SimpleNamespace(find_one_and_update=AsyncMock(return_value={}))
    monkeypatch.setattr(
        "app.repositories.session_repository.AuthSession.get_pymongo_collection",
        lambda: collection,
    )
    now = datetime.utcnow()

    await SessionRepository.rotate_for_refresh(
        session_id=str(SESSION_ID),
        user_id=USER_ID,
        current_refresh_token_hash="old-hash",
        csrf_token_hash="csrf-hash",
        new_refresh_token_hash="new-hash",
        new_expires_at=now + timedelta(days=1),
        now=now,
    )

    query = collection.find_one_and_update.await_args.args[0]
    update = collection.find_one_and_update.await_args.args[1]
    assert query == {
        "_id": SESSION_ID,
        "user_id": USER_ID,
        "refresh_token_hash": "old-hash",
        "csrf_token_hash": "csrf-hash",
        "revoked_at": None,
        "expires_at": {"$gt": now},
    }
    assert update["$set"]["refresh_token_hash"] == "new-hash"
