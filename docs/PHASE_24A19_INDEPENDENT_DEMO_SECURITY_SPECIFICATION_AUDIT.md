# Phase 24A.19 — Independent Demo Security Specification Audit and Implementation Readiness Review

Assessment date: 2026-11-02

Branch: `codex/physiocare-integration-2026-10-31`

Assessment HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

Phase 24A.18 has the correct core security direction: a dedicated local environment, backend default-deny enforcement, normal authentication and role dependencies retained, minimal new response schemas, and no reliance on frontend hiding. No current demo-mode bypass exists because the proposed mode and its 13 data endpoints are not implemented.

The specification is not yet unambiguous enough to implement safely. This audit records **0 Critical, 0 High, 7 Medium, 3 Low, and 2 Informational findings**. The Medium findings concern the single immutable source of runtime policy, deterministic ASGI/CORS enforcement order, Host-header protection, ODM startup/index behavior, frontend serving/HMR/WebSocket scope, the exact `/api/auth/me` demo projection mechanism, and notification feature gating. These are specification/design gaps, not confirmed exploitable vulnerabilities in a deployed demo mode.

The actual backend declares 119 HTTP operations: 71 GET, 28 POST, 17 PATCH, and 3 PUT. Phase 24A.18 proposes 19 allowlist entries. Six existing lifecycle/readiness entries were verified against source. Thirteen proposed role-data routes were confirmed absent and therefore remain design-only. The other 113 declared operations must be denied in demo mode. Four conditional FastAPI documentation operations, CORS preflight behavior, and the separate Vite frontend surface were also classified.

The recommended enforcement is two-stage: an outer immutable ASGI method/path gate for closed-world denial, followed by a demo route dependency that runs normal authentication first, then checks the immutable demo policy and existing role/owner/assignment constraints. A startup assertion should reconcile the immutable table against the registered route inventory. The route gate must not attempt to replace `get_current_user`, `RoleChecker`, or service/repository ownership checks.

**Technical decision: REQUIRES SPECIFICATION REVISION.** This is not implementation authorization. All 11 approvals remain pending, all eight connected gates remain blocked, and Phase 24B remains blocked/not started.

## 2. Documents reviewed

Primary:

- `docs/PHASE_24A18_DEMO_READ_ONLY_MODE_TECHNICAL_SPECIFICATION.md`

Supporting evidence:

- `docs/PHASE_24A17_FIVE_ROLE_READ_ONLY_DEMO_SURFACE_DESIGN_REPORT.md`
- `docs/PHASE_24A16_DEMO_APPROVAL_RESOLUTION_AND_ENVIRONMENT_COMPATIBILITY_PLAN.md`
- `docs/PHASE_24A15_CONTROLLED_LOCAL_DEMO_PREPARATION_AND_VERIFICATION_REPORT.md`
- `docs/PHASE_24A13_CONSOLIDATED_SECURITY_CLOSURE_AND_DEMO_READINESS_REPORT.md`
- Phase 24A.12 Groups A–D reports
- `docs/PHASE_24A14_LOW_SEVERITY_FINDINGS_REMEDIATION_REPORT.md`

Source authority included backend application construction, all registered API modules, configuration/startup/database code, authentication/session/rate-limit code, role dependencies, affected services/repositories/schemas, React route/navigation/auth code, the Axios client, TanStack Query defaults, mutation/PDF/payment/laboratory pages, Vite configuration, and package scripts.

Previous reports were treated as evidence only. Phase 24A.18 was not modified.

## 3. Repository state

State before this audit report:

| Item | Actual value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Tracked modified paths | 114 |
| Untracked paths | 95 |
| Total dirty paths | 209 |

The expected after-state is 0 staged, 114 tracked modified, 96 untracked, and 210 total dirty paths. The only intended new path is this report. No branch, commit, stash, reset, clean, checkout, or push operation occurred.

## 4. Actual application architecture reviewed

### 4.1 Backend construction and route surface

`backend/app/main.py` constructs one FastAPI application, adds CORS and three HTTP middleware functions, registers 13 API routers beneath `/api`, and declares `/` and `/health` (`backend/app/main.py:80-105,138-207,212-231`). No backend mounted sub-application, WebSocket route, or `StaticFiles` mount was found.

| Source router | Declared operations | Demo classification |
|---|---:|---|
| `auth.py` | 6 | Five lifecycle/current-user entries conditionally allowed; registration denied |
| `appointments.py` | 16 | All current operations denied |
| `users.py` | 16 | All current operations denied |
| `home_visits.py` | 15 | All denied |
| `lab_requests.py` | 12 | All current operations denied |
| `exercises.py` | 12 | All denied |
| `care_plans.py` | 10 | All denied |
| `payments.py` | 10 | All denied, including webhook |
| `laboratory.py` | 6 | All denied |
| `reports.py` | 4 | All denied, including upload/download |
| `clinician_schedules.py` | 4 | All denied |
| `notifications.py` | 4 | All current operations denied |
| `analytics.py` | 2 | All current operations denied |
| `main.py` root/health | 2 | Health conditionally allowed after projection change; root denied |
| **Total** | **119** | **6 current entries conditionally allowed; 113 denied** |

When documentation is enabled, FastAPI also creates OpenAPI, Swagger UI, Swagger OAuth redirect, and ReDoc operations. Phase 24A.18 requires documentation disabled and the global gate would deny them, but the future route-inventory test must name all four rather than test only `/docs`, `/redoc`, and `/openapi.json`.

CORS handles preflight `OPTIONS` as middleware behavior rather than a declared API route. This requires its own allowlist-order tests.

### 4.2 Authentication and authorization

- `get_current_user` validates access cookie/JWT, server-side session, expiry/revocation/user binding, CSRF for unsafe methods, user existence, and active state (`backend/app/middleware/auth.py:20-109`).
- `RoleChecker` performs role authorization after `get_current_user` (`backend/app/middleware/auth.py:111-120`).
- Login creates a session; refresh rotates it; logout revokes it (`backend/app/services/auth_service.py:157-227,246-258`).
- `GET /api/auth/csrf` validates the refresh token, sets a cookie, and calls the refresh rate limiter (`backend/app/api/auth.py:115-134`).
- Doctor directory/history authorization uses authenticated clinician identity and assignment checks; laboratorian work is assignment-scoped; patient reads derive ownership from the authenticated user.

### 4.3 Configuration and database startup

- `Settings` is instantiated as a mutable module-global object. Its `model_config` does not set `frozen=True` (`backend/app/core/config.py:104-110,721-737`).
- `create_fastapi_application(configured_settings)` uses the passed object for documentation policy, but lifespan, CORS, storage/scanner, payment worker, database initialization, auth middleware, and services reference the module-global `settings` (`backend/app/main.py:31-60,80-105`; imports throughout services).
- Startup invokes `init_beanie` with every document model, many of which declare indexes (`backend/app/database.py:29-68`; models including user, session, appointment, lab request, payment, and clinician schedule). The specification's promise that restart never indexes is not yet backed by an explicit initialization mode or test.
- The current application has no `TrustedHostMiddleware` or equivalent Host allowlist.

### 4.4 Frontend and integration surfaces

- All normal role routes remain registered in `frontend/src/App.jsx`; existing pages contain numerous mutation hooks, payment polling, upload inputs, PDF/blob viewers, and management navigation.
- The Axios client automatically performs CSRF recovery and refresh after eligible 401 responses (`frontend/src/services/api.js:25-99`).
- TanStack Query defaults to one retry and disables window-focus refetch (`frontend/src/App.jsx:65-72`). Auth login/logout clears the shared query cache.
- No service worker registration was found.
- Vite has `dev`, `build`, and `preview` scripts. The current Vite server configuration does not define the proposed five-role mode, fixed port, strict port, allowed hosts, HMR behavior, source-map policy, or dedicated proxy (`frontend/package.json`; `frontend/vite.config.js:5-22`). Vite is a separate static/HMR/WebSocket surface even though the FastAPI app has no WebSocket route.

## 5. Demo-mode boundary findings

### Verified strengths

- Default-off, bidirectional flag/selector validation and explicit staging/production rejection are correctly required.
- The design does not treat a Vite variable as authority.
- Existing authentication, role, owner, and assignment checks remain mandatory.
- All unlisted operations are denied, including unlisted GETs.
- Product-data mutations have no exception; only session lifecycle writes are documented.
- Payments, reconciliation, file/PDF routes, scanner/storage integrations, docs, registration, and real data are excluded.
- Path normalization, method-override rejection, strict query models, bounded pagination, and a uniform unlisted-route response are included.

### Required boundary corrections

1. Freeze one validated security-policy snapshot at application creation. Middleware, lifespan, auth tag checks, route dependencies, health, CORS, and database target validation must consume the same object. Do not read a mutable module-global flag per request.
2. Define the exact ASGI middleware stack and CORS preflight order. The outer route gate must see or deliberately delegate every preflight, and denial responses must receive appropriate private/no-store headers without invoking endpoints.
3. Add an exact Host-header allowlist and reject untrusted `Host`, `X-Forwarded-Host`, and forwarded-proto/host interpretation because trusted proxies are empty.
4. Define what database initialization is allowed. Either pre-create/verify indexes separately and initialize without reconciliation, or explicitly approve idempotent index creation in the dedicated database. Do not promise “never indexes” without a mechanism.
5. Version the allowlist as an immutable artifact and compare it to the registered route inventory at startup/test time. A future newly registered route must remain denied automatically.

No source evidence shows that a remote request can mutate the current settings object. The immutability issue is an implementation ambiguity with potentially serious consequences, not a confirmed current vulnerability.

## 6. API allowlist reconciliation

Phase 24A.18 contains **19 entries**: 6 existing routes and 13 proposed routes.

### 6.1 Existing entries verified against actual registration

| Entry | Registered path/method | Current dependencies and behavior | Audit result |
|---|---|---|---|
| Health | `GET /health` | Unauthenticated; reads settings; no response model; currently reports existing demo database name and payment enabled state | **Verified path/method. Requires the specified minimal demo branch before allowance.** |
| Login | `POST /api/auth/login` | Public; rate-limited; creates server session and cookies | **Verified. Authentication-state write exception is accurate. Future tag check required.** |
| CSRF recovery | `GET /api/auth/csrf` | Requires valid refresh cookie in handler; rate-limited; sets CSRF cookie | **Verified. Not data-read-only; security lifecycle effect is documented.** |
| Refresh | `POST /api/auth/refresh` | Refresh cookie + CSRF header; rate limiter; atomic session rotation | **Verified lifecycle exception. Future user/session tag recheck required.** |
| Logout | `POST /api/auth/logout` | Matching CSRF header/cookie; validates refresh session only when refresh cookie exists; revokes a decodable token if present | **Verified path/method, but Phase 24A.18 overstates mandatory session context; see A19-L01.** |
| Current user | `GET /api/auth/me` | `get_current_user`; reads user and patient/doctor profile; no declared response model; current shape includes email and broad role profile | **Verified. Must not be allowed until the demo-specific response mechanism is explicit and tested.** |

### 6.2 Proposed role-data entries

All 13 were confirmed **not registered**. Their current-source feasibility basis is accurate, but none can be “verified read-only” until implemented and audited.

| Proposed entry count | Role | Actual registration | Required security boundary |
|---:|---|---|---|
| 3 | patient | Absent | Current-user ownership; completed/file-free/all-read fixed predicates; dedicated schemas |
| 2 | doctor | Absent | Authenticated doctor ID at repository boundary; exact assignment; own completed visits only |
| 4 | receptionist | Absent | Reception role; minimal schedule/directory/clinician/availability projections; no patient contact/clinical data |
| 1 | laboratorian | Absent | Exact current-user assignment; clinic metadata only; no files/contact/payment |
| 3 | admin | Absent | Admin role; minimal staff/clinician/count projections; no credentials/patient/payment/management data |

### 6.3 Denied surface reconciliation

- The other **113 source-declared operations** are default-denied.
- The four conditional documentation operations are denied and must be absent when docs are disabled.
- There are no backend mounted apps, backend WebSockets, or backend static/download aliases beyond the declared report/lab file routes; those file routes are among the 113 denied operations.
- The Razorpay webhook, all payment routes, both `FileResponse` download routes, both upload paths, payment reconciliation endpoint, broad analytics, entitlements, registration, and all mutations are denied.
- CORS `OPTIONS` is a transport surface and must be exact-path/origin constrained.
- The Vite development/HMR/static surface is not covered by the backend allowlist and requires an explicit serving decision.

No current application route was found that Phase 24A.18 would accidentally allow through its closed-world policy. The remaining risk is an incorrect future implementation of the path/method matcher or middleware order.

## 7. Authorization enforcement assessment

### Recommended two-stage design

1. Build a frozen `ReadOnlyDemoPolicy` once from the validated settings used to construct the actual application. Store it in application state and close over it in middleware; do not derive activation from mutable environment/global values per request.
2. Install an outer pure-ASGI gate with a static method/path template table. It canonicalizes/rejects ambiguous raw paths and denies unlisted traffic before routing or request-body processing. CORS/preflight behavior must be explicitly ordered and tested.
3. Add a startup/test assertion that enumerates registered `APIRoute` operations and confirms only the six existing exceptions plus implemented demo route identifiers can pass the table. Framework docs/mounts/WebSockets/static surfaces are separately asserted absent or denied.
4. Attach a `require_read_only_demo` dependency to every proposed demo router. It must run after `get_current_user` and before service invocation, verify the frozen policy and exact tagged session/user, then allow `RoleChecker` and endpoint-specific owner/assignment logic to continue.
5. Enforce owner/assignment predicates in repository/service queries, not by filtering a broader result in React. Return identical missing/unassigned responses where the current security model already does so.

The pre-routing gate may safely deny an unlisted request before authentication; this reduces exposure and work. For a listed protected route, authentication must complete before demo-role/data authorization. This ordering does not bypass existing dependencies.

Uniform 404 for unlisted paths is reasonable. Allowed-but-unauthenticated remains 401; wrong role remains 403; missing/unassigned protected entities remain identical 404. Error bodies and cache headers require explicit tests.

## 8. Five-role security assessment

| Role | Authorization conclusion | Scope concern | Technical result |
|---|---|---|---|
| Patient | Proposed owner-derived endpoints avoid caller-supplied patient identity and are appropriately narrow | Notification content is conditional; `/auth/me` projection remains ambiguous | **Sound after M06/M07 correction** |
| Doctor | Proposed directory/history retain authenticated clinician and assignment predicates; no schedule is claimed | “Assigned” must continue to mean same doctor/patient query on every returned visit, not a one-time directory check followed by broad history | **Sound if repository predicate is invariant** |
| Receptionist | Minimal schedule/status and availability are operationally plausible; mutations and clinical fields are excluded | Full alias-only patient directory and availability are optional rather than essential; scope to displayed schedule participants if clinic policy does not require a full directory | **No authorization expansion, but minimize further if possible** |
| Laboratorian | Proposed single assigned-work projection is appropriate and excludes upload, PDF, contact/address/payment/provider data | Selected tests are clinical metadata and must remain limited to the assigned fictional request | **Sound with assignment predicate and schema tests** |
| Administrator | Proposed staff/clinician/count views avoid patient, credential, payment, and management fields | Staff `created_at` and internal IDs are not necessary unless the approved story uses them | **Sound; further minimization recommended** |

No role is currently demo-ready. These conclusions apply only to the proposed design.

## 9. Data exposure assessment

Phase 24A.18 correctly identifies every broad current schema that must not be reused directly: appointment variants, patient directory variants, report content, notification recipient/entity fields, laboratorian contact/file fields, staff email, clinician email/links, and broad analytics/payment data.

Dedicated response schemas are required for all 13 proposed endpoints and for the demo branch of `/api/auth/me` and `/health`. Explicit `response_model` declarations, repository-level projections, stable bounded ordering, strict query models, and recursive forbidden-key tests are mandatory.

Additional audit requirements:

- Define one concrete `DemoSessionOut` mechanism. Either create a dedicated demo session endpoint and update the frontend, or give `/api/auth/me` an explicit normal/demo union with a discriminator and exhaustive tests. A prose “demo-specific projection” on the currently untyped route is not enough.
- Omit internal IDs when they are not needed for navigation or stable identity. React can use a server-issued non-sensitive display key if the database ID has no user action.
- Fix maximum serialized item size for notification text, test names, clinician names, report titles, and all aggregate arrays in addition to page counts.
- Admin daily aggregation currently materializes a database aggregation result with `to_list(length=None)` (`backend/app/services/analytics_service.py:24-62`). A new demo projection should use a bounded aggregation/result assertion even though the two-day grouping is naturally small.
- Error responses must not disclose whether another patient's or clinician's record exists, raw validation internals, storage paths, database details, or provider state.

No password hash, token, session ID, payment provider reference, or private file path is intentionally included by the Phase 24A.18 projection design.

## 10. Frontend/backend boundary assessment

The specification correctly makes backend enforcement authoritative and proposes a separate GET-only API module, route-specific navigation, absent controls, cache clearing on account change, and no PDF/payment/upload helpers.

Current-source facts that future implementation must address:

- Normal routes and lazy chunks exist and can be reached by browser history or direct navigation. Backend default-deny prevents data/mutation access, but the demo router must never redirect a 403/404 into a normal workflow.
- The Axios interceptor can automatically call CSRF and refresh after a 401. Those exact lifecycle calls are allowlisted and must be covered by browser network tests.
- Query defaults retry once. Every demo query needs a demo-namespaced key, no placeholder/initial data from normal queries, bounded retry behavior, no polling, and cancellation/clear on role or session change.
- Existing payment polling, mutation hooks, PDF/blob helpers, file inputs, and management links must not be imported into demo route chunks.
- No service worker exists, which removes one stale/offline cache surface.
- The future serving model is unspecified. A Vite development server can expose HMR WebSockets and development assets; the guarded demo must choose and validate either a production build served by an approved minimal static server or an explicitly reviewed, loopback-only Vite mode with HMR/host restrictions.

Direct API calls remain subject to the backend gate even if the UI is bypassed. Frontend controls are presentation and testability features only.

## 11. Session and environment isolation assessment

Verified design strengths include dedicated database identity/listener, no production/staging credentials, exact loopback backend/frontend, exact CORS origin, distinct JWT secrets, short session lifetime, CSRF, session rotation/revocation, disabled docs/payments/reconciliation/scanner/file routes, tagged accounts, safe logs, and explicit stop/restart behavior.

Missing or ambiguous requirements:

- Add exact Host-header validation and forwarded-header rejection. Loopback binding alone does not define accepted HTTP authorities.
- Pin one immutable startup policy across app construction, lifespan, middleware, auth, database, and health.
- Specify MongoDB server binding/process identity and how the launcher proves it is the dedicated listener, not merely a URI string resolving to an unexpected process.
- Reconcile Beanie initialization with the no-index/no-migration promise.
- State that the local MongoDB account/process may write only the dedicated demo database. A read-only DB credential is impossible with current same-database sessions and rate-limit buckets, so least-privilege database scope is the compensating control.
- Configure demo-specific CORS allowed methods/headers. The current app advertises GET, POST, PUT, PATCH, DELETE, OPTIONS and upload/idempotency headers (`backend/app/main.py:100-105`); the demo should expose only GET, POST, OPTIONS and only content/CSRF headers required by lifecycle calls.
- Decide production-build versus dev-server frontend serving and classify HMR/WebSocket/static paths.

Session creation/rotation/revocation, auth rate-limit counters, and TTL cleanup remain intentional security-state writes. “Read-only” must continue to mean no product, clinical, operational, payment, file, or account mutation—not a physically read-only database connection.

## 12. Security test coverage gaps

Phase 24A.18's matrix is broad and strong. The following **14 additional adversarial scenarios** should be added; none was executed in this milestone.

| ID | Threat scenario | Required setup | Expected result | Security property |
|---|---|---|---|---|
| T01 | Validated settings object differs from global settings used by lifespan/auth | Construct app with one policy while monkeypatching global to conflicting DB/mode | Startup fails or every component uses the same frozen object | Single immutable policy |
| T02 | Runtime flag mutation disables gate after startup | Attempt to mutate settings/app state after policy construction | Frozen object rejects change; request behavior unchanged | Runtime immutability |
| T03 | CORS short-circuits the allowlist for unlisted preflight | Send OPTIONS for allowed/unlisted paths from allowed/disallowed origins under actual middleware order | Only exact allowed origin/path/method receives preflight; no endpoint call | Middleware/CORS ordering |
| T04 | DNS rebinding or hostile Host/forwarded headers reaches loopback | Send valid-path requests with wrong Host, absolute-form target, X-Forwarded-Host/Proto | Rejected before auth/data access | HTTP authority isolation |
| T05 | FastAPI framework route survives docs suppression | Enumerate `/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json` and app route table | All absent/denied | Framework-generated surface closure |
| T06 | New router operation is registered later but omitted from deny tests | Add a synthetic unlisted route to a test app and compare inventory | Startup/inventory assertion fails; route remains denied | Future route default-deny |
| T07 | ODM startup creates or changes indexes | Mock/spy collection index operations around `init_db`, and compare pre/post approved catalog in an isolated test double | No unapproved create/drop/change; explicit failure if reconciliation attempted | No hidden database maintenance |
| T08 | Untagged or wrong-tag session survives refresh/current-user | Create combinations of tagged/untagged user and session, then call login/refresh/me | Generic rejection and revocation where defined | Demo identity continuity |
| T09 | Logout token combinations bypass tag/CSRF assumptions | Test access-only, refresh-only, neither token, wrong-tag token, mismatched CSRF | Idempotent safe result or explicit reject per corrected contract; no unrelated session revocation | Accurate lifecycle boundary |
| T10 | Duplicate/ambiguous query parameters alter fixed predicates | Repeat `page`, dates, status, mode; include unknown/case-variant keys and encoded delimiters | 422; no service/repository invocation | Query pollution resistance |
| T11 | Error/cache behavior leaks entity existence or private data | Compare missing/unassigned/cross-owner responses and denied errors, including headers | Identical safe body/status where required; private/no-store; no IDs/paths | Error non-disclosure |
| T12 | Shared query cache or browser back/forward cache shows prior role data | Switch tagged roles, navigate back/forward, seed colliding normal/demo query keys | No prior-role rows render; demo keys isolated and cache cleared | Client confidentiality |
| T13 | Vite/static/HMR surface exceeds approved frontend boundary | Start only in a future approved test harness; enumerate HMR WebSocket, source maps, normal route chunks, host handling | Only approved serving model/host/assets; no unexpected HMR/source exposure | Frontend serving isolation |
| T14 | Notification gate becomes active without policy version/review | Enable endpoint code but leave v1 allowlist/version unchanged | Endpoint remains denied until versioned policy and approval change | Controlled scope evolution |

The existing Phase 24A.18 tests for route normalization, unsafe methods, direct API calls, ownership, assignment, file/payment/webhook denial, pagination, side effects, and production/staging failure remain required.

## 13. Findings register

| ID | Severity | Type/status | Evidence and specification section | Threat/failure scenario | Required correction | Code change? | Clinic approval? |
|---|---|---|---|---|---|---|---|
| A19-M01 | Medium | Confirmed architecture/specification ambiguity | Mutable global `settings`; app factory argument used only for docs while lifespan/CORS/services use global (`config.py:104-110,721-737`; `main.py:31-105`). Phase 24A.18 §§5–6. | Different objects or runtime mutation produce a validated gate with a different DB/worker/auth policy | Freeze and inject one `ReadOnlyDemoPolicy`; prohibit per-request environment/global reads | Yes | No, unless identities change |
| A19-M02 | Medium | Design concern | Current CORS plus three HTTP middleware; Phase 24A.18 does not prescribe exact insertion order (§5.3). | CORS preflight or exception path bypasses intended gate/header behavior | Specify/test outer ASGI gate, CORS order, error/cache handling, and endpoint non-invocation | Yes | No |
| A19-M03 | Medium | Confirmed missing control/requirement | No `TrustedHostMiddleware`; Phase 24A.18 §§6/11 specify bind/CORS but not Host validation | Host/DNS-rebinding or forwarded-authority ambiguity reaches loopback service | Exact Host allowlist; reject forwarded host/proto with no trusted proxy | Yes | Network policy approval confirms values |
| A19-M04 | Medium | Confirmed source/specification mismatch; runtime effect unverified | `init_db` calls `init_beanie` with indexed models (`database.py:29-68`); Phase 24A.18 §11 promises restart never indexes | Startup may reconcile indexes or violates an unproven operational promise | Define permitted initialization/index behavior and spy/preflight tests; revise promise | Likely | Data/DB approval if any index operation allowed |
| A19-M05 | Medium | Confirmed specification omission | Vite dev/preview scripts and proxy exist; no five-role host/port/HMR policy (`package.json`, `vite.config.js`). Phase 24A.18 §10/11. | HMR WebSocket, source/dev assets, or host behavior expands the local surface outside backend gate | Select production static serving or fully constrain/review Vite mode; inventory static/WebSocket surface | Yes/launcher | Environment/network approval |
| A19-M06 | Medium | Design ambiguity | Current `/api/auth/me` has no response model and returns broad patient/doctor profiles (`auth.py:156-169`); Phase 24A.18 §§7.1/9 proposes a conditional projection without exact contract | Implementer leaves broad response or frontend validates the wrong shape | Specify dedicated endpoint or discriminated explicit response model and exhaustive role tests | Yes | Data-field approval |
| A19-M07 | Medium | Design ambiguity | Patient notifications appear in proposed allowlist but are also “feature-gated until browser verification” (Phase 24A.18 §§7.2/8) | Endpoint becomes accessible before the condition/approval is defined | Exclude from v1 table or define a separate immutable policy version and approval transition | Yes | Workflow/content approval |
| A19-L01 | Low | Confirmed documentation inaccuracy | Logout validates refresh only if present and can clear cookies with matching CSRF pair and no token (`auth.py:137-154`). Phase 24A.18 §7.1 says valid session/refresh context | Tests/implementation assume stronger current prerequisite than exists | Document idempotent token combinations and desired corrected contract | Optional | No |
| A19-L02 | Low | Design hardening gap | Current CORS advertises PUT/PATCH/DELETE and upload headers (`main.py:100-105`); Phase 24A.18 does not explicitly narrow demo CORS | Browser preflight advertises capabilities that backend denies, increasing ambiguity | Demo-specific GET/POST/OPTIONS and minimum headers | Yes | No |
| A19-L03 | Low | Design hardening gap | Shared QueryClient retry/cache; Phase 24A.18 mentions clearing but not key namespace/BFCache (§10) | Stale prior-role content briefly renders despite backend denial | Namespace demo keys, no placeholder data, clear/cancel on role/session, BFCache test | Yes | No |
| A19-I01 | Informational | Verified strength | No backend mounts/WebSockets/static routes and no frontend service worker found | Fewer alternate surfaces today | Preserve with inventory tests | Test only | No |
| A19-I02 | Informational | Scope minimization | Reception directory/availability and admin created dates/IDs are not essential to every story | Fictional but unnecessary data/surface | Let clinic approve smaller v1; default to omission | Possibly | Yes |

There are no confirmed Critical or High vulnerabilities. The proposed mode is absent, so Medium items are pre-implementation boundary defects/ambiguities rather than exploitable deployed flaws.

## 14. Implementation readiness decision

**REQUIRES SPECIFICATION REVISION.**

Reasoning:

- The foundational default-deny and role/ownership design is sound.
- No Critical or High finding was identified.
- The Medium items govern the security boundary itself and should not be left to implementer interpretation. M01–M07 must be resolved in a revised specification before application code begins.
- Low findings can be corrected in the same revision or made explicit implementation acceptance criteria.

This technical decision does not authorize implementation and does not override pending approvals.

## 15. Required specification corrections

Before implementation review, revise Phase 24A.18 through a new, separately authorized document—not by silently editing it—to:

1. define one frozen policy/settings snapshot shared by app construction, middleware, lifespan, auth, database, CORS, health, and routes;
2. specify the exact outer-ASGI/CORS/error/cache middleware order and startup route-inventory assertion;
3. add exact Host and forwarded-header rules;
4. resolve Beanie/index initialization and replace the unsupported “never indexes” assertion with a testable contract;
5. choose and constrain the frontend serving model, including HMR/WebSocket/source-map/static handling;
6. define an explicit typed demo session/current-user response mechanism;
7. remove notifications from v1 or create a separately versioned, approved allowlist transition;
8. narrow demo CORS methods/headers;
9. require demo-namespaced query keys, cache cancellation/clearing, and BFCache tests;
10. add the 14 missing adversarial tests from section 12; and
11. reduce optional receptionist/admin identifiers and directory scope unless clinic policy approves them.

The revised specification should then receive another independent review before code changes.

## 16. Approval status

All 11 Phase 24A.16 approvals remain **PENDING; 0 APPROVED**:

1. named environment/machine;
2. environment owner/operator;
3. approved viewers;
4. approved workflow list;
5. fictional dataset;
6. demo accounts/role access;
7. network exposure boundary;
8. payment-disabled confirmation;
9. storage/scanner exclusions;
10. start/stop/abort authority; and
11. cleanup/retention decision.

No implementation, endpoint, frontend, account, fixture, launcher, startup, database, browser, connected test, or deployment authorization is granted.

## 17. Eight connected gate status

All gates remain **BLOCKED**. No connected verification occurred.

| Gate | Status |
|---|---|
| 1. Connected multi-clinician authorization | BLOCKED |
| 2. MongoDB query plans and realistic scale | BLOCKED |
| 3. Actual database index verification | BLOCKED |
| 4. Socket-capable ClamAV protocol/scanning | BLOCKED |
| 5. Private storage integration/access | BLOCKED |
| 6. Browser end-to-end journeys | BLOCKED |
| 7. Production proxy/TLS/cookie/cache | BLOCKED |
| 8. Backup and restore | BLOCKED |

Actual controlled local demo remains **NO-GO**. Connected client demo remains **NO-GO**. Phase 24B remains **BLOCKED / NOT STARTED**.

## 18. Recommended next milestone

The next milestone should be **Phase 24A.20 — Demo Security Specification Revision and Closure Review**, limited to documentation. It should incorporate the corrections in section 15, freeze the v1 route/policy version and frontend serving model, and receive independent re-review.

Do not begin demo-mode implementation, launcher development, account/fixture work, service startup, database activity, or browser verification until the revised specification is technically accepted and the separately required approvals are granted.

### Final status

| Item | Result |
|---|---|
| Routes reconciled | **119 application-declared operations + 4 conditional FastAPI documentation operations; CORS OPTIONS separately classified** |
| Allowlist entries | **19 reconstructed: 6 existing verified, 13 proposed confirmed absent/not implemented** |
| Findings | **0 Critical, 0 High, 7 Medium, 3 Low, 2 Informational** |
| Missing adversarial tests | **14** |
| Five-role authorization | **Technically sound only after specified corrections; no role currently demo-ready** |
| Implementation readiness | **REQUIRES SPECIFICATION REVISION** |
| Demo-mode implementation | **NOT STARTED** |
| Approvals | **11 PENDING; 0 APPROVED** |
| Actual controlled local demo | **NO-GO** |
| Connected client demo | **NO-GO** |
| Eight connected gates | **ALL BLOCKED** |
| Phase 24B | **BLOCKED / NOT STARTED** |

No production-readiness claim is made. Stop after Phase 24A.19 and await review.
