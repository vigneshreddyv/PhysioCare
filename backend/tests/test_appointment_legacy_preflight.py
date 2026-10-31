import json
import os
from pathlib import Path

from app.services.appointment_preflight_service import (
    analyze_appointment_records,
    inspect_appointment_indexes,
)
from scripts.appointment_legacy_preflight import (
    load_offline_records,
    main,
    write_report,
)


def record(
    appointment_id,
    *,
    patient_id="patient-1",
    doctor_id="doctor-1",
    appointment_date="2026-11-10T00:00:00",
    starts_at=None,
    time_slot="10:00 AM",
    status="scheduled",
    slot_claim=None,
):
    return {
        "_id": appointment_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appointment_date": appointment_date,
        "starts_at": starts_at,
        "clinic_timezone": "Asia/Kolkata",
        "time_slot": time_slot,
        "status": status,
        "slot_claim": slot_claim,
        # These sensitive fields must never be copied into the report.
        "reason": "Sensitive clinical reason",
        "symptoms": ["Sensitive symptom"],
        "home_address": "Sensitive address",
    }


def test_reports_noncanonical_dates_and_post_normalization_conflicts():
    records = [
        record("a", appointment_date="2026-11-10T09:12:00"),
        record("b", appointment_date="2026-11-10T15:45:00"),
    ]

    report = analyze_appointment_records(records)

    assert report["summary"]["noncanonical_date_records"] == 2
    assert report["summary"]["patient_conflict_groups"] == 1
    assert report["summary"]["doctor_day_conflict_groups"] == 1
    assert report["summary"]["doctor_start_conflict_groups"] == 1
    assert report["summary"]["records_in_conflict"] == 2
    assert report["readiness"] == {
        "canonical_date_migration_ready": False,
        "slot_claim_backfill_ready": False,
        "unique_index_creation_ready": False,
        "deployed_index_state_ready": None,
        "overall_ready": False,
        "requires_owner_resolution": True,
    }


def test_terminal_records_do_not_create_active_slot_conflicts():
    records = [
        record("a", status="completed"),
        record("b", status="cancelled"),
    ]

    report = analyze_appointment_records(records)

    assert report["summary"]["active_records"] == 0
    assert report["summary"]["patient_conflict_groups"] == 0
    assert report["summary"]["doctor_start_conflict_groups"] == 0


def test_patient_and_doctor_conflicts_are_reported_independently():
    records = [
        record("a", patient_id="p1", doctor_id="d1"),
        record("b", patient_id="p1", doctor_id="d2"),
        record("c", patient_id="p2", doctor_id="d1"),
    ]

    report = analyze_appointment_records(records)

    assert report["summary"]["patient_conflict_groups"] == 1
    assert report["summary"]["doctor_day_conflict_groups"] == 1


def test_valid_active_slot_claim_is_ready_when_index_metadata_matches():
    records = [
        record(
            "a",
            starts_at="2026-11-10T04:30:00",
            slot_claim="doctor-1:2026-11-10T04:30Z",
        )
    ]
    indexes = [
        {
            "name": "unique_active_doctor_slot_claim",
            "key": {"slot_claim": 1},
            "unique": True,
            "partialFilterExpression": {"slot_claim": {"$type": "string"}},
        },
        {
            "name": "unique_home_booking_submission_claim",
            "key": {"submission_claim": 1},
            "unique": True,
            "partialFilterExpression": {"submission_claim": {"$type": "string"}},
        },
    ]

    report = analyze_appointment_records(records, actual_indexes=indexes)

    assert report["summary"]["slot_claim_findings"] == 0
    assert report["readiness"]["unique_index_creation_ready"] is True
    assert report["readiness"]["deployed_index_state_ready"] is True
    assert report["readiness"]["overall_ready"] is True
    assert report["indexes"]["missing"] == []
    assert report["indexes"]["mismatched"] == []


def test_invalid_records_are_fail_closed_and_exclude_clinical_fields():
    report = analyze_appointment_records(
        [record("a", appointment_date="not-a-date", time_slot="not-a-slot")]
    )

    assert report["summary"]["invalid_records"] == 1
    rendered = json.dumps(report)
    assert "Sensitive clinical reason" not in rendered
    assert "Sensitive symptom" not in rendered
    assert "Sensitive address" not in rendered
    assert report["readiness"]["unique_index_creation_ready"] is False


def test_index_inspection_reports_missing_and_mismatched_indexes():
    report = inspect_appointment_indexes(
        [
            {
                "name": "unique_active_doctor_slot_claim",
                "key": {"slot_claim": 1},
                "unique": False,
                "partialFilterExpression": None,
            }
        ]
    )

    assert report["missing"] == ["unique_home_booking_submission_claim"]
    assert report["mismatched"][0]["name"] == "unique_active_doctor_slot_claim"
    assert set(report["mismatched"][0]["differences"]) == {
        "unique",
        "partialFilterExpression",
    }


def test_live_index_drift_blocks_overall_readiness_not_data_readiness():
    records = [
        record(
            "a",
            starts_at="2026-11-10T04:30:00",
            slot_claim="doctor-1:2026-11-10T04:30Z",
        )
    ]

    report = analyze_appointment_records(records, actual_indexes=[])

    assert report["readiness"]["unique_index_creation_ready"] is True
    assert report["readiness"]["deployed_index_state_ready"] is False
    assert report["readiness"]["overall_ready"] is False


def test_active_invalid_record_is_still_counted_as_active():
    report = analyze_appointment_records(
        [record("a", appointment_date="not-a-date")]
    )

    assert report["summary"]["active_records"] == 1


def test_analysis_is_deterministic_for_the_same_snapshot():
    records = [record("a", appointment_date="2026-11-10T09:12:00")]

    assert analyze_appointment_records(records) == analyze_appointment_records(records)


def test_offline_loader_accepts_list_or_records_envelope(tmp_path):
    list_path = tmp_path / "list.json"
    list_path.write_text(json.dumps([record("a")]), encoding="utf-8")
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(
        json.dumps({"records": [record("b")]}), encoding="utf-8"
    )

    assert load_offline_records(list_path)[0]["_id"] == "a"
    assert load_offline_records(envelope_path)[0]["_id"] == "b"


def test_report_file_is_private_and_never_overwritten(tmp_path):
    output = tmp_path / "report.json"
    write_report({"safe": True}, output)

    assert output.read_text(encoding="utf-8").endswith("\n")
    assert os.stat(output).st_mode & 0o777 == 0o600

    try:
        write_report({"safe": False}, output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing reports must never be overwritten")


def test_offline_cli_writes_a_deterministic_private_report(tmp_path):
    input_path = tmp_path / "appointments.json"
    output_path = tmp_path / "report.json"
    input_path.write_text(
        json.dumps(
            [
                record(
                    "a",
                    starts_at="2026-11-10T04:30:00",
                    slot_claim="doctor-1:2026-11-10T04:30Z",
                )
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        ["--input-json", str(input_path), "--output", str(output_path)]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert "generated_at" not in report
    assert report["source"] == {
        "kind": "offline_json",
        "path": str(input_path),
    }
    assert os.stat(output_path).st_mode & 0o777 == 0o600
