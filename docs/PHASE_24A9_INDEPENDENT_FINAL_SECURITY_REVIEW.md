# Phase 24A.9 Independent Final Offline Security Review

Review date: 2026-11-02

Repository: `/Users/boddisuryakathyakeya/PhysioCare/PhysioCare`

Branch: `codex/physiocare-integration-2026-10-31`

HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

**Final decision: Outcome B — Conditional Offline-Scope Closure, with additional conditions.**

The independent review supports the narrow claim that the principal Phase 23 and Phase 24A authentication, session, cache, PDF authorization, bounded-page, analytics, role, ownership, and Phase 24A.7 administrator-directory remediations remain present and substantially verified offline. Phase 24A.8 added documentation only and did not change application behavior. The password, email-ownership, recovery, and staff-onboarding decisions remain **POLICY DECISION REQUIRED**.

The review does not support Outcome A. One confirmed Medium residual query finding remains: active home-visit and other API paths still contain unbounded/N+1 work. In particular, the patient `HomeVisitRequests` no-preference availability/booking branch loads every doctor and then performs per-doctor user, appointment, and schedule work. That screen is therefore **PARTIAL**, not PASS. A separate Low evidence-chain discrepancy exists because historical matrices identify `pages/admin/Notifications.jsx`, while the actual `/admin/notifications` route renders `pages/common/Notifications.jsx` and the admin-specific component is unrouted.

After reconciling the historical counts, the application has **25 distinct active routed screen components in the reviewed Phase 24A union: 24 PASS, 1 PARTIAL, 0 FAIL, 0 NOT VERIFIED** for offline contracts. The Phase 24A.3 report listed 21 components; Phase 24A.2 added five, producing a 26-component source inventory; one of those, admin-specific `Notifications.jsx`, is not routed because the common Notifications component serves the route. This explains the active count of 25.

No Critical or High application-code finding was identified. All eight connected release gates remain **BLOCKED**. Phase 24B, client demonstration, staging, and production remain unauthorized.

## 2. Scope and methodology

This was a review-only milestone. The review:

- read the complete requested Phase 20–24A.8 evidence chain and the additional Phase 24A cache/query, closure-reverification, and Phase 24A.2 reports;
- recalculated Git state and inspected current source/tests instead of inheriting PASS labels;
- traced active frontend routes to components and backend routes, services, and repositories;
- searched current application code for unbounded reads, N+1 patterns, obsolete accumulation helpers, authorization dependencies, password/recovery features, and PDF paths;
- executed fresh offline backend, frontend, static, dependency, secret, and whitespace checks using the existing recovered environment; and
- made no database, scanner-daemon, payment-provider, browser-service, infrastructure, deployment, migration, or external-network connection.

No application source, test, historical report, dependency, lock, `.env`, or credential was modified. This report is the only Phase 24A.9 repository addition.

Evidence labels:

- **Verified:** current source plus fresh applicable offline tests.
- **Partial:** implementation exists, but a concrete branch or evidence gap prevents PASS.
- **Environment verification required:** cannot be closed in this sandbox or without approved connected infrastructure.
- **Policy decision required:** requires an authorized clinic/security choice rather than an inferred code change.

## 3. Initial repository state

Before this report was created:

- branch: `codex/physiocare-integration-2026-10-31`;
- HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`;
- upstream: `origin/codex/physiocare-integration-2026-10-31`, ahead 0 / behind 0;
- tracked modifications: **88**;
- untracked paths: **66**;
- total changed paths: **154**.

This independently matches the Phase 24A.8 reported state. The two Phase 24A.8 files were present and untracked:

- `docs/PHASE_24A8_PASSWORD_POLICY_DECISION_PACKAGE.md`;
- `docs/PHASE_24A8_FINAL_OFFLINE_CLOSURE_READINESS_REPORT.md`.

The increase from Phase 24A.7's reported 64 untracked paths to 66 is exactly those two documents. The tracked count remained 88. Because the entire development chain is uncommitted, Git cannot cryptographically attribute changes by phase; nevertheless, current status, the Phase 24A.7 inventory, the Phase 24A.8 inventory, and fresh regression behavior support the conclusion that Phase 24A.8 introduced no application or test change.

## 4. Evidence reviewed

The following requested documents were read:

1. `PHASE_24A6_INDEPENDENT_SECURITY_CLOSURE_REVIEW.md`
2. `PHASE_24A7_RESIDUAL_DEFECT_REMEDIATION_REPORT.md`
3. `PHASE_24A8_PASSWORD_POLICY_DECISION_PACKAGE.md`
4. `PHASE_24A8_FINAL_OFFLINE_CLOSURE_READINESS_REPORT.md`
5. `PHASE_24A5_BACKEND_TEST_ENVIRONMENT_RECOVERY_REPORT.md`
6. `PHASE_24A4_COMBINED_SECURITY_CLOSURE_VERIFICATION.md`
7. `PHASE_24A3_REMAINING_SCREENS_REMEDIATION_REPORT.md`
8. `PHASE_23_SECURITY_REMEDIATION_REPORT.md`
9. `PHASE_22_COMPREHENSIVE_SECURITY_AUDIT.md`
10. `PHASE_21_STAGING_APPROVAL_CHECKLIST.md`
11. `PHASE_20_STAGING_APPROVAL_PACKAGE.md`

Additional closure evidence reviewed:

- `PHASE_24A_CACHE_AND_QUERY_HARDENING_REPORT.md`;
- `PHASE_24A_CLOSURE_REVERIFICATION_REPORT.md`;
- `PHASE_24A2_RESIDUAL_LIST_AND_ANALYTICS_REMEDIATION_REPORT.md`.

Current source evidence included authentication middleware/routes/services; session repositories; API cache/origin middleware; PDF routes/storage/scanner; pagination; analytics, appointment, home-visit, exercise, care-plan, notification, laboratory and user paths; the active React route map; all reviewed screen components; shared page/PDF/auth helpers; Phase 24A.7 directory source; and associated tests.

## 5. Phase 23 security review

### Authentication and sessions

**Verified offline.** Inactive, unknown-account, and wrong-password login attempts share the same generic failure before session creation (`backend/app/services/auth_service.py:156-188`). Refresh rotation binds session/user/token hashes/CSRF, revokes a lost rotation claim, and reloads active user state (`auth_service.py:191-227,261-316`). Access middleware validates token type, live session, expiry, user binding, unsafe-method CSRF, and active account on each authenticated request (`backend/app/middleware/auth.py:20-109`). Therefore deactivated accounts cannot create a new session and an existing session is rejected on its next authenticated request or refresh. Immediate proactive deletion of every session at the moment of deactivation remains operationally unverified.

Cookies remain HttpOnly for access/refresh, Secure in staging/production through configuration, SameSite Lax, and path scoped. CSRF is bound to the stored session hash. Unsafe cross-site origins are rejected before mutation and receive private no-store headers (`backend/app/api/auth.py:30-79`; `backend/app/main.py:94-131`). Login is not accepted by the frontend until `/auth/me` supplies a complete profile. Ambiguous login/profile and failed logout preserve explicit retry paths while private state remains hidden. Authentication changes cancel clinical requests, close PDF viewers, clear CSRF, clear the query cache, and remove the current user (`frontend/src/context/AuthContext.jsx`).

### Clinical PDF protection

**Verified offline; connected scanner/storage/browser behavior blocked.** Clinical downloads require patient ownership; laboratory downloads require patient ownership, current doctor assignment, assigned laboratorian, or administrator role and apply release-state neutrality (`backend/app/api/reports.py:77-117`; `backend/app/api/lab_requests.py:157-176`; `backend/app/services/lab_request_service.py:259-294`). Both response paths set `Cache-Control: private, no-store, no-cache, must-revalidate`, `Pragma: no-cache`, and `Expires: 0`.

Uploads validate type/name/size/structure, write owner-only quarantine files, scan before promotion, delete rejected files, fail closed on scanner error/timeout/invalid verdict, atomically promote approved files, and retain private `0600` files (`backend/app/services/clinical_report_storage.py:166-334`). Application startup rejects an enabled but unready ClamAV adapter (`backend/app/main.py:30-49`). The frontend viewer epoch rejects stale authentication responses and closes object URLs/viewers; patient-history components add patient-switch checks.

### Pagination and query hardening

Current active screen list requests use one-page replacement rather than the obsolete accumulating helpers. The shared helper validates page 1–1000, requests 50 records, deduplicates within a page, shares identical requests, aborts on auth change, and rejects stale generations (`frontend/src/services/clinicalPagination.js`). Backend `page_window` defaults to 50 and caps caller-supplied page size at 100, with stable repository sorting generally ending in `_id`.

Phase 23/24 analytics and exercise totals use database aggregation rather than full browser histories. Appointment availability/conflict paths use authoritative server windows and unique claims. However, section 11 and finding M1 document active residual unbounded/N+1 paths, so broad claims that all internal queries are bounded are not supported.

## 6. Phase 24A screen verification matrix

### Count reconciliation

- Phase 24A.3 named **21** components: 9 patient, 9 admin, 2 doctor, 1 receptionist.
- Phase 24A.2 separately named **5**: `AdminLabRequestsPanel`, common `Notifications`, doctor `HomeVisits`, `LaboratoryDashboard`, and patient `LaboratoryRequests`.
- The union is **26 source components**.
- `frontend/src/App.jsx:55,163-166,196,219,249` routes all role notification links to `pages/common/Notifications.jsx`; `pages/admin/Notifications.jsx` is not imported or routed. The actual active reviewed union is therefore **25 distinct routed components**.

`PASS` below is limited to source and fresh offline test evidence. It is not connected MongoDB, browser E2E, scanner-daemon, private-storage, proxy, or production evidence.

| Active screen | Status | Independent result |
|---|---|---|
| Patient `BookAppointment` | **PASS** | Bounded searchable clinician page; server-owned patient lookup, availability, conflict and slot-claim decisions; current-page/error/empty and booking tests pass. |
| Patient `HomeVisitRequests` | **PARTIAL** | Request, booking and clinician lists are independently paged and patient scoped, but no-preference availability/booking calls `_eligible_home_visit_doctors()`, which loads all doctors and performs per-doctor user plus appointment/schedule work. |
| Patient `PatientAppointments` | **PASS** | Patient ID and lifecycle/future filters precede stable page; frontend replaces pages and handles error/empty states. |
| Patient `PatientCarePlan` | **PASS** | `selection=active_latest` is owner scoped; history is paged and exercise-stage totals aggregate. |
| Patient `PatientDashboard` | **PASS** | Patient-scoped bounded previews and independent aggregate/stat sources; no accumulated history totals. |
| Patient `PatientExercises` | **PASS** | Category/patient/plan filters and assignment joins are server side; pages replace; lifetime totals aggregate. |
| Patient `PatientHistory` | **PASS** | Patient/status filters and stable sort precede page; no unlimited accumulation or false lifetime count. |
| Patient `PatientProgress` | **PASS** | Owner-scoped active/latest plan plus aggregate progress; no full-history browser scan. |
| Patient `PatientReports` | **PASS** | Owner filter and escaped search precede stable page; private PDF authorization/no-store and viewer invalidation pass offline. |
| Patient `LaboratoryRequests` | **PASS** | Patient-owned request/report pages are independent; report IDs deduplicate; download authorization and auth-change viewer invalidation are tested. |
| Admin `AdminDashboard` | **PASS** | Admin-only database aggregates and bounded recent activity; error/loading states tested. |
| Admin `AdminPatientHistory` | **PASS** | Admin-only patient/date scoped dual pages; bounded enrichment and patient-switch PDF guard. |
| Admin `AppointmentBooking` | **PASS** | Server-searchable patient/doctor pages; role-limited projections and authoritative availability/conflict checks. |
| Admin `Billing` | **PASS** | Admin-only status/date page; captured-review/reconciliation is separately bounded by configured batch size. |
| Admin `CarePlanManagement` | **PASS** | Direct authorized patient lookup and bounded plan pages; selected snapshot preserved without whole-directory load. |
| Admin `DemoServices` | **PASS** | The active component always includes a `search` parameter, selecting the bounded entitlement aggregation; other queues and clinician selectors are paged. The same endpoint has an unsafe no-search fallback recorded in finding M1. |
| Admin `ExerciseAssignmentManagement` | **PASS** | Authorized direct patient lookup; plans, assignments and exercises use independent bounded pages; mutation revalidates IDs server side. |
| Admin notification route (`common/Notifications`) | **PASS** | Actual route is authenticated, recipient-scoped, paged, and uses an independent unread count. Historical attribution to `admin/Notifications.jsx` is incorrect. |
| Admin `ReportAuthoring` | **PASS** | Authorized bounded patient selector; report creation revalidates doctor assignment/booking and uses private quarantine. |
| Admin `AdminLabRequestsPanel` | **PASS** | Admin request and laboratorian search pages are bounded; assignment/publication/download roles remain server enforced. |
| Doctor `DoctorDashboard` | **PASS** | Doctor identity derives from session; Mongo summary and independent bounded agenda/released-report pages; pending assignments excluded. |
| Doctor `DoctorPatientHistory` | **PASS** | Non-pending assignment checked before patient history; filters precede stable pages; patient/auth changes reject stale PDF/data. |
| Doctor `HomeVisits` | **PASS** | Doctor-assigned queue is role scoped and paged; frontend replaces pages with error/empty navigation. |
| Receptionist `ReceptionistDashboard` | **PASS** | Reception-only aggregate/schedule/request pages; restricted projections omit clinical and billing fields. |
| Laboratory `LaboratoryDashboard` | **PASS** | Assigned-laboratorian page; role/state controls for upload/finalization/publication; page/auth changes clear private selections. |

Summary: **24 PASS, 1 PARTIAL, 0 FAIL, 0 NOT VERIFIED.**

## 7. Phase 24A.7 administrator directory review

**Assessment: PASS for the offline contract, with exact page-size caveat.**

- Backend authorization: `GET /users/doctors` requires `RoleChecker(["admin"])` (`backend/app/api/users.py:78-90`).
- Safe search: `re.escape()` is used before case-insensitive Mongo regex matching.
- Search fields: name, email, specialization, qualifications, and specialties for the administrator route; public search omits email (`backend/app/repositories/profile_repository.py:49-71`).
- Stable order: `full_name`, then unique `_id`.
- Query structure: one User-to-Doctor aggregation, filter before sort/skip/limit, then a narrow enumerated projection (`profile_repository.py:53-96`). The directory route no longer calls the old unbounded service/N+1 branch.
- Frontend: always sends search (including blank), requests a single page, keys by search/page, resets to page 1, uses `gcTime: 0`, shares identical requests through the helper, rejects stale/auth-cancelled results, and retains schedule/profile-edit workflows (`frontend/src/pages/admin/DoctorsList.jsx`).
- Fresh tests cover role negatives, escaped search, one aggregation/no per-row user lookup, a fictional 1,250-row page-25 result, single-page retention, shared requests, stale ordering, and editing/scheduling contracts.

Exact caveat: the current UI uses **50** records, but the common backend guard permits a direct API caller to request up to **100** (`backend/app/core/pagination.py:8-35`). Therefore “the screen is bounded to 50” is accurate; “the API can never return more than 50” is not. This is informational, not a demonstrated security defect. Connected query plans, index use, regex performance, large-offset latency, and concurrent offset drift remain blocked.

## 8. Phase 24A.8 password-policy review

The source independently confirms:

| Flow | Current minimum | Evidence |
|---|---:|---|
| Public registration backend | 6 | `backend/app/schemas/auth.py:9-12` |
| Public registration frontend | 8 plus confirmation | `frontend/src/pages/common/Register.jsx:9-17` |
| Staff creation backend | 8 | `backend/app/schemas/auth.py:14-19` |
| Staff creation frontend | 8 plus confirmation | `frontend/src/utils/staffManagement.js:20-31` |
| Backend login | No creation minimum | `backend/app/schemas/auth.py:36-38` |

A direct API client can register a public account with 6 or 7 characters. Login compatibility does not reapply a registration minimum, so existing credentials remain usable. Hashing remains Passlib bcrypt. Public duplicate registration remains neutral and performs password-hash work before duplicate resolution. Passwords are not returned by reviewed responses.

No verified-email state/token/endpoint, password-change flow, password-reset/recovery token, or administrator-assisted recovery workflow exists. Staff creation is admin-only, immediately active, and uses an administrator-established initial password that the UI instructs the administrator to share securely. Inactive users are rejected on login and refresh, but a staff deactivation UI/API workflow was not identified.

The Phase 24A.8 decision package consistently labels its 15-character proposal, email verification, recovery, and invitation design as **RECOMMENDATION**, **NOT APPROVED**, **APPROVAL REQUIRED**, or **NOT IMPLEMENTED**. It does not misrepresent them as clinic policy.

Classification: **POLICY DECISION REQUIRED**. No password, email, recovery, staff-role, session, or credential behavior changed in Phase 24A.8 or Phase 24A.9.

## 9. Authentication and session findings

Verified strengths:

- generic failure and synthetic password verification for unknown users;
- inactive rejection before session persistence;
- database-backed session binding/revocation and active-user reload;
- atomic refresh rotation and replay revocation;
- hashed stored refresh/CSRF secrets;
- unsafe-method CSRF and unsafe-origin rejection;
- HttpOnly access/refresh cookies and environment-dependent Secure attribute;
- login profile confirmation, ambiguous-session recovery, privacy-preserving logout failure handling;
- `/auth/me` and authenticated/auth response private no-store policy; and
- auth-change cancellation for lists, caches, CSRF state, and PDF viewers.

No new authentication/session vulnerability was confirmed. Connected multi-worker rate-limit/session behavior and deactivation races remain environment verification items.

## 10. Clinical PDF security findings

Offline authorization, no-store headers, release-state neutrality, ownership/assignment checks, private opaque storage keys, quarantine, fail-closed scanner handling, and stale viewer invalidation remain intact. Fresh full and focused regressions exercise these controls.

The seven socket-free ClamAV protocol tests passed. They verify framing, verdict parsing, readiness responses, closure, and selected fail-closed transport behavior. They do not verify an AF_UNIX client/server exchange, daemon interoperability, storage timeouts through a real socket, real signature detection, deployed private mounts, browser cache, or proxy behavior. Those remain blocked.

## 11. Pagination and analytics findings

Verified strengths:

- all active reviewed screen list components use page replacement rather than `fetchClinicalPages`/`fetchClinicalHistoryPages` accumulation;
- owner, role, assignment, search, date, and status predicates generally precede stable page operations;
- dashboard and exercise totals use Mongo aggregation rather than truncated browser pages;
- appointment conflict and slot decisions remain complete and authoritative rather than page-derived; and
- directory/search regex inputs in the remediated paths are escaped.

Confirmed residual issue M1:

1. `HomeVisitService._eligible_home_visit_doctors()` calls unbounded `ProfileRepository.list_doctors()` and then `UserRepository.get_by_id()` per doctor (`backend/app/services/home_visit_service.py:53-64`). No-preference availability and booking call it (`home_visit_service.py:166-168,264-267`) and then perform per-doctor appointment and effective-schedule work (`home_visit_service.py:177-194,281-300`).
2. `GET /demo-services/entitlements` selects the bounded aggregation only when `search` is present; omission calls `list_admin_entitlements()`, which loads every patient and performs per-patient user and entitlement lookups (`backend/app/api/home_visits.py:44-53`; `home_visit_service.py:107-124`). The current UI always supplies `search`, so `DemoServices` remains PASS, but the API fallback is active.
3. `GET /payments/history` loads every payment attempt for the authenticated patient and fetches one appointment per attempt (`backend/app/api/payments.py:21-25`; `backend/app/services/payment_service.py:603-627`).
4. `GET /users/staff` returns the entire staff collection (`backend/app/api/users.py:60-64`; `backend/app/repositories/user_repository.py:43-44`).

These paths are role/owner scoped and no cross-user disclosure was demonstrated. The consequence is database amplification, response/memory growth, and avoidable latency or resource exhaustion as records grow. The home-visit path is feature/entitlement gated and production demo-mode guards reduce exposure, but it is directly reachable when enabled. Scale/query-plan tests for these branches are absent; existing no-preference tests mock the unbounded helper.

## 12. Fresh test results

All backend tests used the existing recovered Python 3.13 environment from `/private/tmp`, a clean `env -i`, synthetic test secrets, unreachable loopback MongoDB port 1, `physiocare_dev` test identity, disabled payments/reconciliation/scanner startup, disabled plugin autoload, explicit `pytest_asyncio`, and no connected-test opt-in.

| Fresh Phase 24A.9 check | Result |
|---|---:|
| Focused auth/registration/session/directory/API/cache/PDF/production backend selection | **232 passed**, 1 plugin warning, 2.28 s |
| Complete backend suite | **970 passed, 11 failed, 3 skipped**, 1 plugin warning, 6.26 s |
| Backend excluding only `test_clamav_unix_scanner.py` | **969 passed, 3 skipped**, 1 plugin warning, 8.36 s |
| Socket-free ClamAV protocol unit file | **7 passed**, 1 plugin warning, 0.24 s |
| Focused frontend auth/admin/staff/navigation selection | **83 passed** |
| Full frontend suite | **149 passed**, 0 failed/skipped, 4.01 s |
| Frontend lint | **PASS** (`oxlint`) |
| Production build | **PASS**, Vite 8.3.5, **1,838 modules** |
| Asset budget | **74 JS/CSS assets**, zero violations; largest JS 364.5 KiB, CSS 248.4 KiB |
| Python syntax | **162 backend Python files parsed**, zero failures |
| Dependency-lock tests | **2 passed**, 1 plugin warning |
| `pip check` | **No broken requirements found** |
| `npm audit --offline --audit-level=low` | **0 locally cached vulnerabilities**; cache freshness unknown |
| `git diff --check` before this untracked report | **PASS** |

The three skips are the guarded connected account-registration, distributed rate-limit, and report-transaction tests. No skip was added. The recurring warning is the already-imported `pytest_asyncio` assertion-rewrite warning and does not change test collection/results.

## 13. Historical versus fresh test comparison

| Check | Phase 24A.8 historical | Phase 24A.9 fresh | Comparison |
|---|---:|---:|---|
| Focused backend | 232 passed | 232 passed | Exact match |
| Focused frontend | 83 passed | 83 passed | Exact match |
| Full frontend | 149 passed | 149 passed | Exact match |
| Full backend | 970 passed, 11 failed, 3 skipped | 970 passed, 11 failed, 3 skipped | Exact match |
| Backend without socket file | 969 passed, 3 skipped | 969 passed, 3 skipped | Exact match |
| ClamAV protocol units | Covered by full suite | 7 passed separately | Consistent |
| Build/modules | Passed / 1,838 | Passed / 1,838 | Exact match |
| Asset budget | 74 / zero violations | 74 / zero violations | Exact match |
| Python syntax | 162 | 162 | Exact match |
| Lock tests / pip check | 2 passed / clean | 2 passed / clean | Exact match |
| Gitleaks | 6 synthetic fixtures | 6 synthetic fixtures before report | Exact match |

Fresh results substantiate the reported regression baseline. They do not remove the source findings in sections 6, 11, and 16 because current tests do not exercise those branches at realistic cardinality.

## 14. ClamAV environmental limitation

All 11 complete-suite failures are unchanged parametrized cases in `backend/tests/test_clamav_unix_scanner.py`. Each stops at `asyncio.start_unix_server()` while the fake daemon tries to bind its temporary AF_UNIX socket; the sandbox returns `PermissionError: [Errno 1] Operation not permitted` before the application assertion. The one non-binding missing-socket case passes.

Classification: **ENVIRONMENT VERIFICATION REQUIRED**. The observed failures are environmental, but the intended socket behavior is not passed. Socket-free units are useful protocol evidence and are not a replacement for the unchanged socket suite or real-daemon integration.

## 15. Secret-scanning findings

A redacted Gitleaks 8.30.1 current-tree directory scan before this report scanned approximately 8.46 MB and returned exactly **six** findings. The final post-report scan covered approximately 8.50 MB and returned the same six findings, with no Phase 24A.9 path flagged:

- five in `backend/tests/test_api_contract.py`;
- one in `backend/tests/test_schedule_fallback_guard.py`.

They are the previously reviewed synthetic `submission_key` fixtures. No value is reproduced here. This is not a zero-finding result and is not a fresh Git-history scan.

## 16. New findings and severity

### Critical

None confirmed.

### High

None confirmed.

### Medium — M1: residual active unbounded and N+1 query paths

**Confirmed.** Affected paths and evidence are listed in section 11, principally `HomeVisitService._eligible_home_visit_doctors`, the no-search demo-entitlement fallback, patient payment history, and staff listing.

- Impact: database/query amplification, growing response and process memory, latency, and potential authenticated resource exhaustion. No confidentiality or authorization bypass was demonstrated.
- Exploitability: requires an authenticated role; home-visit no-preference additionally requires the feature/entitlement. Repeated requests can trigger work proportional to collection cardinality. Production feature guards lower but do not eliminate the application defect where enabled.
- Recommended remediation: replace no-preference doctor discovery with a bounded/filtered aggregation and explicit allocation strategy; make the entitlement route always use its bounded aggregation even for blank search; paginate payment history and staff; bulk-join required labels; add >1,000 synthetic query-shape and request-count tests plus connected `explain`/scale evidence.
- Release effect: blocks Outcome A and should be remediated/reviewed before Phase 24B authorization or any demo. It does not by itself invalidate Outcome B because the issue is role/feature scoped, transparently classified, and the ordinary offline regression remains intact.

### Low — L1: notification screen evidence-chain/route mismatch

**Confirmed.** Historical Phase 24A.3/24A.5/24A.8 matrices identify `frontend/src/pages/admin/Notifications.jsx` as an active admin screen. `frontend/src/App.jsx` imports only `pages/common/Notifications.jsx` for notification routes, including `/admin/notifications`; the admin-specific component has no import/call site.

- Impact: test/report evidence can be attributed to the wrong component, and intended admin system-alert functionality may be mistaken for the reachable recipient-notification page. No authorization bypass or sensitive-data disclosure was found; the active common route is authenticated and recipient scoped.
- Recommended remediation: obtain a product decision on whether system alerts are intended; then either route and test the admin-specific component or remove it from the active-screen inventory/dead code. Correct future matrices to name the actual component.
- Release effect: documentation/product-scope correction before a later closure claim; it does not block the narrow conditional offline closure.

### Informational

- The admin clinician UI uses 50-row pages, while the API permits up to 100.
- Six Gitleaks findings remain synthetic test fixtures, not a zero-finding scan.
- Offset pagination can drift under concurrent writes and stops at page 1,000.
- The recovered dependency graph is locally reproducible but not a durable approved package mirror or fresh Python vulnerability audit.

### Policy decision required

Password minimum, existing-account transition, email ownership, recovery, staff invitation/onboarding, and related operational/privacy policy remain unresolved. This is not reclassified as a code vulnerability.

### Environment verification required

ClamAV Unix sockets/daemon, connected Mongo authorization/query/index behavior, deployed storage, real browser journeys, production ingress, and backup restoration remain unverified.

## 17. All eight connected release gates

| Gate | Required evidence | Evidence exists? | Why blocked / closure requirement | Owner approval |
|---|---|---|---|---|
| 1. Connected multi-clinician authorization | Approved isolated fictional identities; deliberately mismatched list/detail/mutation/download cases across roles and workers | **No** | Offline mocks/source are not connected proof. Close with sanitized negative/positive results and zero unintended mutation. | Project, privacy/security, test/data and DB owners |
| 2. MongoDB query plans and realistic-scale performance | Approved representative fictional dataset; `explain`, latency, memory, concurrency and residual-query measurements | **No** | No database was contacted; M1 has no scale proof. Close with accepted thresholds and plans for every critical query. | DB, backend and project owners |
| 3. Actual database index verification | Live isolated index inventory and uniqueness/partial-index behavior, especially appointment slot/submission claims | **No** | Model declarations do not prove deployed indexes. Close with actual index listing and collision/concurrency evidence. | DB and backend owners |
| 4. Socket-capable ClamAV protocol/scanning | Unchanged fake-server suite in a socket-capable environment plus approved real daemon, clean/malicious/error/timeout cases | **No** | AF_UNIX bind is denied; protocol units are not integration. Close only with socket and daemon evidence without weakening fail-closed tests. | Security/scanner and deployment owners |
| 5. Private storage integration/access | Approved private mount/service, permissions, separate roots, atomic promotion, cleanup, backup and authorized/denied downloads | **No** | Only local temporary/source evidence exists. Close with deployed inventory and access-negative tests. | Storage/security, backend and privacy owners |
| 6. Browser end-to-end journeys | Approved fictional-data target and real-browser multi-role login/logout/retry, booking/conflict, account/patient switching, search, report/PDF and error paths | **No** | Node render/source tests are not browser E2E. Close with redacted traces/screenshots and cleanup evidence. | Frontend, test, privacy and project owners |
| 7. Production proxy/TLS/cookie/cache | Production-like ingress, certificate/Host/origin/proxy trust, Secure cookie, CSRF, private/no-store and security-header behavior | **No** | Application configuration cannot prove deployed proxy/browser behavior. Close with approved topology and negative network/browser evidence. | Security, deployment and project owners |
| 8. Backup and restore | Coordinated fictional DB/file backup and restore to a separate approved destination with RPO/RTO and consistency checks | **No** | No approved infrastructure or restore target exists. A backup job alone is insufficient. | DB, storage, deployment and project owners |

All eight gates remain **BLOCKED** and require explicit target/scope/owner approval before execution.

## 18. Final Phase 24A outcome

**Outcome B — Conditional Offline-Scope Closure.**

The independent review supports the prior conditional closure only after adding these conditions:

1. M1 must be remediated and independently reviewed before Phase 24B or a demo decision.
2. L1 must be reconciled in the active screen inventory/product routing evidence.
3. Password/email/recovery/staff decisions remain `POLICY DECISION REQUIRED`.
4. The 11 AF_UNIX cases remain an accepted offline-environment exception only; the ClamAV gate remains blocked.
5. All eight connected gates remain blocked and cannot be converted to PASS from this report.

Outcome A is not available. Outcome C is not selected because the confirmed issue is availability/scalability rather than an authorization/data-isolation failure, is scoped by authentication/features, and the otherwise applicable offline regression is stable. This report does not claim production readiness.

## 19. Phase 24B recommendation

**Phase 24B remains BLOCKED / NOT STARTED.** The next approved milestone should be a narrowly scoped Phase 24A residual-query and evidence-correction pass, followed by independent review and explicit clinic/security policy decisions. Phase 24B authorization must be a separate owner decision after those conditions are satisfied; it is not granted here.

## 20. Demo, staging and production authorization status

- Client demonstration: **HOLD / NOT AUTHORIZED**.
- Staging provisioning or validation: **BLOCKED / NOT AUTHORIZED**.
- Production: **NOT READY / NOT AUTHORIZED**.
- Payment/provider/scanner/database connected actions: **NOT AUTHORIZED**.

Successful offline tests do not change these decisions.

## 21. Recommended next milestone

Prepare a review-only plan for a focused residual Phase 24A pass that:

1. bounds and bulk-joins the confirmed M1 paths without truncating appointment conflict or clinician-allocation correctness;
2. adds scale/query-count tests for no-preference home visits, blank-search entitlements, staff, and payment history;
3. reconciles the notification route/component and the 25-active-screen inventory;
4. obtains explicit clinic/security decisions from the Phase 24A.8 package; and
5. returns for independent offline review before any Phase 24B, connected gate, demo, staging, or production action.

No fix, commit, push, deployment, provisioning, migration, payment, database access, or external-service access is authorized by this report.
