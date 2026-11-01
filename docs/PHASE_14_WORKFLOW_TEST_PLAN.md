# Phase 14 Connected Staging Workflow Test Plan

Assessment date: 2026-10-31

Execution status: **Not executed — isolated staging has not been approved/provisioned**

## Common controls and evidence

Use only fictional role-separated accounts and the dedicated staging database,
storage and Test Mode provider. For every case record route/API, fictional record
IDs, expected/actual status, redacted log correlation, before/after state and
cleanup disposition. Never capture credentials, tokens, signatures, health
details, addresses, PDF content, card data or unredacted database documents.

Run the following cross-cutting negative matrix for every direct object:
assigned/owner, unassigned/other owner, wrong role, unauthenticated, malformed ID,
nonexistent ID, stale revision and concurrent request. Missing and out-of-scope
clinician resources must be externally indistinguishable.

## Patient journeys

| Journey | Connected staging cases | Pass condition |
|---|---|---|
| Registration | New and existing fictional email, invalid fields, burst/concurrent requests | Same accepted body for new/existing; 422 remains useful; abuse receives generic 429; exactly one account/profile |
| Login/session | Failure burst, valid login after failures, expiry, refresh rotation/replay, logout, proxy headers | Limits shared across instances; valid session cookies/CSRF; replay revokes; spoofed forwarding ignored |
| Profile | Read/edit/reload; invalid and cross-patient attempts | Only own supported fields change |
| Doctor discovery | Public/patient search, empty/error, selection handoff | Public-safe fields only |
| Booking/cancellation | Published slot, stale/duplicate/concurrent booking, own/other cancellation, payment race | One atomic claim; canonical date/start; idempotent safe cancellation |
| Rescheduling | No first-class implementation | Record as blocked; do not simulate with undocumented field edits |
| Care plan/exercises | View assigned plan, record progress, direct foreign IDs | Own clinical content only; foreign/missing indistinguishable |
| Laboratory | Demo request/idempotent retry/withdraw/released report | Truthful coordination state; no implied price/confirmation; role-scoped release |
| Payment | Deferred until separate Test Mode authorization | Follow Phase 13 payment matrix; never live payment/refund |
| Clinical reports | Clean, malformed, malicious-test, scanner unavailable, owner/foreign download | No pre-approval access; only clean promotion; rejected/unavailable inaccessible; owner access only |

## Clinician journeys

| Journey | Connected staging cases | Pass condition |
|---|---|---|
| Login | Same session/throttle matrix on fictional clinician | No role bypass or address-header bypass |
| Assignment/patient history | Assigned, unassigned, nonexistent and malformed patient IDs | Assigned succeeds; all unavailable cases return the same 404 contract |
| Appointments | Own schedule/status; another clinician record; concurrent admin update | Caseload scope and valid lifecycle preserved |
| Care plans | Create/update/stage/goal/history for assigned and unassigned patients | History retained; no assignment oracle/content leak |
| Exercises | Assign/update and view progress for assigned/unassigned patients | Only assigned clinician can act; generic unavailable responses |
| Report upload/review | Clean PDF, scanner failure/rejection, foreign patient | Fail closed; clean approved only; no foreign report creation/access |

## Administrator journeys

| Journey | Connected staging cases | Pass condition |
|---|---|---|
| Patient/staff management | Create/edit/list fictional users, duplicate staff email, audit history | Admin-only; metadata audit; public registration privacy unaffected |
| Clinician schedules | Draft/preview/publish/stale revision/date exceptions | Published revision authoritative and conflict-safe |
| Appointments | Admin booking/status/reassignment/collision | Atomic claims and assignment audit preserved |
| Laboratory | Review/assign/upload/publish/release chain | Only scanner-approved finalized report released; unavailable/rejected files remain inaccessible |
| Payments | View/reconcile only after Test Mode approval | Provider-confirmed states only; cancellation capture remains clinic review |
| Audits | Patient edits, schedules, care plans, report scan events | Actor/time/action present without copied sensitive values |

## Execution order and stop rules

1. Environment identity, no-normal-data attestation and secret presence checks.
2. Authentication throttling/session/proxy validation across at least two workers.
3. IDOR/role matrix before positive clinical workflows.
4. Appointment concurrency and cancellation.
5. Report quarantine with approved scanner.
6. Lab/admin workflows.
7. Razorpay Test Mode only after separate authorization.

Stop if the target identity is ambiguous, normal data appears, secrets are
logged/client-visible, forwarded headers bypass limits, unavailable resources
differ, a quarantined/rejected file downloads, duplicate active slots occur, or
any live payment credential/event appears.

## Concrete acceptance gates prepared 2026-11-01

These gates are a plan only. No staging resource, proxy, scanner or database was
contacted by this remediation. Do not execute a gate until the owner approves
the exact target, permissions, fictional dataset and evidence retention.

### Gate 0 — approved environment and fixtures

- Record the approved staging deployment marker, exact `physiocare_staging`
  database and host, dedicated credential, HTTPS frontend origin, trusted ingress
  CIDRs and four private report roots. Attest that the database is empty and
  contains no copied patient records. Verify only the presence of independent
  access/refresh secrets, never record their values.
- Use two backend worker processes behind the actual staging ingress and one
  separate direct client for negative proxy tests. Keep Razorpay and payment
  reconciliation disabled. Scanner uploads remain disabled until an adapter is
  selected, implemented and approved; `PDF_SCANNER_MODE=approved` currently fails
  startup by design.
- Create fictional accounts through supported application routes: patient A,
  patient B, primary clinician A, unrelated clinician B, admin and laboratory
  staff. Create one confirmed lab booking for each patient, one released and one
  unreleased laboratory report, one appointment per clinician relationship,
  and one care plan/exercise assignment for patient A. Record generated IDs only
  in a restricted test manifest; never hard-code credentials or copy documents.
- Require sanitized request IDs, status/body, worker ID, relevant before/after
  counters or status, and cleanup outcome for each case. Redact cookies, tokens,
  forwarded IPs, credentials, file contents and clinical text from evidence.

### Gate 1 — Mongo and ingress across workers

1. Confirm the rate-limit collection has a unique `bucket_key` index and a TTL
   index on `expires_at` with `expireAfterSeconds=0`. Test that a completed
   bucket eventually expires; allow Mongo TTL monitor scheduling rather than
   asserting an instantaneous deletion.
2. Send parallel login failures for one fictional account from both workers,
   with an aggregate count above the configured limit. Exactly the configured
   number may pass the limiter; subsequent responses must use the generic 429
   contract on both workers. Repeat for registration and refresh IP/token
   limits, including simultaneous first-use bucket upserts.
3. Rotate one fictional refresh token concurrently through both workers. At
   most one rotation succeeds; replay invalidates the session and both workers
   reject its descendants. Verify no raw token or account key appears in the
   limiter collection or logs.
4. Through the real ingress, compare a request with a forged `X-Forwarded-For`
   header against one without it; the ingress must replace client-supplied
   forwarding values. Send a direct request from an untrusted peer with the
   same forged header; it must not change the computed throttle identity.
   Compare worker logs only through redacted correlation IDs.

The opt-in repository Mongo contract is restricted to its acknowledged
**loopback** database and must not be pointed at staging. Connected staging
needs a separately reviewed harness using the approved environment inventory.
Stop on index mismatch, cross-worker divergence, successful replay, spoofed
header influence, or an identity/data isolation mismatch.

### Gate 2 — connected object authorization

- For appointment update and cancellation, laboratory report download and
  request withdrawal, and care/exercise/report direct objects, compare fictional
  owner/assigned, other-patient/unassigned, nonexistent and malformed IDs.
  Missing and unauthorized responses must match in status and public detail;
  denied operations must leave the database unchanged. Wrong-role and
  unauthenticated cases must follow their explicit role/authentication contract.
- Create a diagnostic report for patient A with patient B's confirmed booking
  ID; require a generic unavailable response, no report, and unchanged booking
  B. Repeat with malformed, nonexistent, non-diagnostic and stale booking IDs.
  Race two valid claims for one confirmed booking across workers: no more than
  one report and one completed transition. Inject a report insert failure in a
  controlled test path and verify conditional compensation or a visible
  reconciliation alert without exposing identifiers.
- Repeat browser workflows with fictional sessions and verify Secure/HttpOnly/
  SameSite cookie attributes, CSRF rejection and no foreign object content in
  HTML, JSON or downloaded files.

### Gate 3 — approved scanner and storage

After the scanner owner approves an adapter, its private transport, version,
health check, timeout, bounded metadata mapping and test fixtures, implement and
review the adapter and staging configuration. Re-run the clean backend gate.
Use only the scanner owner's approved inert malicious-test fixture; do not
introduce real malware into the environment.

For both clinical and laboratory upload paths, run a clean PDF, structurally
malformed PDF, approved malicious-test PDF, approved polyglot fixture, scanner
timeout, scanner crash and scanner-unavailable case. Only a clean verdict may
move to the approved root and become downloadable by the owner. Every other
case must return a bounded error, remain inaccessible, and leave a sanitized
audit event with no raw scanner text, file path or clinical content. Verify
private permissions, distinct quarantine/approved roots, no symlink escape,
and cleanup visibility for an injected deletion failure. Stop on any
unscanned/rejected download or unexplained orphan.

### Cleanup and decision

Inventory all fictional users, sessions, bookings, reports, files, audit events
and limiter buckets by the restricted test-run identifier. Revoke sessions,
remove only that run's approved test records and files through the reviewed
cleanup procedure, and verify zero remaining test artifacts. Do not use a broad
database or volume deletion command. Keep a redacted pass/fail evidence bundle
under the approved retention policy. Phase 14 can be re-reviewed only after
the current locked backend CI gate and Gates 0–3 pass; Razorpay Test Mode is a
separate authorization and is not part of this pass.
