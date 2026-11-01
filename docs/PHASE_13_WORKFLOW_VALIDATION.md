# Phase 13 End-to-End Workflow Validation Matrix

Assessment date: 2026-10-31

Execution level: source review, backend unit/ASGI tests, frontend Node
source-contract tests, lint, and production build. No normal database or real
browser was used.

## Evidence convention

“Automated tests” names the current coverage family rather than claiming an
end-to-end browser run. Every row still needs a browser test using fictional
accounts and an isolated database. Common failure expectations are 401 without
a session, 403 for the wrong role/CSRF failure, 404 for a hidden or missing owned
resource, 409 for a stale/conflicting transition, and 422 for invalid input.

### Patient workflows

| Workflow | Frontend route | Backend API | Role | Database entities | Validation | Expected success | Expected failure | Automated tests | Missing browser test |
|---|---|---|---|---|---|---|---|---|---|
| Registration | `/register` | `POST /api/auth/register` | Public | `users`, `patients` | Email, password, name; unique email | 201, user/profile created; login remains explicit | Duplicate/invalid rejected without partial profile | auth/API contract tests; registration UI contract | Yes: form, duplicate, network retry, login handoff |
| Login | `/login/email` | `POST /api/auth/login`; `GET /api/auth/me` | Public → patient | `users`, `auth_sessions`, `patients` | Generic credential check; session persistence | HttpOnly session/CSRF issued; patient dashboard | Generic 401; no token in browser storage | auth-session/security tests; frontend cookie test | Yes: cookies, refresh, expiry, logout, keyboard/error UX |
| Profile editing | `/patient/profile` | `PATCH /api/users/me/patient-profile` | Patient | `users`, `patients` | Own name/phone/gender limits | Own profile updated | Extra/admin fields rejected; no cross-patient target | API contract and frontend validation tests | Yes: save/reload, invalid fields, concurrent failure |
| Doctor discovery | `/`, `/patient/book` | `GET /api/users/public/doctors` | Public/patient | `users`, `doctors` | Active public-safe fields only | Search/list and preserve selected doctor through auth | Safe empty/error/retry state | clinician-directory/frontend tests | Yes: search, selection persistence, privacy field check |
| Appointment booking | `/patient/book` | `GET /api/appointments/booking-window`; `GET /api/appointments/availability`; `POST /api/appointments` | Patient | `patients`, `doctors`, `clinician_schedules`, `appointments` | Date horizon, future/published slot, ownership, patient/doctor/slot conflicts | One scheduled appointment with canonical date/start/claim | Stale/occupied/invalid slot rejected; no duplicate | appointment, schedule, concurrency and booking UI tests | Yes: real browser + isolated Mongo race and stale-slot refresh |
| Appointment cancellation | `/patient/history`, `/patient/appointments` | `POST /api/appointments/{id}/cancel` | Patient | `appointments`, `payment_attempts` | Own scheduled appointment; atomic/idempotent transition | Cancelled timestamp; claim removed; capture conflict surfaced | Other patient/not cancellable hidden/rejected | cancellation/concurrency/payment tests; UI contract | Yes: confirm dialog, double click, paid/capture race |
| Appointment rescheduling | No dedicated route | No dedicated API | Patient | Would require `appointments`, schedule, audit/link record | Not implemented | N/A | Current in-place patient reschedule must not occur | No first-class reschedule tests | **Yes and blocked by implementation**: cancellation + linked replacement design |
| Care plan viewing | `/patient/care-plan` | `GET /api/care-plans`; history/stage/goal routes as allowed | Patient | `care_plans`, `care_plan_history` | Own profile/plan only | Current plan/history shown | Other patient/plan inaccessible | care-plan authorization/API and frontend tests | Yes: empty/history/progress/revoked access |
| Exercise tracking | `/patient/exercises`, `/patient/progress` | `GET /api/exercises`; assignments; `POST /api/exercise-progress`; stats | Patient | `exercises`, `exercise_assignments`, `exercise_progress` | Own assignment/progress, duration/repetition schema | Completion recorded and stats update | Other assignment/invalid progress denied | exercise authorization/API and UI contract tests | Yes: complete exercise, retry/idempotency, charts |
| Laboratory request (“booking”) | `/patient/laboratory` | `POST /api/lab-requests`; `GET /api/lab-requests/me`; withdraw | Patient in lab demo | `lab_requests`, demo entitlement | 1–12 allowed unique demo tests; mode/contact; idempotency key | Coordination request only; no payment or confirmed slot | Unsupported catalogue/duplicate/withdraw state rejected | lab request/idempotency and frontend tests | Yes: demo isolation, retry, withdrawal, truthful non-booking copy |
| Appointment payment | `/patient/book?paymentAppointmentId=…`, `/patient/payments` | readiness, order, verify, status, abandon/cancel, history | Patient | `appointments`, `payment_attempts`, `razorpay_webhook_events` | Test configuration; own clinic appointment; server amount; signatures/capture | Server-verified paid state/history | Fail closed; no paid mutation; reconciliation for cancel race | extensive mocked payment/worker/UI tests | Yes: authorized Razorpay Test Mode matrix; currently not run |
| Report access | `/patient/reports` | `GET /api/reports`; download; `GET /api/lab-requests/me/reports`; report file | Patient | `reports`, `lab_requests`, `patients` + private files | Own patient and published/released report | Authorized inline PDF view | Unpublished/other-patient/malformed key denied | report/lab access and PDF UI tests | Yes: browser viewer, expiry/revocation, malicious-file handling |
| Notifications | `/patient/notifications`, `/notifications` | list, unread count, mark one/all read | Authenticated patient | `notifications` | Ownership on every read/update | Own list/count/read state | Other user ID not mutable | notification API/frontend route tests | Yes: polling/reload/multi-tab/ownership |
| Home visits | `/patient/home-visits` | context/entitlement; availability; `POST /api/home-visit-bookings`; request list/withdraw | Patient | entitlements, requests, schedules, appointments | Demo mode, entitlement, city/address, date/slot, idempotency | Explicit confirmed home booking or clearly provisional request state | Outside boundary/occupied/disabled rejected | home-visit isolation, booking, API/UI tests | Yes: authorized isolated demo, slot collision, address/city UX |

### Doctor / clinician workflows

| Workflow | Frontend route | Backend API | Role | Database entities | Validation | Expected success | Expected failure | Automated tests | Missing browser test |
|---|---|---|---|---|---|---|---|---|---|
| Login | `/login/email` | auth login/me/refresh/logout | Doctor | `users`, `auth_sessions`, `doctors` | Active doctor credentials/session | Doctor dashboard | Generic 401/inactive denial | auth and role-guard tests | Yes: doctor session lifecycle |
| Assigned patient access | `/doctor/patients` | `GET /api/users/patients` | Doctor | `doctors`, `patients`, `appointments` | Assignment derived from active/history relationship | Minimum assigned-patient directory | Unassigned patient absent | caseload/privacy/frontend tests | Yes: assigned vs unassigned accounts and field minimization |
| Appointment management | `/doctor/dashboard` | `GET /api/appointments`; `PATCH /api/appointments/{id}` | Doctor | `appointments`, `doctors`, `patients` | Assigned doctor; allowed lifecycle/doctor-change rules | View own schedule; permitted status updates | Other clinician appointment and billing manipulation denied | appointment authorization/status tests | Yes: status sequence, concurrent admin change, mobile UI |
| Care plan creation | `/doctor/patients/{id}/care-plan` | care-plan create/update/stage/goal/history routes | Doctor | plans/history, patients, appointments | Assigned patient and schema limits | Plan created/updated with history | Unassigned patient/plan denied | care-plan authorization/history tests | Yes: full authoring/edit/history and stale failures |
| Exercise assignment | `/doctor/patients/{id}/exercises` | exercise assignment create/update/list | Doctor | exercises, assignments, patients | Assigned patient; catalog exercise; dosage fields | Assignment available to patient | Unassigned/invalid exercise denied | exercise API/authorization and frontend tests | Yes: create/edit/revoke and patient reflection |
| Patient history | `/doctor/patients/{id}` | `GET /api/users/doctor/patients/{id}/history` | Doctor | patient, appointments, published lab reports | Current assignment; privacy-reduced response | Assigned history only | Unassigned/missing uniformly 404 | doctor-history/caseload/frontend tests | Yes: direct URL IDOR attempt and assignment removal |
| Clinical report access/authoring | `/doctor/reports/new`, patient history | reports create/list/get/download; `/api/lab-requests/doctor/reports` | Doctor | reports, lab requests, patients, files | Assigned patient; finalized/published lab release | Create allowed report; view authorized released reports | Other patient/unpublished file denied | report authorization/storage and frontend tests | Yes: upload/view/direct URL IDOR/malformed PDF |

### Admin workflows

| Workflow | Frontend route | Backend API | Role | Database entities | Validation | Expected success | Expected failure | Automated tests | Missing browser test |
|---|---|---|---|---|---|---|---|---|---|
| Login | `/login/email` | auth login/me/refresh/logout | Admin | `users`, `auth_sessions` | Active admin credentials/session | Admin dashboard | Generic 401/inactive denial | auth and role-route tests | Yes: admin session lifecycle |
| Patient management | `/admin/patients`, create/edit/history routes | users patient list/get/create/update/history | Admin | users, patients, appointments, reports, audit metadata | Role, field schema, unique email | Create/edit/view history with metadata-only audit | Invalid/duplicate/missing rejected | user/admin-history/audit/frontend tests | Yes: create/edit/history and sensitive-value audit check |
| Doctor/staff management | `/admin/doctors`, `/admin/staff` | users doctors/staff/laboratorians routes | Admin | users, doctors, auth data | Supported role, unique email, profile fields | Staff created/listed; doctor profile updated | Non-admin/invalid/duplicate denied | staff/doctor API and frontend validation tests | Yes: create/filter/edit/deactivate lifecycle |
| Appointment management | `/admin/appointment-booking`, dashboard/billing lists | admin create, list, patch; schedule preview/publish | Admin | appointments, patient/doctor profiles, schedules | Existing patient/doctor, valid slot/status | Managed booking/status/assignment | Collision/stale/invalid target rejected | appointment/schedule/admin UI tests | Yes: booking, reassignment, status, schedule conflict |
| Laboratory management | `/admin/laboratory` | lab-request admin list/status/assignment/publish | Admin | lab requests, users/laboratorians, private files | State machine, assignment, finalized report before publish | Assign/review/publish; patient release | Invalid transition/unfinalized/missing file denied | lab workflow/role/publication tests | Yes: full patient→admin→lab→admin→patient chain |
| Payment visibility | `/admin/billing` | captured review and reconcile; appointment list | Admin | appointments, payment attempts | Admin role; provider-confirmed attempt only | View paid/unpaid/reconciliation; bounded retry | Cannot manually forge paid state; transient failure remains visible | payment/reconciliation/frontend tests | Yes: authorized Test Mode capture/restart/review |
| Audit history | patient history, clinician schedules, care-plan history | patient history; schedule get; care-plan history | Admin (scope varies) | patient audit, schedule audit, care-plan history | Role/resource scope; metadata minimization | Actor/time/changed fields or revisions visible | Other roles denied; sensitive prior values absent | audit/history/API/frontend tests | Yes: changes appear once, ordering, retention limit |
| Report management | `/admin/reports/new`, patient/lab views | reports create/list/download; lab publish | Admin | reports, lab requests, patients, files | Patient exists; PDF/type/size/path; publication state | Authorized report creation/publication/access | Invalid file/path/state denied | report storage/access/lab publication tests | Yes: upload/view/publish and malicious PDF scenario |
| Notifications | `/admin/notifications`, `/notifications` | notifications list/count/read | Admin | notifications | Own notification records only | Read/manage own notifications | Cross-user update denied | notification/frontend tests | Yes: live admin events and read state |

## Additional role journeys

Receptionist routes intentionally expose a reduced patient directory, clinic
booking/cancellation, and home-visit coordination without clinical history or
billing. Laboratorian routes expose assigned lab requests and report preparation,
not patient-wide records or publication. Both have automated role-contract tests
but still need isolated browser IDOR and state-transition testing.

## Validation summary

- Automated baseline: backend **346 passed**; frontend **58 passed**; lint,
  production build, and bundle budget passed.
- Source/API contract coverage is broad, especially for role checks, ownership,
  appointment races, lab state, and mocked payment failures.
- There is no first-class appointment rescheduling workflow.
- The active laboratory experience is a demo coordination request, not a priced,
  confirmed booking or payment flow.
- No real browser E2E suite, connected isolated Mongo workflow suite, protected
  database validation, or Razorpay Test Mode run was completed in Phase 13.

## Browser execution order

After an isolated environment is authorized: seed only fictional accounts in the
dedicated test database, validate login/session/role boundaries first, then
appointment/cancellation, care/report/lab workflows, and finally authorized
Test Mode payments. Record screenshots with fictional data only and destroy test
data according to the approved environment cleanup policy—not by ad hoc commands.
