# Phase 13 Appointment Migration Plan

Status: **Proposal only — no migration or index operation is authorized**

Prerequisite: an authorized preflight with owner-reviewed conflict decisions

## Objective and invariants

Normalize legacy scheduling fields without losing history, inventing intent, or
weakening atomic slot protection. The following invariants are non-negotiable:

- no appointment is deleted;
- no ambiguous date/time/timezone is guessed;
- no active patient or clinician collision is hidden;
- terminal-state and payment history remains intact;
- a clinician has at most one active claim for a UTC start;
- every write is conditional, idempotent, auditable, and reversible from the
  migration ledger and protected backup;
- index changes are a separate, explicitly approved maintenance action.

## Preconditions and stop conditions

Before implementation or execution:

1. Complete the authorized read-only preflight and archive its private report.
2. Obtain owner approval for the exact target, maintenance window, timezone,
   active-status vocabulary, and every duplicate-resolution policy.
3. Produce and restore-test a protected database backup/snapshot.
4. Freeze appointment writes or place the API in a scheduling-maintenance mode;
   background workers that can change appointment/payment state must be handled
   explicitly rather than assumed idle.
5. Capture collection counts, active-status counts, current index definitions,
   and a stable source fingerprint without clinical/contact fields.
6. Stop if preflight input changes, new conflicts appear, the backup is not
   restorable, or the operator lacks a rollback window.

## Proposed transformation

For each preflight-approved record:

1. Parse `appointment_date` without changing it. Derive the canonical UTC-naive
   midnight for the owner-approved clinic calendar date.
2. Normalize `time_slot` to one accepted representation and derive `starts_at`
   by combining that date/time with the approved IANA clinic zone, then convert
   to UTC-naive storage.
3. For an active record, derive
   `<doctor_id>:<starts_at-to-minute>Z` as `slot_claim`. Terminal records must
   not retain an active claim.
4. Compare every original field to the preflight snapshot in the update filter.
   If any value changed, update zero records and quarantine it for a new review.
5. Write the original values, proposed values, record ID, policy decision ID,
   operator/run ID, and result to a protected migration ledger. Do not copy
   reason, symptoms, contact, address, or payment payloads into the ledger.
6. A rerun must treat an already-canonical matching record as a no-op and must
   never append a second semantic migration event.

## Conflict policy options

No default winner is proposed.

| Strategy | When it may be used | History treatment | Main risk |
|---|---|---|---|
| Owner-verified authoritative booking | Clinic has reliable external confirmation | Keep both records; cancel the duplicate with linked audit reason | Incorrect manual selection |
| Confirmed reschedule | Patient/clinic agrees to another open slot | Preserve original record and cancellation/reschedule link; create/claim replacement atomically | Communication or slot race |
| Quarantine | Intent, timezone, status, ownership, or payment is unclear | Leave both unchanged and exclude from automatic normalization | Continued manual scheduling restriction |
| Merge administrative duplicate | Strong evidence proves same booking and all state agrees | Keep both immutable source references; one becomes terminal and links to authoritative ID | Accidental loss of divergent history |

Creation time, object-ID order, current UI ordering, payment presence alone, or
“first record wins” are not sufficient policy.

## Cancellation and rescheduling semantics

- Existing terminal appointments remain terminal; normalization must not reopen
  them or recreate their slot claims.
- Active duplicate resolution uses the existing conditional cancellation path
  where possible so `cancelled_at` and claim release remain consistent.
- The current product has cancellation but no first-class reschedule endpoint.
  A migration reschedule must therefore be represented as an explicitly linked
  cancellation plus a newly validated booking, not as an undocumented in-place
  date rewrite.
- A replacement booking must pass current horizon, published availability,
  patient/doctor conflict, and atomic slot-claim checks.
- A captured payment on a cancelled/conflicting appointment must remain visible
  as `reconciliation_required`; migration must not refund, transfer, or mark it
  paid automatically.

## Concurrency plan

Preferred policy is a short scheduling-write maintenance window. If zero
downtime is required, implementation needs an additional owner-approved design
with source-version compare-and-set and a migration barrier; it must not rely on
best-effort timing.

Within the window:

1. Keep read access available where operationally safe.
2. Disable new appointment/home-visit booking and scheduling changes.
3. Allow payment reconciliation only under an explicit coordinated policy,
   because cancellation/capture races can modify the same appointments.
4. Apply conditional record changes in bounded batches, aborting the batch on a
   duplicate-key or source mismatch.
5. Rerun the preflight before reopening writes.

## Index verification and rollout

Index work is a later approval gate:

1. Require zero invalid records, conflicts, and slot-claim findings.
2. Compare live definitions by name, key order, uniqueness, and partial filter.
3. If an index is missing/mismatched, create or repair it only in an approved
   maintenance step. Do not rely on application startup/Beanie initialization
   as the migration mechanism.
4. Verify the two appointment indexes defined in the model and retain the
   `slot_claim` design; raw `appointment_date` uniqueness cannot represent a
   clinician’s actual UTC slot across clinic/home modes.
5. Run connected race tests against an isolated MongoDB before protected rollout.

## Verification gates

- preflight readiness flags all true, including live index state;
- before/after record counts reconcile exactly;
- every changed record has one ledger entry and every ledger entry has a result;
- no active record lacks/mismatches its claim;
- no patient/day/time or doctor/UTC-start conflict remains;
- booking, home-visit booking, cancellation, clinician reassignment, payment
  reconciliation, and appointment-list regressions pass against isolated Mongo;
- a second migration run reports zero writes;
- scheduling reopens only after owner sign-off.

## Rollback

Rollback is not “delete the new fields.” It must:

1. keep scheduling writes frozen;
2. restore the verified snapshot if any batch has an unbounded or systemic
   failure, or conditionally restore each changed record from the protected
   ledger when the failure is isolated and no later write exists;
3. restore prior index definitions only through a separately approved operation;
4. rerun the read-only preflight and before/after reconciliation;
5. preserve both forward and rollback ledgers for audit;
6. reconcile payment/cancellation changes that occurred under the approved
   worker policy before reopening writes.

## Decisions required

- exact historical timezone and active-status policy;
- duplicate policy per conflict class (and per record when ambiguous);
- maintenance-window versus versioned online migration;
- backup/restore owner and recovery objectives;
- treatment of payment-bearing conflicts;
- migration ledger retention/access policy;
- explicit approval to implement, rehearse, and later execute the migration;
- separate approval for index creation or repair.
