# Phase 24A.11 residual endpoint audit report

Assessment date: 2026-11-02  
Recommendation: **PASS WITH CONDITIONS for completion of the audit-only Phase 24A.11 milestone; Phase 24A remains conditional and Phase 24B remains BLOCKED**

## 1. Executive summary

The complete registered FastAPI surface was inventoried and source-traced offline. The application has **119 registered application route operations**: **117** under `/api` and two application root/health operations. FastAPI contributes four additional public framework documentation/OpenAPI routes. All **119/119** application operations were fully reviewed; **0** are partial and **0** are unverified at the source-trace level.

No Critical or High vulnerability was confirmed. In particular, the review did not find a supported cross-patient IDOR, cross-clinician access bypass, role escalation, unauthenticated PDF read, password-hash response, session-token response, or payment-state trust bypass. The prior session/CSRF, cache, PDF, ownership, pagination, directory aggregation, home-visit aggregation, slot-claim, dashboard aggregation, exercise aggregation, and demo-isolation protections remain present.

Residual work is material: **8 Medium**, **3 Low**, and **3 Informational** findings were confirmed. Four registered paths are genuinely unbounded; 14 registered operations have confirmed result-driven N+1 behavior (two of those are also unbounded). The public Razorpay webhook buffers an unrestricted body before signature rejection, multiple persistent mutation schemas lack practical complexity ceilings, an active admin screen calls a nonexistent patient-create API, and several clinical mutation paths lack a common revision/transaction boundary. These findings do not justify a claim of production readiness.

Phase 24A.11 itself is complete as an investigation/documentation milestone. It does not close Phase 24A. The eight connected release gates and four policy decisions remain open. Phase 24B may **not** be considered without separate explicit approval after prioritized remediation, independent review, policy decisions, and approved connected evidence.

## 2. Scope and methodology

The review was read-only with respect to application source and tests. It:

1. independently recorded Git state and preserved the dirty worktree;
2. read the required Phase 22, 23, and 24A.3–24A.10 evidence plus relevant Phase 20–24 documentation;
3. enumerated decorators and inspected the runtime/router registration structure in `backend/app/main.py`;
4. traced every handler into service, repository/model, response schema, authorization, query, bounds, and mutation paths;
5. searched for unrestricted `to_list`, `find_all`, cursor consumption, database calls in result loops, Python-side filtering, aggregations, projections, raw request buffering, file streams, and unversioned saves;
6. mapped `frontend/src` API calls, routed screens, pagination, stale-response handling, polling, and unsupported paths;
7. reran existing offline backend/frontend tests and syntax/diff checks without connecting to a database, provider, scanner, or external service.

The inventory uses the route operation as the unit: the same path with a different HTTP method is a different operation. Framework docs are recorded but excluded from the 119 application count.

## 3. Initial repository state

The independently observed pre-documentation state matched the Phase 24A.10 handoff:

| Item | Initial value |
|---|---|
| Repository | `/Users/boddisuryakathyakeya/PhysioCare/PhysioCare` |
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | 0 / 0 |
| Tracked modified paths | 88 |
| Untracked paths | 71 |
| Total dirty paths | 159 |

The latest Phase 24A.10 artifacts were present and preserved:

- `backend/app/repositories/home_visit_query_repository.py`;
- `backend/tests/test_phase24a10_home_visit_query.py`;
- `frontend/tests/phase24a10-home-visit-query.test.mjs`;
- `docs/PHASE_24A10_HOME_VISIT_QUERY_REMEDIATION_REPORT.md`.

No reset, clean, restore, stash, checkout, branch switch, commit, push, dependency change, environment-file edit, migration, seed, deployment, or external connection was performed.

## 4. Historical evidence reviewed

The review read and cross-checked the required evidence chain:

- Phase 22 comprehensive security audit;
- Phase 23 security remediation report;
- Phase 24A.3 remaining screens remediation;
- Phase 24A.4 combined closure verification;
- Phase 24A.5 backend test-environment recovery;
- Phase 24A.6 independent closure review;
- Phase 24A.7 residual defect remediation;
- Phase 24A.8 closure readiness and password-policy package;
- Phase 24A.9 independent final offline review;
- Phase 24A.10 home-visit query remediation.

Other Phase 20–24 readiness, query-hardening, production, staging, dependency, and PDF evidence was used where relevant. Historical statements were not treated as authoritative: route count, Git state, current code paths, query reachability, and tests were independently recalculated. Phase 24A.9's four broad residual query paths were refined: the home-visit no-preference query is closed by A.10; payment history, staff listing, and the omitted-search entitlement fallback remain; the present audit also found the legacy lab catalogue and bounded response-formatter N+1 paths.

## 5. Registered endpoint count and coverage

| Area | Operations |
|---|---:|
| Authentication | 6 |
| Appointments | 16 |
| Users/directories/history | 16 |
| Analytics | 2 |
| Demo services/home visits | 15 |
| Laboratory requests/PDF | 12 |
| Clinician schedules | 4 |
| Payments/webhook | 10 |
| Legacy laboratory booking | 6 |
| Clinical reports | 4 |
| Care plans | 10 |
| Exercises/progress | 12 |
| Notifications | 4 |
| Root/health | 2 |
| **Application total** | **119** |

Coverage is **119 FULL / 0 PARTIAL / 0 NOT VERIFIED** for offline source tracing. Four framework routes are separately reviewed. No duplicate registered method/full-path pair was found, all 13 imported API routers are registered, and no decorated API router was found omitted. Compatibility helpers and unregistered frontend calls are explicitly separated from the live surface in the inventory.

## 6. Authentication and authorization results

Verified controls:

- access JWT type, signature, expiry, user/session binding, session revocation/expiry, and active-user status are checked on every authenticated dependency;
- unsafe authenticated operations require a session-bound double-submit CSRF value;
- login, registration, refresh, and CSRF issuance use the current distributed-capable auth-rate-limit service; inactive and unknown login results remain generic;
- public registration remains enumeration-neutral and patient registration uses the transactional account/profile repository;
- refresh tokens are rotated with compare-state semantics and reuse revokes the session;
- admin, receptionist, laboratorian, doctor, and patient roles are checked server-side, not inferred from frontend routes;
- public doctor output uses a dedicated minimum schema; reception appointment output excludes clinical reason/symptoms and billing; doctor appointment output excludes billing; laboratorian lists are assignment-scoped.

No confirmed object-level authorization failure was found. Patient detail/list/download paths derive the patient from the authenticated user or compare ownership server-side. Doctor paths use assigned-patient/assigned-appointment predicates or owning care-plan checks. Laboratory downloads distinguish admin, assigned laboratorian, owning patient, and assigned doctor; drafts are hidden from patient/doctor with the same 404 used for absence. Notifications filter by the authenticated recipient. The legacy laboratory status mutation rechecks doctor-patient assignment in the service.

This source result does not close connected multi-worker, multi-clinician negative authorization testing. That gate remains blocked.

## 7. Unbounded retrieval findings

Four registered-path unbounded materializations are confirmed:

1. `GET /api/payments/history`: all patient payment attempts;
2. `GET /api/demo-services/entitlements` only when `search` is omitted: all patients;
3. `GET /api/users/staff`: all staff users;
4. `GET /api/laboratory/tests`: all active legacy catalogue records.

The first two also have result-driven N+1 lookups. The first three are Medium; the catalogue is Low because it is patient-authenticated and expected to be small, though that expectation is not enforced.

Unbounded optional service/repository compatibility branches exist elsewhere, but the registered handlers were shown to pass `PageWindow`; those dormant helpers are informational rather than live endpoint defects.

## 8. N+1 query findings

Fourteen registered operations have confirmed N+1 behavior:

- four appointment list operations (including the role-conditional admin/patient branch of `/appointments`);
- two patient-directory operations when search is absent;
- three home-visit request list operations;
- three lab-request list operations;
- payment history;
- omitted-search demo entitlements.

The first 12 are page-bounded (maximum 100) but can still cause hundreds of sequential lookups. Payment history and the entitlement fallback are both unbounded. Existing batched implementations in doctor/reception appointment pages, admin/doctor patient history, reception home visits, and doctor lab-report lists prove that page-level projection/batching is compatible with current response contracts.

Configured payment reconciliation also performs per-attempt appointment lookups, but the batch is explicitly bounded to 1..500 (default 50), is an intentional administrative batch, and is classified in the inventory rather than elevated to a residual defect.

## 9. Pagination, filtering, and frontend accumulation

The common clinical page contract is correctly enforced at default 50, max 100, max page 1,000. Reviewed paged repositories apply ownership/status/date/search filters before stable `sort/skip/limit`. Search inputs on active directories/reports/exercises are limited to 100 characters and regex-escaped. Date order is validated; analytics days are 7..365; booking dates use configured horizons.

Offset pagination can drift under concurrent writes and page 1,000 can still create a large skip; actual index use and latency require connected `explain` and representative data. These are environment limitations, not invented execution-plan findings.

The current frontend uses page replacement, record budgets/cancellation, and request keys rather than unbounded accumulation. No polling loop was found. The main full-list consumer is Staff Management. Demo Services always supplies `search`, but the API's missing-search fallback remains reachable directly.

## 10. Aggregation and projection results

Verified improvements remain intact:

- public/admin clinician directories use bounded aggregation/projection;
- home-visit no-preference availability streams one aggregation cursor rather than querying per clinician;
- appointment dashboard and admin daily activity use database grouping/counts;
- exercise adherence and care-plan stage summaries use aggregation, with recent activity limited;
- page identity joins use `$in` and narrow projections on several remediated paths;
- receptionist and public schemas intentionally omit clinical/payment/private fields.

Potential `$lookup` memory, scan volume, group cardinality, sort spill, and index selection cannot be established from source. No connected execution plan was obtained or claimed.

## 11. Sensitive-data exposure results

No password hash, JWT signing secret, refresh token, webhook secret, raw card/payment credential, or generic database-model serialization was found in reviewed responses. Auth session tokens remain HttpOnly cookies; the CSRF value is deliberately returned/readable by the client. Authenticated responses and PDF responses retain private/no-store controls.

Identity/contact/clinical/location data is generally tied to role and task:

- admin sees patient/staff records needed for administration;
- doctor sees assigned patient minimum profile and clinical data;
- receptionist sees scheduling/contact/location data but no reason/symptom/billing fields;
- assigned laboratorian sees collection contact/address and requested tests, not patient email, unrelated orders, diagnoses, or payments;
- patient sees their own records.

One Low minimization finding remains: legacy laboratory booking responses include provider payment/order identifiers even though the client-trusted payment update is disabled. Public OpenAPI/docs exposure is a separate Low information-disclosure hardening item. Demo database name appears in `/health` only in strictly isolated demo modes and is informational.

## 12. Request-limit and abuse-resistance results

Strengths include page/search/date bounds, auth throttling, escaped regex, schedule collection maxima, lab-request selected-test maximum 12, clinical/lab PDF byte caps, streamed upload checks, PDF structure validation, quarantine, scanner fail-closed behavior, and storage-path isolation.

Two Medium gaps remain:

- the public payment webhook buffers the entire body before header/signature rejection and has no application cap;
- no application-wide JSON cap exists, and multiple persistent schemas (auth strings, appointment reason, legacy lab `test_ids`, care-plan nested content, exercise content/notes) lack per-field/list ceilings.

Ingress may impose a body limit, but it was not verified and cannot replace durable persistent-data invariants. Exact clinical text/list limits require policy input.

## 13. Mutation and concurrency results

Verified protections include:

- appointment/home-visit schedule validation and a unique partial active slot claim with duplicate-key conflict handling;
- atomic conditional cancellation and home-visit doctor assignment;
- payment provider signature/capture verification, conditional attempt/appointment updates, webhook digest/event deduplication, and bounded reconciliation;
- lab-request idempotency key, conditional transitions/assignment/publication, expected storage-key replacement, and cleanup;
- schedule expected-revision publication;
- account/profile transaction with no unsafe standalone fallback;
- report transaction/cleanup design where an approved MongoDB transaction topology is available.

A Medium integrity finding remains. Care-plan and exercise assignment updates use unversioned read-modify-save. Care-plan history/notification and exercise progress/assignment state span multiple writes without one universal atomic boundary. General appointment PATCH also has an unversioned save path, although cancellation and slot claims are stronger. Concurrent legitimate operations can lose updates; a later failure can leave partial audit/notification/progress state. Connected replica-set failure-injection and two-writer tests are required.

## 14. Frontend-to-backend mapping

The endpoint inventory names current consumers per operation. Most active screens use registered, role-protected contracts. Shared endpoints include booking window/availability, public doctors, analytics, notifications, patient directories, and PDF downloads.

Confirmed drift:

- active admin `PatientsCreate` calls unregistered `POST /api/users/patients` and therefore cannot complete;
- two unrouted legacy lab components call unregistered `GET /api/users/me/address`;
- a number of registered detail/legacy/clinician endpoints have no visible SPA consumer but remain directly callable and were audited.

No client-side role gate was treated as authorization. No repeated polling was found. PDF viewer code still closes/rejects stale blob responses after authentication changes.

## 15. Previous remediation regression results

Current source and tests support the continued presence of:

- inactive-account rejection, generic login failures, enumeration-neutral registration;
- live session, CSRF, refresh rotation/reuse response, and private cache headers;
- clinical PDF private/no-store response, owner/assignment checks, viewer invalidation, quarantine/scanner/storage isolation;
- bounded clinical pagination and server-side ownership/role enforcement;
- admin clinician-directory bounded aggregation;
- HomeVisitRequests streaming no-preference aggregation;
- date-scoped conflict detection and unique active slot claims;
- dashboard and exercise aggregations;
- production/staging/demo configuration isolation guards.

No regression in those protections was confirmed. Connected behavior is not inferred from mocks.

## 16. Fresh verification

All backend tests were run from `/private/tmp` using the recovered locked Python 3.13 environment, `env -i`, synthetic test-only secrets, an unreachable loopback MongoDB port, `ENVIRONMENT=test`, payments/reconciliation/scanner disabled, plugin autoload disabled, explicit `pytest_asyncio`, and pytest cache disabled. No database or external service was contacted.

| Check | Fresh result |
|---|---:|
| Backend suite excluding only AF_UNIX integration file | **982 passed, 3 connected-only skipped**, 1 known plugin warning |
| Frontend complete suite with `TMPDIR=/private/tmp` | **155 passed** |
| Frontend first run under default macOS temp root | all 155 assertions passed, but suite marked failed by a post-test Vite temp source-map `EINVAL`; isolated rerun 7/7 and full rerun 155/155 passed |
| Python compilation | **164 files**, no errors |
| `git diff --check` | **PASS** |
| Static application route operations | **119** |

The three backend skips are the guarded connected account-registration, distributed-rate-limit, and report-transaction tests. The excluded `test_clamav_unix_scanner.py` has the previously documented sandbox AF_UNIX limitation; socket-free evidence is historical and was not substituted for a real daemon. The frontend transient was an environment write failure in the default temp directory, not an assertion failure; the unchanged suite passed with an approved writable temp root.

## 17. Finding summary and remediation roadmap

| Category | Count | IDs |
|---|---:|---|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 8 | A11-M01..M08 |
| Low | 3 | A11-L01..L03 |
| Informational | 3 | A11-I01..I03 |
| Environment verification required | 1 register entry | A11-E01 |
| Policy decision required | 1 register entry | A11-P01 |

Priority order:

1. obtain the password/verification/recovery/onboarding decisions;
2. bound and batch all four unbounded and 14 N+1 operations;
3. establish webhook/global/schema request limits with approved ingress policy;
4. resolve the active patient-create contract;
5. introduce revision/transaction/outbox semantics and failure-injection coverage;
6. minimize legacy provider identifiers and decide production docs exposure;
7. independently review remediation;
8. execute connected gates only after separate approval.

## 18. Environment verification limitations and release gates

The following remain unverified: deployed indexes and query plans; representative-volume latency/memory; concurrent offset behavior; replica-set transactions; distributed rate limits; real ClamAV socket/daemon/signatures/timeouts; private mounted storage permissions/backup/restore; production proxy/TLS/Host/origin/cookie/cache/body limits/security headers; real provider/webhook behavior; and connected multi-role/multi-clinician authorization.

All eight connected release gates remain **BLOCKED**:

1. connected multi-clinician authorization;
2. connected registration transaction;
3. distributed rate limiting;
4. real scanner integration;
5. private storage integration/access;
6. connected payment/webhook/reconciliation;
7. production-like proxy/TLS/cookie/cache behavior;
8. backup/restore and operational recovery.

No execution-plan, deployed-index, provider, scanner, storage, or production-readiness claim is made.

## 19. Policy dependencies

The clinic/security owners must decide:

1. patient password policy (the current public minimum remains six);
2. email verification;
3. account recovery;
4. staff and administrator-created patient onboarding.

Schema content ceilings also need clinical/product input, but a defensive transport body cap is a technical security requirement rather than a substitute for clinical policy.

## 20. Updated closure recommendation

**Phase 24A.11: PASS WITH CONDITIONS.** The required audit artifacts are complete, all 119 application operations are inventoried, and no application source or test behavior was changed. The condition is that this pass applies only to the investigation/documentation milestone; it is not a release pass.

**Phase 24A overall: CONDITIONAL / NOT CLOSED.** A11-M01 through M08, policy decisions, independent remediation review, and connected gates remain.

**Client demo, staging, and production: NOT AUTHORIZED.**

**Phase 24B: BLOCKED / NOT STARTED.** It may be considered only after a separate owner approval following remediation and evidence closure. This report grants no such approval.

## 21. Final repository state

Only these three Phase 24A.11 documentation paths were added:

- `docs/PHASE_24A11_API_ENDPOINT_INVENTORY.md`;
- `docs/PHASE_24A11_RESIDUAL_SECURITY_AND_QUERY_FINDINGS.md`;
- `docs/PHASE_24A11_RESIDUAL_ENDPOINT_AUDIT_REPORT.md`.

Application source and tests were not edited. Historical reports were not modified. The final Git check confirmed the preserved 88 tracked modifications plus 74 untracked paths (**162 total**), with the branch still 0 ahead / 0 behind its upstream and HEAD unchanged.
