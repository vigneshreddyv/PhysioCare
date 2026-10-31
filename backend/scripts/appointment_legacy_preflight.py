#!/usr/bin/env python3
"""Read-only appointment legacy-data preflight.

MongoDB access is opt-in and uses only ``find`` and ``list_indexes``.  This
script never imports ``app.database`` or calls Beanie initialization, because
Beanie initialization may create indexes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.appointment_preflight_service import (  # noqa: E402
    analyze_appointment_records,
)


MONGO_PROJECTION = {
    "_id": 1,
    "patient_id": 1,
    "doctor_id": 1,
    "appointment_date": 1,
    "starts_at": 1,
    "clinic_timezone": 1,
    "time_slot": 1,
    "status": 1,
    "slot_claim": 1,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Report noncanonical appointment dates, post-normalization slot "
            "conflicts, slot-claim gaps, and index metadata without changing data."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--input-json",
        type=Path,
        help="Analyze an offline JSON list or an object containing a records list.",
    )
    source.add_argument(
        "--mongo",
        action="store_true",
        help=(
            "Explicitly opt in to reading the configured MongoDB "
            "appointments collection."
        ),
    )
    parser.add_argument(
        "--expect-database",
        help="Required with --mongo; must exactly match configured DATABASE_NAME.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Report path. Required with --mongo. Files are created exclusively "
            "with owner-only permissions and are never overwritten."
        ),
    )
    parser.add_argument(
        "--default-timezone",
        default="Asia/Kolkata",
        help="Timezone used only when a legacy record lacks clinic_timezone.",
    )
    return parser


def validate_arguments(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    if not args.output:
        parser.error("--output is required; reports cannot be printed to stdout")
    if args.mongo and not args.expect_database:
        parser.error("--mongo requires --expect-database")
    if args.input_json and args.expect_database:
        parser.error("--expect-database is valid only with --mongo")


def _json_default(value: Any) -> str:
    return str(value)


def write_report(report: dict[str, Any], output: Path | None) -> None:
    rendered = (
        json.dumps(report, indent=2, sort_keys=True, default=_json_default) + "\n"
    )
    if output is None:
        sys.stdout.write(rendered)
        return

    output = output.expanduser().resolve()
    if not output.parent.is_dir():
        raise FileNotFoundError("Report parent directory does not exist.")
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    except Exception:
        try:
            output.unlink(missing_ok=True)
        finally:
            raise


def load_offline_records(path: Path) -> list[dict[str, Any]]:
    with path.expanduser().open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    records = payload.get("records") if isinstance(payload, dict) else payload
    valid_records = isinstance(records, list) and all(
        isinstance(item, dict) for item in records
    )
    if not valid_records:
        raise ValueError(
            "Input JSON must be a list of record objects or {'records': [...]}."
        )
    return records


async def load_mongo_snapshot(
    expected_database: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    # Import configuration only after explicit --mongo validation.  No URL or
    # credential is included in output or error messages from this script.
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.core.config import settings

    if settings.DATABASE_NAME != expected_database:
        raise ValueError(
            "Configured database name does not match --expect-database; "
            "refusing to connect."
        )

    client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        tz_aware=True,
        serverSelectionTimeoutMS=5000,
        appname="physiocare-appointment-readonly-preflight",
    )
    try:
        collection = client[settings.DATABASE_NAME]["appointments"]
        records = await collection.find({}, MONGO_PROJECTION).to_list(length=None)
        indexes = [index async for index in collection.list_indexes()]
        return records, indexes, settings.DATABASE_NAME
    finally:
        client.close()


async def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.mongo:
        records, indexes, database_name = await load_mongo_snapshot(
            args.expect_database
        )
        source = {
            "kind": "mongodb",
            "database": database_name,
            "collection": "appointments",
        }
    else:
        records = load_offline_records(args.input_json)
        indexes = None
        source = {"kind": "offline_json", "path": str(args.input_json)}

    report = analyze_appointment_records(
        records,
        actual_indexes=indexes,
        default_timezone=args.default_timezone,
    )
    report["source"] = source
    exit_code = 0 if report["readiness"]["overall_ready"] else 2
    return report, exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_arguments(args, parser)
    try:
        report, exit_code = asyncio.run(run(args))
        write_report(report, args.output)
        return exit_code
    except Exception as exc:
        # Never include settings or connection strings in diagnostics.
        if args.mongo:
            print(
                f"Preflight failed: {type(exc).__name__}; "
                "connection details suppressed.",
                file=sys.stderr,
            )
        else:
            print(f"Preflight failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
