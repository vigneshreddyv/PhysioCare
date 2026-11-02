# Phase 24A — Authenticated cache and query hardening

Assessment date: 2026-11-01. Branch: `codex/physiocare-integration-2026-10-31`. HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`. All changes remain uncommitted.

## Executive summary and decision

| Finding | Status | Evidence and limit |
| --- | --- | --- |
| Authenticated account and clinical JSON lacked an explicit cache policy | **FIXED locally** | Actual ASGI HTTP tests verify `private, no-store` on successful, unauthenticated and forbidden responses. Ingress/browser cache behavior is **BLOCKED** pending approved staging. |
| Doctor released-report paging materialized every assigned patient ID | **IMPLEMENTED** | The paged service now asks MongoDB to test assignment before skip/limit. Offline pipeline/dispatch tests pass; query plan, indexes, scale and connected authorization remain **BLOCKED**. |
| Legitimate lists above 1,000 records were unavailable | **IMPLEMENTED for the patient directory only** | The directory replaces one 50-row page at a time and can request page 21. Other whole-list consumers, page 1001+, server-side search and large-offset cost remain **OPEN**. |
| Exercise lifetime progress and other residual reads | **OPEN** | Source inventory below; no truncation or speculative aggregation was introduced. |
| Full backend suite | **FAIL in this sandbox** | 889 passed, 11 failed, 1 skipped. All 11 failures are fake ClamAV Unix-socket `PermissionError` cases. This is not a fresh full-suite pass. |

**Client demo: HOLD. Production: FAIL. Phase 24B final verification should not be presented as a completion gate yet.** The remaining large-list and query work, socket-capable full-suite run, and connected operational validation must be resolved or explicitly scoped out by the owner.

## Cache finding and correction

`GET /api/auth/me` returned account/profile JSON without `Cache-Control`. The route itself had no cache policy, and there was no shared authenticated-response policy. The same gap applied to other authenticated JSON routes. The new response middleware in `backend/app/main.py` inspects resolved FastAPI dependencies after routing. It covers routes requiring `get_current_user` or `RoleChecker`, including nested dependencies, plus the session-issuing login, refresh, CSRF and logout routes. It applies `Cache-Control: private, no-store`, `Pragma: no-cache` and `Expires: 0` to successful and handled error responses. A route-specific weaker cache header is replaced. The existing clinical PDF `private, no-store, no-cache, must-revalidate` header is retained. OPTIONS, public doctor listing, public registration, the payment webhook and non-API routes retain their previous policy. No authentication, CSRF, cookie or CORS dependency was removed.

Source inspection found 106 nested API routes: 99 declare authentication dependencies; the remaining seven are registration, login, refresh, CSRF, logout, public doctor listing and the webhook. HTTP tests directly cover admin/patient/doctor `/auth/me`, unauthenticated `/auth/me`, login and refresh cookies/body, an admin patient profile, clinical reports, wrong-role 403 and public routes. Existing HTTP PDF tests cover clinical and laboratory downloads, range responses and denials. The middleware's weaker-header override also has a direct regression test. CDN, reverse proxy and browser caches were not contacted.

## Query inventory and changes

| Candidate and collection | Classification | Current assessment |
| --- | --- | --- |
| `LabRequestService.list_doctor_released_reports` → released `lab_requests` and `appointments` | **AGGREGATE — IMPLEMENTED** | The paged API uses a Mongo `$lookup` requiring matching patient and doctor IDs and `doctor_assignment_pending != true`, followed by authorization match, skip and limit. Sort is stable on release date and `_id`. No assigned-patient ID array is loaded into Python. The legacy unpaged service branch remains available to non-API callers and is **OPEN**. |
| `ExerciseService.get_exercise_progress_stats` → `exercise_assignments`, `exercise_progress`, `care_plans`, `exercises` | **AGGREGATE/PROJECT — OPEN** | It loads lifetime patient assignments/progress and the entire exercise catalogue for weekly, recent and breakdown values. A correct fix needs database summaries and bounded output without changing patient ownership or completion semantics. |
| `ExerciseRepository.list_progress_by_assignment` → `exercise_progress` | **PAGINATE/REVIEW — OPEN** | Assignment scoped, but lifetime unbounded. Check actual operational caller and volume before changing contract. |
| `AppointmentRepository.list_active_by_doctor_id` → `appointments` | **FILTER — SAFE for current scheduling callers** | Phase 23D passes selected-day/horizon windows and keeps every possible conflict. The no-window compatibility path and future callers require review; truncating candidates could hide a booked slot. |
| `AnalyticsService` counts and dashboard summaries → appointments/doctors | **AGGREGATE — previously implemented** | Current count/aggregate paths avoid full document materialization; no Phase 24A change. |
| Paged clinical API paths → appointments, reports, lab requests, histories, notifications, care plans, exercises, patients | **PAGINATE — previously implemented** | Phase 23C filters owner/role before stable sort and skip/limit, 50 default, 100 maximum, page 1000 maximum. Connected explain/index and concurrent-write consistency remain **BLOCKED**. |
| `UserRepository.list_staff`, laboratory catalogue, lab demo, payment maintenance and older unpaged repository methods | **REVIEW — OPEN** | Some are operationally small or demo-only; others could grow. Confirm active callers, cardinality and necessary output before filtering or paging. |

The doctor aggregation still may scan many released reports or appointments; moving the stable sort before the join permits an appropriate release-order index, but no index or query plan was measured. The exact lookup and authorization semantics require an approved isolated connected test. No database was contacted in this phase.

## Frontend 1,000-record assessment

`fetchClinicalPages` and `fetchClinicalHistoryPages` are still used by 26 other page modules for dashboards, history, bookings, payments, care plans, reports, laboratory views and notifications. Their bounded 1,000-record accumulation remains an explicit error. Some views need server-side filters or date windows before page navigation can preserve their existing search and summary behavior. Multiple cached whole-list queries may retain more than 1,000 records in aggregate. These are **OPEN**, not silently considered fixed.

`frontend/src/services/clinicalPagination.js` now also offers `fetchClinicalPage(path, page)`, which requests exactly one 50-record page, deduplicates IDs, shares concurrent identical calls and rejects stale responses after authentication cancellation. `PatientsList.jsx` uses page-and-identity query keys, zero garbage-collection retention after a page becomes inactive, previous/next and direct page controls, plus retry/return navigation on errors. A rendered test checks the bounded page UI; service tests request page 21 (records beyond the former 1,000-record ceiling), deduplication, validation, sharing and logout cancellation. The backend remains authoritative for role and ownership. The frontend does not retain earlier directory pages in this flow.

The backend still rejects page above 1000. Offset page 1000 at 50 per page can skip 49,950 rows and can drift under concurrent writes. The current directory UI cannot reach page 1001 or supply server-side search, and clinician/reception pages may be sparse after inactive records are filtered. A stable authorized cursor or filtered search contract and connected index review are needed for those scenarios. No API contract was changed in Phase 24A.

## Files changed in this phase

- `backend/app/main.py` — shared authenticated-response cache policy.
- `backend/app/repositories/lab_request_repository.py`, `backend/app/services/lab_request_service.py` — paged doctor released-report authorization in MongoDB.
- `backend/tests/test_authenticated_cache_headers.py`, `backend/tests/test_phase24a_query_hardening.py` — new offline HTTP and query tests.
- `frontend/src/services/clinicalPagination.js`, `frontend/src/pages/admin/PatientsList.jsx` — page-replacement helper and patient-directory navigation.
- `frontend/tests/clinical-pagination.test.mjs`, `frontend/tests/navigation-contract.test.mjs` — pagination behavior, rendered directory and navigation contracts.
- This report.

All Phase 16–24 reports, prior implementation work and existing uncommitted files were preserved. No `.env`, credential, lockfile, deployment or infrastructure file was changed by Phase 24A.

## Fresh verification

Tests used the existing 48-pin Python 3.13 locked environment, `env -i` with synthetic local test settings, a non-serving loopback URI ending at port 1, disabled payments/reconciliation/scanner, and no application lifespan or database initialization. The two connected transaction test files were explicitly excluded; the connected throttling test self-skipped. No MongoDB, Atlas, Razorpay, ClamAV daemon or external service was contacted.

| Check | Command or method | Result |
| --- | --- | --- |
| Focused backend auth/API/cache/PDF/query/pagination | `python -m pytest -q ... test_authenticated_cache_headers.py test_pdf_cache_headers.py test_phase24a_query_hardening.py test_phase23d_query_hardening.py test_clinical_pagination.py test_auth_session_rotation.py test_api_contract.py` | **372 passed**, 1 pytest plugin rewrite warning; exit 0. |
| Full available offline backend | `python -m pytest -q --tb=line -rs ... backend/tests --ignore=backend/tests/test_report_transaction_connected_mongo.py --ignore=backend/tests/test_account_registration_connected_mongo.py` | **889 passed, 11 failed, 1 skipped**, 1 pytest plugin rewrite warning; exit 1. Eleven fake ClamAV tests failed at Unix-socket bind with `PermissionError: [Errno 1] Operation not permitted`. Skipped connected throttling contract was not enabled. |
| Frontend | `npm test` | **113 passed**, 0 failed/skipped; exit 0. |
| Lint | `npm run lint` | Exit 0. |
| Production build | `npm run build -- --configLoader runner --outDir /private/tmp/physiocare-phase24a-build-final --emptyOutDir` | Exit 0. |
| Asset budget | Count and size of fresh build assets | 73 assets; largest JS 373,260 B < 460,800 B; largest CSS 254,380 B < 307,200 B. |
| Python syntax | AST parse of backend app and new tests | 95 files parsed. |
| Lock consistency | Compare each `backend/requirements.lock` pin with installed metadata | 48 pins, 0 mismatches. No advisory lookup was run. |
| Whitespace | `git diff --check` | Exit 0. |
| Secret scan | `gitleaks dir . --redact=100` and `gitleaks git . --log-opts=--all --redact=100`, version 8.30.1 | Exit 1 for findings: six current-tree and five historical candidates, all in existing test files and at the same locations previously classified as synthetic fixtures in Phase 24. No new candidate was identified. Redacted output only; no values were printed in this report. This is not proof that no undiscovered secret exists. |

The initial full backend attempt before the final tests gave 887 passed, 11 failed, 1 skipped; the table reports the final-tree run. The full-suite failure remains a verification gate even though focused tests passed.

## Remaining work and connected gates

1. **OPEN:** migrate genuinely large whole-list screens to bounded page replacement with server-side filtering/search or date windows; preserve their existing sorting and search semantics. Provide cursor navigation where page 1001+ or high offsets are plausible. Measure memory and account-switch behavior in a browser.
2. **OPEN:** aggregate/project lifetime exercise statistics and assess the remaining internal unpaged callers. Keep conflict checks complete and clinical owner filters in MongoDB.
3. **BLOCKED:** rerun the unchanged full backend suite in a local socket-capable sandbox and investigate any remaining failure. Run connected doctor-report lookup correctness and index/explain tests only against an explicitly approved isolated fictional-data target.
4. **BLOCKED:** verify no-store behavior through the eventual approved ingress/browser cache path, real scanner/private storage, multi-worker Mongo/proxy authorization workflows, backup restore and payment Test Mode if required. Phase 17 staging ownership and topology remain unapproved.

This is an application-focused source and offline test review, not an independent security audit or production approval.
