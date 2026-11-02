# Phase 24A.12 Group C — N+1 Clinical-List Query Remediation Report

Assessment date: 2026-11-02  
Branch: `codex/physiocare-integration-2026-10-31`  
Baseline and final HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`  
Final status: **PASS WITH CONDITIONS**

## 1. Executive summary

All 14 registered operations identified by the Phase 24A.11 finding register were traced from route through service, repository, formatter, response model, and frontend consumer. Twelve bounded N+1 paths were remediated in Group C. The two dual-classified unbounded/N+1 paths had already been remediated in Group A and were reverified without rework.

For page sizes 1, 10, 50, and 100, mocked related-query counts are now constant rather than proportional to the returned row count. Main list filtering, stable sorting, skip/limit pagination, patient ownership, clinician assignment, receptionist coordination scope, laboratory assignment, and response schemas remain server-controlled. No frontend contract change was required.

The offline implementation is complete: **14 assessed, 14 confirmed historically, 12 resolved in Group C, 2 verified as already resolved in Group A, 0 confirmed N+1 paths remaining in this inventory**. The status is PASS WITH CONDITIONS because real MongoDB execution plans, deployed index state, cursor behavior, representative-scale latency, and all eight connected release gates remain unverified. This is not production-readiness or deployment authorization.

## 2. Initial repository state

Before Group C changes, the independently recalculated state exactly matched the Group B handoff:

- branch `codex/physiocare-integration-2026-10-31`;
- HEAD `5eaced696a156ca74233fd04252fea52345d8af8`;
- upstream `origin/codex/physiocare-integration-2026-10-31`, 0 ahead / 0 behind;
- 101 tracked modified paths;
- 82 untracked paths;
- 183 total dirty paths.

The pre-existing worktree was preserved. Group A included the bounded payment-history aggregation, bounded demo-entitlement aggregation, their API/service wiring, focused tests, and its report. Group B included bounded webhook-body handling, schema/text limits, request-limit tests, frontend validation parity, and its report. Group C did not revert, overwrite, commit, stash, clean, reset, switch, or push any of that work.

## 3. Exact 14-operation inventory

The Phase 24A.11 inventory and finding register were the source of truth.

| # | Finding | Operation and scope | Handler → service | Historical per-row work | Frontend consumer | Disposition |
|---:|---|---|---|---|---|---|
| 1 | A11-M04 | `GET /api/appointments`, admin/patient variants | `list_appointments` → `AppointmentService.list_appointments` | patient, doctor, patient-user, doctor-user | AdminDashboard, DoctorDashboard | Group C fixed; doctor variant was already batched |
| 2 | A11-M04 | `GET /api/appointments/admin/billing`, admin | `list_admin_billing` → same service method | four identity lookups | Billing | Group C fixed |
| 3 | A11-M04 | `GET /api/appointments/me/home-visits`, patient OWN | `list_patient_home_visits` → same service method | four identity lookups | HomeVisitRequests | Group C fixed |
| 4 | A11-M04 | `GET /api/appointments/me/history`, patient OWN | `list_patient_appointment_history` → same service method | four identity lookups | dashboard/history/appointments | Group C fixed |
| 5 | A11-M04 | `GET /api/users/reception/patients`, no search | `list_reception_patients` → `UserService.search_patients` | one user lookup per patient | PatientsList/selectors | Group C fixed |
| 6 | A11-M04 | `GET /api/users/patients`, no search; admin or assigned doctor | `list_patients` → `UserService.search_patients` | admin: user per patient; doctor: patient and user per assigned ID | PatientsList/selectors | Group C fixed |
| 7 | A11-M04 | `GET /api/home-visit-requests/me`, patient OWN | `list_own_home_visit_requests` → `HomeVisitService.list_patient_requests` | patient, doctor, and two users | dashboard/HomeVisitRequests | Group C fixed |
| 8 | A11-M04 | `GET /api/home-visit-requests/admin`, admin | `list_admin_home_visit_requests` → `HomeVisitService.list_admin_requests` | patient, doctor, and two users | DemoServices | Group C fixed |
| 9 | A11-M04 | `GET /api/home-visit-requests/doctor`, assigned preferred doctor | `list_doctor_home_visit_requests` → `HomeVisitService.list_doctor_requests` | patient, doctor, and two users | HomeVisits | Group C fixed |
| 10 | A11-M04 | `GET /api/lab-requests/me`, patient OWN | `list_own` → `LabRequestService.list_own` | patient, user, optional assignee | dashboard/LaboratoryRequests | Group C fixed |
| 11 | A11-M04 | `GET /api/lab-requests/admin`, admin | `list_admin` → `LabRequestService.list_admin` | patient, user, optional assignee | AdminLabRequestsPanel | Group C fixed |
| 12 | A11-M04 | `GET /api/lab-requests/laboratory/assigned`, LAB-ASSIGNED | `list_assigned_orders` → `LabRequestService.list_assigned` | patient and user | LaboratoryDashboard | Group C fixed |
| 13 | A11-M01 and A11-M04 | `GET /api/payments/history`, patient OWN | `list_patient_payment_history` → `PaymentService.get_patient_payment_history` | appointment per payment | PatientPaymentHistory | Already fixed in Group A; reverified |
| 14 | A11-M02 and A11-M04 | `GET /api/demo-services/entitlements` with omitted search, admin | `list_demo_entitlements` → `HomeVisitService.search_admin_entitlements` | patient/entitlement lookups per user | DemoServices | Already fixed in Group A; reverified |

All 14 were confirmed historical N+1 paths. Operations 1–12 were bounded formatting N+1 defects, not unbounded retrieval. Operations 13–14 were separately recorded by A11-M01/M02 because they were both unbounded and N+1. No additional operation was invented or pulled into scope.

## 4. Batch grouping and rationale

1. **Appointments (four operations):** one shared appointment formatter and identity graph.
2. **Patient directories (two operations):** one existing aggregation, with role-specific projections and clinician assignment inside MongoDB.
3. **Home-visit requests (three operations):** one request model; full patient/admin views share four identity sets while the doctor view needs only patient identity.
4. **Laboratory requests (three operations):** one request model; patient/admin responses need patient and assignee identities while laboratory responses need patient collection details only.
5. **Group A verification (two operations):** read-only assessment of already-bounded aggregations; no duplicate implementation.

Each implementation batch was syntax-checked and exercised with focused/neighboring tests before the next batch. No Critical or High issue appeared.

## 5. Original and replacement query architecture

The original page queries were bounded, but their formatters called profile/user repositories once or several times per row. At the maximum page size of 100, the four-identity formatters could perform 400 sequential related lookups after the main query.

The replacement architecture is:

- retain the authorized, filtered, sorted main page query;
- derive unique related IDs only from that bounded page;
- execute one `$in` query per required profile/identity collection;
- use narrow role-specific projections;
- map rows in memory and pass resolved objects to the existing typed formatter;
- fail closed with the existing 404 behavior if a required related identity is absent;
- retain the old per-record fallback only for unpaged/single-record compatibility paths not registered as these page operations.

Patient-directory omitted-search requests now take the same one-aggregation path as searched requests. For doctors, the appointment-assignment `$lookup` and assignment existence match occur before sort/skip/limit. Group A payment history and demo entitlements remain one bounded aggregation each.

## 6. Changes by batch

### Batch 1 — appointments

`AppointmentService._page_profile_maps` now takes page-bounded unique IDs, projects only profile user IDs by default, and separates patient-user and doctor-user projections so doctor email is not fetched. `_format_appointment_page` supplies all four identities to the existing formatter. Admin/patient appointment lists, billing, home visits, and patient history use that page formatter. Reception scheduling explicitly requests its permitted patient phone/email fields; its response schema is unchanged.

### Batch 2 — patient directories

Both handlers always call `UserService.search_patients`, including omitted or empty search. `ProfileRepository.search_patients` now accepts `admin`, `doctor`, or `reception` view intent:

- admin: name, email, phone, date of birth, recorded gender, subscription status;
- doctor: assigned patients only; name, phone, date of birth, recorded gender; no email/subscription status;
- reception: active patients; name, email, phone; no demographics/subscription status.

Password hashes, session/token data, demo tags, and unrelated profile fields are not projected.

### Batch 3 — home-visit requests

Patient/admin pages reuse bounded four-identity maps. Doctor pages use a dedicated two-query patient map and do not refetch the already-authorized doctor. Main request page queries now project only response fields and exclude review actor metadata. Patient ownership remains derived from the authenticated user before the patient-scoped repository query. Doctor assignment remains in the repository predicate before pagination.

### Batch 4 — laboratory requests

Patient/admin pages use bounded patient-profile, patient-user, and optional assignee-user sets. Assigned laboratory pages use only patient-profile and patient-user sets and do not retrieve patient email. Main page projections exclude submission keys, demo tags, review actors, assignment history, storage keys, upload actors, publication actors, and publication history. Patient ownership and laboratorian assignment remain in the main query.

### Group A paths

Payment history remains a patient-scoped aggregation with sorting, skip/limit before the bounded appointment lookup and a narrow billing projection. Omitted-search demo entitlements remain a role-filtered, paged aggregation with patient and entitlement lookups and a narrow contact/entitlement projection.

## 7. Before-and-after query complexity

`N` is returned page rows and `A` is the number of rows having an assignee. “Before” is a source-derived count from the historical call graph; “after” is supported by mocked call-count/query-shape tests. Authentication middleware queries are outside these service counts. Independent owner/doctor-profile lookups are shown where the service performs them.

| Operation | Before | After | At N=100 after |
|---|---:|---:|---:|
| appointments, admin | `1 + 4N` | 1 main + 4 bulk = **5** | 5 |
| appointments, patient | 1 owner + `1 + 4N` | 1 owner + 1 main + 4 bulk = **6** | 6 |
| admin billing | `1 + 4N` | **5** | 5 |
| patient appointment home visits | 1 owner + `1 + 4N` | **6** | 6 |
| patient appointment history | 1 owner + `1 + 4N` | **6** | 6 |
| reception patient directory | `1 + N` | one aggregation = **1** | 1 |
| admin patient directory | `1 + N` | one aggregation = **1** | 1 |
| doctor assigned-patient directory | 1 doctor + 1 assigned-ID page + `2N` | 1 doctor + one scoped aggregation = **2** | 2 |
| home requests, patient | 1 owner + `1 + 4N` | 1 owner + 1 main + 4 bulk = **6** | 6 |
| home requests, admin | `1 + 4N` | **5** | 5 |
| home requests, doctor | 1 doctor + `1 + 4N` | 1 doctor + 1 main + 2 bulk = **4** | 4 |
| lab requests, patient | 1 owner + 1 main + `2N + A` | 1 owner + 1 main + 3 bulk = **5** | 5 |
| lab requests, admin | 1 main + `2N + A` | 1 main + 3 bulk = **4** | 4 |
| lab assigned queue | 1 main + `2N` | 1 main + 2 bulk = **3** | 3 |
| payment history (Group A) | 1 owner + 1 unbounded main + `N` appointments | 1 owner + one bounded aggregation = **2** | 2 |
| demo entitlements omitted search (Group A) | 1 unbounded main + per-row related work | one bounded aggregation = **1** | 1 |

The first row covers one registered route with two role variants, so the table presents 16 role/query shapes for the 14 registered operations. These counts do not claim MongoDB latency, query-plan quality, network timing, or production-scale throughput.

## 8. Pagination and memory safety

- Default and maximum page constraints remain supplied by `PageWindow`; maximum page size remains 100.
- Main ownership, assignment, status, date, and search predicates execute before pagination.
- Stable sorts retain their existing field plus `_id` tie-breaker.
- Every `$in` list is derived only from unique IDs on the current page and is therefore bounded by 100 profile IDs per role set.
- Raw page cursors call `skip`, `limit`, and `to_list(length=page.size)`.
- No full-collection retrieval or arbitrary truncation was introduced.
- Frontend page replacement, request sharing, stale-session rejection, deduplication, and record-budget behavior remain unchanged and passed existing tests.

## 9. Authorization and ownership verification

### Patient ownership

Patient appointment, home-visit, laboratory, and payment services first resolve the patient profile from the authenticated user ID. The resulting server-side patient ID is used in the main repository filter. No frontend patient ID is trusted.

### Clinician assignment

Doctor appointment pages still filter by resolved doctor ID and reject pending assignment. Doctor patient-directory aggregation matches an appointment for the resolved doctor before pagination. Doctor home-visit pages filter `preferred_doctor_id` plus approved coordination status before identity loading. Bulk identity reads do not determine authorization and cannot add records to the authorized page.

### Administrator and receptionist

Admin route dependencies are unchanged. Receptionist patient results remain coordination-only. Reception appointment scheduling explicitly requests only the contact fields its existing response model uses; diagnosis, symptoms, notes, and billing fields were not added.

### Laboratory

The assigned queue remains filtered by authenticated `assigned_laboratorian_user_id` before paging. Its identity projection omits patient email and all storage/publication internals. Selected tests and collection location/contact fields remain available because the existing laboratory workflow requires them.

## 10. Sensitive-field projection review

New projections never request password hashes, tokens, session identifiers, payment/provider credentials, report storage keys, review actors, assignment histories, publication histories, or unrelated clinical data. Appointment pages require nearly the complete existing appointment response, but related identity reads default to names only. Patient email and phone are enabled only for existing role responses that already return them.

No generic database document is returned directly. Main page rows are converted to internal `SimpleNamespace` values and then to the existing Pydantic response types.

## 11. API and frontend compatibility

Field names, types, null/default behavior, empty arrays, dates, status values, sorting, pagination parameters, error responses, and typed response models were preserved. Missing required identities continue to produce a 404 rather than partially returning a row. Optional assignee absence still produces null assignee fields.

Every frontend consumer was traced. Existing React Query keys and `fetchClinicalPage` behavior already isolate filters/pages, cancel stale authenticated requests, share identical requests, and replace rather than accumulate pages. No API contract changed, so no frontend source edit was necessary.

## 12. Regression evidence

All backend commands used the existing locked Python 3.13 environment under `/private/tmp`, `env -i`, synthetic distinct secrets, `ENVIRONMENT=test`, an intentionally unreachable loopback MongoDB port, disabled payments/reconciliation/scanner startup, disabled plugin autoload, explicit `pytest_asyncio`, no pytest cache provider, and no connected opt-in.

| Verification | Fresh result |
|---|---:|
| New Group C query-count/projection file | **37 passed** |
| Group C + clinical pagination focused run | **257 passed** |
| API contract + pagination compatibility run | **329 passed** |
| Complete backend excluding only AF_UNIX scanner file | **1,064 passed, 3 connected-only skipped** |
| Literal complete backend | **1,065 passed, 11 AF_UNIX sandbox failures, 3 connected-only skipped** |
| Focused affected frontend | **56 passed** |
| Complete frontend | **161 passed** |
| Frontend lint | **PASS** |
| Vite production build | **PASS**, Vite 8.3.5, 1,838 modules |
| Asset budget | **74 JS/CSS assets**, zero violations |
| Python syntax | **169 files parsed**, zero failures |
| Dependency-lock tests | **2 passed** |
| `pip check` | **No broken requirements found** |
| Offline npm audit | **0 cached vulnerabilities found**; cache freshness unverified |
| Redacted Gitleaks current-tree scan | **6 existing synthetic fixture findings**, zero in Group C files |
| `git diff --check` | **PASS** |

The 11 literal-suite failures all occur before an application assertion when this sandbox rejects `asyncio.start_unix_server()` AF_UNIX bind with `PermissionError`. The scanner file was not edited, skipped, or weakened. The three skips are the guarded connected account-registration, distributed-rate-limit, and report-transaction tests. The recurring warning is the existing already-imported `pytest_asyncio` assertion-rewrite warning.

## 13. Query-count test coverage

The new tests instrument page identity methods at 1, 10, 50, and 100 rows and assert constant collection-call counts, bounded `to_list(length=...)`, exact role projections, and no sensitive keys. Separate tests cover:

- all four appointment page entry points using the bounded formatter;
- missing related appointment identity failing closed;
- doctor assignment lookup occurring before patient-directory skip/limit;
- patient-directory role projections;
- doctor home-visit identity minimization;
- patient/admin versus laboratory lab-request identity sets;
- main repository filters, stable sort, skip/limit, and projections;
- the two Group A operations remaining one bounded aggregation each.

Mocked counts prove application call complexity, not physical MongoDB performance.

## 14. Recommended but unverified indexes

No index was created or altered. The model source declares appointment slot/submission uniqueness, lab idempotency uniqueness, single-field status/report-status indexes, home-request status, and unique user email. The following compound/join indexes should be compared with the deployed catalog and explain plans in an approved connected environment:

| Collection | Candidate order | Reason / local status |
|---|---|---|
| appointments | `{patient_id:1, appointment_date:-1, _id:-1}` | patient pages/history; not declared locally |
| appointments | `{doctor_id:1, doctor_assignment_pending:1, appointment_date:-1, _id:-1}` | doctor assignment and agenda; not declared locally |
| appointments | `{billing_status:1, appointment_date:-1, _id:-1}` | admin billing filters/sort; not declared locally |
| appointments | `{doctor_id:1, patient_id:1, doctor_assignment_pending:1}` | assigned-patient existence lookup; not declared locally |
| patients | `{user_id:1}` (prefer unique if data permits) | user-to-profile join; not declared locally |
| doctors | `{user_id:1}` (prefer unique if data permits) | user-to-profile join; not declared locally |
| home_visit_requests | `{patient_id:1, created_at:-1, _id:-1}` and `{patient_id:1, updated_at:-1, _id:-1}` | owner pages and recent updates; not declared locally |
| home_visit_requests | `{preferred_doctor_id:1, status:1, created_at:-1, _id:-1}` | doctor coordination page; only status is declared locally |
| lab_requests | `{patient_id:1, created_at:-1, _id:-1}` and `{patient_id:1, updated_at:-1, _id:-1}` | patient pages/recent updates; not declared locally |
| lab_requests | `{assigned_laboratorian_user_id:1, updated_at:-1, _id:-1}` | assigned laboratory queue; not declared locally |
| lab_requests | `{created_at:-1, _id:-1}` | admin page; not declared locally |
| users | `{role:1, full_name:1, _id:1}` | omitted-search directories; only unique email is declared locally |

Case-insensitive regex search is not guaranteed to benefit from the proposed users index. A connected explain review and an approved search-index strategy are required before making any change.

## 15. Remaining risks and findings not resolved

- Real execution plans, deployed indexes, query latency, pool pressure, BSON sizes, and representative-scale behavior were not measured.
- Connected account-registration, distributed rate-limit, and report-transaction gates remain blocked.
- The scanner AF_UNIX tests remain unexecutable in this sandbox, although the rest of the backend passes.
- Group B conditions remain open: provider/proxy enforcement of the 256 KiB webhook ceiling and clinic approval of semantic clinical text limits.
- Eight connected release gates remain BLOCKED. Client demonstration, staging, and production remain unauthorized.
- Historical unregistered/unpaged compatibility helpers still exist. They were not made reachable by these handlers and were deliberately not broadened into Group C.

There is no known remaining confirmed N+1 defect among these 14 registered operations. No Critical or High regression was found.

## 16. Files changed for Group C

Application code:

- `backend/app/api/users.py`
- `backend/app/repositories/profile_repository.py`
- `backend/app/repositories/demo_service_repository.py`
- `backend/app/repositories/lab_request_repository.py`
- `backend/app/services/user_service.py`
- `backend/app/services/appointment_service.py`
- `backend/app/services/home_visit_service.py`
- `backend/app/services/lab_request_service.py`

Tests:

- `backend/tests/test_phase24a12_group_c_nplus1_clinical_queries.py` (new)
- `backend/tests/test_clinical_pagination.py`
- `backend/tests/test_api_contract.py`
- `backend/tests/test_clinician_directory.py`
- `backend/tests/test_phase24a3_patient_dashboard_recent.py`

Documentation:

- `docs/PHASE_24A12_GROUP_C_NPLUS1_CLINICAL_QUERY_REMEDIATION_REPORT.md` (new)

These edits were layered onto an already-dirty preserved worktree; the paths were not assumed to belong exclusively to Group C.

## 17. Final state and recommendation

The final recalculation confirms that the branch, HEAD, and upstream relationship remain unchanged: 101 tracked modified paths plus 84 untracked paths, 185 dirty paths total.

No database, MongoDB Atlas instance, Razorpay endpoint, webhook receiver, ClamAV daemon, protected storage service, deployment target, or other external service was accessed. No migration, seed, index change, payment, refund, deployment, provisioning, commit, or push occurred.

**Recommendation: PASS WITH CONDITIONS for Group C offline closure.** Proceed only to an explicit independent review. Group D remains unstarted. Phase 24B and all connected release gates remain blocked pending separate authorization and connected evidence.
