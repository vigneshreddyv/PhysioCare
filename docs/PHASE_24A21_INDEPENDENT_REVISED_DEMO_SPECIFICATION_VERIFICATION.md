# Phase 24A.21 — Independent Revised Demo Specification Verification

Assessment date: 2026-11-02

Reviewed baseline: `5eaced696a156ca74233fd04252fea52345d8af8`

Review type: source-inspection and documentation only

## 1. Executive summary

The Phase 24A.20 revision is internally consistent with the inspected architecture and concretely addresses all 12 Phase 24A.19 findings. This review found no new Critical, High, Medium, or Low specification defect. Each proposed control remains **NOT IMPLEMENTED**; source evidence confirms the current application does not yet provide the new demo policy, Host gate, narrow CORS stack, no-DDL initialization path, production-style demo frontend, typed demo `/api/auth/me`, or 12 proposed role-data endpoints.

The 19-candidate history is accurate: six routes exist with the reported methods and paths; 13 proposed routes are absent/not implemented. Notification candidate 9 is excluded, leaving an effective v1 table of exactly 18 entries: six existing lifecycle/readiness candidates and 12 proposed role-data candidates. No proposed endpoint was misclassified as existing.

The original 14 Phase 24A.19 adversarial tests and four Phase 24A.20 additions are reproducible and dependency-mapped. Together with the expressly retained Phase 24A.18 route/role/projection/side-effect matrix, they cover the requested security categories. No test was executed in this milestone.

**Technical readiness decision: APPROVED WITH CONDITIONS.** This is approval of the specification for a future, separately authorized implementation review, not permission to implement. Demo implementation remains **NOT STARTED**; all 11 approvals remain **PENDING**; actual local and connected demonstrations remain **NO-GO**; all eight connected gates remain **BLOCKED**; Phase 24B remains **BLOCKED / NOT STARTED**.

## 2. Documents reviewed

Primary documents, read as proposed design and closure claims:

- `docs/PHASE_24A20_DEMO_READ_ONLY_MODE_TECHNICAL_SPECIFICATION.md`
- `docs/PHASE_24A20_DEMO_SECURITY_SPECIFICATION_REVISION_AND_AUDIT_CLOSURE.md`

Historical authorities, read independently:

- `docs/PHASE_24A19_INDEPENDENT_DEMO_SECURITY_SPECIFICATION_AUDIT.md`
- `docs/PHASE_24A18_DEMO_READ_ONLY_MODE_TECHNICAL_SPECIFICATION.md`
- `docs/PHASE_24A17_FIVE_ROLE_READ_ONLY_DEMO_SURFACE_DESIGN_REPORT.md`
- `docs/PHASE_24A16_DEMO_APPROVAL_RESOLUTION_AND_ENVIRONMENT_COMPATIBILITY_PLAN.md`
- `docs/PHASE_24A15_CONTROLLED_LOCAL_DEMO_PREPARATION_AND_VERIFICATION_REPORT.md`

Source authority inspected included `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/database.py`, authentication middleware/routes/services/schemas/session model, all API decorator inventories, role services/repositories/schemas, notifications, reports/files/payments, `frontend/package.json`, `frontend/vite.config.js`, frontend routing, authentication context/validation, query configuration, API interceptors, notification behavior, and alternate-surface inventories.

## 3. Repository state

Initial Phase 24A.21 state:

| Item | Verified value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Tracked modifications | 114 |
| Untracked paths | 98 |
| Total dirty paths | 212 |

The two Phase 24A.20 documents and all historical reports were untracked pre-existing paths at review start. SHA-256 values were captured before this report so preservation can be checked at completion. This milestone adds only this report; no commit, push, stash, reset, clean, checkout, restore, or branch change is authorized or performed.

## 4. Review methodology

1. Recover the 12 findings directly from Phase 24A.19, not from the Phase 24A.20 closure summary.
2. Compare each finding to the complete revised specification and require an actionable design, implementation dependency, and test.
3. Reconstruct current behavior directly from source. Static route-decorator inventory independently produced 119 application operations: 71 GET, 28 POST, 17 PATCH, and 3 PUT.
4. Search current backend/frontend source for every proposed demo name and path; no demo read-only implementation exists.
5. Compare each of the 19 candidates with actual router prefixes, methods, dependencies, projections, side effects, and frontend behavior.
6. Treat source absence as evidence only of current state, not a permanent guarantee.
7. Classify current facts as **VERIFIED IN SOURCE**, proposed corrections as **CORRECTLY SPECIFIED**, incomplete statements as **PARTIALLY SPECIFIED**, inconsistencies as **CONTRADICTORY**, unsupported claims as **NOT VERIFIED**, and absent controls as **NOT IMPLEMENTED**.
8. Perform no import/startup/runtime/database/browser test. This avoids environment side effects and respects the documentation-only boundary.

## 5. Twelve-finding verification register

| ID | Severity | Independent source evidence | Revised correction and test | Verification status | Final finding status |
|---|---|---|---|---|---|
| A19-M01 | Medium | `Settings` is mutable and module-global; app factory uses its argument only for documentation while lifespan, CORS, auth, security, and DB use imported global settings (`backend/app/core/config.py:104-176,721-737`; `backend/app/main.py:31-105`) | One frozen injected policy, one Settings identity, no request-time environment/global reads; T01–T02 | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification; implementation and independent proof required |
| A19-M02 | Medium | Current source registers CORS and three function middleware without an explicit demo ASGI gate (`backend/app/main.py:94-196`) | Exact authority → route gate → CORS → current controls → auth/policy/role/ownership → privacy order; T03/T11/T16 | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification |
| A19-M03 | Medium | No TrustedHost-equivalent middleware is present; current `HOST` config alone is not request authority validation | Exact IPv4-loopback authorities; reject Host/absolute/forwarded ambiguity; no trusted proxy; T04 | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification; network values still require approval |
| A19-M04 | Medium | `init_db()` validates global settings, creates a Motor client, and calls `init_beanie` with models declaring indexes (`backend/app/database.py:29-68` and indexed models) | Approved preparation/runtime split; proven no-DDL runtime path; explicit stop if Beanie cannot provide it; T07/T17 | **CORRECTLY SPECIFIED / NOT IMPLEMENTED / TECHNICAL FEASIBILITY NOT VERIFIED** | Closed as design because uncertainty is an explicit stop condition |
| A19-M05 | Medium | Vite has dev/build/preview, a dev proxy, and only home-visit strict-port handling; FastAPI mounts no frontend/static/WS surface (`frontend/package.json`; `frontend/vite.config.js`; `backend/app/main.py`) | Development-only HMR/WS boundary and separate production-style loopback static server with narrow proxy; T13 | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification; serving artifact/launcher approval remains |
| A19-M06 | Medium | `/api/auth/me` has no response model and returns broad patient/doctor service profiles; frontend validator checks only basic identity plus profile presence (`backend/app/api/auth.py:156-169`; `frontend/src/context/loginSession.js:1-8`) | Discriminated normal/demo union, five exact demo role branches, forbidden fields, current auth retained; T15 and role serialization tests | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification; final model field types require implementation review |
| A19-M07 | Medium | Current notification GET is recipient-scoped/read-only, while unread count and PATCH mutations are used by the UI (`backend/app/api/notifications.py`; `frontend/src/pages/common/Notifications.jsx`) | Candidate 9 excluded from v1; no navigation/background/PATCH; future version and approval required; T14 | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification |
| A19-L01 | Low | Logout requires a matching CSRF pair, validates refresh only when present, then revokes first decodable token and clears cookies (`backend/app/api/auth.py:137-154`; `backend/app/services/auth_service.py:241-257`) | Exact access/refresh/no-token/wrong-tag/CSRF contract; T09 | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification |
| A19-L02 | Low | Current CORS allows GET/POST/PUT/PATCH/DELETE/OPTIONS and upload/idempotency headers (`backend/app/main.py:94-105`) | Demo CORS limited to GET/POST/OPTIONS, Content-Type and X-CSRF-Token; T03/T16 | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification |
| A19-L03 | Low | QueryClient retries once and disables focus refetch; auth transitions clear shared cache, but no demo namespace/BFCache contract exists (`frontend/src/App.jsx:65-72`; `frontend/src/context/AuthContext.jsx`) | Demo-only key namespace, no placeholder data, cancellation/clear, BFCache revalidation; T12 | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification |
| A19-I01 | Informational | No FastAPI mount/static/WebSocket decorator and no frontend service worker registration was found | Preserve absence through docs/route/static/HMR/service-worker inventory; T05/T13 | **VERIFIED IN SOURCE / PRESERVATION NOT IMPLEMENTED** | Not applicable as a current defect; future guard remains required |
| A19-I02 | Informational | Current admin/reception schemas are broader than the proposed story; IDs/created dates and directory breadth are optional design scope | Omit admin IDs/created dates; schedule-participant default for reception; clinic approval for broader scope | **CORRECTLY SPECIFIED / NOT IMPLEMENTED** | Closed in specification; workflow/data approval remains |

Result: **7/7 Medium and 3/3 Low findings are concretely resolved in specification; the two Informational findings are accurately dispositioned.** No written correction is credited as an existing control.

## 6. Runtime policy assessment

The revised policy unambiguously requires startup-time construction from one validated Settings object, immutable process-lifetime values, default-disabled mode, no environment reload/per-request global use, restart revalidation, frontend non-authority, and failure before serving on missing/conflicting configuration. Production rejects the flag/selector/identity/database/tag. V1 staging rejects it unconditionally; a later staging design needs a different reviewed policy version.

This is consistent with the current architecture as a refactoring requirement: current `load_runtime_settings()` produces a module global and existing consumers import it, so the design correctly says that split must be removed for the demo path rather than pretending it is already safe. The conceptual policy fields are sufficient to bind environment identity, route/role/method table, excluded capabilities, exact authorities, database identity, version, tag, and initialization mode. Status: **CORRECTLY SPECIFIED / NOT IMPLEMENTED**.

## 7. Middleware, CORS, and Host-header assessment

The specified outer-to-inner order preserves existing security semantics while adding a stronger closed-world boundary. Authentication/session validation remains in `get_current_user`; CSRF remains mandatory for unsafe authenticated methods; role checks remain in `RoleChecker`; endpoint/service/repository predicates retain owner/assignment enforcement. The demo dependency adds a restriction between authentication and existing authorization. Exception and privacy behavior is test-bound rather than assumed.

Preflight handling is exact-path, exact-origin, exact requested-method, and minimum-header constrained; allowed OPTIONS performs no endpoint/service/repository/database call. The document explicitly states that CORS is not authorization. Unlisted preflights receive no exposure headers.

Host policy accepts only the approved IPv4 loopback origin/authority and rejects localhost aliases, IPv6, LAN/public/wildcard names, malformed/duplicate Host, conflicting absolute-form authority, and forwarded authority with proxy trust disabled. This goes beyond current source, which has no TrustedHost control. Cookie/CORS/proxy relationships are consistent with the proposed same-origin static proxy. Status: **CORRECTLY SPECIFIED / NOT IMPLEMENTED**.

## 8. Beanie and index initialization assessment

Source establishes connection and model initialization in the same `init_db()` path. The document models include explicit `Indexed` fields and `IndexModel` lists. Static inspection cannot prove whether the installed Beanie version will create/reconcile indexes for a given catalog, so Phase 24A.20 correctly retracts the earlier unconditional index-neutral claim.

The revised split is coherent:

- only a separately authorized preparation operation may create the dedicated DB, indexes, tagged users, and records;
- a read-only preflight inventories target/listener/catalog/tagged relationships and never repairs;
- runtime must use an independently proven no-DDL initialization path;
- wrong target/catalog fails before health; and
- inability to prove no-DDL initialization stops implementation for redesign.

It also correctly explains that a physically read-only principal is incompatible with current session, refresh, rate-limit, and TTL security-state operations. Least privilege is therefore scoped to the dedicated database and required reads/security writes, with no index/admin/cross-database authority. Separate preparation is necessary. No database behavior was runtime-verified and no database was contacted. Status: **CORRECTLY SPECIFIED / NOT IMPLEMENTED / FEASIBILITY CONDITION OPEN**.

## 9. Frontend static, HMR, and WebSocket assessment

Current source is a separate Vite application. It defines `dev`, `build`, and `preview`; the dev server proxies `/api`, and only the existing home-visit mode turns on `strictPort`. No controlled five-role Host, fixed-port, HMR authority, source-map, or static-server policy exists. FastAPI currently serves API/root/health only: no mounted frontend, static route, backend WebSocket, or service worker was found.

The revision correctly separates two future modes:

- development may use loopback-only fixed Vite/HMR/proxy behavior but is not client-demo evidence; and
- controlled presentation uses an offline production build with no Vite dev server/HMR/dev WebSocket/source maps and a separate loopback static server that serves only built assets and proxies only `/api/*` and `/health`.

Static and API policies remain independent; static paths cannot become an alternate FastAPI API route. The proposed same-origin API path is compatible with current Axios default `'/api'`. Build, server, proxy, Host, source-map, and chunk-inventory behavior remains to be implemented and tested. Status: **CORRECTLY SPECIFIED / NOT IMPLEMENTED**.

## 10. `/api/auth/me` projection assessment

Current `get_current_user` validates access-token type/signature/expiry, server session existence/revocation/expiry/user binding, unsafe-method CSRF, current user existence, and active state. The current `/api/auth/me` uses that dependency, then loads broad patient or doctor profiles and returns an untyped dictionary. The frontend validates ID, email, full name, known role, and profile presence for patient/doctor.

The revised design preserves this authentication path and adds no second mechanism. It requires a discriminated `AuthMeResponse` with a typed normal branch and five literal demo branches. Demo patient/doctor profiles are enumerated; receptionist/laboratorian/admin profiles are `None`; sensitive contact, subscription, security, payment, audit, and file fields are excluded. Invalid/revoked/expired/inactive/untagged/wrong-tag/unknown-role identities fail before serialization. The frontend must validate the exact view/role/demo-policy combination.

This is sufficiently explicit for implementation, with final Pydantic scalar/optional types and normal-mode compatibility subject to code review. T15 plus positive/forbidden-key tests prevent broad-union fallback. Status: **CORRECTLY SPECIFIED / NOT IMPLEMENTED**.

## 11. Eighteen-entry effective allowlist verification

Static decorator inventory independently verifies all six existing method/path pairs. A source search finds none of the 13 `/api/demo-read-only/*` candidates. The table below reconstructs all 19 historical candidates; candidate 9 is denied, so 18 remain in effective v1.

| # | Method and path | Source status | Auth/role/ownership and projection check | Side effects/files/background | Effective v1 |
|---:|---|---|---|---|---|
| 1 | `GET /health` | **VERIFIED IN SOURCE** | Currently unauthenticated and broader; future exact Host/gate plus minimal `DemoHealthOut` required | Current read; future no DB/file/background | Include after implementation |
| 2 | `POST /api/auth/login` | **VERIFIED IN SOURCE** | Rate-limited; future exact tagged active five-role account restriction | Session/cookie/rate-limit security writes; no product/file action | Include lifecycle exception |
| 3 | `GET /api/auth/csrf` | **VERIFIED IN SOURCE** | Refresh/session validation and throttling; future tag continuity | CSRF cookie/token and throttle security effect; no product/file action | Include lifecycle exception |
| 4 | `POST /api/auth/refresh` | **VERIFIED IN SOURCE** | Refresh session and CSRF validation; future tag/policy recheck | Atomic refresh/session rotation and throttle writes | Include lifecycle exception |
| 5 | `POST /api/auth/logout` | **VERIFIED IN SOURCE** | Current matching-CSRF and conditional token validation; revised exact token/tag/session contract required | Validated revocation/cookie clear; no-token case no DB write | Include lifecycle exception |
| 6 | `GET /api/auth/me` | **VERIFIED IN SOURCE** | `get_current_user`; current broad untyped profile; future tagged role-discriminated schema | Reads user/profile; no file/background | Include only after typed implementation |
| 7 | `GET /api/demo-read-only/patient/completed-visits` | **PROPOSED; NOT IMPLEMENTED** | Patient derived from session; owner-only completed clinic rows; dedicated bounded schema | Pure read; no clinical/payment/address/file fields | Include |
| 8 | `GET /api/demo-read-only/patient/report-metadata` | **PROPOSED; NOT IMPLEMENTED** | Patient derived from session; owner and no-file predicate; minimal metadata schema | Pure read; no content/path/PDF/download | Include |
| 9 | `GET /api/demo-read-only/patient/notifications` | **PROPOSED; NOT IMPLEMENTED** | Recipient-only candidate; content/related-ID policy not approved | Current UI has unread/background and PATCH state changes | **Exclude and deny** |
| 10 | `GET /api/demo-read-only/doctor/patients` | **PROPOSED; NOT IMPLEMENTED** | Doctor ID from session; repository-assigned patients; ID + fictional alias only | Pure read; no contact/profile/file | Include |
| 11 | `GET /api/demo-read-only/doctor/patients/{patient_id}/completed-visits` | **PROPOSED; NOT IMPLEMENTED** | Exact assignment and same-doctor completed-visit predicates; uniform missing/unassigned response | Pure read; no clinical/report/care/file | Include |
| 12 | `GET /api/demo-read-only/reception/schedule` | **PROPOSED; NOT IMPLEMENTED** | Reception role; bounded date window; minimal aliases/time/status schema | Pure read; no contact/address/reason/billing/cancel | Include after scope approval |
| 13 | `GET /api/demo-read-only/reception/patients` | **PROPOSED; NOT IMPLEMENTED** | Reception role; schedule-participant scope by default; alias-only schema | Pure read; no contact/profile/clinical/file | Include minimized default |
| 14 | `GET /api/demo-read-only/reception/clinicians` | **PROPOSED; NOT IMPLEMENTED** | Reception role; active clinicians; bounded ID/alias/specialization | Pure read; no email/bio/image/links | Include |
| 15 | `GET /api/demo-read-only/reception/availability` | **PROPOSED; NOT IMPLEMENTED** | Reception role; validated clinician/date and published schedule | Pure read; no booking/background mutation | Include after scope approval |
| 16 | `GET /api/demo-read-only/laboratory/assigned` | **PROPOSED; NOT IMPLEMENTED** | Laboratorian ID from session; exact assignment; file-free bounded schema | Pure read; no upload/result file/provider/payment | Include |
| 17 | `GET /api/demo-read-only/admin/staff` | **PROPOSED; NOT IMPLEMENTED** | Admin role; fictional alias/role/active only | Pure read; no IDs/email/created/credential/management | Include |
| 18 | `GET /api/demo-read-only/admin/clinicians` | **PROPOSED; NOT IMPLEMENTED** | Admin role; alias/specialization/active-today only | Pure read; no IDs/email/links/profile management | Include |
| 19 | `GET /api/demo-read-only/admin/overview` | **PROPOSED; NOT IMPLEMENTED** | Admin role; explicit bounded daily/time-band counts | Pure aggregation; no patient/revenue/payment/security detail | Include |

Count result: **19/19 reconciled = 6 existing + 13 proposed; notification excluded; effective v1 = 18 = 6 existing + 12 proposed.** Every other current operation—113 including root—plus four conditional FastAPI documentation operations and every future unlisted operation remains default-denied by the proposed policy.

All proposed list endpoints require dedicated response models, database-side minimal projections, deterministic sort/tie-breaker, default page size at most 25, maximum at most 50, strict query models, and existing hard caps. Those are requirements, not current behavior; current generic clinical pagination defaults to 50 and permits 100 (`backend/app/core/pagination.py`).

## 12. Five-role scope assessment

| Role | Meaningful proposed surface | Source-enforceable boundary | Independent conclusion |
|---|---|---|---|
| Patient | Minimal identity, own completed clinic visits, own file-free report metadata | Current session-to-patient patterns exist; new queries must derive patient ID and enforce owner/file predicates | **MEANINGFUL AND TECHNICALLY ENFORCEABLE; NOT IMPLEMENTED** |
| Doctor | Assigned fictional patient aliases and same-doctor completed visits | Existing doctor-role and assignment/history predicates provide a source basis; new endpoint must retain both assignment and visit doctor predicates | **MEANINGFUL AND TECHNICALLY ENFORCEABLE; NOT IMPLEMENTED** |
| Receptionist | Bounded schedule, schedule-scoped aliases, active clinicians, published availability | Existing receptionist role/read sources exist; proposed schemas remove mutation/contact/clinical fields | **MEANINGFUL; REQUIRES FOUR MINIMAL ENDPOINTS/NEW VIEW AND CLINIC SCOPE APPROVAL** |
| Laboratorian | Assigned clinic request/test/status metadata without files | Existing endpoint derives current laboratorian and service scopes assignment; new projection excludes phone/address/filename/upload | **MEANINGFUL AND TECHNICALLY ENFORCEABLE; NEW VIEW/ENDPOINT NOT IMPLEMENTED** |
| Administrator | Minimal staff/clinician status and bounded operational counts | Existing admin role and source queries exist; new projections/aggregation remove management, patient, billing, and identifiers | **MEANINGFUL AND TECHNICALLY ENFORCEABLE; NEW VIEW/ENDPOINT NOT IMPLEMENTED** |

The patient and doctor require dedicated restricted presentation variants even though their source ownership patterns are usable. Receptionist, laboratorian, and administrator require the three new role-specific read-only views identified in Phase 24A.17. Notifications remain excluded. No role relies on frontend hiding for backend authorization.

## 13. Data projection and isolation assessment

The revised specification requires dedicated Pydantic response models constructed explicitly, database-level projections and predicates, strict/bounded inputs, and recursive forbidden-key assertions. It prohibits returning general models, document dumps, arbitrary dictionaries, broad existing appointment/patient/report/lab/staff/doctor schemas, nested documents, or file responses.

Explicit exclusions cover password/hash data, access/refresh/CSRF/session state, phone/address/DOB/subscription, clinical reason/symptom/body-region/pain data, billing/payment/provider/webhook identifiers, audit/revision/security fields, file names/paths/keys/content/PDF data, external links, and other patients' records. Admin IDs and creation dates are removed; reception patient scope is minimized. Error/cache tests require non-disclosure and private/no-store behavior.

Pagination ceilings, deterministic ordering, stable tie-breakers, bounded strings/arrays/date ranges, and prohibition of unbounded `to_list(length=None)` are clear. Current source contains broader schemas and at least one unbounded analytics materialization, so new dedicated repository work is mandatory. Status: **CORRECTLY SPECIFIED / NOT IMPLEMENTED; no unresolved projection exposure identified in the proposed contract**.

## 14. Eighteen adversarial test verification

No test was run. Each Phase 24A.19 test and Phase 24A.20 addition has a reproducible setup, expected outcome, security property, role/environment, and implementation dependency:

| ID | Threat/setup and attack path | Expected property/result | Role/environment and dependency | Verification |
|---|---|---|---|---|
| T01 | Construct configured app and conflicting global settings | Startup fails or every consumer proves one frozen identity | All; policy step 2 | Complete |
| T02 | Change environment/settings after policy construction | Frozen object rejects change or request behavior is unchanged | All; policy step 2 | Complete |
| T03 | OPTIONS matrix over allowed/unlisted path, origin, method, headers | Only exact allowed preflight; no endpoint/service/DB invocation | All; gate/CORS step 3 | Complete |
| T04 | Wrong/malformed/duplicate Host, absolute authority, forwarded authority | Reject before auth/data access | All; Host gate step 3 | Complete |
| T05 | Inventory/request docs, OAuth redirect, ReDoc, OpenAPI | All absent or denied | All; app/gate steps 2–3 | Complete |
| T06 | Register a synthetic route omitted from policy | Startup inventory fails and execution remains denied | All; gate step 3 | Complete |
| T07 | Spy collection/index/schema operations during isolated init | Any unapproved DDL fails | All; database step 4 | Complete |
| T08 | Tagged/untagged user/session combinations through login/refresh/me | Only exact tagged pair succeeds; generic denial otherwise | Five roles; auth step 5 | Complete |
| T09 | Access-only/refresh-only/no-token/invalid/wrong-tag and CSRF logout matrix | Exact contract; no unrelated revocation or write | Five roles; auth step 5 | Complete |
| T10 | Duplicate, unknown, case-variant, encoded query parameters | 422 before service/repository | Data roles; endpoint step 6 | Complete |
| T11 | Compare missing/unassigned/cross-owner/error bodies and headers | Safe equivalent response where required; no IDs/paths; no-store | Data roles; endpoint step 6 | Complete |
| T12 | Switch users/roles, BFCache restore, normal/demo key collision | No prior-role rows render; cancel/clear/revalidate | Five roles; frontend step 8 | Complete |
| T13 | Inventory production build/static server and separate dev harness | No HMR/dev WS/source map/normal route exposure in demo | Local serving; steps 8–9 | Complete |
| T14 | Register notification candidate without changing v1 policy | Startup/gate still denies | Patient; gate/endpoint steps 3/6 | Complete |
| T15 | Serialize every role, broad normal profile, and unknown role under demo | Only exact demo discriminant validates; forbidden keys absent | Five roles; auth step 5 | Complete |
| T16 | Inspect CORS methods/headers and unsafe/upload preflights | Only GET/POST/OPTIONS and minimum headers | All; CORS step 3 | Complete |
| T17 | Wrong DB/host or admin/index/cross-DB principal capability | Fail before initialization and health | Startup; database step 4 | Complete |
| T18 | Spy worker/scanner/storage/provider/network creation at startup/idle reads | No integration starts or calls out | All; lifespan steps 2–4 | Complete |

The retained Phase 24A.18 matrix supplies the broader parameterized coverage: authentication bypass and expiry, role escalation, patient/doctor/lab ownership, direct API requests, unsafe method variations, aliases/normalization/nested paths, all unlisted routes, file/PDF and payment/webhook denial, background writes, CSRF/refresh races, configuration and production/staging fail-closed behavior, sensitive nested fields, and pagination limits. Route-by-route implementation must instantiate those cases for all effective 18 entries, candidate 9, 113 other current operations, and four conditional documentation routes. No additional test ID is required at specification stage.

## 15. Implementation sequence assessment

Phase 24A.20 defines a dependency-correct 14-step sequence. The mapping below verifies every minimum Phase 24A.21 concern:

| Required concern | Revised sequence coverage | Dependency assessment |
|---|---|---|
| 1. Configuration/environment guards | Step 2, after independent specification freeze | Correct: before connection or route implementation |
| 2. Immutable backend policy | Step 2 | Correct: same app-factory refactor as configuration |
| 3. Backend allowlist | Step 3, after policy | Correct |
| 4. Role/ownership preservation | Steps 5–6, after global deny boundary | Correct; existing checks are retained, not replaced |
| 5. Read-only endpoints | Step 6 | Correct: after policy, gate, DB design, and tagged auth |
| 6. Schemas/projections | Steps 5–6 | Correct: typed auth/me first; dedicated endpoint projections together |
| 7. Frontend demo navigation | Step 8, after independent backend boundary review at step 7 | Correct |
| 8. Three missing role-specific views | Step 8 includes receptionist, laboratorian, and administrator demo routes | Correct; must be explicit in implementation acceptance evidence |
| 9. Patient/doctor restricted integration | Step 8 includes all five role routes and demo-only API/query contracts | Correct; dedicated variants, not ordinary pages |
| 10. Security regression tests | Introduced with steps 2–9 and consolidated at step 10 | Correct; tests accompany each control and full offline review follows |
| 11. Browser verification | Step 13 | Correct: after implementation, review, launcher, and approved preparation |
| 12. Guarded macOS/cross-platform launcher | Step 11 | Correct: after full offline implementation review |
| 13. Fictional accounts/data after approval | Step 12 | Correct; approval ordinals match Phase 24A.16 preparation prerequisites |
| 14. Controlled demonstration | Step 14 | Correct: after all 11 approvals and prior steps |

The mandatory stop after step 7 prevents frontend or launcher work from outrunning the backend security boundary. Step 4 has an earlier fail-stop if no-DDL initialization cannot be proven. The approval sets for preparation and browser smoke match Phase 24A.16; the actual demonstration requires all 11. No implementation step is scheduled before its technical prerequisite.

## 16. New findings

**No new Critical, High, Medium, or Low finding was identified.**

Two implementation-review cautions are already documented conditions, not new defects:

1. Beanie/no-DDL runtime feasibility is **NOT VERIFIED**. Step 4 must stop for redesign if spies and isolated evidence cannot prove the required behavior.
2. Final scalar/optional types and ordinary-mode compatibility for the discriminated `/api/auth/me` union require code-level review and T15; the security branches and permitted fields are nevertheless sufficiently specified.

Neither caution authorizes implementation, connection, index work, or runtime testing now.

## 17. Technical readiness decision

**APPROVED WITH CONDITIONS** for a future, separately authorized implementation review.

Evidence for this decision:

- all 12 audit findings have concrete, consistent corrections and tests;
- middleware, authority, CORS, authentication, role, owner/assignment, and privacy layers have an explicit order;
- database uncertainty is represented as a stop condition, not an unsupported guarantee;
- the frontend development and presentation surfaces are separated;
- `/api/auth/me` has a role-discriminated minimum-data contract;
- the route table is closed-world, exact, versioned, and count-consistent;
- notifications are unambiguously excluded;
- all five roles have technically enforceable minimal stories; and
- the implementation sequence prevents downstream work before independent backend review.

Conditions:

1. Freeze the Phase 24A.20 policy/version/table through independent acceptance.
2. Obtain explicit authorization before any code or test change.
3. Implement only steps 2–7, in order, and stop for independent backend review.
4. Stop at database step 4 if a no-DDL initialization path cannot be proven.
5. Do not expand route, field, role, integration, environment, database, Host, or frontend scope without a new reviewed policy version.
6. Preserve ordinary-mode behavior and independently verify existing security/regression contracts.
7. Obtain the relevant Phase 24A.16 approvals before environment, data, account, launcher, browser, or runtime work.

Technical approval does **not** authorize implementation. Implementation remains **NOT AUTHORIZED / NOT STARTED**.

## 18. Remaining approval requirements

No approval evidence was introduced. All 11 remain **PENDING**, with owners still unassigned unless separately documented outside the reviewed repository evidence:

| # | Approval | Status |
|---:|---|---|
| 1 | Named demo environment and machine | **PENDING** |
| 2 | Environment owner/operator | **PENDING** |
| 3 | Approved demo viewers | **PENDING** |
| 4 | Approved five-role route/workflow scope | **PENDING** |
| 5 | Fictional dataset and fields | **PENDING** |
| 6 | Role accounts, access, activation, credentials, and custody | **PENDING** |
| 7 | Loopback/network/Host/origin boundary | **PENDING** |
| 8 | Payment-disabled configuration/evidence | **PENDING** |
| 9 | File/storage/scanner exclusion/evidence | **PENDING** |
| 10 | Start, stop, abort, and incident authority | **PENDING** |
| 11 | Retention, cleanup, database, logs, and evidence disposition | **PENDING** |

Approval of the technical design cannot substitute for any item above.

## 19. Eight connected gate status

No connected verification occurred. The exact eight gates remain **BLOCKED**:

| # | Connected gate | Status | Required future evidence / demo limitation |
|---:|---|---|---|
| 1 | Connected multi-clinician authorization | **BLOCKED** | Approved replica-set identities; mismatched role/owner; transaction/race/rollback evidence. Narrow demo role smoke cannot close the full gate. |
| 2 | MongoDB query plans and realistic scale | **BLOCKED** | Representative data, explain, offsets, latency/concurrency/BSON/pool evidence. No performance claim is permitted without it. |
| 3 | Actual database index verification | **BLOCKED** | Approved catalog, uniqueness/preflight, and plan-use evidence. The preparation/runtime design is not operational evidence. |
| 4 | Socket-capable ClamAV protocol/scanning | **BLOCKED** | Approved daemon/config and clean/malicious/error/timeout evidence. Only irrelevant while all file/PDF routes remain denied. |
| 5 | Private storage integration/access | **BLOCKED** | Approved roots/permissions/promotion/cleanup/traversal/authorization evidence. Only irrelevant while all file routes remain denied. |
| 6 | Browser end-to-end journeys | **BLOCKED** | Approved environment/browser/data with session/role/CSRF/account-switch/recovery evidence. Narrow smoke does not close the full gate. |
| 7 | Production proxy/TLS/cookie/cache | **BLOCKED** | Production-like ingress/TLS/Host/forwarding/CORS/cookie/cache/body/docs/webhook evidence. Loopback demo cannot close it. |
| 8 | Backup and restore | **BLOCKED** | Approved artifact, isolated restore, validation, RPO/RTO, and cleanup. Any disposable-demo waiver requires approval 11. |

Actual controlled local demo: **NO-GO**. Connected client demo: **NO-GO**. Phase 24B: **BLOCKED / NOT STARTED**.

## 20. Recommended next milestone

The next milestone may be a **separately authorized Phase 24A demo backend-boundary implementation** limited to revised-plan steps 2–7:

1. immutable Settings/policy/app construction;
2. Host, method/path, CORS, and route-inventory gates;
3. isolated no-DDL database initialization design and tests;
4. tagged authentication/logout and typed `/api/auth/me`;
5. dedicated bounded schemas/repository projections/12 role-data endpoints; and
6. an independent backend security review stop.

Such a milestone must explicitly authorize code/tests and define its offline test boundary. It must not authorize frontend routes, launcher work, account/fixture preparation, service or database startup, browser activity, presentation, connected verification, or Phase 24B.

Final Phase 24A.21 status:

| Decision item | Status |
|---|---|
| Historical findings | **7 Medium + 3 Low resolved in specification; 2 Informational accurately dispositioned** |
| New findings | **NONE** |
| Candidate/effective allowlist | **19 candidates; 6 existing + 13 proposed; 18 effective after notification exclusion** |
| Five-role scope | **Meaningful and enforceable in design; all new/restricted surfaces NOT IMPLEMENTED** |
| Adversarial tests | **18/18 verified as specified; retained broader matrix complete; NOT RUN** |
| Technical readiness | **APPROVED WITH CONDITIONS** |
| Implementation authorization | **NOT AUTHORIZED** |
| Demo implementation | **NOT STARTED** |
| Clinic approvals | **0/11 approved; 11/11 PENDING** |
| Connected gates | **0/8 closed; 8/8 BLOCKED** |
| Controlled local demo | **NO-GO** |
| Connected client demo | **NO-GO** |
| Phase 24B | **BLOCKED / NOT STARTED** |

Stop after Phase 24A.21 and wait for explicit review before implementation.
