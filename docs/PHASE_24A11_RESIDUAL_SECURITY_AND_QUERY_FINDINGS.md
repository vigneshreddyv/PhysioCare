# Phase 24A.11 residual security and query findings

Assessment date: 2026-11-02  
Assessed branch/HEAD: `codex/physiocare-integration-2026-10-31` / `5eaced696a156ca74233fd04252fea52345d8af8`

## Finding register

| ID | Category | State | Short title | Blocks |
|---|---|---|---|---|
| A11-M01 | Medium | Confirmed | Patient payment history is unbounded and N+1 | affected workflow offline closure; Phase 24B |
| A11-M02 | Medium | Confirmed | Demo-entitlement omitted-search fallback is unbounded and N+1 | affected admin API; Phase 24B |
| A11-M03 | Medium | Confirmed | Staff directory is unbounded | affected admin API; Phase 24B |
| A11-M04 | Medium | Confirmed | Fourteen registered list operations retain bounded N+1 formatters | query remediation; Phase 24B |
| A11-M05 | Medium | Confirmed app gap / infrastructure unknown | Public payment webhook buffers an uncapped body before authentication | staging/production; Phase 24B |
| A11-M06 | Medium | Confirmed | Persistent JSON models lack practical payload/list/string ceilings | affected mutations; Phase 24B |
| A11-M07 | Medium | Confirmed | Active admin patient-create screen calls an unregistered API route | demo/workflow approval; Phase 24B |
| A11-M08 | Medium | Confirmed pattern / race outcome not connected-tested | Clinical read-modify-save and multi-write flows can lose updates or leave partial side effects | connected integrity gate; Phase 24B |
| A11-L01 | Low | Confirmed | Active legacy laboratory catalogue is unbounded | affected legacy API |
| A11-L02 | Low | Confirmed | Legacy laboratory booking responses expose provider identifiers unnecessarily | privacy hardening before production |
| A11-L03 | Low | Confirmed application default / deployment unknown | OpenAPI and interactive documentation are public by default | production configuration review |
| A11-I01 | Informational | Confirmed | Unbounded compatibility helpers remain but are not registered-path reachable | maintenance only |
| A11-I02 | Informational | Confirmed | Two dormant frontend components reference a nonexistent address route | maintenance only |
| A11-I03 | Informational | Confirmed intentional behavior | Health endpoint exposes demo database name only in isolated demo modes | none; retain deployment review |
| A11-E01 | Environment verification required | Not verified offline | Indexes, execution plans, scale, proxy and connected security gates | all connected release gates |
| A11-P01 | Policy decision required | Unresolved | Password, verification, recovery, and staff-onboarding policy | client demo, staging, production |

Severity totals are **Critical 0, High 0, Medium 8, Low 3, Informational 3**. Environment and policy entries are tracked separately and are not folded into the security-severity totals.

## A11-M01 — Patient payment history is unbounded and N+1

- **Affected endpoint:** `GET /api/payments/history`.
- **File/function:** `backend/app/api/payments.py:21-25`, `PaymentService.get_patient_payment_history` at `backend/app/services/payment_service.py:603-627`.
- **Exact evidence:** the patient filter is correct, but `.sort("-created_at").to_list()` at lines 608-610 has no limit. Lines 612-613 then call `Appointment.get` once per payment attempt.
- **Path:** authenticated patient -> own patient profile -> all `payment_attempts` for that patient -> one `appointments` lookup per attempt -> safe response model.
- **Impact:** response size, memory, latency, and database-call count grow with the patient's lifetime payment-attempt history. Repeated failed/abandoned checkout attempts make this growth realistic.
- **Exploitability/operational consequence:** a patient can repeatedly call the endpoint against their own growing history; there is no cross-patient disclosure, but the path can consume disproportionate application/database resources.
- **Classification:** confirmed unbounded retrieval and confirmed N+1; no authorization defect.
- **Recommended remediation:** add the common bounded page contract and stable `created_at/_id` sort; fetch appointment fields with a bounded `$lookup`, batched `$in` query, or denormalized immutable payment-history snapshot.
- **Required tests:** default/max/invalid pages, stable ties, >1,000-history navigation, constant query count for 1 and 100 rows, OWN isolation, and frontend page replacement.
- **Blocking:** blocks closure of the affected workflow and Phase 24B consideration. It does not by itself prove a production compromise.

## A11-M02 — Demo-entitlement omitted-search fallback is unbounded and N+1

- **Affected endpoint:** `GET /api/demo-services/entitlements` when `search` is omitted.
- **File/function:** branch at `backend/app/api/home_visits.py:45-53`; `HomeVisitService.list_admin_entitlements` at `backend/app/services/home_visit_service.py:95-112`; `ProfileRepository.list_patients` at `backend/app/repositories/profile_repository.py:145-146`.
- **Exact evidence:** the bounded aggregation is used only when `search is not None`. The fallback materializes all patients, then performs one user and one entitlement lookup per patient at service lines 99-103.
- **Path:** admin -> optional query branch -> all patients -> per-patient user and entitlement -> contact/entitlement response.
- **Impact:** full patient contact directory materialization and 1+2N database-call growth.
- **Exploitability/operational consequence:** admin-only, so the attack surface is restricted, but a direct or buggy admin client can trigger a high-cost path. The current `DemoServices` screen always sends a search parameter and is bounded; that frontend behavior does not protect the API.
- **Classification:** confirmed unbounded/N+1 endpoint path; server role check remains correct.
- **Recommended remediation:** remove the fallback and always call the paginated aggregation, treating missing search as an empty search string.
- **Required tests:** omitted, empty, whitespace, and populated search all use one bounded aggregation; max page rules; contact projection; current screen contract.
- **Blocking:** blocks the affected admin API and Phase 24B consideration.

## A11-M03 — Staff directory is unbounded

- **Affected endpoint:** `GET /api/users/staff`.
- **File/function:** `backend/app/api/users.py:60-64`, `UserService.list_staff` at `backend/app/services/user_service.py:97-109`, `UserRepository.list_staff` at `backend/app/repositories/user_repository.py:42-44`.
- **Exact evidence:** all staff roles are sorted then consumed with `.to_list()` without a limit; there is no query parameter or enforced business cap.
- **Path:** admin -> all matching `users` -> `StaffOut` names/emails/roles/status.
- **Impact:** unbounded response/memory growth and retention of the whole staff directory in the active Staff Management screen.
- **Exploitability/operational consequence:** admin-only and likely small at present, but the bound is an undocumented assumption rather than an invariant.
- **Classification:** confirmed unbounded retrieval; no N+1 and no role defect.
- **Recommended remediation:** add bounded server-side page/search/role/status filters and make the frontend replace pages.
- **Required tests:** default/max pages, stable ordering, escaped search, combined filters, >1,000-record navigation, role enforcement, and current edit-snapshot behavior.
- **Blocking:** blocks closure of this admin query path and Phase 24B consideration.

## A11-M04 — Fourteen registered list operations retain bounded N+1 formatters

- **Affected operations:**
  - `GET /api/appointments` for admin/patient, `/api/appointments/admin/billing`, `/api/appointments/me/home-visits`, `/api/appointments/me/history`;
  - `GET /api/users/reception/patients` and `/api/users/patients` without search;
  - `GET /api/home-visit-requests/me`, `/admin`, and `/doctor`;
  - `GET /api/lab-requests/me`, `/admin`, and `/laboratory/assigned`;
  - `GET /api/payments/history` and the omitted-search demo-entitlement path are also N+1 but are separately recorded because they are additionally unbounded.
- **File/functions and evidence:**
  - appointment page retrieval returns a page, then `AppointmentService.list_appointments`, `list_admin_billing`, `list_patient_home_visits`, or `list_patient_appointment_history` calls `_format_appointment` per row (`backend/app/services/appointment_service.py:272-387`); `_format_appointment` performs patient, doctor, and two user lookups when maps are not supplied (`:693-708`);
  - `UserService.list_patients`, `list_reception_patients`, and `list_assigned_patients` perform per-row user or patient+user lookups (`backend/app/services/user_service.py:207-248`, `:354-391`);
  - home-visit list loops call `_format_full`/`_format_doctor`, which call `_related` and four related lookups (`backend/app/services/home_visit_service.py:438-497`, `:561-620`);
  - lab-request list loops call `_format` or `_format_for_laboratorian`, which perform patient/user and optional assignee lookups (`backend/app/services/lab_request_service.py:69-119`, `:335-376`).
- **Path:** the initial collection read is correctly DB-filtered and bounded to at most 100; result formatting then performs database calls proportional to row count. Doctor appointment lists, reception appointment lists, admin patient history, doctor history, reception home-visit lists, and doctor lab-report lists already demonstrate batched alternatives.
- **Impact:** a nominal 100-row page can cause hundreds of sequential database calls. This raises latency, pool pressure, timeout risk, and noisy-neighbor impact despite correct pagination.
- **Exploitability/operational consequence:** callers need the appropriate authenticated role and scope. This is a reliability/scalability defect, not a demonstrated data-isolation failure.
- **Classification:** confirmed bounded N+1. It must not be mislabeled as unbounded retrieval.
- **Recommended remediation:** use aggregation projections or one bounded `$in` query per related collection; reuse page-level identity maps; keep role-specific minimum projections.
- **Required tests:** query-call count constant at page sizes 1 and 100, missing-related-record handling, exact role projections, OWN/ASSIGNED scope, stable page output, and no reintroduction of clinical/billing fields into receptionist schemas.
- **Blocking:** blocks residual query closure and Phase 24B consideration; representative-scale latency remains a connected test.

## A11-M05 — Public webhook buffers an uncapped body before authentication

- **Affected endpoint:** `POST /api/webhooks/razorpay`.
- **File/function:** `backend/app/api/payments.py:90-97`; signature verification begins only in `PaymentService.handle_webhook` at `backend/app/services/payment_service.py:657-675`.
- **Exact evidence:** `raw_body = await request.body()` buffers the entire request before checking for required headers or verifying HMAC. No application-wide request-size middleware or webhook-specific content-length/stream cap exists in `backend/app/main.py`.
- **Path:** unauthenticated network caller -> full body buffering -> test-mode configuration check/header check -> signature verification -> JSON parse -> event deduplication and provider verification.
- **Impact:** memory and worker time can be consumed by invalid unsigned requests before the trust boundary is evaluated.
- **Exploitability/operational consequence:** remotely reachable if the webhook is exposed. A reverse proxy may impose a cap, but no such deployed control is verifiable offline.
- **Classification:** confirmed missing application-level limit; actual externally exploitable maximum is environment verification required.
- **Recommended remediation:** enforce a small webhook-specific byte limit while streaming or via trusted ingress plus an application fail-safe; reject missing/oversized content before buffering and signature work.
- **Required tests:** absent/invalid/negative/oversized content length, chunked body crossing the cap, exact-limit valid signed body, signature-before-JSON semantics, duplicate event behavior, and proxy/application cap agreement.
- **Blocking:** blocks staging/production webhook approval and Phase 24B consideration. Payments remain Test Mode only; no provider was contacted.

## A11-M06 — Persistent JSON models lack practical payload/list/string ceilings

- **Affected endpoints (representative, not exhaustive):** public `/api/auth/register` and `/login`; appointment creation; legacy laboratory booking creation; care-plan create/update; exercise assignment/progress mutations.
- **File/functions:** `backend/app/schemas/auth.py:9-18`, `backend/app/schemas/appointment.py:9-14`, `backend/app/schemas/laboratory_booking.py:14-23`, `backend/app/schemas/care_plan.py:6-73`, `backend/app/schemas/exercise.py:24-53` and `:89-130`.
- **Exact evidence:** examples include registration/password/name strings with minimum but no maximum, appointment `reason` with no maximum, laboratory `test_ids` with no maximum item count or item length, and care-plan stages/goals/recommendations and nested text/list fields without maximums. `backend/app/main.py` has no general JSON body cap. In contrast, lab requests and clinician schedules demonstrate explicit safe maxima.
- **Path:** role-appropriate caller (public for auth; patient/clinician/admin for others) -> Pydantic parses potentially large structures -> services may hash, loop, query `$in`, embed, persist, or return them.
- **Impact:** avoidable CPU/memory/database-document growth, oversized embedded documents, expensive validation/hash work, and late MongoDB document-size failures.
- **Exploitability/operational consequence:** authentication rate limiting narrows repeated public auth abuse, and infrastructure may cap bodies; neither establishes per-field or persistent-document invariants.
- **Classification:** confirmed application-control gap; maximum accepted network size is environment-dependent.
- **Recommended remediation:** define a global defensive JSON cap and schema-specific maximum strings/list counts/numeric ranges based on clinic policy and MongoDB document design; forbid unexpected fields on mutation schemas.
- **Required tests:** exact-limit/over-limit bodies and every persisted list/string, duplicate/oversized lab IDs, large nested care plans, large auth credentials without secret echo, and 413/422 consistency.
- **Blocking:** blocks affected mutation closure and Phase 24B consideration. Exact clinical content limits require a clinic policy decision.

## A11-M07 — Active admin patient-create screen calls an unregistered route

- **Affected frontend/backend contract:** admin route `/admin/patients-create` -> `POST /api/users/patients`.
- **File/function:** `frontend/src/App.jsx:237`; `frontend/src/pages/admin/PatientsCreate.jsx:30`. `backend/app/api/users.py` has no POST `/patients` handler, and all 13 registered API routers were inspected.
- **Exact evidence:** the active screen submits a payload to an operation absent from the 119-route inventory.
- **Path:** authenticated admin UI -> Axios POST -> FastAPI 404/405 -> no patient created.
- **Impact:** a visible admin workflow cannot complete and may mislead demo/clinic users. It also creates uncertainty about the intended secure staff-vs-patient onboarding policy.
- **Exploitability/operational consequence:** this is not an authorization bypass; it is confirmed frontend/backend drift and a release-readiness defect.
- **Classification:** confirmed.
- **Recommended remediation:** first make the patient onboarding policy decision. Then either remove/hide the unsupported route or implement an admin-only transactional endpoint with explicit response minimization, enumeration behavior, password/onboarding rules, and audit semantics.
- **Required tests:** route existence or deliberate absence, admin-only access, transaction rollback, duplicate email behavior, no password echo, frontend success/error states, and navigation truthfulness.
- **Blocking:** blocks demo approval for that screen and Phase 24B consideration.

## A11-M08 — Clinical read-modify-save and multi-write flows lack a common atomicity boundary

- **Affected endpoints:** care-plan create/update/stage/goal mutations, exercise-assignment update, exercise-progress creation, and the general appointment PATCH path; optional saved-address follow-up after home-visit creation is another partial-write example.
- **File/functions and exact evidence:**
  - care-plan status history/notification can be inserted/sent before `await care_plan.save()` (`backend/app/services/care_plan_service.py:174-230`, save at `:269`); stage and goal updates use unversioned embedded read-modify-save (`:273-322`, `:353-391`);
  - exercise assignment updates load then save without a revision predicate (`backend/app/services/exercise_service.py:152-215`); progress is inserted before subsequent assignment status saves (`:219-265`);
  - general appointment fields are mutated then `appointment.save()` without an expected version (`backend/app/services/appointment_service.py:497-536`), although booking uniqueness and cancellation paths have stronger atomic controls.
- **Path:** authorized actor -> read current document -> validate -> one or more side-effect writes -> unversioned save.
- **Impact:** concurrent authorized actions can overwrite newer embedded state, and a later failure can leave a history/notification/progress side effect without the corresponding primary state change (or vice versa).
- **Exploitability/operational consequence:** requires concurrent legitimate or automated actions/failure timing; no connected race was executed. It is a clinical integrity and recovery risk rather than an unauthenticated attack.
- **Classification:** confirmed non-atomic pattern; actual race frequency and transaction availability require connected verification.
- **Recommended remediation:** define expected revisions/conditional update filters for mutable clinical documents; place primary record and audit writes in approved MongoDB transactions where atomicity is required; use an outbox/idempotent follow-up for notifications; return conflict on stale revision.
- **Required tests:** two-writer stale revision, failure between each write, retry/idempotency, no false audit/notification, assignment status/progress consistency, and replica-set transaction integration.
- **Blocking:** blocks the connected clinical-integrity gate and Phase 24B consideration.

## Low findings

### A11-L01 — Active legacy laboratory catalogue is unbounded

`GET /api/laboratory/tests` calls `LaboratoryTestRepository.get_active_tests`, whose `.to_list()` is unbounded (`backend/app/api/laboratory.py:20-37`; `backend/app/repositories/laboratory_test_repository.py:7-10`). The endpoint is patient-only and the catalogue is expected to be small, so impact is limited, but no enforced cap makes that an assumption. Add a hard catalogue maximum or pagination, stable sort, and an exact projection. Test over-cap behavior and active-only filtering. This blocks only the affected legacy API, not offline source review.

### A11-L02 — Legacy laboratory booking responses expose provider identifiers unnecessarily

`LaboratoryBookingResponse` includes `payment_id` and `payment_order_id` (`backend/app/schemas/laboratory_booking.py:26-41`), and handlers serialize them at `backend/app/api/laboratory.py:73-95`, `:119-142`, `:170-192`, and the status response. Access is patient-owner or authorized admin/assigned doctor, so this is not cross-user leakage and provider IDs are not payment secrets by themselves. The client-supplied legacy payment mutation is disabled with 410, making these fields unnecessary for normal clients. Remove them from patient/general schemas unless a documented support need exists; test response exclusion.

### A11-L03 — OpenAPI and interactive documentation are public by default

`FastAPI(...)` at `backend/app/main.py:61-65` does not disable or protect the default `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, or `/redoc` routes. This exposes route/schema intelligence, not patient data or credentials. Decide per environment whether documentation is intended; disable or authenticate it in production and test production settings. Deployed ingress behavior is not verified.

## Informational findings

### A11-I01 — Dormant compatibility helpers

Unbounded optional `page=None` branches remain in appointment, care-plan, exercise, lab-request, report, notification, and demo repositories/services. Registered list handlers were traced and now pass `PageWindow` except for A11-M01/M02/M03 and A11-L01. Treat these helpers as refactor debt; do not call them endpoint vulnerabilities without a reachable path. Add call-graph/static contract tests if they must remain.

### A11-I02 — Dormant frontend address calls

`HomeVisitLab.jsx:31` and `LaboratoryReview.jsx:25` request nonexistent `/users/me/address`, but neither component is imported/routed by current `App.jsx`. Remove or clearly archive them during a separately authorized cleanup; no current user path is broken by these calls.

### A11-I03 — Demo-only health metadata

`GET /health` returns `DATABASE_NAME` only when `HOME_VISIT_DEMO_MODE` or `LAB_DEMO_MODE` is true (`backend/app/main.py:160-172`). Both demo modes have strict loopback/dedicated-database startup guards. Production returns `null`. This is intentional demo observability; confirm deployed health exposure during the proxy gate.

## Environment verification required — A11-E01

Offline source and mocks cannot establish deployed index presence, query plans, `$lookup` memory/latency, large-offset performance, concurrent offset drift, replica-set transactions, distributed rate limits, real ClamAV behavior, private mount permissions, proxy request limits/security headers/TLS, real provider webhook behavior, backup/restore, or connected cross-role negative authorization. The eight connected release gates remain **BLOCKED**. Required evidence must use approved isolated fictional data and must not be inferred from these documents.

## Policy decision required — A11-P01

The Phase 24A.8 policy package remains unresolved: public password policy (currently six characters minimum), email verification, account recovery, and staff/patient onboarding are not authorized business/security decisions. A11-M06 and A11-M07 depend partly on those decisions. Do not silently strengthen, weaken, or invent clinic policy.

## Verified strengths and cleared concerns

- No confirmed Critical/High IDOR, cross-patient, cross-clinician, role-escalation, password-hash, session-token, or secret response exposure was found.
- Inactive accounts are rejected; unknown/wrong/inactive login responses are generic; registration is enumeration-neutral; refresh rotation/reuse detection and live-session binding remain intact.
- Authenticated unsafe operations use CSRF, and authenticated/private PDF responses retain private/no-store handling.
- Patient PDF ownership, doctor assignment, laboratorian assignment, released/draft hiding, basename isolation, separate quarantine/storage, streamed size checks, PDF structure checks, scanner fail-closed behavior, atomic promotion, and cleanup paths remain present.
- Clinical list pagination defaults to 50 and enforces max 100/max page 1,000 with database-side filter/sort/skip/limit on the reviewed paths. Search regex terms are escaped and limited to 100 characters on the active directory/report/catalog searches.
- Admin clinician directory and HomeVisitRequests no-preference availability retain their bounded aggregation/streaming remediations. Dashboard and exercise statistics remain database aggregations rather than lifetime document materializations.
- Appointment and home-visit booking retain server schedule validation, read conflict detection, and the unique active slot claim as the final concurrent authority. Lab-request creation retains its stable idempotency-key path.
- Reception schemas exclude clinical reason/symptoms and billing details. Laboratorian output contains the collection information needed for assigned work but not email, diagnosis, unrelated records, or payment data.
- No passwords, hashes, JWT secrets, refresh tokens, webhook secrets, or raw payment credentials are returned by response schemas or deliberately logged on the reviewed paths.

## Prioritized remediation order

1. Decide password/verification/recovery/onboarding policy (A11-P01), because it controls the legitimate patient-creation contract.
2. Bound and batch A11-M01/M02/M03/M04 and A11-L01, preserving minimum role projections.
3. Add webhook/global/schema request limits for A11-M05/M06 and align them with the approved ingress policy.
4. Resolve the active patient-create contract (A11-M07).
5. Introduce revision/transaction/outbox semantics and failure-injection tests for A11-M08.
6. Minimize legacy payment identifiers and decide production docs exposure (A11-L02/L03).
7. Execute A11-E01 only in separately approved isolated connected environments.

No remediation is authorized or implemented by this audit.
