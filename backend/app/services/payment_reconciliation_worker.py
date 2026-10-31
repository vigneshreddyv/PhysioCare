import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.models.payment_attempt import PaymentAttempt
from app.services.payment_service import PaymentService


logger = logging.getLogger(__name__)


class PaymentReconciliationWorker:
    """Bounded at-least-once reconciliation loop coordinated by a Mongo lease."""

    LEASE_ID = "razorpay-captured-payment-reconciliation"
    LEASE_COLLECTION = "payment_reconciliation_worker_leases"

    def __init__(self):
        self.worker_id = str(uuid4())
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._cycle_lock = asyncio.Lock()

    @staticmethod
    def _lease_collection():
        attempts = PaymentAttempt.get_pymongo_collection()
        return attempts.database[PaymentReconciliationWorker.LEASE_COLLECTION]

    async def _acquire_lease(self) -> bool:
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=settings.PAYMENT_RECONCILIATION_LEASE_SECONDS)
        try:
            lease = await self._lease_collection().find_one_and_update(
                {
                    "_id": self.LEASE_ID,
                    "$or": [
                        {"lease_expires_at": {"$lte": now}},
                        {"lease_expires_at": {"$exists": False}},
                        {"owner_id": self.worker_id},
                    ],
                },
                {"$set": {"owner_id": self.worker_id, "lease_expires_at": lease_until}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            # Another instance owns the single lease document.
            return False
        return bool(lease and lease.get("owner_id") == self.worker_id)

    async def _renew_lease(self) -> bool:
        now = datetime.now(timezone.utc)
        result = await self._lease_collection().update_one(
            {
                "_id": self.LEASE_ID,
                "owner_id": self.worker_id,
                "lease_expires_at": {"$gt": now},
            },
            {"$set": {
                "lease_expires_at": now + timedelta(seconds=settings.PAYMENT_RECONCILIATION_LEASE_SECONDS),
            }},
        )
        return bool(result.matched_count)

    async def _release_lease(self) -> None:
        await self._lease_collection().update_one(
            {"_id": self.LEASE_ID, "owner_id": self.worker_id},
            {"$set": {"lease_expires_at": datetime.now(timezone.utc)}},
        )

    async def _maintain_lease(self, stop_event: asyncio.Event, lost_event: asyncio.Event) -> None:
        heartbeat_seconds = max(1, settings.PAYMENT_RECONCILIATION_LEASE_SECONDS // 3)
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=heartbeat_seconds)
                return
            except asyncio.TimeoutError:
                pass
            try:
                if not await self._renew_lease():
                    lost_event.set()
                    logger.warning("Payment reconciliation worker lease was lost")
                    return
            except Exception as exc:
                lost_event.set()
                logger.warning(
                    "Payment reconciliation worker lease renewal failed",
                    extra={"error_type": type(exc).__name__},
                )
                return

    async def run_once(self) -> dict:
        """Run one bounded cycle; callers may safely retry after any interruption."""
        if self._cycle_lock.locked():
            return {"examined": 0, "recovered": 0, "clinic_review": [], "failed": []}

        async with self._cycle_lock:
            if not settings.PAYMENT_RECONCILIATION_ENABLED or not PaymentService.is_test_configuration_ready():
                return {"examined": 0, "recovered": 0, "clinic_review": [], "failed": []}
            try:
                acquired = await self._acquire_lease()
            except Exception as exc:
                logger.error(
                    "Payment reconciliation worker could not acquire its database lease",
                    extra={"error_type": type(exc).__name__},
                )
                return {"examined": 0, "recovered": 0, "clinic_review": [], "failed": [None]}
            if not acquired:
                return {"examined": 0, "recovered": 0, "clinic_review": [], "failed": []}

            heartbeat_stop = asyncio.Event()
            lease_lost = asyncio.Event()
            heartbeat = asyncio.create_task(self._maintain_lease(heartbeat_stop, lease_lost))
            try:
                result = await PaymentService.reconcile_captured_payments(
                    batch_size=settings.PAYMENT_RECONCILIATION_BATCH_SIZE,
                    include_clinic_review=False,
                    should_continue=lambda: not lease_lost.is_set(),
                )
                if lease_lost.is_set():
                    logger.warning("Payment reconciliation cycle completed after losing its lease")
                logger.info(
                    "Payment reconciliation cycle completed",
                    extra={
                        "processed": result["examined"],
                        "recovered": result["recovered"],
                        "unresolved": len(result["clinic_review"]),
                        "failed": len(result["failed"]),
                    },
                )
                return result
            except Exception as exc:
                logger.error(
                    "Payment reconciliation database cycle failed; a later cycle will retry",
                    extra={
                        "processed": 0,
                        "recovered": 0,
                        "unresolved": 0,
                        "failed": 1,
                        "error_type": type(exc).__name__,
                    },
                )
                return {"examined": 0, "recovered": 0, "clinic_review": [], "failed": [None]}
            finally:
                heartbeat_stop.set()
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
                try:
                    await self._release_lease()
                except Exception as exc:
                    logger.warning(
                        "Payment reconciliation worker lease release failed; it will expire automatically",
                        extra={"error_type": type(exc).__name__},
                    )

    async def _run_loop(self) -> None:
        failures = 0
        interval = settings.PAYMENT_RECONCILIATION_INTERVAL_SECONDS
        while not self._stop_event.is_set():
            result = await self.run_once()
            failures = failures + 1 if result["failed"] else 0
            delay = min(interval * (2 ** min(max(failures - 1, 0), 5)), 300)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                continue

    async def start(self) -> None:
        if not settings.PAYMENT_RECONCILIATION_ENABLED:
            logger.info("Payment reconciliation worker is disabled by configuration")
            return
        if not PaymentService.is_test_configuration_ready():
            logger.info("Payment reconciliation worker is disabled because Razorpay Test Mode is not ready")
            return
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="payment-reconciliation-worker")
        logger.info(
            "Payment reconciliation worker started",
            extra={
                "interval_seconds": settings.PAYMENT_RECONCILIATION_INTERVAL_SECONDS,
                "batch_size": settings.PAYMENT_RECONCILIATION_BATCH_SIZE,
            },
        )

    async def stop(self) -> None:
        self._stop_event.set()
        task, self._task = self._task, None
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        try:
            await self._release_lease()
        except Exception as exc:
            logger.warning(
                "Payment reconciliation worker shutdown could not release its lease",
                extra={"error_type": type(exc).__name__},
            )
        logger.info("Payment reconciliation worker stopped")
