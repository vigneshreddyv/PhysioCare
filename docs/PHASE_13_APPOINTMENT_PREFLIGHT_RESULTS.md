# Phase 13 Appointment Legacy-Data Preflight Results

Assessment date: 2026-10-31

Execution status: **NOT EXECUTED against any database — authorization required**

## Result boundary

The implementation and its synthetic tests were inspected. No MongoDB client
was opened, no collection was read, and no protected environment was selected.
The requested live counts therefore do not exist yet and must not be inferred
from unit tests.

| Required result | Phase 13 value |
|---|---|
| Total records inspected | Not available — protected read not authorized |
| Noncanonical dates found | Not available — protected read not authorized |
| Duplicate groups found | Not available — protected read not authorized |
| Malformed records found | Not available — protected read not authorized |
| Ambiguous timezone cases | Not available — protected read not authorized |
| Live index-readiness | Not verified — `list_indexes` not authorized |
| Database writes | 0 |
| Index changes | 0 |

The focused synthetic suite passes 12 cases and the full backend suite passes
346 tests. That validates analyzer behavior; it is not a legacy-data result.

## Representation and canonicalization

- New appointment requests accept a calendar `date` and a normalized time slot.
- `app.core.appointment_time.clinic_start_to_utc_naive` combines the clinic date
  and local time in `CLINIC_TIMEZONE`, then stores a UTC-naive `starts_at`.
- `appointment_date` is stored as UTC-naive midnight for its calendar day.
- `slot_claim` is `<doctor_id>:<UTC-start-to-minute>Z`; it is the concurrency
  claim shared by clinic and confirmed home-visit appointments.
- The legacy resolver accepts `starts_at` when present. Without it, it only
  infers a clinic date when the legacy timestamp is an unambiguous midnight
  representation; otherwise it fails closed.
- The preflight recognizes `scheduled`, `in_progress`, `confirmed`, and
  `pending_payment` as active legacy vocabularies. Current application lifecycle
  writes primarily use `scheduled` and `in_progress`; the broader set prevents
  historical active records from being ignored.

## Indexes under review

`Appointment.Settings` defines:

1. `unique_active_doctor_slot_claim`: unique `slot_claim`, partial on string
   values.
2. `unique_home_booking_submission_claim`: unique `submission_claim`, partial on
   string values.

Despite its historical name, the first index applies to every record with a
string claim. Terminal transitions unset `slot_claim`, releasing capacity.

## Read-only implementation assessment

The inspected path is `backend/scripts/appointment_legacy_preflight.py` plus
the pure analyzer in `backend/app/services/appointment_preflight_service.py`.

- Offline mode reads a JSON file only.
- Mongo mode is unavailable unless `--mongo`, `--expect-database`, and a new
  `--output` path are supplied.
- The configured database name must exactly equal `--expect-database` before a
  connection is attempted.
- The only Mongo operations in the script are `appointments.find` with a narrow
  scheduling projection and `appointments.list_indexes`.
- It does not import `app.database`, initialize Beanie, update/delete data, run
  migrations, or create indexes.
- Reports are created with `0600`, use exclusive creation, and are never
  overwritten.
- Names, contact information, clinical reasons/symptoms, addresses, and payment
  fields are not projected or emitted.

The exact target is the configured `DATABASE_NAME` and its `appointments`
collection. Index metadata is read from that same collection. A database-name
match is a guard, not proof that a host is safe; authorization, a read-only
credential, host allow-listing, and an operator-reviewed environment remain
mandatory.

## Findings the authorized report will contain

The deterministic JSON report contains:

- summary counts for total/active records, noncanonical dates, invalid records,
  slot-claim gaps, three conflict-group types, and records in conflict;
- affected-record scheduling summaries using internal IDs only;
- patient/day/time, doctor/day/time, and doctor/UTC-start collision groups;
- missing or mismatched slot claims;
- expected, actual, missing, and mismatched index metadata;
- readiness flags for date migration, claim backfill, unique index creation,
  deployed index state, and manual owner resolution.

Invalid timezone names appear as `invalid_clinic_timezone` in the invalid-record
list. Records with no `clinic_timezone` use the explicitly supplied default,
which must match the owner-approved clinic timezone; the current default is
`Asia/Kolkata` and is not itself proof of historical intent.

## Authorized execution plan

No command below is authorized by this document alone.

1. Owner identifies the exact non-production/protected target and confirms the
   authorized database name and clinic timezone.
2. Operator creates or selects a Mongo account limited to the built-in `read`
   role for that database and verifies there is no inherited write privilege.
3. Operator verifies the resolved host, database, and environment out of band;
   no URI or credential is copied into chat, logs, or the report.
4. Use a private, pre-existing output directory with restricted access. Choose
   a new filename because the script refuses overwrite.
5. From `backend/`, run:

   ```text
   python scripts/appointment_legacy_preflight.py \
     --mongo \
     --expect-database <AUTHORIZED_DATABASE_NAME> \
     --default-timezone <OWNER_APPROVED_IANA_ZONE> \
     --output <PRIVATE_NEW_REPORT_PATH>
   ```

6. Record exit code and only the sanitized aggregate counts in this document.
   Keep the identifier-bearing report outside Git and chat.
7. Confirm database audit logs show only `find` and `listIndexes`; stop on any
   target mismatch, privilege mismatch, or unexpected operation.
8. Have the clinic owner review every conflict group before choosing a policy.

## Duplicate-resolution options (not selected)

- **Preserve one, cancel the other with an audit reason:** suitable only when
  the clinic can verify which booking is authoritative; never infer by creation
  order alone.
- **Preserve both but reschedule one:** requires patient/clinic confirmation, an
  available replacement slot, and explicit history linking old and new times.
- **Quarantine both from automated migration:** safest for ambiguous ownership,
  timezone, or lifecycle state; scheduling remains blocked until manual review.
- **Treat a proven duplicate as a linked duplicate record:** retain both source
  records for audit, mark the non-authoritative record terminal, and store an
  owner-approved linkage/reason in the future migration ledger.

No option may delete history silently, create a claim over an occupied slot, or
mark a payment state without separate provider evidence.

## Current conclusion

The preflight design is read-only and suitable for a separately authorized run
with operational safeguards. **Appointment legacy-data readiness remains Not
verified**, and migration/index work is blocked until the report exists and the
owner selects a conflict policy.
