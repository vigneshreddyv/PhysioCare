# Phase 24A.15 — Controlled Local Demo Preparation and Verification Report

Assessment date: 2026-11-02  
Branch: `codex/physiocare-integration-2026-10-31`  
Baseline HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

Phase 24A.15 prepared an offline, evidence-based plan for a restricted local demonstration. It did not start an application service, browser workflow, database, container, or external connection. No account or record was created.

The current source contains two strongly guarded but workflow-specific local environments:

- the Laboratory Demo pins a dedicated database, loopback MongoDB/API/frontend ports, exact CORS, disabled payments, and private demo storage, but its supported preparation/rehearsal deliberately creates a laboratory request and exercises PDF upload/publication; and
- the Home Visit Demo pins a different dedicated database and loopback ports with disabled payments and supplies fictional patient, clinician, and administrator fixtures, but it has no receptionist or laboratory account, no broad clinical dataset, and no data-cleanup action.

Neither environment is an approved fit for the proposed five-role read-only walkthrough. Ordinary development is also not acceptable as the demo environment: it uses the shared `physiocare_dev` identity, `backend/run.py` has a `0.0.0.0` fallback if host configuration is absent, and development documentation is enabled by default. A dedicated demo guard must not be replaced with operator convention.

All eleven required approvals are **PENDING**. The current machine is macOS and has neither PowerShell (`pwsh`) nor Docker installed, while the supported demo launchers are PowerShell-based and their MongoDB lifecycle depends on Docker. No installation was attempted.

Fresh offline verification is strong: 409 focused workflow tests passed; the reconciled backend total is 1,135 passed with three deliberately skipped connected-only tests; all 167 frontend tests passed; and lint, build, bundle, compilation, lock, dependency, offline audit, secret-scan, and whitespace checks passed.

**Demo preparation: PARTIALLY PREPARED.** Scope, approval register, fictional-data plan, verification matrix, abort procedure, and operator runbook are documented, but the environment choice, machine, people, dataset, accounts, and browser evidence remain unapproved/unexecuted.

**Actual controlled local demo authorization: NO-GO.** A complete runbook is not authorization. Explicit approvals, an executable supported isolated environment, separately approved account/data preparation, and a successful narrow browser smoke test are still required.

Connected client demo remains **NO-GO**. Production readiness is not claimed. Phase 24B remains **BLOCKED / NOT STARTED**.

## 2. Initial repository state

The nested project repository at `/Users/boddisuryakathyakeya/PhysioCare/PhysioCare` was verified before Phase 24A.15 work:

| Item | Initial value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Unstaged tracked modifications | 114 |
| Untracked paths | 91 |
| Total dirty paths | 205 |

The state exactly matched the Phase 24A.14 handoff. Existing dirty work was preserved. No checkout, restore, reset, clean, stash, commit, push, or history rewrite was performed.

## 3. Previous evidence reviewed

The following were read and reconciled against current source and tests:

- `PHASE_24A13_CONSOLIDATED_SECURITY_CLOSURE_AND_DEMO_READINESS_REPORT.md`, including its workflow matrix, policy register, eight connected gates, exclusions, and CONDITIONAL GO boundary;
- `PHASE_24A14_LOW_SEVERITY_FINDINGS_REMEDIATION_REPORT.md`, including the bounded legacy catalogue, minimized legacy booking response, and environment-specific documentation policy;
- all four Phase 24A.12 Group A–D reports and their remaining offline/connected conditions;
- `LAB_DEMO.md`, both demo compose files, both PowerShell launchers, both fictional fixture implementations, environment examples, `run.py`, `run_production.py`, FastAPI configuration/startup, Vite configuration, and current demo tests; and
- the existing client-demo/readiness/start documents. Historical documentation was treated as evidence, not as current authorization.

Phase 24A is not represented as fully closed.

## 4. Exact proposed demo workflow scope

This is the **proposed** least-privilege scope. Nothing in this table is approved or executed.

### 4.1 Proposed included scope

| Order | Planned workflow | Exact frontend surface | API/read behavior | Role | Guardrail |
|---:|---|---|---|---|---|
| 1 | Login, account switch, logout | `/login`, `/login/email` and role redirect | `/api/auth/login`, `/me`, `/csrf`, `/logout`; refresh only as needed | Each approved role | Pre-created fictional accounts only; no registration/recovery/verification narrative. |
| 2 | Fictional patient profile view | `/patient/profile` | authenticated own profile | Patient | View only; do not enter edit mode. |
| 3 | Patient overview/history | `/patient/dashboard`, `/patient/history`, `/patient/appointments` | bounded own appointments/history summaries | Patient | Seeded records only; no booking, cancellation, checkout, or status mutation. |
| 4 | Assigned-patient directory/history | `/doctor/patients`, then one assigned patient | assigned-patient directory and bounded history | Clinician | Only the pre-assigned fictional patient; no PDF open, appointment update, care-plan write, or exercise assignment. |
| 5 | Reception patient directory | `/reception/patients` | minimized receptionist directory | Receptionist | View only; no contact edit, booking, cancellation, clinical, or billing access. |
| 6 | Administrator directories | `/admin/patients`, `/admin/doctors` | bounded patient/clinician directories | Administrator | View only; do not open edit, schedule, care, exercise, billing, or staff-creation controls. |
| 7 | Notifications display | role notification route | current recipient's bounded notifications | Approved roles | Display only. Mark-read is excluded unless separately approved as the CSRF smoke mutation. |
| 8 | Read-only report metadata | `/patient/reports` | bounded owner metadata | Patient | Seed metadata with no file; no download/viewer/PDF capability. |

This scope deliberately omits dashboards whose current implementations combine read data with mutation or PDF controls. A successful browser rehearsal must confirm that the operator can follow this exact route sequence without entering an excluded path. If that cannot be done safely, the scope must be reduced again or an independently authorized presentation-only control must be designed; this milestone does not implement one.

### 4.2 Candidate workflow decisions

| Candidate from Phase 24A.15 | Decision | Reason |
|---|---|---|
| Login/logout | Planned | Strong offline session/CSRF/logout evidence; still requires real browser smoke. |
| Patient profile | Planned, view only | Owner-scoped; edit control is outside scope. |
| Patient dashboard/history | Planned, restricted | Use seeded read-only data; exclude all actions. |
| Administrator dashboard/directories | Directories only | Admin dashboard can update appointments and link to excluded billing/actions. |
| Clinician dashboard/assigned patient | Assigned directory/history only | Doctor dashboard exposes appointment mutations and released-PDF controls. |
| Receptionist coordination dashboard | Directory only | Dashboard exposes booking and cancellation and shows home-visit address data. |
| Laboratory dashboard | Excluded | The current screen is an upload/finalization workflow, not a pure read-only view. |
| Notifications | Planned, display only | Recipient scoping is tested; read-state mutation needs separate approval if used. |
| Schedules/appointments | Patient seeded appointment display only | Admin schedule management and appointment mutation remain excluded. |
| Care plan/exercise display | Excluded from first walkthrough | Current product surfaces also expose revision-bearing mutations/progress actions. |
| Report metadata | Planned only for records with no file | Avoids all PDF storage/scanner/download dependencies. |
| Demo entitlement display | Excluded | Admin Demo Services exposes grant/revoke, review, and clinician-assignment mutations. |

## 5. Explicit workflow exclusions

The following are excluded even if a route or control exists:

- public registration, administrator-created patient onboarding, staff creation, password delivery, email/phone verification, recovery, and credential policy claims;
- appointment booking, cancellation, status changes, slot reservation, home-visit requests, entitlement changes, schedule changes, and clinician allocation;
- all Razorpay order, checkout, verification, webhook, refund, reconciliation, billing-success, or payment-readiness activity;
- legacy laboratory booking/catalogue use, despite the Phase 24A.14 offline fixes;
- modern laboratory request creation/review/assignment, laboratory report upload/publication, and the laboratorian dashboard;
- all clinical/laboratory PDF upload, scanner, storage, viewer, download, and publication workflows;
- care-plan creation/update/stage/goal writes, exercise assignment/progress writes, and other transaction-dependent clinical mutations;
- real identities, contact details, addresses, medical histories, records, credentials, databases, storage, or services;
- staging, production, remote databases, public interfaces, external services, and connected-release claims.

The operator must not enable an excluded feature to improve the presentation.

## 6. Approval register

No approver, operator, viewer, machine, or window was supplied. The register therefore fails closed:

| Required approval | Status | Required recorded evidence before execution |
|---|---|---|
| Named demo environment and machine | **PENDING** | Machine identifier, OS, isolation choice, exact database identity, and local-only port plan. |
| Environment owner/operator | **PENDING** | Named accountable operator and contact. |
| Approved viewers | **PENDING** | Named viewers and purpose; no open/public audience. |
| Exact workflow list | **PENDING** | Approval of section 4 or an explicitly smaller list. |
| Fictional dataset | **PENDING** | Approval of section 10, labels, retention, and prohibited fields. |
| Demo account roles/access | **PENDING** | Required roles, pre-creation method, owner/assignment matrix, credential custodian. |
| Network exposure boundary | **PENDING** | Loopback-only or named isolated interface; ports and firewall check. |
| Payments disabled | **PENDING** | Runtime evidence of disabled mode, blank provider credentials, disabled reconciliation. |
| Storage/scanner exclusions | **PENDING** | Confirmation that no PDF/file workflow is included and scanner/storage are not used. |
| Start/stop/abort authority | **PENDING** | Named people authorized to start, stop, and declare an abort. |
| Disposable-data cleanup | **PENDING** | Retention decision, backup prohibition/approval, exact cleanup owner and separately approved procedure. |

An additional operational decision is required: approve either a reduced existing workflow-specific demo or separately authorize design of a unified five-role demo profile. This report does not choose that policy on behalf of the clinic.

## 7. Environment configuration inspection

### 7.1 Dedicated Laboratory Demo

Verified from source:

- MongoDB `127.0.0.1:27018`, database `physiocare_lab_demo`;
- backend `127.0.0.1:8001`, frontend `127.0.0.1:5175`;
- exact frontend CORS origin, development-only mode, disabled Razorpay and reconciliation, blank payment credentials;
- guarded private laboratory storage and quarantine paths;
- environment and database guards execute before MongoDB client construction; and
- Phase 24A.14 makes documentation routes disabled by default in demo mode.

Not suitable for the Phase 24A.15 proposed walkthrough without changing scope: its fixtures provide only patient/admin/laboratorian identities and its supported preparation/rehearsal creates laboratory records and a sample PDF. Those writes and all PDF workflows are excluded here. The demo was not configured, prepared, started, rehearsed, or cleaned.

### 7.2 Dedicated Home Visit Demo

Verified from source:

- MongoDB `127.0.0.1:27019`, database `physiocare_home_visit_demo`;
- backend `127.0.0.1:8002`, frontend `127.0.0.1:5176`;
- exact CORS origin, development-only mode, disabled Razorpay and reconciliation, blank payment credentials;
- fixtures use clearly tagged fictional patient, clinician, and administrator accounts, an entitlement, and a published schedule; and
- startup tracks processes, checks ports, validates container identity/health, and has a scoped stop action.

Limitations: the fixture is a write operation; it lacks receptionist and laboratory accounts and the broader section 10 dataset; it stores a synthetic home address; its Docker volume is persistent; and its launcher has no data-cleanup action. It cannot be treated as disposable without an approved retention/cleanup procedure.

### 7.3 Ordinary development and production/staging templates

Ordinary development is rejected as the demo target. It is guarded to the loopback `physiocare_dev` MongoDB identity and disabled payments/scanner, but it is not a dedicated named demo database. `backend/run.py` falls back to host `0.0.0.0` if the variable is absent, and development documentation is enabled by default. These properties make it unsuitable for a controlled client demo without a dedicated guarded profile.

Staging and production examples were inspected only as source inventories. Neither was loaded or selected. Production has strict database/storage/scanner/proxy requirements and application documentation cannot be enabled. Nothing in this milestone establishes deployability.

### 7.4 Current-machine execution capability

Read-only tool inventory found:

| Capability | Current machine |
|---|---|
| OS | macOS (`Darwin`) |
| PowerShell | Not installed |
| Docker | Not installed |
| Node/npm | npm 11.18.0 available |
| Locked backend Python | Python 3.13.1 available under the recovered test environment |

The supported demo launchers are PowerShell scripts, and both MongoDB compose paths require Docker. Dependencies were not installed and no alternative launcher was invented.

## 8. Isolation and safety assessment

| Requirement | Offline source/test assessment | Current execution status |
|---|---|---|
| Dedicated demo database | Enforced by both strict demo modes | **PLANNED / target not approved** |
| No production database | Demo URLs are exact loopback constants; production reserved identities are rejected | **VERIFIED OFFLINE**, not runtime-verified |
| No production credentials/data | Demo configurations generate local secrets and reject payment credentials; fixture contents are tagged | **VERIFIED OFFLINE**, operator/data approval pending |
| Fictional records only | Existing fixtures are explicitly fictional/tagged; proposed dataset is specified below | **PLANNED**, not created |
| Payments/reconciliation disabled | Both strict demo validators fail on drift | **VERIFIED OFFLINE**, not runtime-verified |
| No webhook/external service | Excluded by plan | **NOT EXECUTED** |
| Loopback-only API/frontend/database | Exact values enforced in strict modes and launchers | **VERIFIED OFFLINE**, not socket/runtime-verified |
| No unapproved storage/scanner | All file workflows excluded; ordinary development requires scanner disabled | **PLANNED**, no storage/scanner accessed |
| Documentation restricted | Demo defaults return 404 for `/docs`, `/redoc`, and `/openapi.json` | **VERIFIED OFFLINE**, browser/proxy unverified |
| Cookie/CSRF model understood | Local development uses non-Secure HTTP-only session cookies, SameSite=Lax, double-submit CSRF, exact CORS, and unsafe-origin rejection | **VERIFIED OFFLINE**, browser behavior unverified |
| Health disclosure | Demo health returns fixed demo identity/database and payment-enabled boolean, not secrets; application mode omits DB name | **VERIFIED OFFLINE**, exposure boundary unverified |
| Fail-safe startup | Demo database/port/payment/CORS/storage drift tests pass | **VERIFIED OFFLINE** |

The configuration can enforce either existing strict demo mode. It cannot currently enforce the complete proposed five-role scope as one supported, prepared environment. That mismatch is a blocker, not an invitation to reuse ordinary development.

## 9. Fictional account matrix

This is a proposal only. No email, password, phone number, address, or account was created.

| Fictional display name | Role | Minimum permitted workflow | Ownership/assignment | Required? |
|---|---|---|---|---|
| Demo Patient Alpha | Patient | Own profile, dashboard, history, appointments, notifications, file-free report metadata | Owns only Demo Patient Alpha records | Yes for proposed scope |
| Demo Clinician One | Doctor/clinician | Assigned-patient directory and file-free bounded history | Assigned only to Demo Patient Alpha | Yes for proposed scope |
| Demo Coordinator One | Receptionist | Read-only minimized patient directory | No clinical, billing, or cross-role access | Yes only if reception view is approved |
| Demo Administrator One | Administrator | Read-only patient and clinician directories | Administrative listing only for the walkthrough | Yes for proposed scope |
| Demo Laboratory Operator One | Laboratorian | No approved Phase 24A.15 workflow | No assignment until a safe read-only laboratory surface is approved | No; reserve for a future approved scope |

If accounts are later approved, authentication aliases must be generated in a non-deliverable demo namespace and credentials must be random, temporary, stored outside the repository/chat/logs, and delivered only to the named operator. Existing fixture credentials must not be copied into documentation.

## 10. Fictional data specification

Every future record must carry a conspicuous demo-only tag and display label. This is a specification, not seeded data.

| Data type | Minimum proposed records | Required content | Explicitly prohibited |
|---|---:|---|---|
| Patient profile | 1 | `Demo Patient Alpha`, demo-only label, no actual contact/address | Real name, phone, email, government ID, actual address |
| Clinician profile/assignment | 1 clinician + 1 assignment | `Demo Clinician One` assigned only to patient Alpha | Real clinician identity or credential claim |
| Appointments | 2–3 read-only historical/upcoming records | Clearly fictional service labels and non-sensitive reasons | Payment success claim, real clinical narrative, mutation-dependent state |
| Schedules | Minimal display prerequisite if needed | Clearly provisional demo times | Claimed clinic hours or availability commitment |
| Care plans | 0 for first walkthrough | Not required because route is excluded | Clinical instructions presented as real advice |
| Exercise assignments/progress | 0 for first walkthrough | Not required because route is excluded | Real treatment/progress data |
| Laboratory requests | 0 for first walkthrough | Laboratory workflow is excluded | PDF/file keys, results, specimens, provider IDs |
| Notifications | 2–3 per demonstrated account | Generic fictional reminders/status text | Contact information, tokens, real patient references |
| Report metadata | 1 file-free metadata record | Demo-only title/category/date; `hasFile=false` or equivalent | PDF, storage key, detailed medical history |
| Demo entitlements | 0 for first walkthrough | Admin entitlement screen is excluded | Payment/subscription implication |

The existing Home Visit fixture's synthetic address and entitlement are not required by this narrower proposal. If home visits are later approved, their inclusion requires a revised dataset approval.

## 11. Offline workflow verification matrix

All results are offline tests against mocks/in-process clients; none is browser evidence.

| Workflow | Frontend/API evidence | Required role/data | Fresh outcome | Known limitation | Eligibility |
|---|---|---|---|---|---|
| Login/logout/session | login/logout rendered tests; auth rate/session/cache suites; `/auth/*` | Pre-created role account | **PASS in 409 focused suite and full suites** | No real cookie/browser/account switching | **PLANNED, approval/browser gated** |
| Patient profile | `/patient/profile`; own-profile contracts | Fictional patient profile | **PASS** | Edit control exists; view-only discipline unverified | **PLANNED, view only** |
| Patient dashboard/history | bounded recent/history tests | Owned fictional appointments | **PASS** | Empty/realistic rendering needs approved seed/browser | **PLANNED** |
| Admin directories | bounded patient/doctor/staff tests | Admin + fictional profiles | **PASS** | Staff page and directory controls expose excluded mutations | **PATIENT/DOCTOR DIRECTORIES ONLY** |
| Clinician assignment | clinician-directory/history/authorization/query tests | Assigned patient | **PASS** | Doctor dashboard/history exposes status/PDF controls | **DIRECTORY/HISTORY ONLY; browser gated** |
| Reception coordination | receptionist projection/query/frontend tests | Receptionist + minimized directory | **PASS** | Dashboard contains cancel/book actions and address display | **DIRECTORY ONLY; browser gated** |
| Laboratory requests | role, assignment, partial-failure tests | Patient/admin/lab assignment | **PASS offline** | Current lab dashboard is upload-oriented; files excluded | **EXCLUDED** |
| Notifications | recipient, unread, pagination, UI tests | Recipient-specific records | **PASS** | Mark-read is a write | **DISPLAY ONLY** |
| Appointments/schedules | ownership, revision, conflict, bounded-list tests | Owned/assigned records | **PASS** | Index/browser/transaction evidence incomplete | **PATIENT READ ONLY** |
| Care plan/exercise display | ownership, revision, pagination, Group D tests | Seeded clinical records | **PASS offline** | Screens expose excluded transaction-dependent actions | **EXCLUDED FROM FIRST WALKTHROUGH** |
| Report metadata | owner/search/pagination/cache tests | File-free metadata | **PASS** | Existing pages can expose PDF controls when a file exists | **PLANNED ONLY WITH NO FILE** |
| Demo entitlements | Group A and home-visit tests | Demo DB/entitlement | **PASS offline** | UI contains grant/revoke/review/assignment actions | **EXCLUDED** |
| Demo isolation/startup | lab/home/development guard tests | Exact configuration | **PASS** | No runtime process/socket/database evidence | **OFFLINE VERIFIED ONLY** |

The focused selection executed 409 tests across authentication, sessions, cache, patient/admin/clinician/reception workflows, appointments, notifications, laboratory requests, care/exercise behavior, both demo guards, Groups A–D, and Phase 24A.14. All 409 passed.

## 12. Browser smoke-test results

**Status: BLOCKED / NOT PERFORMED.**

The gated browser phase was not authorized because every approval in section 6 is pending, no target environment was selected, no fictional dataset/accounts were approved, and the current machine lacks the supported launcher/runtime prerequisites. Therefore:

- no backend, frontend, MongoDB, container, or browser was started;
- no process/port ownership was created or recorded;
- no login, role switch, CSRF mutation, route denial, ownership negative, or documentation-route browser check was performed; and
- no screenshot or browser artifact exists.

## 13. Browser limitations

Offline tests do not close connected gate 6. A future approved smoke test must record time, machine/environment identifier, browser/version, fictional role, route, expected/actual behavior, result, and a redacted artifact reference.

It must specifically verify patient cross-access denial, clinician unassigned-patient denial, receptionist field minimization, unauthenticated denial, session revocation/account switching, docs 404 behavior, disabled payment behavior, and absence/non-use of PDF workflows. It must stop if any step requires an unapproved record mutation.

No credential, token, cookie, internal identifier, patient data, or raw response body may be captured in retained evidence.

## 14. Planned demo runbook

This runbook is **PLANNED**. It must not be executed until the approvals and environment blocker are resolved.

### Before the demo

1. Attach the completed approval register and name the start/stop/abort authority.
2. Select an approved dedicated guarded demo profile and compatible machine. Do not use ordinary development.
3. Confirm the exact database constant, loopback MongoDB/API/frontend bindings, exact CORS origin, and owned ports before startup.
4. Confirm provider credentials are blank, `RAZORPAY_MODE=disabled`, reconciliation is false, scanner/file workflows are excluded, and documentation is disabled.
5. Obtain separate authorization for account/data preparation. Run only the approved idempotent/tagged preparation procedure; record counts, never credentials.
6. Verify all data is fictional/tagged and no unexpected collection/file/record exists.
7. Start only through the approved supported launcher. Record process IDs and port owners.
8. Verify the health response's demo identity and `payments_enabled=false`; check `/docs`, `/redoc`, and `/openapi.json` return 404.
9. Perform the negative authorization smoke before admitting viewers.
10. Open a clean browser profile and confirm no prior cookies/session remain.

The current macOS machine cannot use the existing PowerShell/Docker launcher path. Do not improvise a manual MongoDB or broad-interface start. Either approve a compatible machine or separately authorize implementation/review of an equivalent safe launcher.

### During the demo

1. State that the environment and data are fictional, local, disposable only under the approved cleanup policy, and not production.
2. Log in as Demo Patient Alpha; show profile, dashboard, bounded history/appointments, notifications, and file-free report metadata. Do not edit, cancel, book, pay, or open a file.
3. Log out and verify protected content disappears.
4. Log in as Demo Clinician One; show the assigned-patient directory and the single approved patient's bounded history. Do not use the doctor dashboard, mutate an appointment, or open a report.
5. Log out. If reception is approved, log in as Demo Coordinator One and show only the minimized patient-directory fields. Do not edit contact details or open the coordination dashboard.
6. Log out and log in as Demo Administrator One; show only the bounded patient and clinician directories. Do not enter staff, billing, schedule, editing, care, exercise, laboratory, or entitlement controls.
7. Log out and confirm server-side revocation/account switching.
8. Explain the intentionally excluded capabilities: onboarding, payments, laboratory workflow, PDFs, clinical mutations, connected services, staging, and production.

### After the demo

1. Stop the frontend and backend using the tracked approved launcher action.
2. Stop only the dedicated demo MongoDB/container; verify all approved ports and process IDs are gone.
3. Preserve only approved redacted logs and the approval/smoke result.
4. Record incidents and deviations. Do not repair or rerun beyond the approved window.
5. Do not delete records, volumes, credentials, or logs automatically. Execute cleanup only after separate target-specific approval and validation.

## 15. Abort and recovery procedures

Abort immediately if:

- the database, environment selector, process, port, or interface differs from the approval;
- a production/staging credential, database, record, hostname, export, or patient identity appears;
- a provider key is present, payments/reconciliation become enabled, or a payment route is invoked;
- the application listens beyond the approved loopback/isolated boundary;
- `/docs`, `/redoc`, or `/openapi.json` violates the approved demo policy;
- authentication, logout, role, ownership, assignment, field-minimization, or cache isolation fails;
- a PDF/file/storage/scanner or other excluded control is required or inadvertently exercised;
- unexpected sensitive data appears in UI, logs, screenshots, or responses;
- an unapproved write is required; or
- any operator cannot positively confirm the environment identity and safety.

On abort: stop the walkthrough; if safe, stop only the affected tracked demo service; keep the dedicated database untouched; preserve redacted diagnostics; do not attempt unapproved repair, cleanup, deletion, or restart; notify the named owner and record the incident for review.

## 16. Fresh test and quality results

| Verification | Fresh result |
|---|---|
| Focused offline demo/workflow backend selection | **409 passed**, 1 TestClient deprecation warning |
| Full backend excluding the local Unix-socket file | **1,123 passed, 3 connected-only skipped**, 1 warning |
| Fake local Unix-socket scanner protocol file | **12 passed** |
| Reconciled complete backend | **1,135 passed, 3 connected-only skipped** |
| Full frontend | **167 passed** |
| Frontend lint | PASS |
| Vite production build to `/private/tmp` | PASS — Vite 8.3.5, 1,837 modules |
| Bundle budget | PASS — 73 JS/CSS assets; max JS 373,260 / 460,800 bytes; max CSS 254,338 / 307,200 bytes |
| In-memory Python compilation | PASS — 171 files |
| Dependency-lock tests | **2 passed** |
| `pip check` | PASS — no broken requirements |
| Frontend offline npm audit | PASS — 0 cached vulnerabilities |
| Redacted current-tree secret scan | Six known synthetic `generic-api-key` fixtures only |
| `git diff --check` | PASS |

The three skips are guarded connected-only MongoDB tests. The socket file used only a temporary fake local Unix-domain scanner and did not contact ClamAV. The six secret-scan fixtures are five in `test_api_contract.py` and one in `test_schedule_fallback_guard.py`; no secret value was emitted.

## 17. Remaining policy decisions

- approve the exact reduced workflow list or authorize a different scope;
- choose a compatible dedicated environment/machine or authorize design/review of a unified guarded demo profile and launcher;
- name the operator, viewers, environment owner, start/stop/abort authority, and credential custodian;
- approve the fictional dataset, retention, backup prohibition/allowance, and cleanup procedure;
- decide whether a safe notification mark-read action will be the local CSRF mutation smoke;
- retain existing clinic decisions for onboarding, password handling, invitations, verification/recovery, duplicate accounts, and audit;
- approve semantic clinical content limits before any richer clinical narrative is seeded; and
- decide whether documentation may ever be opt-in enabled in a demo; the proposed safe setting is disabled.

## 18. Remaining connected release gates

All eight connected gates remain **BLOCKED**:

1. real multi-clinician/role authorization and transaction behavior;
2. real MongoDB plans, scale, latency, BSON, pool, and concurrency;
3. deployed indexes and uniqueness;
4. real ClamAV interoperability;
5. private storage integration and access;
6. complete browser end-to-end connected journeys;
7. proxy/TLS/cookie/cache/CORS/body-limit/docs exposure and webhook agreement; and
8. backup/restore and recovery evidence.

A future narrow local smoke is a demo prerequisite but will not close gate 6. Phase 24A.15 does not alter the Group B provider/proxy or clinical-limit conditions, Group C connected query conditions, or Group D replica-set transaction conditions.

## 19. Demo readiness decision

### A. Demo preparation: PARTIALLY PREPARED

Prepared offline:

- exact reduced scope and exclusions;
- approval register;
- environment safety inspection;
- fictional account/data proposal;
- offline workflow matrix;
- runbook and abort procedure; and
- fresh regression/quality evidence.

Not prepared/executed:

- approved environment/machine and compatible launcher;
- named people and authority;
- approved/pre-created accounts and dataset;
- runtime database/payment/network/docs verification; and
- browser smoke and redacted evidence.

### B. Actual controlled local demo authorization: NO-GO

The demo is not currently authorized. All required approvals are pending, the current machine cannot run the supported launchers, no unified approved five-role environment exists, and the mandatory browser smoke has not occurred.

This NO-GO can be reconsidered only after those exact conditions are satisfied. Connected client demo remains NO-GO and production readiness is not claimed.

## 20. Final repository state

| Item | Final value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Unstaged tracked modifications | 114 |
| Untracked paths | 92 |
| Total dirty paths | 206 |

Phase 24A.15 intentionally changed no application, environment, fixture, dependency, or test file; this report is its only repository artifact. The one-path increase is this untracked report. All 205 pre-existing dirty paths remain preserved.

Temporary build and scan outputs are under `/private/tmp` and are not repository artifacts.

## 21. External-service access statement

No application service, frontend server, backend server, browser workflow, MongoDB instance, container, Razorpay endpoint, webhook, real ClamAV daemon, external storage, staging/production system, or public interface was started or accessed.

No account, credential, file, fixture, record, database, index, migration, payment, refund, reconciliation event, deployment, or infrastructure resource was created, changed, or deleted. Tests used mocks, in-process clients, temporary build files, and one fake local Unix-domain scanner protocol server only.

## 22. Phase 24B status

**Phase 24B remains BLOCKED / NOT STARTED.**

Stop after Phase 24A.15. The next action is independent review and explicit human approval of the environment, people, dataset, workflow scope, and execution path—not connected execution or Phase 24B implementation.
