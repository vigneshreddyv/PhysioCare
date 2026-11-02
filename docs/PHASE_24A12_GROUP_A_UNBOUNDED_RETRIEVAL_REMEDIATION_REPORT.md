# Phase 24A.12 Group A — Unbounded Retrieval Remediation Report

Assessment and implementation date: 2 November 2026  
Branch: `codex/physiocare-integration-2026-10-31`  
Baseline commit: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

Phase 24A.12 Group A is **PASS** for its bounded offline implementation scope. The three confirmed Phase 24A.11 findings addressed here are:

- **A11-M01:** patient payment history was unbounded and performed one appointment lookup per payment;
- **A11-M02:** an omitted entitlement search selected an unbounded all-patient, two-lookups-per-patient fallback;
- **A11-M03:** the administrator staff directory was unbounded.

All three registered paths now enforce the shared page contract (default 50, maximum 100, page 1..1000), filter before pagination, sort deterministically, materialize no more than the requested page, and return only their existing consumer fields. Payment and staff screens now replace one page at a time. The existing entitlement screen was already page-replacing; the server now uses its bounded aggregation for omitted, empty, whitespace, and populated searches.

Patient ownership and role boundaries remain intact. Booking eligibility does not use a directory page: it still performs the unique, patient-targeted entitlement lookup. No payment state transition, staff mutation/onboarding behavior, or entitlement grant/revoke rule changed.

This is not a performance claim against a connected MongoDB deployment and is not client-demonstration, staging, or production authorization. Groups B, C, and D are unstarted. Phase 24B remains blocked.

## 2. Scope and initial Git state

The Phase 24A.11 endpoint inventory, residual finding register, residual audit, Phase 24A.10 report, Phase 24A.9 review, and Phase 24A.8 closure report were read before implementation. The actual route-to-query paths were traced independently.

Initial repository state:

| Item | Verified initial value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | 0 / 0 |
| Tracked modifications | 88 |
| Untracked paths | 74 |
| Total dirty paths | 162 |

The three Phase 24A.11 documents were present as untracked files and remain unmodified:

- `docs/PHASE_24A11_API_ENDPOINT_INVENTORY.md`
- `docs/PHASE_24A11_RESIDUAL_SECURITY_AND_QUERY_FINDINGS.md`
- `docs/PHASE_24A11_RESIDUAL_ENDPOINT_AUDIT_REPORT.md`

No reset, clean, checkout, restore, stash, branch switch, commit, push, dependency change, environment-file edit, migration, index operation, deployment, or external-service connection was performed.

## 3. Exact findings and affected endpoints

| Finding | Endpoint | Original path | Result |
|---|---|---|---|
| A11-M01 | `GET /api/payments/history` | patient filter -> unbounded payment attempts -> one appointment read per result | Closed in Group A |
| A11-M02 | `GET /api/demo-services/entitlements` when search omitted | all patients -> user and entitlement read per patient | Closed in Group A |
| A11-M03 | `GET /api/users/staff` | all staff roles -> unbounded sorted materialization | Closed in Group A |

The registered application surface remains 119 unique operations. No endpoint was added or removed.

## 4. Payment-history remediation

The route at `backend/app/api/payments.py:25` now accepts bounded `page` and `page_size` parameters plus optional status and inclusive calendar-date filters. It rejects an inverted date range. Access remains patient-only.

`backend/app/services/payment_service.py:605` still resolves the patient profile from the authenticated user ID. It then calls the dedicated query repository once instead of materializing every attempt and calling `Appointment.get` per row.

`backend/app/repositories/payment_query_repository.py:13` performs one aggregation:

1. `$match` on the authenticated patient's `patient_id`, optional payment status, and optional UTC creation-date interval;
2. stable `$sort` by `created_at` descending and `_id` descending;
3. `$skip` and `$limit` from the validated `PageWindow`;
4. one `$lookup` for the page's appointment display fields;
5. null-preserving `$unwind` so a legacy orphan does not drop a payment-history record;
6. an explicit projection.

The projection excludes provider order/payment identifiers, processed webhook IDs, reconciliation timestamps, and unrelated appointment/clinical fields. The response retains transaction status, reconciliation status, amount/currency, and the appointment fields previously shown by the patient screen. No Razorpay, verification, reconciliation, cancel, abandon, webhook, or order behavior changed.

The patient screen at `frontend/src/pages/patient/PatientPaymentHistory.jsx:17` uses one `fetchClinicalPage` result, provides status/from/to filters, resets to page 1 when a filter changes, exposes page navigation, and preserves loading, retryable error, empty, and display states. It does not accumulate earlier pages.

## 5. Staff-query remediation

The admin-only route at `backend/app/api/users.py:60` now accepts the shared page parameters, a 100-character search, a supported staff role filter, and active/inactive account status. Omitting account status intentionally includes both states, preserving the administration workflow.

`backend/app/repositories/user_repository.py:44` applies the staff-role predicate, optional status, and escaped name/email search before pagination. It sorts by `full_name` ascending and `_id` ascending, then uses `$skip`, `$limit`, and `to_list(length=page.size)`. The raw Mongo projection contains only `_id`, name, email, role, active state, and creation time. Password hashes, tokens, demo tags, and other user fields are not fetched or serialized.

Email remains present because the existing administrator directory displays and searches it; it is not exposed to a broader role. Staff creation, activation semantics, onboarding, and other staff selectors were not changed.

`frontend/src/pages/admin/StaffManagement.jsx:27` now sends search, role, and status to the server and displays only the current page. Search uses `useDeferredValue`; filter changes reset to page 1. Loading skeleton, recoverable error, no-account/no-match states, page navigation, and the existing staff-creation workflow remain.

## 6. Entitlement-query remediation

The defect was the omitted-search branch, not the existing aggregation. `backend/app/api/home_visits.py:44` now always calls `HomeVisitService.search_admin_entitlements`, normalizing a missing or whitespace search to the empty string. The obsolete unbounded service fallback was removed.

The reused aggregation in `backend/app/repositories/demo_service_repository.py` starts with the patient role and optional escaped name/email search, joins the matching patient and entitlement, sorts by `full_name` and `_id`, applies skip/limit, and projects only the administrator directory's patient ID/name/email/phone and current `active` flag. It is consumed with `to_list(length=page.size)`.

This repository does not contain an entitlement-history ledger or expired/consumed entitlement states. `DemoEntitlement` is a unique current grant per patient with `active`, grant metadata, and `revoked_at`. Therefore Phase 24A.12 did not invent expiry or consumption policy. Inactive/revoked current state remains denied, grant/revoke behavior remains unchanged, and the feature flag still participates in the displayed/authorized active result.

The critical authorization distinction is preserved at `backend/app/services/home_visit_service.py:55`: booking eligibility resolves the authenticated patient's profile and calls `get_entitlement(patient_id)` directly. It never consults an arbitrary entitlement-directory page, so a valid grant cannot be omitted by pagination and another patient's grant cannot satisfy the decision.

The existing `DemoServices` screen already used page replacement, server search, page-keyed requests, and `ClinicalPageNav`; no frontend entitlement change was required.

## 7. Pagination and response behavior

All three routes reuse `backend/app/core/pagination.py`:

- default page size: 50;
- maximum page size: 100;
- valid page numbers: 1 through 1000;
- invalid page or size: HTTP 422.

The API's existing list response contracts were preserved. `frontend/src/services/clinicalPagination.js` wraps a list as `{data, page, hasNext}`, validates the response is no larger than the requested 50-item UI page, deduplicates within the page, and replaces rather than accumulates. A full page exposes the next-page action rather than claiming the result is complete. Page identity is included in request keys, identical in-flight requests are shared, and authentication/session cancellation rejects stale results.

Offset pagination cannot promise a transactionally frozen view while records are concurrently inserted or renamed. The stable `_id` tie-breakers prevent ambiguous ordering for a stable dataset. Connected concurrency and representative-volume behavior remain an environment gate.

## 8. Query strategy, privacy, and complexity

| Path | Before | After | Materialized application rows |
|---|---|---|---:|
| Payment history | profile + unbounded payment query + N appointment queries | profile + one bounded aggregation/lookup | at most page size |
| Staff directory | one unbounded staff query | one projected, filtered, bounded query | at most page size |
| Entitlement admin directory, omitted search | all patients + approximately 2N related reads | one filtered, joined, bounded aggregation | at most page size |
| Booking entitlement decision | targeted patient + targeted unique entitlement | unchanged targeted patient + targeted unique entitlement | one eligibility subject |

Query-shape tests inspect the generated Mongo filters/pipelines rather than only response values. They assert filter-before-page ordering, stable sorts, offsets beyond 1,000 records, explicit limits, bounded cursor consumption, projections, escaped regex values, a single payment join for 50 rows, and the absence of provider IDs/password hashes. Empty repository results remain empty response lists without a fallback query.

## 9. Authorization and ownership verification

Fresh route-dependency assertions verify:

- payment history: patient only;
- staff directory: admin only;
- entitlement directory: admin only.

Payment ownership is derived server-side from the authenticated user and its patient profile; clients cannot supply a patient ID. The repository receives that resolved patient ID as its first match predicate. Separate administrator billing/reconciliation endpoints are unchanged.

Entitlement administration remains admin-only. Patient entitlement display and booking eligibility derive the patient from the authenticated user. Active targeted entitlement permits the eligibility gate; inactive/revoked state returns 403. Existing feature-disabled, missing-entitlement, grant/revoke, booking, appointment, and role-contract regressions were included in the focused or neighboring test selections.

No cross-patient or cross-role disclosure was identified in the modified paths.

## 10. Frontend verification

The two newly affected screens use bounded page replacement:

- Patient Payment History: page, status, start date, end date, previous/next, loading, error, empty, and current-page display.
- Staff Management: deferred server search, role/status filters, previous/next, loading skeleton, recoverable error, empty/no-match, and current-page display.

The entitlement screen's existing bounded integration was retained. Shared pagination tests cover exact full pages, pages beyond 1,000 records, request sharing, stale-session rejection, page bounds, and no prior-page retention. The full frontend suite covers authentication rendering, payment resume/status, admin billing, staff creation/role routing, home-visit booking, clinician assignment, dashboards, and related page controls.

## 11. Fresh test and quality results

Backend tests ran from `/private/tmp` with the existing locked Python 3.13 environment, `env -i`, synthetic distinct secrets, `ENVIRONMENT=test`, an intentionally unreachable loopback MongoDB port, payment/reconciliation/scanner modes disabled, plugin autoload disabled, explicit `pytest_asyncio`, no pytest cache provider, and no connected-test opt-in. No database or external service was contacted.

| Check | Fresh result |
|---|---:|
| Final Group A + payment history + API contract + existing admin Group B2 focused backend selection | **147 passed** |
| Neighboring payment/billing/appointment/pagination/clinician/home-visit/auth/dashboard backend selection | **375 passed** |
| Complete backend excluding only `test_clamav_unix_scanner.py` | **998 passed, 3 connected-only skipped** |
| Literal complete backend suite | **999 passed, 11 AF_UNIX environment failures, 3 connected-only skipped** |
| Focused affected frontend selection | **50 passed** |
| Complete frontend | **159 passed** |
| Frontend lint | **PASS** |
| Production build | **PASS**, Vite 8.3.5, 1,838 modules |
| Asset budget | **74 JS/CSS assets**, zero violations |
| Python syntax | **166 files parsed**, zero failures |
| Dependency-lock tests | **2 passed** |
| `pip check` | **No broken requirements found** |
| Offline `npm audit --audit-level=low` | **0 locally cached vulnerabilities**; cache freshness unknown |
| Redacted Gitleaks current-tree scan | **6 existing synthetic fixture findings**, none in a Group A path |
| Static application route inventory | **119 unique operations** |
| `git diff --check` | **PASS** |

The recurring warning is the pre-existing already-imported `pytest_asyncio` assertion-rewrite warning. The three skips are the explicitly guarded connected registration, distributed-rate-limit, and report-transaction contracts. The 11 failures all occur when the sandbox rejects `asyncio.start_unix_server` with `PermissionError` in the existing fake ClamAV integration file; the same run passes 999 other tests. No assertion, skip, or scanner behavior was weakened.

The six redacted Gitleaks detections remain five synthetic idempotency fixtures in `backend/tests/test_api_contract.py` and one in `backend/tests/test_schedule_fallback_guard.py`. This is not a zero-finding or Git-history scan.

## 12. Recommended indexes — unverified and not applied

No index was created, altered, queried from a deployment, or measured. The following are review candidates only:

| Collection | Candidate order | Rationale / limitation |
|---|---|---|
| `payment_attempts` | `patient_id:1, created_at:-1, _id:-1` | Supports the ownership match and default stable history sort. |
| `payment_attempts` | `patient_id:1, status:1, created_at:-1, _id:-1` | Candidate for status-filtered history; evaluate selectivity and write cost before adoption. |
| `users` | `role:1, is_active:1, full_name:1, _id:1` | Candidate for role/status filtered staff order. Omitted status and case-insensitive substring search may require a different plan. |
| `patients` | `user_id:1` | Candidate for user-to-patient joins/lookups if the deployed collection lacks it. |

The model source declares a unique `demo_entitlements.patient_id` index and a unique `users.email` index, but deployed index presence was not inspected. The current unanchored, case-insensitive name/email search may not benefit from ordinary B-tree indexes; a separately approved normalized search field or search facility should be evaluated with connected `explain` evidence. Bounded result materialization does not itself prove low database scan cost.

## 13. Remaining risks and environment limitations

- No connected Mongo query plan, deployed index inventory, latency, memory, concurrency, or representative-volume measurement exists.
- Offset pages are bounded but can become more expensive at high offsets; the established page ceiling limits application materialization, not Mongo scan work.
- No real browser, multi-user connected authorization, payment provider, scanner, storage, proxy, deployment, or backup exercise ran.
- The list response contract has no server total count; `hasNext` is conservatively inferred by the UI from a full page.
- Entitlement expiry and consumption are not omitted implementations; they are absent business states in the current unique-current-grant model. Adding them requires a separately authorized policy/schema milestone.
- The current fixture-only secret-scan disposition remains open and the offline npm audit is only as fresh as local cache.

All eight connected release gates remain **BLOCKED**: connected multi-clinician authorization, connected registration transaction, distributed rate limiting, real scanner integration, private storage integration/access, connected payment/webhook/reconciliation, production-like proxy/TLS/cookie/cache behavior, and backup/restore operational recovery.

## 14. Remaining Phase 24A.11 findings

This milestone closes only A11-M01, A11-M02, and A11-M03 at the implementation/offline-regression level. The following audit work remains open and was not modified:

- A11-M04: bounded N+1 clinical list formatters;
- A11-M05: uncapped public payment-webhook body buffering;
- A11-M06: persistent payload/list/string ceilings;
- A11-M07: active admin patient-create screen/API mismatch;
- A11-M08: mutation revision/transaction/outbox boundaries;
- A11-L01 through A11-L03;
- A11-I01 through A11-I03;
- A11-E01 environment verification;
- A11-P01 password/verification/recovery/staff-onboarding policy.

Groups B, C, and D have not started. Phase 24B is **BLOCKED / NOT STARTED**. Client demonstration, staging, and production remain **NOT AUTHORIZED**.

## 15. Files changed for Group A

Backend implementation:

- `backend/app/api/home_visits.py`
- `backend/app/api/payments.py`
- `backend/app/api/users.py`
- `backend/app/repositories/payment_query_repository.py` (new)
- `backend/app/repositories/user_repository.py`
- `backend/app/services/home_visit_service.py`
- `backend/app/services/payment_service.py`
- `backend/app/services/user_service.py`

Backend tests:

- `backend/tests/test_patient_payment_history.py`
- `backend/tests/test_phase24a12_group_a_unbounded_retrieval.py` (new)

Frontend implementation and tests:

- `frontend/src/pages/patient/PatientPaymentHistory.jsx`
- `frontend/src/pages/admin/StaffManagement.jsx`
- `frontend/tests/staff-management.test.mjs`
- `frontend/tests/phase24a12-group-a-unbounded-retrieval.test.mjs` (new)

Documentation:

- `docs/PHASE_24A12_GROUP_A_UNBOUNDED_RETRIEVAL_REMEDIATION_REPORT.md` (new)

Final repository state:

| Item | Final value |
|---|---|
| Branch / HEAD | unchanged: `codex/physiocare-integration-2026-10-31` / `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream relationship | unchanged: 0 ahead / 0 behind |
| Tracked modifications | 94 |
| Untracked paths | 78 |
| Total dirty paths | 172 |

The count increase from the 162-path baseline is six newly modified tracked paths and four new untracked Group A paths. Five other Group A tracked edits overlap files that were already modified at baseline. All pre-existing tracked and untracked work remains present.

## 16. Completion decision and next milestone

**Group A: PASS.** The three affected registered paths are bounded; filters run in Mongo before pagination; ordering is stable; projections are consumer-specific; route roles and patient ownership remain enforced; payment query count is constant with page-row count; entitlement authorization remains targeted and complete for the actual current-grant model; affected frontend screens replace pages without unlimited accumulation; and relevant offline regressions pass.

This PASS is limited to Group A's offline source and test criteria. It does not close Phase 24A, clear connected gates, or establish production readiness.

The recommended next milestone is an independent review of this Group A remediation. Any implementation of Group B, C, or D requires its own authorization and scope. Stop after Group A.
