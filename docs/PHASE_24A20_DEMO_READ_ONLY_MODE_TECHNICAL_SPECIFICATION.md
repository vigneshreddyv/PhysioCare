# Phase 24A.20 — Revised Demo Read-Only Mode Technical Specification

Specification date: 2026-11-02

Policy revision: `five-role-read-only-v1`

Repository baseline: `5eaced696a156ca74233fd04252fea52345d8af8`

> **Status:** complete technical specification for independent review. Every proposed application, test, environment, launcher, account, fixture, database, and frontend change is **NOT IMPLEMENTED** and **NOT AUTHORIZED** by this document.

## 1. Purpose, scope, and decision boundary

This specification defines a future isolated, local, five-role demonstration mode that permits authentication lifecycle activity and an explicitly bounded set of presentation reads while denying every unlisted backend operation. It incorporates Phase 24A.18 and resolves the Phase 24A.19 findings.

The mode demonstrates fictional data for `patient`, `doctor`, `receptionist`, `laboratorian`, and `admin`. It does not demonstrate registration, account administration, booking, cancellation, rescheduling, clinical authoring, care/exercise mutations, laboratory submission/upload, files/PDFs, payment/provider operations, entitlements, infrastructure administration, or database maintenance.

“Read-only” means no product, clinical, operational, account, payment, file, or fixture mutation. Authentication sessions, refresh rotation, logout revocation, authentication rate-limit counters, and TTL cleanup remain documented security-state writes. The current single-database architecture therefore cannot use a physically read-only database credential.

All normal authentication, active-account checks, role authorization, patient ownership, doctor assignment, and laboratorian assignment remain mandatory. Demo mode adds restrictions and never bypasses existing controls. Frontend state has no authorization effect.

## 2. Current source architecture and verified surface

The current FastAPI source declares 119 HTTP operations: 71 GET, 28 POST, 17 PATCH, and 3 PUT. Thirteen routers are mounted under `/api`; `/` and `/health` are root operations (`backend/app/main.py:192-231`). When enabled, FastAPI also supplies OpenAPI, Swagger UI, Swagger OAuth redirect, and ReDoc. No backend mounted sub-application, backend WebSocket, or backend static-file mount exists.

Authentication is cookie/session based. `get_current_user` validates access JWT, server session, revocation, expiry, session/user binding, active account, and CSRF on unsafe methods; `RoleChecker` then validates role (`backend/app/middleware/auth.py:20-120`). Existing service/repository code supplies owner and assignment predicates.

The React application registers all ordinary product routes and contains mutation, polling, file/PDF, payment, and management components. Axios automatically refreshes eligible 401 requests, TanStack Query retries reads once by default, and auth transitions clear the shared query cache. No service worker exists. Vite is a separate development/static/HMR surface; it is not part of the FastAPI API allowlist.

## 3. Immutable runtime security policy — NOT IMPLEMENTED

### 3.1 Single effective policy

Application construction must first create and fully validate one `Settings` instance, then derive one frozen `ReadOnlyDemoPolicy`. The policy is immutable for the entire process lifetime. Application factory, middleware, lifespan, CORS, Host validation, authentication tag checks, demo dependencies, database target selection, health output, and route-inventory assertions must consume that same object by closure or read-only application state.

No demo authorization decision may read `os.environ`, reload an environment file, reconstruct `Settings`, or consult a mutable module-global flag after policy creation. Runtime environment changes cannot expand or reduce access. A policy change requires a complete process restart and full revalidation.

The current split—where `create_fastapi_application(configured_settings)` receives one object while lifespan/services reference global `settings`—must be removed for the demo path. A startup test must prove object identity or equivalent immutable-value identity across every consumer.

### 3.2 Conceptual policy object

The frozen object contains only validated, non-secret values:

| Field | Required value/purpose |
|---|---|
| `policy_version` | Exact `five-role-read-only-v1` |
| `environment_identity` | Exact approved local instance identifier |
| `enabled` | `True` only after complete validation; default policy is disabled |
| `startup_validated` | `True` only after every static guard succeeds; cannot be mutated |
| `allowed_routes` | Immutable tuples of method, canonical path template, route ID, authentication class, and role set |
| `excluded_capabilities` | Immutable set covering registration, account/product mutations, files, PDF, payments, webhooks, entitlements, maintenance, docs, and external integrations |
| `approved_backend_authority` | Exact `127.0.0.1:<backend-port>` |
| `approved_frontend_origin` | Exact `http://127.0.0.1:<frontend-port>` |
| `database_identity` | Dedicated database name and loopback listener identity; no credential value |
| `rehearsal_tag` | Exact `five_role_read_only_demo_v1` |
| `database_initialization_mode` | Exact reviewed mode proving runtime performs no index/schema/fixture maintenance |

Secrets remain in protected settings and are never copied into diagnostics or the policy representation.

### 3.3 Fail-closed construction

Missing, invalid, conflicting, or partially initialized configuration raises before the ASGI application can serve any route. There is no permissive fallback policy. If route-inventory, middleware, database-target, integration-disablement, or policy construction validation fails, startup terminates before database initialization and health exposure.

Production always rejects the flag, selector, instance identity, reserved demo database, and rehearsal tag. Staging also rejects v1 unconditionally; any future staging demo requires a separate documented policy version and approval. Frontend variables cannot enable or modify backend policy.

## 4. Environment and startup guards — NOT IMPLEMENTED

The following proposed names do not exist in current source:

| Proposed setting | Required v1 behavior |
|---|---|
| `READ_ONLY_DEMO_MODE` | Default `False`; explicit `True` required |
| `READ_ONLY_DEMO_INSTANCE_ID` | Exact `physiocare-five-role-read-only-demo` |
| `READ_ONLY_DEMO_DATABASE_NAME` | Exact dedicated name, proposed `physiocare_read_only_demo` |
| `READ_ONLY_DEMO_MONGODB_URL` | One exact loopback listener on its dedicated port; no SRV, credentials from another environment, multiple hosts, URI options, or remote resolution |
| `PHYSIOCARE_READ_ONLY_DEMO_ENV_FILE` | Sole selected environment file; exact resolved path under the dedicated demo home |
| `HOST` / `PORT` | Exact `127.0.0.1` and approved dedicated backend port |
| `CORS_ORIGINS` | Exactly one frontend origin |
| `API_DOCUMENTATION_ENABLED` | Exactly `False` |
| Other demo/local flags | `LAB_DEMO_MODE=False`, `HOME_VISIT_DEMO_MODE=False`, `PHYSIOCARE_LOCAL_DEV=False` |
| Payment settings | Mode disabled; key ID/secret/webhook secret/currency empty; reconciliation false |
| Scanner/storage | Scanner disabled/socket empty; dedicated unused local report paths; all file routes denied |
| Proxy/rate limit | Trusted proxies empty; auth throttling enabled |
| JWT secrets | Fresh, distinct, demo-only, minimum-length, never logged |

Flag without selector, selector without flag, multiple selectors, multiple demo flags, wrong environment/instance/database/host/port/origin, enabled docs/integrations, or unknown application variable fails startup. `validate_runtime_startup()` repeats the complete guard immediately before external connection.

`ENVIRONMENT='development'` may be retained only if ordinary-development validation explicitly excludes this validated mode. Staging and production validators must explicitly reject every new demo selector/identity. The new database name is added to production/staging reserved identities.

The launcher must later prove port/process ownership and that the loopback MongoDB listener is the approved dedicated process. A URI string alone is not sufficient runtime evidence.

## 5. Exact request-processing and CORS order — NOT IMPLEMENTED

The future application must construct an explicit middleware stack rather than rely on incidental decorator insertion order. Outermost-to-innermost request order is:

1. **Trusted authority gate:** reject unapproved Host and forwarded authority before any route, CORS, auth, or health work.
2. **Immutable demo method/path gate:** canonicalize the raw request target and apply the frozen table. It directly returns uniform 404 for unlisted traffic with `Cache-Control: private, no-store`, `Pragma: no-cache`, and `Expires: 0`.
3. **Demo-specific CORS middleware:** exact origin, methods, and headers only. It never authorizes data access.
4. **Existing unsafe-origin and bounded-body controls:** preserve current protections for the allowed lifecycle POSTs.
5. **FastAPI routing and dependencies:** session authentication/CSRF → frozen demo-policy dependency → `RoleChecker` → owner/assignment service/repository predicate → endpoint serialization.
6. **Response privacy handling:** authenticated and lifecycle responses retain private/no-store headers; CORS adds only approved exposure headers.

The implementation must verify the actual Starlette stack order by an integration test, including exception paths. Expected parsing failures are handled inside the outer gate; no exception may fall through to a permissive route.

### OPTIONS behavior

`OPTIONS` is not an API allowlist entry. The outer gate accepts a preflight only when all are true:

- path canonicalizes to an effective v1 route;
- `Origin` is the exact frontend origin;
- `Access-Control-Request-Method` is the exact method allowed for that path; and
- requested headers are a subset of `Content-Type` and `X-CSRF-Token`.

Allowed preflight delegates to narrowly configured CORS and never invokes authentication, a route handler, service, repository, or database. Every other OPTIONS request returns a non-disclosing denial without CORS exposure. A successful preflight does not imply the subsequent request will pass authentication, role, ownership, or policy checks.

Demo CORS advertises only `GET`, `POST`, and `OPTIONS`; PUT, PATCH, DELETE, idempotency, report filename, and upload headers are absent. `HEAD` is denied unless a later policy revision explicitly adds it.

## 6. Host, proxy, origin, and public-access protection — NOT IMPLEMENTED

V1 binds only IPv4 loopback. Approved browser origin is exactly `http://127.0.0.1:<frontend-port>` and approved backend authority is exactly `127.0.0.1:<backend-port>`. `localhost`, IPv6, LAN addresses, wildcards, suffix patterns, and public names are not aliases in v1.

Use `TrustedHostMiddleware` or an equivalent outer ASGI control plus exact authority/port validation. Reject malformed/duplicate Host, absolute-form authorities that disagree, and any `X-Forwarded-Host`, `X-Forwarded-Proto`, `Forwarded`, or similar authority input. Uvicorn proxy-header trust is disabled and `TRUSTED_PROXY_NETWORKS` is empty. A future reverse proxy requires a new approved policy.

The production-style local static server may proxy browser `/api` and `/health` requests to the backend, but it must set the exact backend Host and preserve the exact approved browser Origin. Cookies remain host-only, SameSite=Lax, with existing scoped paths. Secure cookies cannot operate over v1 loopback HTTP; public/LAN exposure is therefore prohibited.

CORS is defense in depth for browser response exposure, not authorization. Host validation, loopback binding, route denial, authentication, role, and ownership are all independently required.

## 7. Database, Beanie, and index initialization — NOT IMPLEMENTED

Current `init_db()` calls `init_beanie` with all document models, many of which declare indexes. Source inspection alone does not establish that runtime initialization is index-neutral. Therefore v1 makes no claim that current startup is read-only or index-free.

### 7.1 Required preparation/runtime split

- A separately authorized preparation step creates the dedicated database, approved collections/indexes, fictional accounts, and records. It is not part of presentation startup.
- A read-only preflight records the exact loopback listener/process identity, selected database, approved index catalog, tagged record counts/relationships, and absence of unexpected records. It performs no repair.
- Presentation runtime must use a reviewed initialization path proven by spies and an isolated test not to create, drop, alter, or reconcile indexes/collections, seed data, migrate, or clean records.
- If the installed Beanie version cannot initialize documents without index/collection maintenance, implementation stops. The team must design and independently review a separate safe runtime initialization approach; it may not silently permit index work.
- Runtime startup compares the validated database identity and approved catalog before serving health. Any mismatch fails closed. It never auto-fixes the mismatch.

### 7.2 Database privilege boundary

A physically read-only user is incompatible with the current same-database session, refresh, rate-limit, and TTL security-state writes. The runtime database principal/process must be limited to the dedicated demo database and only the operations required for product reads plus authentication security state. It receives no cross-database, administrative, index-management, backup, or production/staging privilege. Where the local MongoDB mode cannot express that least privilege, process/listener isolation and the application deny layer are documented compensating controls requiring approval.

Index creation is prohibited during presentation startup/runtime. Any index creation is a separately approved preparation action with exact target validation and post-action inventory. No migration, repair, or cleanup is automatic. Restart revalidates everything and performs no preparation work.

## 8. Closed-world API allowlist — NOT IMPLEMENTED

Phase 24A.18 contained 19 candidates: 6 existing and 13 proposed. V1 excludes notification display, so the **effective immutable v1 table contains 18 entries: 6 existing and 12 proposed**. The excluded 19th candidate remains documented below and is denied. All other 113 current application operations (including root), four conditional documentation operations, and future unlisted operations are denied.

Dynamic templates are compiled from immutable route IDs and exact segment grammars; no authorization uses prefix matching. Reject encoded slash/backslash/dot, duplicate/trailing slash ambiguity, invalid UTF-8, NUL, case variants, unexpected parameters, method-override headers/fields, and duplicate/unknown query keys. The startup inventory assertion proves each effective template maps to exactly one intended registered operation after implementation.

### 8.1 Existing lifecycle/readiness entries

| # | Method/path | Role/auth | Current dependency and ownership | Typed projection / side effects | V1 decision |
|---:|---|---|---|---|---|
| 1 | `GET /health` | Unauthenticated, loopback/Host gate | None today | New `DemoHealthOut`: `status='ok'`, `environment='read_only_demo'`, `policy_version`, `payments_enabled=false`, `documentation_enabled=false`; no DB/host/path detail; no DB write | **INCLUDE after implementation** |
| 2 | `POST /api/auth/login` | Untagged request; only approved tagged five-role user succeeds | Auth rate limiter; future tag/role check | Session/rate-limit write; cookies + existing login projection | **INCLUDE lifecycle exception** |
| 3 | `GET /api/auth/csrf` | Valid tagged refresh cookie | Refresh/session validation + rate limiter | Cookie/rate-limit security effect; no product write | **INCLUDE lifecycle exception** |
| 4 | `POST /api/auth/refresh` | Valid tagged refresh + CSRF | Refresh/session validation | Atomic session rotation/rate-limit write | **INCLUDE lifecycle exception** |
| 5 | `POST /api/auth/logout` | See §13 exact token/CSRF contract | Session validation when token exists | Revocation/clear-cookie security effect; idempotent no-token case | **INCLUDE lifecycle exception** |
| 6 | `GET /api/auth/me` | Any approved tagged role; authenticated | `get_current_user`, active account, future tag/policy check | Exact discriminated response in §9; DB reads only | **INCLUDE after typed implementation** |

### 8.2 Proposed role-data entries

Every path below is proposed and absent from current registration.

| # | Method/path | Role and boundary | Response/data projection | Side effects/files | V1 decision |
|---:|---|---|---|---|---|
| 7 | `GET /api/demo-read-only/patient/completed-visits` | patient; patient derived from session | Bounded completed clinic visits: visit ID, date/time/timezone, clinician alias, clinic mode, completed status | Pure read; no clinical/billing/payment/address/cancel fields | **INCLUDE** |
| 8 | `GET /api/demo-read-only/patient/report-metadata` | patient; owner derived from session; file path absent | Bounded report ID/title/category/date/therapist alias/`has_file=false` | Pure read; no content, description, booking/patient ID, file/PDF | **INCLUDE** |
| 9 | `GET /api/demo-read-only/patient/notifications` | patient recipient | Candidate all-read minimal notification projection | Listing can be read-only; current page has PATCH controls and content policy is unapproved | **EXCLUDE FROM V1; DENY** |
| 10 | `GET /api/demo-read-only/doctor/patients` | doctor; authenticated doctor scopes repository | Bounded assigned patient ID + fictional alias | Pure assigned read; no phone/DOB/gender | **INCLUDE** |
| 11 | `GET /api/demo-read-only/doctor/patients/{patient_id}/completed-visits` | doctor; exact doctor/patient assignment and same-doctor visit predicate | Patient ID/alias + bounded own completed visit ID/date/time/mode/status | Pure read; no clinical/report/file/care/exercise fields | **INCLUDE** |
| 12 | `GET /api/demo-read-only/reception/schedule` | receptionist; bounded approved date range | Appointment ID, fictional patient/clinician aliases, date/time/timezone, assignment-pending, status | Pure read; no contact/address/reason/billing/cancellation fields | **INCLUDE, clinic scope approval required** |
| 13 | `GET /api/demo-read-only/reception/patients` | receptionist | Bounded fictional patient ID + alias; optionally restrict to approved schedule participants | Pure read; no contact/profile/clinical data | **INCLUDE, default to schedule-participant scope** |
| 14 | `GET /api/demo-read-only/reception/clinicians` | receptionist; active only | Clinician ID, alias, specialization; home-visit flag only if approved | Pure read; no email/bio/image/links | **INCLUDE** |
| 15 | `GET /api/demo-read-only/reception/availability` | receptionist; validated clinician/date | Timezone/date and bounded published slot/time/state | Pure read; no booking | **INCLUDE, clinic scope approval required** |
| 16 | `GET /api/demo-read-only/laboratory/assigned` | laboratorian; exact current-user assignment | Request ID, patient alias, clinic-visit mode, bounded test names, request/report status, created time | Pure read; no contact/address/file/provider/payment | **INCLUDE** |
| 17 | `GET /api/demo-read-only/admin/staff` | admin | Fictional display name, role, active state only | Pure read; no ID/email/created date/credential | **INCLUDE** |
| 18 | `GET /api/demo-read-only/admin/clinicians` | admin | Clinician alias, specialization, active-today only | Pure read; no ID/email/link/profile management | **INCLUDE** |
| 19 | `GET /api/demo-read-only/admin/overview` | admin | Explicit counts: today/yesterday and morning/afternoon/evening only | Pure bounded aggregation; no revenue/patient/subscription/payment/security data | **INCLUDE** |

List defaults are at most 25 and maximum page size at most 50, with existing hard caps retained. Every list has deterministic sort and stable tie-breaker. Date range and text/item lengths are bounded. Repository queries project only schema fields and use no unbounded `to_list(length=None)`.

Registration, normal product GETs, all product unsafe methods, files/PDFs, reports detail/download/upload, laboratory writes/file routes, care/exercise, home visits, schedules management, payments/webhook/reconciliation, broad analytics, entitlements, docs/OpenAPI, root, maintenance, migrations, indexing, fixtures, and cleanup are denied.

## 9. Exact typed `/api/auth/me` contract — NOT IMPLEMENTED

The endpoint remains the single authentication initialization mechanism and preserves `get_current_user`; no second authentication system is created.

Add an explicit discriminated `AuthMeResponse` response model. Each branch has a unique literal `view` value so broad normal output cannot validate as a demo branch:

- `NormalAuthMeOut(view='normal', demo_mode=False, id, email, full_name, role, profile)` preserves ordinary application behavior with typed existing patient/doctor/none profile variants.
- `DemoPatientAuthMeOut(view='demo_patient', demo_mode=True, id, fictional email, full_name, role='patient', policy_version, profile)` where profile contains only `patient_id` and optional supported `gender`.
- `DemoDoctorAuthMeOut(view='demo_doctor', ..., role='doctor')` where profile contains only `doctor_id`, specialization, and active-today state.
- `DemoReceptionAuthMeOut(view='demo_reception', ..., role='receptionist', profile=None)`.
- `DemoLaboratoryAuthMeOut(view='demo_laboratory', ..., role='laboratorian', profile=None)`.
- `DemoAdminAuthMeOut(view='demo_admin', ..., role='admin', profile=None)`.

Top-level `id`, fictional `email`, `full_name`, and `role` preserve current frontend authentication initialization and query-key needs. The frontend validator must accept only known views/roles and require `demo_mode=true` before entering `/demo`. It must not display email unless the approved profile story requires it.

Demo responses exclude password hash, session/token/CSRF identifiers, active/internal security metadata, phone, DOB, subscription, address, clinician email/bio/image/qualifications/links, payment/provider fields, audit fields, file/storage fields, and complete documents.

Expired/revoked/invalid sessions fail in `get_current_user` before projection. Inactive accounts preserve existing denial. Untagged/wrong-tag/unknown-role accounts fail closed with the generic demo authentication/authorization response and are never serialized. Every role branch has positive and forbidden-key serialization tests.

## 10. Role-specific presentation and authorization — NOT IMPLEMENTED

| Role | Frontend routes | Backend reads | Mandatory boundary |
|---|---|---|---|
| Patient | `/demo/patient`, `/history`, `/reports` | Typed auth/me, completed visits, file-free report metadata | Current-user patient ownership; completed clinic-only; no notifications in v1 |
| Doctor | `/demo/doctor`, `/patients/:patientId` | Assigned directory and same-doctor completed visits | Doctor ID derived from session at every query; identical missing/unassigned response; no schedule claim |
| Receptionist | `/demo/reception`, `/patients`, `/availability` | Schedule, schedule-scoped alias directory by default, clinician list, published availability | Reception role; no contact, clinical, address, billing, booking, cancellation, or edit data/control |
| Laboratorian | `/demo/laboratory` | Assigned clinic work metadata | Laboratorian ID derived from session; no upload/result/file/payment/provider data |
| Admin | `/demo/admin` | Staff alias/role/status, clinician alias/specialization/status, bounded operational counts | Admin role; no IDs unless technically required, credentials, patient records, billing, management action, or sensitive metrics |

Frontend controls are absent, not disabled. Each route has loading, empty, 401, 403, 404, and recoverable 5xx states. Forbidden/unavailable never redirects to normal product workflows.

## 11. Schemas, projections, and data minimization — NOT IMPLEMENTED

Every demo endpoint declares a dedicated Pydantic `response_model` and constructs that schema explicitly. No database document, general `model_dump()`, arbitrary dictionary, existing broad Appointment/Patient/Report/Lab/Staff/Doctor schema, nested document, or file response is returned.

Repository helpers must apply owner/assignment/status/file predicates and field projection in the database query, use bounded deterministic paging, and return no broader intermediate list for frontend filtering. Item strings and arrays have explicit serialized maxima. Unknown query fields and duplicate scalar query keys fail 422.

Forbidden keys are recursively asserted absent: password/hash; access/refresh/CSRF/session; email/phone except fictional auth email; address; DOB/subscription; reason/symptoms/body regions/pain; billing/payment/provider/webhook; revision/audit/security; file path/key/name/content/PDF; external links; other patients' data.

Internal IDs are returned only for permitted child navigation or stable record identity. Admin IDs/created dates are omitted. Reception patient directory defaults to patients appearing in the approved bounded schedule window unless clinic policy explicitly approves a wider fictional alias directory.

Admin overview uses an explicit bounded aggregation; it may reuse the daily calculation semantics but not `/api/analytics/stats` or an unbounded result materialization.

## 12. Frontend and static-serving architecture — NOT IMPLEMENTED

### 12.1 Development behavior

Development is not an approved client-demo serving mode. If used during a separately authorized implementation task, Vite must bind `127.0.0.1`, use fixed strict ports, restrict allowed Host/origin, pin the API proxy to the validated local backend, and bind HMR WebSocket to the same loopback host/explicit port. HMR, dev WebSocket, source serving, and debug errors are development-only and must be covered by source/static inventory tests. They are absent from presentation evidence.

### 12.2 Production-style local demo behavior

The controlled demo uses an offline production build with source maps disabled, no Vite development server, no HMR client, and no development WebSocket. An approved minimal static server binds `127.0.0.1:<frontend-port>`, serves only built hashed assets plus the SPA entry, disables directory listing/dotfiles/source maps, applies no-store to the entry and appropriate immutable caching only to hashed public assets, and reverse-proxies only `/api/*` and `/health` to the exact backend authority.

Static requests never enter the FastAPI allowlist because FastAPI mounts no frontend assets. The static server has its own exact Host, path, method (`GET`/`HEAD` assets only), and proxy rules. It must not proxy arbitrary paths, WebSockets, file-system paths, or dev endpoints. Browser API calls are same-origin through the narrow proxy; backend Host and policy checks remain authoritative.

### 12.3 React behavior

Use a separate `DemoLayout`, immutable role navigation, persistent fictional/read-only banner, role pages, and named GET-only `demoReadOnlyApi` functions. Demo chunks must not import normal mutation pages, `useMutation`, file inputs, PDF/blob helpers, payment code, management navigation, or polling.

Every demo query key starts with `['read-only-demo', policyVersion, userId, role, ...]`; no normal/demo keys overlap. Use no placeholder/initial data from ordinary queries, no polling, no prefetch to normal routes, bounded retry, request cancellation, and explicit cache clear on login/logout/role/session/policy change. Add browser back-forward cache handling so restored pages revalidate the tagged session before rendering private rows.

Axios refresh remains limited to exact auth lifecycle calls. A 401 clears private state; 403 renders role denial; 404 renders unavailable-in-demo; none redirects to a normal product page.

## 13. Session, logout, and security-state writes — NOT IMPLEMENTED

Pre-created accounts and sessions carry exact rehearsal tag and approved role. Login rejects inactive, untagged, wrong-tag, or unknown-role accounts generically. `get_current_user` and refresh recheck user/session tag and immutable policy. Dedicated secrets prevent cross-environment token acceptance.

Access lifetime remains at or below 15 minutes; refresh lifetime is at most the approved demonstration day. Refresh rotates atomically; reuse revokes. Cookies retain HttpOnly access/refresh, host-only scope, SameSite=Lax, current paths, and CSRF header/cookie/session-hash validation. Loopback HTTP cookies cannot be Secure; non-loopback exposure is prohibited.

Logout contract:

- missing/mismatched CSRF header/cookie returns 403;
- with refresh or access cookie, validate the server session, rehearsal tag, user/role, and CSRF session hash before revoking that session;
- invalid/wrong-tag token returns the generic session error and cannot revoke another session;
- with no auth token but a valid matching CSRF pair, return idempotent 204, clear cookies, and perform no database write; and
- successful token logout revokes once, clears cookies, and subsequent protected access returns 401.

Session, rate-limit, and TTL writes are the only permitted runtime database mutations. Product repositories used by demo endpoints receive read-only service interfaces; no background payment worker, file scanner, analytics writer, fixture, cleanup, or mutation task starts.

## 14. Notification decision and policy versioning

Current `GET /api/notifications` is recipient-scoped and read-only, but its response includes recipient/related entity fields; the current UI also exposes `PATCH` one/all read. Listing does not automatically mark read, yet notification text may contain sensitive or workflow-dependent content. “All-read” is data state, not a guarantee that the page cannot mutate.

**V1 decision: exclude notifications.** The route is absent from demo navigation, proposed notification endpoint remains unregistered or denied, current notification GET/PATCH routes are denied, and no unread-count/background request occurs.

A future notification display requires a new immutable policy version, explicit fictional-content schema, recipient-only minimal endpoint, absence of related entity ID and mutations, new tests, clinic content/workflow approval, independent review, and approved browser verification. General mark-read/read-all mutation will not be added merely for demonstration.

## 15. Required security test plan — NOT IMPLEMENTED / NOT EXECUTED

The original Phase 24A.18 matrix remains required: authentication/session/CSRF; role/owner/assignment; exact allow/unlisted denial; unsafe methods; path/query normalization; data forbidden keys; bounded paging; side-effect inventories; environment default-off/staging/production failure; frontend absence; and later approved browser traffic.

The following audit-derived tests are mandatory:

| ID | Threat/request path | Setup and expected result | Property | Step/role |
|---|---|---|---|---|
| T01 | Configured app object differs from global settings | Construct conflicting objects; startup fails or all consumers prove same frozen policy | Single policy | Policy; all |
| T02 | Runtime flag/environment mutation | Attempt change after construction; object rejects/change has no effect | Immutability | Policy; all |
| T03 | CORS short-circuit on unlisted OPTIONS | Matrix of path/origin/request method/header; only exact allowed preflight succeeds, no endpoint call | Stack order/CORS | Gate; all |
| T04 | Host/DNS/forwarded spoof | Wrong/malformed Host, absolute authority, forwarded headers; reject before auth | Authority isolation | Host; all |
| T05 | Framework docs survive | Enumerate OpenAPI, docs, OAuth redirect, ReDoc and route table; all absent/denied | Generated surface | App factory; all |
| T06 | New router omitted from table | Register synthetic route; inventory assertion fails and request denied | Future default-deny | Gate; all |
| T07 | ODM index/schema activity | Spy collection/index operations around runtime initialization; any unapproved DDL fails | No hidden maintenance | DB init; all |
| T08 | Tag discontinuity | Tagged/untagged user/session combinations through login/refresh/me; only exact pair succeeds | Identity continuity | Auth; all |
| T09 | Logout token combinations | Access-only, refresh-only, none, wrong tag, invalid token, CSRF variants; exact §13 behavior | Lifecycle accuracy | Auth; all |
| T10 | Duplicate/query pollution | Repeated/unknown/case/encoded page/date/status/mode; 422 before service | Fixed semantics | Endpoints; roles |
| T11 | Error/cache leakage | Compare missing/unassigned/cross-owner/denied bodies/headers; no identity/path leak, no-store | Non-disclosure | Endpoints; roles |
| T12 | Query/BFCache cross-role leak | Switch users/roles, back-forward, colliding normal keys; no stale private row renders | Client confidentiality | Frontend; roles |
| T13 | Static/HMR surface expansion | Inspect production build/static server and dev-only harness; no HMR/source maps/dev WS in demo | Serving isolation | Frontend/launcher |
| T14 | Notification code enabled under v1 | Register/enable candidate with v1 policy; startup inventory or gate still denies | Versioned scope | Gate; patient |
| T15 | Auth-me branch confusion | Serialize each known role and broad normal profile under demo; only exact demo branch validates; unknown role denied | Typed minimization | Auth; roles |
| T16 | Demo CORS capability drift | Inspect actual allow methods/headers and unsafe preflights; only GET/POST/OPTIONS + minimum headers | Browser least privilege | CORS; all |
| T17 | Cross-database/privilege drift | Mock parsed target/principal capabilities; wrong DB/host/admin/index privilege fails before init | DB isolation | Startup; all |
| T18 | Outbound/background integration | Spy worker/scanner/storage/provider/network creation during startup and idle demo reads; none occurs | Integration isolation | Lifespan; all |

Additional route-by-route tests cover all effective 18 entries, the excluded notification candidate, the remaining 113 current operations, four framework documentation operations, CORS OPTIONS, and absence of backend mounts/WebSockets/static routes. No new test is run by this specification milestone.

## 16. Implementation dependency and stop points

| Step | Work | Dependency and exit criterion | Approval boundary |
|---:|---|---|---|
| 1 | Independent review/freeze of this specification and v1 table | No unresolved Medium finding | Technical review only |
| 2 | Immutable config/policy/app-factory refactor | T01/T02/default-off/staging/production tests pass; no external connection | Explicit code authorization |
| 3 | Host/gate/CORS/route-inventory enforcement | T03–T06/T16 pass; every unlisted route denied | Security code authorization |
| 4 | Safe database initialization design | T07/T17 pass; no runtime DDL; wrong target fails | Database/security approval before connected work |
| 5 | Tagged auth and typed auth/me | T08/T09/T15 plus existing auth/session regression pass | Security/data-field approval |
| 6 | Dedicated schemas/repository projections/endpoints | Effective route tests, forbidden fields, role/owner/assignment, side-effect inventory pass | Workflow/data approval |
| 7 | Independent backend boundary review | No blocking finding; exact diff/test evidence | Review approval |
| 8 | Demo React routes/query isolation | Frontend render/import/network-contract/T12 pass | Frontend authorization |
| 9 | Production-style static serving specification/implementation | T13, Host, proxy, asset/source-map checks pass | Launcher/environment authorization |
| 10 | Full offline regression/security review | New + existing suites, lint/build/lock/audit/diff checks pass | Independent review |
| 11 | Guarded cross-platform launcher | Exact preflight/start/stop/abort/process ownership; no data preparation | Separate launcher authorization |
| 12 | Approved database/index/account/fixture preparation | Tagged inventory and read-only preflight; no real/payment/file data | Approvals 1,2,4–6,8,9,11 |
| 13 | Approved narrow browser smoke | Five roles, exact network table, session/role negatives, no HMR/files/payments | Approvals 1–10 and named viewers/operator |
| 14 | Actual controlled demonstration | Named GO, window, abort authority; otherwise NO-GO | All 11 approvals |

Implementation must stop after step 7 for independent review before frontend/launcher work. No step in this document is authorized now.

## 17. Isolation, logging, lifecycle, and approval requirements

The dedicated database contains only approved tagged fictional records and no payment, webhook, entitlement, PDF/file, real contact/address, or real clinical data. Pre-created credentials are random, temporary, outside repository/chat/logs, and held by the named custodian.

Logs exclude bodies, cookies, tokens, secrets, credentials, contact/clinical text, database URLs, file paths, provider data, and viewer-facing stack traces. Preserve only approved redacted lifecycle evidence.

Startup: validate immutable policy/Host/route inventory → verify integration disablement and target identity → perform proven no-DDL ODM initialization → expose minimal health. Shutdown: block new activity → logout if possible → stop only tracked frontend/backend/database processes → verify ports closed → preserve approved evidence. Never auto-clean; cleanup requires exact separate approval.

All 11 Phase 24A.16 approvals remain pending: environment/machine; operator; viewers; workflow; fictional dataset; accounts/access; network boundary; payment-disabled evidence; storage/scanner exclusion; start/stop/abort authority; cleanup/retention.

## 18. Connected gates and final readiness

All eight connected gates remain blocked:

| Gate | Required closure evidence | Demo relationship |
|---|---|---|
| 1. Connected multi-clinician authorization | Approved replica-set DB/identities; mismatched role/owner; transaction/race/rollback evidence | Narrow role smoke mandatory; mutations excluded |
| 2. MongoDB query plans and realistic scale | Representative data, explain, offsets, latency/concurrency/BSON/pool | May be excluded only with no performance claim |
| 3. Actual database index verification | Approved catalog, uniqueness/preflight, plan use | Preparation/runtime split still needs approved evidence |
| 4. Socket-capable ClamAV protocol/scanning | Approved daemon/config and clean/malicious/error/timeout | Irrelevant only while every file/PDF route is denied |
| 5. Private storage integration/access | Approved roots/permissions/promotion/cleanup/traversal/auth | Irrelevant only while every file route is denied |
| 6. Browser end-to-end journeys | Approved environment/browser/data; session/role/CSRF/account-switch/recovery | Narrow smoke mandatory but does not close full gate |
| 7. Production proxy/TLS/cookie/cache | Production-like ingress/TLS/Host/forwarding/CORS/cookie/cache/body/docs/webhook | Loopback demo does not close production gate |
| 8. Backup and restore | Approved artifact, isolated restore, validation, RPO/RTO, cleanup | Waiver requires approval 11 for disposable fictional demo |

**Technical specification readiness: APPROVED WITH CONDITIONS for a future, separately authorized implementation review.** Conditions are independent acceptance of this revision, no scope expansion, implementation in dependency order with the step-7 stop, and all relevant approvals before environment/data/runtime work.

Implementation authorization remains **NOT AUTHORIZED**. Demo implementation is **NOT STARTED**. Actual local demo and connected client demo remain **NO-GO**. Phase 24B remains **BLOCKED / NOT STARTED**.
