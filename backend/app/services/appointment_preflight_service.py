"""Pure analysis helpers for the appointment legacy-data preflight.

This module deliberately has no database imports.  Callers provide plain record
dictionaries and optional index metadata, which keeps the analysis testable and
ensures that importing it can never initialize Beanie or create indexes.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ACTIVE_APPOINTMENT_STATUSES = frozenset(
    {"scheduled", "in_progress", "confirmed", "pending_payment"}
)

EXPECTED_APPOINTMENT_INDEXES = {
    "unique_active_doctor_slot_claim": {
        "key": [["slot_claim", 1]],
        "unique": True,
        "partialFilterExpression": {"slot_claim": {"$type": "string"}},
    },
    "unique_home_booking_submission_claim": {
        "key": [["submission_claim", 1]],
        "unique": True,
        "partialFilterExpression": {"submission_claim": {"$type": "string"}},
    },
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _canonical_stored_day(value: datetime) -> datetime:
    """Match the proposed raw-date index migration: UTC-naive midnight."""

    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_time_slot(value: Any) -> time | None:
    if not isinstance(value, str):
        return None
    candidate = " ".join(value.strip().upper().split())
    for pattern in ("%I:%M %p", "%H:%M"):
        try:
            return datetime.strptime(candidate, pattern).time()
        except ValueError:
            continue
    return None


def _utc_start(
    record: dict[str, Any],
    canonical_day: datetime,
    parsed_slot: time,
    default_timezone: str,
) -> tuple[datetime | None, str]:
    stored_start = _parse_datetime(record.get("starts_at"))
    if stored_start is not None:
        return stored_start, "stored_starts_at"

    timezone_name = _text(record.get("clinic_timezone")) or default_timezone
    try:
        clinic_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None, "invalid_clinic_timezone"

    inferred_local = datetime.combine(
        canonical_day.date(), parsed_slot, tzinfo=clinic_zone
    )
    return (
        inferred_local.astimezone(timezone.utc).replace(tzinfo=None),
        "inferred_from_legacy_date_and_slot",
    )


def _record_summary(
    record: dict[str, Any],
    stored_date: datetime | None,
    canonical_day: datetime | None,
) -> dict[str, Any]:
    return {
        "appointment_id": _text(record.get("_id") or record.get("id")),
        "patient_id": _text(record.get("patient_id")),
        "doctor_id": _text(record.get("doctor_id")),
        "status": _text(record.get("status")),
        "time_slot": _text(record.get("time_slot")),
        "stored_appointment_date": stored_date.isoformat() if stored_date else None,
        "canonical_appointment_date": (
            canonical_day.isoformat() if canonical_day else None
        ),
    }


def _conflict_groups(
    grouped: dict[tuple[str, ...], list[dict[str, Any]]],
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    conflicts = []
    for key, records in sorted(grouped.items(), key=lambda item: item[0]):
        if len(records) < 2:
            continue
        conflicts.append(
            {
                **dict(zip(fields, key)),
                "record_count": len(records),
                "records": sorted(
                    records,
                    key=lambda item: item.get("appointment_id") or "",
                ),
            }
        )
    return conflicts


def inspect_appointment_indexes(
    actual_indexes: Iterable[dict[str, Any]] | None,
) -> dict[str, Any]:
    if actual_indexes is None:
        return {
            "checked": False,
            "expected": EXPECTED_APPOINTMENT_INDEXES,
            "actual": [],
            "missing": sorted(EXPECTED_APPOINTMENT_INDEXES),
            "mismatched": [],
        }

    normalized_actual = []
    by_name: dict[str, dict[str, Any]] = {}
    for index in actual_indexes:
        name = _text(index.get("name"))
        key_value = index.get("key", [])
        if hasattr(key_value, "items"):
            key_value = [
                [str(field), direction] for field, direction in key_value.items()
            ]
        else:
            key_value = [[str(field), direction] for field, direction in key_value]
        normalized = {
            "name": name,
            "key": key_value,
            "unique": bool(index.get("unique", False)),
            "partialFilterExpression": index.get("partialFilterExpression"),
        }
        normalized_actual.append(normalized)
        if name:
            by_name[name] = normalized

    missing = sorted(set(EXPECTED_APPOINTMENT_INDEXES) - set(by_name))
    mismatched = []
    for name, expected in EXPECTED_APPOINTMENT_INDEXES.items():
        actual = by_name.get(name)
        if actual is None:
            continue
        differences = {
            field: {"expected": expected[field], "actual": actual.get(field)}
            for field in expected
            if actual.get(field) != expected[field]
        }
        if differences:
            mismatched.append({"name": name, "differences": differences})

    return {
        "checked": True,
        "expected": EXPECTED_APPOINTMENT_INDEXES,
        "actual": sorted(normalized_actual, key=lambda item: item.get("name") or ""),
        "missing": missing,
        "mismatched": mismatched,
    }


def analyze_appointment_records(
    records: Iterable[dict[str, Any]],
    *,
    actual_indexes: Iterable[dict[str, Any]] | None = None,
    default_timezone: str = "Asia/Kolkata",
) -> dict[str, Any]:
    """Analyze legacy appointment records without mutating the input.

    Only identifiers, scheduling fields, and lifecycle status are copied into
    the report. Clinical reasons, symptoms, addresses, payment details, names,
    and contact information are intentionally excluded.
    """

    patient_day_slots: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    doctor_day_slots: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    doctor_starts: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    noncanonical_dates: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    slot_claim_findings: list[dict[str, Any]] = []
    active_record_ids: set[str] = set()
    total_records = 0

    for record in records:
        total_records += 1
        stored_date = _parse_datetime(record.get("appointment_date"))
        canonical_day = _canonical_stored_day(stored_date) if stored_date else None
        summary = _record_summary(record, stored_date, canonical_day)
        appointment_id = summary["appointment_id"] or f"<record-{total_records}>"
        status = (summary["status"] or "").casefold()
        is_active = status in ACTIVE_APPOINTMENT_STATUSES
        if is_active:
            active_record_ids.add(appointment_id)

        validation_errors = []
        if stored_date is None:
            validation_errors.append("missing_or_invalid_appointment_date")
        parsed_slot = _parse_time_slot(record.get("time_slot"))
        if parsed_slot is None:
            validation_errors.append("missing_or_invalid_time_slot")
        if not summary["patient_id"]:
            validation_errors.append("missing_patient_id")
        if not summary["doctor_id"]:
            validation_errors.append("missing_doctor_id")

        if validation_errors:
            invalid_records.append(
                {**summary, "validation_errors": validation_errors}
            )
            continue

        if stored_date != canonical_day:
            noncanonical_dates.append(summary)

        if not is_active:
            continue

        normalized_slot = parsed_slot.strftime("%H:%M")
        day_value = canonical_day.date().isoformat()
        patient_key = (summary["patient_id"], day_value, normalized_slot)
        doctor_key = (summary["doctor_id"], day_value, normalized_slot)
        patient_day_slots[patient_key].append(summary)
        doctor_day_slots[doctor_key].append(summary)

        starts_at, start_source = _utc_start(
            record, canonical_day, parsed_slot, default_timezone
        )
        if starts_at is None:
            invalid_records.append(
                {
                    **summary,
                    "validation_errors": [start_source],
                }
            )
            continue

        start_value = starts_at.isoformat(timespec="minutes") + "Z"
        doctor_starts[(summary["doctor_id"], start_value)].append(summary)
        expected_claim = f"{summary['doctor_id']}:{start_value}"
        stored_claim = _text(record.get("slot_claim"))
        if stored_claim != expected_claim:
            slot_claim_findings.append(
                {
                    **summary,
                    "starts_at": starts_at.isoformat(),
                    "starts_at_source": start_source,
                    "stored_slot_claim": stored_claim,
                    "expected_slot_claim": expected_claim,
                    "finding": (
                        "missing_slot_claim"
                        if stored_claim is None
                        else "mismatched_slot_claim"
                    ),
                }
            )

    patient_conflicts = _conflict_groups(
        patient_day_slots, ("patient_id", "canonical_date", "time_slot_24h")
    )
    doctor_day_conflicts = _conflict_groups(
        doctor_day_slots, ("doctor_id", "canonical_date", "time_slot_24h")
    )
    doctor_start_conflicts = _conflict_groups(
        doctor_starts, ("doctor_id", "starts_at_utc")
    )
    index_report = inspect_appointment_indexes(actual_indexes)

    conflicting_record_ids = {
        record["appointment_id"]
        for group in patient_conflicts + doctor_day_conflicts + doctor_start_conflicts
        for record in group["records"]
        if record.get("appointment_id")
    }
    unique_index_creation_ready = not (
        noncanonical_dates
        or invalid_records
        or patient_conflicts
        or doctor_day_conflicts
        or doctor_start_conflicts
        or slot_claim_findings
    )
    deployed_index_state_ready = (
        not (index_report["missing"] or index_report["mismatched"])
        if index_report["checked"]
        else None
    )
    overall_ready = unique_index_creation_ready and (
        deployed_index_state_ready is not False
    )

    return {
        "schema_version": 1,
        "safety": {
            "database_writes_performed": False,
            "clinical_fields_included": False,
            "analysis_only": True,
        },
        "summary": {
            "total_records": total_records,
            "active_records": len(active_record_ids),
            "noncanonical_date_records": len(noncanonical_dates),
            "invalid_records": len(invalid_records),
            "slot_claim_findings": len(slot_claim_findings),
            "patient_conflict_groups": len(patient_conflicts),
            "doctor_day_conflict_groups": len(doctor_day_conflicts),
            "doctor_start_conflict_groups": len(doctor_start_conflicts),
            "records_in_conflict": len(conflicting_record_ids),
        },
        "readiness": {
            "canonical_date_migration_ready": not (
                invalid_records or patient_conflicts or doctor_day_conflicts
            ),
            "slot_claim_backfill_ready": not (
                invalid_records or doctor_start_conflicts
            ),
            "unique_index_creation_ready": unique_index_creation_ready,
            "deployed_index_state_ready": deployed_index_state_ready,
            "overall_ready": overall_ready,
            "requires_owner_resolution": bool(conflicting_record_ids),
        },
        "affected_records": {
            "noncanonical_dates": sorted(
                noncanonical_dates,
                key=lambda item: item.get("appointment_id") or "",
            ),
            "invalid": sorted(
                invalid_records,
                key=lambda item: item.get("appointment_id") or "",
            ),
            "slot_claims": sorted(
                slot_claim_findings,
                key=lambda item: item.get("appointment_id") or "",
            ),
        },
        "conflict_groups": {
            "patient_canonical_day_slot": patient_conflicts,
            "doctor_canonical_day_slot": doctor_day_conflicts,
            "doctor_start_utc": doctor_start_conflicts,
        },
        "indexes": index_report,
    }
