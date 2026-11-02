# Phase 23 Security Remediation — Clinical PDF Cache Protection and Bounded Lists

**Date:** 2026-11-01  
**Branch / HEAD:** `codex/physiocare-integration-2026-10-31` / `5eaced696a156ca74233fd04252fea52345d8af8`  
**Phase 23B PDF finding:** **FIXED for the identified backend PDF routes**, verified by actual HTTP response tests. Connected staging and ingress behavior remain unverified. **Client demo: HOLD. Production: FAIL.**

## Original finding and root cause

Phase 22 finding M2 observed that private clinical PDF responses did not explicitly prevent browser or intermediary caching. The two PDF delivery handlers constructed Starlette `FileResponse` objects with a PDF media type and attachment filename, but without `Cache-Control`, `Pragma`, or `Expires` headers. No application-wide middleware supplied them. Because these are cookie-authenticated GET responses containing clinical data, an explicit no-store policy belongs on the actual response and must also be checked at the eventual ingress.

## Delivery-path inventory

| Route | Use | Authorization and storage path |
| --- | --- | --- |
| `GET /api/reports/{report_id}/download` | Patient clinical-report download | `backend/app/api/reports.py:69-109` requires the patient role, resolves the current patient's profile, uses `ReportService.get_report_by_id` to compare patient IDs, and resolves the opaque private storage key before constructing `FileResponse`. |
| `GET /api/lab-requests/{request_id}/report-file` | Laboratory report download and frontend PDF blob preview | `backend/app/api/lab_requests.py:134-153` requires patient, doctor, laboratorian or admin role. `backend/app/services/lab_request_service.py:211-248` checks release state and patient ownership, doctor assignment, laboratorian assignment or administrator access before resolving private storage. |

The backend API search found no other `FileResponse`, `StreamingResponse`, PDF GET, inline-preview or redirect delivery path under `backend/app/api`. The patient report page downloads the first route. Patient, doctor and admin laboratory pages fetch the second route as a blob and open a browser PDF viewer; they do not call a separate inline API route. Upload and report-metadata endpoints are outside this PDF-response fix.

## Remediation

`backend/app/api/reports.py` and `backend/app/api/lab_requests.py` now attach the same headers to their `FileResponse` objects:

```http
Cache-Control: private, no-store, no-cache, must-revalidate
Pragma: no-cache
Expires: 0
```

The existing `application/pdf` content type, attachment filename/content disposition, and `FileResponse` streaming/range behavior remain in place. The change does not buffer PDFs, alter object authorization, expose storage paths, or change upload quarantine/scanner behavior. There is no new middleware affecting public assets. Error paths still return their existing 401, 403 or 404 responses without document bytes.

## Regression evidence

New `backend/tests/test_pdf_cache_headers.py` uses `httpx.ASGITransport` against the actual FastAPI routes with fictional PDFs in pytest temporary storage. It does not enter the application lifespan or connect to MongoDB. Its ten parameterized cases verify:

- Both successful PDF endpoints carry all three cache headers in the **HTTP response**.
- The laboratory endpoint used by browser blob preview and an admin laboratory download carry the same policy.
- Media type, attachment content disposition, content length and byte-range support remain intact; range responses return 206 and retain the cache headers.
- Unauthenticated and wrong-role requests return 401/403 with no PDF content or attachment header.
- Cross-patient clinical and laboratory requests, and an unassigned doctor request, return 404 without resolving the private file or exposing its path/content.

The existing report, laboratory, report transaction, cleanup, API contract and auth-session tests were rerun without changing their assertions.

### Commands and results

Pytest used the existing locked Python 3.13 environment at `/private/tmp/physiocare-phase14-locked.36WQ5D/venv/bin/python`, with `env -i`, synthetic JWT secrets, `ENVIRONMENT=test`, Mongo pointed to unreachable `127.0.0.1:1`, payment/reconciliation disabled, scanner disabled, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and `-p pytest_asyncio.plugin -p no:cacheprovider -c backend/pytest.ini`. No connected test was included.

| Command (test selection shown) | Result |
| --- | --- |
| `python -m pytest -q -rs … backend/tests/test_pdf_cache_headers.py` | **Exit 0:** 10 passed, 1 pytest plugin warning. |
| `python -m pytest -q -rs … backend/tests/test_pdf_cache_headers.py backend/tests/test_reports.py backend/tests/test_api_contract.py backend/tests/test_laboratory.py backend/tests/test_report_cleanup_reconciliation.py backend/tests/test_report_transaction.py backend/tests/test_report_transaction_target_guard.py backend/tests/test_auth_session_rotation.py` | **Exit 0:** 213 passed, 1 pytest plugin warning. |
| `ast.parse` on both changed API files and the new test file | **Exit 0:** 3 parsed, 0 syntax errors. |
| `git diff --check` | **Exit 0.** |

The warning is `PytestAssertRewriteWarning` because `pytest_asyncio` was already imported before pytest attempted assertion rewriting. The full backend suite was not rerun in this task. Phase 22's 11 fake ClamAV Unix-socket bind failures are historical sandbox results and are not counted as a current pass. The real scanner, private storage/ingress caching, connected role-negative workflows and browser behavior require approved staging verification.

## Scope and remaining work

The prior Phase 23 inactive-account login fix in `backend/app/services/auth_service.py` and its regression test were preserved; the selected auth-session tests passed in the 213-test run. At the end of Phase 23B, clinical query pagination (Phase 22 M3) had not started; the Phase 23C work below records the subsequent change. Phase 22 also mentioned sensitive authenticated **non-PDF** responses; the PDF fix does not establish a no-store policy for those responses. Review that broader cache policy separately before real-data deployment. Do not infer that application headers alone control a future CDN, reverse proxy, service worker or browser blob URL lifetime.

No `.env`, credential, database, external service, deployment, commit or push was touched. All pre-existing uncommitted work remains in place.

## Phase 23C — Bounded clinical query pagination

**Status: IMPLEMENTED; connected performance and some internal aggregation paths remain OPEN.** Phase 22 M3 found that appointment, clinical-report and laboratory-request list queries used unbounded `to_list()` calls. An API request could load and return all matching records. The Phase 23C review also found this pattern in care-plan/history, exercise assignment/progress, laboratory booking, home-visit request, notification, patient directory, and nested patient-history responses. This is a memory, latency and response-size risk; no cross-patient disclosure was demonstrated.

### API and data-access inventory

The following routes now accept `page` and `page_size`. Each server list query filters in MongoDB, sorts deterministically with the unique `_id` tie-breaker, and applies `skip` and `limit` before `to_list()`. Existing JSON arrays and nested history object shapes remain intact.

| API route(s) | Collection / query scope | Sort |
| --- | --- | --- |
| `GET /api/appointments`, `/api/appointments/reception` | `appointments`; patient ID, assigned doctor ID with pending assignments excluded, or active reception schedule according to role | Appointment date and `_id`, newest first except reception schedule ascending |
| `GET /api/reports` | `reports`; authenticated patient ID | Date and `_id`, newest first |
| `GET /api/lab-requests/me`, `/admin`, `/laboratory/assigned`, `/me/reports`, `/doctor/reports` | `lab_requests`; own patient ID, administrator scope, assigned laboratorian ID, or released reports for permitted patients | Creation, update or release date and `_id`, newest first |
| `GET /api/care-plans`, `/patient/{patient_id}`, `/{care_plan_id}/history`, `/{care_plan_id}/exercises` | `care_plans`, `care_plan_history`, `exercise_assignments`; patient or care-plan ID after existing role and assignment checks | Creation/assignment date and `_id`, newest first |
| `GET /api/exercises`, `/exercise-assignments`, `/exercise-progress`, `/exercise-progress/patient/{patient_id}` | `exercises`, `exercise_assignments`, `exercise_progress`; active catalog for patients, patient ownership or clinician authorization | Title and `_id` for catalog; assignment/completion date and `_id` for clinical records |
| `GET /api/laboratory/bookings` | `laboratory_bookings`; authenticated patient ID | Creation date and `_id`, newest first |
| `GET /api/home-visit-requests/me`, `/admin`, `/reception`, `/doctor` | `home_visit_requests`; own patient, administrator, approved reception or approved assigned-doctor scope | Creation date and `_id`, newest first |
| `GET /api/notifications` | `notifications`; authenticated recipient ID | Creation date and `_id`, newest first |
| `GET /api/users/patients`, `/reception/patients` | `patients`; role-gated administrator, assigned-doctor patient IDs, or receptionist contacts | Patient `_id` ascending; assigned-doctor IDs are grouped, sorted and paged in MongoDB |
| `GET /api/users/patients/{patient_id}/history`, `/doctor/patients/{patient_id}/history` | `appointments` and released `lab_requests`; requested patient and authorized clinician assignment | Appointment/release date and `_id`, newest first in each nested array |

Authorization remains server side. A patient-owned route derives the patient ID from the authenticated account; a supplied `patient_id` query parameter cannot replace it. Doctor appointment pages exclude pending doctor assignments in the database query. The doctor-history route checks assignment separately from the requested page so that an empty later page does not become a false authorization denial. Missing and unassigned doctor histories retain the same 404 response. Clinician care-plan and exercise paths keep their existing assignment checks. Tests cover wrong roles and a supplied cross-patient ID.

The laboratory PDF's doctor authorization check also now uses the same doctor/patient/pending-assignment existence filter instead of loading all of that doctor's appointments. It still returns 404 for an unassigned doctor and does not resolve the private file in that case.

`backend/app/core/pagination.py` defines **page 1**, **50 items by default**, **100 items maximum per page**, and **page 1000 maximum** (offset at most 99,900). It returns 422 for zero, negative, noninteger, oversized, or out-of-range values. The 50-item default keeps clinic lists usable while bounding a single API response. No full-collection count was added. The server response schema stays an array, or the existing patient-history object with independently paged appointment and report arrays; `total` and `has_more` are intentionally absent. An empty page marks the end.

The new `list_page_*` repository methods keep the previous unbounded methods for internal service callers and direct-test compatibility. API handlers pass a `PageWindow` to the bounded path. The React pages that consume these lists use `frontend/src/services/clinicalPagination.js` to request sequential 50-item pages before returning the prior array/object shape to existing loading, empty and error views. Patient directories keep paging until an empty database page because profile/account filtering can make an intermediate response shorter than 50. A later-page error is surfaced rather than presenting a partial clinical list. The helper has the same 1000-page ceiling and reports an error instead of silently truncating. This is a minimal compatibility bridge: the browser still gathers all pages for these screens, so very large authorized histories can cause many requests and client memory use. Incremental page navigation or virtualized lists remain future UI work.

### Files and offline evidence

Phase 23C changes are confined to the new pagination helper in `backend/app/core/pagination.py`; clinical API, service and repository modules under `backend/app/api/`, `backend/app/services/`, and `backend/app/repositories/`; `backend/tests/test_clinical_pagination.py` and direct-route contract assertions; `frontend/src/services/clinicalPagination.js`; affected clinical page consumers; `frontend/tests/clinical-pagination.test.mjs` and navigation contracts; and this report. The Phase 23A inactive-account check and Phase 23B PDF cache headers were not removed.

The affected backend API modules are `appointments.py`, `reports.py`, `lab_requests.py`, `care_plans.py`, `exercises.py`, `laboratory.py`, `home_visits.py`, `notifications.py`, and `users.py`. The repository modules are `appointment_repository.py`, `report_repository.py`, `lab_request_repository.py`, `care_plan_repository.py`, `exercise_repository.py`, `laboratory_booking_repository.py`, `demo_service_repository.py`, `notification_repository.py`, and `profile_repository.py`. The service modules are `appointment_service.py`, `report_service.py`, `lab_request_service.py`, `care_plan_service.py`, `exercise_service.py`, `laboratory_service.py`, `home_visit_service.py`, `notification_service.py`, `user_service.py`, `admin_patient_history_service.py`, and `doctor_history_service.py`. Existing direct-route assertions were updated in `backend/tests/test_api_contract.py`, `test_notifications.py`, `test_clinician_directory.py`, and `test_pdf_cache_headers.py` without weakening their authorization checks.

Frontend consumers changed in `frontend/src/pages/admin/` (`AdminDashboard`, `AdminLabRequestsPanel`, `AdminPatientHistory`, `AppointmentBooking`, `Billing`, `CarePlanManagement`, `DemoServices`, `ExerciseAssignmentManagement`, `Notifications`, `PatientsList`, `ReportAuthoring`); `doctor/` (`DoctorDashboard`, `DoctorPatientHistory`, `HomeVisits`); `laboratorian/` (`LaboratoryDashboard`); `receptionist/` (`ReceptionistDashboard`); `common/` (`Notifications`); and `patient/` (`BookAppointment`, `HomeVisitRequests`, `LaboratoryRequests`, `PatientAppointments`, `PatientCarePlan`, `PatientDashboard`, `PatientExercises`, `PatientHistory`, `PatientProgress`, `PatientReports`). Frontend source-contract assertions changed in `frontend/tests/navigation-contract.test.mjs`.

The backend tests ran with the existing pinned Python 3.13 environment, `env -i`, `ENVIRONMENT=test`, synthetic JWT secrets, Mongo directed to unreachable loopback port 1, payment reconciliation disabled, scanner disabled, automatic pytest plugins disabled, and only `pytest_asyncio.plugin` loaded. They did not enter a connected database contract test. The commands used `python -m pytest -q --tb=line -p pytest_asyncio.plugin -p no:cacheprovider -c backend/pytest.ini` followed by the selections below.

| Command / selection | Result |
| --- | --- |
| `backend/tests/test_clinical_pagination.py backend/tests/test_admin_patient_management.py backend/tests/test_clinician_monitoring.py backend/tests/test_clinician_directory.py backend/tests/test_api_contract.py backend/tests/test_auth_session_rotation.py backend/tests/test_pdf_cache_headers.py` | **Exit 0: 367 passed**, 1 pytest plugin warning. Includes authorization, paging, inactive-session and PDF cache regression paths. |
| `backend/tests` (full offline attempt on the final code/test tree) | **Exit 1: 873 passed, 11 failed, 3 skipped**, 1 pytest plugin warning. All 11 failures were fake ClamAV Unix-socket tests unable to bind in this sandbox (`PermissionError: Operation not permitted`); they were not skipped or changed. The 3 connected Mongo tests skipped under their existing target approval guards. |
| `npm test` in `frontend/` | **Exit 0: 102 passed**, 0 failed, 0 skipped. Includes paging and navigation contracts. |
| `npm run lint` | **Exit 0**, no warnings on the final edited frontend. |
| `npm run build -- --configLoader runner --outDir <fresh temporary directory>` | **Exit 0**; temporary production build. |
| JS/CSS asset-size check against that fresh build, with the project's 450 KiB JS / 300 KiB CSS thresholds | **Exit 0: 74 assets checked, 0 violations.** |
| Syntax-only `compile()` over all backend app and test Python files | **Exit 0.** |
| `git diff --check` | **Exit 0.** |

The pytest warning is `PytestAssertRewriteWarning` for an already imported `pytest_asyncio` module. The earlier socket-capable full-suite result from Phase 21/22 does not replace a fresh clean full-suite pass on this tree.

### Remaining limitations and release status

Several unbounded methods still serve internal computations rather than the paged list API: appointment conflict and availability checks, exercise statistics, analytics dashboards, payment operations, and demo rehearsal scripts. `AnalyticsService.get_clinic_stats()` still reads all appointments and doctors into memory; it needs a separate database aggregation design. Doctor released-report paging currently obtains a distinct set of assigned patient IDs before its bounded `lab_requests` query, so a large caseload may still create a large in-memory ID set. Reception patient pages filter inactive user accounts after fetching a bounded database page; the frontend scans through sparse pages to avoid hiding later records. Existing catalog and staff directories were not indiscriminately changed because they are outside the clinical record list finding. These paths require their own performance review with fictional scale data.

No connected Mongo or load test was authorized. Index use, query plans, page consistency under concurrent writes, and the real proxy/client behavior remain unverified. A stable sort prevents duplicate ordering under static data, but offset pagination is not a snapshot across concurrent inserts. Phase 23C does not establish a complete security review or release signoff. **Client demo: HOLD. Staging: BLOCKED. Production: FAIL.** No credential, `.env`, database, external service, commit, push or deployment was touched.

## Phase 23D — Residual queries and browser memory

**Status: IMPLEMENTED for the selected analytics, booking-window, and browser-request paths; the broader residual-query finding remains OPEN.** The current tree was inspected on the same branch and HEAD above, with all prior uncommitted changes preserved. This phase made no database connection or index change. Findings and tests below describe the current code, not a connected query-plan or browser performance measurement.

### Backend query inventory and changes

| Finding / collection | Previous behavior and impact | Current disposition and evidence |
| --- | --- | --- |
| `AnalyticsService.get_clinic_stats`; `appointments`, `doctors`, `patients`, `users` | Loaded every appointment and doctor to calculate 30–365 day summary, weekly buckets, status, specialization, and six-month revenue. Collection growth directly increased application memory. | **IMPLEMENTED:** period `$match` plus `$facet` summary/week/status aggregation; paid six-month `$match`/`$group`; specialization `$group`; database counts for totals and patient measures. The wire response shape and recorded-billing semantics remain. Offline empty and 1,200-record synthetic tests verify aggregate pipelines and that full document lists are not called. Connected Mongo aggregation behavior and plans are **BLOCKED** pending an approved target. |
| `AppointmentRepository.list_active_by_doctor_id`; `appointments` | Availability, home-visit availability, slot conflict, schedule preview, and schedule publication loaded every active appointment for a doctor, including history. Truncating this list could falsely make a booked slot appear available. | **IMPLEMENTED:** all runtime callers now pass the selected clinic day or publication booking window. The query filters doctor and active status in Mongo, matches `starts_at` in the UTC clinic-day interval or a padded `appointment_date` interval for legacy records, and projects only ID, time, and mode fields. It does **not** truncate conflict candidates. Tests cover date/doctor/status filters, a conflict after 150 records, legacy local-midnight resolution, and selected-day availability. The no-window repository method is retained for internal compatibility and remains **OPEN** if called from new code. Index and real data behavior are **BLOCKED** pending connected validation. |
| `LabRequestService.list_doctor_released_reports`; `appointments`, `lab_requests` | The paged report route first materializes all distinct assigned patient IDs; the later report query is paged, but a large caseload can still create a large ID set and `$in` filter. | **OPEN:** replace the ID-list bridge with a Mongo-side authorized join or an equivalent bounded design after contract/performance review. Keep the assignment and released-state filters server side. |
| `ExerciseService.get_progress_stats` and `ExerciseRepository.list_progress_by_assignment`; `exercise_progress` | Assignment-scoped progress is still fully read for statistics. Its scope is narrower than a whole collection, but lifetime completion history can grow. | **OPEN:** aggregate the needed counts/date measures in Mongo with assignment filtering and compare against the current output contract. |
| Older unpaged repository/service methods (appointment operational schedule, clinical lists) and staff/catalogue/demo/payment paths | Phase 23C API handlers select paged methods, but some internal or rehearsal methods still call unbounded `to_list()`. Staff and catalogue directories have different expected volumes; payment and rehearsal flows are separate scopes. | **OPEN for internal callers:** audit each actual caller before changing it. Do not equate every `find()` with a security defect or replace bounded API paths indiscriminately. Payment queries and demo scripts were not altered in this phase. |

Schedule query ownership remains by `doctor_id`; patient-facing availability obtains a valid doctor first, and conflict checks run during authorized booking. Existing role and object authorization were not moved into the browser. The time-window filter is deliberately wider for legacy dates, so a clinician's dense schedule can still yield many candidates. Only a connected `explain()` and fictional scale test can establish its actual memory and latency profile. The unique active slot-claim index remains the atomic booking backstop.

### Browser accumulation and pagination decision

The Phase 23C frontend helper previously fetched up to 1,000 pages and combined all returned records into one array per query. Repeated requests could overlap, old requests could resolve after logout, and overlapping offset pages could duplicate records. **IMPLEMENTED:** the helper now shares concurrent same-path requests, deduplicates stable `id` values (or report `request_id` in history), passes `AbortSignal` to Axios, rejects responses from a prior authentication generation, and caps retained records at **1,000** across each clinical list or combined history. Login and logout cancel active clinical page requests and clear the React Query cache; private content remains gated by the existing auth state. Filtered routes use distinct request keys. Tests cover simultaneous requests, cancellation, distinct patient filters, duplicate pages, the record cap, and history cap. Existing loading/error handling is retained.

**OPEN:** these screens still collect sequential pages before rendering. A legitimate list above 1,000 unique records now produces an explicit error rather than a partial or silently truncated list; there is no in-screen page navigation yet. Multiple different mounted queries can each retain up to 1,000 records, and browser blob/PDF viewer lifetime is a separate concern. React Query's normal cache lifetime can retain recently unmounted data until garbage collection, though logout/login clears it. The helper's cap is a provisional memory guard, not a complete large-clinic UX. Replace whole-list consumers with page-by-page or virtualized interfaces before approving workloads that exceed it. A browser test with fictional patients, filter changes, logout and account switching is still **BLOCKED** on approved staging.

Server defaults remain 50 records per page, maximum 100, maximum page 1,000, with database filtering, deterministic date/`_id` sort, and `skip`/`limit`. The 1,000-page ceiling can permit a 99,900-record offset and up to 100,000 records over many requests. **OPEN:** offset paging is acceptable for small recent lists but increasingly costly for high-page directories/history and can duplicate or miss records during concurrent writes. Consider cursor paging first for high-volume history, appointments, notifications and directories using the existing date plus `_id` tie-breaker; validate cursors and preserve ownership/role filters. This phase did not change the API contract or silently lower its limits. Schedule conflict checks must continue scanning the complete relevant window, not use a capped page.

### Index review

`Appointment` declares unique partial indexes on `slot_claim` and `submission_claim`, plus a single-field status index. `LabRequest` has a unique partial `(patient_id, submission_key)` index and single-field status/report-status indexes. `Notification` indexes recipient only. Many paged clinical models have no explicit compound filter/sort indexes. The existing indexes protect uniqueness and basic lookup but do not visibly cover the new doctor/status/time schedule query, appointment-date analytics, or several ownership-plus-date pages.

**Recommendation, not executed:** evaluate `(doctor_id, status, starts_at)` and `(doctor_id, status, appointment_date)` against the schedule query's two branches; `appointment_date` for period analytics; and selected `(owner_id, sort_date, _id)` compounds for high-volume patient/doctor lab requests, reports, notifications, exercise progress and histories. Consider a paid-billing/date index only if the revenue aggregation plan warrants its write/storage overhead. Avoid duplicating existing unique or single-field indexes without `explain()` evidence. Actual index inventory, selectivity, planner choice, write overhead, migration timing and any rollout are **BLOCKED** until an approved isolated Mongo environment exists. No migration or connected test was run.

### Fresh Phase 23D verification

Backend commands used the pinned Python 3.13 environment at `/private/tmp/physiocare-phase14-locked.36WQ5D/venv/bin/python`, `env -i`, `ENVIRONMENT=test`, synthetic JWT values, Mongo directed to unreachable `127.0.0.1:1`, disabled payment/reconciliation and scanner, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `-p pytest_asyncio.plugin -p no:cacheprovider -c backend/pytest.ini`. The three connected contracts remained behind their explicit approval guards. No test in this run contacted a database.

| Command / selection | Actual result |
| --- | --- |
| `python -m pytest -q --tb=line -rs … backend/tests/test_phase23d_query_hardening.py backend/tests/test_api_contract.py backend/tests/test_schedule_fallback_guard.py backend/tests/test_clinical_pagination.py backend/tests/test_pdf_cache_headers.py backend/tests/test_auth_session_rotation.py` | **Exit 0: 376 passed**, 1 pytest plugin warning. |
| Same safe pytest environment, `backend/tests` (full suite) | **Exit 1: 880 passed, 11 failed, 3 skipped**, 1 pytest plugin warning. All 11 failures are fake ClamAV Unix-socket tests blocked by this sandbox's `PermissionError: Operation not permitted`; they were not altered or skipped. The 3 skipped tests are connected Mongo contracts without approval. This is not a full-suite pass. |
| `npm test` in `frontend/` | **Exit 0: 108 passed**, 0 failed, 0 skipped; includes clinical paging, auth/logout and page behavior tests. |
| `npm run lint` | **Exit 0.** |
| `npm run build -- --configLoader runner --outDir /private/tmp/physiocare-phase23d-build-20261101` | **Exit 0**; Vite 8.3.5, 1,836 modules transformed. Warning: out-of-project temporary directory was not emptied. |
| Fresh build asset budget (450 KiB JS / 300 KiB CSS) | **Exit 0:** 78 assets, 72 JS and 1 CSS; 0 violations. Largest JS 373,260 bytes; CSS 254,380 bytes. |
| Syntax-only `compile()` over `backend/app` and `backend/tests` | **Exit 0:** 138 Python files parsed. |
| `pip check`; installed versions against applicable `backend/requirements.lock` pins | **Exit 0:** no broken requirements; 48 applicable pins, 0 mismatches. Pip warned its local cache was not writable and disabled the cache. No dependency installation or audit lookup occurred. |
| `git diff --check` | **Exit 0.** |

The pytest warning is `PytestAssertRewriteWarning` for the previously imported `pytest_asyncio` plugin. The fresh full backend result must be rechecked in a local environment that permits temporary Unix sockets before treating this tree as fully passing. The edited Phase 23D paths were `backend/app/services/analytics_service.py`, `backend/app/repositories/appointment_repository.py`, `backend/app/services/{appointment_service,clinician_schedule_service,home_visit_service}.py`, `backend/tests/{test_phase23d_query_hardening,test_api_contract}.py`, `frontend/src/services/clinicalPagination.js`, `frontend/src/context/AuthContext.jsx`, `frontend/tests/clinical-pagination.test.mjs`, and this report. Earlier uncommitted Phase 16–23 changes were preserved.

**Phase 23D outcome:** Selected query and browser guards are implemented and locally tested; remaining internal reads, large-list UX, index/performance measurement, and connected browser/staging checks remain **OPEN/BLOCKED**. The full backend suite is not clean in this sandbox. Phase 24 combined security re-verification can be planned after review, but cannot be claimed complete or release-ready from this evidence. **Client demo: HOLD. Staging: BLOCKED. Production: FAIL.** No commit, push, deployment, credential modification, real patient data, or external service contact occurred.
