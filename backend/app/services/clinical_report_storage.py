import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.services.pdf_malware_scanner import (
    PdfMalwareScanner,
    ScanResult,
    ScanVerdict,
    UnavailablePdfMalwareScanner,
)


logger = logging.getLogger(__name__)


class ClinicalReportStorage:
    CHUNK_SIZE = 64 * 1024
    PDF_HEADER = re.compile(br"^%PDF-1\.[0-9](?:\r?\n|\r)")
    SCAN_METADATA = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    OPAQUE_STORAGE_KEY = re.compile(r"^[0-9a-f]{32}\.pdf$")
    scanner: PdfMalwareScanner = UnavailablePdfMalwareScanner()
    STORAGE_DIR_SETTING = "CLINICAL_REPORT_STORAGE_DIR"
    QUARANTINE_DIR_SETTING = "CLINICAL_REPORT_QUARANTINE_DIR"
    MAX_BYTES_SETTING = "CLINICAL_REPORT_MAX_BYTES"
    STORAGE_LABEL = "Clinical report storage"
    QUARANTINE_LABEL = "Clinical report quarantine"
    REPORT_LABEL = "clinical report attachment"

    @staticmethod
    def _private_root(configured_value: str, label: str) -> Path:
        configured = Path(configured_value).expanduser()
        if configured.is_symlink():
            raise RuntimeError(f"{label} cannot be a symbolic link")
        root = configured.resolve()
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.is_symlink():
            raise RuntimeError(f"{label} cannot be a symbolic link")
        os.chmod(root, 0o700)
        return root

    @classmethod
    def _root(cls) -> Path:
        return cls._private_root(
            getattr(settings, cls.STORAGE_DIR_SETTING),
            cls.STORAGE_LABEL,
        )

    @classmethod
    def _quarantine_root(cls) -> Path:
        root = cls._private_root(
            getattr(settings, cls.QUARANTINE_DIR_SETTING),
            cls.QUARANTINE_LABEL,
        )
        approved_root = cls._root()
        if (
            root == approved_root
            or root.is_relative_to(approved_root)
            or approved_root.is_relative_to(root)
        ):
            raise RuntimeError(f"{cls.QUARANTINE_LABEL} must be separate from approved storage")
        return root

    @classmethod
    def resolve(cls, storage_key: str) -> Path:
        key_path = Path(storage_key)
        if key_path.name != storage_key or key_path.suffix.lower() != ".pdf":
            raise ValueError(f"Invalid {cls.REPORT_LABEL} storage key")
        root = cls._root()
        path = root / storage_key
        if path.is_symlink() or path.resolve().parent != root:
            raise ValueError(f"Invalid {cls.REPORT_LABEL} storage path")
        return path

    @classmethod
    def _audit_path(cls, storage_key: str) -> Path:
        return cls._quarantine_root() / f"{storage_key}.audit.json"

    @classmethod
    def _safe_scan_metadata(cls, value: str | None, fallback: str) -> str:
        normalized = value.strip().casefold() if isinstance(value, str) else ""
        return normalized if cls.SCAN_METADATA.fullmatch(normalized) else fallback

    @classmethod
    def _audit(
        cls,
        storage_key: str,
        state: str,
        *,
        uploaded_by_user_id: str,
        reason_code: str | None = None,
        scanner_engine: str | None = None,
    ) -> None:
        path = cls._audit_path(storage_key)
        payload: dict[str, Any]
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                payload = {
                    "schema_version": 1,
                    "storage_key": storage_key,
                    "events": [],
                }
        else:
            payload = {
                "schema_version": 1,
                "storage_key": storage_key,
                "uploaded_by_user_id": uploaded_by_user_id,
                "events": [],
            }
        event = {
            "state": state,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        if reason_code:
            event["reason_code"] = cls._safe_scan_metadata(
                reason_code,
                "scanner_reason_unavailable",
            )
        if scanner_engine:
            event["scanner_engine"] = cls._safe_scan_metadata(
                scanner_engine,
                "scanner_engine_unavailable",
            )
        payload["state"] = state
        payload["events"].append(event)
        temporary = path.with_name(f".{path.name}.part")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @classmethod
    def _validate_pdf_structure(cls, path: Path) -> bool:
        with path.open("rb") as handle:
            header = handle.read(16)
            if not cls.PDF_HEADER.match(header):
                return False
            handle.seek(max(0, path.stat().st_size - 2048))
            tail = handle.read()
        return b"%%EOF" in tail

    @classmethod
    async def store_pdf(
        cls,
        upload: UploadFile,
        *,
        uploaded_by_user_id: str = "unknown",
    ) -> str:
        content_type = (upload.content_type or "").split(";", 1)[0].lower()
        if content_type != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Only PDF {cls.REPORT_LABEL}s are accepted",
            )
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"The {cls.REPORT_LABEL} must use a .pdf filename",
            )
        max_bytes = getattr(settings, cls.MAX_BYTES_SETTING)
        if upload.size is not None and upload.size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"The {cls.REPORT_LABEL} is larger than the configured limit",
            )

        storage_key = f"{uuid4().hex}.pdf"
        quarantine_root = cls._quarantine_root()
        quarantine_path = quarantine_root / storage_key
        if quarantine_path.resolve().parent != quarantine_root:
            raise ValueError(f"Invalid {cls.REPORT_LABEL} quarantine path")
        descriptor = os.open(
            quarantine_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        size = 0
        approved_path: Path | None = None
        try:
            with os.fdopen(descriptor, "wb") as handle:
                while chunk := await upload.read(cls.CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"The {cls.REPORT_LABEL} is larger than the configured limit",
                        )
                    handle.write(chunk)
                if size == 0:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=f"The {cls.REPORT_LABEL} is empty",
                    )
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(quarantine_path, 0o600)
            cls._audit(
                storage_key,
                "Uploaded",
                uploaded_by_user_id=uploaded_by_user_id,
            )
            cls._audit(
                storage_key,
                "Quarantined",
                uploaded_by_user_id=uploaded_by_user_id,
            )
            if not cls._validate_pdf_structure(quarantine_path):
                cls._audit(
                    storage_key,
                    "Rejected",
                    uploaded_by_user_id=uploaded_by_user_id,
                    reason_code="invalid_pdf_structure",
                )
                quarantine_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"The {cls.REPORT_LABEL} is not a structurally valid PDF"
                    ),
                )

            cls._audit(
                storage_key,
                "Scanning",
                uploaded_by_user_id=uploaded_by_user_id,
            )
            try:
                result = await asyncio.wait_for(
                    cls.scanner.scan(quarantine_path),
                    timeout=settings.PDF_SCAN_TIMEOUT_SECONDS,
                )
                if not isinstance(result, ScanResult):
                    result = ScanResult(
                        verdict=ScanVerdict.ERROR,
                        engine="invalid-scanner-response",
                        reason_code="invalid_scanner_result",
                    )
                elif not isinstance(result.verdict, ScanVerdict):
                    result = ScanResult(
                        verdict=ScanVerdict.ERROR,
                        engine="invalid-scanner-response",
                        reason_code="invalid_scanner_verdict",
                    )
                else:
                    result = ScanResult(
                        verdict=result.verdict,
                        engine=cls._safe_scan_metadata(
                            result.engine,
                            "scanner_engine_unavailable",
                        ),
                        reason_code=cls._safe_scan_metadata(
                            result.reason_code,
                            "scanner_reason_unavailable",
                        ),
                    )
            except asyncio.TimeoutError:
                result = ScanResult(
                    verdict=ScanVerdict.ERROR,
                    engine="scanner-timeout",
                    reason_code="scanner_timeout",
                )
            except Exception:
                result = ScanResult(
                    verdict=ScanVerdict.ERROR,
                    engine="scanner-exception",
                    reason_code="scanner_transport_error",
                )

            if result.verdict == ScanVerdict.ERROR:
                cls._audit(
                    storage_key,
                    "Rejected",
                    uploaded_by_user_id=uploaded_by_user_id,
                    reason_code=result.reason_code,
                    scanner_engine=result.engine,
                )
                quarantine_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"{cls.REPORT_LABEL.capitalize()} scanning is temporarily unavailable",
                )
            if result.verdict != ScanVerdict.CLEAN:
                cls._audit(
                    storage_key,
                    "Rejected",
                    uploaded_by_user_id=uploaded_by_user_id,
                    reason_code=result.reason_code,
                    scanner_engine=result.engine,
                )
                quarantine_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"The {cls.REPORT_LABEL} failed the security scan",
                )

            approved_path = cls.resolve(storage_key)
            os.replace(quarantine_path, approved_path)
            os.chmod(approved_path, 0o600)
            cls._audit(
                storage_key,
                "Approved",
                uploaded_by_user_id=uploaded_by_user_id,
                reason_code=result.reason_code,
                scanner_engine=result.engine,
            )
            return storage_key
        except Exception:
            quarantine_path.unlink(missing_ok=True)
            if approved_path is not None:
                approved_path.unlink(missing_ok=True)
            raise

    @classmethod
    def delete(
        cls,
        storage_key: str | None,
        *,
        reason_code: str = "database_write_failed",
    ) -> bool:
        if not storage_key:
            return True
        try:
            approved_path = cls.resolve(storage_key)
            audit_path = cls._audit_path(storage_key)
            if audit_path.is_symlink():
                raise ValueError("Report audit path cannot be a symbolic link")
            uploader = "unknown"
            if audit_path.is_file():
                payload = json.loads(audit_path.read_text(encoding="utf-8"))
                uploader = str(payload.get("uploaded_by_user_id") or "unknown")
            # Persist the intent before touching the approved file. A database
            # transport error can follow a successful commit, so its outcome
            # must be checked against Mongo before any deletion.
            cls._audit(
                storage_key,
                "CleanupPending",
                uploaded_by_user_id=uploader,
                reason_code=reason_code,
            )
            if reason_code == "database_write_failed":
                return False
            approved_path.unlink(missing_ok=True)
            cls._audit(
                storage_key,
                "Removed",
                uploaded_by_user_id=uploader,
                reason_code=reason_code,
            )
            return True
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
            logger.warning(
                "Report attachment cleanup failed",
                extra={
                    "report_storage_type": cls.REPORT_LABEL,
                    "error_type": type(exc).__name__,
                },
            )
            return False

    @classmethod
    def pending_cleanup_inventory(cls) -> list[tuple[str, datetime]]:
        """List only validated pending intents; never infer orphans from files."""
        pending = []
        for audit_path in cls._quarantine_root().glob("*.pdf.audit.json"):
            try:
                if audit_path.is_symlink() or not audit_path.is_file():
                    continue
                if audit_path.stat().st_size > 256 * 1024:
                    continue
                payload = json.loads(audit_path.read_text(encoding="utf-8"))
                key = payload.get("storage_key")
                events = payload.get("events")
                if (
                    not isinstance(key, str)
                    or not cls.OPAQUE_STORAGE_KEY.fullmatch(key)
                    or audit_path.name != f"{key}.audit.json"
                    or payload.get("state") != "CleanupPending"
                    or not isinstance(events, list)
                    or not events
                    or events[-1].get("state") != "CleanupPending"
                ):
                    continue
                occurred_at = datetime.fromisoformat(events[-1]["occurred_at"])
                if occurred_at.tzinfo is None:
                    continue
                pending.append((key, occurred_at))
            except (OSError, TypeError, ValueError, KeyError, AttributeError):
                logger.warning(
                    "Report cleanup inventory skipped an invalid audit",
                    extra={"report_storage_type": cls.REPORT_LABEL},
                )
        return pending

    @classmethod
    async def reconcile_pending_cleanup(
        cls,
        is_referenced: Callable[[str], Awaitable[bool]],
        *,
        min_age_seconds: int = 24 * 60 * 60,
    ) -> dict[str, int]:
        """Explicit maintenance only: verify Mongo references before retrying."""
        if min_age_seconds < 0:
            raise ValueError("Cleanup grace period cannot be negative")
        counts = {"pending": 0, "deferred": 0, "retained": 0, "removed": 0, "failed": 0}
        now = datetime.now(timezone.utc)
        for key, occurred_at in cls.pending_cleanup_inventory():
            counts["pending"] += 1
            if (now - occurred_at).total_seconds() < min_age_seconds:
                counts["deferred"] += 1
                continue
            try:
                referenced = await asyncio.wait_for(is_referenced(key), timeout=5.0)
                if not isinstance(referenced, bool):
                    raise ValueError("Reference check did not return a boolean")
                if referenced:
                    cls._audit(
                        key,
                        "CleanupRetained",
                        uploaded_by_user_id="system",
                        reason_code="database_reference_present",
                    )
                    counts["retained"] += 1
                elif cls.delete(key, reason_code="reconciled_unreferenced"):
                    counts["removed"] += 1
                else:
                    counts["failed"] += 1
            except Exception:
                logger.warning(
                    "Report cleanup reconciliation failed",
                    extra={"report_storage_type": cls.REPORT_LABEL},
                )
                counts["failed"] += 1
        return counts


class LabReportStorage(ClinicalReportStorage):
    """Laboratory-report quarantine with separate approved and audit roots."""

    STORAGE_DIR_SETTING = "LAB_REPORT_STORAGE_DIR"
    QUARANTINE_DIR_SETTING = "LAB_REPORT_QUARANTINE_DIR"
    MAX_BYTES_SETTING = "LAB_REPORT_MAX_BYTES"
    STORAGE_LABEL = "Laboratory report storage"
    QUARANTINE_LABEL = "Laboratory report quarantine"
    REPORT_LABEL = "laboratory report"
