import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


class ClinicalReportStorage:
    CHUNK_SIZE = 64 * 1024

    @staticmethod
    def _root() -> Path:
        configured = Path(settings.CLINICAL_REPORT_STORAGE_DIR).expanduser()
        if configured.is_symlink():
            raise RuntimeError("Clinical report storage cannot be a symbolic link")
        root = configured.resolve()
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        return root

    @staticmethod
    def resolve(storage_key: str) -> Path:
        key_path = Path(storage_key)
        if (
            key_path.name != storage_key
            or key_path.suffix.lower() != ".pdf"
        ):
            raise ValueError("Invalid clinical report storage key")
        root = ClinicalReportStorage._root()
        path = root / storage_key
        if path.is_symlink() or path.resolve().parent != root:
            raise ValueError("Invalid clinical report storage path")
        return path

    @staticmethod
    async def store_pdf(upload: UploadFile) -> str:
        content_type = (upload.content_type or "").split(";", 1)[0].lower()
        if content_type != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only PDF clinical report attachments are accepted",
            )
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Clinical report attachments must use a .pdf filename",
            )
        if upload.size is not None and upload.size > settings.CLINICAL_REPORT_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The clinical report attachment is larger than the configured limit",
            )

        storage_key = f"{uuid4().hex}.pdf"
        path = ClinicalReportStorage.resolve(storage_key)
        temporary_path = path.with_name(f".{storage_key}.part")
        descriptor = os.open(
            temporary_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        size = 0
        first_chunk = True
        try:
            with os.fdopen(descriptor, "wb") as handle:
                while chunk := await upload.read(ClinicalReportStorage.CHUNK_SIZE):
                    if first_chunk:
                        first_chunk = False
                        if not chunk.startswith(b"%PDF-"):
                            raise HTTPException(
                                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail="The clinical report attachment is not a valid PDF",
                            )
                    size += len(chunk)
                    if size > settings.CLINICAL_REPORT_MAX_BYTES:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=(
                                "The clinical report attachment is larger than "
                                "the configured limit"
                            ),
                        )
                    handle.write(chunk)
                if size == 0:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="The clinical report attachment is empty",
                    )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            os.chmod(path, 0o600)
            return storage_key
        except Exception:
            temporary_path.unlink(missing_ok=True)
            path.unlink(missing_ok=True)
            raise

    @staticmethod
    def delete(storage_key: str | None) -> None:
        if not storage_key:
            return
        try:
            ClinicalReportStorage.resolve(storage_key).unlink(missing_ok=True)
        except (OSError, RuntimeError, ValueError):
            pass
