# Phase 24A closure re-verification

Date: 2026-11-01. Branch: `codex/physiocare-integration-2026-10-31`. HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`. The worktree remains uncommitted; earlier Phase 16–24 changes were preserved.

## Decision

**Phase 24A closure: NOT PASSED. Client demo: HOLD. Production: FAIL. Phase 24B: BLOCKED.** The authenticated JSON cache policy passes local HTTP checks, and the patient-directory sparse-page defect found in this review is fixed. The unchanged fake ClamAV socket tests cannot run to their protocol assertions in this sandbox. Doctor report authorization and query performance lack a connected isolated MongoDB result. The other large-list screens and lifetime exercise statistics remain open. None of those gaps is treated as a passing check.

## Changes and files audited

Reviewed `backend/app/main.py`, `backend/app/api/auth.py`, `backend/app/api/users.py`, `backend/app/api/lab_requests.py`, the two clinical PDF routes, `backend/app/repositories/lab_request_repository.py`, `backend/app/repositories/appointment_repository.py`, `backend/app/repositories/profile_repository.py`, `backend/app/services/lab_request_service.py`, `backend/app/services/exercise_service.py`, `backend/app/services/pdf_malware_scanner.py`, `backend/app/core/pagination.py`, `frontend/src/services/clinicalPagination.js`, `frontend/src/pages/admin/PatientsList.jsx`, `frontend/src/context/AuthContext.jsx`, their focused tests, and the Phase 24A report. The repository still has substantial earlier uncommitted work; no reset, clean, stash, commit or push was performed.

This review changed only:

- `backend/app/main.py`: reuse the private cache-header policy for the early unsafe-origin 403 response, which previously escaped the inner cache middleware.
- `backend/tests/test_authenticated_cache_headers.py`: HTTP regressions for that early 403 and for an authenticated 404 patient-profile response.
- `frontend/src/pages/admin/PatientsList.jsx`: allow Next on a short administrator page. The backend can filter missing user records after fetching a database page, so a short response does not prove that later pages are empty.
- `frontend/tests/clinical-pagination.test.mjs`: static 1,250-record page traversal and rendered sparse-page, loading and empty-state regressions.
- This closure report.

No `.env`, credential, dependency, lockfile, payment, scanner or database configuration was modified.

## 1. Fake ClamAV failures

`backend/tests/test_clamav_unix_scanner.py` has 12 cases: four verdict mappings, one missing-socket fail-closed case, readiness, disconnect, timeout and four upload-path combinations. Eleven create a temporary fake daemon with `asyncio.start_unix_server`; the missing-socket case does not. A separate temporary Unix-socket bind probe failed with `PermissionError`, errno 1. A fresh run of the unchanged scanner test file produced **11 failed, 1 passed**. Each failure stopped at `asyncio/unix_events.py:321` during server bind, before scanner protocol or storage assertions; there were no protocol assertion failures in that run. This supports an **environmental cause for all 11 observed failures**, but it does not prove that the unexecuted protocol behavior is defect-free.

A portable supplemental strategy is to inject in-memory fake `StreamReader`/`StreamWriter` transports into `asyncio.open_unix_connection` and assert `zPING`, `zINSTREAM`, length framing, termination, verdict mapping, disconnect and timeout behavior. Keep the current real Unix-socket fake-daemon tests unchanged and mandatory in a socket-capable local/CI environment. Do not replace them with mocks or skip them merely to produce a green suite. A real approved ClamAV daemon remains a separate staging gate. No fake-daemon test was edited in this review.

## 2. Authenticated JSON cache policy

The middleware checks resolved FastAPI route dependencies for `get_current_user` or `RoleChecker`; login, refresh, CSRF and logout are explicitly included. An offline route inventory found 106 API routes, 99 with authentication dependencies and seven session/public/webhook routes without them. Actual ASGI HTTP checks cover `/api/auth/me` for administrator, patient, doctor and unauthenticated callers; login and refresh cookies; an administrator patient profile; clinical report JSON; wrong-role 403; public doctor/root responses; and the two existing private PDF delivery paths. The stronger PDF cache policy remains intact.

During this audit, an unsafe-origin POST returned a generic 403 before the cache middleware, with no `Cache-Control`. It contained no sensitive fields, but it was an inconsistent auth response path. The early 403 now shares the same header setter. Fresh HTTP probes and tests show `Cache-Control: private, no-store` on authenticated success, 401, 403, 404 and 422 paths, and on that early origin rejection; `Pragma: no-cache` and `Expires: 0` are also present. A weaker route-specific cache header is overwritten. Public non-sensitive routes keep their existing behavior. No CSRF, CORS or cookie enforcement was weakened. Unhandled ASGI errors and eventual ingress/browser cache behavior were not proven by these local tests; a generic outer 500 is not a source of clinical JSON in the inspected code.

**Local cache finding: FIXED through HTTP-level tests. Ingress validation: BLOCKED.**

## 3. Doctor released-report authorization

The paged API passes an authenticated doctor user ID to `LabRequestService`, which resolves the doctor profile, then passes that profile's ID to `LabRequestRepository.list_page_released_for_doctor`. Its Mongo pipeline matches released reports, sorts by release timestamp and `_id`, joins `appointments` on the report's patient ID plus the authenticated doctor's ID and `doctor_assignment_pending != true`, requires a nonempty assignment, and only then applies `$skip`/`$limit`. A missing doctor profile returns an empty list without querying. The route rejects wrong roles and invalid page parameters; the pagination guard limits page to 1–1000 and size to 1–100. Offline tests verify pipeline shape, filter-before-page order, service dispatch, empty profile, role rejection and invalid pages.

This provides a **fail-closed structural authorization design**, but the tests mock the collection. They do not execute the lookup against MongoDB or demonstrate that another clinician's report is absent in a connected multi-clinician dataset. No query `explain()`, index selectivity, large-offset cost or concurrent-write behavior was measured. The legacy unpaged service branch still materializes assignments for non-API callers. **Connected correctness/performance: BLOCKED; legacy branch: OPEN.**

## 4. Patient-directory pagination

The directory asks `fetchClinicalPage` for one 50-record page, keyed by user ID, role and page in React Query with `gcTime: 0`. The helper deduplicates IDs within a page, shares identical in-flight requests and rejects stale results after authentication cancellation. The backend patient directory uses `_id` ordering, and assigned-doctor IDs are grouped/sorted before paging. A fresh mocked 1,250-record traversal retrieved pages 1–25 in order with 1,250 unique IDs and no missing IDs for that **static dataset**. A rendered test confirms one page of rows, sparse-page Next navigation, loading and empty states; an existing rendered test covers a recoverable error without stale patient rows. The directory can request page 21 without first retaining 1,000 earlier records.

The audit found and fixed a real navigation defect: the admin Next button had been disabled whenever the rendered page had fewer than 50 rows, although the backend may omit missing user accounts after paging. Next now stays available through the supported page range; an empty or sparse page does not prematurely stop navigation. The tradeoff is that users may visit an empty last page because the API has no `has_more` metadata.

**Limits:** `MAX_RETAINED_CLINICAL_RECORDS = 1000` still applies to 26 other whole-list page modules. The directory itself remains bound by backend/frontend page 1000; page 1001+ is inaccessible. Offset pagination can repeat or miss records during concurrent inserts/deletes, even with deterministic sorting. The 1,250-record test is mocked and static, not a connected or interactive browser proof. Per-page deduplication does not reconcile duplicates across changing pages. These items are **OPEN**, so the broad claim that no 1,000-record browser limit remains would be false.

## 5. Residual query and usability inventory

| Area | Risk and affected path | Follow-up |
| --- | --- | --- |
| Other large-list screens | 26 pages still call `fetchClinicalPages` or `fetchClinicalHistoryPages`, including appointments, reports, notifications, lab requests, care-plan views and dashboards. Lists above 1,000 still raise an error. | Add server-side filters/date windows, page replacement or authorized cursors per workflow; preserve search and summary semantics and test account switching in a browser. |
| Exercise lifetime statistics | `ExerciseService.get_exercise_progress_stats` loads all patient assignments and progress plus the catalogue and care plans. | Database-side aggregate/project with bounded breakdown output and patient ownership tests. |
| Doctor reports | New `$lookup` may scan many released reports or appointments; index suitability is unknown. | Approved isolated Mongo query-plan, multi-clinician negative and high-volume tests. |
| Older internal reads | The unpaged doctor-report branch, assignment progress, staff/catalogue and payment maintenance methods retain unbounded reads. | Audit runtime callers and cardinality, then filter/project/page where appropriate. Do not truncate appointment conflict checks. |

## 6. Fresh verification

All backend tests used the existing locked Python 3.13 environment with synthetic `ENVIRONMENT=test` settings, disabled scanner and payments, and a non-serving loopback Mongo URI at port 1. The two connected transaction files were explicitly excluded, and no application lifespan, external database, provider or service was started. Commands below omit synthetic environment values but retain their test selection.

| Check | Command/selection | Actual result |
| --- | --- | --- |
| Scanner file, unchanged | `python -m pytest -q --tb=line -rs backend/tests/test_clamav_unix_scanner.py` | **11 failed, 1 passed**, 1 pytest plugin warning; exit 1. All failures at sandbox Unix bind. |
| Full available offline remainder | `python -m pytest -q --tb=line -rs backend/tests --ignore=backend/tests/test_clamav_unix_scanner.py --ignore=backend/tests/test_report_transaction_connected_mongo.py --ignore=backend/tests/test_account_registration_connected_mongo.py` | **890 passed, 1 skipped**, 1 pytest plugin warning; exit 0. Skipped connected rate-limit test was not enabled. This is an explicit subset, not a full-suite pass. |
| Focused auth/cache/PDF/query/pagination/API | `python -m pytest -q ... test_authenticated_cache_headers.py test_pdf_cache_headers.py test_phase24a_query_hardening.py test_clinical_pagination.py test_phase23d_query_hardening.py test_auth_session_rotation.py test_api_contract.py` | **374 passed**, 1 pytest plugin warning; exit 0. |
| Frontend | `npm test` | **116 passed**, 0 failed/skipped; exit 0. |
| Frontend lint | `npm run lint` | Exit 0. |
| Production build | `npm run build -- --configLoader runner --outDir /private/tmp/physiocare-phase24a-closure-build-final --emptyOutDir` | Exit 0. |
| Asset budget | Fresh build asset inspection | 73 assets; largest JS 373,260 B under 460,800 B; largest CSS 254,380 B under 307,200 B. |
| Python syntax | AST parse of `backend/app` and `backend/tests` | 140 files parsed. |
| Dependency lock consistency | Compare installed metadata against `backend/requirements.lock` | 48 pins, zero mismatches. No new vulnerability advisory lookup. |
| Whitespace | `git diff --check` | Exit 0. |

The last attempted combined full backend run before this closure audit was **889 passed, 11 failed, 1 skipped**; the newly added 404 test is included in the fresh explicit remainder/focused counts above. The current sandbox's Unix bind denial means a reliable complete run was not possible here. Previous connected report-transaction evidence belongs to Phase 15 and does not validate the new doctor-report aggregation.

## Required closure work

1. Run the **unchanged** 12 scanner cases and the complete backend suite in a socket-capable local or CI environment; investigate any protocol assertion that then fails.
2. Complete large-list navigation for the remaining high-volume screens and address page 1001+/offset drift through a justified search/cursor contract.
3. Replace lifetime exercise statistics and remaining active unbounded reads with bounded database-side work, with correctness tests.
4. In an explicitly approved isolated fictional-data Mongo target, verify doctor-report cross-clinician denial, assignment changes, pagination and query plan/index behavior. Separately verify cache policy through approved ingress/browser paths.

No staging, deployment, connected MongoDB test, Razorpay call, real ClamAV daemon, commit or push occurred. This is a focused closure audit, not an independent security signoff.
