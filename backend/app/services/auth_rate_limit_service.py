import asyncio
import hashlib
import hmac
import ipaddress
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from fastapi import HTTPException, Request, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.time import utc_now
from app.models.auth_rate_limit import AuthRateLimitBucket


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int


def _utc_epoch_seconds(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


class RateLimitStore(Protocol):
    async def check(
        self,
        bucket_key: str,
        *,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> RateLimitDecision: ...

    async def consume(
        self,
        bucket_key: str,
        *,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> RateLimitDecision: ...

    async def clear(self, bucket_key: str) -> None: ...


class MongoRateLimitStore:
    """Atomic shared store used by every application worker."""

    async def check(
        self,
        bucket_key: str,
        *,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> RateLimitDecision:
        document = await AuthRateLimitBucket.get_pymongo_collection().find_one(
            {"bucket_key": bucket_key},
            {"attempt_count": 1},
        )
        count = int(document["attempt_count"]) if document else 0
        window_end = datetime.fromtimestamp(
            (math.floor(_utc_epoch_seconds(now) / window_seconds) + 1)
            * window_seconds,
            timezone.utc,
        ).replace(tzinfo=None)
        retry_after = max(1, math.ceil((window_end - now).total_seconds()))
        return RateLimitDecision(count < limit, retry_after)

    async def consume(
        self,
        bucket_key: str,
        *,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> RateLimitDecision:
        window_end = datetime.fromtimestamp(
            (math.floor(_utc_epoch_seconds(now) / window_seconds) + 1) * window_seconds,
            timezone.utc,
        ).replace(tzinfo=None)
        collection = AuthRateLimitBucket.get_pymongo_collection()
        for attempt in range(2):
            try:
                document = await collection.find_one_and_update(
                    {"bucket_key": bucket_key},
                    {
                        "$inc": {"attempt_count": 1},
                        "$setOnInsert": {
                            "expires_at": window_end + timedelta(seconds=window_seconds),
                        },
                    },
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                )
                break
            except DuplicateKeyError:
                # Two workers can race while upserting the first counter for a
                # window. Once the unique-key winner commits, retry as an
                # ordinary atomic increment instead of failing authentication.
                if attempt:
                    raise
        else:  # pragma: no cover - the bounded loop always breaks or raises
            raise RuntimeError("Unable to update authentication rate limit")
        count = int(document["attempt_count"])
        retry_after = max(1, math.ceil((window_end - now).total_seconds()))
        return RateLimitDecision(count <= limit, retry_after)

    async def clear(self, bucket_key: str) -> None:
        await AuthRateLimitBucket.get_pymongo_collection().delete_one(
            {"bucket_key": bucket_key}
        )


class InMemoryRateLimitStore:
    """Deterministic test implementation; never used as the app default."""

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[int, datetime]] = {}
        self._lock = asyncio.Lock()

    @property
    def bucket_keys(self) -> set[str]:
        return set(self._buckets)

    async def check(
        self,
        bucket_key: str,
        *,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> RateLimitDecision:
        window_end = datetime.fromtimestamp(
            (math.floor(_utc_epoch_seconds(now) / window_seconds) + 1)
            * window_seconds,
            timezone.utc,
        ).replace(tzinfo=None)
        async with self._lock:
            count, existing_end = self._buckets.get(bucket_key, (0, window_end))
            if now >= existing_end:
                count, existing_end = 0, window_end
                self._buckets.pop(bucket_key, None)
        retry_after = max(1, math.ceil((existing_end - now).total_seconds()))
        return RateLimitDecision(count < limit, retry_after)

    async def consume(
        self,
        bucket_key: str,
        *,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> RateLimitDecision:
        window_end = datetime.fromtimestamp(
            (math.floor(_utc_epoch_seconds(now) / window_seconds) + 1) * window_seconds,
            timezone.utc,
        ).replace(tzinfo=None)
        async with self._lock:
            count, existing_end = self._buckets.get(bucket_key, (0, window_end))
            if now >= existing_end:
                count, existing_end = 0, window_end
            count += 1
            self._buckets[bucket_key] = (count, existing_end)
        retry_after = max(1, math.ceil((existing_end - now).total_seconds()))
        return RateLimitDecision(count <= limit, retry_after)

    async def clear(self, bucket_key: str) -> None:
        async with self._lock:
            self._buckets.pop(bucket_key, None)


def _trusted_proxy_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return tuple(
        ipaddress.ip_network(value, strict=False)
        for value in settings.TRUSTED_PROXY_NETWORKS
    )


def client_ip(request: Request) -> str:
    """Resolve a client address without trusting arbitrary forwarding headers."""

    direct_text = request.client.host if request.client else "0.0.0.0"
    try:
        direct = ipaddress.ip_address(direct_text)
    except ValueError:
        return "0.0.0.0"

    trusted = _trusted_proxy_networks()
    if not any(direct in network for network in trusted):
        return direct.compressed

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct.compressed
    try:
        chain = [ipaddress.ip_address(item.strip()) for item in forwarded.split(",")]
    except ValueError:
        return direct.compressed

    for candidate in reversed(chain):
        if not any(candidate in network for network in trusted):
            return candidate.compressed
    return direct.compressed


class AuthRateLimiter:
    SAFE_MESSAGE = "Too many requests. Try again later."

    def __init__(self, store: RateLimitStore) -> None:
        self.store = store

    @staticmethod
    def _digest(purpose: str, identifier: str, now: datetime, window: int) -> str:
        window_number = math.floor(_utc_epoch_seconds(now) / window)
        message = f"physiocare-auth-limit:{purpose}:{identifier}:{window_number}"
        return hmac.new(
            settings.JWT_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _raise_limited(retry_after: int) -> None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=AuthRateLimiter.SAFE_MESSAGE,
            headers={"Retry-After": str(retry_after)},
        )

    @staticmethod
    def _storage_unavailable() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )

    async def _consume(
        self,
        purpose: str,
        identifier: str,
        *,
        limit: int,
        window: int,
        now: datetime,
    ) -> str:
        bucket_key = self._digest(purpose, identifier, now, window)
        try:
            decision = await self.store.consume(
                bucket_key,
                limit=limit,
                window_seconds=window,
                now=now,
            )
        except Exception as exc:
            raise self._storage_unavailable() from exc
        if not decision.allowed:
            self._raise_limited(decision.retry_after_seconds)
        return bucket_key

    async def _check(
        self,
        purpose: str,
        identifier: str,
        *,
        limit: int,
        window: int,
        now: datetime,
    ) -> None:
        bucket_key = self._digest(purpose, identifier, now, window)
        try:
            decision = await self.store.check(
                bucket_key,
                limit=limit,
                window_seconds=window,
                now=now,
            )
        except Exception as exc:
            raise self._storage_unavailable() from exc
        if not decision.allowed:
            self._raise_limited(decision.retry_after_seconds)

    async def before_login(
        self, request: Request, email: str, *, now: datetime | None = None
    ) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return
        current = now or utc_now()
        await self._consume(
            "login-ip",
            client_ip(request),
            limit=settings.AUTH_LOGIN_IP_LIMIT,
            window=settings.AUTH_LOGIN_WINDOW_SECONDS,
            now=current,
        )
        # Reserve the account attempt before password verification. A separate
        # check followed by a post-failure increment lets a concurrent burst
        # perform an unbounded number of password guesses before the counter is
        # visible. A successful login clears this reservation.
        await self._consume(
            "login-account-failure",
            email.strip().casefold(),
            limit=settings.AUTH_LOGIN_FAILURE_LIMIT,
            window=settings.AUTH_LOGIN_WINDOW_SECONDS,
            now=current,
        )

    async def login_succeeded(self, email: str, *, now: datetime | None = None) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return
        current = now or utc_now()
        key = self._digest(
            "login-account-failure",
            email.strip().casefold(),
            current,
            settings.AUTH_LOGIN_WINDOW_SECONDS,
        )
        try:
            await self.store.clear(key)
        except Exception:
            # Authentication has already succeeded and its session has been
            # persisted. A best-effort failure-counter clear must not orphan
            # that valid session or suppress its cookies.
            return

    async def registration(
        self, request: Request, *, now: datetime | None = None
    ) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return
        current = now or utc_now()
        await self._consume(
            "registration-ip",
            client_ip(request),
            limit=settings.AUTH_REGISTRATION_LIMIT,
            window=settings.AUTH_REGISTRATION_WINDOW_SECONDS,
            now=current,
        )

    async def refresh(
        self,
        request: Request,
        refresh_token: str | None,
        *,
        now: datetime | None = None,
    ) -> None:
        if not settings.AUTH_RATE_LIMIT_ENABLED:
            return
        current = now or utc_now()
        address = client_ip(request)
        await self._consume(
            "refresh-ip",
            address,
            limit=settings.AUTH_REFRESH_IP_LIMIT,
            window=settings.AUTH_REFRESH_WINDOW_SECONDS,
            now=current,
        )
        identifier = refresh_token or f"missing:{address}"
        await self._consume(
            "refresh-token",
            identifier,
            limit=settings.AUTH_REFRESH_LIMIT,
            window=settings.AUTH_REFRESH_WINDOW_SECONDS,
            now=current,
        )


auth_rate_limiter = AuthRateLimiter(MongoRateLimitStore())
