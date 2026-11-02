# Phase 24A.13 — Consolidated Security Closure and Demo Readiness Assessment

Assessment date: 2026-11-02  
Repository: PhysioCare  
Branch: `codex/physiocare-integration-2026-10-31`  
Assessed HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`  
Assessment type: independent offline review; assessment-only  

## 1. Executive summary

Phase 24A.12 Groups A through D have strong, independently reproducible offline evidence for the remediation work they actually implemented. The current source and fresh tests support the following group outcomes:

- **Group A: PASS for its declared M01-M03 scope.** Payment history, the entitlement directory, and the staff directory are bounded and paginated. The result does not close A11-L01.
- **Group B: PASS WITH CONDITIONS.** The application enforces the webhook and ordinary mutation limits offline. Provider/proxy agreement for the 256 KiB webhook ceiling and clinic approval of semantic clinical text limits remain unresolved.
- **Group C: PASS WITH CONDITIONS.** The 14-operation N+1 inventory is covered by constant-query-count tests, but deployed indexes, query plans, representative-scale latency, and concurrency have not been verified.
- **Group D: PASS WITH CONDITIONS.** The unsupported administrator patient-create workflow is absent from the active product surface, and revision/CAS/transaction behavior is supported by deterministic offline tests. Administrator onboarding policy and real MongoDB replica-set transaction/rollback behavior remain unresolved.

The Phase 24A.11 register contains 16 entries. All 16 were independently reconciled against the current source, tests, and prior evidence. Final dispositions are: four `CLOSED – VERIFIED OFFLINE`, one `RESOLVED ON ACTIVE PRODUCT SURFACE`, three `PASS WITH CONDITIONS`, three `OPEN`, three `NOT APPLICABLE – JUSTIFIED`, one `POLICY DECISION REQUIRED`, and one `CONNECTED VERIFICATION REQUIRED`. No item is `CLOSED – VERIFIED CONNECTED`.

A material documentation discrepancy was confirmed. The Group A report explicitly left A11-L01 through A11-L03 open, while the later Group B report states that Group A addressed L01. The current source resolves the conflict: `LaboratoryTestRepository.get_active_tests()` still performs an unbounded `.to_list()`, and the Group A test file contains no laboratory-catalogue case. A11-L01 therefore remains **OPEN**, alongside the already known A11-L02 provider-identifier exposure and A11-L03 public OpenAPI/documentation default.

No new Critical or High vulnerability was confirmed. The open items are three Low findings, policy gaps, and missing connected evidence. Those items prevent an unconditional security-closure claim.

**Controlled local/demo decision: CONDITIONAL GO**, limited to an explicitly approved loopback or isolated environment, fictional data, pre-created accounts, disabled payments, and the workflow exclusions in sections 11, 17, and 18. This is not authorization to conduct a demo by itself.

**Connected client-demo decision: NO-GO.** All eight connected gates remain blocked, the intended connected environment has not been approved or exercised, and clinic policy decisions remain outstanding.

**Phase 24A closure recommendation: PASS WITH CONDITIONS for the completed offline remediation packages, but do not mark consolidated Phase 24A security closure complete.** Resolve or formally disposition A11-L01-L03, obtain the clinic decisions, and complete the approved connected gates before advancing.

**Phase 24B: BLOCKED / NOT STARTED.**

## 2. Assessment scope

This assessment:

- reconciled the complete Phase 24A.11 finding register against Groups A-D;
- inspected current implementation and regression tests rather than accepting report conclusions alone;
- reviewed authentication, authorization, clinical-data boundaries, payment and entitlement controls, PDF handling, configuration isolation, logs, and dependency evidence;
- mapped active frontend routes to registered backend operations for demo purposes;
- reran safe offline checks without opting into connected tests;
- did not connect to MongoDB, Razorpay, a ClamAV daemon, external storage, or any deployed environment;
- did not execute migrations, seed operations, index changes, payments, refunds, webhooks, deployments, commits, or pushes; and
- changed no application, test, configuration, dependency, or prior report file.

The only repository file created by this milestone is this report.

## 3. Repository state

### 3.1 State before creating this report

| Item | Independently observed state |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | 0 / 0 |
| Staged paths | 0 |
| Unstaged tracked modifications | 112 |
| Untracked paths | 87 |
| Total dirty paths | 199 |
| Group A-D reports | All four present and untracked |

The branch, HEAD, upstream relationship, and dirty counts exactly matched the final Group D report. File-time inspection showed the Group D backend test file was touched after the Group D report, consistent with its final cleanup/verification; no new path or dirty-count drift was present. Because the work is uncommitted, Git cannot cryptographically attribute every dirty hunk to a milestone. This assessment therefore relies on current-source inspection and fresh tests rather than assuming report ownership.

### 3.2 Expected state after this report

Creating this report adds one untracked documentation path. No tracked path is intentionally changed. Expected final counts are 112 unstaged tracked modifications, 88 untracked paths, 200 total dirty paths, and zero staged paths. Section 14 records the final verification.

## 4. Evidence reviewed

### 4.1 Mandatory milestone evidence

The following documents were reviewed and reconciled:

- `docs/PHASE_24A11_API_ENDPOINT_INVENTORY.md`
- `docs/PHASE_24A11_RESIDUAL_SECURITY_AND_QUERY_FINDINGS.md`
- `docs/PHASE_24A11_RESIDUAL_ENDPOINT_AUDIT_REPORT.md`
- `docs/PHASE_24A12_GROUP_A_UNBOUNDED_RETRIEVAL_REMEDIATION_REPORT.md`
- `docs/PHASE_24A12_GROUP_B_WEBHOOK_AND_PAYLOAD_PROTECTION_REPORT.md`
- `docs/PHASE_24A12_GROUP_C_NPLUS1_CLINICAL_QUERY_REMEDIATION_REPORT.md`
- `docs/PHASE_24A12_GROUP_D_API_CONTRACT_AND_MULTIWRITE_INTEGRITY_REPORT.md`
- `docs/PHASE_24A9_INDEPENDENT_FINAL_SECURITY_REVIEW.md`
- `docs/PHASE_24A8_FINAL_OFFLINE_CLOSURE_READINESS_REPORT.md`
- `docs/PHASE_24A8_PASSWORD_POLICY_DECISION_PACKAGE.md`
- `docs/PHASE_24A7_RESIDUAL_DEFECT_REMEDIATION_REPORT.md`

### 4.2 Current implementation evidence

Representative source evidence included:

- pagination and bounded query paths: `backend/app/core/pagination.py`, `backend/app/repositories/payment_query_repository.py`, `backend/app/repositories/demo_service_repository.py`, `backend/app/repositories/user_repository.py`;
- webhook and body controls: `backend/app/core/request_limits.py`, `backend/app/main.py`, `backend/app/api/payments.py`, `backend/app/services/payment_service.py`;
- batched list formatting: appointment, profile, home-visit, and lab-request repositories/services;
- revision and transaction boundaries: `backend/app/repositories/appointment_repository.py`, `care_plan_repository.py`, `exercise_repository.py`, and `account_registration_repository.py`;
- authorization: `backend/app/middleware/auth.py`, `backend/app/services/clinical_authorization.py`, and endpoint-specific owner/assignment checks;
- PDF quarantine and scanner behavior: `backend/app/services/clinical_report_storage.py`, `backend/app/services/pdf_malware_scanner.py`, `backend/app/api/reports.py`, and `backend/app/api/lab_requests.py`;
- environment isolation: `backend/app/core/config.py`, `backend/staging.env.example`, `backend/production.env.example`, and `backend/run_production.py`;
- active product routes: `frontend/src/App.jsx` and the current page implementations; and
- every new Group A-D backend test plus the Group A, B, and D frontend regression files.

### 4.3 Evidence labels used in this report

- **Independently verified:** current source or a fresh command was inspected in this assessment.
- **Report-reported:** a prior report records a result that was not independently reproduced in exactly the same command shape.
- **Inference:** a conclusion follows from source and configuration but was not exercised in a connected runtime.
- **Missing evidence:** the required connected, policy, or operational proof does not exist in the repository.

## 5. Phase 24A.11 finding reconciliation

| ID | Original severity | Original description / workflow | Group | Evidence inspected | Current implementation and test evidence | Remaining condition | Final disposition |
|---|---|---|---|---|---|---|---|
| A11-M01 | Medium | Unbounded/N+1 patient payment history, `GET /api/payments/history` | A; rechecked C | `payment_query_repository.py:13-67`; Group A/C tests | `$match` precedes stable sort/skip/limit; one bounded `$lookup`; owner route remains patient-scoped. Group A 16/16 and Group C 37/37 fresh passes include this path. | Connected query plan/scale is covered by E01, not needed for offline closure. | **CLOSED – VERIFIED OFFLINE** |
| A11-M02 | Medium | Omitted entitlement search selected all patients and two lookups per row | A; rechecked C | `demo_service_repository.py:52-68`; home-visit API/service; Group A/C tests | Missing/blank search uses one bounded aggregation with stable sort, page, projection, and current entitlement state. | Connected plan/scale under E01. | **CLOSED – VERIFIED OFFLINE** |
| A11-M03 | Medium | Unbounded administrator staff directory | A | `user_repository.py:44-78`; users API/service; frontend page; Group A tests | Server filtering, stable `full_name/_id` order, projection, skip/limit, and page replacement are present. | Search/index efficiency remains connected evidence, but retrieval is bounded. | **CLOSED – VERIFIED OFFLINE** |
| A11-M04 | Medium | Fourteen bounded N+1 clinical list operations | C | Group C 14-operation table; affected services/repositories; 37 fresh tests | Twelve paths use bounded page-level identity reads; M01/M02 remain single aggregations. Counts are constant at 1/10/50/100 rows in mocked tests. | Real plans, indexes, latency, BSON sizes, and pool behavior remain E01. | **CLOSED – VERIFIED OFFLINE** |
| A11-M05 | Medium | Public Razorpay webhook buffered an uncapped body before authentication | B | `request_limits.py:14-68`; `api/payments.py:115-129`; payment service; 29 fresh tests | Headers are rejected before reading; declared and actual streamed bytes are capped at 256 KiB; exact bytes reach signature verification; malformed/oversized input does not reach persistence. | Provider maximum, proxy buffering/chunking, and cap agreement require approved connected verification. | **PASS WITH CONDITIONS** |
| A11-M06 | Medium | Persistent JSON/list/string inputs lacked practical ceilings | B | request middleware; auth, appointment, care-plan, exercise, report and laboratory schemas; Group B tests | 1 MiB ordinary mutation envelope and field/list/nesting ceilings are enforced before service writes; oversized legacy response records remain readable. | Clinic must approve semantic clinical text/content limits; technical maxima are not clinic policy. | **PASS WITH CONDITIONS** |
| A11-M07 | Medium | Active admin patient-create screen called missing `POST /api/users/patients` | D | `frontend/src/App.jsx:221-250`; `PatientsCreate.jsx`; users API; Group D tests | No active route or launch control remains and no unsupported backend endpoint was invented. The orphan component is unreachable. | Credentials, invitation, activation, verification, duplicate behavior, and audit policy are required before re-enabling. | **RESOLVED ON ACTIVE PRODUCT SURFACE** |
| A11-M08 | Medium | Clinical RMW/multi-write races and partial side effects | D | appointment/care-plan/exercise repositories and services; 18 fresh Group D tests | Expected revisions, conditional atomic updates, revision increments, explicit 409 mapping, shared transaction sessions, fail-closed behavior, and idempotent address repair are present. Deterministic two-writer tests permit one winner. | Real replica-set commit/rollback, callback retry, two-client race, and legacy-document behavior require connected MongoDB evidence. | **PASS WITH CONDITIONS** |
| A11-L01 | Low | Active legacy laboratory catalogue unbounded | Claimed inconsistently; not implemented by A-D | `laboratory_test_repository.py:7-10`; `laboratory.py:20-37`; Group A report/tests | Current code still calls `.to_list()` without limit, stable order, projection, or hard catalogue cap. Group A report section 14 leaves L01 open; Group B section 18 incorrectly says Group A addressed it. | Implement or formally retire/unregister the active legacy API in a separately authorized remediation. | **OPEN** |
| A11-L02 | Low | Legacy laboratory responses expose provider payment/order IDs unnecessarily | None | `laboratory_booking.py:31-46`; `laboratory.py` response constructors | `payment_id` and `payment_order_id` remain in the general response and are serialized. Access is scoped, so this is unnecessary exposure rather than cross-user leakage. | Remove/minimize or document an approved support need; add response-exclusion tests. | **OPEN** |
| A11-L03 | Low | OpenAPI and interactive docs public by default | None | `main.py:62-66`; registered framework defaults | `FastAPI(...)` supplies no `docs_url`, `redoc_url`, or `openapi_url` restriction. Deployment ingress is unknown. | Clinic/deployment policy and production-like verification; disable, authenticate, or explicitly approve exposure. | **OPEN** |
| A11-I01 | Informational | Dormant unbounded compatibility helpers | None | A11 call graph, current registered paths, current bounded handlers | Helpers remain maintenance debt, but no reviewed registered handler reaches their unbounded optional branches. | Keep static/call-graph tests or remove in authorized cleanup. | **NOT APPLICABLE – JUSTIFIED** |
| A11-I02 | Informational | Dormant components call nonexistent address route | None | current `App.jsx`; dormant component references | Components remain unrouted/unimported; no active workflow depends on the missing route. | Remove/archive in a separately authorized cleanup. | **NOT APPLICABLE – JUSTIFIED** |
| A11-I03 | Informational | Health endpoint shows demo DB name in demo mode | None | `main.py:190-202`; demo isolation guards in config | Production/application mode returns no DB name; dedicated demo modes intentionally expose their fixed demo identity and have strict guards. | Verify deployed health exposure during proxy gate. | **NOT APPLICABLE – JUSTIFIED** |
| A11-E01 | Environment | Indexes, plans, scale, proxy, scanner, storage, browser, and connected security | All | Phase 24A.8 gate register; current connected-test guards | No approved connected evidence exists. Three MongoDB-only contracts remain deliberately skipped offline. | Close all eight gates with approved fictional data and recorded evidence. | **CONNECTED VERIFICATION REQUIRED** |
| A11-P01 | Policy | Password, verification, recovery, and onboarding decisions unresolved | Cross-cutting | policy package; `schemas/auth.py:9-42`; current auth/onboarding flows | Public API still permits six-character new patient passwords; verification/recovery are absent; staff accounts use admin-chosen passwords and immediate activation. | Written clinic/security decisions and later authorized implementation. | **POLICY DECISION REQUIRED** |

### 5.1 Reconciliation counts

| Disposition | Count |
|---|---:|
| CLOSED – VERIFIED OFFLINE | 4 |
| CLOSED – VERIFIED CONNECTED | 0 |
| RESOLVED ON ACTIVE PRODUCT SURFACE | 1 |
| PASS WITH CONDITIONS | 3 |
| OPEN | 3 |
| NOT APPLICABLE – JUSTIFIED | 3 |
| POLICY DECISION REQUIRED | 1 |
| CONNECTED VERIFICATION REQUIRED | 1 |
| Total | 16 |

All 16 current dispositions were independently checked. At the finding-register level, one entry has a final policy disposition and one has a final connected disposition. In addition, M06 and M07 carry policy dependencies, while M04, M05, M08, L03, and several closed query paths require connected corroboration under the umbrella E01 gate. Counts must not be interpreted as only one policy choice or one connected test.

## 6. Group A verification — unbounded retrieval

**Outcome: PASS for Group A's declared M01-M03 scope.**

Verified strengths:

- Common pagination defaults to 50, limits page size to 100, and limits page number to 1,000.
- Payment history filters by the authenticated patient's profile before stable `created_at/_id` sorting, page slicing, a bounded appointment lookup, and a minimum response projection.
- The entitlement directory always uses the bounded aggregation for missing, blank, whitespace, and populated search shapes.
- The staff directory applies role/status/search filters in MongoDB, escapes search regex input, projects only administrator-directory fields, and uses stable ordering.
- Frontend consumers replace the current page rather than accumulating an unlimited client list.
- Fresh evidence: Group A backend 16 passed; four focused frontend Group A tests passed; the complete frontend suite passed.

Documentation discrepancy and scope boundary:

- Group A's executive summary and finding table address M01-M03 only, and its section 14 explicitly lists L01-L03 as remaining.
- Group B later states that Group A addressed L01. That statement is inaccurate.
- The live L01 repository method is still unbounded. Group A therefore remains a pass for its actual declared scope, not for all unbounded reads in the Phase 24A.11 register.

## 7. Group B verification — webhook and payload protection

**Outcome: PASS WITH CONDITIONS.**

Independently verified controls:

- `read_bounded_body` validates non-negative integer `Content-Length`, rejects declared oversize before streaming, counts actual chunks, and stops before retaining the over-limit chunk.
- Missing webhook signature/event ID and oversized headers are rejected before body reading.
- The webhook-specific maximum is 256 KiB; ordinary non-upload mutation bodies use a 1 MiB ceiling.
- The webhook is excluded from general JSON middleware so it is read once by its specialized bounded reader.
- Existing signature handling receives the original bytes; JSON is parsed only after signature validation.
- Oversized/malformed input and oversized provider IDs do not reach the ledger or payment/appointment state.
- Rejection logs include route and sizes, not request bodies, signatures, or secrets.
- Schema maxima are present for auth, appointments, lab bookings, care plans, exercises, reports, schedules, and related persistent inputs; mutation schemas reject unexpected fields where reviewed.
- Fresh Group B result: 29 passed.

Conditions retained without reinterpretation:

1. The 256 KiB ceiling is an application fail-safe, not a verified Razorpay contract. Provider payload size, proxy buffering, chunking, timeout, and cap agreement require an approved connected exercise before webhook enablement.
2. The 8,000/16,000-character clinical ceilings are technical storage safeguards. The clinic must decide semantic clinical content limits.
3. The route-level lab PDF upload accumulates bounded chunks and joins them before storage; it remains bounded by the configured PDF maximum but is not a zero-copy transport claim.

## 8. Group C verification — N+1 clinical lists

**Outcome: PASS WITH CONDITIONS.**

The original 14 operations were reconciled: four appointment list shapes, two patient-directory shapes, three home-visit lists, three lab-request lists, payment history, and the entitlement directory. The 12 Group C paths now batch related identities per page; the two Group A paths remain one bounded aggregation each.

Fresh Group C tests passed 37/37 and assert:

- constant collection-call counts at page sizes 1, 10, 50, and 100;
- filtering and assignment predicates before paging;
- stable ordering and bounded cursor consumption;
- missing-related-record fail-closed behavior;
- patient OWN, clinician ASSIGNED, receptionist coordination, and laboratory assignment boundaries; and
- role-specific projections without password, session, payment credential, report storage, or unrelated clinical fields.

The evidence is mocked query-shape and call-count evidence. It does not establish real MongoDB execution plans, deployed index presence, large-offset behavior, BSON transfer size, pool pressure, or representative latency. Those remain connected gates 2 and 3.

## 9. Group D verification — API contract and multi-write integrity

**Outcome: PASS WITH CONDITIONS.**

### 9.1 A11-M07 active-surface contract

- `frontend/src/App.jsx` has no `/admin/patients-create` route and no `PatientsCreate` import.
- Dashboard launch controls no longer direct administrators to that workflow.
- `backend/app/api/users.py` has no administrator `POST /patients` operation.
- The preserved `PatientsCreate.jsx` is dormant and does not establish a supported workflow.
- The Group D frontend contract verifies absence of the active route/launch control; the backend test verifies absence of the route contract.

No active misleading patient-create control was found. Administrator patient onboarding remains a policy and product gap, not an implemented capability.

### 9.2 A11-M08 revision and integrity controls

- Appointment, care-plan, and exercise-assignment models expose revision zero for legacy compatibility.
- Mutation schemas require the expected revision on affected writes.
- Repository predicates include resource identity, patient/doctor scope, and expected revision; successful updates increment the revision in the same operation.
- A missing-revision legacy document matches only an expected revision of zero.
- Services map stale updates to explicit HTTP 409 conflicts.
- Care-plan primary/audit/notification changes and exercise assignment/progress changes use one MongoDB transaction session and provide no non-transactional fallback.
- Home-address persistence remains a separate preference write. Booking idempotency prevents a duplicate booking, and a retry repairs the preference.
- Fresh Group D result: 18 passed, including deterministic two-writer appointment/care-plan/progress cases, fail-closed transaction-unavailable cases, session-sharing assertions, conflict mapping, and address-repair behavior.

The race tests model repository results deterministically; they are not simultaneous real MongoDB clients. Real transaction capability, commit/rollback, retry callback semantics, stale legacy records, and two-client races remain unverified.

## 10. Independent security review

### 10.1 Authentication and authorization

Verified strengths:

- Access and refresh tokens have distinct types and secrets; access tokens are bound to a persisted live session.
- Access-cookie authentication checks session existence, expiry, revocation, user binding, current user existence, and active-account status.
- Authenticated unsafe requests require a matching double-submit CSRF value also bound to the stored session hash.
- Refresh rotation uses a conditional repository operation; rotation failure/reuse revokes the session and returns a generic 401.
- Login uses the same expensive password verification path for unknown and wrong-password accounts and returns the same error for unknown, wrong, or inactive users.
- Public registration returns a neutral 202 response and suppresses duplicate-email disclosure.
- The default authentication rate limiter uses atomic MongoDB counters, HMAC-obscured bucket keys, trusted-proxy-aware client IP resolution, bounded retry for initial upsert races, and fail-closed 503 behavior on store failure.
- Role dependencies protect frontend-corresponding APIs; patient OWN and clinician ASSIGNED checks remain server-side.

Conditions:

- Distributed rate-limit behavior and registration transactions have connected-only tests and remain unverified against an actual MongoDB deployment.
- Public new-patient password policy, email ownership, recovery, and onboarding remain unresolved under P01.
- HTTPS/Secure-cookie/CORS/proxy/CSRF behavior in the intended connected environment is gate 7, not established by offline tests.

### 10.2 Clinical data protection

- Current patient, doctor, receptionist, laboratory, and administrator list responses retain role-specific projections.
- The shared clinician authorization helper denies malformed/unassigned patient IDs without disclosing resource existence.
- Care-plan and exercise writes include patient/therapist/assignment scope in their conditional update predicates.
- Authenticated API responses and PDF routes use private/no-store headers.
- Pagination and batch-query remediations reduce unbounded materialization and N+1 exposure on the reviewed active paths.
- No Critical/High cross-patient, cross-clinician, password-hash, session-token, or role-escalation regression was identified.

Residuals are A11-L01-L03 and the connected concurrency/authorization gates.

### 10.3 Payments and entitlements

- Payment order/status/verify/cancel/abandon routes derive and enforce patient ownership.
- Webhook verification occurs before parsing or persistence; provider IDs are bounded; event and body-digest uniqueness provide replay/idempotency controls.
- Appointment/payment transitions retain conditional state checks and reconciliation markers.
- Entitlement administration is admin-only; patient eligibility derives from the authenticated patient's profile and targeted current grant.

No Razorpay call, real payment record, webhook, refund, or reconciliation run occurred. Payment readiness is therefore offline source/test evidence only. A11-L02 remains open for legacy laboratory responses.

### 10.4 File uploads and storage

- Clinical and laboratory PDF stores use opaque names, separate approved/quarantine roots, non-symlinked paths, owner-only directories/files, byte ceilings, PDF header/EOF checks, scan-before-promotion, atomic move, and cleanup on failure.
- The default scanner is unavailable/fail-closed. The Unix adapter uses ClamAV INSTREAM, maps only exact clean/malicious results, treats disconnect/protocol error as failure, and has surrounding timeout enforcement.
- Scanner error returns 503 and malicious content returns 422; neither is promoted.
- Clinical report download checks patient ownership; laboratory downloads check patient ownership/release, clinician assignment, laboratory assignment, or administrator role in the service before returning a private no-store file.
- All 12 fake-socket scanner tests passed with a temporary local Unix socket; no real daemon was contacted.

Deployed filesystem permissions, mount isolation, cleanup recovery, daemon interoperability, and authorized downloads remain gates 4 and 5.

### 10.5 Logging, secrets, and dependencies

- Reviewed logs use bounded metadata and generic error types; raw webhook bodies, passwords, JWTs, CSRF values, provider secrets, and database credentials are not intentionally logged.
- Settings diagnostics redact credential-bearing fields.
- Fresh redacted current-tree Gitleaks scan found six known synthetic `generic-api-key` fixtures: five in `backend/tests/test_api_contract.py` and one in `backend/tests/test_schedule_fallback_guard.py`. No application credential was identified. This was not a Git-history scan.
- Dependency-lock tests passed 2/2, `pip check` reported no broken requirements, and offline npm audit reported zero cached vulnerabilities. Audit cache freshness and future advisories are not connected-verified.

## 11. Demo workflow matrix

`PASS` below means the workflow has adequate offline contract evidence. `CONDITIONAL` means it may be included only after the listed local/isolated prerequisites. `BLOCKED` means it must not be shown as working in the proposed demo. `OUT OF SCOPE` is an explicit safe exclusion, not a completion claim.

| Workflow | Active frontend route | Principal backend API | Authorization | Data dependency | Offline evidence | Connected dependency | Demo status | Reason |
|---|---|---|---|---|---|---|---|---|
| Login/logout/session | `/login`, role portals | `/api/auth/login`, `/refresh`, `/csrf`, `/logout`, `/me` | own live session; CSRF on unsafe actions | users, sessions, rate buckets | auth/session/rate-limit suites in 1,094 pass | real DB counters; HTTPS/cookies/proxy | **CONDITIONAL** | Use pre-created fictional accounts in approved isolated DB; exclude recovery/verification claims. |
| Patient profile | `/patient/profile` | `GET /auth/me`, `PATCH /users/me/patient-profile` | patient OWN | users/patients | ownership and rendered-flow tests | isolated DB/browser | **CONDITIONAL** | Safe with fictional profile and local browser smoke. |
| Administrator dashboard/directories | `/admin/dashboard`, `/admin/patients`, `/admin/doctors`, `/admin/staff` | analytics/users/appointments APIs | admin | isolated DB | bounded list, role, frontend tests | query plans/indexes/browser | **CONDITIONAL** | Directory/view/edit can be shown with fictional data; administrator patient creation is absent. |
| Administrator-created patient | no active route | no registered API | not applicable | policy and future transaction | deliberate-absence tests | policy + future connected transaction | **BLOCKED** | Do not imply this capability exists. |
| Staff creation/onboarding | `/admin/staff` | `POST /api/users/staff` | admin | users/profile | API/UI contract tests | clinic onboarding policy | **BLOCKED** | Current admin-chosen password/immediate activation is not an approved demo onboarding story. Read-only staff directory may be shown. |
| Clinician dashboard/patients | `/doctor/dashboard`, `/doctor/patients`, patient history | appointment/user/report APIs | doctor ASSIGNED | isolated DB | assignment, projection, query tests | connected multi-clinician/browser | **CONDITIONAL** | Use a pre-assigned fictional patient and run a narrow authorization smoke first. |
| Receptionist coordination | `/reception/dashboard`, `/reception/patients`, `/reception/appointment-booking` | reception appointment/patient/home-visit APIs | receptionist, minimized schemas | isolated DB | role/projection/frontend tests | browser/account-switch gate | **CONDITIONAL** | No clinical/billing fields may be represented as available. |
| Appointment management | patient/admin/doctor appointment routes | appointments APIs | patient OWN; doctor ASSIGNED; admin | DB, schedules, slot indexes | booking/conflict/revision tests | actual indexes, browser, transaction/race | **CONDITIONAL** | Seeded appointment viewing/status flows are suitable; mutation flows need an approved transaction-capable isolated DB smoke. |
| Appointment checkout/payment | `/patient/book`, `/patient/payments`, `/admin/billing` | payment order/verify/status/webhook/reconcile APIs | patient OWN/admin; provider webhook | Razorpay and payment records | extensive offline mocks | provider, webhook/proxy, payment approval | **OUT OF SCOPE** | Payments must remain disabled; no checkout, provider, capture, reconciliation, or billing-success claim. Synthetic history may be shown only if clearly labeled. |
| Home-visit booking | `/patient/home-visits`, `/admin/demo-services`, `/doctor/home-visits` | demo entitlement, availability, booking/assignment APIs | patient entitlement/OWN; admin; assigned doctor | dedicated demo DB, schedules, city, entitlement | focused home-visit/query tests | browser, actual indexes | **CONDITIONAL** | Only dedicated guarded demo mode, fictional address, preconfigured schedule/entitlement, and no payment. |
| Care plans | patient care plan; admin/doctor patient care-plan routes | care-plan APIs | patient OWN; admin; doctor ASSIGNED/owner | transaction-capable MongoDB for writes | revision/transaction mocks | real replica-set rollback/race | **CONDITIONAL** | Read-only seeded display may be shown; create/update/stage/goal writes excluded until isolated transaction smoke passes. |
| Exercises/progress | patient exercises/progress; admin/doctor assignment routes | exercise/assignment/progress APIs | patient OWN; admin; doctor ASSIGNED | transaction-capable MongoDB for progress transitions | revision/race/query tests | real transaction/race/browser | **CONDITIONAL** | Read-only seeded data is suitable; progress/assignment mutation excluded until transaction gate evidence exists. |
| Modern laboratory requests | `/patient/laboratory`, `/admin/laboratory`, `/laboratory/dashboard` | `/api/lab-requests...` | patient OWN; admin; LAB-ASSIGNED; doctor ASSIGNED | DB; private storage/scanner for PDFs | idempotency, role, query, partial-failure tests | storage/scanner/browser | **CONDITIONAL** | Request/list/assignment with fictional data may be shown; PDF upload/publication/download is excluded. |
| Legacy laboratory booking | no active routed screen for normal workflow | `/api/laboratory/tests`, `/bookings...` | patient/admin/doctor scopes | DB | partial API tests | none needed to confirm open source defects | **OUT OF SCOPE** | A11-L01 and L02 remain open; do not use these endpoints in the demo. |
| Clinical reports metadata | `/patient/reports`, admin/doctor `/reports/new` | `/api/reports...` | patient OWN; doctor ASSIGNED; admin | DB | ownership/pagination tests | browser | **CONDITIONAL** | Seeded metadata/read-only display is suitable. Report authoring with a file is excluded. |
| Private PDF access | patient reports and lab viewers | report download and lab report-file APIs | owner/assignment/release/admin rules | private storage + scanner | strong unit/contract and fake-socket tests | gates 4, 5, 6, 7 | **BLOCKED** | Do not show upload/download until approved storage, scanner, browser, and cache behavior are verified. |
| Notifications | role portal notification routes | `/api/notifications...` | authenticated recipient | DB | pagination/recipient/UI tests | browser | **CONDITIONAL** | Use only fictional recipient data and verify account switching locally. |
| Entitlement administration | `/admin/demo-services`; patient home-visit screen | demo entitlement APIs | admin write; patient OWN read | dedicated demo DB | Group A/home-visit tests | browser/DB | **CONDITIONAL** | Demonstrable as a demo-only control with fictional accounts; do not conflate it with payment. |

## 12. Clinic policy decision register

| Decision | Why required / dependent workflow | Scope blocked | Safe current default | Must not be assumed |
|---|---|---|---|---|
| Administrator-created patient onboarding | No active contract exists; M07 was resolved by removal | admin patient creation | capability absent | that staff creation or public registration is an acceptable substitute |
| Credential establishment | Initial patient/staff credential owner and delivery are undefined | onboarding and any onboarding demo | pre-created fictional accounts only | that administrators may know/share permanent passwords |
| Account activation | Public patient and staff accounts currently become active immediately | onboarding and connected access | do not create demo accounts during presentation; seed approved accounts | that email possession or clinic identity has been verified |
| Email verification | No state/token/resend/change flow exists | registration and recovery story | exclude verification claims | that a syntactically valid email is owned by the user |
| Patient invitation | No invitation model or endpoint exists | administrator onboarding | no admin patient invitation | token lifetime, delivery channel, or activation semantics |
| Duplicate patient/account handling | Public registration is neutral; staff duplicate response differs; no admin patient policy | onboarding/support | retain existing neutral public response | merge, disclose, retry, or manual override policy |
| Patient-creation audit | No approved admin patient-create event exists | future onboarding | no workflow, therefore no fabricated audit | actor, fields, retention, review, or correction semantics |
| Clinical text/content limits | Group B maxima are technical safeguards | clinical authoring limits, not read-only demo | keep current technical limits unchanged | that 8,000/16,000 characters are clinic-approved semantic limits |
| Required demo workflows | The product contains more features than a safe demo needs | demo scope | smallest approved workflow set | that every routed feature must be demonstrated |
| Payment inclusion | Payment integration is not connected-verified and webhook contract is open | payment/checkout/billing-success demo | payments disabled; exclude provider activity | that Test Mode is authorized merely because code exists |
| Demo-data access authority | Even fictional clinical records should have named viewers/operators | all demo data | explicit least-privilege demo accounts and approved viewers | that any employee/client attendee may use admin/clinical roles |

Additional unresolved P01 choices include the authoritative new-password minimum, legacy-password transition, recovery channel and identity proofing, staff invitation/deactivation, support ownership, and mail/SMS privacy/infrastructure. This report makes none of those choices.

## 13. Connected release-gate matrix

The identifiers below are copied from the authoritative Phase 24A.8 gate table. All remain **BLOCKED**.

| Gate | Why needed | Current status | Approval required | Verification procedure and closure evidence | Blocks controlled local demo? | Blocks staging? | Blocks production? |
|---|---|---|---|---|---|---|---|
| 1. Connected multi-clinician authorization | Prove OWN/ASSIGNED/role controls with real queries and concurrent actors; includes connected registration and clinical transaction cases | **BLOCKED** | Approved isolated replica-set DB, identities, fictional data, test plan | Deliberately mismatched patient/doctor/lab/admin cases; registration commit/rollback; care-plan/exercise/appointment two-client races and rollback; signed results and logs | Narrow read-only demo can proceed only after local role smoke; mutation workflows blocked | Yes | Yes |
| 2. MongoDB query plans and realistic-scale performance | Offline call counts do not prove scans, memory, latency, or pool behavior | **BLOCKED** | Approved representative fictional dataset | `explain` for Group A/C and critical lists, large offsets, latency/concurrency thresholds, no disk/memory surprises | Not for a tiny controlled dataset if performance claims are excluded | Yes | Yes |
| 3. Actual database index verification | Source declarations do not prove deployed indexes/uniqueness | **BLOCKED** | Approved target DB and read-only inventory; separate approval for changes | Capture deployed indexes, unique/partial slot claims, query-plan index use, duplicate-data preflight; no unapproved index creation | Booking mutation demo blocked until required unique claims are verified | Yes | Yes |
| 4. Socket-capable ClamAV protocol and scanning | Fake server proves adapter logic, not daemon interoperability | **BLOCKED** | Approved private daemon/socket and inert test corpus | Readiness ping, clean/malicious/error/timeout/oversize cases, fail-closed startup/runtime, recorded daemon version/config | PDF workflow blocked; non-PDF workflows may proceed | Yes for PDF-enabled staging | Yes |
| 5. Private storage integration and access verification | Local units do not prove deployed mount permissions or isolation | **BLOCKED** | Approved private storage and fictional PDFs | permissions, separate quarantine/approved roots, atomic promotion, cleanup/reconciliation, traversal/symlink negatives, authorized and unauthorized downloads | PDF workflow blocked | Yes for PDF-enabled staging | Yes |
| 6. Browser end-to-end journeys | Source/render tests do not prove real multi-role cookies, navigation, account switching, and PDFs | **BLOCKED** | Approved browser, isolated environment, workflow/data plan | login/logout/refresh/CSRF, role transitions, booking conflicts, account switching, stale data, PDF, recovery states; retained artifacts | Yes for any client-facing demo; a narrow pre-demo smoke is mandatory but does not close the release gate | Yes | Yes |
| 7. Production proxy, TLS, cookie and cache verification | Secure cookies, origins, forwarding headers, request limits, webhook buffering, docs exposure, and no-store depend on ingress | **BLOCKED** | Approved production-like ingress and security config | TLS/Host/forwarded-IP trust, exact CORS, Secure/SameSite cookies, CSRF/same-origin, cache headers, body caps, OpenAPI exposure, provider/proxy webhook agreement | Local loopback demo can avoid this only by excluding webhook/payment and restricting access | Yes | Yes |
| 8. Backup and restore testing | Recovery cannot be inferred from code or config | **BLOCKED** | Approved infrastructure, retention, encryption, owners, fictional dataset | create backup, verify artifact/access, restore to isolated target, validate records/files/audits, record RPO/RTO and cleanup | No for disposable fictional local demo if explicitly approved | Yes | Yes |

Payment integration is not a ninth invented gate. It is verified through the applicable browser and proxy/TLS gates, plus separately approved Razorpay Test Mode credentials, webhook delivery, payment state transitions, idempotency, reconciliation, failure handling, and no-production-data evidence. Until that evidence exists, payment remains excluded.

## 14. Offline test evidence

### 14.1 Fresh results

| Check | Fresh result | Interpretation |
|---|---:|---|
| Group A backend file | **16 passed** | independently verified |
| Group B backend file | **29 passed** | independently verified |
| Group C backend file | **37 passed** | independently verified |
| Group D backend file | **18 passed** | independently verified |
| Combined Group A-D backend selection | **100 passed** | independently verified |
| Backend excluding AF_UNIX scanner file | **1,082 passed, 3 skipped** | skips are connected-only MongoDB contracts |
| Fake ClamAV AF_UNIX file with temporary local-socket permission | **12 passed** | fake local server only; no daemon/external service |
| Reconciled backend total | **1,094 passed, 3 connected-only skipped** | two-command reproduction; matches reported total, not one literal invocation |
| Complete frontend suite | **165 passed** | clean serial rerun |
| First frontend attempt | **165 passed assertions, 1 harness failure** | one temp-directory `ENOTEMPTY` cleanup race; isolated file then passed 7/7; clean full rerun above is authoritative |
| Group A/B/D focused frontend | **10 passed** | four A, two B, four D |
| Frontend lint | **PASS** | `oxlint` |
| Production build to `/private/tmp` | **PASS** | Vite 8.3.5; 1,837 modules; repository `dist` not overwritten |
| Bundle measurement | **73 JS/CSS assets; zero budget violations** | largest JS 373,260 bytes < 450 KiB; CSS 254,380 bytes < 300 KiB |
| Python syntax compilation | **170 files compiled in memory; zero failures** | no bytecode written to repository |
| Dependency-lock tests | **2 passed** | locked input parity/reproducibility contracts |
| Production-configuration + lock selection | **64 passed** | source/config guards only; no deployment |
| `pip check` | **PASS** | no broken requirements |
| Offline npm audit | **0 vulnerabilities** | local cache only; freshness unknown |
| Redacted Gitleaks current-tree scan | **6 synthetic fixture findings** | five API-contract fixtures, one schedule fallback fixture; not history scan |
| `git diff --check` | **PASS** | no whitespace errors |

All backend runs used the existing locked Python environment, a cleared test environment, synthetic distinct secrets, an intentionally unreachable loopback MongoDB URL, payments/reconciliation/scanner disabled, plugin autoload disabled, no pytest cache, and no connected-test opt-in. The fake scanner file required permission to bind only a temporary local Unix socket. No test suppression or weakening occurred.

### 14.2 Reported but not freshly duplicated in identical form

- Group D's historical single-command full backend result of 1,094 passed/3 skipped is corroborated by the fresh 1,082 + 12 split, but the exact single invocation was not repeated because AF_UNIX binding is sandbox-sensitive.
- Prior milestone build/bundle/secret results are consistent with fresh results; the fresh build deliberately targeted `/private/tmp` to preserve repository files.
- No Git-history secret scan was performed; the evidence is a redacted current-tree scan only.

### 14.3 Repository state after report creation

Final state must remain the same branch, HEAD, and upstream, with zero staged paths, 112 unstaged tracked modifications, and one additional untracked report path. The final command verification is recorded at handoff; any different values invalidate this paragraph and must be reported instead.

## 15. Unresolved security findings

### 15.1 Confirmed open Low findings

1. **A11-L01 — unbounded legacy laboratory catalogue.** Active patient-authenticated API; source-confirmed; incorrectly described as closed by the Group B report.
2. **A11-L02 — unnecessary legacy provider identifiers.** Owner/authorized access limits exposure, but the fields are unnecessary for normal clients and remain in responses.
3. **A11-L03 — public OpenAPI and interactive documentation default.** No patient data is directly exposed, but route/schema intelligence remains public unless ingress restricts it.

### 15.2 Conditional Medium findings

- M05 requires provider/proxy contract evidence.
- M06 requires clinic semantic-content policy.
- M08 requires real replica-set integrity evidence.

### 15.3 Policy and connected findings

- P01 remains unresolved across password policy, email verification, recovery, invitation/onboarding, activation, and support/audit ownership.
- E01 remains unverified; all eight gates are blocked.

No Critical or High issue was confirmed during this targeted review. That statement is limited to the current source, tests, and offline scope and is not a penetration-test or production-readiness claim.

## 16. Technical limitations

- No database connection means no deployed data shape, index, uniqueness, query plan, transaction, rollback, scale, or race claim is possible.
- Mocked concurrency establishes intended predicates and one-winner handling, not driver/server behavior under real contention.
- Offline frontend tests and build do not establish real-browser cookies, network caching, focus, account switching, or multi-role server behavior.
- Fake Unix-socket tests establish the ClamAV protocol adapter, not daemon compatibility or malware-detection quality.
- Local temporary storage tests do not establish deployed mount ownership, backup inclusion, durability, or cross-process behavior.
- Offline audits may use stale advisory caches. The secret scan excludes Git history and external logs.
- The 199-path dirty baseline is uncommitted; milestone attribution is document/source based rather than commit based.
- OpenAPI exposure and proxy body/cookie behavior cannot be inferred from application source alone.

## 17. Demo blockers

### 17.1 Blocks any connected client demo

- no approval or execution evidence for any of the eight connected gates;
- no approved connected environment/data/access plan;
- unresolved password, verification, recovery, and onboarding policy;
- no verified production-like HTTPS/cookie/CSRF/cache behavior;
- no connected MongoDB transaction, index, or authorization evidence; and
- payments, storage, scanner, backup, and browser journeys unverified.

### 17.2 Blocks particular workflows in a controlled local demo

- administrator-created patient and staff-onboarding stories: policy incomplete;
- payment/checkout/webhook/reconciliation: external activity prohibited and contract unverified;
- legacy laboratory booking: L01/L02 open;
- PDF upload/publication/download: scanner/storage/browser gates open;
- care-plan/exercise/other multi-document mutations: real transaction capability unverified;
- any public OpenAPI/docs exposure beyond loopback: L03 open; and
- any use of real patient data, production credentials, or production database: prohibited.

### 17.3 Conditions before a controlled local presentation

1. Obtain explicit written approval for the named local/isolated environment, workflow list, operators, and viewers.
2. Use only loopback or a specifically approved isolated host and a dedicated demo database; verify demo-mode guards before startup.
3. Use fictional, pre-seeded data and pre-created least-privilege accounts; do not use production exports.
4. Keep Razorpay and reconciliation disabled and remove payment success/checkout from the script.
5. Exclude administrator patient creation, staff credential onboarding, legacy lab booking, all PDF workflows, and transaction-dependent mutations unless their specific prerequisites are separately approved and verified.
6. Run a narrow real-browser pre-demo smoke covering login/logout, role routing, account switching, stale-session rejection, and every included read-only workflow. This smoke is a demo condition, not closure of gate 6.
7. Restrict `/docs`, `/redoc`, and `/openapi.json` by loopback/network access for the demo; do not claim the application default has been remediated.
8. Preserve a stop procedure and delete disposable fictional demo data only under a separately approved cleanup instruction.

## 18. Controlled local/demo GO / NO-GO decision

**Decision: CONDITIONAL GO.**

This decision means the current offline evidence is sufficient to prepare a narrowly controlled presentation after every condition in section 17.3 is met. It is not approval to conduct the presentation now, and it does not close any connected release gate.

Suitable included scope after approval and smoke testing:

- login/logout with pre-created fictional accounts;
- patient profile and read-only dashboard/history;
- read-only administrator, clinician, receptionist, and laboratory dashboards using role-appropriate fictional data;
- bounded directories, schedules, notifications, and appointment/home-visit views;
- carefully scripted appointment or home-visit creation only if the isolated DB indexes/schedules are preflighted and no payment success is implied;
- read-only seeded care-plan, exercise, laboratory-request, and report metadata; and
- demo entitlement grant/read behavior, clearly described as a demo-only control rather than payment.

Excluded scope:

- real data, production DB, production credentials, external services, or public network exposure;
- administrator patient creation and staff onboarding;
- payment order, checkout, verification, webhook, reconciliation, refund, or any real provider activity;
- legacy laboratory catalogue/booking endpoints;
- PDF upload, scanning, publication, private download, or storage claims;
- care-plan/exercise/progress multi-document mutations until transaction capability is verified; and
- any claim of staging, production, connected, security-certification, or operational readiness.

If any condition cannot be met, the controlled local/demo decision becomes **NO-GO**.

## 19. Connected client-demo GO / NO-GO decision

**Decision: NO-GO.**

The intended connected environment is not approved or verified. All eight gates are blocked, P01 is unresolved, L01-L03 remain open, and payment/storage/scanner/browser/backup evidence is absent. Offline pass results cannot substitute for those controls. A connected client demo requires a separately approved environment, fictional-data plan, named access authority, closure evidence for every workflow-relevant gate, clinic policy sign-off, and a new independent readiness decision.

## 20. Exact recommended next tasks, in priority order

1. **Review and approve this assessment.** Do not begin Phase 24B or remediation until the owners accept or correct the reconciliation, especially the L01 discrepancy.
2. **Open a narrowly scoped Phase 24A follow-up for L01-L03.** Bound or retire the legacy catalogue, minimize legacy provider IDs, and implement an explicit per-environment OpenAPI/docs policy with tests. Do not combine this with connected work.
3. **Obtain written clinic/security policy decisions.** Resolve new-password rules, existing-account transition, email ownership, recovery, administrator patient onboarding, staff invitation/activation, duplicate handling, audit semantics, clinical content limits, demo workflow scope, payment inclusion, and demo-data access.
4. **Approve a controlled-demo runbook if a local demo is desired.** Name the environment, people, fictional dataset, included/excluded workflows, start/stop checks, and incident/abort procedure.
5. **Perform the narrow local browser smoke.** Use fictional pre-seeded accounts; keep payments/PDFs/transaction-dependent writes excluded. Record results without treating them as connected gate closure.
6. **Design the isolated connected verification milestone.** It must use a transaction-capable MongoDB replica set, approved fictional data, no production access, and explicit authority for read/write test operations.
7. **Execute gates 1-3 under approval.** Verify cross-role negatives, registration and clinical transactions/rollback/races, deployed indexes, and query plans/latency.
8. **Execute gates 4-5 under approval.** Verify private storage and a real private ClamAV daemon with inert test PDFs, cleanup, and authorization negatives.
9. **Execute gates 6-7 under approval.** Run browser journeys and production-like proxy/TLS/Secure-cookie/CSRF/cache/docs/webhook-cap checks. Include Razorpay Test Mode only if payment is explicitly approved.
10. **Execute gate 8 under approval.** Complete backup/restore of fictional database and files and record RPO/RTO evidence.
11. **Commission a new independent connected-demo decision.** Only that milestone may change the connected demo from NO-GO.
12. **Consider Phase 24B only after Phase 24A is formally closed.** Do not treat this report as Phase 24B authorization.

## 21. Phase 24A closure recommendation

**Recommendation: PASS WITH CONDITIONS for the offline remediation packages; consolidated Phase 24A remains incomplete and must not be described as fully closed.**

M01-M04 are closed offline, M07 is resolved on the active surface, and M05/M06/M08 have credible offline remediation with explicit conditions. However, L01-L03 are open, P01 is unresolved, and E01/all eight connected gates lack evidence. The phrase “offline remediation complete” is acceptable only when qualified by those exact exclusions. “Security closed,” “demo ready” without conditions, “staging ready,” “production ready,” and “connected ready” are not supported.

The minimum path to formal Phase 24A closure is:

- resolve or formally risk-accept L01-L03 with authorized evidence;
- obtain clinic/security policy decisions relevant to the approved product/demo scope;
- complete the workflow-relevant connected gates; and
- commission an independent final closure review on a traceable baseline.

## 22. Phase 24B status

**BLOCKED / NOT STARTED.**

This assessment did not start Phase 24B and does not authorize it. Phase 24B may be considered only after explicit review/approval of this report and satisfaction of the Phase 24A closure conditions.

