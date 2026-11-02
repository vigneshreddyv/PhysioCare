# Phase 24A.20 — Demo Security Specification Revision and Audit Closure

Assessment date: 2026-11-02

Repository baseline: `5eaced696a156ca74233fd04252fea52345d8af8`

Revised policy: `five-role-read-only-v1`

## 1. Executive summary

Phase 24A.20 is complete as a **documentation-only specification revision**. The self-contained revised specification is `docs/PHASE_24A20_DEMO_READ_ONLY_MODE_TECHNICAL_SPECIFICATION.md`. No application, test, configuration, environment, launcher, account, fixture, database, or infrastructure change was made or authorized.

All 12 Phase 24A.19 findings are retained and reconciled. The seven Medium and three Low findings are **RESOLVED IN SPECIFICATION**; A19-I01 is **NOT APPLICABLE WITH EVIDENCE** as a current alternate-surface concern, with preservation tests still required; A19-I02 is **RESOLVED IN SPECIFICATION** through explicit minimization. These are design dispositions, not proof of implementation or operational closure.

The original 19 candidates remain traceable: six existing operations are verified and 13 proposed operations remain absent/not implemented. Notifications are deliberately excluded, producing an effective immutable v1 table of 18 candidates (six existing and 12 proposed). No proposed route has been promoted to existing status.

Technical specification readiness is **APPROVED WITH CONDITIONS** for a future, separately authorized implementation review. Implementation is **NOT AUTHORIZED** and remains **NOT STARTED**. All 11 clinic approvals are **PENDING**; both actual controlled local demo and connected client demo are **NO-GO**; all eight connected gates are **BLOCKED**; Phase 24B is **BLOCKED / NOT STARTED**.

## 2. Documents and source reviewed

The following authoritative documents were read and preserved unchanged:

- `docs/PHASE_24A19_INDEPENDENT_DEMO_SECURITY_SPECIFICATION_AUDIT.md` — finding authority.
- `docs/PHASE_24A18_DEMO_READ_ONLY_MODE_TECHNICAL_SPECIFICATION.md` — superseded design baseline, retained as historical evidence.
- `docs/PHASE_24A17_FIVE_ROLE_READ_ONLY_DEMO_SURFACE_DESIGN_REPORT.md`.
- `docs/PHASE_24A16_DEMO_APPROVAL_RESOLUTION_AND_ENVIRONMENT_COMPATIBILITY_PLAN.md`.
- `docs/PHASE_24A15_CONTROLLED_LOCAL_DEMO_PREPARATION_AND_VERIFICATION_REPORT.md`.

Relevant architecture was checked in `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/database.py`, authentication middleware/routes/schemas, notification routes/models/frontend, database models/repositories/services, `frontend/package.json`, `frontend/vite.config.js`, frontend routing/auth/query/API code, and service-worker/static/mount/WebSocket inventories. No service or external system was started or contacted.

## 3. Repository state

State captured before the first Phase 24A.20 document was created:

| Item | Verified value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Tracked modifications | 114 |
| Untracked paths | 96 |
| Total dirty paths | 210 |

After creating the first authorized document, and before this report, the counts were 0 staged, 114 tracked modifications, 97 untracked paths, and 211 total dirty paths. The expected final Phase 24A.20 delta is exactly two new untracked documentation files. All pre-existing tracked and untracked changes were preserved. No commit, push, branch switch, stash, reset, clean, checkout, or restore was performed.

## 4. Twelve-finding reconciliation register

Status describes specification closure only. Every row that requires code or testing remains operationally unimplemented.

| ID | Severity | Audit evidence | Original specification section | Required correction | Revised specification section | Resolution status | Remaining limitation | Implementation / clinic approval |
|---|---|---|---|---|---|---|---|---|
| A19-M01 | Medium | Mutable global `settings`; the app-factory argument controls docs while lifespan/CORS/services use the global (`backend/app/core/config.py:104-110,721-737`; `backend/app/main.py:31-105`) | Phase 24A.18 §§5–6 | Freeze and inject one policy; prohibit runtime environment/global reads | Revised spec §§3–4; tests T01–T02 | **RESOLVED IN SPECIFICATION** | Current code still has the object split | Code and independent review; approval only if identities change |
| A19-M02 | Medium | Current CORS plus three HTTP middleware; exact effective order was not prescribed | Phase 24A.18 §5.3 | Specify/test outer gate, CORS, errors/cache, endpoint non-invocation | Revised spec §5; T03, T11, T16 | **RESOLVED IN SPECIFICATION** | Stack is not implemented or runtime-proven | Code/tests; no clinic approval |
| A19-M03 | Medium | No `TrustedHostMiddleware`; binding/CORS did not define Host validation | Phase 24A.18 §§6, 11 | Exact Host authority; reject forwarded authority without trusted proxy | Revised spec §6; T04 | **RESOLVED IN SPECIFICATION** | Current app still lacks this demo control | Code/tests; clinic network policy confirms exact values |
| A19-M04 | Medium | `init_db()` invokes `init_beanie` with indexed models (`backend/app/database.py:29-68`); index-neutral behavior is unverified | Phase 24A.18 §11 | Define preparation/runtime split; prove no runtime DDL; stop if unsupported | Revised spec §7; T07, T17 | **RESOLVED IN SPECIFICATION** | Installed Beanie behavior and feasible safe initialization remain unproven | Code/test design; database approval for any preparation/index action |
| A19-M05 | Medium | Vite dev/preview/proxy exist; no five-role Host/port/HMR policy (`frontend/package.json`; `frontend/vite.config.js`) | Phase 24A.18 §§10–11 | Choose constrained serving model; inventory assets, HMR, WebSockets | Revised spec §12; T13 | **RESOLVED IN SPECIFICATION** | Static server/build/launcher are not designed in executable form | Frontend/launcher implementation; environment/network approval |
| A19-M06 | Medium | `/api/auth/me` has no response model and returns broad patient/doctor profiles (`backend/app/api/auth.py:156-169`) | Phase 24A.18 §§7.1, 9 | Explicit discriminated response model and exhaustive role tests | Revised spec §§9, 11; T15 | **RESOLVED IN SPECIFICATION** | Field types must be verified during implementation against final schemas | Code/tests; clinic data-field approval |
| A19-M07 | Medium | Notification candidate was allowlisted while also gated pending browser verification | Phase 24A.18 §§7.2, 8 | Exclude from v1 or create a separate immutable version/approval transition | Revised spec §§8, 14; T14 | **RESOLVED IN SPECIFICATION** | Notification display is absent from v1 | Code must enforce denial; future workflow/content approval for any new version |
| A19-L01 | Low | Current logout validates refresh only when present and can clear cookies with matching CSRF and no token (`backend/app/api/auth.py:137-154`) | Phase 24A.18 §7.1 | Define token/CSRF combinations and corrected contract | Revised spec §13; T09 | **RESOLVED IN SPECIFICATION** | Current behavior has not been changed or re-tested | Code optional depending on final gap; no clinic approval |
| A19-L02 | Low | Current CORS advertises unsafe methods and upload headers (`backend/app/main.py:100-105`) | Phase 24A.18 did not explicitly narrow demo CORS | Restrict to GET/POST/OPTIONS and minimum headers | Revised spec §5; T03, T16 | **RESOLVED IN SPECIFICATION** | Current CORS remains broader | Code/tests; no clinic approval |
| A19-L03 | Low | Shared QueryClient retry/cache; no exact namespace or back-forward-cache policy | Phase 24A.18 §10 | Namespace keys; no placeholder; cancel/clear; BFCache revalidation | Revised spec §12.3; T12 | **RESOLVED IN SPECIFICATION** | Frontend behavior remains unimplemented | Frontend/browser tests; no clinic approval |
| A19-I01 | Informational | No backend mount/WebSocket/static route and no frontend service worker found | Current source inventory | Preserve smaller surface with inventory tests | Revised spec §§2, 12, 15; T05, T13 and route inventory | **NOT APPLICABLE WITH EVIDENCE** | Future code can introduce a surface, so tests remain mandatory | Test/inventory implementation; no clinic approval |
| A19-I02 | Informational | Reception directory/availability and admin IDs/created dates were not essential to every story | Phase 24A.18 role projections | Default to smaller scope and require clinic choice for broader fields | Revised spec §§8.2, 10–11 | **RESOLVED IN SPECIFICATION** | Reception schedule/availability scope still needs clinic approval | Projection implementation; workflow/data approval |

Finding totals remain exactly 0 Critical, 0 High, 7 Medium, 3 Low, and 2 Informational. Phase 24A.19 remains unchanged.

## 5. Revised immutable runtime security policy

The revised design requires one validated `Settings` instance and one frozen `ReadOnlyDemoPolicy` created at application construction. All app-factory, middleware, lifespan, CORS, authentication-tag, route-inventory, health, and database-target decisions consume that same policy. No request-time environment reload, mutable global flag, or frontend setting can expand permissions. A restart reconstructs and revalidates the policy.

The policy contains the environment identity, enabled and startup-validated states, immutable role/method/path table, excluded capabilities, policy version, exact frontend/backend authorities, database identity, rehearsal tag, and reviewed database-initialization mode. It contains no secrets.

Missing/conflicting settings, wrong environment/identity/database/authority, enabled excluded integration, route drift, or incomplete validation prevents the ASGI application from serving any route. Production rejects demo mode. V1 staging rejects it unconditionally; any staging exception requires a new policy and approval. This is specified, not implemented.

## 6. Middleware and CORS ordering

Required outer-to-inner order is: exact authority gate → immutable method/path gate → narrow demo CORS → existing unsafe-origin and bounded-body controls → FastAPI routing with authentication/session/CSRF, then demo policy, existing role checker, and owner/assignment predicate → privacy response handling.

`OPTIONS` is not an allowed application operation. Only exact-path preflight from the exact frontend origin, for the exact allowed method and a subset of `Content-Type`/`X-CSRF-Token`, reaches CORS. It performs no authentication, endpoint, service, repository, or database call. Other preflights receive a non-disclosing denial without browser exposure.

CORS advertises only GET, POST, and OPTIONS plus the two minimum headers. It is never authorization. Unauthorized endpoint responses remain inaccessible because the backend gate, session, role, and ownership checks remain authoritative and privacy headers apply on success and error paths. Exact Starlette order and exception behavior require tests T03, T11, and T16.

## 7. Host-header protection

V1 accepts exactly browser origin `http://127.0.0.1:<frontend-port>` and backend authority `127.0.0.1:<backend-port>`. `localhost`, IPv6, LAN/public addresses, wildcard/suffix hosts, and alternate ports are rejected. Binding is IPv4 loopback only.

An outer TrustedHost-equivalent control rejects malformed or duplicate Host, conflicting absolute-form authority, and forwarded Host/protocol inputs. Uvicorn proxy-header trust is disabled and trusted proxy networks are empty. The controlled static proxy must set the exact backend Host and preserve the exact approved browser Origin. Host validation, binding, cookies, CORS, authentication, and route authorization remain independent controls. Exact values still require clinic network approval.

## 8. Beanie and index initialization

Current `init_beanie` behavior is explicitly **unverified** for index neutrality. The revised design separates a future, separately authorized preparation step from presentation runtime. Preparation alone may create the dedicated database, approved indexes, tagged fictional accounts, and fixtures. A read-only preflight then records target/listener identity, catalog, tagged counts/relationships, and unexpected-record absence without repair.

Runtime must use a reviewed initialization path proven by spies and isolated tests to perform no collection/index reconciliation, schema maintenance, seeding, migration, cleanup, or fixture activity. If the installed Beanie version cannot do this, work stops for a new independently reviewed design; runtime index creation is never silently accepted. Wrong database, host, catalog, process identity, or privilege fails before health is served.

A physically read-only database user is incompatible with the current same-database session, refresh, throttle, and TTL security writes. The runtime principal is therefore limited to the dedicated database and only approved product reads/security-state operations, without cross-database, administrative, index, backup, production, or staging privilege. Where local MongoDB cannot express that boundary, listener/process isolation is a documented compensating control requiring approval. No database was contacted in Phase 24A.20.

## 9. Frontend static, HMR, and WebSocket behavior

Development is not an approved presentation mode. Any separately authorized development work must bind Vite and its HMR WebSocket to fixed IPv4-loopback ports, restrict Host/origin, and proxy only to the validated backend. Source serving, HMR, debug output, and development WebSockets stay outside presentation evidence.

The controlled local demonstration uses an offline production build with source maps disabled and no Vite development server, HMR client, or development WebSocket. A minimal loopback static server serves only built assets and the SPA entry, blocks directory listing/dotfiles/source maps, and proxies only `/api/*` and `/health` to the exact backend. It cannot proxy arbitrary paths, WebSockets, file-system paths, or dev endpoints.

Static assets do not enter FastAPI's API allowlist because the current backend has no frontend mount. The static server has a separate exact Host/path/method policy; backend API policy remains independently authoritative. React uses a demo-only layout/API/query namespace, imports no mutation/file/payment pages, performs no polling or normal-route prefetch, clears/cancels private state on identity changes, and revalidates sessions on browser back-forward restoration.

## 10. Typed `/api/auth/me` projection

The existing endpoint remains the sole authentication initialization path and retains `get_current_user`, active-account, session, and revocation checks. The future response model is an explicit discriminated union with unique `view` literals:

- `NormalAuthMeOut(view='normal', demo_mode=False, ...)` preserves typed normal-mode behavior.
- `DemoPatientAuthMeOut` exposes top-level account ID, fictional email, full name, role, policy version, and only patient ID plus optional supported gender.
- `DemoDoctorAuthMeOut` exposes the same top-level identity and only doctor ID, specialization, and active-today state.
- `DemoReceptionAuthMeOut`, `DemoLaboratoryAuthMeOut`, and `DemoAdminAuthMeOut` expose the same minimal top-level identity with `profile=None`.

Demo output excludes hashes, tokens, session/CSRF data, internal security state, phone, DOB, subscription, address, clinician contact/profile links, payment/provider/audit/file fields, and full database documents. Expired, revoked, invalid, inactive, untagged, wrong-tag, or unknown-role identities fail before serialization. The frontend accepts only known role/view combinations and never treats `demo_mode` as backend authorization.

## 11. Notification feature-gating decision

Current notification listing is recipient-scoped and read-only, while mark-one and mark-all-read operations mutate state. Existing notification content and related IDs can also expose workflow-sensitive information, and the current UI presents mutation controls.

**Decision: option A is not sufficiently unambiguous for v1, and option B is not justified. Notifications are excluded.** Candidate 9 remains proposed/absent and is denied; current notification GET and PATCH operations, unread counts, background requests, navigation, and read-state changes are denied. A future display requires a new policy version, minimal fictional-content schema, recipient-only endpoint, no related IDs/mutations, clinic approval, tests, independent review, and approved browser verification.

## 12. Reconciled 19-entry allowlist

The table preserves six verified existing operations and 13 proposed absent operations. “Schema” for proposed routes means the dedicated future schema required by the design, not an existing implementation. Existing auth dependencies remain mandatory; proposed demo policy/role/tag checks add restrictions.

| # | Exact method and registered/proposed path | Status | Role and authentication | Existing authorization dependency / ownership | Required response schema and data projection | Side effects; notification/file interaction | V1 decision | Further source verification |
|---:|---|---|---|---|---|---|---|---|
| 1 | `GET /health` | **Existing verified** | Unauthenticated; exact loopback/Host gate | None currently | Future `DemoHealthOut`: status, demo environment, policy version, payments/docs disabled; no DB/host/path detail | Read-only; no notification/file | Include after guarded projection | Verify implemented schema and no DB call |
| 2 | `POST /api/auth/login` | **Existing verified** | Untagged request; only approved tagged five-role account succeeds | Current auth rate limiter; future immutable tag/role check | Existing typed login result/cookies; no product document | Creates session/cookies and throttle state; no notification/file | Include as security-write exception | Verify tag continuity and exact current response |
| 3 | `GET /api/auth/csrf` | **Existing verified** | Valid tagged refresh cookie | Refresh/session validation and rate limiter | Existing CSRF response/cookie only | Cookie/throttle security effect; no product/file activity | Include as security lifecycle | Verify tagged session behavior |
| 4 | `POST /api/auth/refresh` | **Existing verified** | Valid tagged refresh plus CSRF | Refresh/session validation | Existing typed refresh/cookies | Atomic session rotation/throttle write; no notification/file | Include as security-write exception | Verify tag recheck and reuse behavior |
| 5 | `POST /api/auth/logout` | **Existing verified** | Token combinations governed by revised spec §13; valid CSRF pair | Current validation only when token present; future tag/user/role/session validation | Empty 204/cleared cookies or generic session error | Revocation only for validated token; no-token case no DB write; no file | Include as security lifecycle | Verify and implement exact token matrix |
| 6 | `GET /api/auth/me` | **Existing verified** | Any approved tagged role; authenticated | `get_current_user`, active account; future tag/policy check; own identity | Future discriminated `AuthMeResponse`; exact role branch from §10 | DB read only; no notification/file | Include after typed implementation | Verify final field types and frontend compatibility |
| 7 | `GET /api/demo-read-only/patient/completed-visits` | **Proposed; absent/not implemented** | patient; authenticated/tagged | Patient role; patient ID derived from session | Dedicated bounded visit-list schema: visit ID, date/time/timezone, clinician alias, clinic mode, completed status | Pure owner read; no clinical/billing/address/file | Include | Verify repository predicate/projection and registered route after implementation |
| 8 | `GET /api/demo-read-only/patient/report-metadata` | **Proposed; absent/not implemented** | patient; authenticated/tagged | Patient role; owner from session; require no file path | Dedicated bounded metadata schema: report ID/title/category/date/therapist alias/`has_file=false` | Pure owner read; no content/description/file/PDF | Include | Verify file predicate and serialized forbidden keys |
| 9 | `GET /api/demo-read-only/patient/notifications` | **Proposed; absent/not implemented** | patient recipient; authenticated/tagged | Patient role and recipient equality | Candidate minimal all-read notification schema was not approved | Listing could read; existing UI/PATCH mutates; sensitive content/related IDs possible | **Exclude from v1; deny** | Reverify only under a future policy/version review |
| 10 | `GET /api/demo-read-only/doctor/patients` | **Proposed; absent/not implemented** | doctor; authenticated/tagged | Doctor role; doctor ID from session scopes repository | Dedicated bounded assigned-patient schema: patient ID and fictional alias | Pure assigned read; no contact/DOB/gender/file | Include | Verify query is assignment-scoped in repository |
| 11 | `GET /api/demo-read-only/doctor/patients/{patient_id}/completed-visits` | **Proposed; absent/not implemented** | doctor; authenticated/tagged | Doctor role; exact assignment and same-doctor visit predicate; uniform missing/unassigned | Dedicated patient/visit schema: patient ID/alias and bounded completed visit ID/date/time/mode/status | Pure assigned read; no clinical/report/care/file data | Include | Verify both predicates and error equivalence |
| 12 | `GET /api/demo-read-only/reception/schedule` | **Proposed; absent/not implemented** | receptionist; authenticated/tagged | Receptionist role; bounded approved date window | Dedicated schedule schema: appointment ID, fictional aliases, date/time/timezone, assignment-pending, status | Pure read; no contact/address/reason/billing/cancel/file | Include, clinic scope approval required | Verify date bounds and field projection |
| 13 | `GET /api/demo-read-only/reception/patients` | **Proposed; absent/not implemented** | receptionist; authenticated/tagged | Receptionist role; default schedule-participant scope | Dedicated bounded alias schema: fictional patient ID and display alias | Pure read; no contact/profile/clinical/file | Include with minimized default | Verify source query and clinic decision on directory breadth |
| 14 | `GET /api/demo-read-only/reception/clinicians` | **Proposed; absent/not implemented** | receptionist; authenticated/tagged | Receptionist role; active clinicians only | Dedicated bounded clinician schema: ID, alias, specialization; home-visit flag only if approved | Pure read; no email/bio/image/links/file | Include | Verify active predicate and optional-field approval |
| 15 | `GET /api/demo-read-only/reception/availability` | **Proposed; absent/not implemented** | receptionist; authenticated/tagged | Receptionist role; validated clinician/date; published schedule only | Dedicated bounded availability schema: timezone/date and slot time/state | Pure read; no booking or file | Include, clinic scope approval required | Verify published-state semantics and strict query model |
| 16 | `GET /api/demo-read-only/laboratory/assigned` | **Proposed; absent/not implemented** | laboratorian; authenticated/tagged | Laboratorian role; assigned user equals current user | Dedicated bounded lab schema: request ID, patient alias, clinic-visit mode, tests, request/report status, created time | Pure assigned read; no contact/address/upload/result file/provider/payment | Include | Verify assignment predicate, list bounds, forbidden keys |
| 17 | `GET /api/demo-read-only/admin/staff` | **Proposed; absent/not implemented** | admin; authenticated/tagged | Admin role | Dedicated bounded staff schema: fictional display name, role, active state | Pure read; no ID/email/created date/credential/file | Include with minimized projection | Verify no hidden entitlement/account fields |
| 18 | `GET /api/demo-read-only/admin/clinicians` | **Proposed; absent/not implemented** | admin; authenticated/tagged | Admin role | Dedicated bounded clinician schema: alias, specialization, active-today | Pure read; no ID/email/link/profile/file | Include with minimized projection | Verify active-today calculation and projection |
| 19 | `GET /api/demo-read-only/admin/overview` | **Proposed; absent/not implemented** | admin; authenticated/tagged | Admin role | Dedicated bounded aggregate: today/yesterday and morning/afternoon/evening counts | Pure aggregation; no revenue/patient/subscription/payment/security/file data | Include | Verify bounded DB aggregation and no broad analytics reuse |

The effective immutable v1 table therefore has 18 entries. All lists use deterministic stable ordering, default page size at most 25, maximum at most 50, existing hard caps, strict query schemas, and database-level projections. Every unlisted application operation, all four conditional documentation operations, root, files/PDFs, payments/webhooks, background integrations, maintenance, and future route additions are denied by default.

## 13. Reconciled adversarial test matrix

No test below was implemented or executed during Phase 24A.20.

| ID | Threat scenario | Required setup and request/attack path | Expected response | Security property | Role | Implementation step |
|---|---|---|---|---|---|---|
| T01 | App settings conflict with global settings | Construct app with one validated object and conflicting mutable global | Startup fails or all consumers prove same frozen identity | Single effective policy | all | Policy/app factory, step 2 |
| T02 | Runtime flag mutation changes authorization | Mutate environment/settings/app state after construction, then request allowed/denied paths | Mutation rejected or has no request effect | Runtime immutability | all | Policy, step 2 |
| T03 | CORS preflight bypasses deny gate | OPTIONS matrix for allowed/unlisted path, origin, method, and headers | Only exact allowed preflight succeeds; no endpoint/service/DB call | Middleware/CORS order | all | Gate/CORS, step 3 |
| T04 | Host, DNS-rebinding, or forwarded spoof | Wrong/duplicate/malformed Host, absolute authority, forwarded Host/proto | Rejected before auth or data access | Authority isolation | all | Host gate, step 3 |
| T05 | Generated docs route survives | Inventory/request OpenAPI, docs, OAuth redirect, and ReDoc | All absent or uniformly denied | Framework surface closure | all | App factory/gate, steps 2–3 |
| T06 | Later route omitted from table | Register synthetic unlisted operation in test app and request it | Startup inventory fails and route cannot execute | Future default-deny | all | Inventory/gate, step 3 |
| T07 | ODM initialization performs DDL | Spy collection/index calls around isolated runtime initialization and compare catalog | Any unapproved create/drop/change fails | No hidden DB maintenance | all | DB design, step 4 |
| T08 | Untagged/wrong-tag identity survives | Combine tagged/untagged users/sessions through login, refresh, me | Only exact tagged user/session succeeds; generic denial otherwise | Demo identity continuity | all roles | Tagged auth, step 5 |
| T09 | Logout token combinations bypass boundary | Access-only, refresh-only, none, invalid, wrong-tag, CSRF variants | Exact revised contract; no unrelated revocation/write | Accurate lifecycle boundary | all roles | Auth, step 5 |
| T10 | Query pollution changes predicates | Repeat/case-change/encode/unknown page/date/status/mode parameters | 422 before service/repository | Fixed request semantics | all data roles | Endpoints, step 6 |
| T11 | Error/cache leaks identity/data | Compare missing, unassigned, cross-owner, denied bodies and headers | Safe equivalent response where required; no-store; no IDs/paths | Non-disclosure | all data roles | Endpoints, step 6 |
| T12 | Query or BFCache leaks previous role | Switch users/roles; navigate back/forward; seed normal/demo key collision | No prior-role row renders; cache cancelled/cleared; session revalidated | Client confidentiality | all roles | Frontend, step 8 |
| T13 | Static/HMR surface expands demo | Inventory production build/static server; separately inspect dev harness | No HMR/dev WS/source maps/normal route chunks in demo | Serving isolation | all | Frontend/static, steps 8–9 |
| T14 | Notification code activates in v1 | Add/register candidate without changing v1 policy | Startup inventory or gate still denies | Versioned scope | patient | Gate/endpoint, steps 3/6 |
| T15 | Broad `/auth/me` branch validates as demo | Serialize each role, normal broad profile, and unknown role | Only exact role-discriminated demo branch succeeds; forbidden keys absent | Typed minimization | all roles | Auth schema, step 5 |
| T16 | Demo CORS advertises excess capability | Inspect configured methods/headers and send unsafe/upload preflights | Only GET/POST/OPTIONS and minimum headers advertised | Browser least privilege | all | CORS, step 3 |
| T17 | DB target/principal drifts | Supply wrong host/DB or admin/index/cross-DB capability in isolated checks | Fail before ODM initialization/health | Database isolation | all | DB design, step 4 |
| T18 | Worker/provider starts or calls out | Spy payment worker, scanner, storage, provider, network creation at startup and idle reads | No integration starts and no outbound activity occurs | Integration isolation | all | Lifespan, steps 2–4 |

T15–T18 are the additional tests justified by the seven Medium corrections. Route-by-route tests must also cover the effective 18 entries, excluded notification candidate, 113 other current operations, four framework documentation operations, normalization, projections, paging, role/owner/assignment, and frontend absence/network behavior.

## 14. Low and Informational finding dispositions

- **A19-L01, Low — RESOLVED IN SPECIFICATION.** Revised §13 defines CSRF mismatch, token-present validation/revocation, invalid/wrong-tag denial, and the no-token idempotent 204/no-DB-write case. Implementation and T09 remain required; severity is unchanged.
- **A19-L02, Low — RESOLVED IN SPECIFICATION.** Revised §5 narrows methods and headers and separates preflight from authorization. Implementation plus T03/T16 remain required.
- **A19-L03, Low — RESOLVED IN SPECIFICATION.** Revised §12.3 defines a demo namespace, no placeholder data, cancellation/clearing, identity/policy keying, and BFCache revalidation. Frontend and browser tests remain required.
- **A19-I01, Informational — NOT APPLICABLE WITH EVIDENCE** to the current alternate-surface inventory. Absence is a verified strength, not a permanent guarantee. T05/T13 and mount/WebSocket/static/service-worker inventories preserve it.
- **A19-I02, Informational — RESOLVED IN SPECIFICATION.** Admin IDs/created dates are omitted; receptionist patient scope defaults to approved schedule participants. Broader fictional scope remains a clinic choice, not a default.

## 15. Revised implementation dependency plan

No step is authorized by this report.

| Step | Future work | Required exit evidence | Authorization boundary |
|---:|---|---|---|
| 1 | Independent review and freeze of Phase 24A.20 | No unresolved Medium design finding; accepted v1 table/version | Technical review only |
| 2 | Single Settings/policy/app-factory refactor | T01–T02; default-off and staging/production failure; no connection | Explicit code authorization |
| 3 | Host, route gate, CORS, and inventory enforcement | T03–T06/T16; every unlisted route denied | Security code authorization |
| 4 | Safe runtime database initialization design | T07/T17; no runtime DDL; wrong target fails | Database/security approval before any connected work |
| 5 | Tagged authentication, logout contract, typed auth/me | T08–T09/T15 and existing auth/session regressions | Security and data-field approval |
| 6 | Dedicated response schemas, projections, repositories, endpoints | All 18 entry tests, forbidden fields, role/owner/assignment, side-effect inventory | Workflow/data approval |
| 7 | Independent backend boundary review | Exact diff and tests; no blocking finding | Independent review approval |
| 8 | Demo-only React routes and query isolation | Render/import/network contract and T12 | Separate frontend authorization |
| 9 | Production-style build/static server | T13 plus Host/proxy/assets/source-map checks | Launcher/environment authorization |
| 10 | Full offline regression/security review | Approved new/existing suites, lint/build/lock/audit/diff evidence | Independent review |
| 11 | Guarded cross-platform launcher | Preflight/start/stop/abort/process ownership; no data prep | Separate launcher authorization |
| 12 | Database/index/account/fictional-fixture preparation | Tagged inventory and read-only preflight; no real/payment/file data | Approvals 1, 2, 4–6, 8, 9, 11 |
| 13 | Narrow approved browser smoke | Five roles; exact traffic; session/role negatives; no HMR/files/payments | Approvals 1–10; named operator/viewers |
| 14 | Controlled demonstration | Named GO, window, abort authority; otherwise NO-GO | All 11 approvals |

Implementation must stop after step 7 for independent review before frontend or launcher work. If safe no-DDL ODM initialization cannot be proven at step 4, implementation stops for a new specification/review. No step implicitly authorizes a later step.

## 16. Technical implementation readiness decision

**Decision: APPROVED WITH CONDITIONS for a future, separately authorized implementation review.**

Conditions:

1. An independent reviewer accepts this complete revision and effective 18-entry v1 table.
2. No route, field, role, integration, host, environment, or database scope expands without a new policy revision and review.
3. Work follows the dependency plan and stops after step 7.
4. The database initialization question is resolved with isolated evidence; inability to prove no runtime DDL is a stop condition.
5. Relevant clinic approvals precede environment, data, account, launcher, browser, or runtime activity.
6. Existing security/regression behavior remains independently verified in separately authorized work.

This readiness decision means the seven Medium ambiguities now have concrete, internally consistent design corrections. It does not mean the current code satisfies the design. **Implementation authorization: NOT AUTHORIZED. Demo implementation: NOT STARTED.**

## 17. Clinic approval status

No new approval evidence was produced. All 11 Phase 24A.16 approvals remain **PENDING**:

| # | Approval | Status |
|---:|---|---|
| 1 | Environment and machine | **PENDING** |
| 2 | Named operator | **PENDING** |
| 3 | Named viewers | **PENDING** |
| 4 | Five-role workflow and presentation scope | **PENDING** |
| 5 | Fictional dataset and field content | **PENDING** |
| 6 | Accounts, access, credential custody, and lifetimes | **PENDING** |
| 7 | Loopback/network/Host/origin boundary | **PENDING** |
| 8 | Payment-disabled configuration and evidence | **PENDING** |
| 9 | Storage/scanner/file exclusion and evidence | **PENDING** |
| 10 | Start, stop, abort, and incident authority | **PENDING** |
| 11 | Cleanup, retention, database, logs, and evidence disposition | **PENDING** |

These approvals cannot be inferred from technical readiness, prior local test results, fictional-data intent, or documentation authorship.

## 18. Eight connected gate status

The exact eight connected release gates remain **BLOCKED**; no connected verification was performed.

| # | Connected gate | Status | Required closure evidence / demo relationship |
|---:|---|---|---|
| 1 | Connected multi-clinician authorization | **BLOCKED** | Approved replica-set database/identities, mismatched role/owner, transaction/race/rollback evidence. Narrow role smoke is mandatory but mutations remain excluded. |
| 2 | MongoDB query plans and realistic scale | **BLOCKED** | Representative data, explain plans, offsets, latency/concurrency/BSON/pool evidence. It may be excluded from demo only with no performance claim. |
| 3 | Actual database index verification | **BLOCKED** | Approved catalog, uniqueness/preflight, and plan-use evidence. Preparation/runtime separation still requires approved evidence. |
| 4 | Socket-capable ClamAV protocol/scanning | **BLOCKED** | Approved daemon/config plus clean, malicious, error, and timeout evidence. Irrelevant to v1 only while every file/PDF route stays denied. |
| 5 | Private storage integration/access | **BLOCKED** | Approved roots/permissions/promotion/cleanup/traversal/authorization evidence. Irrelevant to v1 only while every file route stays denied. |
| 6 | Browser end-to-end journeys | **BLOCKED** | Approved environment/browser/data plus session, role, CSRF, account-switch, and recovery evidence. A narrow smoke does not close the full gate. |
| 7 | Production proxy/TLS/cookie/cache | **BLOCKED** | Production-like ingress/TLS/Host/forwarding/CORS/cookie/cache/body/docs/webhook evidence. A loopback demo cannot close this gate. |
| 8 | Backup and restore | **BLOCKED** | Approved backup artifact, isolated restore, validation, RPO/RTO, and cleanup evidence. A disposable fictional-demo waiver requires approval 11. |

## 19. Outstanding limitations

- Every security correction exists only in documentation; current runtime behavior is unchanged.
- Current app construction still uses mutable/global settings across consumers.
- Trusted Host enforcement, immutable route gating, narrow demo CORS, typed demo auth/me, tagged identities, and dedicated demo endpoints do not exist.
- Beanie/index behavior is unverified; no safe no-DDL runtime initialization has been demonstrated.
- The effective frontend build/static server/Host/HMR design has no implementation or test evidence.
- The proposed 12 demo-data routes and their schemas/projections remain absent.
- Exact final Pydantic field types and repository query behavior require implementation-time source verification.
- Database privilege feasibility, dedicated listener/process identity, and operational isolation are unverified.
- Clinic choices for receptionist scope, availability, fictional fields, environment, operators, viewers, credentials, and lifecycle remain pending.
- No test in the 18-test matrix was added or run in this phase; no prior test result is re-claimed.
- No source/dependency/build/browser/connected audit was performed beyond safe inspection needed for this specification revision.
- Phase 24A.18 and Phase 24A.19 remain historical evidence and were not edited.

These limitations prevent any claim of production readiness, operational readiness, or demo authorization.

## 20. Recommended next milestone and final status

The next milestone should be an **independent Phase 24A.20 documentation and architecture review**. It should verify the 12 finding dispositions, effective 18-entry v1 table, typed auth/me contract, exact middleware/Host/CORS policy, and the preparation/runtime database split. It must remain read-only unless the user later supplies separate implementation authorization.

If that review accepts the revision, a separately authorized implementation milestone may begin steps 2–7 only and must stop for another independent boundary review. It must not proceed directly to frontend, launcher, account/data preparation, service startup, browser work, controlled demonstration, connected verification, or Phase 24B.

| Decision item | Final Phase 24A.20 status |
|---|---|
| Specification revision completeness | **COMPLETE FOR INDEPENDENT REVIEW** |
| Phase 24A.19 Medium findings | **7/7 RESOLVED IN SPECIFICATION; NOT IMPLEMENTED** |
| Low findings | **3/3 RESOLVED IN SPECIFICATION; NOT IMPLEMENTED** |
| Informational findings | **A19-I01 NOT APPLICABLE WITH EVIDENCE; A19-I02 RESOLVED IN SPECIFICATION** |
| Allowlist reconciliation | **COMPLETE: 19/19; 6 existing + 13 proposed; effective v1 = 18** |
| Adversarial test reconciliation | **COMPLETE: original 14 + 4 justified additions; NOT IMPLEMENTED / NOT RUN** |
| Technical implementation readiness | **APPROVED WITH CONDITIONS** |
| Implementation authorization | **NOT AUTHORIZED** |
| Demo-mode implementation | **NOT STARTED** |
| Launcher/accounts/fixtures | **NOT AUTHORIZED / NOT STARTED** |
| Clinic approvals | **11/11 PENDING** |
| Connected gates | **8/8 BLOCKED** |
| Actual controlled local demo | **NO-GO** |
| Connected client demo | **NO-GO** |
| Phase 24B | **BLOCKED / NOT STARTED** |

Stop after Phase 24A.20 and await independent review.
