# Phase 24A.6 Independent Security Closure Review

Review date: 2026-11-02

Repository: `/Users/boddisuryakathyakeya/PhysioCare/PhysioCare`

Decision: **Outcome B — recommend conditional closure of the offline-verifiable Phase 24A scope**

## 1. Executive summary

The current source, configuration, and freshly executed offline checks support conditional closure of the Phase 24A offline scope. All 21 named screens are classified **PASS** for that scope. Authentication, session binding, CSRF, backend role/ownership controls, sensitive response cache policy, private PDF access, appointment slot claims, and bounded screen-specific data access are implemented and covered by relevant offline tests.

No Critical or High application-code defect was identified. One confirmed Medium availability/scalability defect remains outside the 21-screen matrix: the admin clinician directory uses an unbounded legacy endpoint and performs an N+1 user lookup. A six-character minimum for public registration is a confirmed Low policy weakness. The Phase 24A.5 report also contains one Low documentation mismatch for the PatientCarePlan endpoint; the actual implementation is consistent across frontend and backend.

Fresh backend execution collected 976 tests and produced **962 passed, 11 failed, 3 skipped**. The 11 failures are confined to `backend/tests/test_clamav_unix_scanner.py`; every failure occurs while the test tries to bind an AF_UNIX server and receives `PermissionError: [Errno 1] Operation not permitted`, before the intended application assertions. A supplemental run excluding only that file produced **961 passed, 3 skipped**. The seven socket-free protocol tests were also run independently and passed. This supports an environmental classification for the observed failures, but does not prove actual Unix-socket, daemon, scanner, or storage integration.

All eight connected release gates remain **BLOCKED**. This decision is not approval for Phase 24B, a client demonstration, staging, or production.

## 2. Review scope and methodology

The review read the Phase 22, Phase 23, Phase 24, Phase 24A, Phase 24A.2, Phase 24A.3, Phase 24A.4, and Phase 24A.5 reports, then checked the associated implementation, configuration, and tests rather than accepting prior PASS labels. It used only local files and isolated offline commands. It did not contact MongoDB, Razorpay, ClamAV, a browser service, external package registries, or any other network service.

Evidence labels used here are:

- **Fresh**: executed during Phase 24A.6.
- **Inspected**: verified directly from current source or local artifacts.
- **Historical**: reported by an earlier phase but not independently rerun in the same grouping.
- **Blocked**: requires an approved connected or socket-capable environment.

No migration, deployment, provisioning, payment/refund operation, commit, push, reset, clean, branch switch, or application-code change was performed.

## 3. Current branch and worktree state

At review start:

- Branch: `codex/physiocare-integration-2026-10-31`.
- HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`.
- Upstream: `origin/codex/physiocare-integration-2026-10-31`, with ahead/behind `0/0`.
- Tracked changed paths: **87**.
- Untracked paths: **59**.
- Total changed paths: **146**.

These counts independently match the historical Phase 24A.5 baseline. The existing changes were treated as user work and preserved. The two Phase 24A.5 additions are present:

- `backend/tests/test_clamav_protocol_unit.py`
- `docs/PHASE_24A5_BACKEND_TEST_ENVIRONMENT_RECOVERY_REPORT.md`

This review adds only this report. The final state is therefore 87 tracked changed paths, 60 untracked paths, and 147 total changed paths. It does not alter any application, test, dependency, configuration, or existing documentation file.

## 4. Independent dependency recovery assessment

**Assessment: verified for the present local environment; durable future availability is not proven.**

- `backend/requirements.txt` directly pins FastAPI, and `backend/requirements.lock` contains `annotated-doc==0.0.5` and the complete resolved set.
- The original local HTTP-cache body for `annotated-doc==0.0.5` remains available. Its SHA-256 is `117bac03a25ede5df5440e855b32d556049ca169ead221505badf432fed4b101`; metadata identifies version 0.0.5, Python `>=3.9`, and `py3-none-any` compatibility.
- The documented read-only inventory procedure was rerun against the lock and local pip HTTP cache: **48 locked artifacts found, zero missing, zero invalid**. Embedded wheel `RECORD` validation succeeded for all 48.
- The existing isolated environment uses Python 3.13.1. Installed versions exactly match all 48 lock pins, and `pip check` reports no broken requirements.
- The local wheelhouse contains 48 wheels and is owner-only (`0700`). No package was installed or downloaded during this review.
- There is no diff in `backend/requirements.txt`, `backend/requirements.lock`, `backend/pytest.ini`, or root `pytest.ini` attributable to recovery.

The evidence confirms Phase 24A.5's root-cause classification: the failure was offline discovery of an opaque cached artifact under `--no-index`, not an invalid pin, resolver conflict, or Python/platform incompatibility. The procedure is reproducible now from the still-present local cache and wheelhouse. It is not a substitute for an approved durable artifact mirror, and neither `pip check` nor lock agreement is a vulnerability audit.

## 5. Backend test evidence assessment

### Fresh execution

The backend suite was run from `/private/tmp` using the existing Phase 24A.5 virtual environment, `env -i`, synthetic test-only secrets, an unreachable loopback MongoDB URI, disabled payment reconciliation, disabled Razorpay, disabled scanner startup, disabled plugin autoload, explicit `pytest_asyncio`, and no pytest cache provider.

| Check | Fresh result | Assessment |
|---|---:|---|
| Full backend suite | 962 passed, 11 failed, 3 skipped; 976 total | Credible; failures isolated below |
| Same suite excluding only `test_clamav_unix_scanner.py` | 961 passed, 3 skipped | No ordinary application failure hidden by the socket file |
| `test_clamav_protocol_unit.py` | 7 passed | Socket-free protocol assertions pass |
| Python AST parse | 160 files | Syntax-valid current backend |

The single warning is a pytest assertion-rewrite warning because `pytest_asyncio` was already imported. It did not alter collection or test outcomes.

The three skips are deliberate connected-test safeguards:

1. `backend/tests/test_account_registration_connected_mongo.py` — exact empty local registration database not approved.
2. `backend/tests/test_auth_rate_limit_connected_mongo.py` — connected opt-in not enabled.
3. `backend/tests/test_report_transaction_connected_mongo.py` — approved MongoDB replica set not supplied.

The historically reported focused-security count (354) and pagination/query count (535) were not rerun as separate groupings. Their current tests were collected and exercised by the fresh complete run. The historical 142-test frontend count was independently reproduced, as documented in section 14.

### Failure classification

All 11 failed cases are parametrized instances of these functions in `backend/tests/test_clamav_unix_scanner.py`:

- `test_unix_scanner_streams_file_and_maps_only_safe_verdicts` (four verdict/reply cases)
- `test_unix_scanner_requires_daemon_ping_for_readiness`
- `test_unix_scanner_fails_closed_on_daemon_disconnect`
- `test_unix_scanner_timeout_is_bounded_by_storage_policy`
- `test_both_upload_paths_use_private_clamav_verdict` (clinical/laboratory × clean/malicious)

Each reaches `asyncio.start_unix_server`, then fails at AF_UNIX bind with `PermissionError: [Errno 1] Operation not permitted`. The separate missing-socket fail-closed test passes. Therefore the **observed failures are an environment restriction**, not evidence of a dependency/configuration issue or a demonstrated application/test defect. Their intended integration behavior remains unresolved in this environment.

## 6. ClamAV environmental exception assessment

`backend/app/services/pdf_malware_scanner.py:36-87` sends `zPING\0` for readiness and `zINSTREAM\0` for scanning, frames chunks with four-byte big-endian lengths, sends a zero-length terminator, recognizes exact clean and malicious responses, and returns an error verdict for all other responses and transport exceptions.

`backend/tests/test_clamav_protocol_unit.py:39-110` independently exercises:

- multi-chunk framing and the zero terminator;
- clean, malicious, daemon-error, and unexpected verdict parsing;
- readiness PONG and unexpected responses;
- writer closure; and
- fail-closed `OSError` behavior.

The seven cases passed freshly. They prove protocol construction/parsing and selected fail-closed behavior without a socket. They do **not** prove AF_UNIX exchange, clamd interoperability, daemon disconnect behavior, timeout enforcement through storage, upload-path integration, or real malware detection.

`backend/app/services/clinical_report_storage.py:166-334` shows quarantine-before-approval, owner-only files/directories, separate storage roots, bounded scan waiting, deletion of rejected quarantine files, atomic promotion, and fail-closed scanner errors. `backend/app/main.py:30-49` refuses startup when configured ClamAV readiness fails. These are source-level controls, not connected integration evidence.

**Exception status: requires formal acceptance for offline closure; socket-capable scanner and storage testing remains BLOCKED.**

## 7. Complete 21-screen verification matrix

The matrix traces each component to its active API behavior and relevant current tests. The fresh backend and frontend suites exercised these tests. Shared controls include `frontend/src/services/clinicalPagination.js`, which retains only the current page, validates page bounds, and supports abort/auth-generation invalidation; no active screen calls the older page-accumulating helpers. Backend page queries apply role/owner/assignment/search/date filters before stable sort, skip, and limit. Searches at and beyond the former 1,000-record boundary are covered by pagination tests.

| Screen | Classification | Evidence-based explanation |
|---|---|---|
| Patient `BookAppointment` | **PASS** | `frontend/src/pages/patient/BookAppointment.jsx` uses bounded clinician/availability selection and server booking. Appointment routes/services revalidate the slot and patient identity; unique slot/submission claims cover races. Appointment and patient-lookup tests cover conflict, idempotency, loading/error/empty states, and cleanup. |
| Patient `HomeVisitRequests` | **PASS** | `frontend/src/pages/patient/HomeVisitRequests.jsx` uses paged owned requests and bounded clinician search. Backend home-visit service/repository scopes to the patient and validates schedule eligibility. Home-visit page and booking tests cover later pages, empty/error states, and authorization. |
| Patient `PatientAppointments` | **PASS** | The component requests stable, paged, patient-owned appointments with date/status filters. Repository filters precede pagination. Appointment-history and clinical-pagination tests cover later pages, empty/error states, cancellation, and auth cleanup. |
| Patient `PatientCarePlan` | **PASS** | The active request is `GET /care-plans?selection=active_latest`; the service resolves only the patient's active/latest plan and bounded detail. Care-plan selection/stage tests cover ownership, empty/error states, and deterministic selection. Phase 24A.5's `/care-plans/me/active` wording is documentation-only and inaccurate. |
| Patient `PatientDashboard` | **PASS** | Dashboard summary/recent items are bounded and patient-scoped; no history accumulation occurs in the browser. Dashboard-recent tests and frontend render-state tests cover loading, empty, error, and current-patient transitions. |
| Patient `PatientExercises` | **PASS** | Active assignments are patient/plan scoped; progress statistics are database-side or bounded aggregation rather than a full browser history. Exercise-navigation, progress-aggregation, and frontend state tests cover empty/error and auth change. |
| Patient `PatientHistory` | **PASS** | Uses the paged patient appointment-history contract with stable sort and server-side filters. History and pagination tests cover records beyond earlier client limits, empty/error states, and patient ownership. |
| Patient `PatientProgress` | **PASS** | Active-plan selection and exercise progress are patient-scoped and bounded; tests cover correct aggregate values and empty plans. Auth-generation cleanup prevents previous-session results from being rendered. |
| Patient `PatientReports` | **PASS** | Uses server-side patient ownership, released-state rules, escaped search, stable pagination, private PDF download, and viewer invalidation. Report-search, PDF security, and frontend stale-response tests pass. |
| Admin `AdminDashboard` | **PASS** | Dashboard APIs return database-side aggregates and bounded recent activity. Admin activity/dashboard and frontend state tests cover loading/error/empty behavior; role checking is backend-enforced. |
| Admin `AdminPatientHistory` | **PASS** | Patient, date, status, and release filters run before stable paging; associated records are enriched in bounded batches. Patient-switch epoch guards close PDF viewers and reject stale responses. Group B2, patient-management, and PDF tests pass. |
| Admin `AppointmentBooking` | **PASS** | Patient/doctor pickers always send a search parameter and therefore select the bounded endpoint branch. Server availability and slot-claim logic remain authoritative. Group B2, schedule, appointment, and frontend picker/error-state tests pass. |
| Admin `Billing` | **PASS** | Billing queries are paged and role-restricted; payment ownership and provider-signature logic are tested offline. Empty/error states are present. Razorpay reconciliation remains a connected gate. |
| Admin `CarePlanManagement` | **PASS** | Patient/clinician access is role/assignment checked by the backend, list queries are paged, and plan detail is bounded. Group B2 and care-plan tests cover authorization, empty/error, and later-page behavior. |
| Admin `DemoServices` | **PASS** | Clinician selection explicitly uses bounded search and home-visit filtering. Demo isolation and group B2 tests verify separation from protected records; UI state tests cover empty/error behavior. |
| Admin `ExerciseAssignmentManagement` | **PASS** | Assignment operations are patient/plan scoped and screen lists are bounded. Exercise and group B2 tests cover authorization, aggregate correctness, empty/error, and patient changes. |
| Admin `Notifications` | **PASS** | Notification lists are recipient scoped and paged with stable ordering. Admin activity/notification tests cover isolation and frontend loading/error/empty states. |
| Admin `ReportAuthoring` | **PASS** | Backend revalidates admin/assigned-doctor patient authority and associated booking, then uses private quarantine/storage. Authoring, report, PDF, and group B2 tests cover invalid uploads, authorization, empty/error, and stale selection cleanup. |
| Doctor `DoctorDashboard` | **PASS** | Queries are clinician-scoped, recent rows are bounded, and aggregate work is server-side. Group C, lab-query, dashboard, and frontend state tests pass. |
| Doctor `DoctorPatientHistory` | **PASS** | Backend verifies a non-pending assignment before patient history, applies filters before pagination, and returns neutral denial behavior. Patient switching invalidates stale PDF/data responses. Group C, PDF, and lab authorization tests pass. |
| Receptionist `ReceptionistDashboard` | **PASS** | Backend role checks and projections expose scheduling fields without clinical reasons/symptoms or billing detail; date/status filters precede stable paging. Group C and frontend dashboard tests cover bounded data and empty/error states. |

The classifications are offline only. They do not establish browser E2E behavior, connected database indexes, query plans, real concurrency, or production proxy behavior.

## 8. Authentication and session review

**Verified strengths**

- `backend/app/services/auth_service.py:157-188` uses the same generic 401 path for unknown email, invalid password, and inactive account before issuing a session, limiting registration/account-state enumeration.
- Refresh validation and rotation (`auth_service.py:191-227,261-316`) bind token type, session, user, expiry, revocation, stored hash, and CSRF; failed rotation claims revoke the session.
- `backend/app/middleware/auth.py:20-109` binds access tokens to live sessions, enforces CSRF on unsafe methods, and reloads active-user state on every authenticated request. Existing sessions are not proactively deleted on deactivation, but their next request and refresh are rejected because the user must still be active.
- `backend/app/api/auth.py:30-79` uses HttpOnly access/refresh cookies, Secure cookies in staging/production, SameSite Lax, scoped paths, a readable CSRF cookie, and revocation before cookie clearing on normal logout.
- Frontend login waits for profile confirmation. Ambiguous login is recoverable. Logout failure hides private data and retains an explicit retry path. Login, logout, and auth changes cancel clinical requests, close PDF viewers, and clear the query cache (`frontend/src/contexts/AuthContext.jsx`, `frontend/src/services/loginSession.js`, and `logoutSession.js`).
- `backend/app/main.py:94-131` applies private/no-store headers to authenticated/auth endpoints and to early unsafe-origin 403 responses.
- `backend/run_production.py:8-21` requires an explicit production process environment, ignores dotenv input, validates runtime settings, and disables reload. `backend/app/core/config.py` validates environment-specific database identity, hosts/TLS, credentials, storage, payments, and scanner configuration before supported startup.

No supported production entry-point bypass was identified. Operational invocation outside the documented entry points remains a deployment-governance concern, not an identified code bypass.

## 9. Clinical PDF and document security review

- Clinical report download (`backend/app/api/reports.py:77-117`) resolves the authenticated patient's profile and delegates ownership checks before resolving an opaque private storage key.
- Laboratory download (`backend/app/api/lab_requests.py:157-176`) delegates patient ownership, assigned clinician/laboratorian, release-state, and admin checks to the service before storage resolution.
- Both sensitive routes preserve exactly `Cache-Control: private, no-store, no-cache, must-revalidate`, `Pragma: no-cache`, and `Expires: 0`; middleware will not weaken the stronger route policy.
- Storage rejects invalid type/name/size/PDF structure, quarantines with owner-only permissions, separates clinical and lab roots, deletes rejected quarantine files, and promotes only approved files.
- `frontend/src/services/openPdfBlob.js` tracks an auth/viewer generation, closes prior object URLs/viewers, and rejects stale responses. Admin and doctor history components also invalidate on patient changes.
- Report creation and lab publication authorization are backend controls. Frontend navigation is not trusted as the authorization boundary.

The current evidence supports authorization, isolation design, cache policy, and stale-response behavior offline. Actual ClamAV exchange, storage-service integration, and browser cache behavior remain blocked and are not claimed as passed.

## 10. Appointment and scheduling review

Appointment routes are role gated. The service, not the browser, validates effective availability and the requested slot. Candidate conflict queries cover the relevant date window, and the model uses partial unique `slot_claim` and `submission_claim` indexes; duplicate-key races become 409 responses. Patient cancellation is ownership checked, limited to scheduled appointments and the 24-hour cutoff, and conditionally unsets the slot claim. Reception cancellation follows the same cutoff. Paid cancellation enters reconciliation rather than asserting a completed provider refund.

Doctors may update only their assigned, non-pending patients/appointments, with billing-sensitive changes restricted. Receptionist projections exclude clinical reasons/symptoms and billing details. Same-day and fallback-schedule behavior, slot removal, repeated submissions, concurrent claims, and cross-clinician denial are covered by offline tests.

There is no general rescheduling workflow; cancellation plus a new booking is the supported behavior. Legacy rows without canonical `starts_at` retain a same-day limitation and require the documented preflight before migration/index enforcement. Actual index presence and connected concurrency remain blocked.

## 11. Role and ownership authorization review

Backend dependencies enforce patient, doctor, administrator, receptionist, and laboratorian roles. Services/repositories then narrow records by patient ownership, doctor assignment, release state, recipient, or appointment relationship before pagination. Relevant verified boundaries include:

- patient-owned reports, appointments, home visits, plans, exercises, progress, notifications, and payments;
- doctor access only through non-pending patient assignment and assigned appointments;
- laboratory access by assigned laboratorian, with patient/doctor visibility limited by release status;
- receptionist access to scheduling-safe projections rather than clinical or payment detail;
- notification recipient isolation; and
- payment ownership plus offline provider signature/status validation.

The fresh suite contains no ordinary application failure in these boundaries. Connected multi-clinician proof remains blocked; offline mocks and repository-contract tests are not represented as live MongoDB evidence.

## 12. Analytics and query safety review

Dashboard daily counts and clinic statistics use MongoDB match/group/facet aggregation. Recent-record panels are bounded. Patient/clinician filters precede pagination, and stable sorts include deterministic keys. Exercise progress uses scoped aggregation rather than downloading complete histories. Schedule conflict queries are date/clinician/slot scoped and protected by unique claims.

No unbounded browser accumulation is active on the 21 screens. The older exported helpers `fetchClinicalPages` and `fetchClinicalHistoryPages` in `frontend/src/services/clinicalPagination.js` have no callers.

One active query defect exists outside the 21 screens: the admin `DoctorsList` component calls `/users/doctors` without `search` (`frontend/src/pages/admin/DoctorsList.jsx:19-24`). That selects the legacy unpaged branch (`backend/app/api/users.py:78-90`), loads every doctor (`backend/app/repositories/profile_repository.py:125-127`), and performs one user lookup per doctor (`backend/app/services/user_service.py:176-195`). This is a confirmed Medium availability/scalability and N+1 issue. It does not expose the endpoint to a non-admin role.

Other legacy bulk repository methods and low-cardinality specialization aggregation should be kept under review. Offset pagination can drift under concurrent writes and retains a configured maximum page. Connected explain plans, index verification, and realistic-scale performance remain blocked.

## 13. Gitleaks assessment

A fresh local Gitleaks directory scan completed with **exactly six findings**:

- Five `generic-api-key` findings in `backend/tests/test_api_contract.py`.
- One `generic-api-key` finding in `backend/tests/test_schedule_fallback_guard.py`.

AST/context review maps all six to synthetic `submission_key` or idempotency fixtures for booking and scheduling tests: atomic shared-slot reservation, removed-slot rejection, repeated submissions, changed payload rejection, and unpublished demo-slot rejection. They are not loaded as credentials, provider keys, JWT secrets, or deployment configuration. The secret-like values are intentionally not reproduced here.

No Phase 24A.5 file was flagged in the pre-report scan. A fresh post-report scan returned the same six findings and did not flag this report. These findings should remain documented rather than deleting fixtures to manufacture a zero count. No current finding requires credential rotation based on its code context.

## 14. Current frontend and backend evidence

| Verification | Evidence during Phase 24A.6 | Result |
|---|---|---:|
| Backend complete suite | Fresh isolated run | 962 passed, 11 AF_UNIX-bind failures, 3 connected skips |
| Backend without only socket integration file | Fresh isolated run | 961 passed, 3 connected skips |
| Socket-free ClamAV protocol tests | Fresh isolated run | 7 passed |
| Frontend tests | Fresh `npm test` | 142 passed, 0 failed/skipped |
| Frontend lint | Fresh | Passed |
| Frontend production build | Fresh, output under `/private/tmp` | Passed; 1,838 modules transformed |
| Asset budget | Fresh build inspection | 74 JS/CSS assets, zero violations; largest JS 373,260 bytes, CSS 254,380 bytes |
| Python syntax | Fresh AST parse | 160 files parsed |
| npm audit | Fresh offline audit in `frontend` | Zero locally cached vulnerabilities |
| Whitespace | Fresh pre-report `git diff --check` | Passed |

The offline npm audit is limited to the local advisory cache; its freshness is unknown. No current offline Python advisory database was available, so lock consistency and `pip check` must not be read as a Python vulnerability scan. The production build was emitted outside the repository.

## 15. All eight connected release gates

| Gate | Status | Reason |
|---|---|---|
| 1. Connected multi-clinician authorization | **BLOCKED** | No approved isolated MongoDB identity/data set; offline authorization tests are not connected proof. |
| 2. MongoDB query plans and realistic-scale performance | **BLOCKED** | No approved database or representative dataset; no live `explain` evidence. |
| 3. Actual database index verification | **BLOCKED** | Model/index declarations were inspected, but actual deployed indexes were not queried. |
| 4. Socket-capable ClamAV protocol and scanning | **BLOCKED** | AF_UNIX bind is denied in this environment; socket-free tests do not clear integration. |
| 5. Private storage integration and access verification | **BLOCKED** | Local source/tests support design, but no approved deployed private storage was contacted. |
| 6. Browser end-to-end journeys | **BLOCKED** | Component/source tests are not a real-browser, multi-role E2E run. |
| 7. Production proxy, TLS, cookie, and cache verification | **BLOCKED** | Configuration guards were inspected; no production-like proxy/TLS environment was used. |
| 8. Backup and restore testing | **BLOCKED** | No approved infrastructure, backup, or restore target was available. |

## 16. Confirmed defects

### Medium — unbounded admin clinician directory with N+1 lookups

**Confirmed.** `frontend/src/pages/admin/DoctorsList.jsx:19-24` invokes `/users/doctors` without search or page semantics. `backend/app/api/users.py:78-90` consequently selects the legacy bulk branch; `backend/app/repositories/profile_repository.py:125-127` has no limit, and `backend/app/services/user_service.py:176-195` loads each associated user separately. A large clinician population can amplify database work and response size. The route remains admin-only, so this is not a confirmed confidentiality breach. It lies outside the required 21-screen matrix but is current application code.

### Low — public registration permits six-character passwords

**Confirmed.** `backend/app/schemas/auth.py:9-12` uses `min_length=6` for public registration, while staff creation uses eight. Hashing and login throttling reduce some risk, but the clinic must choose and document an appropriate password policy before release.

### Low — Phase 24A.5 PatientCarePlan endpoint wording

**Confirmed documentation discrepancy.** The report names `/care-plans/me/active`; the active frontend/backend contract is `GET /care-plans?selection=active_latest`. This does not indicate an implementation mismatch or authorization defect.

No Critical or High application-code defect was identified.

## 17. Residual risks

- Unix-socket scanner, daemon interoperability, timeout, real scanning, and quarantine-to-private-storage integration are unverified.
- Connected database authorization, real indexes, transaction/concurrency behavior, query plans, and scale are unverified.
- Browser lifecycle, cookies behind a real proxy/TLS terminator, cache behavior, and cross-role journeys are unverified.
- Razorpay reconciliation/refund behavior was not contacted or exercised.
- Local dependency recovery relies on cache/wheelhouse artifacts that are not a durable approved mirror.
- The offline npm advisory cache may be stale, and no current offline Python advisory audit was possible.
- Existing sessions are rejected on the next authenticated request after deactivation, but there is no demonstrated connected test of deactivation racing with in-flight requests.
- Offset pagination can drift during concurrent writes; it is bounded but not snapshot consistent.
- Legacy bulk endpoints/repository helpers remain outside the remediated screen paths and require continued inventory as new UI flows are added.

## 18. Independent closure decision

**Outcome B — recommend conditional closure of the offline-verifiable Phase 24A scope.**

The decision is supported because all 21 screens have traceable current implementation and relevant fresh offline test coverage; authentication, authorization, PDF cache/ownership, appointment, and query controls are present; no Critical or High application-code defect was found; the 11 observed failures are demonstrably caused by prohibited AF_UNIX server binding; and all six Gitleaks findings were reviewed as synthetic fixtures.

This is not full release closure. The Medium legacy admin-directory defect, the formal environmental exception, and durable dependency-evidence limitation require explicit acceptance. The eight connected gates remain separate and blocked.

## 19. Conditions for proceeding

Before any later phase treats Phase 24A as closed, an authorized reviewer should explicitly accept all of the following:

1. The 11 AF_UNIX failures are accepted only as an offline-environment exception; the socket-capable ClamAV gate remains blocked and must pass in a suitable isolated environment before demo/staging/production claims.
2. The confirmed unbounded/N+1 admin clinician directory is tracked for remediation before realistic high-volume use, with pagination and bulk enrichment tests.
3. A durable approved source for all 48 locked artifacts is established before relying on rebuild reproducibility outside this machine.
4. The six-character public password minimum is accepted or changed under an explicit clinic security policy before release.
5. The eight connected gates remain blocked until separately approved and evidenced; offline PASS classifications must not be promoted into connected or production claims.
6. Phase 24B does not begin without explicit approval after this review.

Client demonstration: **HOLD**.

Production readiness: **NOT ESTABLISHED**.

Phase 24B: **NOT STARTED / AWAITING EXPLICIT APPROVAL**.
