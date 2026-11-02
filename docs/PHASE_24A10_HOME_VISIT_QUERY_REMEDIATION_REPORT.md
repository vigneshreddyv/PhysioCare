# Phase 24A.10 Home Visit Query Remediation Report

Assessment date: 2026-11-02

Repository: `/Users/boddisuryakathyakeya/PhysioCare/PhysioCare`

Branch: `codex/physiocare-integration-2026-10-31`

HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

The targeted no-preference `HomeVisitRequests` query defect is **RESOLVED for the offline application contract**.

The former flow loaded every doctor and then made sequential user, appointment, and schedule reads for each clinician. It now uses one deterministic, read-only MongoDB aggregation cursor that:

- filters doctor role, active account, and home-visit eligibility in MongoDB;
- projects only clinician ID, published schedule fields, and conflict-time fields;
- limits appointment data to the requested clinic day and active statuses;
- streams clinician contexts instead of materializing an unlimited clinician collection;
- computes daily availability without retaining a clinician-sized result; and
- skips known occupied candidates before retaining the unique slot-claim insertion as the final concurrent-booking authority.

Mocked query instrumentation observed one aggregation invocation for both 1 and 250 clinicians. The application-level read count no longer grows with clinician count. This is not a MongoDB `explain`, wire-command count, latency benchmark, connected scale test, or production-readiness claim.

The affected screen can move from **PARTIAL to PASS for this offline query contract**. Phase 24A remains conditionally closed only within its documented offline scope. Other out-of-scope residual endpoints, policy decisions, and all eight connected release gates remain unresolved. Phase 24B remains **BLOCKED pending explicit approval and independent review**.

## 2. Initial repository state

Before Phase 24A.10 changes:

- branch: `codex/physiocare-integration-2026-10-31`;
- HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`;
- upstream: `origin/codex/physiocare-integration-2026-10-31`, ahead 0 / behind 0;
- tracked modifications: **88**;
- untracked paths: **67**;
- total changed paths: **155**.

This exactly matched the Phase 24A.9 final state. `docs/PHASE_24A9_INDEPENDENT_FINAL_SECURITY_REVIEW.md` was present as the additional untracked Phase 24A.9 path. No existing tracked modification or untracked path was discarded, restored, stashed, cleaned, committed, or pushed.

## 3. Original query flow

The frontend flow is:

1. `frontend/src/pages/patient/HomeVisitRequests.jsx` selects `no_preference` and requests `GET /api/home-visit-bookings/availability` using the preference and date as the React Query key.
2. The patient submits `POST /api/home-visit-bookings` with `preferred_doctor_id: null`.
3. `backend/app/api/home_visits.py` applies the patient-only role dependency and passes the authenticated user ID to `HomeVisitService`.
4. `_entitled_patient()` resolves only the current user's patient profile and requires the feature-specific entitlement before clinician work.
5. The old `_eligible_home_visit_doctors()` called `ProfileRepository.list_doctors()` without a bound, then called `UserRepository.get_by_id()` sequentially for every doctor.
6. Availability called `AppointmentRepository.list_active_by_doctor_id()` and `ClinicianScheduleService.effective_slots()` sequentially for every eligible clinician.
7. Booking called `ClinicianScheduleService.validate_effective_slot()` sequentially for every eligible clinician, then attempted deterministic unique slot claims until one insert succeeded.

The old application-level allocation-read complexity was:

- availability: one unbounded doctor read plus `N` user reads, `N` appointment reads, and `N` schedule reads: **`1 + 3N`**;
- booking: one unbounded doctor read plus `N` user reads and up to `N` schedule reads: **`1 + 2N`**, before submission/idempotency and insert operations.

The loops were sequential. Eligibility filtering occurred in Python after the entire doctor collection was loaded. Full doctor and user objects crossed repository boundaries even though no-preference allocation needed only clinician IDs, schedule data, and conflict-time fields.

## 4. Root cause

The no-preference branch reused single-clinician repository/service methods inside a collection loop. It had no query object representing the actual allocation question: active home-visit clinicians, their published schedule for one day, and their active conflicts for that same day. This caused collection-wide retrieval, redundant identity reads, N+1 access, avoidable object exposure, and process memory growth.

## 5. Files changed

Phase 24A.10 application changes:

- `backend/app/repositories/home_visit_query_repository.py` — new streaming allocation aggregation;
- `backend/app/services/home_visit_service.py` — no-preference availability and booking consume the streamed context;
- `backend/app/services/clinician_schedule_service.py` — pure helpers evaluate already-fetched schedules and slots without another repository read.

Backend regression changes:

- `backend/tests/test_phase24a10_home_visit_query.py` — new focused query-shape, cardinality, eligibility, conflict, atomicity, ownership, response, and neighboring-path tests;
- `backend/tests/test_phase23d_query_hardening.py` — existing day-window contract now asserts the aggregate context call;
- `backend/tests/test_api_contract.py` — existing no-preference atomic-retry test uses the aggregate context;
- `backend/tests/test_schedule_fallback_guard.py` — existing fail-closed fallback tests use the aggregate context.

Frontend regression addition:

- `frontend/tests/phase24a10-home-visit-query.test.mjs` — no-preference, query-key isolation, reset, loading, empty, error, request-count, and nullable-doctor contract tests.

Documentation addition:

- `docs/PHASE_24A10_HOME_VISIT_QUERY_REMEDIATION_REPORT.md`.

No frontend application component, API schema, route, database model, index, dependency, lock file, environment file, credential, payment path, or migration was changed.

## 6. New query architecture

`HomeVisitQueryRepository.iter_clinician_contexts()` executes one aggregation against the users collection:

1. `$match` restricts accounts to doctor role and `is_active: true`.
2. A projected doctor lookup retains only profiles whose `accepts_home_visits` value is not false; a missing legacy value retains the previous default-eligible meaning.
3. A projected schedule lookup uses the unique clinician-schedule relationship and returns only `doctor_id`, slot length, published revision, published weekly blocks, and published date exceptions.
4. A projected appointment lookup includes only `scheduled` or `in_progress` records whose authoritative `starts_at` or legacy `appointment_date` intersects the requested clinic day.
5. A stable `doctor._id` sort preserves deterministic allocation order.
6. Final projection contains only `doctor_id`, projected schedule, and projected conflict records. User names, emails, passwords, contact data, patient data, billing data, addresses, symptoms, and other clinical fields are absent.
7. The service consumes the cursor with `async for`; no unlimited `to_list()` is used.

Availability retains only the finite daily slot union, available-slot set, counts needed for configuration labels, and one clinician's projected conflict set at a time. Booking validates each streamed schedule, skips an already occupied selected start, and attempts the existing unique slot claim for the first currently viable clinician. A concurrent collision still advances to the next streamed candidate.

No eligible clinician is silently truncated. No appointment conflict is capped. The aggregation may stream additional MongoDB cursor batches at large cardinality; application instrumentation counts one aggregation invocation, not wire-level `getMore` commands.

## 7. Before-and-after query complexity

`N` is the eligible clinician count. Counts below describe allocation reads after the patient entitlement gate. “Measured” means mocked repository/aggregation invocation instrumentation, not a connected MongoDB profiler.

| Operation | Before | After |
|---|---|---|
| Clinician retrieval | 1 unbounded full doctor-list read; Python eligibility filter | Part of 1 filtered, stable, projected streaming aggregation |
| User lookup | `N` sequential full user lookups | 0 separate lookups; active doctor account filter occurs in aggregation |
| Appointment retrieval | Availability: `N` sequential one-day reads; booking relied only on insert collision | 0 separate reads; active one-day conflict projection is included in the aggregation for both availability and booking |
| Schedule retrieval | `N` sequential schedule reads | 0 separate reads; published schedule projection is included in the aggregation |
| Total allocation reads | Availability: `1 + 3N`; booking: `1 + 2N` | **1 logical aggregation invocation** for availability or booking |
| Instrumented scale evidence | No prior cardinality test | **1 invocation at 1 clinician; 1 invocation at 250 clinicians** |

Including unchanged business gates, a normal availability request performs current-patient lookup, entitlement lookup, and one allocation aggregation. A normal new booking additionally performs its submission-claim lookup and one atomic insert. Concurrent unique-key collisions can require further insert/submission checks; those are contention-dependent correctness operations, not per-clinician discovery queries.

No connected MongoDB query plan, index inventory, cursor-batch count, latency, memory profile, or realistic-scale benchmark was available or attempted. The connected MongoDB performance/index gate remains blocked.

## 8. Booking behavior preservation

The following behavior remains intact:

- deterministic clinician order by doctor ID;
- active-account and home-visit eligibility checks;
- no-preference response semantics and pending clinician assignment flag;
- selected date and normalized time validation;
- booking-window and future-slot validation;
- published schedule and demo-fallback semantics;
- authoritative conflict detection for modern `starts_at` and supported legacy date/time records;
- unique `slot_claim` protection for concurrent clinician-slot booking;
- submission-key idempotency and changed-payload conflict handling;
- retry with the next clinician after a concurrent unique-key collision;
- saved-address behavior after successful booking only;
- existing success/error response models and status behavior.

Availability still marks a slot available when at least one eligible clinician has schedule capacity, occupied when every scheduled clinician is conflicted, and past when the requested start is not future. Booking revalidates the selected slot from the streamed schedule and does not trust frontend availability.

## 9. Authorization and privacy verification

- Both affected endpoints retain `RoleChecker(["patient"])`.
- The service passes the authenticated user's ID to `_entitled_patient()` before running the allocation aggregation.
- `_entitled_patient()` resolves the patient profile by that user ID and requires that patient's home-visit entitlement.
- The frontend cannot supply a patient ID for either availability or booking.
- The new projection returns no clinician identity/contact fields and no patient, address, symptom, billing, payment, password, or credential fields.
- User input is not interpolated into a regular expression or field name. The date is schema parsed, the service validates the booking window, and the selected time is parsed by the existing strict time parser.
- The response contract remains the existing availability/appointment schema; no new sensitive field is exposed.

## 10. Backend regression tests

The new focused file covers:

- one aggregation and projection shape;
- database-side active-role and eligibility conditions;
- active-status and one-day conflict constraints;
- no sensitive user-field projection;
- constant aggregation invocation count at 1 and 250 clinicians;
- availability across multiple clinicians;
- all-candidate conflict behavior;
- absence of legacy per-clinician repository calls;
- no-eligible and no-scheduled-clinician handling;
- existing-conflict prefiltering;
- concurrent unique-claim retry;
- specific-clinician isolation from the bulk path;
- entitlement/ownership gate ordering;
- response-contract preservation.

Fresh results:

- Phase 24A.10 focused file: **13 passed**;
- compatibility selection for Phase 24A.10 plus existing API/query/fallback contracts: **142 passed**;
- broader appointment, availability, authorization, ownership, pagination, admin, doctor, and receptionist selection: **418 passed**.

Tests use deterministic fictional IDs/data and mocked repositories/aggregation. No database was contacted.

## 11. Frontend regression tests

The new frontend file verifies:

- no-preference remains valid without a selected clinician object;
- availability is keyed by both preference and date so an older key cannot replace a newer selection;
- changing preference or date clears the previous time;
- loading, empty-availability, and recoverable API-error states remain visible;
- no-preference submits the existing nullable `preferred_doctor_id` contract;
- success still reads `doctor_assignment_pending`; and
- exactly one availability request definition exists with no polling loop.

The focused home-visit/booking/coordination selection passed **27 tests**. No frontend application source or design was changed.

## 12. Neighboring workflow verification

The 418-test focused backend selection included:

- clinician-specific home-visit validation;
- general appointment booking/model behavior;
- appointment availability and legacy conflict resolution;
- schedule fallback, preview, and publication guards;
- patient role and ownership API contracts;
- patient appointment and home-visit pages;
- admin scheduled-home-visit coordination;
- doctor/reception coordination;
- clinical pagination and query-hardening contracts.

The 27-test focused frontend selection included patient home visits, clinic booking, admin home-visit coordination, and doctor/reception coordination. All passed.

## 13. Full verification results

| Verification | Fresh result |
|---|---:|
| Phase 24A.10 backend file | **13 passed** |
| Focused related backend | **418 passed** |
| Complete backend | **983 passed, 11 environment-failed, 3 connected-skipped** |
| Backend excluding only Unix-socket integration file | **982 passed, 3 skipped** |
| Socket-free ClamAV protocol + dependency-lock files | **9 passed** (7 protocol, 2 lock) |
| Focused frontend | **27 passed** |
| Complete frontend | **155 passed** |
| Frontend lint | **PASS** |
| Production build | **PASS**, Vite 8.3.5, **1,838 modules** |
| Asset budget | **74 JS/CSS assets**, zero violations |
| Python syntax | **164 files**, zero failures |
| `pip check` | **PASS**, no broken requirements |
| Offline `npm audit --audit-level=low` | **0 locally cached vulnerabilities**; cache freshness unknown |
| Redacted Gitleaks current-tree scan | **6 existing synthetic test fixtures**; no Phase 24A.10 path flagged |
| `git diff --check` | **PASS** |

The recurring pytest warning is the pre-existing already-imported `pytest_asyncio` assertion-rewrite warning. The three skips are the guarded connected registration, distributed-rate-limit, and report-transaction tests. No skip or assertion was weakened.

## 14. ClamAV environmental limitation

The complete suite's 11 failures are unchanged cases in `backend/tests/test_clamav_unix_scanner.py`. Each fake-daemon case stops when `asyncio.start_unix_server()` attempts to bind an AF_UNIX socket and the sandbox returns:

`PermissionError: [Errno 1] Operation not permitted`

The socket-free protocol units passed. This does not verify the Unix-socket integration or a real ClamAV daemon. No ClamAV test was modified.

## 15. Remaining risks

- No connected MongoDB `explain`, actual deployed-index inventory, cursor-batch measurement, memory profile, or representative-scale latency test exists. The aggregation is structurally constant at the application query boundary, but real server execution and index use require the separately approved connected gate.
- Concurrent inserts can still collide after the read, by design. The unique partial slot-claim index remains the final authority; connected concurrency behavior and deployed index presence are unverified.
- Legacy records with malformed time fields continue to be ignored during availability conflict resolution as before. The separate legacy preflight remains the migration evidence path.
- The broader Phase 24A.9 Medium section also named out-of-scope unbounded paths in the no-search demo-entitlement API fallback, payment history, and staff listing. Phase 24A.10 did not modify or close those findings.
- Password/email/recovery/onboarding policy decisions and the Phase 24A.9 notification-route evidence discrepancy remain unchanged.
- Redacted Gitleaks still reports six previously reviewed synthetic submission-key fixtures. This is not a zero-finding scan or proof that no secret exists.
- Offline npm audit depends on the local advisory cache and is not a fresh online vulnerability audit.

No Critical, High, or new Medium finding was identified in the Phase 24A.10 change. The absence of connected evidence prevents any production-readiness claim.

## 16. Updated Phase 24A closure recommendation

Recommendation: **PASS WITH CONDITIONS for the targeted Phase 24A.10 offline remediation**.

The `HomeVisitRequests` no-preference query path can be recorded as PASS for offline application behavior and query-shape evidence. Overall Phase 24A remains **conditional offline-scope closure**, because other residual query paths, policy choices, and connected environment gates remain open.

This report does not authorize client demonstration, staging, production, migrations, index changes, payments, real-patient workflows, or deployment.

## 17. Medium finding disposition

The specific Medium finding against the `HomeVisitRequests` no-preference clinician query is **RESOLVED OFFLINE**:

- unbounded full clinician list: eliminated by database-side filtering plus streaming;
- per-clinician user queries: eliminated;
- per-clinician appointment queries: eliminated;
- per-clinician schedule queries: eliminated;
- application-level read count linear in clinician count: eliminated and instrumented at 1 versus 250 clinicians;
- booking, conflict, ownership, authorization, response, and atomicity contracts: preserved by fresh regression evidence.

The broader Phase 24A.9 M1 category is not completely closed because its other three out-of-scope endpoints remain. Connected performance and index verification are also still required.

## 18. Phase 24B status

Phase 24B may be considered only as a separate future approval decision after independent review of this milestone and explicit treatment of the remaining conditions. It was not started.

All eight connected release gates from Phase 24A.9 remain **BLOCKED**. Client demonstration, staging, and production remain unauthorized.

## 19. External-access and repository statement

No production or external service was accessed. No MongoDB, protected database, payment provider, scanner daemon, infrastructure service, deployment target, package registry, or advisory network was contacted. Tests used mocked data, unreachable/local test configuration, existing installed dependencies, and local offline caches.

No commit, push, stash, reset, clean, destructive checkout, migration, index operation, seed, payment, refund, or deployment was performed.

Final worktree state after this report:

- tracked modifications: **88**;
- untracked paths: **71**;
- total changed paths: **159**;
- upstream ahead / behind: **0 / 0**.

The four-path increase from the initial state is exactly the new query repository, focused backend test, focused frontend test, and this report. Phase 24A.10 edits to existing source/tests occurred in paths that were already modified or untracked at baseline. All unrelated worktree content remains present.
