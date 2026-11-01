import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.services.payment_reconciliation_worker import PaymentReconciliationWorker
from app.services.payment_service import PaymentService


class AtomicLeaseStore:
    """Deterministic fake for Mongo's single-document lease operation."""

    def __init__(self):
        self.document = None

    async def find_one_and_update(self, query, update, **_kwargs):
        owner_id = update["$set"]["owner_id"]
        now = datetime.now(timezone.utc)
        if (
            self.document is None
            or self.document["lease_expires_at"] <= now
            or self.document["owner_id"] == owner_id
        ):
            self.document = {"_id": query["_id"], **update["$set"]}
            return dict(self.document)
        return None

    async def update_one(self, query, update):
        if not self.document or self.document["_id"] != query["_id"] or self.document["owner_id"] != query["owner_id"]:
            return SimpleNamespace(matched_count=0)
        expires_after = query.get("lease_expires_at", {}).get("$gt")
        if expires_after and self.document["lease_expires_at"] <= expires_after:
            return SimpleNamespace(matched_count=0)
        self.document.update(update["$set"])
        return SimpleNamespace(matched_count=1)


def enable_worker(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_RECONCILIATION_ENABLED", True)
    monkeypatch.setattr(settings, "PAYMENT_RECONCILIATION_BATCH_SIZE", 17)
    monkeypatch.setattr(settings, "PAYMENT_RECONCILIATION_INTERVAL_SECONDS", 30)
    monkeypatch.setattr(settings, "PAYMENT_RECONCILIATION_LEASE_SECONDS", 120)
    monkeypatch.setattr(PaymentService, "is_test_configuration_ready", MagicMock(return_value=True))


def test_worker_configuration_has_validated_small_app_defaults():
    config = Settings(
        _env_file=None,
        ENVIRONMENT="test",
        PAYMENT_RECONCILIATION_ENABLED=True,
        JWT_SECRET="a" * 32,
        JWT_REFRESH_SECRET="b" * 32,
    )
    assert config.PAYMENT_RECONCILIATION_ENABLED is True
    assert config.PAYMENT_RECONCILIATION_INTERVAL_SECONDS == 30
    assert config.PAYMENT_RECONCILIATION_BATCH_SIZE == 50
    assert config.PAYMENT_RECONCILIATION_LEASE_SECONDS == 120
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="test",
            PAYMENT_RECONCILIATION_ENABLED=True,
            JWT_SECRET="a" * 32,
            JWT_REFRESH_SECRET="b" * 32,
            PAYMENT_RECONCILIATION_INTERVAL_SECONDS=30,
            PAYMENT_RECONCILIATION_LEASE_SECONDS=29,
        )


@pytest.mark.asyncio
async def test_worker_runs_one_bounded_service_cycle_and_releases_lease(monkeypatch):
    enable_worker(monkeypatch)
    lease_store = AtomicLeaseStore()
    monkeypatch.setattr(PaymentReconciliationWorker, "_lease_collection", staticmethod(lambda: lease_store))
    reconcile = AsyncMock(return_value={"examined": 3, "recovered": 1, "clinic_review": [], "failed": []})
    monkeypatch.setattr(PaymentService, "reconcile_captured_payments", reconcile)
    worker = PaymentReconciliationWorker()

    result = await worker.run_once()

    assert result["recovered"] == 1
    reconcile.assert_awaited_once()
    assert reconcile.await_args.kwargs["batch_size"] == 17
    assert reconcile.await_args.kwargs["include_clinic_review"] is False
    assert reconcile.await_args.kwargs["should_continue"]()
    assert lease_store.document["lease_expires_at"] <= datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_two_instances_do_not_run_worker_cycles_concurrently(monkeypatch):
    enable_worker(monkeypatch)
    lease_store = AtomicLeaseStore()
    monkeypatch.setattr(PaymentReconciliationWorker, "_lease_collection", staticmethod(lambda: lease_store))
    entered_service = asyncio.Event()
    release_service = asyncio.Event()

    async def slow_service(**_kwargs):
        entered_service.set()
        await release_service.wait()
        return {"examined": 1, "recovered": 1, "clinic_review": [], "failed": []}

    reconcile = AsyncMock(side_effect=slow_service)
    monkeypatch.setattr(PaymentService, "reconcile_captured_payments", reconcile)
    first = PaymentReconciliationWorker()
    second = PaymentReconciliationWorker()
    first_cycle = asyncio.create_task(first.run_once())
    await entered_service.wait()

    second_result = await second.run_once()
    release_service.set()
    first_result = await first_cycle

    assert first_result["recovered"] == 1
    assert second_result == {"examined": 0, "recovered": 0, "clinic_review": [], "failed": []}
    reconcile.assert_awaited_once()


@pytest.mark.asyncio
async def test_lease_renewal_cannot_revive_expired_lease(monkeypatch):
    enable_worker(monkeypatch)
    lease_store = AtomicLeaseStore()
    monkeypatch.setattr(PaymentReconciliationWorker, "_lease_collection", staticmethod(lambda: lease_store))
    worker = PaymentReconciliationWorker()
    assert await worker._acquire_lease()

    lease_store.document["lease_expires_at"] = datetime(2000, 1, 1, tzinfo=timezone.utc)

    assert not await worker._renew_lease()


@pytest.mark.asyncio
async def test_worker_stops_before_next_record_after_lease_loss(monkeypatch):
    enable_worker(monkeypatch)
    lease_store = AtomicLeaseStore()
    monkeypatch.setattr(PaymentReconciliationWorker, "_lease_collection", staticmethod(lambda: lease_store))
    service_started = asyncio.Event()
    lease_loss_signalled = asyncio.Event()
    worker = PaymentReconciliationWorker()

    async def lose_lease(stop_event, lost_event):
        await service_started.wait()
        lost_event.set()
        lease_loss_signalled.set()

    monkeypatch.setattr(worker, "_maintain_lease", lose_lease)

    async def service(**kwargs):
        assert kwargs["should_continue"]()
        service_started.set()
        await lease_loss_signalled.wait()
        assert not kwargs["should_continue"]()
        return {"examined": 1, "recovered": 0, "clinic_review": [], "failed": []}

    reconcile = AsyncMock(side_effect=service)
    monkeypatch.setattr(PaymentService, "reconcile_captured_payments", reconcile)

    cycle = asyncio.create_task(worker.run_once())
    await service_started.wait()
    result = await cycle

    assert result["examined"] == 1
    assert not reconcile.await_args.kwargs["should_continue"]()


@pytest.mark.asyncio
async def test_database_outage_is_reported_without_crashing_the_worker_cycle(monkeypatch):
    enable_worker(monkeypatch)
    lease_store = AtomicLeaseStore()
    monkeypatch.setattr(PaymentReconciliationWorker, "_lease_collection", staticmethod(lambda: lease_store))
    reconcile = AsyncMock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr(PaymentService, "reconcile_captured_payments", reconcile)
    worker = PaymentReconciliationWorker()

    result = await worker.run_once()

    assert result == {"examined": 0, "recovered": 0, "clinic_review": [], "failed": [None]}
    reconcile.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_shutdown_cancels_and_awaits_active_task(monkeypatch):
    enable_worker(monkeypatch)
    lease_store = AtomicLeaseStore()
    monkeypatch.setattr(PaymentReconciliationWorker, "_lease_collection", staticmethod(lambda: lease_store))
    entered_service = asyncio.Event()

    async def wait_until_cancelled(**_kwargs):
        entered_service.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(PaymentService, "reconcile_captured_payments", AsyncMock(side_effect=wait_until_cancelled))
    worker = PaymentReconciliationWorker()
    await worker.start()
    await entered_service.wait()
    task = worker._task

    await worker.stop()

    assert task is not None and task.done()
    assert worker._task is None
    assert not [task for task in asyncio.all_tasks() if task.get_name() == "payment-reconciliation-worker"]


@pytest.mark.asyncio
async def test_application_lifespan_initializes_database_before_worker_and_stops_it(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "PAYMENT_RECONCILIATION_ENABLED", True)
    calls = []

    async def init_database():
        calls.append("database")

    class FakeWorker:
        async def start(self):
            calls.append("worker-start")

        async def stop(self):
            calls.append("worker-stop")

    monkeypatch.setattr(main_module, "init_db", init_database)
    monkeypatch.setattr(main_module, "PaymentReconciliationWorker", FakeWorker)
    app_state = SimpleNamespace(state=SimpleNamespace())

    async with main_module.lifespan(app_state):
        calls.append("serve")

    assert calls == ["database", "worker-start", "serve", "worker-stop"]
