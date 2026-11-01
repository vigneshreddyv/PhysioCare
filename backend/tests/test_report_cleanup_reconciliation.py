import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.models.lab_request import LabRequest
from app.models.report import Report
from app.services.clinical_report_storage import ClinicalReportStorage, LabReportStorage
from app.services.report_cleanup_reconciler import ReportCleanupReconciler


@pytest.fixture(params=[ClinicalReportStorage, LabReportStorage])
def storage(request, monkeypatch, tmp_path):
    storage_class = request.param
    monkeypatch.setattr(settings, storage_class.STORAGE_DIR_SETTING, str(tmp_path / "approved"))
    monkeypatch.setattr(settings, storage_class.QUARANTINE_DIR_SETTING, str(tmp_path / "audit"))
    return storage_class


def approved_fixture(storage):
    key = "a" * 32 + ".pdf"
    path = storage.resolve(key)
    path.write_bytes(b"%PDF-1.4\nfictional\n%%EOF\n")
    storage._audit(key, "Approved", uploaded_by_user_id="fictional-user")
    return key, path


@pytest.mark.asyncio
async def test_ambiguous_database_failure_retains_private_file_until_checked(storage):
    key, path = approved_fixture(storage)
    assert storage.delete(key) is False
    assert path.is_file()
    assert storage.pending_cleanup_inventory()[0][0] == key

    referenced = AsyncMock(return_value=True)
    counts = await storage.reconcile_pending_cleanup(referenced, min_age_seconds=0)
    assert counts["retained"] == 1
    referenced.assert_awaited_once_with(key)
    assert path.is_file()
    assert storage.pending_cleanup_inventory() == []
    audit = json.loads(storage._audit_path(key).read_text(encoding="utf-8"))
    assert audit["state"] == "CleanupRetained"


@pytest.mark.asyncio
async def test_failed_delete_keeps_pending_intent_for_safe_retry(storage, monkeypatch, caplog):
    key, path = approved_fixture(storage)
    original_unlink = Path.unlink
    fail_once = True

    def flaky_unlink(candidate, *args, **kwargs):
        nonlocal fail_once
        if candidate == path and fail_once:
            fail_once = False
            raise OSError("/private/clinical/fictional.pdf")
        return original_unlink(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    with caplog.at_level(logging.WARNING):
        assert storage.delete(key, reason_code="superseded") is False
    assert path.is_file()
    assert storage.pending_cleanup_inventory()[0][0] == key
    assert key not in caplog.text
    assert "/private/clinical/fictional.pdf" not in caplog.text

    counts = await storage.reconcile_pending_cleanup(
        AsyncMock(return_value=False), min_age_seconds=0
    )
    assert counts["removed"] == 1
    assert not path.exists()
    assert storage.pending_cleanup_inventory() == []


@pytest.mark.asyncio
async def test_reference_check_failure_and_grace_period_never_delete(storage):
    key, path = approved_fixture(storage)
    assert storage.delete(key) is False

    checker = AsyncMock(return_value=False)
    counts = await storage.reconcile_pending_cleanup(checker)
    assert counts["deferred"] == 1
    checker.assert_not_awaited()

    checker.side_effect = RuntimeError("database unavailable")
    counts = await storage.reconcile_pending_cleanup(checker, min_age_seconds=0)
    assert counts["failed"] == 1
    assert path.is_file()
    assert storage.pending_cleanup_inventory()[0][0] == key


def test_cleanup_journal_failure_keeps_file_private_and_logs_without_path(
    storage, monkeypatch, caplog
):
    key, path = approved_fixture(storage)

    def unavailable_journal(*_, **__):
        raise OSError("/private/clinical/audit-unavailable")

    monkeypatch.setattr(storage, "_audit", unavailable_journal)
    with caplog.at_level(logging.WARNING):
        assert storage.delete(key, reason_code="superseded") is False
    assert path.is_file()
    assert key not in caplog.text
    assert "/private/clinical/audit-unavailable" not in caplog.text


@pytest.mark.asyncio
async def test_reconciler_checks_majority_primary_references_for_both_stores(monkeypatch):
    clinical_collection = AsyncMock()
    lab_collection = AsyncMock()
    clinical_collection.count_documents.return_value = 1
    lab_collection.count_documents.return_value = 0

    class CollectionDouble:
        def __init__(self, configured):
            self.configured = configured

        def with_options(self, **options):
            assert options["read_preference"].name == "Primary"
            assert options["read_concern"].level == "majority"
            return self.configured

    monkeypatch.setattr(Report, "get_pymongo_collection", lambda: CollectionDouble(clinical_collection))
    monkeypatch.setattr(LabRequest, "get_pymongo_collection", lambda: CollectionDouble(lab_collection))

    async def clinical_reconcile(checker, **_):
        assert await checker("clinical-key.pdf") is True
        return {"retained": 1}

    async def lab_reconcile(checker, **_):
        assert await checker("lab-key.pdf") is False
        return {"removed": 1}

    monkeypatch.setattr(ClinicalReportStorage, "reconcile_pending_cleanup", clinical_reconcile)
    monkeypatch.setattr(LabReportStorage, "reconcile_pending_cleanup", lab_reconcile)
    assert await ReportCleanupReconciler.run(min_age_seconds=0) == {
        "clinical": {"retained": 1},
        "laboratory": {"removed": 1},
    }
