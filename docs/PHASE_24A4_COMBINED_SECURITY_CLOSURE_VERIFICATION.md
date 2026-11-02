# Phase 24A.4 — Combined Security Closure Verification

Assessment date: 2026-11-02

Repository: `/Users/boddisuryakathyakeya/PhysioCare/PhysioCare`

Branch: `codex/physiocare-integration-2026-10-31`

HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

**Phase 24A closure: NOT RECOMMENDED. Phase 24B: BLOCKED. Client demonstration: HOLD. Production: FAIL.**

This pass re-read all six required Phase 22–24A.3 reports, inspected the current implementations and regression tests, and rechecked the 21 Phase 24A.3 screens plus the five Phase 24A.2 screens. It found and remediated five confirmed defect classes:

1. `AdminPatientHistory` could open a completed PDF response after the route changed to another patient.
2. Authentication changes cancelled list requests but did not close or invalidate outstanding PDF viewers application-wide.
3. `BookAppointment` and `HomeVisitRequests` loaded the complete public clinician directory instead of replacing bounded pages.
4. `AdminLabRequestsPanel` loaded the complete laboratory-staff selector.
5. Bounding the public clinician endpoint exposed a separate landing-page regression: `PublicHome` could search only the first page and silently hide later eligible clinicians.

The fixes add identity/epoch checks for PDF responses, application-wide PDF cancellation on authentication changes, bounded server-side selector search, stable sorting, current-page navigation, and regression tests. Public clinician search includes only published name/profile fields and does not search email.

Fresh frontend verification is clean: **142 passed**, lint passed, the production build passed, and **74 JS/CSS assets** stayed within budget. Python syntax, static lock consistency, offline Node lock installation, offline Node advisory-cache lookup, whitespace, and the redacted current-tree secret scan were also executed.

The decisive evidence gap is the backend. The historical pinned virtual environment no longer exists, and an exact offline recreation cannot resolve `annotated-doc==0.0.5` from the available cache. **No current backend pytest test was executed.** This is an environment/lock-reproduction blocker, not an observed application test failure, but historical counts are not substituted for current evidence. Consequently all 21 screen results are **PARTIAL**, even where current source and frontend evidence are strong. The connected release gates remain **BLOCKED**.

No database, provider, scanner daemon, staging service, protected record, deployment, migration, payment, refund, commit, push, branch switch, stash, reset, or cleanup operation was performed. No `.env` file or credential was read or changed.

## 2. Repository and working-tree state

- Branch and HEAD match the requested baseline. Upstream is `origin/codex/physiocare-integration-2026-10-31`; ahead/behind is `0/0`.
- Initial Phase 24A.4 observation: 84 modified tracked paths and 55 untracked paths. Existing Phase 16–24A.3 work and unrelated-looking user work were treated as user-owned and preserved.
- Immediately before this report was created: 87 modified tracked paths and 56 untracked paths. This report adds one untracked documentation path.
- Final post-report status: 87 modified tracked paths and 57 untracked paths, 144 changed paths in total.
- The initial tracked diff was approximately 3,421 insertions and 1,162 deletions. This phase intentionally changed only the residual-remediation paths listed in section 19.
- No destructive Git command was used. No commit or push occurred.

The Phase 24A.3 groups are represented by the nine patient components, nine admin components, two doctor components, and one receptionist component listed in section 6. Earlier Phase 22–24A documents and all new backend/frontend test files remain untracked as they were found. Authorship of unrelated pre-existing changes was not inferred.

## 3. Phase 22 findings rechecked

| Finding | Current classification | Current evidence and limit |
| --- | --- | --- |
| H1 connected operational security | **BLOCKED** | Real scanner, private storage, connected Mongo authorization, ingress, backups and multi-worker behavior were not available and were not contacted. |
| M1 inactive login session issuance | **PASS** in source; current test execution **PARTIAL** | `backend/app/services/auth_service.py:165` combines inactive status with the generic credential failure before session creation. Access middleware rejects inactive users at `backend/app/middleware/auth.py:103`; refresh rejects them at `auth_service.py:311`. Current backend tests could not execute. |
| M2 PDF/authenticated-response caching | **PASS** at application-code level; ingress **BLOCKED** | PDF routes set `private, no-store, no-cache, must-revalidate` (`backend/app/api/reports.py:113`, `backend/app/api/lab_requests.py:172`). `backend/app/main.py:101-129` applies `private, no-store` to authenticated JSON and auth/session responses, including unsafe-origin early rejections. Proxy behavior is unverified. |
| M3 unbounded clinical lists | **PARTIAL** | The 21 screens and five Phase 24A.2 screens use bounded server-side pages/aggregates. This pass fixed three remaining selector paths and the public directory. Legacy unpaged repository methods and staff/catalogue/payment-maintenance assumptions remain; connected scale and plans are blocked. |
| L1 six-character public password minimum | **BLOCKED** on clinic policy | `backend/app/schemas/auth.py` still permits six characters. A clinic-approved password, email-ownership and recovery policy is required; this pass did not invent one. |
| I1 ingress security headers/Host policy | **BLOCKED** | CORS and unsafe-origin controls exist; actual HSTS/CSP/frame/referrer/content-type/Host and TLS behavior needs the approved ingress. |
| I2 environment intent | **PASS** structurally; deployment **BLOCKED** | Settings construction, lifespan, development/staging/production guards, `run.py`, and `run_production.py` fail closed for supported entry points. Admission policy still has to select the intended environment. |
| I3 payment/file operational controls | **PARTIAL/BLOCKED** | Server-side payment verification and fail-closed PDF quarantine are implemented. No provider, real scanner or private-storage integration was run. |
| I4 secret-scan candidates | **PASS** for disposition, not a zero-finding scan | Fresh redacted scan returned six historical current-tree synthetic `submission_key` fixtures; exact safe disposition is in section 14. |

No confirmed Critical or High application-code vulnerability was found. That is a bounded source/offline conclusion, not a penetration-test or production-readiness claim.

## 4. Phase 23 fixes rechecked

### Authentication and session rotation

- Login preserves a generic failure for unknown, invalid-password and inactive users and creates no inactive session.
- Access checks JWT type, session binding/revocation/expiry, unsafe-method CSRF and active user state.
- Refresh validates the active user and stored hashed refresh/CSRF state before atomically rotating; a lost rotation claim revokes the session as refresh-token reuse.
- Access and refresh cookies are HttpOnly; staging/production make them Secure; SameSite is `lax`; CSRF is intentionally readable and path-scoped (`backend/app/api/auth.py:33-78`).
- The frontend considers login ready only after a valid `/auth/me` profile. Ambiguous login and profile failure remain retryable without another password submission.
- Failed logout hides private state but remains visibly unconfirmed and retryable.
- Query cache, in-flight clinical list requests, and now all registered PDF viewers are cleared/cancelled on login, logout and global auth logout (`frontend/src/context/AuthContext.jsx:70-74,94-99,157-172`).

### PDF delivery and storage

- General reports are patient-owner downloads; lab reports permit patient owner, currently assigned doctor, assigned laboratorian and admin according to report state. Patient/doctor access remains released-only (`backend/app/services/lab_request_service.py:261-283`).
- Report authoring retains doctor assignment/booking checks and admin authorization.
- Separate quarantine/approved roots, opaque storage keys, structure/size validation, private permissions, fail-closed scanner handling and cleanup audit remain in the storage services/configuration.
- Scanner safety is **not** claimed: no real ClamAV protocol or socket test executed in this pass.

### Pagination and query hardening

- `backend/app/core/pagination.py` enforces pages 1–1,000 and sizes 1–100; UI page replacement uses 50.
- Current repository paths apply owner/role/assignment/date/status/search predicates before stable sort/skip/limit. Domain sort keys end in `_id` where relevant.
- `frontend/src/services/clinicalPagination.js` validates response bounds, replaces pages, deduplicates concurrent identical requests, aborts on auth changes and rejects stale generations.
- Offset drift and page-1,000 ceilings remain design limitations. Connected index/query-plan evidence is blocked.

## 5. Phase 24 and 24A fixes rechecked

- Authenticated JSON and unsafe-origin early rejection now receive private no-store headers.
- Analytics uses Mongo aggregation/count paths rather than full appointment/doctor materialization for its published metrics.
- Appointment/schedule checks use date-scoped database candidates and remain backend authoritative; they are not inferred from a truncated browser list.
- Patient, admin, doctor and reception current-page screens no longer retain an arbitrary 1,000-record browser accumulation.
- Five Phase 24A.2 screens remain bounded in current source:

| Screen | Current result | Evidence / limit |
| --- | --- | --- |
| `AdminLabRequestsPanel` | **PARTIAL** | Admin-only request pages; this pass added bounded name-search/page replacement for laboratorians. Frontend test passes; backend test exists but could not execute. |
| Common `Notifications` | **PARTIAL** | Recipient-scoped current pages and separate unread count; backend current execution unavailable. |
| Doctor `HomeVisits` | **PARTIAL** | Doctor role/assignment scoped current pages; backend current execution unavailable. |
| `LaboratoryDashboard` | **PARTIAL** | Laboratorian-assigned current pages and upload/release rules; backend current execution unavailable. |
| Patient `LaboratoryRequests` | **PARTIAL** | Patient-owner request/report pages and authorized PDF preview; backend current execution unavailable. |

## 6. Phase 24A.3 Group A, B and C screen matrix

Every status below is **PARTIAL** because current backend regression execution is unavailable. “Source verified” means the actual current route/service/repository was inspected; it does not substitute historical test counts.

| Group / screen | Frontend | Backend route → service/repository | Authorization, paging and current evidence | Status |
| --- | --- | --- | --- | --- |
| A `BookAppointment` | `frontend/src/pages/patient/BookAppointment.jsx` | `/users/public/doctors`, `/appointments/availability`, `/appointments`, `/appointments/{id}` → `UserService`/`ProfileRepository`; `AppointmentService`/`AppointmentRepository` | Public directory is active, published-field searchable, stable and bounded; payment-resume lookup is patient-owned; availability/create are authoritative. Fresh frontend selector/booking tests pass. | **PARTIAL** |
| A `HomeVisitRequests` | `frontend/src/pages/patient/HomeVisitRequests.jsx` | `/users/public/doctors`, `/home-visit-bookings/*`, `/appointments/me/home-visits`, `/home-visit-requests/me` → `UserService`, `HomeVisitService`, `AppointmentService` and scoped repositories | Active home-visit-capable clinicians filter before page; own bookings/requests have independent pages and owner predicates. Fresh frontend tests pass. | **PARTIAL** |
| A `PatientAppointments` | `frontend/src/pages/patient/PatientAppointments.jsx` | `/appointments/me/history` → `AppointmentService`/`AppointmentRepository` | Authenticated patient ID, status/future filters before stable page; truthful current-page state. | **PARTIAL** |
| A `PatientCarePlan` | `frontend/src/pages/patient/PatientCarePlan.jsx` | `/care-plans/me/active`, `/care-plans/patient/*` → `CarePlanService`/`CarePlanRepository` | Patient ownership or admin/assigned-doctor boundary precedes active/latest selection and history paging; stage totals aggregate. | **PARTIAL** |
| A `PatientDashboard` | `frontend/src/pages/patient/PatientDashboard.jsx` | bounded appointment/lab/home preview routes → corresponding services/repositories | Patient owner scope, bounded future/recent previews, aggregate metrics not inferred from page length. | **PARTIAL** |
| A `PatientExercises` | `frontend/src/pages/patient/PatientExercises.jsx` | `/exercises`, `/exercise-assignments/me`, progress stats → `ExerciseService`/`ExerciseRepository` | Patient/plan scope, category before page, bounded assignment join, aggregate lifetime completion. | **PARTIAL** |
| A `PatientHistory` | `frontend/src/pages/patient/PatientHistory.jsx` | `/appointments/me/history` → `AppointmentService`/`AppointmentRepository` | Patient ownership and status filter precede date/time/ID page; no browser lifetime totals. | **PARTIAL** |
| A `PatientProgress` | `frontend/src/pages/patient/PatientProgress.jsx` | active/latest plan and progress-stat routes → `CarePlanService`, `ExerciseService` and repositories | Patient-derived plan selection and aggregate stats; no full history retained by screen. | **PARTIAL** |
| A `PatientReports` | `frontend/src/pages/patient/PatientReports.jsx` | `/reports`, `/reports/{id}/download` → `ReportService`/`ReportRepository` | Patient ownership before escaped title/category search and stable page; separate download ownership/no-store; page/identity viewer cleanup. | **PARTIAL** |
| B `AdminDashboard` | `frontend/src/pages/admin/AdminDashboard.jsx` | `/analytics/stats`, `/analytics/admin-daily-activity`, bounded appointments → `AnalyticsService`, `AppointmentService` and repositories | Admin role; Mongo aggregation for counts/buckets; bounded recent list. | **PARTIAL** |
| B `AdminPatientHistory` | `frontend/src/pages/admin/AdminPatientHistory.jsx` | `/users/patients/{id}/history`, lab report file → `AdminPatientHistoryService`, appointment/lab repositories | Admin role; patient/date predicates before two stable pages; new patient identity check closes stale PDF. | **PARTIAL** |
| B `AppointmentBooking` | `frontend/src/pages/admin/AppointmentBooking.jsx` | `/users/patients`, `/users/doctors`, `/appointments/availability`, admin/reception create → `UserService`, `AppointmentService` and repositories | Role-appropriate server selectors; availability/conflict and slot claim remain backend decisions. | **PARTIAL** |
| B `Billing` | `frontend/src/pages/admin/Billing.jsx` | `/appointments/admin/billing`, payment reconciliation → `AppointmentService`, payment service/repositories | Admin role; date/status filters before bounded page; capture reconciliation separate from page counts. | **PARTIAL** |
| B `CarePlanManagement` | `frontend/src/pages/admin/CarePlanManagement.jsx` | direct patient plus `/care-plans/patient/{id}` → `UserService`, `CarePlanService` and repositories | Admin or assigned doctor; direct scoped patient lookup and bounded plans; selected snapshot retained. | **PARTIAL** |
| B `DemoServices` | `frontend/src/pages/admin/DemoServices.jsx` | demo entitlement/request/scheduled-home routes and bounded doctors → demo/home services/repositories | Admin role; filters/search before independent pages; production demo guard remains fail-closed. | **PARTIAL** |
| B `ExerciseAssignmentManagement` | `frontend/src/pages/admin/ExerciseAssignmentManagement.jsx` | direct patient, plans, exercises and assignments → `UserService`, `ExerciseService` and repositories | Admin/assigned doctor checks; bounded pages/search and bounded label projections. | **PARTIAL** |
| B `Notifications` | `frontend/src/pages/admin/Notifications.jsx` | admin daily aggregate and stats → `AnalyticsService`/repositories | Admin-only aggregate; no clinical appointment list fetched for system alerts. | **PARTIAL** |
| B `ReportAuthoring` | `frontend/src/pages/admin/ReportAuthoring.jsx` | role-scoped `/users/patients`, `POST /reports` → `UserService`, `ReportService` and repositories | Admin or assigned-doctor patient selector; create path revalidates authorization and private PDF handling. | **PARTIAL** |
| C `DoctorDashboard` | `frontend/src/pages/doctor/DoctorDashboard.jsx` | `/appointments/doctor/summary`, bounded doctor agenda and released reports → appointment/lab services/repositories | Authenticated doctor identity, non-pending assignment predicates and Mongo aggregate totals; independent pages. | **PARTIAL** |
| C `DoctorPatientHistory` | `frontend/src/pages/doctor/DoctorPatientHistory.jsx` | `/users/doctor/patients/{id}/history`, lab report file → `DoctorHistoryService`, appointment/lab repositories | Assignment check before patient lookup; patient/doctor/date/status predicates before pages; stale PDF patient guard. | **PARTIAL** |
| C `ReceptionistDashboard` | `frontend/src/pages/receptionist/ReceptionistDashboard.jsx` | reception summary/schedule/home routes → appointment/home services/repositories | Reception role; restricted projections omit reasons, symptoms, reports and billing; independent bounded queues and DB count. | **PARTIAL** |

Summary: **0 PASS, 21 PARTIAL, 0 FAIL, 0 BLOCKED at screen level.** Connected gates are recorded separately in section 17. No screen is marked PASS solely from a prior report.

## 7. Authentication and session results

**Application-code assessment: PASS; current backend regression evidence: PARTIAL; connected behavior: BLOCKED.**

- Deactivation denies new login, existing access on the next request, refresh, and CSRF refresh. Existing database sessions are not proactively deleted at the moment of deactivation, but they cannot authorize once the active-user check runs. A connected deactivation race remains unmeasured.
- Distributed throttling uses stored hashed identifiers and fail-closed configuration in staging/production; multi-worker/connected behavior is blocked.
- Registration preserves a neutral public success shape and transaction design; connected commit/rollback remains opt-in and blocked.
- Refresh credentials and CSRF values are stored hashed; atomic rotation and replay revocation are present.
- Startup validation is reached through Settings creation, direct app import/lifespan and both launchers. An operator-selected development identity still requires deployment admission controls.
- Frontend private-data clearing now includes PDF viewer cancellation. Fresh direct unit tests cover stale and current viewer generations.

## 8. Clinical PDF and report security results

**Offline application assessment: PARTIAL.** Route/service authorization, no-store headers, private storage separation and fail-closed scanner code were inspected. Current backend tests did not execute; real scanner/storage and browser behavior are blocked.

The new `openPdfBlob` epoch closes all tracked viewers when authentication changes and refuses a response from an older epoch. `AdminPatientHistory` now independently snapshots the route patient ID, closes its viewer on patient switch/unmount, and refuses mismatched responses. `DoctorPatientHistory` already had the equivalent patient guard. Server authorization remains the final control even when a frontend viewer is prepared.

No claim is made that mocked scanner tests establish malware-scanning safety. The current fake Unix-socket suite was not reached because the Python environment could not be reproduced.

## 9. Appointment and scheduling results

**Source assessment: PASS; current backend execution: PARTIAL; connected legacy/index evidence: BLOCKED.**

- Availability is calculated from server schedule rules and date-scoped active appointment candidates.
- Booking validates the effective slot and checks occupancy before insert. A unique partial `slot_claim` index is the concurrency backstop; `DuplicateKeyError` becomes conflict rather than double booking.
- Cancellation atomically changes status and unsets `slot_claim`; patient and reception paths enforce ownership/role and the 24-hour cutoff. Captured-payment cancellation is flagged for reconciliation.
- No rescheduling workflow exists; it was not invented in this pass.
- Legacy records without canonical `starts_at`, especially same-day behavior, remain a connected-data/preflight limitation. No production or protected database was accessed.
- Actual unique-index presence, query plan and concurrent connected booking remain blocked.

## 10. Dashboard and analytics results

**Source assessment: PASS for bounded shapes; connected performance: BLOCKED.**

- Admin metrics use `$match`/`$facet`/`$group` and counts; recent records are bounded.
- Doctor totals use doctor-scoped aggregation; agenda/reports are separate current pages.
- Reception active count is database-derived; both coordination queues use restricted projections and bounded pages.
- Patient dashboard previews are owner-scoped and bounded; summary definitions are not recomputed from page lengths.
- Exercise statistics and stage summaries use aggregation/projection paths in the changed screens.
- No current screen-level N+1 defect was confirmed. Some page formatting uses bounded bulk lookups. Real explain plans, index selectivity and high-cardinality specialization groups remain blocked.

## 11. Role and ownership isolation

**Source/test-inventory assessment: PARTIAL.**

- Patient: own appointments, reports, lab records, plans, assignments, notifications and payment lookups derive identity from the session.
- Doctor: assigned-patient checks precede history/detail/report access; pending assignments do not grant access.
- Admin: explicit admin dependencies protect patient administration, billing, analytics, laboratory publication and staff controls.
- Receptionist: dedicated response models/projections exclude clinical history, reasons, symptoms, reports, care plans and billing.
- Laboratorian: assignment is required to prepare/replace a report; released files cannot be silently replaced.
- Notification recipient IDs and payment appointment ownership are enforced server-side.

The repository contains extensive synthetic role-negative and cross-patient tests (`test_api_contract.py`, `test_pdf_cache_headers.py`, `test_clinical_pagination.py`, the Phase 24A query/screen files, and auth/session files), but none executed in the current environment. Approved connected multi-clinician and deliberately mismatched identity tests remain required.

## 12. Database and test safety

**PASS for static safety review; no connection attempted.**

- `backend/tests/conftest.py:11-15` defaults to `ENVIRONMENT=test`, `mongodb://127.0.0.1:1/physiocare_dev`, and `DATABASE_NAME=physiocare_dev`; port 1 is deliberately unreachable.
- Development requires the loopback-only, credential-free `physiocare_dev` identity and rechecks it before client initialization (`backend/app/core/config.py:291-335`).
- Staging and production have separate name/host/TLS/credential/storage/payment/scanner constraints.
- Connected tests require explicit mode, exact database/host identity and acknowledgement and otherwise skip.
- No test configuration weakens the production validators. Synthetic fixtures use `.invalid` identities and synthetic keys.
- No MongoDB client, migration, index creation, provider, scanner, external network or protected data was used in this phase.

## 13. Dependency and lock results

| Check | Classification and result |
| --- | --- |
| Python lock shape/direct consistency | **PASS:** 48 exact lock pins; all 15 direct pins matched after normalizing extras; zero static mismatches. |
| Python clean offline lock installation | **BLOCKED:** `/private/tmp/physiocare-phase24a4-venv/bin/python -m pip install --no-index -r backend/requirements.lock` exited 1 because `annotated-doc==0.0.5` is absent from available offline artifacts. |
| Python advisory lookup | **BLOCKED:** no current offline-complete advisory source is available and network access was not used. A lock match is not a vulnerability audit. |
| Node clean offline lock installation | **PASS:** temporary `npm ci --offline --ignore-scripts` installed 177 packages and audited 178 from `package-lock.json`. |
| Node advisory cache | **PASS with limitation:** `npm audit --offline` reported zero vulnerabilities; advisory-cache freshness is unknown, so no current-online claim is made. |

## 14. Secret-scanning result

Gitleaks 8.30.1 ran against the current working directory with `--redact=100` and a temporary JSON report. It exited **1** with exactly **six** findings:

- `backend/tests/test_api_contract.py`: five `generic-api-key` findings at lines 1078, 1171, 1222, 1256 and 1284.
- `backend/tests/test_schedule_fallback_guard.py`: one `generic-api-key` finding at line 181.

These are the same historical current-tree locations documented in Phases 22, 24, 24A.2 and 24A.3. Prior AST/test-context review classifies them as fictional `submission_key` idempotency fixtures. No new Phase 24A.4 implementation path was flagged. Candidate values were not printed or copied. This is **not** a zero-finding scan and does not prove absence of other secret classes or remote-history findings.

## 15. Exact fresh commands and results

| Command / scope | Current result |
| --- | --- |
| `npm test` (`frontend/`) | **Exit 0: 142 passed, 0 failed/skipped.** Includes two new PDF-viewer session tests and updated bounded-selector/static contracts. |
| `npm run lint` (`frontend/`) | **Exit 0.** |
| `npm run build -- --configLoader runner --outDir /private/tmp/physiocare-phase24a4-build --emptyOutDir` | **Exit 0:** Vite 8.3.5, 1,838 modules transformed. |
| Fresh temporary-build budget, 450 KiB JS / 300 KiB CSS | **Exit 0:** 74 JS/CSS assets checked, zero violations. |
| Python `ast.parse` over `backend/**/*.py` | **Exit 0:** 159 files parsed. |
| Static exact lock/direct-pin check | **Exit 0:** 48 exact lock pins, 15 direct pins, zero mismatches after extras normalization. |
| Temporary `npm ci --offline --ignore-scripts` | **Exit 0:** 177 packages installed; 178 audited; zero vulnerabilities reported by local cache. |
| `npm audit --offline` | **Exit 0:** zero vulnerabilities reported; cache freshness unknown. |
| `gitleaks dir --no-banner --redact=100 --report-format=json --report-path=/private/tmp/physiocare-phase24a4-final-gitleaks.json .` | **Exit 1:** six findings in the final tree; disposition in section 14. |
| `git diff --check` | **Exit 0** after report creation. |

## 16. Full backend suite outcome

**BLOCKED — zero current backend tests executed.**

The first focused pytest attempt could not start because the historical interpreter path no longer existed. A fresh temporary virtual environment was created outside the repository. Exact offline installation then failed at `annotated-doc==0.0.5`; attempts to use only locally available cached versions also lacked exact transitive pins. The system interpreter lacks required packages including Beanie/Motor/PyMongo and is not an acceptable substitute for the lock.

The Phase 24A.3 results (**952 selected offline passed; broader 953 passed/11 fake-ClamAV socket failures**) are historical context only. This report does not claim those results for the current tree, does not claim a current 11-failure scanner outcome, and did not weaken or skip scanner tests to improve counts.

## 17. Connected release gates

All required connected gates remain **BLOCKED**:

1. Multi-clinician authorization against an approved connected MongoDB environment.
2. MongoDB explain plans and realistic-scale performance.
3. Actual index verification, including the unique partial slot-claim index.
4. Socket-capable ClamAV protocol/scanning tests and a real scanner daemon.
5. Private storage integration, permissions, cleanup and access verification.
6. Browser journeys for login, failed logout/retry, booking/conflict, patient/account switching, reports and PDF access.
7. Production proxy, TLS, Secure-cookie, Host/security-header and cache behavior.
8. Backup and restore verification.

Provider Test Mode/reconciliation/refund work, if included in launch scope, also requires separate approval and remains blocked. No external service was contacted.

## 18. Remaining defects, limitations and closure decision

### Confirmed open or blocked limitations

- **Backend regression execution — BLOCKED:** the exact offline Python environment is not reproducible from available artifacts. This prevents a current focused/full backend verdict.
- **Public password/email recovery policy — BLOCKED:** clinic decision required.
- **Legacy/internal unpaged methods — PARTIAL:** active Phase 24A screens use paged paths, but compatibility methods and staff/catalogue/payment-maintenance assumptions remain. Remove or bound only after caller/cardinality review; appointment conflict candidates must not be truncated.
- **Offset pagination — PARTIAL:** page drift under concurrent writes and the 1,000-page ceiling remain. No eligible record is silently hidden within the changed UI contracts, but page >1,000 is rejected explicitly.
- **Legacy appointment data — BLOCKED:** same-day records without canonical `starts_at` and actual slot/index drift require the read-only preflight on an approved data export/target.
- **Operational scanner/storage/proxy/database/backups/browser evidence — BLOCKED.**

### Recommended decision

Phase 24A cannot be recommended for closure because relevant backend security regressions have no current executed result and all 21 screens therefore have incomplete evidence. No unresolved Critical or High application-code defect was confirmed, and the current frontend/static checks are clean, but that is insufficient for the requested closure standard.

**Client demo: HOLD.** Reassess only after an exact locked backend environment produces a current focused and full offline result, followed by an approved fictional-data browser smoke test.

**Production: FAIL / NOT READY.** Connected gates, clinic policies, independent review and explicit release approval remain absent.

**Phase 24B: do not start.**

## 19. Phase 24A.4 files changed

Residual remediation changed these paths:

- `backend/app/api/users.py`
- `backend/app/repositories/profile_repository.py`
- `backend/app/repositories/user_repository.py`
- `backend/app/services/user_service.py`
- `backend/tests/test_authenticated_cache_headers.py`
- `backend/tests/test_phase24a3_admin_group_b2.py`
- `frontend/src/context/AuthContext.jsx`
- `frontend/src/pages/admin/AdminLabRequestsPanel.jsx`
- `frontend/src/pages/admin/AdminPatientHistory.jsx`
- `frontend/src/pages/common/PublicHome.jsx`
- `frontend/src/pages/patient/BookAppointment.jsx`
- `frontend/src/pages/patient/HomeVisitRequests.jsx`
- `frontend/src/utils/openPdfBlob.js`
- `frontend/tests/admin-group-b2.test.mjs`
- `frontend/tests/booking-rendered-flow.test.mjs`
- `frontend/tests/clinical-pagination.test.mjs`
- `frontend/tests/navigation-contract.test.mjs`
- `frontend/tests/pdf-viewer-session.test.mjs`
- `docs/PHASE_24A4_COMBINED_SECURITY_CLOSURE_VERIFICATION.md`

Several of these paths already contained Phase 22–24A.3 modifications; this list identifies paths touched during the residual-remediation work, not exclusive authorship of their full diff. No worktree change was made outside the intended security verification/remediation/documentation scope.
