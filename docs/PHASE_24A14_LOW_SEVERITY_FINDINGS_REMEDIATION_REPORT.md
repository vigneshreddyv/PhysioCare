# Phase 24A.14 — Remaining Low-Severity Findings Remediation Report

Assessment date: 2026-11-02  
Branch: `codex/physiocare-integration-2026-10-31`  
Baseline HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

Phase 24A.14 addressed exactly the three Low-severity findings left open by the independent Phase 24A.13 assessment. The work remained offline and did not start Phase 24B.

- **A11-L01 — PASS.** The registered patient-only legacy laboratory catalogue was retained for compatibility, but database retrieval is now active-only, minimally projected, deterministically sorted, and capped at 100 records before materialization.
- **A11-L02 — PASS.** General legacy laboratory booking responses no longer serialize provider `payment_id` or `payment_order_id` values. The internal persistence model and the input-only compatibility schema still retain those fields for internal payment behavior.
- **A11-L03 — PASS WITH CONDITIONS.** FastAPI now has an explicit environment policy for Swagger, ReDoc, and OpenAPI. Production cannot enable them; demo and staging require an explicit opt-in; development and test retain their existing enabled default and can opt out. Actual application routes were tested. Reverse-proxy, TLS, and ingress behavior remains unverified connected gate 7.

Fresh evidence comprises 1,135 passing backend tests plus three deliberately skipped connected-only tests, 167 passing frontend tests, passing lint/build/bundle/compile/lock/dependency checks, and six unchanged synthetic secret-scan detections. No application regression was observed.

**Phase 24A.14 outcome: PASS WITH CONDITIONS.** The three application findings are remediated to the extent possible offline, but this does not close the remaining clinic-policy decisions or any connected release gate. It does not authorize a connected client demo or Phase 24B.

## 2. Initial Git state

The state below was independently recorded before Phase 24A.14 changes in the nested project repository at `/Users/boddisuryakathyakeya/PhysioCare/PhysioCare`:

| Item | Initial value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Unstaged tracked modifications | 112 |
| Untracked paths | 88 |
| Total dirty paths | 200 |

The outer wrapper repository was not used as the project repository. Existing tracked and untracked work in both repositories was preserved. No reset, clean, restore, checkout, stash, commit, or push was performed.

## 3. Exact findings addressed

| ID | Severity | Phase 24A.13 authoritative description | Initial disposition |
|---|---|---|---|
| A11-L01 | Low | The active legacy laboratory catalogue was unbounded; `get_active_tests()` materialized all active tests without a limit, stable order, or minimal projection. | OPEN |
| A11-L02 | Low | General legacy laboratory responses exposed provider payment/order identifiers unnecessarily. Access was already scoped, so this was unnecessary exposure rather than cross-user leakage. | OPEN |
| A11-L03 | Low | OpenAPI and interactive documentation were public by FastAPI default; deployed ingress behavior was unknown. | OPEN |

No Critical or High finding was introduced or claimed resolved by this milestone.

## 4. Root-cause analysis

### A11-L01

The compatibility repository used Beanie `.find(...).to_list()` without a server-side limit. It also relied on implicit collection order and materialized full documents. The route remained registered for patients, and its catalogue is part of the legacy booking contract even though the normal frontend route is dormant. Retiring it without consumer evidence would have been an avoidable compatibility break.

### A11-L02

Five route handlers independently constructed the same response model. That response schema contained internal provider identifiers, so every general constructor serialized them. The dormant booking-detail page also rendered both values. Persistence, payment input, and public output concerns were not separated cleanly.

### A11-L03

The application instantiated `FastAPI` without setting `docs_url`, `redoc_url`, or `openapi_url`, leaving all three at framework defaults in every environment. Existing environment guards did not establish a documentation-exposure policy.

## 5. A11-L01 implementation and endpoint decision

The endpoint was **retained and bounded**, not retired:

- `GET /api/laboratory/tests` remains registered and patient-only.
- `LaboratoryTestRepository.get_active_tests()` now queries the underlying collection with `{"active": true}`.
- Projection is limited to `test_id`, `name`, `category`, `sample`, and `price`; `_id` is excluded from returned documents.
- The stable order is `category`, `name`, `test_id`, then `_id`, all ascending.
- Both cursor `.limit(100)` and `.to_list(length=100)` enforce the hard ceiling before materialization.
- The existing response remains an object containing the plain `tests` list; no pagination-shaped compatibility break was introduced.
- `get_by_test_ids()` is outside the catalogue path and is bounded by the booking schema's maximum of 12 requested test identifiers.

The hard ceiling is intentionally an application constant, `LEGACY_LABORATORY_CATALOG_MAX = 100`, rather than a client-controlled value. It prevents the original resource-exhaustion shape while preserving the legacy contract.

## 6. A11-L02 response minimization

`payment_id` and `payment_order_id` were removed from `LaboratoryBookingResponse` and from the centralized general-booking serializer. The serializer is now used by create, list, detail, compatibility-payment-update, and status-update response paths, avoiding inconsistent field leakage through an alternate constructor.

The following were deliberately preserved:

- `LaboratoryBooking` persistence fields, so existing internal records and payment/reconciliation code are not migrated or rewritten;
- the input-only `LaboratoryBookingPaymentUpdate` fields used by the existing compatibility call shape;
- payment method, payment status, billing status, billing amount, booking status, tests, appointment information, and timestamps in the public response;
- all existing role, ownership, and assignment checks.

The dormant `LaboratoryBookingDetail.jsx` display no longer references or labels provider transaction/order IDs. No Razorpay behavior, record, request, webhook, or reconciliation path was changed or exercised.

## 7. A11-L03 environment-specific documentation policy

`API_DOCUMENTATION_ENABLED: bool | None` is now an explicit application setting. It is applied consistently to `/docs`, `/redoc`, and `/openapi.json` when the FastAPI application is created.

| Runtime | Default | Explicit `false` | Explicit `true` | Security rule |
|---|---:|---:|---:|---|
| Development | Enabled | Disabled | Enabled | Preserves developer behavior. |
| Test | Enabled | Disabled | Enabled | Preserves test tooling. |
| Dedicated lab demo | Disabled | Disabled | Enabled | Exposure requires a deliberate opt-in and approved boundary. |
| Dedicated home-visit demo | Disabled | Disabled | Enabled | Exposure requires a deliberate opt-in and approved boundary. |
| Staging | Disabled | Disabled | Enabled | Exposure requires a deliberate opt-in and approved boundary. |
| Production | Disabled | Disabled | **Disabled** | The setting cannot override the production prohibition. |

The three actual FastAPI routes return 404 when disabled. No claim is made that an explicit demo/staging opt-in is sufficient by itself: access control at the proxy or network boundary remains an operational approval and connected-verification requirement. No environment example or runtime `.env` file was modified in this milestone.

## 8. API compatibility analysis

- **Catalogue:** response shape and route remain unchanged. The observable change is deterministic ordering and truncation after the first 100 active catalogue entries. This is an intentional security ceiling. Inactive records and non-response fields are no longer materialized.
- **General legacy booking responses:** removal of `payment_id` and `payment_order_id` is a deliberate privacy-oriented response-contract change. No active routed frontend depends on those fields; the dormant detail component was updated as defense in depth. All other response fields are asserted unchanged.
- **Payment internals:** stored identifiers and the compatibility input schema remain available internally. Unrelated payment APIs were not changed.
- **Documentation endpoints:** development/test behavior remains enabled by default. Demo/staging change to deny-by-default and require explicit opt-in. Production is now unconditionally deny-only at the application layer.
- **Modern laboratory requests:** `/api/lab-requests` and active modern frontend laboratory pages were not changed by this milestone.

## 9. Authorization and ownership verification

The catalogue, booking list, booking detail, and compatibility payment-update routes remain patient-only. The status route remains admin/doctor-only. The catalogue does not contain patient data.

The booking-detail path continues to derive the patient profile from the authenticated user and supplies that patient identifier to the service lookup; the new response serializer is applied only after that owner-scoped lookup succeeds. Existing service-level doctor/assignment enforcement for status changes remains intact. Focused tests assert the registered route roles and owner-derived detail lookup.

No authorization scope was broadened. No alternate provider-ID response alias was added.

## 10. Tests added

`backend/tests/test_phase24a14_low_severity_findings.py` adds 41 parametrized cases covering:

- empty, small, exactly-100, and over-limit catalogue behavior;
- active-only database filtering, minimal projection, stable sort, hard cursor limit, and bounded materialization length;
- registered legacy catalogue and booking role scopes;
- exact general response serialization without either provider identifier;
- continued presence of the two identifiers on the internal booking model;
- owner derivation from the authenticated user for booking detail;
- actual `/docs`, `/redoc`, and `/openapi.json` status behavior across development, test, staging, both demo modes, and production, including explicit true/false settings.

`frontend/tests/phase24a14-low-severity-findings.test.mjs` adds two cases covering:

- absence of provider-ID references and labels from the dormant booking-detail page while payment status and billing remain;
- continued absence of the legacy booking screens from the active router and continued presence of the modern laboratory-request route.

## 11. Backend and frontend verification

All results below are fresh executions against the current dirty tree.

| Verification | Result |
|---|---|
| Phase 24A.14 focused backend | **41 passed** |
| Phase 24A.14 focused frontend | **2 passed** |
| Broader affected backend selection: laboratory, payment, API contract, docs/config, auth/rate/session, Phase 14 | **390 passed** |
| Combined Group A/B/C/D regressions | **100 passed** |
| Full backend excluding the Unix-socket scanner file | **1,123 passed, 3 connected-only skipped** |
| Fake local ClamAV Unix-socket protocol suite | **12 passed** |
| Reconciled complete backend result | **1,135 passed, 3 connected-only skipped** |
| Full frontend | **167 passed** |

The three skips are guarded connected-only MongoDB tests and were not bypassed or converted into passes. The main backend run emitted two non-failing warnings (the existing pytest-asyncio configuration warning and Starlette TestClient/httpx deprecation); the fake-scanner run emitted the pytest-asyncio warning.

The sandbox initially prevented AF_UNIX socket creation in the ordinary test context. The scanner protocol file was therefore kept separate and rerun with narrowly approved local Unix-socket permission against a fake local scanner; all 12 tests passed. No real ClamAV daemon or external socket was contacted. This was an environmental constraint, not an application-test failure.

## 12. Build, lint, bundle, and dependency checks

| Check | Fresh result |
|---|---|
| Frontend lint | PASS |
| Frontend production build, written under `/private/tmp` | PASS |
| Bundle budget | PASS — 73 JS/CSS assets; largest JS 373,260 bytes vs 460,800-byte budget; largest CSS 254,338 bytes vs 307,200-byte budget |
| In-memory Python syntax compilation | PASS — 171 Python files |
| Dependency-lock tests | **2 passed** |
| `pip check` in the recovered locked backend environment | PASS — no broken requirements |
| Frontend `npm audit --offline --audit-level=low` | PASS — 0 cached vulnerabilities |
| Redacted current-tree gitleaks scan | Six known synthetic detections only |
| `git diff --check` | PASS |

The six redacted secret-scan detections are the pre-existing synthetic `generic-api-key` fixtures: five in `backend/tests/test_api_contract.py` and one in `backend/tests/test_schedule_fallback_guard.py`. No secret value was printed in this assessment. Dependency files or versions were not changed.

## 13. Group A / Group B documentation discrepancy reconciliation

Historical reports were intentionally left unchanged.

1. Group A's declared scope was A11-M01 through A11-M03: bounded payment history, entitlement directory, and staff directory. Its report explicitly left A11-L01 through A11-L03 open.
2. The later Group B report incorrectly stated that Group A addressed L01.
3. Phase 24A.13 independently inspected source and tests and confirmed that `LaboratoryTestRepository.get_active_tests()` still performed an unbounded `.to_list()` and that Group A had no laboratory-catalogue regression case. It therefore authoritatively retained A11-L01 as OPEN.
4. Phase 24A.14—not Group A—implemented the active-only projection, deterministic order, 100-record hard limit, bounded materialization, and focused catalogue tests described above.
5. A11-L01 is now **PASS / closed offline by Phase 24A.14**. This correction does not retroactively expand Group A's scope or validate the inaccurate Group B sentence.

No previous report and no Phase 24A.11 inventory file was edited.

## 14. Remaining policy decisions

The following pre-existing decisions remain open and were not reinterpreted:

- clinic approval of semantic clinical text/content limits;
- administrator onboarding, invitation, activation, email-verification, duplicate-account, and audit policy;
- required demo workflow and named demo-data access authority;
- payment inclusion and provider-contract approval;
- whether documentation should ever be explicitly enabled in demo or staging, and the access boundary required if it is.

The safe current documentation default is disabled in demo/staging and prohibited in production.

## 15. Remaining connected-verification conditions

All eight connected release gates remain blocked pending explicit approval and controlled evidence. This includes, without limitation:

- Group B webhook provider/proxy agreement for the 256 KiB application ceiling;
- Group C real MongoDB indexes, plans, representative-scale latency, BSON size, pool, and concurrency behavior;
- Group D real replica-set transactions, rollback, retry, and two-client race behavior;
- real private storage and ClamAV integration;
- real-browser role/session/cache/download verification (gate 6);
- proxy, TLS, cookie, cache, and documentation exposure verification (gate 7);
- approved isolated infrastructure and all other existing staging/production prerequisites.

No offline result in this report substitutes for those gates.

## 16. Updated finding statuses

| Finding | Phase 24A.13 | Phase 24A.14 | Evidence boundary |
|---|---|---|---|
| A11-L01 | OPEN | **PASS** | Closed offline: bounded active query, projection, deterministic order, and focused regressions. |
| A11-L02 | OPEN | **PASS** | Closed offline: minimized general response plus internal-field and ownership regressions. |
| A11-L03 | OPEN | **PASS WITH CONDITIONS** | Application policy and routes verified offline; proxy/ingress behavior remains connected gate 7. |

These status changes do not mean that all Phase 24A policy and connected conditions are closed.

## 17. Final Git state

At report completion, the state was independently rechecked:

| Item | Final value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Unstaged tracked modifications | 114 |
| Untracked paths | 91 |
| Total dirty paths | 205 |

HEAD remains the baseline commit because this milestone did not commit. Compared with the initial state, two previously clean tracked paths became modified and three new untracked files were added. Other implementation edits overlap paths that were already tracked and modified when work began.

No pre-existing tracked or untracked path was discarded. Temporary build and scan outputs were kept under `/private/tmp`, not added to the repository.

## 18. Files modified and created by Phase 24A.14

Implementation files modified in the existing dirty tree:

- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/repositories/laboratory_test_repository.py`
- `backend/app/services/laboratory_service.py`
- `backend/app/schemas/laboratory_booking.py`
- `backend/app/api/laboratory.py`
- `frontend/src/pages/patient/LaboratoryBookingDetail.jsx`

Files created:

- `backend/tests/test_phase24a14_low_severity_findings.py`
- `frontend/tests/phase24a14-low-severity-findings.test.mjs`
- `docs/PHASE_24A14_LOW_SEVERITY_FINDINGS_REMEDIATION_REPORT.md`

Several listed implementation files contained earlier uncommitted milestone work. Only the targeted L01-L03 changes described in this report are attributed to Phase 24A.14.

## 19. External-service access confirmation

No MongoDB instance, protected database, Razorpay endpoint, real webhook, real ClamAV daemon, protected external storage, deployment platform, or other external service was accessed. No migration, index operation, seed, payment, refund, record mutation, infrastructure change, or deployment was performed. No real patient data was used.

The tests used mocks, in-process FastAPI clients, and a fake local Unix-domain scanner protocol server only.

## 20. Recommended next milestone

Stop after Phase 24A.14 and obtain independent review of this report and the current dirty-tree diff. If accepted, the next work should be an explicitly authorized closure-planning milestone for the outstanding clinic policy decisions and connected gates—not Phase 24B implementation.

- **Phase 24B:** BLOCKED / NOT STARTED.
- **Controlled local/demo status:** CONDITIONAL GO remains unchanged, limited to the Phase 24A.13 approved isolation, fictional data, pre-created accounts, disabled payments, and workflow exclusions. Resolution of these Low findings does not itself authorize a demo.
- **Connected client-demo status:** NO-GO until the approved connected gates and policy decisions are complete.
- **Production readiness:** not claimed.
