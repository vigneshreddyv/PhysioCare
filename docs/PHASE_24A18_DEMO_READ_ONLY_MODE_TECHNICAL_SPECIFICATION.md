# Phase 24A.18 — Demo Read-Only Mode Technical Specification and Implementation Plan

Assessment date: 2026-11-02

Branch: `codex/physiocare-integration-2026-10-31`

Assessment HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

> **Planning status:** every change described as proposed in this document is **NOT IMPLEMENTED**. This milestone authorizes no application, test, environment, launcher, account, fixture, database, or service change.

## 1. Executive summary

A dedicated five-role, read-only local demonstration mode is technically feasible. The recommended security model is a separate, explicitly selected local environment with a dedicated database and a fail-closed backend request allowlist. The mode must add restrictions to the existing cookie-session, CSRF, role, patient-owner, doctor-assignment, and laboratorian-assignment controls; it must never bypass or replace them.

The current broad product GET endpoints are not a sufficient v1 allowlist. Several return more information than the presentation needs, accept query parameters that select excluded workflows, or sit beside mutations in the same UI. The proposed v1 therefore permits only the existing authentication lifecycle routes and a minimal health check, then introduces demo-specific GET endpoints with explicit response schemas for the five roles. Those proposed endpoints do not exist today and remain denied until separately implemented and tested.

All ordinary product routes—including unlisted GET routes—must be denied while read-only demo mode is active. Product POST, PUT, PATCH, and DELETE requests have no exception. The only unsafe-method exceptions are login, refresh, and logout because server-side session creation, rotation, and revocation are required to preserve normal authentication security. CSRF establishment and rate-limit accounting are also documented security-lifecycle side effects.

The new mode must be disabled by default; selected by its own environment file and explicit flag; restricted to a fixed loopback database, ports, origin, and instance identity; mutually exclusive with existing laboratory and home-visit demos; and rejected by staging and production. Payments, reconciliation, files, PDFs, scanner access, external storage, public API documentation, public registration, and real patient data remain excluded.

**Readiness decision:** architecture and implementation plan are complete enough for independent review, but implementation is **NOT STARTED**. Five-role demo remains **FEASIBLE, NOT IMPLEMENTED**. Actual local and connected demos remain **NO-GO**.

## 2. Previous milestone status

Phase 24A.17 remains accurate:

- patient and doctor are **READY WITH RESTRICTIONS**;
- receptionist, laboratorian, and administrator **REQUIRE NEW READ-ONLY VIEWS**;
- frontend-only control hiding is not a security boundary;
- a backend demo-specific allowlist is required;
- all 11 Phase 24A.16 approvals remain **PENDING**, with 0 approved;
- demo preparation remains **PARTIALLY PREPARED**;
- actual controlled local demo and connected client demo remain **NO-GO**;
- all eight connected release gates remain **BLOCKED**; and
- Phase 24B remains **BLOCKED / NOT STARTED**.

Phase 24A.15 and 24A.16 test results remain historical evidence. No earlier report grants implementation or execution permission.

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
| Untracked paths | 94 |
| Total dirty paths | 208 |

The complete status was inspected. All existing tracked and untracked work was preserved. This report should be the only new path, producing an expected after-state of 0 staged, 114 tracked modified, 95 untracked, and 209 total dirty paths.

## 4. Existing security architecture

### 4.1 Configuration and startup

- `Settings` forbids unknown model fields, masks configured secret fields in diagnostics, validates independent access/refresh secrets, and validates environment-specific database, payment, CORS, proxy, scanner, and storage properties (`backend/app/core/config.py:104-272`).
- Runtime isolation is revalidated before external startup (`backend/app/core/config.py:291-305` and `backend/app/main.py:31-50`).
- Ordinary development requires a loopback `physiocare_dev` database and disabled payments/scanning; staging and production have separate strict identities (`backend/app/core/config.py:307-475`).
- Production already rejects the two existing demo flags and local/demo selectors (`backend/app/core/config.py:477-489`). It does not yet know a five-role read-only flag.
- Existing lab and home-visit demo modes pin database identity, loopback listener, backend port, disabled payments, and a dedicated frontend origin (`backend/app/core/config.py:653-715`). Neither is an appropriate substitute for a unified five-role mode.
- API documentation is disabled by policy in production and opt-in for staging and the existing demos (`backend/app/main.py:62-92`).
- Payment reconciliation starts whenever its setting is enabled (`backend/app/main.py:50-60`), so the new mode must fail startup unless reconciliation is false.

### 4.2 Authentication and session controls

- Access is cookie-based. `get_current_user` validates the access JWT, server-side session existence, revocation, expiry, session/user binding, active user, and CSRF for unsafe methods (`backend/app/middleware/auth.py:20-109`).
- `RoleChecker` enforces explicit internal roles after authentication (`backend/app/middleware/auth.py:111-120`).
- Login creates a server-side session; refresh atomically rotates it; logout revokes it (`backend/app/services/auth_service.py:157-227,246-258`). These are unavoidable authentication-state writes.
- Refresh and logout require CSRF validation. `GET /api/auth/csrf` validates the refresh session and resets the CSRF cookie; rate limiting can update security buckets (`backend/app/api/auth.py:100-154`).
- Login and refresh return tokens only in cookies plus a CSRF value in the response; legacy bearer storage is removed by the frontend (`frontend/src/context/AuthContext.jsx:60-69`).
- Existing authentication does not require a dedicated five-role rehearsal tag at login. That additional demo identity check is missing.

### 4.3 Request and response controls

- Credentialed CORS uses explicit origins (`backend/app/main.py:100-106`).
- Unsafe cross-site origins are rejected, JSON bodies are bounded, and authenticated/session responses receive `private, no-store` cache headers (`backend/app/main.py:124-190`).
- Clinical list paging is bounded to pages 1–1000 and page sizes 1–100 (`backend/app/core/pagination.py:8-34`). Demo endpoints should use a smaller fixed/default size but retain these hard caps.
- FastAPI currently registers all normal product routers beneath `/api` (`backend/app/main.py:192-207`). There is no global demo deny layer.

### 4.4 Existing ownership and assignment controls

- Patient list/history/report queries derive the patient identity from the authenticated user.
- Doctor patient lists pass the authenticated doctor ID to the service; patient detail/history checks `AppointmentRepository.has_assigned_patient` and uses identical missing/unassigned responses (`backend/app/api/users.py:146-174`; `backend/app/services/doctor_history_service.py:18-79`).
- Laboratorian assigned work is queried by the authenticated laboratorian user ID (`backend/app/services/lab_request_service.py:113-135`; `backend/app/repositories/lab_request_repository.py:114-119`).
- These controls remain mandatory inside demo mode. The proposed policy adds a route boundary before them and never grants new access.

## 5. Proposed demo-mode boundary — NOT IMPLEMENTED

### 5.1 Control model

The future mode should use three independent layers:

1. **Startup identity guard:** configuration proves this is the dedicated local read-only environment before any database, scanner, storage, or worker initialization.
2. **Global fail-closed route guard:** when the mode is active, an immutable method/path table rejects every request not expressly listed below. It applies to all backend HTTP paths, not only `/api`.
3. **Endpoint authorization:** every demo data endpoint still calls `get_current_user` through `RoleChecker`, then applies patient owner, doctor assignment, or laboratorian assignment constraints in service/repository queries.

The frontend may use a display flag to select demo navigation, but that flag has no authority. Only backend configuration and enforcement define the security mode.

### 5.2 Proposed modules

| Proposed module/change | Responsibility | Status |
|---|---|---|
| `backend/app/core/config.py` | New settings/constants, selector validation, mutual exclusion, startup fail-closed checks | **NOT IMPLEMENTED** |
| `backend/app/core/read_only_demo.py` | Immutable route specifications, rehearsal tag, path normalization helpers | **NOT IMPLEMENTED** |
| `backend/app/middleware/read_only_demo.py` | Global active-mode allowlist/deny enforcement | **NOT IMPLEMENTED** |
| `backend/app/api/demo_read_only.py` | Proposed demo-only GET routes with `RoleChecker` dependencies | **NOT IMPLEMENTED** |
| `backend/app/schemas/demo_read_only.py` | Explicit minimum response schemas | **NOT IMPLEMENTED** |
| `backend/app/services/demo_read_only_service.py` | Owner/assignment-scoped orchestration and schema construction | **NOT IMPLEMENTED** |
| Existing repositories plus narrowly scoped projection helpers | Bounded, deterministic, side-effect-free reads | **NOT IMPLEMENTED** |
| `backend/app/main.py` | Register middleware/router; suppress docs; never start reconciliation in demo | **NOT IMPLEMENTED** |
| `backend/app/middleware/auth.py`, `backend/app/services/auth_service.py` | Require exact demo tag and approved role for every demo session/account | **NOT IMPLEMENTED** |

### 5.3 Enforcement behavior

- The middleware activates only when the validated backend setting is true.
- Outside demo mode, existing product route behavior remains unchanged; proposed `/api/demo-read-only/*` routes must return 404 through a `require_read_only_demo` dependency.
- In demo mode, unmatched paths and method/path mismatches return a uniform non-disclosing 404. Wrong roles on an allowed route continue to return the existing 403; unauthenticated requests to allowed protected routes return 401.
- Match decoded, canonical ASGI paths against explicit route templates. Reject encoded slash/backslash, dot segments, duplicate slash ambiguity, invalid UTF-8, trailing-path variants, and unexpected route parameters. Dynamic IDs must match the exact identifier grammar used by the endpoint.
- Do not use prefix matching such as `startswith('/api/demo')` as authorization.
- Ignore `X-HTTP-Method-Override`, `_method`, and similar override inputs; authorize only `request.method` supplied by the server.
- CORS preflight `OPTIONS` is a transport exception only for exact allowed paths and the one approved origin. It grants no API capability. `HEAD` remains denied unless later proven necessary and explicitly listed.
- Query parameters never expand an allowlisted route. Each endpoint uses strict Pydantic query models with `extra='forbid'`, fixed enums, bounded lengths/date ranges, and bounded pagination.
- The middleware must run early enough to stop disallowed endpoint execution. Endpoint dependencies remain responsible for authentication and role/ownership checks.

### 5.4 Demo identity enforcement

Every pre-created demo user and server session must carry one exact versioned rehearsal tag, proposed as `five_role_read_only_demo_v1`. In active mode:

- login rejects inactive, untagged, differently tagged, or unsupported-role accounts using the normal generic authentication failure;
- `get_current_user` additionally requires both the user and session tag to match and the role to be one of the five approved internal roles;
- refresh preserves the same session ID/tag and rechecks the tagged user;
- tokens signed with another environment's secrets cannot validate; and
- no public registration or staff creation route is allowlisted.

This is an additional restriction. It must not make demo tags valid in ordinary development, staging, or production.

## 6. Environment and configuration guards — NOT IMPLEMENTED

### 6.1 Proposed configuration contract

Names below are proposed and do not exist in current source:

| Setting/constant | Required value/behavior |
|---|---|
| `READ_ONLY_DEMO_MODE` | Boolean, default `False`; must be explicitly `True` |
| `READ_ONLY_DEMO_INSTANCE_ID` | Exact approved value such as `physiocare-five-role-read-only-demo` |
| `READ_ONLY_DEMO_DATABASE_NAME` | Exact dedicated name such as `physiocare_read_only_demo`; never reused by development, lab demo, home-visit demo, staging, or production |
| `READ_ONLY_DEMO_MONGODB_URL` | One exact loopback MongoDB listener on a dedicated port; no remote host, SRV, multiple hosts, options, or production/staging credential material |
| `PHYSIOCARE_READ_ONLY_DEMO_ENV_FILE` | Sole selector; must resolve to the dedicated demo home and cannot coexist with other selectors |
| `HOST` / `PORT` | Exact `127.0.0.1` and dedicated backend port approved for the launcher |
| `CORS_ORIGINS` | Exactly one dedicated `http://127.0.0.1:<frontend-port>` origin |
| `API_DOCUMENTATION_ENABLED` | Exactly `False` |
| `LAB_DEMO_MODE`, `HOME_VISIT_DEMO_MODE`, `PHYSIOCARE_LOCAL_DEV` | All `False`; modes are mutually exclusive |
| `RAZORPAY_MODE` | `disabled` |
| Razorpay keys/webhook secret | Empty |
| `APPOINTMENT_BILLING_CURRENCY` | Empty |
| `PAYMENT_RECONCILIATION_ENABLED` | `False`; no worker startup |
| `PDF_SCANNER_MODE`, `PDF_SCANNER_SOCKET` | `disabled` and empty; no scanner connection |
| Report storage paths | Dedicated unused local paths only; routes that read/write them remain denied |
| `AUTH_RATE_LIMIT_ENABLED` | `True` |
| `TRUSTED_PROXY_NETWORKS` | Empty for loopback-only v1 |
| JWT secrets | Fresh, distinct, demo-only, minimum-length secrets; never logged or shared with another environment |

Use `ENVIRONMENT='development'` only if the validator explicitly distinguishes this mode from ordinary development and requires the dedicated selector/identity. A separate `demo` environment value is also viable, but it expands the environment enum and cookie policy. The lower-risk change is to follow the existing isolated-demo pattern while adding strict mutual exclusion and its own selector.

### 6.2 Fail-closed rules

- Flag true without the exact selector, or selector present without the flag: startup error.
- More than one environment selector or demo flag: startup error.
- Read-only mode combined with staging or production: startup error.
- Staging and production validators explicitly reject the new flag, selector, instance ID, demo database, and reserved database/host tokens.
- Missing instance identity, mismatched database name/URL, non-loopback host, wrong ports/origin, enabled docs, payment material, reconciliation, scanner, proxy, or other demo mode: startup error.
- `validate_runtime_startup()` repeats the complete check before `init_db()`.
- The database client receives only the validated dedicated URL and selects only the dedicated database.
- The health response identifies `read_only_demo`, `payments_enabled: false`, and `documentation_enabled: false`, but must not disclose database name, credentials, storage paths, secrets, or internal host details.

## 7. Complete proposed API allowlist — NOT IMPLEMENTED

### 7.1 Existing lifecycle/readiness routes retained

These exact paths were recovered from source. Only these ordinary routes may survive in active demo mode:

| Method and exact path | Roles/authentication | Existing dependency/ownership | Projection/side effects | Inclusion reason |
|---|---|---|---|---|
| `GET /health` | Unauthenticated; loopback boundary | None today | Must be reduced to non-sensitive readiness booleans. Existing implementation would need a demo branch. Read-only. | Guarded launcher readiness only |
| `POST /api/auth/login` | One pre-created tagged account; unauthenticated request | Rate limiter; future exact tag/role check | Creates server session and cookies; documented authentication-write exception | Establish authenticated session |
| `GET /api/auth/csrf` | Valid tagged refresh cookie | Refresh-session validation and rate limiter | Sets CSRF cookie; may update security throttle state | Recover CSRF safely |
| `POST /api/auth/refresh` | Valid tagged refresh cookie and CSRF | Refresh-session validation | Atomically rotates session secret/cookies; documented authentication-write exception | Preserve current secure session behavior |
| `POST /api/auth/logout` | Valid session/refresh context and CSRF | Refresh/session validation | Revokes server session and clears cookies; documented authentication-write exception | Mandatory safe logout |
| `GET /api/auth/me` | Any of five tagged roles; authenticated | `get_current_user`; future tag check | Demo-specific `DemoSessionOut`: account ID, fictional email, display name, role, `demo_mode: true`, and only minimal patient/doctor profile fields | Frontend session confirmation and role routing |

`POST /api/auth/register` is expressly excluded. The lifecycle exceptions above do not permit product-data writes.

### 7.2 Proposed demo data routes

The following path names are **future proposed endpoints, not claims about current routes**. They remain denied until separately implemented. The “current source basis” column records the actual existing route/repository used to justify feasibility, satisfying the requirement not to misrepresent invented paths as existing APIs.

| Proposed method/path | Role | Auth and existing boundary retained | Minimum projection | Current source basis | Read-only/new endpoint | Excluded mutations and reason |
|---|---|---|---|---|---|---|
| `GET /api/demo-read-only/patient/completed-visits` | patient | `RoleChecker(['patient'])`; resolve patient from current user | `visit_id`, clinic date/time/timezone, clinician display name, `service_mode='clinic'`, `status='completed'` | Current `GET /api/appointments/me/history` (`backend/app/api/appointments.py:150-165`) | **New endpoint required**; current `AppointmentOut` is too broad | No create/cancel/reschedule/payment; presents owned completed visits only |
| `GET /api/demo-read-only/patient/report-metadata` | patient | Patient role; resolve owner from current user; require no file path | `report_id`, title, category, report date, therapist display name, `has_file=false` | Current `GET /api/reports` (`backend/app/api/reports.py:34-54`) | **New endpoint required**; current response exposes clinical content/description/patient/booking IDs | No report detail, upload, download, PDF, or file path |
| `GET /api/demo-read-only/patient/notifications` | patient | Patient role; recipient equals current user; server filters `is_read=true` | notification ID, title, message, type, created time, `is_read=true`; no related entity ID | Current `GET /api/notifications` (`backend/app/api/notifications.py:11-31`) | **New endpoint required and feature-gated until browser verification** | No mark-one/read-all PATCH; no automatic state transition |
| `GET /api/demo-read-only/doctor/patients` | doctor | Doctor role; authenticated doctor ID scopes repository query | patient ID and fictional display name only | Current doctor branch of `GET /api/users/patients` (`backend/app/api/users.py:146-158`) | **New endpoint required**; current response includes phone/DOB/gender | No care-plan, exercise, report, profile, or contact management |
| `GET /api/demo-read-only/doctor/patients/{patient_id}/completed-visits` | doctor | Doctor role; exact assignment check; identical missing/unassigned 404 | patient ID/display name and completed visit ID/date/time/mode/status | Current `GET /api/users/doctor/patients/{patient_id}/history` and assignment service (`backend/app/api/users.py:209-233`) | **New endpoint required**; current response includes clinical details and released reports | No status update, clinical authoring, report/PDF, care-plan/exercise mutation |
| `GET /api/demo-read-only/reception/schedule` | receptionist | Receptionist role; bounded approved date range | appointment ID, fictional patient/clinician names, date/time/timezone, assignment-pending flag, status | Current `GET /api/appointments/reception` (`backend/app/api/appointments.py:53-65`) | **New endpoint required**; current response includes email/phone/address/cancellation fields | No booking, cancellation, rescheduling, reason, billing, address, or contact data |
| `GET /api/demo-read-only/reception/patients` | receptionist | Receptionist role | patient ID and fictional display name only | Current `GET /api/users/reception/patients` (`backend/app/api/users.py:123-134`) | **New endpoint required**; current response includes email/phone | No edit contact or patient mutation |
| `GET /api/demo-read-only/reception/clinicians` | receptionist | Receptionist role; active clinicians only | clinician ID, display name, specialization, accepts-home-visits boolean only if approved | Current `GET /api/users/reception/doctors` (`backend/app/api/users.py:112-121`) | **New endpoint required**; current public profile includes bio/image/links | No clinician/profile/schedule mutation and no external links |
| `GET /api/demo-read-only/reception/availability` | receptionist | Receptionist role; validated clinician/date, published schedule logic | date/timezone and bounded slots: time, availability state | Current authenticated `GET /api/appointments/availability` (`backend/app/api/appointments.py:86-92`) | **New role-specific endpoint required**; current route is open to every authenticated role | No booking; query cannot select another workflow |
| `GET /api/demo-read-only/laboratory/assigned` | laboratorian | `RoleChecker(['laboratorian'])`; assigned user equals current user | request ID, fictional patient name, `mode='clinic_visit'`, selected tests, request status, report status, created time | Current `GET /api/lab-requests/laboratory/assigned` (`backend/app/api/lab_requests.py:89-96`) | **New endpoint required** for narrow projection | No upload, submit, edit, filename/time, report-file, address, phone, payment, provider data |
| `GET /api/demo-read-only/admin/staff` | admin | Admin role | staff ID, fictional display name, role, active flag, created date | Current `GET /api/users/staff` (`backend/app/api/users.py:60-74`) | **New endpoint required**; current response includes email | No create, credential, role, activation, entitlement, or account mutation |
| `GET /api/demo-read-only/admin/clinicians` | admin | Admin role | clinician ID, display name, specialization, active-today flag | Current `GET /api/users/doctors` (`backend/app/api/users.py:88-100`) | **New endpoint required**; current response includes email and external-profile fields | No profile/schedule editing |
| `GET /api/demo-read-only/admin/overview` | admin | Admin role | today/yesterday appointment counts and morning/afternoon/evening counts only | Current `GET /api/analytics/admin-daily-activity` (`backend/app/api/analytics.py:15-17`) | New wrapper/schema recommended; source aggregation is read-only | No patient rows, billing, payments, revenue, subscriptions, security or infrastructure metrics |

All list endpoints use deterministic ordering, default page size no greater than 25, maximum page size no greater than 50, and existing hard page caps. Date ranges are clinic-timezone-aware and narrowly bounded.

### 7.3 Explicit deny set

All paths not listed in sections 7.1–7.2 are denied. This explicitly includes:

- registration, staff creation, password/account/profile management, activation/deactivation, and role changes;
- all ordinary appointment GETs and all appointment create/cancel/update/reschedule/payment routes;
- care plans, exercises, exercise progress, clinical authoring, and admin patient history;
- laboratory bookings, lab-request create/withdraw/review/assignment/publication/upload, legacy laboratory APIs, and every report-file route;
- all `/reports/{id}` detail/download/upload paths and every PDF/file viewer;
- payment readiness/history/status, order/verify/abandon/cancel/reconciliation, and `/api/webhooks/razorpay`;
- demo entitlement GET/mutation routes and home-visit request/booking routes;
- clinician schedule draft/preview/publish and all other administrator management routes;
- broad `/api/analytics/stats`, which includes billing/revenue-adjacent values;
- API documentation and OpenAPI routes; and
- maintenance, migration, index, fixture, seed, or cleanup operations, whether HTTP-exposed now or added later.

## 8. Role-specific view specifications — NOT IMPLEMENTED

| Role/view | Proposed frontend route | Backend data | UI requirements | Required authorization/tests |
|---|---|---|---|---|
| Patient overview/profile | `/demo/patient` | Demo-specific `/api/auth/me` projection | Fictional name/email and approved minimal profile; demo banner; logout only | Patient role/tag; another account cannot read; no edit form |
| Patient completed history | `/demo/patient/history` | `GET /api/demo-read-only/patient/completed-visits` | Completed clinic rows only; no reason, payment, cancel, book, address, or detail action | Owner derived from session; completed-only query/projection tests |
| Patient report metadata | `/demo/patient/reports` | `GET /api/demo-read-only/patient/report-metadata` | Text metadata only; no file icon/link/view/download | Owner + `file_path` absent; PDF paths denied |
| Patient notifications | `/demo/patient/notifications` | Gated notification endpoint | Render only all-read fictional notifications; no mark-read controls | Recipient scope; all records read; browser network verification before inclusion |
| Doctor directory | `/demo/doctor` | `GET /api/demo-read-only/doctor/patients` | Assigned fictional aliases only | Doctor role and assignment-scoped repository test |
| Doctor completed history | `/demo/doctor/patients/:patientId` | Assigned completed-visits endpoint | Minimal completed clinic history; no report/care/exercise/status controls | Missing and unassigned identical; no cross-doctor data |
| Doctor schedule | Not included in v1 | None | Do not claim a schedule; no safe existing doctor schedule page | Absence/navigation tests |
| Reception schedule | `/demo/reception` | Demo schedule endpoint | Date filters, patient/clinician aliases, date/time/status only | Reception role; strict date bounds; no contact/address/clinical/payment fields |
| Reception directory | `/demo/reception/patients` | Demo patient directory endpoint | Alias-only directory | Reception role; no edit form; bounded paging |
| Reception availability | `/demo/reception/availability` | Demo clinicians + availability endpoints | Read-only clinician/date selection and slot display; no confirm/book action | Reception role; query validation; no mutation/background call |
| Laboratory assigned work | `/demo/laboratory` | Demo assigned endpoint | Test names and workflow statuses; no file control | Laboratorian role and exact assignment; no address/contact/file metadata |
| Admin operations | `/demo/admin` | Admin overview/staff/clinician endpoints | Aggregate counts plus fictional role/status and clinician lists | Admin role; no email, patient directory, billing, credentials, or management controls |

Each view must have loading, empty, 401/session-expired, 403/wrong-role, 404/unavailable, and recoverable 5xx states. A forbidden response must never fall back to an ordinary product route.

## 9. Response projection requirements — NOT IMPLEMENTED

### 9.1 Explicit schema rules

- Define every response with a dedicated Pydantic model and `response_model`; never return a document, `model_dump()` of a database model, or arbitrary `dict` from demo routes.
- Prefer repository `$project`/aggregation fields matching the response rather than loading complete documents.
- Use opaque record IDs only when required for stable React keys or a permitted child route. Never return user IDs, session IDs, token claims, payment IDs, provider references, storage keys, file paths, audit/security metadata, hashes, or revision/write-control fields.
- List schemas must remain bounded, deterministic, and stable across pagination. Search strings and date ranges are normalized and capped.
- Store and display only approved fictional aliases. No real addresses or unnecessary email/phone values are returned.

### 9.2 Existing shapes that are too broad

| Existing response | Excess fields for demo | Required action |
|---|---|---|
| `AppointmentOut` (`backend/app/schemas/appointment.py:62-93`) | reason, address/city, symptoms/body regions, pain/duration, billing, payment identifiers, cancellation data, revision | Do not allow; create minimal completed-visit and reception schedule schemas |
| `DoctorAppointmentOut` (`backend/app/schemas/appointment.py:96-118`) | reason, address/city, symptoms/body regions, pain/duration, revision | Do not allow; create minimal assigned completed-visit schema |
| `ReceptionAppointmentOut` (`backend/app/schemas/appointment.py:121-140`) | email, phone, address/city, cancellation capability/deadline/message | Do not allow; create minimal schedule schema |
| `PatientOut` / `DoctorPatientOut` / `ReceptionPatientOut` (`backend/app/schemas/patient.py:48-75`) | contact, DOB, gender, subscription, email depending on role | Do not allow for directories; create alias-only schemas |
| `ReportResponse` (`backend/app/schemas/report.py:23-34`) | patient/booking IDs, description, clinical content, file state, created time | Do not allow; create file-free metadata schema |
| `NotificationOut` (`backend/app/schemas/notification.py:5-13`) | recipient ID and related entity ID | Create recipient-derived, all-read projection; gate feature |
| `LaboratorianLabRequestOut` (`backend/app/schemas/lab_request.py:73-85`) | phone, address/city, filename, upload time | Do not allow; create clinic-only workflow metadata schema |
| `StaffOut` (`backend/app/schemas/auth.py:29-35`) | email | Create fictional alias/role/status schema |
| `DoctorOut` (`backend/app/schemas/doctor.py:22-26`) | email plus public links/profile content inherited from `DoctorProfileFields` | Create name/specialization/status schema |
| `/analytics/stats` arbitrary dictionary | paid totals, revenue trend, subscriptions and broader metrics | Deny; use explicit daily overview schema only |

## 10. Frontend architecture — NOT IMPLEMENTED

### 10.1 Route and component map

```text
App.jsx
└── /demo
    └── DemoProtectedRoute (UX guard; backend remains authoritative)
        └── RoleProtectedRoute
            └── DemoLayout
                ├── DemoModeBanner
                ├── DemoNavigation (role-specific, immutable entries)
                ├── DemoForbiddenState / DemoSessionExpiredState
                ├── patient/
                │   ├── DemoPatientOverview
                │   ├── DemoPatientHistory
                │   ├── DemoPatientReports
                │   └── DemoPatientNotifications (gated)
                ├── doctor/
                │   ├── DemoDoctorPatients
                │   └── DemoDoctorPatientHistory
                ├── receptionist/
                │   ├── DemoReceptionSchedule
                │   ├── DemoReceptionPatients
                │   └── DemoReceptionAvailability
                ├── laboratorian/DemoLaboratoryAssignments
                └── admin/DemoAdminOverview
```

Expected files include `frontend/src/App.jsx`, a new `frontend/src/layouts/DemoLayout.jsx`, `frontend/src/routes/DemoProtectedRoute.jsx`, new demo-only components/pages, and `frontend/src/services/demoReadOnlyApi.js`.

### 10.2 Behavior contract

- The backend-authenticated `/api/auth/me` response supplies `demo_mode: true`; an optional Vite flag may change presentation/build routing but cannot grant access.
- Successful login redirects to the role's `/demo/*` landing route. Normal role routes are absent from demo navigation and backend requests to their APIs are denied.
- Use a separate demo navigation model, not filtered copies of `Sidebar.jsx`, whose current menu includes booking, management, reports, billing, settings, and upload workflows.
- Render a persistent “Fictional data · Read-only local demonstration” indicator and role label.
- Demo components contain no `<form>` for mutation, mutation hook, file input, blob/PDF helper, payment control, management link, optimistic update, or automatic state-changing request.
- `demoReadOnlyApi.js` exports only named GET functions for the exact demo endpoints; it does not accept arbitrary paths or methods.
- Axios retains cookie credentials and refresh behavior. A 401 clears private state through the existing auth flow. A 403 shows a friendly role-boundary state. A 404 shows “not available in this demonstration” and never redirects to an ordinary workflow.
- Logout remains available and keeps current confirmed-revocation behavior. Query caches and any PDF viewers are cleared on account change even though demo views cannot open PDFs.
- Route-split bundles and tests must confirm normal mutation pages are not imported by demo routes.

## 11. Session and environment isolation — NOT IMPLEMENTED

- Use a dedicated five-role demo database on an exact loopback listener. It must contain only approved fictional, tagged records and must never reuse development, lab-demo, home-visit-demo, staging, or production data.
- The process receives no production/staging database URL or credentials, payment keys, webhook secret, external storage credentials, or scanner socket.
- Pre-create exactly the approved accounts outside presentation time after separate authorization: one per role unless the approved script specifies more for assignment-negative tests. No account creation is available in the UI/API.
- Bind backend and frontend to `127.0.0.1` on dedicated fixed ports. Any non-loopback isolated interface is a separate architecture decision requiring written network/security approval and new validation.
- Retain HttpOnly access/refresh cookies, SameSite=Lax, scoped paths, CSRF cookie/header comparison, server-side session validation, rate limiting, private/no-store cache headers, and role checks. For loopback HTTP, `Secure` cannot function; no LAN/public exposure is permitted.
- Keep access lifetime at or below the current 15 minutes. Reduce refresh lifetime to the approved demo window (recommended maximum one day), rotate on refresh, revoke on logout, and reject a session whose tag/user/role no longer matches.
- API documentation/OpenAPI remains disabled. Root and every unlisted health/diagnostic endpoint remain denied.
- Logs must exclude request/response bodies, cookies, tokens, secrets, credentials, contact data, clinical text, raw database URLs, file paths, and stack traces shown to viewers. Preserve only approved redacted lifecycle evidence.
- Startup order: validate configuration → construct app/allowlist → initialize only dedicated database → confirm reconciliation/scanner/external integrations remain off → expose health.
- Shutdown order: block new presentation activity → logout active session if possible → stop only tracked frontend/backend/database processes → verify ports closed → preserve approved redacted evidence. Do not delete records, files, volumes, credentials, or logs without separate cleanup approval.
- Restart repeats all validation and never auto-seeds, migrates, indexes, repairs, or cleans data.

## 12. Security test matrix — NOT IMPLEMENTED / NOT EXECUTED

| Area | Required tests | Expected result |
|---|---|---|
| Authentication | No cookie; invalid signature; expired access; missing/revoked/expired session; inactive user; untagged/wrong-tag user or session; unsupported role | 401/403 as specified; no demo data |
| Login lifecycle | Tagged account success; untagged/ordinary account generic failure; rate limit; session tag copied; cookie attributes | Only approved tagged role establishes session |
| Refresh/CSRF/logout | Missing/mismatched CSRF; refresh replay; rotation race; logout revocation; post-logout access | Existing protections remain effective; logout invalidates session |
| Default/environment | Mode default false; selector/flag mismatch; multiple selectors; wrong instance/database/URL/host/port/origin; enabled docs/payment/reconciliation/scanner/proxy | Settings/startup fails before external connection |
| Staging/production | New flag, selector, instance ID, reserved DB/host token in staging/production | Configuration rejected |
| Frontend non-authority | Frontend flag true while backend mode false; direct request to proposed endpoint; normal API request from demo UI | No access; backend is authoritative |
| Allowlisted GETs | Each exact method/path with correct role/tag and valid query | 200 and explicit minimal schema |
| Unlisted GETs | Every currently registered GET not in allowlist, root/docs/OpenAPI, path variants | Uniform deny; endpoint/service not invoked |
| Unsafe methods | POST/PUT/PATCH/DELETE to every product route; unsafe method on demo GET; HEAD unless listed | Denied before endpoint; no write mock called |
| Lifecycle exceptions | Exact login/refresh/logout only; path suffix/prefix variants | Only exact existing endpoints work |
| Route normalization | Encoded slash/backslash/dot, duplicate slash, trailing slash, invalid ID, mixed case, percent encoding, query `_method`, override headers | Cannot bypass table |
| Patient ownership | Own completed visits/reports/read notifications; another patient ID/data in repository | Only current owner data; no caller-supplied patient selector |
| Doctor assignment | Assigned vs unassigned/nonexistent patient; pending assignment; different clinician | Only assigned records; identical missing/unassigned response |
| Reception role | Schedule/directory/availability reads; clinical/admin routes; booking/cancel/edit attempts | Minimal reads only; every mutation denied |
| Laboratorian assignment | Own assigned clinic work; unassigned/different laboratorian; upload/result/report-file attempt | Own minimal metadata only; mutations/files denied |
| Administrator | Staff/clinician/overview reads; create/edit/activate/entitlement/patient/payment attempts | Minimal reads only; all management writes denied |
| Query controls | Oversized page, page size, search, date range, unknown query field, status/mode injection | 422; cannot select excluded workflow |
| Response exposure | Schema serialization and raw JSON absence checks for passwords/hashes, session/token/CSRF, emails/phones where excluded, address, clinical fields, payment/provider IDs, revision/audit fields, file/storage/PDF data | Sensitive keys/values absent at every nesting level |
| Pagination | Deterministic order, max/default size, page boundary, sparse/empty page, no unbounded repository call | Bounded stable results only |
| Side-effect audit | Patch repositories/services and inspect database operation inventory for every allowed GET | Reads only; no save/insert/update/delete/state transition/background task |
| Background behavior | Mount each demo page, idle, retry failures, account switch, visibility change | No mutation, polling write, PDF/file, payment, or ordinary product request |
| Frontend rendering | Route/module inventory, no forms/mutation hooks/file inputs/PDF/payment controls, role navigation snapshot, 401/403/404 states | Presentation-only UI |
| Browser smoke (later) | Network log for each role, direct blocked URL, account switching, session expiry/logout, no cache leak | Only exact allowlist traffic; requires approval and does not occur in this milestone |

Suggested future files: `backend/tests/test_read_only_demo_configuration.py`, `test_read_only_demo_allowlist.py`, `test_read_only_demo_authentication.py`, `test_read_only_demo_projections.py`, `test_read_only_demo_role_isolation.py`, and corresponding frontend route/render/network-contract tests. Existing auth, cache, clinician, notification, appointment, lab, environment, API-contract, and Phase 24A regression suites must also remain green.

## 13. Implementation dependency plan — NOT IMPLEMENTED

| Step | Expected files/modules | Dependencies | Required tests | Principal risk | Approval | Exit criterion |
|---:|---|---|---|---|---|---|
| 1. Configuration/guards | `backend/app/core/config.py`, new core demo constants/helpers, environment examples only after approval | Frozen identities/ports/origin/database | Default-off, mismatch, mutual exclusion, staging/production rejection, pre-connection failure | Selecting wrong DB/environment | Architecture/environment + code-change approval | Every invalid combination fails before connection |
| 2. Backend allowlist | New middleware + `backend/app/main.py` | Step 1 and frozen route table | Exact allow/deny, normalization, method override, no endpoint invocation | Pattern bypass or middleware-order error | Security implementation approval | All unlisted methods/paths fail closed |
| 3. Role read endpoints | New demo router/service; existing repository helpers | Steps 1–2; approved role stories | Auth/role/owner/assignment and side-effect tests | Copying broad normal services without re-audit | Workflow/field approval | Each route reads only approved records |
| 4. Schemas/projections | New explicit schemas and repository projections | Step 3, approved field matrix | JSON forbidden-key and bounded-query tests | Sensitive field leakage | Clinic/data/security approval | Responses contain only enumerated fields |
| 5. Frontend demo navigation | `App.jsx`, demo route guard/layout/banner/navigation/API module | Stable backend contract | Route/import/navigation/forbidden-state tests | Normal pages reachable or UI flag trusted | Frontend implementation approval | Only demo routes/navigation are exposed |
| 6. Reception view | New receptionist demo pages/components | Steps 3–5 | Schedule/directory/availability rendered and no mutation requests | Contact/address or booking exposure | Workflow/data approval | Minimal read-only reception flow passes |
| 7. Laboratory view | New lab demo page | Steps 3–5 | Assignment, field absence, no file controls/requests | Upload/PDF metadata exposure | Lab/clinic/security approval | Assigned metadata only |
| 8. Administrator view | New admin demo page | Steps 3–5 | Staff/clinician/overview fields and no management requests | Email/account/billing exposure | Admin/data approval | Non-sensitive summary only |
| 9. Patient/doctor integration | New patient/doctor demo pages | Steps 3–5 | Ownership/assignment, completed-only, no PDF/payment/mutations | Clinical overexposure | Clinic/data approval | Restricted flows pass negative tests |
| 10. Security regression | New suites plus full relevant existing suites | Steps 1–9 | Matrix in section 12; compilation/lint/build/audit/diff | False confidence from focused tests | Test/security review approval | Independent offline review has no blocking finding |
| 11. Browser verification | Approved local environment/browser only | Steps 1–10, accounts/data, approvals | Five role network/route/session negative smoke | Runtime requests differ from tests | Startup/presentation approval | Recorded redacted evidence; exact traffic only |
| 12. Guarded macOS launcher | New cross-platform launcher/docs/tests | Approved architecture and verified implementation | Static guards, process tracking, port/DB/origin checks, stop/abort | Wrong process/DB or incomplete shutdown | Separate launcher implementation approval | Independently reviewed exact launcher |
| 13. Fictional accounts/data | Separately reviewed fixture/preflight scripts | Approved schemas, retention, relationship graph | Tag/count/ownership/assignment/no-real-data/file/payment checks | Realistic/real data or orphan relationships | Dataset/account/cleanup approvals | Preflight proves exact approved graph |
| 14. Controlled local demo | No code change; runbook execution | Every prior exit criterion and named people | Final preflight, narrow browser smoke, abort readiness | Operational drift | All 11 approvals and GO decision | Named authority records GO; otherwise NO-GO |

The guarded launcher must follow implementation and independent offline review. Fixture preparation must not be used to develop or test against an unapproved environment.

## 14. Approval requirements

All 11 Phase 24A.16 items remain pending:

1. named demo environment and machine;
2. environment owner/operator;
3. approved viewers;
4. approved workflow list;
5. fictional dataset;
6. demo account roles and access;
7. network exposure boundary;
8. payment-disabled confirmation;
9. storage and scanner exclusions;
10. start, stop, and abort authority; and
11. disposable-data cleanup/retention decision.

Before code changes, explicit approval is also required for this architecture, setting/selector names, route table, response fields, lifecycle-write exceptions, new endpoint/modules, and test scope. Later steps separately require launcher implementation, account/fixture preparation, service startup, database use, browser verification, and presentation approval.

This report is not authorization for any of those actions.

## 15. Connected gate status

All eight gates are carried forward exactly from Phase 24A.16 and remain **BLOCKED**. No connected verification was run.

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

Phase 24B remains **BLOCKED / NOT STARTED**.

## 16. Remaining risks

1. The proposed mode, middleware, endpoints, schemas, views, tests, environment, launcher, accounts, and dataset do not exist.
2. Middleware path canonicalization and ordering can create bypasses if implemented incorrectly.
3. Authentication lifecycle writes mean “read-only” must always be described as no product/clinical/operational data mutation, not a physically read-only database connection.
4. Rate-limit buckets, session creation/rotation/revocation, and TTL deletion are expected security-state writes and require explicit acceptance.
5. Current `/auth/me` is too broad and untyped for demo use until its active-mode projection is explicit.
6. New repository projection helpers could accidentally omit assignment predicates or use unbounded queries.
7. Notification text can carry sensitive or workflow-triggering content; that surface remains conditional on approved fictional content and browser verification.
8. A frontend build can still contain normal application code even when demo routes hide it; backend denial is decisive, and route-split/import tests are still needed.
9. Local HTTP means cookies cannot use `Secure`; loopback-only binding and no public/LAN exposure are non-negotiable for v1.
10. A dedicated database prevents production access only if configuration and launcher guards are correct and independently reviewed.
11. All approvals and operational ownership remain unresolved.
12. No browser, runtime, database, query-plan, index, scanner, storage, proxy/TLS, or backup evidence exists.

## 17. Recommended next milestone

The next milestone should be an **independent security and architecture review of this specification plus explicit human scope approval**. Reviewers should challenge:

- the authentication lifecycle exceptions and rehearsal-tag model;
- route normalization and middleware placement;
- the decision to use new minimal endpoints instead of broad current GET routes;
- every field in the projection matrix;
- loopback/database/selector fail-closed rules;
- frontend module isolation; and
- the test matrix and dependency order.

Only after that review and written approval should a separate implementation milestone begin steps 1–4 (configuration, allowlist, endpoints, and projections). It should stop for independent review before frontend or launcher work. Do not proceed directly to account/data preparation, service startup, browser work, or Phase 24B.

## 18. Final readiness decision

| Status item | Result |
|---|---|
| Demo-mode architecture feasibility | **FEASIBLE; SPECIFIED; NOT IMPLEMENTED** |
| Backend allowlist design completeness | **COMPLETE FOR INDEPENDENT REVIEW; NOT IMPLEMENTED** |
| Patient/doctor integration requirements | **SPECIFIED; NOT IMPLEMENTED** |
| Receptionist implementation requirements | **NEW VIEW + MINIMAL ENDPOINT REQUIRED; NOT IMPLEMENTED** |
| Laboratorian implementation requirements | **NEW VIEW + MINIMAL ENDPOINT REQUIRED; NOT IMPLEMENTED** |
| Administrator implementation requirements | **NEW VIEW + MINIMAL ENDPOINT REQUIRED; NOT IMPLEMENTED** |
| Security test plan | **SPECIFIED; NOT EXECUTED** |
| Approval status | **11 PENDING; 0 APPROVED** |
| Demo-mode implementation | **NOT STARTED** |
| Five-role demo | **FEASIBLE, NOT IMPLEMENTED** |
| Overall demo preparation | **PARTIALLY PREPARED** |
| Actual controlled local demo | **NO-GO** |
| Connected client demo | **NO-GO** |
| Eight connected release gates | **ALL BLOCKED** |
| Phase 24B | **BLOCKED / NOT STARTED** |

No production-readiness claim is made. Stop after Phase 24A.18 and await explicit review.
