# Phase 24A.3 — Remaining Screens Remediation, Groups A–C

Assessment date: 2026-11-02. Branch: `codex/physiocare-integration-2026-10-31`. HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`.

## Decision

**Groups A (nine patient screens), B (nine admin screens), and C (two doctor screens and one receptionist screen): IMPLEMENTED and offline regression verified. Phase 24A closure: NOT PASSED. Phase 24B: BLOCKED. Client demo: HOLD. Production: FAIL.** This is a local code and offline-test result, not connected MongoDB, browser, staging, scanner, or production validation. No commit or push occurred.

The source inventory agrees with the requested 21 screens. The Phase 24A.2 naming/count inconsistency is resolved by listing each actual source file below. The five Phase 24A.2 screens remain separate and unchanged by this pass: `AdminLabRequestsPanel`, common `Notifications`, doctor `HomeVisits`, `LaboratoryDashboard`, and patient `LaboratoryRequests`.

Group A began with 118 existing changed/untracked paths and ended with 128 including this report. Group B began from that worktree. Earlier modifications were preserved; neither `.env` nor credentials were edited.

## Screen inventory and strategy

`IMPLEMENTED` means source was changed and focused offline tests passed, while connected and interactive browser evidence remains open. `OPEN` means its 1,000-record accumulation path remains. None of these statuses implies Phase 24A closure.

| Group | Screen | Strategy and result | Status |
| --- | --- | --- | --- |
| Patient | `BookAppointment` | Payment resume now reads one patient-owned appointment by ID; missing and foreign IDs share 404. Availability and conflict checks remain in the existing booking service. | IMPLEMENTED |
| Patient | `HomeVisitRequests` | Independent current-page navigation for own home-visit bookings and earlier requests. Booking query filters owner and `home_visit` before skip/limit. | IMPLEMENTED |
| Patient | `PatientAppointments` | Status-scoped, future-filtered pages; client still removes expired same-day legacy records. Each page replaces the previous one. | IMPLEMENTED |
| Patient | `PatientCarePlan` | Server selects active/latest plan; history uses one page; stage assignment totals use a patient/plan-scoped aggregation rather than loading every assignment. | IMPLEMENTED |
| Patient | `PatientDashboard` | First bounded future appointment page, plus separate bounded lab/home previews ordered by `updated_at`. Existing analytics are not recomputed from page counts. | IMPLEMENTED |
| Patient | `PatientExercises` | Category filter runs in Mongo before page; prescribed assignments join active catalogue details inside an owner-scoped aggregation; independent page controls; lifetime completion uses existing aggregate stats. | IMPLEMENTED |
| Patient | `PatientHistory` | Status filter runs before skip/limit with stable date/time/ID order. Tab counts formerly computed from the accumulated list were removed; current-page count is labeled accurately. | IMPLEMENTED |
| Patient | `PatientProgress` | Active/latest plan selected by an owner-scoped database query; existing exercise aggregate provides totals. | IMPLEMENTED |
| Patient | `PatientReports` | Patient-scoped title/category search with escaped literal, then stable date/ID page navigation. PDF preview clears on page/identity change. | IMPLEMENTED |
| Admin | `AdminDashboard` | Daily counts and schedule buckets come from a Mongo grouping; recent appointments use one bounded page. Connected performance remains open. | IMPLEMENTED |
| Admin | `AdminPatientHistory` | Patient/date scoped appointment and released-report pages, with page-local counts and preserved PDF view. | IMPLEMENTED |
| Admin | `AppointmentBooking` | Server-searchable patient/doctor selectors; availability and conflict checks remain authoritative in the backend. | IMPLEMENTED |
| Admin | `Billing` | Admin-only billing route filters status/date before bounded page; captured-payment reconciliation remains separate. | IMPLEMENTED |
| Admin | `CarePlanManagement` | Direct authorized patient lookup and bounded plan pages, with selected plan retained during editing. | IMPLEMENTED |
| Admin | `DemoServices` | Bounded entitlement/request/home-booking pages and server-filtered home-visit clinician choices. | IMPLEMENTED |
| Admin | `ExerciseAssignmentManagement` | Direct authorized patient lookup, bounded plan/assignment pages, searchable exercise selector and bounded assignment labels. | IMPLEMENTED |
| Admin | `Notifications` | System alerts derive from admin-only daily aggregate and existing stats, with no appointment-list fetch. The separate common Notifications screen was already handled. | IMPLEMENTED |
| Admin | `ReportAuthoring` | Server-searchable authorized patient selector; existing report creation and PDF controls preserved. | IMPLEMENTED |
| Doctor | `DoctorDashboard` | Doctor-scoped Mongo aggregation for all-time caseload totals; bounded agenda/report pages; server status/date filters. | IMPLEMENTED |
| Doctor | `DoctorPatientHistory` | Assignment check before patient lookup; date/status-filtered appointment and released-report pages; patient-keyed query and stale PDF guard. | IMPLEMENTED |
| Receptionist | `ReceptionistDashboard` | Database active-count summary, projected active schedule page, independent home-visit queue, date controls, and restricted output. | IMPLEMENTED |

All nine patient source files were inspected and changed. Group B was completed in two local subgroups. The three Group C screens were then changed in this pass; their earlier accumulation paths are described in the Group C section below.

## API, database, frontend, and security changes

- Added patient-only `GET /api/appointments/{id}`, `/api/appointments/me/home-visits`, and `/api/appointments/me/history`. The history route accepts `status_group`, `future_only`, `page`, and `page_size`. Query predicates on patient, status, future time, and service mode precede pagination; sort keys end with `_id`. The direct lookup checks ownership before formatting. Invalid status groups and pages fail validation.
- Added optional `selection=active_latest` to the patient care-plan list, and patient-only `GET /api/care-plans/{id}/exercise-summary`. The latter verifies plan ownership before aggregating assignment counts by stage. Existing default care-plan list behavior remains.
- Added optional patient report `search`, exercise catalogue `category`, and patient request `order=updated` parameters. Defaults retain existing responses. Search is escaped before the Mongo regex; owner filters precede page operations. Invalid category/order values fail validation.
- Added patient-only `GET /api/exercise-assignments/me/details`, with patient filter, active-exercise join, optional category match, stable sort, skip/limit, and projected UI fields. The existing assignment endpoint is unchanged.
- The nine patient screens now avoid whole-list accumulation. Shared current-page fetches are deduplicated, bounded to 50 records, aborted on auth changes, and keyed by page/filter/identity where applicable. The shared navigation control can disable Next on a known short final page. Explicit page controls can reach page 21 (records after the old 1,000-record boundary). Existing global auth logout clearing remains in place.
- Existing inactive-account session denial, CSRF, clinical PDF cache headers, authenticated JSON no-store policy, scanner fail-closed logic, demo schedule guard, and role/ownership checks were not relaxed. New patient JSON routes use the existing `Cache-Control: private, no-store` middleware; focused HTTP tests checked this on representative routes.

### Remaining query and analytics findings

| Query | Classification | Evidence and follow-up |
| --- | --- | --- |
| Existing patient exercise assignment/progress stats | SAFE for bounded output; connected performance BLOCKED | Existing patient `$match` and facets remain; current offline aggregate tests pass. The new stage summary matches patient and care-plan IDs before grouping. Synthetic 1,201-assignment totals were checked without loading individual rows. |
| Patient dashboard upcoming appointment preview | FILTER / REVIEW | Status and future predicates run in Mongo; only the first 50 are rendered. Legacy appointments with no `starts_at` use a local-date fallback, so exact same-day expiration and query plans need connected validation. |
| Lab and home dashboard previews | FILTER | Owner-scoped, updated-time-descending pages with `_id` tie-breaker; frontend merges at most 50 of each to find the latest three. |
| Admin, doctor, receptionist dashboards | AGGREGATE / FILTER | Their old accumulation paths remain open; totals must not be inferred from the first page. |
| Clinic specialization grouping and legacy unpaged internal calls | REVIEW | Cardinality and active call sites still need investigation. |
| Doctor report query and all new Mongo pipelines | BLOCKED connected review | Query plans, indexes, page stability under writes, and cross-clinician authorization need approved connected tests. |

The new assignment join loads at most one page into the browser, but Mongo may process more matching patient assignments before skip. Its cost and indexing are unmeasured. Offset pagination is bounded to page 1,000; it is not a long-term cursor solution for very large collections. Full pages require probing the next page to distinguish an exact boundary. Interactive filters, last-page behavior under concurrent writes, and account switching have only offline component/helper evidence, not browser end-to-end evidence. The patient appointment date fallback cannot perfectly classify old same-day records lacking `starts_at` without a data migration or a more complex legacy query; this remains open.

## Synthetic database test correction

Phase 24A.2's first broad command supplied `DATABASE_NAME=physiocare_test`, while `test_normal_test_configuration_uses_dedicated_development_database` expects the explicit safe development identity `physiocare_dev`. This was a **test-invocation mismatch**, not a production configuration defect. This pass used `env -i`, `ENVIRONMENT=test`, `MONGODB_URL=mongodb://127.0.0.1:1/physiocare_dev`, `DATABASE_NAME=physiocare_dev`, payment reconciliation/Razorpay/scanner disabled, and `/private/tmp` as the working directory. Port 1 is intentionally unreachable; all executed tests were offline and mocked. The exact affected test passed on the corrected invocation; it also passed in the final 920-test offline run. No `.env`, database, or application configuration was changed to force a pass.

## Verification

Commands below ran on the current worktree with pinned Python 3.13 packages in `/private/tmp/physiocare-phase14-locked.36WQ5D/venv`. Backend test commands used `env -i`, `PYTHONPATH=<repo>/backend`, `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, the synthetic environment above, and `python -m pytest -q -p pytest_asyncio.plugin -p no:cacheprovider` from `/private/tmp`.

| Check | Result |
| --- | --- |
| Eight new `backend/tests/test_phase24a3_*.py` modules | Focused tests for owner/role boundaries, 404 neutrality, status/category/search filtering before page 21, stable ordering, 1,201-row aggregate totals, and cache policy passed. Included in broader result. |
| Complete offline backend except 3 connected Mongo files and `test_clamav_unix_scanner.py` | **920 passed, 0 failed, 1 pytest plugin rewrite warning**, exit 0. This includes Phase 23/24 security, API contracts, existing exercise aggregation, and the corrected synthetic configuration test. The four files were explicitly ignored in this command. |
| Broader backend excluding only 3 connected Mongo files | **920 passed, 11 failed, 1 warning**, exit 1. Every failure was in the fake ClamAV Unix-socket file at `asyncio.start_unix_server` → `sock.bind` → `PermissionError: [Errno 1] Operation not permitted` in this sandbox. No application assertion was reached in those cases. This is not a clean full-suite pass. |
| Frontend `npm test` | **128 passed, 0 failed/skipped**, exit 0. Includes shared 1,250-row/page-21 traversal, deduplication/cancellation, patient screen static rendering, and prior auth tests. |
| `npm run lint` | Exit 0, no warnings. |
| `npm run build -- --configLoader runner --outDir /private/tmp/physiocare-phase24a3-build --emptyOutDir` | Exit 0, Vite 8.3.5, 1,837 modules transformed. The default Vite config loader attempted a sandbox-denied write to `node_modules/.vite-temp`; the runner loader and temporary output completed successfully. |
| Equivalent asset budget over temporary output | 74 JS/CSS assets; largest 365 KiB; zero violations of the repository's 450 KiB JS / 300 KiB CSS limits. |
| Python AST and lock check | 155 backend Python files parsed; 48 applicable installed lock pins matched, zero mismatches. |
| `git diff --check` | Exit 0. |
| Gitleaks 8.30.1 | `gitleaks dir --no-banner --redact=100 --report-format=json --report-path=/private/tmp/physiocare-phase24a3-gitleaks.json .`: exit 1, six candidates, all in two pre-existing test files; no Phase 24A.3 path flagged. AST context classifies all six as **synthetic test submission keys**, not credentials. The scan included current working-tree content; it did not separately scan Git history. No possible secret value was printed or copied into this report. |

### Files changed in this pass

Backend API: `appointments.py`, `care_plans.py`, `exercises.py`, `home_visits.py`, `lab_requests.py`, `reports.py`. Backend repositories: `appointment_repository.py`, `care_plan_repository.py`, `demo_service_repository.py`, `exercise_repository.py`, `lab_request_repository.py`, `report_repository.py`. Backend services: `appointment_service.py`, `care_plan_service.py`, `exercise_service.py`, `home_visit_service.py`, `lab_request_service.py`, `report_service.py`. Backend schema: `schemas/exercise.py`. Eight new `test_phase24a3_*.py` files were added under `backend/tests/`.

Frontend: all nine Group A patient pages listed above, `components/common/ClinicalPageNav.jsx`, and `tests/booking-rendered-flow.test.mjs`, `tests/clinical-pagination.test.mjs`, `tests/navigation-contract.test.mjs`. The files already contained Phase 23/24 or Phase 24A.2 changes; this list does not imply those earlier changes were authored in this pass.

## Next controlled group and release gates

Complete the **six OPEN Group B admin screens** in focused subgroups (booking and patient history; care-plan and exercise management; demo services and report authoring) with server-side selectors, summaries, and role-negative tests; then obtain review before Group C doctor/reception. Do not count the shared helper tests as screen verification. Before Phase 24A closure, run real browser journeys on an approved fictional-data target, perform connected Mongo explain/index and cross-clinician checks, and rerun the full backend suite in a socket-capable environment. Approved scanner, isolated staging, private storage, proxy, backups, and independent security review remain separate release gates. **Phase 24B remains blocked pending Phase 24A closure review.**

## Group B — First three admin screens (earlier 2026-11-02 snapshot)

At this earlier snapshot, the source and all nine component data flows were inventoried. Three screens were changed and tested. Six screens were OPEN because their selectors, filtered records, or exact summaries required coupled backend and frontend contracts; a simple page-one substitution would have hidden eligible patients or misstated counts. The subsequent Group B.2 section records their current state.

| Screen | Original problem and selected strategy | Authorization and evidence | Status |
| --- | --- | --- | --- |
| `AdminDashboard` | Accumulated `/appointments` to calculate today/yesterday totals and time-of-day buckets. Added admin-only `/api/analytics/admin-daily-activity`: Mongo date match then group by day and slot, without patient fields. Recent appointment cards use one page. Existing `/analytics/stats` aggregates remain. | New route rejects patient, doctor and receptionist (403); synthetic 1,501-today/99-yesterday grouping and static dashboard render pass. | IMPLEMENTED |
| `AdminPatientHistory` | Both appointment and released-report arrays are accumulated; visible totals are derived from them. Needs independent date-filtered pages and exact summary counts. Existing admin-only route and patient-scoped backend pages were inspected. | Existing admin role dependency retained. No change or new screen-specific test this pass. | OPEN |
| `AppointmentBooking` | Whole patient directory is accumulated for selection. Needs authorized patient search, including receptionist field restrictions. Existing availability and booking conflict paths remain unchanged. Legacy same-day `starts_at` behavior remains a separate compatibility review. | Existing admin/reception booking endpoints and server availability remain. No new conflict-path code or test this pass. | OPEN |
| `Billing` | Whole appointment ledger is accumulated. Added admin-only `/api/appointments/admin/billing` with status and date predicates before stable date/ID skip/limit. Frontend uses current-page navigation and labels count as current-page only. Captured review and reconcile actions remain separate. | Admin 200 with private no-store; patient/doctor/receptionist 403; invalid reversed date range 422. Page 21 repository query and static billing render pass. No Razorpay request was made. | IMPLEMENTED |
| `CarePlanManagement` | Whole patient directory and patient plan list are accumulated, and selected plan is found in the list. Needs direct authorized patient/plan lookups plus plan navigation before changing edit behavior. | Doctor/patient relationship checks in existing backend were not altered. | OPEN |
| `DemoServices` | Whole request and appointment lists are accumulated; home bookings are filtered in the browser. Needs separate request pages and a server-filtered home booking page. | Existing demo/environment guards were inspected and left unchanged; no production fallback was enabled. | OPEN |
| `ExerciseAssignmentManagement` | Whole patient, plan, exercise and assignment lists are accumulated. Needs separate authorized selectors and patient-scoped assignment pages while preserving stage/assignment editing. | Existing doctor/patient authorization and Phase 24A.2 exercise aggregate were not changed. | OPEN |
| `Notifications` | System alerts counted today's appointments from an accumulated appointment list. Now uses the same admin-only daily aggregate and existing aggregate patient statistic; no broad notification or appointment query. Message accurately says selected period. | Admin-only aggregate route; static alert render with 1,201 daily appointments passes. This page generates system alerts and never reads another user's private notification collection. | IMPLEMENTED |
| `ReportAuthoring` | Whole patient directory is accumulated for the authoring selector. Needs server-side authorized patient search that keeps the selected patient stable, including >1,000-record access. | Existing clinical report creation, PDF quarantine, file and cache controls were left unchanged; no new PDF route was added. | OPEN |

### Group B changed files and contracts

- Backend: `app/api/analytics.py`, `app/services/analytics_service.py`, `app/api/appointments.py`, `app/services/appointment_service.py`, and `app/repositories/appointment_repository.py`; added `tests/test_phase24a3_admin_activity.py` and `tests/test_phase24a3_admin_billing.py`.
- Frontend: `pages/admin/AdminDashboard.jsx`, `pages/admin/Notifications.jsx`, `pages/admin/Billing.jsx`, `pages/admin/dashboard/DashboardStats.jsx`, `pages/admin/dashboard/DashboardCharts.jsx`, and `tests/clinical-pagination.test.mjs`.
- New routes default to private no-store through existing authenticated JSON middleware. `/api/analytics/admin-daily-activity` returns `{today_appointments, yesterday_appointments, schedule_counts}`. `/api/appointments/admin/billing` returns the existing appointment array contract, accepts validated `page`, `page_size`, optional status and optional inclusive start/end dates. Existing routes and response defaults were not changed.
- Browser memory for the changed dashboard and alerts no longer depends on a 1,000-row accumulation. Billing retains one 50-row page, keyed by administrator, page and filters with `gcTime: 0`; shared page loading deduplicates concurrent requests and aborts stale requests on authentication changes.

### Group B verification and limits

| Check | Current result |
| --- | --- |
| New admin activity and billing offline tests | **4 passed**, 1 pytest plugin rewrite warning. Tests check role rejection, no-store headers, page 21, date/status filtering before pagination, stable sorting, and grouped totals over synthetic >1,000 counts. |
| Offline backend excluding three connected Mongo files and fake ClamAV socket file | **924 passed**, 1 warning, exit 0. Includes prior appointment conflict, billing, care plan, exercise, notification, report, PDF, and authentication tests; those unchanged paths were not independently exercised in a browser. |
| Broader backend excluding only three connected Mongo files | **925 passed, 11 failed**, 1 warning, exit 1. All 11 failures are fake ClamAV cases denied at Unix-socket bind with `PermissionError: [Errno 1] Operation not permitted`. No clean full-suite pass is claimed. |
| Frontend `npm test` | **130 passed**, no failures/skips, exit 0; includes separate static Billing, dashboard, and admin system-alert render tests. |
| Frontend lint, Vite production build, equivalent bundle budget | All exit 0. Temporary Vite runner build; 74 JS/CSS assets, zero over the 450 KiB JS / 300 KiB CSS limits. |
| Python AST and applicable pinned lock versions | 157 Python files parsed, 48 pins matched, zero mismatches. |
| `git diff --check` | Exit 0. |
| Gitleaks 8.30.1 current working-tree directory scan with `--redact=100` | Exit 1, six previously classified synthetic test submission-key candidates; none in a new Group B path. This is not a zero-finding scan. |

The daily grouping emits one row per distinct date and time slot; its connected query plan and legacy date interpretation remain unmeasured. The recent dashboard preview uses the first 50 authorized appointments, which is bounded but may not represent every appointment on the current day; the count and time buckets come from the aggregate, not that preview. Billing formatting still uses existing per-appointment enrichment, so connected N+1 cost needs measurement. No connected MongoDB, scanner, browser workflow, payment provider, staging, or production validation occurred in that earlier subgroup. **At that point Group B was incomplete; Group C remained unstarted.**

## Group B.2 — Six remaining admin screens (2026-11-02)

The earlier Group B table above records the state *before* this subgroup. All six remaining screens were inspected and changed. **Group B is now IMPLEMENTED with focused offline evidence.** `FIXED` is reserved pending connected query and browser validation. Group C and Phase 24B were not started.

| Screen | Original behavior and root cause | Selector/query and authorization change | Verification and status |
| --- | --- | --- | --- |
| `AdminPatientHistory` | Accumulated patient appointment and released-report pages, then presented accumulated lengths as totals. | Admin-only route accepts inclusive date bounds and a page. Mongo filters by exact patient ID and date before stable date/ID skip/limit; released reports retain the release-status predicate. Doctor/user names are fetched in two bounded bulk queries per page; the already-loaded patient identity is reused for reports. UI renders one 50-item page of each list, truthful page-local counts, date controls, and unchanged private report-file action. | Date/patient/released predicates, page 21, 50-visit bulk formatting and existing admin route/PDF tests passed offline. **IMPLEMENTED.** |
| `AppointmentBooking` | Patient selector accumulated the full directory and doctors were unpaged. | Searchable server-side patient and doctor selectors. Receptionist results retain their narrower public fields; doctor choice and patient choice persist through search/page changes. Existing availability lookup, same-day handling, slot conflict precheck, and unique slot-claim collision response remain in the backend. No appointment conflict is decided from a truncated browser page. | Page 25 patient search, page 21 doctor search, role checks, existing same-day/duplicate-claim booking tests and frontend contract tests passed offline. **IMPLEMENTED.** |
| `CarePlanManagement` | Loaded every patient and every plan for the selected patient. | Direct admin or assignment-checked doctor patient lookup, one stable patient-scoped plan page, and a retained selected-plan snapshot while editing. Existing plan mutation authorization and status rules remain. | Existing care-plan authorization/regression tests and screen-specific page contract passed offline. **IMPLEMENTED.** |
| `DemoServices` | Accumulated requests and appointments, then filtered scheduled home visits in the browser; entitlement and clinician lists were unbounded. | Separate bounded request, entitlement, scheduled-home-visit and clinician pages. Mongo filters scheduled home visits and home-visit-capable clinicians before pagination. The new home-visit queue joins patient names after page selection and projects only the fields this admin screen needs. Entitlement search joins patient and entitlement in Mongo, then pages. Existing production guard rejects demo mode and production demo fallback; the admin-only queue and backend clinician-allocation eligibility remain. | Admin-only scheduled-home route, filter-before-page, synthetic >1,000 entitlement search, configuration regression tests and frontend contract test passed offline. **IMPLEMENTED.** |
| `ExerciseAssignmentManagement` | Accumulated patient, plan, exercise and assignment lists; labels depended on full browser catalogues. | Direct authorized patient lookup; bounded plan and assignment pages; searchable active-exercise selector. The selected plan survives page changes. Optional assignment labels are fetched in two bounded bulk projections after the patient/doctor scope check, preserving stage and prescription editing without full-catalogue loading. | Search escaping, page 21 selector, existing assignment/progress authorization and aggregation tests, plus screen-specific frontend contract passed offline. **IMPLEMENTED.** |
| `ReportAuthoring` | Accumulated the patient directory before showing the create-report form. | Searchable, role-scoped patient selector with current selection retained across pages. Existing `/reports` mutation, doctor assignment and booking ownership checks, private PDF quarantine/access and no-store download headers were unchanged. The original screen has report creation but no editing or appointment picker; those workflows were not invented in this pass. | Existing report/PDF/cross-patient tests and screen-specific frontend contract passed offline. **IMPLEMENTED.** |

### Group B.2 source and tests

- Backend API: `users.py`, `home_visits.py`, `exercises.py`. Services: `user_service.py`, `admin_patient_history_service.py`, `appointment_service.py`, `home_visit_service.py`, `exercise_service.py`. Repositories: `profile_repository.py`, `appointment_repository.py`, `lab_request_repository.py`, `demo_service_repository.py`, `exercise_repository.py`. Schemas: `schemas/exercise.py`, `schemas/home_visit.py`. Added `tests/test_phase24a3_admin_group_b2.py`.
- Frontend: the six named admin screens, new `pages/admin/ClinicalEntityPicker.jsx`, new `tests/admin-group-b2.test.mjs`, and updated `tests/navigation-contract.test.mjs` expectations for the new bounded contracts. Existing Group A and three earlier Group B implementations were preserved.
- Backend search uses escaped literal regex, role or assignment predicates, stable name/ID sorting, and skip/limit inside Mongo. The one-page selector retains a selected record outside the displayed page. Final mutations still validate IDs and relationships on the server. Query-client pages are keyed by route, search and page, use zero cache retention after inactivity, and share concurrent identical requests through the existing clinical pagination helper. Sensitive authenticated JSON remains under `Cache-Control: private, no-store`.

### Group B.2 fresh verification

| Command/check | Actual result |
| --- | --- |
| `pytest -q backend/tests/test_phase24a3_admin_group_b2.py` with isolated test environment | **19 passed**, 1 pytest plugin rewrite warning, exit 0. |
| Focused pre-existing API contract, clinical pagination and clinician directory tests | **335 passed**, 1 warning, exit 0. |
| All offline backend tests excluding three connected Mongo test files and the fake Unix-socket scanner file | **943 passed, 2 skipped**, 1 plugin warning, exit 0. Connected tests were not run. |
| Broad backend run excluding only three connected Mongo test files | **944 passed, 11 failed, 2 skipped**, 1 plugin warning, pytest exit 1. All 11 failures are in `test_clamav_unix_scanner.py` at local Unix-socket bind with `PermissionError: [Errno 1] Operation not permitted`. The fake scanner tests were neither changed nor silently skipped; this sandbox did not permit their socket setup. This is not a fresh full-suite pass. |
| `npm test` | **136 passed, 0 failed, 0 skipped**, exit 0; includes six new Group B.2 frontend checks. |
| `npm run lint`; Vite production build with `--configLoader runner` and temporary output directory | Both exit 0. **75 JS/CSS assets**, none over 450 KiB JS or 300 KiB CSS budget. |
| Python AST parse; installed-version check against `backend/requirements.lock` | **158 Python files parsed; 48 applicable pins; 0 mismatches**, exit 0. No dependency installation or advisory lookup occurred. |
| `git diff --check` | Exit 0. No commit or push. |
| `gitleaks dir --no-banner --redact=100 --report-format=json --report-path=/private/tmp/physiocare-phase24a3-b2-gitleaks.json .` (8.30.1) | Exit 1, six previously reviewed synthetic submission-key candidates in earlier test files; zero candidates in new Group B.2 paths. This directory scan included the current worktree, not a separate Git-history scan. No candidate values were printed. |

The test environment used `env -i`, `ENVIRONMENT=test`, the deliberately unreachable `mongodb://127.0.0.1:1/physiocare_dev` configuration, disabled payment reconciliation and scanner, and ran from `/private/tmp` so a real `.env` was not loaded. No MongoDB, payment provider, scanner service, staging, production, or external infrastructure was contacted.

### Remaining limits and decision

Offset pages stop at page 1,000 and can shift under concurrent writes; connected query-plan/index and stability checks are still required. Searchable selectors can find an eligible record beyond the former 1,000-row browser cap, but this was validated with synthetic offline query/selector tests rather than an approved connected dataset. The fake ClamAV suite needs a socket-capable local run. Interactive browser journeys, report authoring UX on account switching, operational scanner/private storage, and approved isolated staging remain unverified. Demo controls are effectively disabled in production by the existing configuration guard, but their admin page is still present; no production configuration was changed. The three Group C screens remain **OPEN**. **Group B.2: IMPLEMENTED; Phase 24A closure: NOT PASSED; Phase 24B: BLOCKED; client demo: HOLD; production: FAIL.**

## Group C — Doctor and receptionist screens (2026-11-02)

The Group B.2 decision above describes the state *before* Group C. The three remaining screens were inspected and changed. **Group C is IMPLEMENTED with offline evidence.** This does not close Phase 24A, since connected authorization/performance and browser checks remain open.

| Screen | Original behavior and finding | Remediation and status |
| --- | --- | --- |
| `DoctorDashboard` | Fetched and accumulated every assigned appointment and released report, then counted the loaded rows. At the 1,000-record browser cap the totals could be incomplete. | Doctor-only `/appointments/doctor/summary` groups assigned, non-pending appointments in Mongo: scheduled/in-progress, completed, and distinct patients. The metrics keep their former all-time definitions. The agenda and released-report lists each retain only their current 50-row page, with separate page controls and error states. Agenda status and inclusive date bounds are applied before Mongo skip/limit. The existing doctor report query joins assignment inside Mongo before paging; report names are enriched with two bounded profile/user queries. **IMPLEMENTED.** |
| `DoctorPatientHistory` | Accumulated appointment and report pages, then filtered appointments in the browser and presented accumulated lengths as lifetime totals. A patient switch could leave private data in prior query state or an in-flight PDF viewer. | The doctor-only route checks the actual non-pending appointment assignment before patient lookup. Appointment predicates include the authenticated doctor's profile ID, patient ID, status group, and date before stable date/ID paging. Released reports remain patient-scoped and released-only, with release-date filtering and stable release-date/ID ordering. The UI uses one 50-item page of each array, truthful page-local counts, patient/filter/page query keys, zero inactive cache retention, an Axios abort signal, and a patient identity check before opening an asynchronous PDF response. Existing PDF endpoint authorization remains independent. **IMPLEMENTED.** |
| `ReceptionistDashboard` | Accumulated the complete active appointment and approved home-visit queues. Its displayed appointment count was the length of the retained browser list. | Reception-only summary counts all active appointments in Mongo, with optional inclusive date bounds. The schedule query filters active status/date before stable date/ID pagination and projects only contact, appointment, and cancellation fields needed for coordination. Approved home-visit requests are separately paged with a restricted projection that omits reason, symptoms, pain severity, and billing; profile/user names are bulk-enriched per page. The existing cancellation endpoint and role-limited response models remain. Each queue has its own loading/error/empty state. **IMPLEMENTED.** |

### Authorization, pagination, and data boundaries

- Doctor dashboard totals derive doctor ID from the authenticated user, never from query parameters. The Mongo match excludes pending assignments. Doctor history uses the same assignment relationship and returns the same 404 for unassigned or missing patients. Page/date/status parameters cannot broaden this scope. The doctor report query and PDF download retain separate authorization checks.
- Reception routes use `RoleChecker(["receptionist"])`; the response models omit clinical history, appointment reasons, report content, care plans, and billing. The raw Mongo page projections for reception appointments and approved requests also exclude clinical reason/symptom and billing fields. Reception appointment cancellation rules were not changed.
- Current-page navigation uses the existing 50-row helper and unique-ID tie breakers. Query keys include page, date/status, or patient identity; the helper shares identical in-flight requests and auth change aborts them. No Group C screen calls the accumulating `fetchClinicalPages` or `fetchClinicalHistoryPages` helpers. Page 21 is covered by synthetic backend tests. A full page may offer an extra empty next page; offset paging can shift under concurrent writes and stops at page 1,000.
- Doctor agenda rows still use the shared appointment formatter. The API projects to `DoctorAppointmentOut`, which excludes financial fields, but the repository loads a full appointment document before formatting. A narrower Mongo projection for this clinical agenda is a remaining data-minimization improvement. Doctor history shows only appointment and released-lab-report records; it does not add care-plan or exercise-progress permissions that were not part of the existing history contract.

### Group C source and test changes

Frontend: the three named screens, `tests/doctor-reception-group-c.test.mjs`, and updated obsolete assertions in `tests/navigation-contract.test.mjs`. Backend: `api/appointments.py`, `api/users.py`, appointment and demo-service repositories, appointment, doctor-history, home-visit, and lab-request services, `tests/test_phase24a3_doctor_reception_group_c.py`, and the projected-query expectation in `tests/test_clinical_pagination.py`. The previously modified Group A/B files and all unrelated uncommitted work were preserved.

### Group C verification

The commands used pinned Python 3.13 packages from `/private/tmp/physiocare-phase14-locked.36WQ5D/venv`. Pytest ran under `env -i` from `/private/tmp`, with `PYTHONPATH=<repo>/backend`, `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `ENVIRONMENT=test`, `MONGODB_URL=mongodb://127.0.0.1:1/physiocare_dev`, `DATABASE_NAME=physiocare_dev`, and Razorpay, payment reconciliation, and PDF scanner disabled. The command was `python -m pytest -q -p pytest_asyncio.plugin -p no:cacheprovider <selected tests>`; the three connected Mongo test files were never run.

| Check | Actual result |
| --- | --- |
| Group C plus clinical-pagination and API-contract backend files | **340 passed**, 1 pytest plugin rewrite warning, exit 0. The new Group C file contains 11 tests for doctor identity/assignment, 1,000+ totals, status/date predicates, page 21, reception projections, and role-limited summary routes. |
| All offline backend files except three connected Mongo files and fake Unix-socket scanner file | **952 passed**, 1 plugin rewrite warning, exit 0. No connected test was run. |
| Broader backend command excluding only the three connected Mongo files | **953 passed, 11 failed**, 1 plugin rewrite warning, pytest exit 1. All 11 failures occurred in `test_clamav_unix_scanner.py` when its fake server attempted a Unix-socket bind and the sandbox returned `PermissionError: [Errno 1] Operation not permitted`. The scanner tests were unchanged; no clean full-suite pass is claimed. |
| `npm test`; `npm run lint` | **140 passed, 0 failed, 0 skipped**, exit 0; lint exit 0. Group C has four new frontend checks, including rendered page-local/aggregate states and patient-switch request contracts. These are not interactive browser tests. |
| `npm run build -- --configLoader runner --outDir /private/tmp/physiocare-groupc-build --emptyOutDir` | Exit 0. Equivalent asset-budget check: **75** JS/CSS assets; zero over 450 KiB JS or 300 KiB CSS. |
| Python AST and pinned lock check | **159 Python files parsed; 48 applicable lock pins matched; zero mismatches.** The first local lock check incorrectly treated the `PyJWT[crypto]` extra as the installed package name; after normalizing that package name, the check passed. No dependency changed. |
| `git diff --check` | Exit 0. No commit or push. |

The tests use fictional identities and mocks. The rendered frontend tests exercise server-rendered output and source-level request contracts; they do not establish real browser cancellation, account-switch behavior, Mongo query-plan efficiency, or concurrent page stability. **Connected multi-clinician authorization: BLOCKED** until an exact approved isolated target is available. The fake ClamAV test suite still needs a socket-capable local environment, and operational scanner/private-storage, browser journeys, staging topology, backup restore, and payment Test Mode gates remain outside this pass. **Group C: IMPLEMENTED. Phase 24A closure: NOT PASSED. Phase 24B: BLOCKED. Client demo: HOLD. Production: FAIL.**
