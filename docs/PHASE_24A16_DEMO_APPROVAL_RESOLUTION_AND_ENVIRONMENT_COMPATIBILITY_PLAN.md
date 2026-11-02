# Phase 24A.16 — Demo Approval Resolution and Environment Compatibility Plan

Assessment date: 2026-11-02  
Branch: `codex/physiocare-integration-2026-10-31`  
Baseline HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

Phase 24A.16 converts the Phase 24A.15 demo blockers into an ordered approval and environment plan. It is planning evidence only: no application, database, container, browser, launcher, fixture, account, credential, or external service was started or changed.

All **11 of 11 approval requirements remain PENDING**. The repository contains proposals and technical guards, but no signed approval, named operator/viewer, approved machine, approved dataset, or execution authorization.

The application has five relevant internal role identifiers: `patient`, `doctor`, `receptionist`, `laboratorian`, and `admin`. Authentication is shared cookie-session authentication with server-side session validation and CSRF on unsafe methods; authorization then differs by route role, patient ownership, clinician assignment, and laboratory assignment.

Neither current demo environment provides a coherent five-role presentation:

- the Laboratory Demo covers patient, laboratorian, and administrator around request/PDF workflows that Phase 24A.15 excludes;
- the Home Visit Demo covers patient, doctor, and administrator around home-visit fixtures, but lacks receptionist/laboratorian coverage and has no data-cleanup action; and
- ordinary development is not a demo environment and must not be used as a substitute.

**Recommended architecture: Option A, a future dedicated unified local demo environment**, with one isolated fictional-data database, all five least-privilege accounts, a presentation-only/read-only route policy, disabled payment/file integrations, one guarded cross-platform lifecycle, and deterministic tagged fixtures/cleanup. This is a recommendation, not approval to implement it.

**Operating-system recommendation: remain blocked on the current macOS machine and separately authorize a future macOS/cross-platform launcher implementation if this machine is the intended host.** An approved Windows machine can execute the existing PowerShell launchers for their existing workflow-specific scopes, but it does not solve the unified five-role gap. Ad hoc FastAPI/Vite startup on macOS is not an approved supported path because it bypasses launcher safety and no supported local MongoDB lifecycle is available.

The strict read-only shortlist can meaningfully represent patient and assigned-clinician views with carefully shaped fictional records. Receptionist, administrator, and laboratorian screens currently expose mutation or PDF controls; they cannot be described as pure read-only pages. The five roles can be pre-created for later authorization tests, but three roles need a future presentation-only surface or an explicit stakeholder acceptance of mixed pages plus browser-verified operator restrictions.

Fresh offline evidence passed: 409 planning-relevant backend tests, all 167 frontend tests, lint, production build, bundle budget, compilation, dependency-lock, dependency-health, offline audit, secret scan, and whitespace checks.

- **Demo preparation:** PARTIALLY PREPARED.
- **Actual controlled local demo authorization:** NO-GO.
- **Connected client demo:** NO-GO.
- **Production readiness:** not claimed.
- **Phase 24B:** BLOCKED / NOT STARTED.

## 2. Initial repository state

The nested project repository was verified before Phase 24A.16 work:

| Item | Initial value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Unstaged tracked modifications | 114 |
| Untracked paths | 92 |
| Total dirty paths | 206 |

This matched the Phase 24A.15 handoff. Existing work was preserved. No reset, clean, restore, checkout, stash, commit, push, or history rewrite was performed.

## 3. Phase 24A.15 evidence reviewed

The complete Phase 24A.15 report was treated as authoritative for the approval register, reduced route scope, environment inventory, current-machine limitations, fictional account/data proposal, browser gate, and NO-GO decision.

It was reconciled with:

- Phase 24A.13's workflow, clinic-policy, demo-blocker, and eight-gate matrices;
- Phase 24A.14's legacy laboratory and documentation-exposure changes;
- all four Phase 24A.12 Group A–D reports;
- current role/authentication/route source;
- both demo validators, launchers, compose files, fixtures, and static tests;
- current frontend pages, including their read APIs and mutation/file controls; and
- environment, staging, production, security, demo, and operational documentation.

No previous report or inventory was modified. Phase 24A is not represented as fully closed.

## 4. All 11 approval items

No formal approval IDs existed in Phase 24A.15. The source ordinals below preserve its exact order instead of inventing identifiers. No responsible person was documented, so every owner is **UNASSIGNED**.

| Source ordinal and original requirement | Why required | Responsible role | Required evidence | Affected workflow | Before prepare | Before startup | Before presentation | Status | Next action |
|---|---|---|---|---|---:|---:|---:|---|---|
| 1. Named demo environment and machine | Prevents use of ordinary development, production, or an incompatible host | Project/environment owner — **UNASSIGNED** | Machine ID/OS, chosen architecture, exact database, ports, interface, launcher | All | Yes | Yes | Yes | **PENDING** | Select unified architecture and host; record written approval. |
| 2. Environment owner/operator | Establishes accountability for configuration and evidence | Project owner — **UNASSIGNED** | Named operator, contact, responsibility/window | All | Yes | Yes | Yes | **PENDING** | Nominate one accountable operator and reviewer. |
| 3. Approved demo viewers | Limits even fictional clinical access | Clinic/project authority — **UNASSIGNED** | Named viewers, purpose, least-privilege viewing rule | Presentation | No | No | Yes | **PENDING** | Produce viewer roster and approval. |
| 4. Approved workflow list | Prevents accidental demonstration of incomplete/mutating features | Clinic/product/security authority — **UNASSIGNED** | Signed route-level included/excluded scope | Every role route | Yes | Yes | Yes | **PENDING** | Approve section 12 or a smaller list. |
| 5. Fictional dataset approval | Prevents realistic identifiers and unsupported clinical/payment claims | Clinic/data owner — **UNASSIGNED** | Record specification, labels, retention, prohibited fields | All displayed records | Yes | Yes | Yes | **PENDING** | Review and approve section 15. |
| 6. Demo account roles and access | Establishes five least-privilege identities and relationship boundaries | Security/account owner — **UNASSIGNED** | Role matrix, creation method, assignment map, activation and credential custodian | Authentication and role switching | Yes | Yes | Yes | **PENDING** | Resolve account policy and approve pre-creation. |
| 7. Network exposure boundary | Prevents public/LAN exposure | Environment/security owner — **UNASSIGNED** | Exact loopback/isolated interface, ports, firewall/port evidence | All services | No | Yes | Yes | **PENDING** | Approve loopback-only boundary and verification method. |
| 8. Payment-disabled confirmation | Prevents provider or reconciliation activity | Payment/security owner — **UNASSIGNED** | Blank provider credentials, disabled mode/reconciliation, runtime health evidence | Booking/billing-adjacent pages | Yes | Yes | Yes | **PENDING** | Approve exclusion and runtime check. |
| 9. Storage and scanner exclusions | Prevents unverified file/PDF dependencies | Security/storage owner — **UNASSIGNED** | Signed PDF/file exclusion; no scanner/storage use | Reports and laboratory | Yes | Yes | Yes | **PENDING** | Approve metadata-only/no-file scope. |
| 10. Start, stop and abort authority | Ensures safe lifecycle and immediate response | Operational owner — **UNASSIGNED** | Named start/stop/abort people and decision rules | Environment lifecycle | No | Yes | Yes | **PENDING** | Assign authority and rehearsal observer. |
| 11. Disposable-data cleanup approval | Prevents unapproved deletion and ambiguous retention | Data/operational owner — **UNASSIGNED** | Retention choice, targets, validation, owner, confirmation, evidence | Accounts, DB, logs, credentials | Yes | No | Yes | **PENDING** | Approve retain-or-clean policy and separately reviewed procedure. |

Status count: **11 PENDING; 0 APPROVED – EVIDENCE REQUIRED; 0 APPROVED – VERIFIED; 0 REJECTED; 0 NOT APPLICABLE – JUSTIFIED.**

## 5. Approval dependency matrix

### 5.1 Classification

| Dependency class | Approval source ordinals |
|---|---|
| Environment and infrastructure | 1, 7, 8, 9 |
| Security and access control | 3, 6, 7, 8, 9 |
| Demo workflow and feature scope | 4 |
| Fictional accounts and dataset | 5, 6 |
| Operational ownership and recovery | 2, 10, 11 |
| Client-facing authorization | 3, supported by 1–11 |

### 5.2 Required order

| Activity | Required approvals before activity |
|---|---|
| Design/implement a future environment or launcher | 1, 2, 4, 7, 8, 9, 10, plus separate implementation authorization |
| Prepare environment configuration | 1, 2, 4, 7, 8, 9, 10 |
| Create accounts or fictional data | 1, 2, 4, 5, 6, 8, 9, 11 |
| Start services | 1, 2, 4, 7, 8, 9, 10 |
| Run narrow browser smoke | 1, 2, 4, 5, 6, 7, 8, 9, 10 |
| Conduct client presentation | all 11 plus successful recorded smoke review |
| Clean data/credentials | 2, 10, 11 and a target-specific final confirmation |

Priority chain: approve architecture/machine and owner first; approve route scope and boundaries second; approve accounts/dataset/retention third; implement and independently verify the approved environment fourth; run the browser smoke fifth; approve named viewers and the presentation window last.

## 6. Approval request package

The following package is ready to share but has not been sent or approved:

> **Request:** Approve planning and later controlled execution of a loopback-only PhysioCare demonstration using one dedicated fictional-data environment. The purpose is to show a limited read-only product journey, not staging or production readiness.
>
> **Proposed participants:** one named environment owner/operator, one named start/stop/abort authority, approved clinic/project reviewers, and approved client viewers. Names remain to be supplied by the project owner.
>
> **Data and accounts:** five pre-created least-privilege fictional accounts (`patient`, `doctor`, `receptionist`, `laboratorian`, `admin`) with explicit ownership/assignment. No registration or onboarding occurs during the presentation. All data is tagged fictional and contains no real names, contacts, addresses, identifiers, histories, credentials, or files.
>
> **Proposed included scope:** login/logout; patient own-profile and completed-history views; assigned-clinician directory/history; and only those additional role views that receive a technically safe presentation-only state before approval.
>
> **Excluded:** account creation/recovery/verification; payments and billing success; laboratory mutations; PDFs, scanner, and storage; appointment/care/exercise mutations; external services; production/staging data; public exposure.
>
> **Lifecycle:** use only the approved guarded launcher on the approved host; verify exact database, loopback ports, disabled payments, docs 404, and fictional records; stop on any identity/boundary deviation; stop tracked services afterward; never delete data without separate cleanup approval.
>
> **Approval requested now:** approve or reject the unified architecture, intended machine, reduced route scope, five-role account/data specification, named owners/viewers, loopback boundary, payment/file exclusions, browser-smoke plan, and retention/cleanup policy. Approval of this package does not itself authorize startup; implementation and smoke evidence require subsequent review.

## 7. Five-role application permission analysis

All roles use `/api/auth/login`, cookie-based access/refresh sessions, server-side session records, `/api/auth/me`, CSRF on unsafe methods, and `/api/auth/logout`. Internal identifiers are source evidence, not display-label guesses.

| Display role | Internal ID | Read permissions relevant to demo | Boundary | Data dependency | Excluded actions/controls |
|---|---|---|---|---|---|
| Patient | `patient` | own profile, own bounded appointment/history, own notifications, own file-free report metadata | Authenticated user resolves one patient profile; owner-only APIs | Patient profile and owned records | profile edit, booking/cancel, payment, requests, files, progress mutations |
| Clinician | `doctor` | assigned-patient directory and assigned patient's bounded history | `doctor` route plus assignment service/repository checks | Doctor profile and explicit assignment through appointment/history relationships | status updates, care/exercise writes, report authoring/PDF access |
| Receptionist | `receptionist` | minimized reception patient directory and coordination data | Role-specific schemas exclude clinical/billing fields | Pre-created receptionist; fictional directory records | contact edit, booking, cancellation, home-address coordination in first scope |
| Laboratory staff | `laboratorian` | assigned laboratory request list | Role plus laboratory assignment | Pre-created laboratorian and assigned request | current screen exposes finalized-PDF upload; no pure read-only surface exists |
| Administrator | `admin` | bounded patient/doctor/staff directories and analytics | Admin role; broad administrative access | Pre-created admin and directory profiles | edits, staff creation, schedules, billing, booking, lab review/publication, entitlements |

The role model stores `role` as a string, while account-creation schemas restrict staff creation to `doctor`, `admin`, `receptionist`, or `laboratorian`; public registration supplies the patient path. The demo must not use either creation workflow during presentation.

## 8. Existing demo-environment comparison

| Capability | Laboratory Demo | Home Visit Demo | Proposed unified five-role demo |
|---|---|---|---|
| Actual purpose | Isolated modern laboratory request/rehearsal | Isolated home-visit entitlement/schedule workflow | Restricted cross-role read-only presentation |
| Patient | Yes, fixture | Yes, fixture | Required |
| Clinician (`doctor`) | No fixture/workflow | Yes, fixture | Required |
| Receptionist | No fixture/workflow | No fixture/workflow | Required |
| Laboratory staff (`laboratorian`) | Yes, fixture | No fixture/workflow | Required |
| Administrator | Yes, fixture | Yes, fixture | Required |
| Database | `physiocare_lab_demo` | `physiocare_home_visit_demo` | New dedicated identity required; name not yet approved |
| MongoDB | `127.0.0.1:27018` | `127.0.0.1:27019` | Loopback-only required; port undecided |
| API/frontend | `8001` / `5175` | `8002` / `5176` | Dedicated strict ports required; undecided |
| Payment | Guarded disabled, credentials blank | Guarded disabled, credentials blank | Guarded disabled/blank required |
| Documentation | Disabled by demo default | Disabled by demo default | Disabled required |
| Fixture assumptions | Tagged users/request/sample PDF; prepare/rehearse writes | Tagged patient/doctor/admin, address, entitlement, schedule; prepare writes | Tagged minimal read-only consistent graph; no files/payments |
| Startup | PowerShell; separate Docker compose; foreground API/frontend | PowerShell-managed Docker/process lifecycle | One reviewed cross-platform lifecycle required |
| Cleanup | Tagged cleanup command with confirmation; not automatic | Stops services; no data cleanup action | Separate validated/approved cleanup required |
| Workflow scope | Laboratory mutations/PDF | Home-visit preparation/coordination | Read-only route-state whitelist |
| Designed for five roles | No | No | Yes, planned only |

The two existing environments use distinct ports, databases, and container identities, so source suggests technical port coexistence. Simultaneous operation is **NOT VERIFIED**, not documented as a combined product, and would create two unrelated account/data/session contexts. They must not share a database or be automatically combined.

## 9. Recommended demo architecture

| Option | Isolation | Role/data consistency | Startup/compatibility | Reproducibility/maintenance | Mixing risk | Decision |
|---|---|---|---|---|---|---|
| A. Dedicated unified local demo | Strong if a new exact validator pins DB, ports, CORS, disabled integrations, docs, and tags | Best: one five-role graph | Requires future launcher and current-machine decision | One lifecycle and fixture package; new code/tests to maintain | Lowest when guarded | **RECOMMENDED, NOT APPROVED** |
| B. Separate Laboratory and Home Visit demos | Each is strongly isolated | Poor: roles and data split across two DBs; no receptionist | Existing Windows/PowerShell routes, multiple ports/profiles | Two lifecycles, credentials, fixtures, stops, evidence sets | High operator/context confusion | Not recommended for five-role demo; acceptable only for separately approved narrow demos |
| C. Ordinary development/manual commands | Development DB guard exists, but not a named demo and host fallback can be broad | Could contain five roles, but risks mixing developer data | Commands exist but no safe supported macOS DB/process lifecycle | Ad hoc and hard to reproduce | Highest | **REJECTED AS DEMO APPROACH** |

Option A should include an exact environment identity, loopback database/API/frontend constants, disabled payment/reconciliation/scanner/file features, default-disabled docs, no trusted proxy, one tagged fictional graph, idempotent preflight/prepare, inventory-only verification, tracked processes, fail-closed stop, and separately confirmed cleanup.

No Option A code or configuration was implemented in this milestone.

## 10. macOS versus Windows compatibility assessment

| Host choice | Evidence | Advantages | Limitations/risks | Approval needed |
|---|---|---|---|---|
| Approved Windows machine | Existing `.ps1` launchers use Windows PowerShell process/network commands and expected Windows venv paths; Docker compose supplies MongoDB | Uses reviewed workflow-specific safety checks | Still only separate Lab/Home scopes; requires Docker, Python/Node dependencies, protected local storage, and approved host | Machine/environment, operator, software, ports, data, network, lifecycle |
| Current macOS machine with manual commands | Python 3.13.1 and npm 11.18.0 were available in Phase 24A.15; FastAPI/Vite commands are portable in principle | Avoids another host | `pwsh` and Docker absent; no documented macOS demo route; no approved MongoDB lifecycle; manual commands bypass port/process/config checks | Not acceptable without new implementation/review |
| Future macOS/cross-platform launcher | Feasible as a separately scoped implementation | Matches current host and can encode unified controls once | Must be designed, tested, independently reviewed, and paired with an approved database lifecycle | Explicit architecture and implementation authorization |

PowerShell is an implementation choice, but its checks are security-relevant and cannot simply be omitted. Docker is not logically required by FastAPI/Vite, but it is essential to the repository's currently documented isolated MongoDB lifecycle. No safe supported replacement is present.

**Portability decision:** remain blocked pending the architecture/host decision. If the current Mac is the intended machine, authorize a future macOS/cross-platform launcher; do not use manual startup. An approved Windows machine is a temporary option only for one existing narrow environment, not the recommended unified demo.

## 11. Startup launcher inspection

### Laboratory Demo

- `LabDemo.ps1` supports `configure`, `start`, `prepare`, `rehearse`, `cleanup`, and `frontend`.
- The documented database command is `docker compose -f backend\docker-compose.lab-demo.yml up -d`.
- The launcher selects the protected environment file, clears conflicting process variables, validates the backend Python, pins API `127.0.0.1:8001`, and pins Vite `127.0.0.1:5175`.
- `prepare`, `rehearse`, and `cleanup` are database/file operations and require their explicit confirmations; they remain prohibited here.
- API/frontend processes run in the foreground; the script has no combined tracked start/stop action. MongoDB shutdown must use the matching compose target after approval. Cleanup is not a service-stop substitute.

### Home Visit Demo

- `HomeVisitDemo.ps1` supports `start`, `backend`, `frontend`, `verify`, and `stop`.
- `start` validates ports/container ownership, starts only the dedicated compose MongoDB, and waits for health.
- `backend` and `frontend` use tracked processes pinned to `127.0.0.1:8002` and `127.0.0.1:5176`.
- `verify` checks the dedicated DB service, frontend configuration, health identity, database name, and `payments_enabled=false`.
- `stop` terminates only tracked processes and stops only the validated dedicated MongoDB container. It does not delete the persistent volume/data.

Neither launcher is documented or statically tested as a macOS path. Neither provides the proposed unified role/data environment. No launcher was run.

## 12. Final read-only workflow shortlist

The list below is narrower than the original Phase 24A.15 candidates. “Safe state” means a specific page state, not a claim that the whole page is read-only.

| Order | Role | Route / state | Required fictional record | Read APIs | Controls/navigation to avoid | Include? |
|---:|---|---|---|---|---|---|
| 1 | Patient | `/patient/profile`, display state | Patient Alpha profile | `/api/auth/me` profile data | Edit form and PATCH submit | **Conditional** |
| 2 | Patient | `/patient/history`, completed-only filter | 2 completed owned appointments | bounded `/api/appointments/me/history` | Cancel control; suppress by using non-cancelable completed records | **Conditional** |
| 3 | Patient | `/patient/reports`, file-free record | 1 metadata record with no file | bounded `/api/reports/me` | Laboratory link; download appears only when file exists | **Conditional** |
| 4 | Doctor | `/doctor/patients` | Explicit assignment to Patient Alpha | assigned patient directory | Care-plan/exercise navigation; use only View history | **Conditional** |
| 5 | Doctor | `/doctor/patients/{patientId}`, no reports | Assigned patient's completed appointments, zero PDF reports | bounded assigned history | PDF buttons absent only when no report records | **Conditional** |
| 6 | Receptionist | `/reception/patients` | Patient Alpha minimum contact row | minimized reception directory | Edit contact is exposed for populated rows | **Not safe as pure read-only; gap** |
| 7 | Administrator | `/admin/patients` or `/admin/doctors` | Fictional profiles | bounded directories | Edit/history/care/exercise or schedule/profile-edit controls are exposed | **Not safe as pure read-only; gap** |
| 8 | Laboratorian | `/laboratory/dashboard` | Assigned request | assigned request list | Upload/replace finalized PDF is core page functionality | **Excluded; no safe meaningful state** |
| 9 | Any approved role | notifications in an all-read state | Generic recipient notifications | list and unread count | PATCH mark-read/read-all; use all-read seed | **Conditional after browser verification** |
| 10 | All five roles | login/logout only | Five pre-created accounts | auth session APIs | Registration, recovery, onboarding | **Conditional; does not by itself demonstrate role workflow** |

The final first presentation should include only rows 1–5 and possibly 9 after a successful smoke. Rows 6–8 are product gaps for a technically enforced read-only five-role demo. Stakeholders must not be told that five role workflows are covered merely because five accounts can log in.

## 13. Exact route and mutation-control analysis

| Page | Inspected behavior | Mutation/file exposure | Planning conclusion |
|---|---|---|---|
| Patient profile | Profile display and edit form share one page | `PATCH /users/me/patient-profile` on submit | Display state only; do not enter edit mode. |
| Patient dashboard | Reads upcoming appointments, lab/home requests | `POST` cancellation for eligible appointments; links into booking/request flows | Omit dashboard or seed no cancelable upcoming item. |
| Patient history | Bounded status-filtered list | `POST` cancellation for cancelable rows | Completed-only fictional records suppress unsafe action. |
| Patient appointments | Bounded upcoming view | Navigation to booking | Omit from first walkthrough. |
| Doctor directory | Assigned minimum-field list | Links to history, care plan, exercise management | Use only history navigation. |
| Doctor patient history | Bounded appointments and published reports | GET PDF-file action opens viewer | Seed zero report/file rows; show appointment history only. |
| Reception patient directory | Minimized data | Contact-edit form and `PATCH` are available | No technically pure read-only populated state. |
| Reception dashboard | Bounded schedule/requests | Booking navigation and appointment-cancel `POST` | Exclude. |
| Admin patient/doctor directories | Bounded lists | Editing, schedules, care/exercise navigation and PATCH | No technically pure read-only populated state. |
| Laboratorian dashboard | Assigned requests | PDF file input and `PUT` upload/replace | Exclude. |
| Notifications | Bounded list/count | PATCH one/all read | Only all-read view state, after smoke. |
| Patient reports | Bounded metadata/search | Preview state; file download when `hasFile` | Use file-free metadata only; no laboratory link navigation. |

Background reads remain authenticated and private/no-store under existing middleware. Pagination controls and search forms are read operations, but browser evidence is still required for actual route behavior and account switching.

## 14. Fictional account matrix

No account, alias, or credential was generated.

| Fictional display name | Internal role | Purpose | Required permission/boundary | Included routes | Excluded actions | Required pre-created state |
|---|---|---|---|---|---|---|
| Demo Patient Alpha | `patient` | Owner-view journey | Own profile/records only | profile, completed history, file-free reports, optional all-read notifications | all edits, booking/cancel/payment/request/file actions | Active user + one patient profile |
| Demo Clinician One | `doctor` | Assigned-view journey | Assigned only to Patient Alpha | assigned directory and file-free patient history | status/care/exercise/report/file writes | Active user + doctor profile + explicit assignment |
| Demo Coordinator One | `receptionist` | Role-boundary/account-switch proof | Minimized reception schema only | Login/logout; populated directory withheld until safe surface exists | edit, booking, cancellation, clinical/billing data | Active user; no extra records required initially |
| Demo Laboratory Operator One | `laboratorian` | Role-boundary/account-switch proof | Assigned laboratory data only | Login/logout only until safe page exists | request mutation and all PDF actions | Active user; no request assignment initially |
| Demo Administrator One | `admin` | Role-boundary/account-switch proof | Administrative role without presentation mutations | Login/logout; directories withheld until safe surface exists | edits, onboarding, schedules, billing, lab, entitlements | Active user; no additional data initially |

Credential establishment, activation, storage, delivery, rotation, and cleanup remain policy/approval items. Accounts must be pre-created only after approval and must never be created during the presentation.

## 15. Fictional dataset specification

All future records must share one explicit demo tag, be internally consistent, and use non-deliverable aliases generated only during an approved preparation step. No real name, phone, email, address, government ID, provider ID, file, or clinical history is permitted.

| Record | Minimum | Relationships and constraints |
|---|---:|---|
| Users | 5 | Exactly one active account for each internal role; random protected credentials outside repository/logs. |
| Patient profile | 1 | Belongs only to Demo Patient Alpha; no real contact/address. |
| Doctor profile | 1 | Belongs only to Demo Clinician One; fictional specialization wording; no real credentials claimed. |
| Assignment evidence | 1 relationship | Doctor One is assigned only to Patient Alpha through the same source used by the directory/history authorization. |
| Completed appointments | 2 | Owned by Patient Alpha, assigned to Doctor One, non-cancelable terminal states, fictional non-clinical reasons, no payment success. |
| Notifications | 1–2 per shown role | Generic all-read text; recipient IDs match each account; no mutation needed. |
| Report metadata | 1 | Owned by Patient Alpha, no storage/file key and no detailed medical content. |
| Reception coordination | 0 initially | Do not seed until a safe presentation surface is approved. |
| Laboratory request | 0 initially | Do not seed while laboratorian page remains upload-oriented. |
| Schedule | 0 initially | Not needed for completed-history walkthrough. |
| Care plan/exercise/progress | 0 initially | Excluded until a safe read-only surface and semantic content approval exist. |
| Payment, webhook, entitlement, PDF/file | 0 | Explicitly prohibited. |

Referential validation must confirm user/profile links, appointment owner/doctor links, notification recipient links, demo tags, terminal/non-mutating states, absence of files/provider identifiers, and zero untagged records in the dedicated database.

## 16. Environment prerequisites

Every owner remains **UNASSIGNED** until approved:

| Pre-start check | Owner | Required evidence |
|---|---|---|
| Written architecture/environment/machine approval | UNASSIGNED | Approved source ordinal 1 and implementation review |
| Named operator | UNASSIGNED | Approval 2 |
| Approved viewers | UNASSIGNED | Approval 3 |
| Approved route-state scope | UNASSIGNED | Approval 4 |
| Dedicated DB identity and zero unexpected records | UNASSIGNED | Read-only preflight after approved preparation |
| Fictional dataset and five accounts | UNASSIGNED | Approvals 5–6; tagged inventory only, no credentials in evidence |
| Payment disabled/blank and reconciliation false | UNASSIGNED | Config plus health/runtime evidence |
| No production credential/database/data | UNASSIGNED | Redacted environment inventory and exact target check |
| Loopback-only database/API/frontend | UNASSIGNED | Listener/port ownership record |
| Docs routes restricted | UNASSIGNED | `/docs`, `/redoc`, `/openapi.json` 404 smoke |
| File/storage/scanner excluded | UNASSIGNED | Zero file records/paths used; approval 9 |
| Startup script reviewed and exact version recorded | UNASSIGNED | Approved launcher hash/diff and test result |
| Shutdown/abort authority and procedure | UNASSIGNED | Approval 10 |
| Retention/cleanup decision | UNASSIGNED | Approval 11 |

No checklist item may be self-approved by the operator who implemented the environment without the named review required by the project owner.

## 17. Start, stop, and abort plan

### 17.1 Existing exact commands — reference only

These commands are inspected from repository documentation/scripts and must not be run without approval.

Laboratory Demo on an approved compatible machine:

1. `docker compose -f backend\docker-compose.lab-demo.yml up -d`
2. `.\backend\scripts\LabDemo.ps1 -Action configure`
3. `.\backend\scripts\LabDemo.ps1 -Action start` in a dedicated foreground terminal
4. `.\backend\scripts\LabDemo.ps1 -Action frontend` in a second foreground terminal
5. Stop the foreground processes, then use the same compose file/project context to stop only its MongoDB service. The separate `cleanup` action deletes tagged data/files and requires separate approval; it is not automatic shutdown.

Home Visit Demo on an approved compatible machine:

1. `.\backend\scripts\HomeVisitDemo.ps1 -Action start`
2. `.\backend\scripts\HomeVisitDemo.ps1 -Action backend`
3. `.\backend\scripts\HomeVisitDemo.ps1 -Action frontend`
4. `.\backend\scripts\HomeVisitDemo.ps1 -Action verify`
5. `.\backend\scripts\HomeVisitDemo.ps1 -Action stop`

Expected ports/identities are recorded in section 8. Account/data preparation commands are intentionally omitted from the start plan because they are writes and remain unapproved.

### 17.2 Recommended unified environment

No exact command exists because the environment and launcher do not exist. Commands must not be invented. A future approved implementation must provide one preflight, database start, backend start, frontend start, verify, stop, and separately confirmed cleanup path; track process ownership; reject occupied ports; validate exact DB before client creation; show only redacted health; and verify all processes/listeners are gone after stop.

### 17.3 Abort procedure

Abort on any external/production DB or credential, real data, enabled payment/reconciliation, non-approved listener, external exposure, role/ownership failure, sensitive logging, excluded action availability beyond the approved state, unapproved write, environment mismatch, or inability to establish identity.

Stop the walkthrough; safely invoke only the validated tracked stop action; verify expected process IDs/listeners ended; preserve redacted diagnostics; leave database/data unchanged; notify the named owner; do not repair, restart, or clean automatically. Cleanup always requires separate explicit target approval.

## 18. Policy decision register

| Unresolved decision | Restricted local demo | Specific workflow blocked | Connected demo | Staging/production |
|---|---|---|---|---|
| Patient onboarding | Does not block if accounts are approved/pre-created | Any patient-creation story | Blocks onboarding demo | Required |
| Credential establishment | **Blocks account preparation** | All role logins | Required | Required |
| Account activation | **Blocks account preparation** | Trust/activation story | Required | Required |
| Email verification | Exclude claim | Verification/recovery | Required for such story | Policy required |
| Invitation | Exclude | Admin invitation | Required for such story | Policy required |
| Duplicate handling | Avoid through approved tagged inventory | Onboarding/support | Required | Required |
| Patient-creation audit | No creation in demo | Admin patient-create | Required | Required |
| Password policy | **Blocks final temporary credential policy** | Account creation/change/recovery | Required | Required |
| Recovery | Exclude | Recovery journey | Required for such story | Required |
| Clinical text/content limits | Minimal predefined non-clinical text only | Clinical authoring/richer seed | Required | Required |
| Demo workflow scope | **Blocks entire presentation** | Route-state whitelist | Required | Not a substitute for release scope |
| Payment inclusion | Excluded/disabled | Checkout/billing/provider claims | Required before inclusion | Required |
| Demo-data access authority | **Blocks entire presentation** | Every role/data view | Required | Required |

No clinic policy was inferred from technical validation limits or existing UI behavior.

## 19. Eight connected release-gate status

All gates remain **BLOCKED** and no connected verification was run.

| Gate | Required closure evidence | Restricted read-only local demo relationship |
|---|---|---|
| 1. Connected multi-clinician authorization | Approved replica-set DB/identities; mismatched role/owner cases; transaction/race/rollback logs | Narrow local role smoke still mandatory; full gate not required if mutations excluded |
| 2. MongoDB query plans and realistic scale | Representative dataset, `explain`, offsets, latency/concurrency/BSON/pool results | Not required for tiny local demo if performance claims excluded |
| 3. Actual database index verification | Deployed index inventory, uniqueness/preflight, plan use | Mutation/booking demo blocked; read-only tiny display may exclude claim |
| 4. Socket-capable ClamAV protocol/scanning | Approved daemon/version/config and clean/malicious/error/timeout evidence | Irrelevant only because every PDF workflow is excluded |
| 5. Private storage integration/access | Approved roots, permissions, promotion/cleanup, traversal and authorization | Irrelevant only because every file workflow is excluded |
| 6. Browser end-to-end journeys | Approved environment/browser/data; session/role/CSRF/account-switch/PDF/recovery evidence | Narrow browser smoke is mandatory but does not close this full gate |
| 7. Production proxy/TLS/cookie/cache | Production-like ingress/TLS/Host/forwarding/CORS/cookies/cache/body/docs/webhook evidence | Loopback demo may avoid full gate by excluding webhook/payment/public exposure |
| 8. Backup and restore | Approved backup, protected artifact, isolated restore, validation, RPO/RTO, cleanup | May be waived only for explicitly approved disposable fictional demo; approval 11 decides |

## 20. Fresh offline verification

| Check | Fresh Phase 24A.16 result |
|---|---|
| Focused backend: demo guards/startup static tests, auth/session, role/ownership, read/workflow contracts, Groups A–D, Phase 24A.14 | **409 passed**, 1 TestClient deprecation warning |
| Full frontend | **167 passed** |
| Frontend lint | PASS |
| Production build to `/private/tmp` | PASS — Vite 8.3.5, 1,837 modules |
| Bundle budget | PASS — 73 JS/CSS assets; max JS 373,260 / 460,800 bytes; max CSS 254,338 / 307,200 bytes |
| In-memory Python compilation | PASS — 171 files |
| Dependency-lock tests | **2 passed** |
| `pip check` | PASS — no broken requirements |
| Offline npm audit | PASS — 0 cached vulnerabilities |
| Redacted secret scan | Six known synthetic `generic-api-key` fixtures only |
| `git diff --check` before report | PASS |

The six detections remain five test fixtures in `test_api_contract.py` and one in `test_schedule_fallback_guard.py`; no value was printed. A full backend suite and scanner protocol suite were not rerun because this milestone is documentation-only and its focused selection covered the relevant demo/security regressions. Their Phase 24A.15 results remain historical evidence, not fresh Phase 24A.16 results.

## 21. Outstanding blockers

1. All 11 approvals are pending and owners are unassigned.
2. The recommended unified five-role environment, validator, fixture, launcher, verification, and cleanup do not exist.
3. No compatible approved host is selected; current macOS has no verified supported path.
4. Receptionist, administrator, and laboratorian lack a technically enforced meaningful read-only presentation surface.
5. Credential/activation/password/access-authority and dataset/retention policies are unresolved.
6. No accounts or data are approved/pre-created.
7. No runtime target, listener, payment, docs, or inventory check exists.
8. The mandatory narrow browser smoke has not occurred.
9. All eight connected gates remain blocked.

## 22. Recommended next actions in priority order

1. Project owner selects and approves Option A or explicitly reduces the demo to one existing workflow-specific environment.
2. Assign the environment owner/operator and independent reviewer; select Windows or macOS host.
3. Clinic/product/security authorities approve the exact route-state shortlist and accept or reject the three role-surface gaps.
4. Approve fictional account/data, credential/activation/password handling, viewers, retention, cleanup, payment/file exclusions, and abort authority.
5. If Option A/current Mac is approved, authorize a separate implementation milestone for the unified environment and cross-platform launcher with tests; do not combine it with execution.
6. Independently review the implementation and run offline tests only.
7. Separately authorize tagged account/data preparation; capture redacted inventory, not credentials.
8. Separately authorize startup and the narrow local browser smoke; review evidence and incidents.
9. Only then issue or deny actual presentation authorization for named viewers/window.
10. Keep connected work and Phase 24B blocked until their independent prerequisites are satisfied.

## 23. Demo readiness decision

### Demo preparation: PARTIALLY PREPARED

The approval package, dependency order, architecture recommendation, compatibility analysis, role gaps, exact route states, account/data specification, prerequisites, lifecycle reference, abort procedure, policy register, and fresh offline evidence are prepared.

The executable environment, launcher, owners, approvals, accounts, data, runtime evidence, and browser smoke are not prepared or approved.

### Actual controlled local demo authorization: NO-GO

All 11 approvals remain pending, so NO-GO is mandatory. Planning completeness cannot substitute for approval or execution evidence.

## 24. Final repository state and Phase 24B status

| Item | Final value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Unstaged tracked modifications | 114 |
| Untracked paths | 93 |
| Total dirty paths | 207 |

This report is the only Phase 24A.16 repository artifact; no application, test, dependency, launcher, environment, or previous documentation file was modified. The one-path increase from Phase 24A.15 is this untracked report, and all 206 prior dirty paths remain preserved.

No service or external resource was accessed. No account, credential, fixture, record, database, migration, index, payment, file, or infrastructure resource was created, changed, or deleted.

**Phase 24B remains BLOCKED / NOT STARTED.** Stop after Phase 24A.16 and wait for explicit review before implementing a launcher, preparing accounts/data, starting services, running a browser, or performing connected work.
