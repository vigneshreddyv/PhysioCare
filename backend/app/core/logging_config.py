"""
Centralized application logging configuration (Phase 4, Task 20).

WHY THIS EXISTS

    The refund reconciliation driver (Task 18) reports every batch start,
    every per-refund outcome, and every batch summary through
    logger.info(...) on the standard `logging` module. Until Task 20 the
    application never configured logging anywhere: the root logger ran at
    its default WARNING level with no handler, so every INFO observability
    line — the entire point of Task 18 — was silently dropped (verified
    empirically). This module installs ONE root-logger handler at INFO so
    those lines actually reach stderr.

WHAT IT DOES — deliberately little

    - configure_logging() is called ONCE, at `app.main` import time,
      before any request handler or background loop can run.
    - The ROOT logger gets a single StreamHandler (stderr) with a fixed,
      plain formatter: timestamp, level, logger name, message. No request
      data, no headers, no record extras — the message text is the only
      thing ever rendered, and the reconciliation path already pins
      (test-enforced) that only truncated identifiers and allowlisted
      outcome codes ever reach those messages.
    - The level comes from settings.LOG_LEVEL (default INFO); an absent
      or unrecognized value falls back to INFO — never a crash, and
      never a silent downgrade to WARNING.
    - IDEMPOTENT: the installed handler carries an internal marker and is
      never installed twice, so re-imports, `--reload` workers, and test
      collection cannot duplicate log lines.
    - Uvicorn's own loggers (uvicorn / uvicorn.error / uvicorn.access)
      are left exactly as uvicorn configures them; this module never
      touches them. The print()-based request middleware in app.main is
      likewise unchanged (Task 11's allowlisted SAFE_LOG_HEADERS remain
      the request-log boundary).

WHAT IT NEVER DOES

    - Reads exactly ONE setting (LOG_LEVEL); no secret, key, token,
      signature, or payload value is ever referenced, formatted, or
      logged here (pinned by test).
    - Imports nothing from repositories/services/APIs, flips no flag, and
      starts no loop: reconciliation policy (REFUND_RECONCILIATION_ENABLED,
      outcome vocabulary, scheduler cadence, refund states) is untouched —
      pinned by tests/test_logging_config.py.
"""

from __future__ import annotations

import logging
import sys
from typing import IO, Optional

from app.core.config import settings

# Internal marker attribute: proves a handler was installed by THIS
# module, so configure_logging() can stay idempotent without guessing
# from handler types (third-party handlers must never be touched).
_HANDLER_MARKER = "_physiocare_configured_handler"

# Fixed format: no request data, no extras, nothing dict- or payload-
# shaped beyond what the caller already guarantees is safe. The
# reconciliation log contract (Task 18) is enforced at the message level;
# the formatter adds nothing beyond time/level/logger name.
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _resolve_level(raw: object) -> int:
    """Map settings.LOG_LEVEL to a logging level, failing SAFE.

    An absent, empty, or unrecognized value resolves to INFO — the
    observability baseline — never DEBUG, and never a crash.
    """
    if isinstance(raw, str) and raw.strip():
        level = logging.getLevelName(raw.strip().upper())
        if isinstance(level, int):
            return level
    return logging.INFO


def configure_logging(stream: Optional[IO[str]] = None) -> logging.Handler:
    """Install the application's root-logger handler exactly once.

    Installs one StreamHandler on the ROOT logger (stderr unless a stream
    is passed — tests use an in-memory stream to prove real emission) at
    settings.LOG_LEVEL (default INFO), with the fixed plain LOG_FORMAT.
    Returns the installed handler; if this module's handler is already
    installed, returns it unchanged and installs nothing (idempotent).

    This is pure configuration: it reads only settings.LOG_LEVEL and
    mutates nothing else — no settings field, no flag, no background
    loop, no reconciliation state.
    """
    root = logging.getLogger()
    for existing in root.handlers:
        if getattr(existing, _HANDLER_MARKER, False):
            return existing

    handler = logging.StreamHandler(
        stream if stream is not None else sys.stderr
    )
    handler.setFormatter(
        logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    )
    setattr(handler, _HANDLER_MARKER, True)

    root.addHandler(handler)
    root.setLevel(_resolve_level(settings.LOG_LEVEL))
    return handler
