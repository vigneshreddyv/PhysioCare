# Phase 24A.17 — Five-Role Read-Only Demo Surface Design and Scope Validation

Assessment date: 2026-11-02  
Branch: `codex/physiocare-integration-2026-10-31`  
Assessment HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

An eventual meaningful five-role read-only demo is **technically feasible, but it is not implemented or authorized**. The existing patient and doctor surfaces can support a restricted presentation if the dataset and route set are tightly constrained. The receptionist, administrator, and laboratorian accounts have useful role-scoped GET APIs, but their current pages combine those reads with booking, editing, status updates, account creation, or PDF upload controls. They therefore require new presentation-only frontend views.

New frontend views alone would not make the environment strictly read-only. The normal role permissions would still authorize mutations through direct API calls. A future implementation must add an environment-specific, fail-closed backend demo policy that permits only an audited role/route/method allowlist, while retaining the existing session, role, owner, clinician-assignment, and laboratorian-assignment checks. Login, refresh, CSRF establishment, and logout need narrowly documented lifecycle exceptions because authentication itself uses server-side session writes.

No new administrator API is required. Existing administrator staff, clinician, and daily-activity GET endpoints can supply a minimal summary. The existing laboratorian assignment endpoint can supply a useful fictional work-status view, although a narrower response projection is recommended if the project requires data minimization at the API boundary rather than only in the renderer. No database schema change is presently indicated.

This milestone changed no application, test, launcher, environment, fixture, or prior documentation file. It started no service, accessed no database or external system, and created no account or data. Its only intended repository artifact is this report.

**Current outcome:** five-role design **FEASIBLE WITH REQUIRED NEW VIEWS AND BACKEND ENFORCEMENT**; actual local demo **NO-GO**; connected client demo **NO-GO**; Phase 24B **BLOCKED / NOT STARTED**.

## 2. Previous milestone status

Phase 24A.16 remains the controlling demo-planning authority. Its status is unchanged:

- all 11 approvals are **PENDING**, with 0 approved and all owners unassigned;
- a dedicated unified five-role environment is recommended but not implemented or approved;
- a guarded macOS/cross-platform launcher is recommended but not implemented or authorized;
- demo preparation is **PARTIALLY PREPARED**;
- actual controlled local demo is **NO-GO**;
- connected client demo is **NO-GO**;
- all eight connected release gates are **BLOCKED**; and
- Phase 24B is **BLOCKED / NOT STARTED**.

This report also reconciles the Phase 24A.15, 24A.13, Phase 24A.12 Group A–D, and Phase 24A.14 reports with current source. Planning or source feasibility is not execution approval, runtime evidence, production readiness, or closure of a connected release gate.

## 3. Repository state

State recorded before creating this report:

| Item | Actual value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Staged paths | 0 |
| Tracked modified paths | 114 |
| Untracked paths | 93 |
| Total dirty paths | 207 |

The complete `git status --short --branch` was inspected. All 207 pre-existing dirty paths were preserved. This untracked report is expected to increase the untracked and total dirty counts by one. No branch switch, commit, stash, reset, clean, or push was performed.

## 4. Patient assessment

All routes below are nested beneath the patient-only route guard in `frontend/src/App.jsx:169-196`. Authentication is a validated cookie session; the frontend loads the active identity with `GET /api/auth/me` (`frontend/src/context/AuthContext.jsx:35-47`), and backend session and active-account checks are enforced in `backend/app/middleware/auth.py:20-109`.

| Surface | Existing frontend and API | Authorization and returned data | Mutations/files | Read-only suitability |
|---|---|---|---|---|
| Profile display | `/patient/profile`; profile data comes from `GET /api/auth/me` through the auth context | Authenticated user only; own account/profile fields | The page includes an edit form and `PATCH /api/users/me/patient-profile` (`frontend/src/pages/patient/PatientProfile.jsx:26-55`). It does not mutate automatically. No file access. | **Conditional.** A new display-only view, or a backend-enforced allowlist that makes the current edit action unreachable, is required for a strict demo. |
| Completed history | `/patient/history`; `GET /api/appointments/me/history?status_group=completed&page=…` (`backend/app/api/appointments.py:150-165`) | Patient role; user ID is derived from the authenticated session and passed to the service. `AppointmentOut` includes visit, clinical, location, billing, payment, cancellation, and internal payment-ID fields (`backend/app/schemas/appointment.py:62-93`). | The current page renders payment continuation and cancellation controls for applicable non-completed rows (`frontend/src/pages/patient/PatientHistory.jsx:41-115`). No automatic mutation. | **Conditional.** A completed-only fixture suppresses row actions, but a dedicated minimal projection is preferable because the API contract is broader than the presentation needs. Payment fields must not be rendered. |
| File-free report metadata | `/patient/reports`; bounded `GET /api/reports` (`backend/app/api/reports.py:34-54`) | Patient role; backend resolves the patient profile from the session and queries only that patient. Response includes title/category/date/description/therapist/content and `has_file`. | The page implements `GET /api/reports/{id}/download` and blob download when a file exists (`frontend/src/pages/patient/PatientReports.jsx:58-77`). No data mutation. | **Conditional.** Use only approved fictional records with no file path and deny the download route in the demo policy. A presentation-only component should omit the file action entirely. |
| All-read notifications | `/patient/notifications` or `/notifications`; `GET /api/notifications` and `GET /api/notifications/unread-count` | Any authenticated user; recipient user ID is derived from the session (`backend/app/api/notifications.py:11-38`). Notification response includes recipient ID, text/type/read state, related entity ID, and timestamp. | The page includes `PATCH /api/notifications/{id}/read` and `PATCH /api/notifications/read-all` (`frontend/src/pages/common/Notifications.jsx:80-114`). It does not automatically mark records read. No files. | **Conditional.** Seeded all-read records reduce visible actions, but strict enforcement still must deny PATCH and the read-only view should omit management controls. Related-entity content requires dataset review. |

Patient classification: **READY WITH RESTRICTIONS**. The owner boundaries are suitable, but the existing pages are not intrinsically read-only and the appointment response is broader than a minimum demo projection.

## 5. Doctor assessment

Doctor routes are nested beneath the doctor-only guard in `frontend/src/App.jsx:198-219`.

| Surface | Existing frontend and API | Assignment/ownership and returned data | Mutations/files | Read-only suitability |
|---|---|---|---|---|
| Assigned-patient directory | `/doctor/patients`; `GET /api/users/patients` | Doctor role. The API passes the authenticated doctor user ID to the service (`backend/app/api/users.py:146-158`). `DoctorPatientOut` contains ID, name, phone, date of birth, and gender (`backend/app/schemas/patient.py:48-53`). Repository/service filtering limits results to assigned patients. | Shared page also links to care-plan and exercise management (`frontend/src/pages/admin/PatientsList.jsx:241-245`). No automatic write. | **Conditional.** A dedicated directory can reuse the endpoint, display only approved fields, and omit all management links. |
| Assigned-patient history | `/doctor/patients/:patientId`; `GET /api/users/doctor/patients/{patientId}/history` | Doctor role. The service resolves the doctor, checks `has_assigned_patient`, returns the same 404 for missing and unassigned records, and queries doctor/patient-scoped appointments (`backend/app/services/doctor_history_service.py:18-79`; repository predicate at `backend/app/repositories/appointment_repository.py:455-466`). `DoctorAppointmentOut` intentionally excludes payment and cancellation fields but includes clinical and possible home-visit data (`backend/app/schemas/appointment.py:96-118`). | History also includes released laboratory-report metadata and the page can expose report/PDF actions when records exist. No automatic mutation. | **Conditional.** Use assigned fictional clinic visits, completed status, no address, and no released report/file. Deny every file route. A dedicated presentation renderer should show only approved appointment fields. |
| Completed appointment information | `GET /api/appointments` with doctor filters such as `status_group=completed` (`backend/app/api/appointments.py:94-120`) | Doctor role; service receives the current doctor ID. Returns `DoctorAppointmentOut`. | Existing dashboard includes appointment status PATCH controls and laboratory report/PDF behavior, so it is not a safe presentation surface. | **Conditional.** Existing GET can support a new completed-only view; current dashboard must be excluded. |
| Clinician schedule | No existing doctor-facing schedule page was found. Administrator schedule management is not a doctor read-only surface. | Not applicable. | Existing schedule workflows are management-oriented. | **Not currently available.** Do not claim a clinician schedule in the demo. Assigned completed visits are the supported substitute. |

Doctor classification: **READY WITH RESTRICTIONS**. API, service, and repository assignment checks are present, but current shared pages expose management navigation and possible report-file actions.

## 6. Receptionist assessment

Current routes `/reception/dashboard`, `/reception/patients`, and `/reception/appointment-booking` are role-guarded (`frontend/src/App.jsx:252-266`), but none is a strict presentation-only page.

| Proposed display | Existing route/API and fields | Current mutation controls | Required work and risks |
|---|---|---|---|
| Schedule/status summary | Current `/reception/dashboard`; `GET /api/appointments/reception` and `GET /api/appointments/reception/summary` (`backend/app/api/appointments.py:53-76`). `ReceptionAppointmentOut` includes patient ID/name/email/phone, doctor, date/time/mode, optional address/city, status, and cancellation fields (`backend/app/schemas/appointment.py:121-140`). | Book-appointment navigation and `POST /api/appointments/reception/{id}/cancel` (`frontend/src/pages/receptionist/ReceptionistDashboard.jsx:23-61`). | Create a new read-only view that renders fictional clinic visits only: patient alias, clinician, date/time, and status. Reuse existing GETs. The existing network projection includes contact and address data, so the dataset must keep optional fields empty; a narrower backend projection is desirable if strict API-level minimization is required. |
| Coordination directory | Current `/reception/patients`; `GET /api/users/reception/patients`. Response is ID, name, email, and optional phone (`backend/app/schemas/patient.py:56-60`); receptionist role is enforced (`backend/app/api/users.py:123-134`). | Shared page exposes an edit form and `PATCH /api/users/reception/patients/{id}` (`frontend/src/pages/admin/PatientsList.jsx:47-69,238-240`). | Create a new view and render only approved fictional aliases and the minimum approved coordination field. Omit the edit form. Email/phone remain personal data even when fictional and need explicit scope approval. |
| Clinician directory/availability | No current receptionist display route dedicated to this. `GET /api/users/reception/doctors` returns public clinician fields and is receptionist-only (`backend/app/api/users.py:112-121`); authenticated `GET /api/appointments/availability` exists (`backend/app/api/appointments.py:86-92`). | Existing booking page uses these reads in a mutation workflow. | A new display-only clinician/availability component may reuse the GETs, but availability requires an approved clinician and date and must not imply that booking is enabled. External professional links in the clinician projection should be omitted. |
| Completed summary | Existing schedule GET supports date filtering and completed status in returned records; summary endpoint returns aggregate integers. | Current dashboard remains cancellable/bookable. | A new view can filter/render completed fictional clinic appointments. Server-side status filtering is not exposed on the receptionist route, so client display filtering may leave other records in the response. Prefer a fixture containing only approved rows or a future narrow read endpoint if this becomes a hard boundary. |

No normal receptionist permission needs to be weakened. The ordinary workflows should remain unchanged outside the dedicated demo environment. The principal risks are contact/address overexposure, direct access to authorized mutation endpoints, and accidentally navigating into booking.

Receptionist classification: **REQUIRES NEW READ-ONLY VIEW**.

## 7. Administrator assessment

Current administrator routes are protected by the admin role (`frontend/src/App.jsx:221-250`) but are management surfaces.

| Proposed display | Existing route/API and projection | Current mutation controls | Required work, strategy, and risks |
|---|---|---|---|
| User/role and account-status directory | Current `/admin/staff`; `GET /api/users/staff`. `StaffOut` contains ID, name, email, role, active state, and creation time (`backend/app/schemas/auth.py:29-35`). Admin role is enforced (`backend/app/api/users.py:60-74`). | The same page contains a password-bearing staff creation form and `POST /api/users/staff` (`frontend/src/pages/admin/StaffManagement.jsx:16-22,45-64,76-91`). | New frontend view; reuse GET. Render fictional alias, role, status, and optionally created date. Omit email unless explicitly approved; never render credentials. Backend demo allowlist must deny staff creation. |
| Clinician directory | Current `/admin/doctors`; `GET /api/users/doctors`. `DoctorOut` contains name, email, public profile fields, and `is_active_today` (`backend/app/schemas/doctor.py:5-26`). | Same page exposes profile editing through `PATCH /api/users/doctors/{id}` and schedule navigation (`frontend/src/pages/admin/DoctorsList.jsx:20-71`). | New frontend view; reuse GET. Render only alias, specialization, and active-today status. Omit email and external links by default. |
| Operational overview | Current `/admin/dashboard`; `GET /api/analytics/admin-daily-activity` returns count-level activity. Admin role is enforced (`backend/app/api/analytics.py:15-17`). | Current dashboard also calls broad `/analytics/stats`, loads appointment records, and exposes appointment status PATCH (`frontend/src/pages/admin/AdminDashboard.jsx:8-62`). | New frontend view that calls only daily activity. Do not use `/analytics/stats` because it is broader and can be payment/revenue-adjacent. Display non-sensitive counts with no patient detail. |
| Patient summary | Current `/admin/patients`; `GET /api/users/patients` returns `PatientOut`, including email, phone, DOB, gender, and subscription (`backend/app/schemas/patient.py:48-75`). | Edit, history, care-plan, and exercise navigation (`frontend/src/pages/admin/PatientsList.jsx:200-237`). | **Exclude from the first read-only admin view.** It is not necessary to meet a non-sensitive system-summary objective and returns unnecessary patient information. |

No new administrator API is necessary or proposed. A dedicated frontend route can compose the existing staff, clinician, and daily-activity GET endpoints, while the backend demo policy allows only those exact GET routes. Normal admin authorization remains unchanged outside demo mode.

Administrator classification: **REQUIRES NEW READ-ONLY VIEW**.

## 8. Laboratorian assessment

The current `/laboratory/dashboard` is laboratorian-only (`frontend/src/App.jsx:270-280`) but is fundamentally a report-upload workflow.

The existing `GET /api/lab-requests/laboratory/assigned` endpoint is restricted to the laboratorian role (`backend/app/api/lab_requests.py:89-96`). The service queries by the authenticated laboratorian user ID (`backend/app/services/lab_request_service.py:113-135`), preserving assignment ownership. `LaboratorianLabRequestOut` returns request ID, patient name/optional phone, mode, selected tests, optional home address/city, request status, report status, optional report filename/upload time, and creation time (`backend/app/schemas/lab_request.py:73-85`). This is sufficient for a meaningful display of assigned work, completion/publication status, and historical timestamps.

The current page is not suitable: it includes a PDF file input and `PUT /api/lab-requests/laboratory/{id}/report` (`frontend/src/pages/laboratorian/LaboratoryDashboard.jsx:32-39,102-120`). The upload service checks assignment, but that protects authorization rather than read-only behavior. Released report filename metadata also risks implying file access even when no viewer is shown.

A genuinely read-only view is technically possible with the existing assigned-work GET endpoint if it:

- uses only approved fictional clinic-mode requests;
- renders patient alias, test names, request/report status, and non-sensitive timestamps;
- keeps phone, home address, city, report filename, and file timestamps absent or unrendered;
- has no file input, upload, result submission, modification, payment, provider identifier, or legacy laboratory route;
- does not call any report-file endpoint; and
- is protected by the backend demo allowlist as well as the existing assignment check.

A new backend endpoint is not strictly required. A narrower laboratorian demo projection is nevertheless recommended if the security decision requires minimum data at the API response boundary, because frontend omission does not remove fields from the network response.

Laboratorian classification: **REQUIRES NEW READ-ONLY VIEW**.

## 9. Five-role comparison matrix

| Role | Existing read-only surface | Missing capability | Required work | Security concerns | Classification |
|---|---|---|---|---|---|
| Patient | Owner-scoped profile, completed history, reports, and notifications have usable GET paths | Existing pages also contain edit/cancel/payment/download/read-state actions; appointment projection is broad | Dedicated presentation components or tightly constrained variants; demo GET allowlist; file-free fictional data | Direct mutation calls, payment fields, clinical over-display, PDF route, notification entity content | **READY WITH RESTRICTIONS** |
| Doctor | Assigned directory/history and completed appointments have role- and assignment-scoped GET paths | No safe doctor schedule; shared pages link to clinical management and possible report files | Dedicated assigned-patient/completed-visit presentation; allowlist; no reports/files | Cross-patient access, clinical minimum-necessary scope, home address, PDF access | **READY WITH RESTRICTIONS** |
| Receptionist | Schedule, summary, directory, clinician, and availability GET APIs exist | No current presentation-only route | New read-only view; reuse GETs; optionally narrow response later | Contact/address overexposure and still-authorized booking/cancellation/edit APIs | **REQUIRES NEW READ-ONLY VIEW** |
| Laboratorian | Assigned-work GET is role- and assignment-scoped | Current UI is upload-first; response contains contact/address/file metadata | New read-only view; reuse GET; optional narrow projection | Upload endpoint, file metadata, address/phone, legacy/file routes | **REQUIRES NEW READ-ONLY VIEW** |
| Admin | Staff, clinician, and aggregate daily-activity GET APIs exist | Current pages are management-oriented | New non-sensitive summary view using existing APIs; no new admin API | Account creation/edit/status mutation, email exposure, broad analytics/payment-adjacent data | **REQUIRES NEW READ-ONLY VIEW** |

No role is classified **READY FOR READ-ONLY DEMO** without restrictions because the unified backend enforcement layer and dedicated five-role presentation have not been implemented.

## 10. Read-only enforcement requirements

The required future control is defense in depth:

1. **Dedicated routes/components:** presentation controls must be absent, not disabled. No mutation form, upload input, management navigation, PDF link, or payment link may be rendered.
2. **Exact frontend request inventory:** the demo bundle must issue only approved GET requests plus narrowly defined authentication lifecycle calls. No background POST, PUT, PATCH, or DELETE may occur.
3. **Fail-closed backend demo policy:** when the dedicated five-role demo mode is enabled, deny every application route/method except an explicit per-role allowlist. Deny disallowed GET endpoints as well as all product mutations.
4. **Authentication exceptions:** permit only the minimum login, refresh/CSRF establishment, current-user, and logout routes required for cookie-session lifecycle. Document that authentication session creation/rotation/revocation writes are operational exceptions, not product-data mutations.
5. **Existing controls remain authoritative:** `get_current_user`, `RoleChecker`, patient ownership, doctor assignment, and laboratorian assignment checks must still execute. The demo policy adds restrictions; it must never bypass or weaken normal authorization.
6. **Audited GET semantics:** verify that every allowed GET is side-effect free. HTTP verb alone is not proof of read-only behavior.
7. **Minimum response/data:** seed only approved fictional fields. Prefer narrow response schemas where current endpoints return more data than the view needs; never rely on CSS to protect a field.
8. **Files and payments excluded:** deny PDF/report-file routes, upload routes, billing/payment/reconciliation routes, provider callbacks, and external storage/scanner paths regardless of UI visibility.
9. **No background mutation:** disable or omit automatic mark-read, polling that changes state, optimistic updates, analytics writes, and any mutation-triggering retry behavior.
10. **Verification:** add route-policy unit/contract tests, frontend source/rendered tests proving controls and mutation calls are absent, negative role/owner/assignment tests, and—only after approval—browser network inspection confirming the allowlist.

CSRF protection in `backend/app/middleware/auth.py:72-87` remains valuable for ordinary mutations, but CSRF does not turn an authorized role account into a read-only account. The environment-specific deny policy is still required.

## 11. Missing capabilities

| Missing capability | Classification | Required? |
|---|---|---|
| Dedicated patient minimal presentation variants | Frontend-only presentation + existing API reuse | Required for strict and consistent five-role UX |
| Dedicated doctor assigned-directory/completed-history presentation | Frontend-only presentation + existing API reuse | Required |
| Dedicated receptionist schedule/directory presentation | Frontend-only presentation + existing API reuse | Required |
| Dedicated administrator staff/clinician/activity presentation | Frontend-only presentation + existing API reuse | Required; no new admin API |
| Dedicated laboratorian assigned-work presentation | Frontend-only presentation + existing API reuse | Required |
| Per-role, per-route demo allowlist and authentication exceptions | Backend authorization/policy change | Required |
| Narrow patient appointment projection | Backend read-only endpoint/projection | Recommended; required if network-level minimum-data is a hard criterion |
| Narrow receptionist schedule/directory projection | Backend read-only endpoint/projection | Optional with minimal fictional dataset; recommended for stronger minimization |
| Narrow laboratorian summary projection | Backend read-only endpoint/projection | Optional with clinic-only/null contact/file data; recommended for stronger minimization |
| New administrator API | Backend endpoint | **Not required and prohibited by this milestone** |
| Database schema/index change | Database change | Not indicated |
| Unified fictional fixture/account graph | Data preparation, not schema | Required later, after approval |
| Unified guarded cross-platform launcher | Environment tooling | Required later if Option A is approved; outside this milestone |
| Route content and fictional clinical semantics | Clinic policy decision | Required before implementation/data preparation |

## 12. Implementation dependency map

The dependency order is:

1. Obtain written approval for the chosen demo option, exact route/field scope, fictional data, accounts, environment, network boundary, payment/file exclusions, and responsible people.
2. Authorize a separate implementation milestone; Phase 24A.17 itself grants no implementation authority.
3. Define the backend demo-mode contract: configuration guard, exact per-role GET allowlist, auth lifecycle exceptions, deny behavior, and no-write invariant.
4. Decide which broad responses may be reused with fictional null/minimal fields and which need narrower read-only projections. Do not add an administrator API.
5. Implement and test backend enforcement before relying on new UI routes.
6. Implement the five dedicated frontend presentation routes with mutation/file/payment controls absent.
7. Define and separately approve the unified five-role fictional relationship graph and pre-created account policy.
8. Run an independent offline security/source review and full relevant regression suites.
9. If still approved, implement and review the unified guarded macOS/cross-platform launcher in a separate milestone.
10. Only after all prerequisite approvals, prepare accounts/data and conduct the narrow browser smoke on the named isolated host.

The critical path is approval → backend restriction → minimal projections → frontend views → offline independent review → environment/launcher → approved data/accounts → browser smoke. Frontend development must not precede agreement on the enforceable route contract.

## 13. Demo scope alternatives

| Option | Security | Credibility | Implementation effort | Approval needs | Assessment |
|---|---|---|---|---|---|
| **A. Five-role read-only demo** | Strong only after backend allowlist, minimum data, unified isolated environment, and negative tests; weakest if implemented as UI hiding alone | Highest: shows real role boundaries and connected fictional relationships | Highest: five views, backend policy, possible narrow projections, fixture graph, launcher, tests/review | All 11 approvals plus explicit implementation, field/route scope, and launcher authorization | Best match for the stated objective, but not ready now |
| **B. Restricted patient/doctor demo** | Lower surface area and fewer sensitive projections; still requires backend enforcement and approvals | Good for clinical owner/assignment story, but omits three operating roles | Lower | Same safety approvals, narrower workflow/data approval | Safest fallback if the project declines five-role work |
| **C. Mixed actual plus screenshots/architecture** | Reduces live surface; screenshot creation, contents, storage, and redaction still need approval | Lowest: does not demonstrate working receptionist/admin/lab authorization | Low to medium | Live two-role approvals plus screenshot/content approval | Acceptable only if explicitly described as non-functional evidence; must not be presented as five-role readiness |

## 14. Recommended scope

Recommend **Option A as the future target**, not as the current execution plan. It is the only option that satisfies the requested five-role objective credibly. It must be delivered through separately authorized implementation and review milestones, with backend enforcement preceding UI reliance.

The minimum recommended live presentation is:

- patient: own alias/profile, completed clinic visits, file-free report metadata, all-read notifications;
- doctor: assigned fictional patients and completed assigned clinic visits, with no report files;
- receptionist: minimal fictional clinic schedule/status and approved coordination aliases;
- administrator: fictional staff role/status, clinician aliases/specialization, and aggregate daily activity only; and
- laboratorian: assigned fictional clinic-test names and request/report workflow status only.

Exclude booking, cancellation, editing, account creation, schedule management, clinical authoring, care-plan/exercise writes, home addresses, payment/billing, provider identifiers, PDFs/files, uploads, legacy laboratory workflows, and external integrations.

If Option A implementation or its controls are not approved, select Option B explicitly. Do not substitute Option C while claiming a functioning five-role demo.

## 15. Additional approval requirements

All Phase 24A.16 approvals remain **PENDING**: named environment/machine; owner/operator; viewers; workflow list; fictional dataset; role accounts/access; network boundary; payment-disabled confirmation; storage/scanner exclusions; start/stop/abort authority; and cleanup/retention decision.

The proposed work also needs explicit approval for:

- application-code changes for the backend demo policy and frontend routes;
- the exact per-role route, method, and response-field allowlist;
- whether narrow patient/receptionist/laboratorian projections are mandatory;
- the operational authentication-write exception;
- the five-role fictional relationship graph and visible clinical/laboratory semantics;
- new tests and an independent security review;
- later unified environment and launcher implementation; and
- later account/data preparation and browser execution.

This milestone is not approval to modify application code, create accounts, seed data, install dependencies, start services, modify launchers, access external systems, or clean up data.

## 16. Verification performed

| Verification | Result |
|---|---|
| Required prior reports | Read and reconciled against current source |
| Git branch/HEAD/upstream/ahead-behind and complete status | Verified as recorded in section 3 |
| Frontend route guards and role route inventory | Source-inspected |
| Patient profile/history/report/notification pages and APIs | Source-inspected through frontend, API, schemas, service ownership paths |
| Doctor directory/history and assignment enforcement | Source-inspected through frontend, API, service, and repository |
| Receptionist schedule/directory/clinician APIs and mutation controls | Source-inspected |
| Admin staff/clinician/activity APIs and mutation controls | Source-inspected |
| Laboratorian assigned-work API, assignment scope, response, and upload UI | Source-inspected |
| Full frontend offline suite | **167 passed, 0 failed** on 2026-11-02 |
| Backend focused suite attempt | **Not executed.** System Python lacked `pytest_asyncio`; the existing offline dependency runner could not resolve three uncached locked packages while forced offline. No dependency was installed and no network access was used. |
| Historical evidence retained | Phase 24A.16 records **409 focused backend passed** and **167 frontend passed**; Phase 24A.15 records **1,135 backend passed, 3 connected-only skipped**. These are historical evidence, not fresh Phase 24A.17 backend results. |

The failed backend invocations occurred before test collection and therefore are not test failures. This documentation-only milestone relies on source inspection and the unchanged historical backend evidence; it does not claim fresh backend execution.

No backend/frontend service, browser automation, MongoDB, Docker, Razorpay, ClamAV, storage, migration, index operation, account/fixture creation, or database access occurred. No `.env` file was changed.

## 17. Remaining blockers

1. Eleven required approvals remain pending and responsible people are unassigned.
2. The backend strict read-only demo policy does not exist.
3. Dedicated receptionist, administrator, and laboratorian read-only views do not exist; patient and doctor still need constrained presentation variants for strict behavior.
4. The exact route/field allowlist and authentication lifecycle exception are undecided.
5. Broad patient, receptionist, and laboratorian responses require a data-minimization decision.
6. No unified five-role fictional fixture/account graph is approved or prepared.
7. The unified isolated environment and guarded macOS/cross-platform launcher do not exist and are unauthorized.
8. No named host, operator, viewer list, network boundary, lifecycle authority, or cleanup policy is approved.
9. No runtime database, role-switch, network, payment-disabled, file-exclusion, or browser evidence exists.
10. All eight connected release gates remain blocked; this design does not close any of them.

## 18. Next recommended milestone

The next milestone should be **human scope/approval resolution for Option A and an implementation authorization package**, not implementation or launcher development. It should freeze:

- the five role stories and exact visible fields;
- the per-role API allowlist and authentication exceptions;
- the decision on narrow projections;
- the fictional relationship/data specification;
- the environment and network model;
- named owners, viewers, start/stop/abort authority, and retention policy; and
- acceptance tests for the backend deny policy and each presentation view.

Only after that package is approved should a separate implementation milestone build the backend restriction and new frontend routes. A later independently reviewed milestone may address the unified launcher. Stop after Phase 24A.17 and await review.

## Final status

| Status item | Result |
|---|---|
| Five-role read-only feasibility | **FEASIBLE WITH REQUIRED NEW FRONTEND VIEWS, BACKEND DEMO ENFORCEMENT, AND A UNIFIED APPROVED ENVIRONMENT — NOT IMPLEMENTED** |
| Patient demo readiness | **READY WITH RESTRICTIONS** |
| Doctor demo readiness | **READY WITH RESTRICTIONS** |
| Receptionist demo readiness | **REQUIRES NEW READ-ONLY VIEW** |
| Laboratorian demo readiness | **REQUIRES NEW READ-ONLY VIEW** |
| Administrator demo readiness | **REQUIRES NEW READ-ONLY VIEW** |
| Overall demo preparation | **PARTIALLY PREPARED** |
| Actual controlled local demo authorization | **NO-GO** |
| Connected client demo authorization | **NO-GO** |
| Eight connected release gates | **ALL BLOCKED** |
| Phase 24B | **BLOCKED / NOT STARTED** |

No production-readiness claim is made.
