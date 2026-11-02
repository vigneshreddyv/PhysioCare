# PhysioCare Phase 24A.2 — Residual Lists and Exercise Analytics

Assessment date: 2026-11-01. Branch: `codex/physiocare-integration-2026-10-31`; HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`. All work remains uncommitted.

## Decision

**Phase 24A closure: NOT PASSED. Client demo: HOLD. Production: FAIL. Phase 24B: BLOCKED.** Five of the 26 provisional large-list screens now have bounded page replacement, and lifetime exercise statistics now use patient-scoped MongoDB aggregation. Twenty-one screens still use the 1,000-record accumulation helper and require workflow-specific server contracts. The five changed screens have unit and static-render evidence, but no interactive browser, connected database, or more-than-1,000-record screen-level result. Their status is **IMPLEMENTED**, not fully **FIXED**. The aggregation has offline structural/output tests but no connected MongoDB correctness or query-plan evidence; it is also **IMPLEMENTED**.

The source inventory below supersedes any conflicting historical count. The prior Phase 24A closure report listed 26 screens; current source confirms those 26 components and 41 calls to `fetchClinicalPages` or `fetchClinicalHistoryPages` before this change. `PatientsList.jsx` was already separately paged and is outside this 26-screen set.

## Exact 26-screen inventory

Every listed component uses React Query and `frontend/src/services/clinicalPagination.js`. “Accumulated” means the old helper fetches successive 50-row pages into one array, then throws after retaining 1,000 distinct records. Patient-history endpoints accumulate two 50-row arrays under a combined 1,000-record budget. All endpoints are under `/api`; the paths below are relative to that prefix. Current backend list routes accept `page` and `page_size`, default to 50, cap size at 100, and cap page at 1,000. The strategy column distinguishes implemented code from required follow-up.

| # | Screen / component | Endpoint(s) | Multiple pages needed; current behavior | Navigation strategy / evidence | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Admin dashboard / `admin/AdminDashboard.jsx` | `/appointments` | Yes; accumulated appointments feed today/yesterday activity, so page-one totals would be false. | Add authorized date-window activity endpoint; keep `/analytics/stats` for aggregate totals. Dashboard tests need >1,000 appointments. | OPEN |
| 2 | Admin lab requests / `admin/AdminLabRequestsPanel.jsx` | `/lab-requests/admin` | Yes; previously accumulated review queue. | One 50-row page with Previous/Go/Next, per-page count and isolated mutation state. Static render plus shared page-21 tests. | IMPLEMENTED |
| 3 | Admin patient history / `admin/AdminPatientHistory.jsx` | `/users/patients/{id}/history` | Yes; two accumulated arrays and completed count. | Separate bounded history navigation and server summary for count, preserving patient authorization. | OPEN |
| 4 | Staff appointment booking / `admin/AppointmentBooking.jsx` | `/users/reception/patients` or `/users/patients` | Yes; accumulated patient selector. | Authorized server search plus bounded results; preserve receptionist visibility. | OPEN |
| 5 | Billing / `admin/Billing.jsx` | `/appointments` | Yes; accumulated records feed billing review. | Server-side billing/status/date filters and page replacement; verify totals independently. | OPEN |
| 6 | Care-plan management / `admin/CarePlanManagement.jsx` | `/users/patients`, `/care-plans/patient/{id}` | Yes; selector plus selected patient's plans. | Bounded patient search and separate plan pages; reset selected plan on patient change. | OPEN |
| 7 | Demo services / `admin/DemoServices.jsx` | `/home-visit-requests/admin`, `/appointments` | Yes; accumulated requests and filtered home bookings. | Separate request pages and server-filtered home booking pages. | OPEN |
| 8 | Exercise assignment management / `admin/ExerciseAssignmentManagement.jsx` | `/users/patients`, `/care-plans/patient/{id}`, `/exercises`, `/exercise-assignments?patient_id={id}` | Yes; four accumulated selectors/lists. | Search each selector server-side and page assignments within authenticated patient scope. | OPEN |
| 9 | Admin notifications view / `admin/Notifications.jsx` | `/appointments` | Yes; accumulated activity feeds today/yesterday summaries. | Date-window summary/activity API, not a partial page count. | OPEN |
| 10 | Report authoring / `admin/ReportAuthoring.jsx` | `/users/patients` | Yes; accumulated patient selector. | Authorized patient search with bounded suggestions. | OPEN |
| 11 | Notifications / `common/Notifications.jsx` | `/notifications`, `/notifications/unread-count` | Yes; previously accumulated notification list. | One page at a time; global unread count remains independent. Per-page badge and static render tested. | IMPLEMENTED |
| 12 | Doctor dashboard / `doctor/DoctorDashboard.jsx` | `/appointments`, `/lab-requests/doctor/reports` | Yes; appointments feed open/completed summaries and reports feed a list. | Server date/status summaries plus independent report pages. | OPEN |
| 13 | Doctor patient history / `doctor/DoctorPatientHistory.jsx` | `/users/doctor/patients/{id}/history` | Yes; two accumulated arrays, filters and status counts. | Filtered dual-list navigation plus server summary; keep assignment filter inside DB. | OPEN |
| 14 | Doctor home visits / `doctor/HomeVisits.jsx` | `/home-visit-requests/doctor` | Yes; previously accumulated assigned queue. | One page at a time with navigation, scoped query key and page count. Static render tested. | IMPLEMENTED |
| 15 | Laboratory dashboard / `laboratorian/LaboratoryDashboard.jsx` | `/lab-requests/laboratory/assigned` | Yes; previously accumulated assigned orders. | One page at a time; selected PDF and upload feedback state clear on page/identity change. Static render tested. | IMPLEMENTED |
| 16 | Patient appointment booking / `patient/BookAppointment.jsx` | `/appointments` | No full scan is justified; payment resume searches accumulated appointments for one ID. | Use the existing authorized appointment-by-ID contract after confirming payment semantics. | OPEN |
| 17 | Patient home visits / `patient/HomeVisitRequests.jsx` | `/home-visit-requests/me`, `/appointments` | Yes; request history and filtered home bookings. | Two independent pages; server-filter home bookings. | OPEN |
| 18 | Patient laboratory / `patient/LaboratoryRequests.jsx` | `/lab-requests/me`, `/lab-requests/me/reports` | Yes; two previously accumulated lists; catalogue search is separate static demo data. | Independent bounded request/report pages; reports deduplicate by `request_id`; existing partial-failure behavior tested. | IMPLEMENTED |
| 19 | Patient appointments / `patient/PatientAppointments.jsx` | `/appointments` | Yes; local status filter and sort over accumulated list. | Server-side status filter and stable page navigation; filter changes reset page. | OPEN |
| 20 | Patient care plan / `patient/PatientCarePlan.jsx` | `/care-plans`, `/care-plans/{id}/history`, `/care-plans/{id}/exercises` | Yes; selects active/latest plan, then accumulates two histories. | Dedicated active/latest query plus separate history/exercise pages and exact stage counts. | OPEN |
| 21 | Patient dashboard / `patient/PatientDashboard.jsx` | `/appointments`, `/lab-requests/me`, `/home-visit-requests/me` | Yes; accumulated data feed recent and upcoming summaries. | Scoped summary endpoints plus bounded recent previews. | OPEN |
| 22 | Patient exercises / `patient/PatientExercises.jsx` | `/exercises`, `/exercise-assignments` | Yes; catalogue/assignment join and category filter over accumulated arrays. | Server-side category/search and bounded assignment views; stats remain on aggregate endpoint. | OPEN |
| 23 | Patient history / `patient/PatientHistory.jsx` | `/appointments` | Yes; local lifecycle filter and sort over accumulated list. | Server-side lifecycle/date filtering and page navigation. | OPEN |
| 24 | Patient progress / `patient/PatientProgress.jsx` | `/care-plans` | No full scan needed to choose active/latest plan; exercise stats are a separate aggregate. | Bounded active/latest care-plan query; avoid suppressing later active plans. | OPEN |
| 25 | Patient reports / `patient/PatientReports.jsx` | `/reports` | Yes; title/category search over accumulated reports. | Patient-scoped server search plus page navigation; retain secure per-report PDF access. | OPEN |
| 26 | Reception dashboard / `receptionist/ReceptionistDashboard.jsx` | `/appointments/reception`, `/home-visit-requests/reception` | Yes; schedule and home request lists accumulate. | Date-window schedule navigation plus independent request pages. | OPEN |

For rows 2, 11, 14, 15 and 18, `fetchClinicalPage` requests only the selected page; query keys include authenticated user ID and page, with `gcTime: 0`. Changing identity resets the page to one, and the existing `AuthContext` cancels clinical requests and clears the query cache on logout/account change. React Query does not display a stale prior page for a new key. The API still returns arrays without total/next metadata, so the UI reports **only the count on the current page** and allows navigation to an empty page. Exact global totals, stable pagination under concurrent writes, and page 1,001+ need an explicit server contract. These are not claimed fixed.

The other 21 rows still retain the old helper and its 1,000-record failure. Replacing them with a single page without backend filter or summary work would silently falsify filters, selection, or totals. No such substitution was made.

## Exercise statistics

**Root cause:** `ExerciseService.get_exercise_progress_stats` previously loaded every patient assignment and progress record, every catalogue exercise, and every care plan into Python. Lifetime growth increased database transfer and process memory. The API route derives the patient from the authenticated account; the doctor route checks assigned-patient access before calling the same service.

**IMPLEMENTED:** `ExerciseRepository.aggregate_assignment_stats` matches the patient and excludes cancelled assignments before sorting and grouping totals, stages and latest targets. `aggregate_progress_stats` matches the patient before faceted totals, the current-week date window, the five most recent projected records, exercise breakdown and stage breakdown. The stage lookup rechecks assignment patient ID and non-cancelled status. Exercise titles are joined inside MongoDB; the active care-plan stage titles use one patient-scoped projected query. The service assembles the existing response fields and performs no full-document list read. No new API route or response contract was introduced.

Offline tests assert the pipeline's first patient filter, date/status conditions, projection, five-record recent limit, ownership recheck, empty response, large grouped totals, and retained service output shape. They do **not** execute MongoDB aggregation semantics. `exercise_breakdown` and `stage_breakdown` still contain one row per distinct exercise/stage and are not response-size bounded. A real high-cardinality dataset could reach MongoDB `$facet` output/memory limits; index suitability and correctness must be checked on an approved isolated fictional-data database. Do not treat a mocked large total as a 100,000-record database benchmark.

## Other analytics and query classification

| Candidate | Classification | Evidence and next action |
| --- | --- | --- |
| `AnalyticsService.get_clinic_stats` appointment period/weekly/status/revenue summaries | SAFE for bounded output; connected performance BLOCKED | Mongo `$match` precedes grouped facets; six-month revenue has `length=6`. Validate query plans and indexes in approved staging. |
| Clinic doctor specialization summary | REVIEW | Mongo groups by specialization, then returns all distinct groups. Cardinality is normally small but not enforced. Review maximum output with real policy and connected scale data. |
| Admin/doctor/patient/reception dashboard appointment and laboratory previews | FILTER or AGGREGATE | Several frontend screens still fetch accumulated lists to derive totals or recent items; rows 1, 9, 12, 21 and 26 above remain open. |
| Billing, patient history, patient reports, exercise selectors | PAGINATE + FILTER | Existing backend page routes are scoped, but frontend filters/selectors still depend on full accumulated arrays. Add targeted server filters and summary contracts. |
| Doctor released reports | BLOCKED connected review | Existing Mongo authorization `$lookup` filters doctor assignment before `$skip`/`$limit`, but cross-clinician results and `explain()` have not been measured on approved MongoDB. |
| Legacy unpaged repository/service branches | REVIEW | Some non-API callers still use `.to_list()` without a page. Confirm actual callers and bound them before treating them as safe operational paths. |

## Files changed in this Phase 24A.2 pass

- `backend/app/repositories/exercise_repository.py`, `backend/app/repositories/care_plan_repository.py`, `backend/app/services/exercise_service.py`: patient-scoped grouped exercise statistics and projected active stage titles.
- `backend/tests/test_exercise_progress.py`, `backend/tests/test_phase24a2_exercise_aggregation.py`: updated service fixtures and new aggregation, empty and large-summary checks.
- `frontend/src/services/clinicalPagination.js`, `frontend/src/components/common/ClinicalPageNav.jsx`: configurable per-page identity key and shared page navigation.
- `frontend/src/pages/admin/AdminLabRequestsPanel.jsx`, `frontend/src/pages/common/Notifications.jsx`, `frontend/src/pages/doctor/HomeVisits.jsx`, `frontend/src/pages/laboratorian/LaboratoryDashboard.jsx`, `frontend/src/pages/patient/LaboratoryRequests.jsx`: five bounded work queues.
- `frontend/tests/clinical-pagination.test.mjs`, `frontend/tests/navigation-contract.test.mjs`: >1,000 helper behavior, static screen integration and updated navigation contract.

Earlier Phase 16–24 changes and documentation were preserved. Neither application `.env` nor credentials were edited. No commit or push occurred.

## Verification and security evidence

Backend commands used Python 3.13 from `/private/tmp/physiocare-phase14-locked.36WQ5D/venv`, `env -i`, `PYTHONPATH` pointing to `backend`, `ENVIRONMENT=test`, an unreachable loopback URL at port 1, payment reconciliation and Razorpay mode disabled, PDF scanner disabled, plugin autoload disabled, and `-p pytest_asyncio.plugin -p no:cacheprovider`. The first full attempt supplied the synthetic database name `physiocare_test`; final focused and offline-remainder runs used `MONGODB_URL=mongodb://127.0.0.1:1/physiocare_dev` and `DATABASE_NAME=physiocare_dev`, matching the test's expected development identity. They ran from `/private/tmp`, so the repository's `.env` was not the settings file for this run. The three `*connected_mongo.py` files were explicitly excluded. No database connection or external service was used.

| Check | Actual result |
| --- | --- |
| Focused exercise, pagination, API contract, and query tests | 371 passed, 1 pytest plugin warning, exit 0 on the final tree. |
| Full offline attempt, excluding connected files | 894 passed, 12 failed, 1 pytest plugin warning, exit 1. Eleven fake ClamAV cases failed at Unix-socket `PermissionError`; one development-default test failed because the first synthetic environment supplied `DATABASE_NAME=physiocare_test`. That is a test-run configuration error, not an application assertion under the expected environment. |
| Offline remainder with corrected synthetic `physiocare_dev`, excluding scanner and connected files | 895 passed, 1 pytest plugin warning, exit 0 on the final tree. Scanner file excluded due the demonstrated Unix-socket sandbox limit, not counted as passed. |
| Frontend | 120 passed, 0 failed/skipped, exit 0. Includes current-page screen render tests, shared 1,250-row static traversal, page 21, deduplication, request cancellation, and existing laboratory partial-failure tests. Browser interaction with the five changed screens remains untested. |
| Frontend lint | `npm run lint`: exit 0. |
| Production build and asset budget | `npm run build -- --configLoader runner --outDir <temporary directory> --emptyOutDir`: exit 0. Equivalent budget check: 74 JS/CSS assets, no JS over 450 KiB or CSS over 300 KiB. The Vite runner config loader avoided a sandbox-denied temporary write in `node_modules`; the default loader attempt failed with `EPERM` before building. |
| Python syntax | AST parsed 147 backend Python files, exit 0. |
| Lockfile | Parsed `backend/requirements.lock` using `packaging.Requirement`: 48 applicable pinned distributions match the installed environment, exit 0. |
| Whitespace | `git diff --check`: exit 0 for tracked changes. |
| Secret scan | Gitleaks 8.30.1 `gitleaks dir --no-banner --redact=100 --report-format=json --report-path=<temporary redacted report> .`: 6 candidates, exit 1. All six are synthetic `submission_key` literals in `backend/tests/test_schedule_fallback_guard.py` and `backend/tests/test_api_contract.py`; their test-function context and literal AST were checked without displaying values. No Phase 24A.2 file was flagged. This is not a zero-finding scan. |

The backend security properties remain enforced by the existing API guards: patient records derive from the authenticated user, doctor patient access checks remain in place, and the new aggregation's first database stage matches patient ID. No auth, CSRF, PDF cache, authenticated JSON cache, payment or scanner code was changed in this phase. Prior inactive-account, PDF cache and authenticated JSON cache regressions are in the offline remainder; no new browser or connected confirmation is implied. The existing global clinical-request cancellation and query-cache clear remain untouched.

## Remaining gates and recommended next work

1. Complete the 21 open screens in workflow-sized changes. Start with server-side report title/category search, appointment status/date filters, patient picker search and exact dashboard summaries; add screen-specific interactive tests with >1,000 fictional records. Preserve stable sort keys plus unique tie-breakers and authorization inside DB queries. Do not treat the shared helper test as coverage for these screens.
2. Run unchanged fake ClamAV tests in a local socket-capable environment; the current sandbox cannot establish their behavior. Do not skip them in a release gate.
3. In an explicitly approved isolated staging target, validate the new aggregation against representative fictional data, index/query plans, group cardinality, doctor-report cross-clinician denial, and pagination under concurrent writes. No such connected test was authorized or run here.
4. Resolve the page-1,001 limit and large-offset cost with a justified keyset/cursor or bounded search contract before claiming arbitrary-depth navigation. API arrays currently have no exact total or `has_next` metadata.
5. Preserve Phase 17/20/21 infrastructure and ownership gates, approved operational scanner/private storage, backup restore, authenticated browser journeys and independent review. **Phase 24B remains blocked.**
