# Appointment Legacy-Data Preflight

This preflight reports scheduling data that must be resolved before any legacy
appointment normalization, slot-claim backfill, or new unique-index rollout.
It performs no database writes and contains no migration operation.

## Safety boundary

- MongoDB mode is disabled unless `--mongo` is supplied explicitly.
- `--mongo` also requires the expected database name and a new output path.
- The configured database name must exactly match the expected name before a
  connection is attempted.
- MongoDB access uses only `find` and `list_indexes` against `appointments`.
- The script does not import `app.database` and does not initialize Beanie,
  because Beanie initialization may create indexes.
- Use a MongoDB account with the built-in `read` role only.
- Reports are created with owner-only permissions and are never overwritten.
- The same input snapshot produces the same report content; no run timestamp is
  embedded in the report.
- Reports exclude names, contact details, reasons, symptoms, addresses, and
  payment data. They do contain internal record/profile identifiers and must be
  handled as sensitive operational data.

Do not paste connection strings, credentials, or generated reports into chat.

## Offline rehearsal

From `backend/`, analyze a synthetic JSON fixture without connecting to MongoDB:

```bash
python scripts/appointment_legacy_preflight.py \
  --input-json /path/to/synthetic-appointments.json \
  --output /path/to/new-preflight-report.json
```

The input may be a JSON list of record objects or `{ "records": [...] }`.

## Explicit MongoDB preflight

This command is for a separately authorized read-only run:

```bash
python scripts/appointment_legacy_preflight.py \
  --mongo \
  --expect-database physiocare \
  --output /private/authorized/location/appointment-preflight.json
```

The script reads `MONGODB_URL` and `DATABASE_NAME` from the existing backend
configuration. It never prints the connection string.

Exit codes:

- `0`: no blocking data findings and, in MongoDB mode, matching live indexes.
- `2`: report created, but migration/index readiness is blocked by findings.
- `1`: configuration, connection, input, or output error.

## Findings

The report identifies:

- appointment dates that are not stored at canonical midnight;
- missing or invalid dates, identifiers, time slots, or clinic timezones;
- active patient duplicates after canonical day/time normalization;
- active doctor duplicates after canonical day/time normalization;
- active doctor collisions at the resolved UTC start time;
- missing or mismatched active `slot_claim` values;
- missing or mismatched appointment index definitions.

`unique_index_creation_ready` describes the data only. In MongoDB mode,
`deployed_index_state_ready` separately verifies the live definitions and
`overall_ready` requires both checks. Offline mode reports
`deployed_index_state_ready` as `null` because no live metadata was read.

Active status recognition covers both branch vocabularies: `scheduled`,
`in_progress`, `confirmed`, and `pending_payment`. Terminal records remain in
the noncanonical-date report but do not block a slot through active conflicts.

## Separately approved migration design

No migration code is included in this change. A future migration must be
reviewed and approved after the preflight report is available.

1. Freeze the report input boundary or take a consistent backup/snapshot.
2. Resolve every patient or doctor conflict through an explicit owner-approved
   decision. Never select a winner based only on insertion order.
3. Record the disposition of every conflicting appointment. Do not delete or
   overwrite any appointment silently.
4. Normalize only records whose original values still match the preflight
   report, using conditional updates so concurrent changes fail closed.
5. Backfill `starts_at` and `slot_claim` only where the clinic-local time is
   unambiguous. Quarantine ambiguous records for manual resolution.
6. Make each operation idempotent: canonical records are no-ops, and a rerun
   produces zero additional changes.
7. Rerun this preflight and require all readiness flags to be true.
8. Compare live index definitions with the expected definitions, then create or
   repair indexes only in a separately approved maintenance step.
9. Run real MongoDB race tests and connected booking/cancellation regression
   tests before reopening scheduling writes.

The integration branch should retain the unique `slot_claim` design rather than
blindly adopting uniqueness on raw `appointment_date`: `slot_claim` represents
the actual clinician UTC start and works across clinic and home-visit modes.
