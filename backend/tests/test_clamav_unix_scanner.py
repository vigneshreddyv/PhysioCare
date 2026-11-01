import asyncio
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.core.config import settings
from app.services.clinical_report_storage import ClinicalReportStorage, LabReportStorage
from app.services.pdf_malware_scanner import ClamAvUnixScanner, ScanVerdict


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "verdict", "reason"),
    [
        (b"stream: OK", ScanVerdict.CLEAN, "scan_clean"),
        (b"stream: Synthetic.Test FOUND", ScanVerdict.MALICIOUS, "malware_detected"),
        (b"stream: internal path ERROR", ScanVerdict.ERROR, "scanner_error"),
        (b"unexpected reply", ScanVerdict.ERROR, "scanner_error"),
    ],
)
async def test_unix_scanner_streams_file_and_maps_only_safe_verdicts(tmp_path, reply, verdict, reason):
    contents = b"%PDF-1.4\nfictional content\n%%EOF\n"
    sample = tmp_path / "fictional.pdf"
    sample.write_bytes(contents)
    received = bytearray()

    async def respond(reader, writer):
        assert await reader.readexactly(10) == b"zINSTREAM\0"
        while True:
            size = int.from_bytes(await reader.readexactly(4), "big")
            if size == 0:
                break
            received.extend(await reader.readexactly(size))
        writer.write(reply + b"\0")
        await writer.drain()
        writer.close()

    with TemporaryDirectory(prefix="physiocare-clamav-test-") as directory:
        socket_path = str(Path(directory) / "clamd.sock")
        server = await asyncio.start_unix_server(respond, path=socket_path)
        try:
            result = await ClamAvUnixScanner(socket_path).scan(sample)
        finally:
            server.close()
            await server.wait_closed()

    assert received == contents
    assert result.verdict == verdict
    assert result.engine == "clamav"
    assert result.reason_code == reason


@pytest.mark.asyncio
async def test_unix_scanner_fails_closed_when_socket_is_unavailable(tmp_path):
    sample = tmp_path / "fictional.pdf"
    sample.write_bytes(b"%PDF-1.4\n%%EOF\n")
    result = await ClamAvUnixScanner(str(tmp_path / "missing.sock")).scan(sample)
    assert result.verdict == ScanVerdict.ERROR
    assert result.reason_code == "scanner_error"
    assert await ClamAvUnixScanner(str(tmp_path / "missing.sock")).ready() is False


@pytest.mark.asyncio
async def test_unix_scanner_requires_daemon_ping_for_readiness():
    async def respond(reader, writer):
        assert await reader.readexactly(6) == b"zPING\0"
        writer.write(b"PONG\0")
        await writer.drain()
        writer.close()

    with TemporaryDirectory(prefix="physiocare-clamav-test-") as directory:
        socket_path = str(Path(directory) / "clamd.sock")
        server = await asyncio.start_unix_server(respond, path=socket_path)
        try:
            assert await ClamAvUnixScanner(socket_path).ready() is True
        finally:
            server.close()
            await server.wait_closed()


@pytest.mark.asyncio
async def test_unix_scanner_fails_closed_on_daemon_disconnect(tmp_path):
    sample = tmp_path / "fictional.pdf"
    sample.write_bytes(b"%PDF-1.4\n%%EOF\n")

    async def disconnect(_reader, writer):
        writer.close()

    with TemporaryDirectory(prefix="physiocare-clamav-test-") as directory:
        socket_path = str(Path(directory) / "clamd.sock")
        server = await asyncio.start_unix_server(disconnect, path=socket_path)
        try:
            result = await ClamAvUnixScanner(socket_path).scan(sample)
        finally:
            server.close()
            await server.wait_closed()
    assert result.verdict == ScanVerdict.ERROR


@pytest.mark.asyncio
async def test_unix_scanner_timeout_is_bounded_by_storage_policy(tmp_path):
    sample = tmp_path / "fictional.pdf"
    sample.write_bytes(b"%PDF-1.4\n%%EOF\n")

    async def hang(reader, writer):
        try:
            await reader.read()
        finally:
            writer.close()

    with TemporaryDirectory(prefix="physiocare-clamav-test-") as directory:
        socket_path = str(Path(directory) / "clamd.sock")
        server = await asyncio.start_unix_server(hang, path=socket_path)
        try:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ClamAvUnixScanner(socket_path).scan(sample), 0.05)
        finally:
            server.close()
            await server.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_class", [ClinicalReportStorage, LabReportStorage])
@pytest.mark.parametrize("reply,expected_status", [(b"stream: OK", None), (b"stream: Inert.Test FOUND", 422)])
async def test_both_upload_paths_use_private_clamav_verdict(
    monkeypatch, tmp_path, storage_class, reply, expected_status
):
    approved = tmp_path / "approved"
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, storage_class.STORAGE_DIR_SETTING, str(approved))
    monkeypatch.setattr(settings, storage_class.QUARANTINE_DIR_SETTING, str(quarantine))
    pdf = b"%PDF-1.4\nfictional document\n%%EOF\n"

    async def respond(reader, writer):
        assert await reader.readexactly(10) == b"zINSTREAM\0"
        while size := int.from_bytes(await reader.readexactly(4), "big"):
            await reader.readexactly(size)
        writer.write(reply + b"\0")
        await writer.drain()
        writer.close()

    with TemporaryDirectory(prefix="physiocare-clamav-test-") as directory:
        socket_path = str(Path(directory) / "clamd.sock")
        server = await asyncio.start_unix_server(respond, path=socket_path)
        monkeypatch.setattr(storage_class, "scanner", ClamAvUnixScanner(socket_path))
        upload = UploadFile(
            BytesIO(pdf), size=len(pdf), filename="fictional.pdf",
            headers=Headers({"content-type": "application/pdf"}),
        )
        try:
            if expected_status:
                with pytest.raises(HTTPException) as error:
                    await storage_class.store_pdf(upload, uploaded_by_user_id="fictional-user")
                assert error.value.status_code == expected_status
                assert list(approved.glob("*.pdf")) == []
            else:
                key = await storage_class.store_pdf(upload, uploaded_by_user_id="fictional-user")
                assert storage_class.resolve(key).read_bytes() == pdf
        finally:
            server.close()
            await server.wait_closed()
    assert list(quarantine.glob("*.pdf")) == []
