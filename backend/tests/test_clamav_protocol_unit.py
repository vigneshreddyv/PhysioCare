"""Socket-free unit contracts for the ClamAV Unix adapter protocol.

The Unix-socket integration tests remain in ``test_clamav_unix_scanner.py``.
These tests do not replace or weaken that coverage; they exercise framing and
verdict parsing when the sandbox cannot bind an AF_UNIX server socket.
"""

import asyncio

import pytest

from app.services.pdf_malware_scanner import ClamAvUnixScanner, ScanVerdict


class MemoryReader:
    def __init__(self, reply: bytes):
        self.reply = reply

    async def readuntil(self, separator: bytes) -> bytes:
        assert separator == b"\0"
        return self.reply + separator


class MemoryWriter:
    def __init__(self):
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, value: bytes) -> None:
        self.writes.append(value)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "verdict", "reason"),
    [
        (b"stream: OK", ScanVerdict.CLEAN, "scan_clean"),
        (b"stream: Inert.Test FOUND", ScanVerdict.MALICIOUS, "malware_detected"),
        (b"stream: internal ERROR", ScanVerdict.ERROR, "scanner_error"),
        (b"unexpected reply", ScanVerdict.ERROR, "scanner_error"),
    ],
)
async def test_clamav_instream_framing_and_verdicts_without_socket(
    monkeypatch, tmp_path, reply, verdict, reason,
):
    contents = b"%PDF-1.4\n" + b"x" * (ClamAvUnixScanner.CHUNK_SIZE + 7) + b"\n%%EOF\n"
    sample = tmp_path / "fictional.pdf"
    sample.write_bytes(contents)
    reader = MemoryReader(reply)
    writer = MemoryWriter()

    async def open_connection(path, *, limit):
        assert path == "/private/clamd.sock"
        assert limit == 1024
        return reader, writer

    monkeypatch.setattr(asyncio, "open_unix_connection", open_connection)
    result = await ClamAvUnixScanner("/private/clamd.sock").scan(sample)

    assert writer.writes[0] == b"zINSTREAM\0"
    assert writer.writes[-1] == b"\0\0\0\0"
    frames = writer.writes[1:-1]
    assert b"".join(frame[4:] for frame in frames) == contents
    assert all(int.from_bytes(frame[:4], "big") == len(frame[4:]) for frame in frames)
    assert all(len(frame[4:]) <= ClamAvUnixScanner.CHUNK_SIZE for frame in frames)
    assert writer.closed is True
    assert result.verdict == verdict
    assert result.engine == "clamav"
    assert result.reason_code == reason


@pytest.mark.asyncio
@pytest.mark.parametrize(("reply", "ready"), [(b"PONG", True), (b"unexpected", False)])
async def test_clamav_ping_readiness_without_socket(monkeypatch, reply, ready):
    reader = MemoryReader(reply)
    writer = MemoryWriter()

    async def open_connection(_path, *, limit):
        assert limit == 1024
        return reader, writer

    monkeypatch.setattr(asyncio, "open_unix_connection", open_connection)

    assert await ClamAvUnixScanner("/private/clamd.sock").ready() is ready
    assert writer.writes == [b"zPING\0"]
    assert writer.closed is True


@pytest.mark.asyncio
async def test_clamav_transport_failure_remains_fail_closed_without_socket(monkeypatch, tmp_path):
    sample = tmp_path / "fictional.pdf"
    sample.write_bytes(b"%PDF-1.4\n%%EOF\n")

    async def fail_connection(_path, *, limit):
        assert limit == 1024
        raise OSError("synthetic unavailable transport")

    monkeypatch.setattr(asyncio, "open_unix_connection", fail_connection)
    scanner = ClamAvUnixScanner("/private/clamd.sock")

    assert await scanner.ready() is False
    result = await scanner.scan(sample)
    assert result.verdict == ScanVerdict.ERROR
    assert result.reason_code == "scanner_error"
