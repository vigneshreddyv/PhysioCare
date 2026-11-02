# Phase 24A.11 API endpoint inventory

Assessment date: 2026-11-02  
Branch: `codex/physiocare-integration-2026-10-31`  
HEAD assessed: `5eaced696a156ca74233fd04252fea52345d8af8`

## Inventory rules and notation

This is a source-traced, offline inventory. It covers **119 registered application route operations**: **117** under `/api`, plus `/` and `/health`. FastAPI also registers four framework routes (`/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc`), recorded separately. All 119 application operations were traced through their handler and principal service/repository path; none is marked partial or unverified. No database or external service was contacted.

The source-of-truth router registrations are `backend/app/main.py:136-148`. Handler locations below use `module:function`. `R` means read-only; `W` means a persistent mutation can occur; `410` means the registered compatibility endpoint always rejects without a database mutation. Sensitive classifications are: `none`, `identity`, `contact`, `clinical`, `location`, `billing`, `PDF`, or a combination.

Query notation:

- `ONE`: fixed-count lookup(s), not result-cardinality driven.
- `PAGE`: database-side filter/sort/skip/limit using `page_window`; defaults to 50, maximum 100, maximum page 1,000 (`backend/app/core/pagination.py:8-35`).
- `AGG`: database aggregation/count; shape and filter order inspected offline, execution plan not verified.
- `U`: confirmed registered-path unbounded materialization.
- `N+1`: database calls inside a result-cardinality loop. `PAGE+N+1` is bounded but can still reach hundreds of calls.
- `OWN`, `ASSIGNED`, `RECIPIENT`, and `LAB-ASSIGNED` are server-side object scopes.
- `UI none` means no visible consumer in `frontend/src`; it does not mean the endpoint is unused by all clients.

All authenticated unsafe methods also pass live-session and CSRF validation in `backend/app/middleware/auth.py:20-109`; role dependencies are in `backend/app/middleware/auth.py:111-120`. The inventory calls out additional object scope rather than repeating those controls in every row.

## Authentication (6)

| # | Method and path | Handler | Access and object scope | Models / main path | Query / bound | Sensitive; mutation | Frontend consumer | Status |
|---:|---|---|---|---|---|---|---|---|
| 1 | POST `/api/auth/register` | `api/auth.py:register` | Public; registration throttled; enumeration-neutral response | `AuthService.register`; `users`, `patients`; transactional profile creation | ONE; auth rate window | identity; W | Register | FULL |
| 2 | POST `/api/auth/login` | `api/auth.py:login` | Public; IP/account throttles; inactive rejected | `AuthService.login`; `users`, `auth_sessions` | ONE; auth rate window | session/identity; W session | AuthContext | FULL |
| 3 | POST `/api/auth/refresh` | `api/auth.py:refresh` | Refresh cookie + CSRF; session binding and atomic rotation | `AuthService.refresh_tokens`; `auth_sessions`, `users` | ONE; refresh throttles | session; W rotation | API interceptor | FULL |
| 4 | GET `/api/auth/csrf` | `api/auth.py:csrf` | Valid refresh cookie/session | `AuthService.issue_csrf_token`; `auth_sessions`, `users` | ONE; refresh throttles | CSRF token; R | API client | FULL |
| 5 | POST `/api/auth/logout` | `api/auth.py:logout` | Cookie + double-submit and session-bound CSRF | `AuthService.revoke_session`; `auth_sessions` | ONE | session; W revoke | AuthContext | FULL |
| 6 | GET `/api/auth/me` | `api/auth.py:get_me` | Authenticated; own account/profile only | `UserService.get_*_profile`; `users`, `patients` or `doctors` | ONE | identity/contact; R | AuthContext | FULL |

## Appointments (16)

| # | Method and path | Handler | Access and object scope | Models / main path | Query / bound | Sensitive; mutation | Frontend consumer | Status |
|---:|---|---|---|---|---|---|---|---|
| 7 | GET `/api/appointments/booking-window` | `api/appointments.py:get_booking_window` | Any authenticated role | settings only | fixed | none; R | booking, schedules, home visits | FULL |
| 8 | POST `/api/appointments` | `api/appointments.py:create_appointment` | patient; OWN derived from session | `AppointmentService._create_for_patient`; patients/doctors/schedules/appointments | ONE + date-scoped conflict; unique slot claim | clinical/billing; W | BookAppointment | FULL |
| 9 | POST `/api/appointments/admin` | `api/appointments.py:create_admin_appointment` | admin; supplied patient validated | same as #8 | ONE + conflict; unique slot claim | clinical/billing; W | AppointmentBooking | FULL |
| 10 | POST `/api/appointments/reception` | `api/appointments.py:create_reception_appointment` | receptionist; no clinical reason accepted | same as #8 | ONE + conflict; unique slot claim | contact/schedule; W | AppointmentBooking | FULL |
| 11 | GET `/api/appointments/reception` | `api/appointments.py:list_reception_schedule` | receptionist; coordination projection | `list_page_operational_schedule`; appointments + batched patient/doctor/user maps | PAGE; stable sort; batched joins | contact/location; R | ReceptionistDashboard | FULL |
| 12 | GET `/api/appointments/reception/summary` | `api/appointments.py:reception_schedule_summary` | receptionist | appointments count aggregation | AGG; optional date filter | operational counts; R | ReceptionistDashboard | FULL |
| 13 | GET `/api/appointments/doctor/summary` | `api/appointments.py:doctor_dashboard_summary` | doctor; ASSIGNED doctor profile | appointment summary aggregation | AGG | clinical counts; R | DoctorDashboard | FULL |
| 14 | GET `/api/appointments/availability` | `api/appointments.py:get_appointment_availability` | any authenticated role | doctors, clinician schedules, date-scoped active appointments | bounded schedule/day query | schedule; R | patient/admin booking | FULL |
| 15 | GET `/api/appointments` | `api/appointments.py:list_appointments` | admin, doctor, patient; doctor ASSIGNED, patient OWN | appointments; doctor uses batched maps, admin/patient use per-row formatter | PAGE; **PAGE+N+1 for admin/patient** | clinical/location/billing (doctor schema excludes billing); R | admin and doctor dashboards | FULL |
| 16 | GET `/api/appointments/admin/billing` | `api/appointments.py:list_admin_billing` | admin | appointments + per-row profile formatter | **PAGE+N+1**; filters before page | billing/clinical; R | Billing | FULL |
| 17 | GET `/api/appointments/me/home-visits` | `api/appointments.py:list_patient_home_visits` | patient; OWN | appointments + per-row formatter | **PAGE+N+1** | clinical/location/billing; R | HomeVisitRequests | FULL |
| 18 | GET `/api/appointments/me/history` | `api/appointments.py:list_patient_appointment_history` | patient; OWN | appointments + per-row formatter | **PAGE+N+1**; status/date in DB | clinical/location/billing; R | dashboard/history/appointments | FULL |
| 19 | GET `/api/appointments/{appointment_id}` | `api/appointments.py:get_patient_appointment` | patient; OWN checked server-side | appointment, patient/doctor/user | ONE | clinical/location/billing; R | payment resume | FULL |
| 20 | POST `/api/appointments/{appointment_id}/cancel` | `api/appointments.py:cancel_appointment` | patient; OWN + state/deadline | conditional atomic appointment update; payment reconciliation marker | ONE; compare-state update | billing/schedule; W | dashboard/history | FULL |
| 21 | POST `/api/appointments/reception/{appointment_id}/cancel` | `api/appointments.py:cancel_reception_appointment` | receptionist; coordination state/deadline | conditional appointment update | ONE; compare-state update | contact/schedule; W | ReceptionistDashboard | FULL |
| 22 | PATCH `/api/appointments/{appointment_id}` | `api/appointments.py:update_appointment` | admin or ASSIGNED doctor; doctor cannot write billing | appointment, payment attempts | ONE; some transitions atomic, general save not versioned | clinical/billing; W | admin/doctor dashboards | FULL |

## Users and clinical directories (16)

| # | Method and path | Handler | Access and object scope | Models / main path | Query / bound | Sensitive; mutation | Frontend consumer | Status |
|---:|---|---|---|---|---|---|---|---|
| 23 | GET `/api/users/public/doctors` | `api/users.py:list_public_doctors` | public; active public projection | `ProfileRepository.search_doctors`; doctors/users aggregation | PAGE; search max 100, escaped regex | public profile; R | PublicHome, booking, home visits | FULL |
| 24 | PATCH `/api/users/me/patient-profile` | `api/users.py:update_own_patient_profile` | patient; OWN derived from session | users/patients | ONE | identity/contact; W | PatientProfile | FULL |
| 25 | POST `/api/users/staff` | `api/users.py:create_staff` | admin | `AuthService.register_staff`; users (+ doctor profile transaction when doctor) | ONE | internal identity; W | StaffManagement | FULL |
| 26 | GET `/api/users/staff` | `api/users.py:list_staff` | admin | `UserRepository.list_staff`; users | **U** | staff names/emails/roles; R | StaffManagement | FULL |
| 27 | GET `/api/users/laboratorians` | `api/users.py:list_laboratorians` | admin | bounded `search_by_role`; users | PAGE; search max 100, escaped | staff name/id; R | AdminLabRequestsPanel | FULL |
| 28 | GET `/api/users/doctors` | `api/users.py:list_doctors` | admin | bounded doctor/user aggregation | PAGE; escaped search | staff identity/profile; R | DoctorsList, demo services, selectors | FULL |
| 29 | PATCH `/api/users/doctors/{doctor_id}` | `api/users.py:update_doctor_profile` | admin | doctors/users | ONE | staff identity/profile; W | DoctorsList | FULL |
| 30 | GET `/api/users/reception/doctors` | `api/users.py:list_reception_doctors` | receptionist; active public projection | bounded doctor/user aggregation | PAGE | public profile; R | appointment booking | FULL |
| 31 | GET `/api/users/reception/patients` | `api/users.py:list_reception_patients` | receptionist; coordination projection | no-search patients page then user per row; search uses aggregation | **PAGE+N+1 without search** | identity/contact; R | PatientsList, selectors | FULL |
| 32 | PATCH `/api/users/reception/patients/{patient_id}` | `api/users.py:update_reception_patient` | receptionist; name/phone schema only | patient/user | ONE | identity/contact; W | PatientsList | FULL |
| 33 | GET `/api/users/patients` | `api/users.py:list_patients` | admin or doctor; doctor ASSIGNED | admin no-search page + user per row; doctor distinct IDs + patient/user per row; search aggregation | **PAGE+N+1 without search** | admin identity/contact; doctor minimized clinical identity | PatientsList/selectors | FULL |
| 34 | GET `/api/users/patients/{patient_id}` | `api/users.py:get_admin_patient` | admin | patient/user | ONE | identity/contact; R | AdminPatientEdit | FULL |
| 35 | GET `/api/users/doctor/patients/{patient_id}` | `api/users.py:get_doctor_patient` | doctor; ASSIGNED predicate | appointment existence + patient/user | ONE | minimized clinical identity; R | doctor care/exercise screens | FULL |
| 36 | PATCH `/api/users/patients/{patient_id}` | `api/users.py:update_admin_patient` | admin | patient/user; bounded embedded audit (50) | ONE | identity/contact; W | AdminPatientEdit | FULL |
| 37 | GET `/api/users/patients/{patient_id}/history` | `api/users.py:get_admin_patient_history` | admin | paged appointments/released reports + batched doctor identities | PAGE; two independently bounded result arrays | clinical/contact/PDF metadata; R | AdminPatientHistory | FULL |
| 38 | GET `/api/users/doctor/patients/{patient_id}/history` | `api/users.py:get_doctor_patient_history` | doctor; ASSIGNED | assignment predicate, paged appointment/report queries | PAGE | clinical/contact/PDF metadata; R | DoctorPatientHistory | FULL |

## Analytics (2)

| # | Method and path | Handler | Access | Models / main path | Query / bound | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 39 | GET `/api/analytics/stats` | `api/analytics.py:get_stats` | admin | appointments/patients/doctors/users aggregations | AGG; `days` 7..365; grouped output | clinic metrics; R | dashboards/Analytics | FULL |
| 40 | GET `/api/analytics/admin-daily-activity` | `api/analytics.py:get_admin_daily_activity` | admin | two-day appointment grouping | AGG; fixed 2-day match | clinic metrics; R | dashboards/Notifications | FULL |

## Demo services and home visits (15)

| # | Method and path | Handler | Access and scope | Models / main path | Query / bound | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 41 | GET `/api/home-visit-requests/me/context` | `api/home_visits.py:get_home_visit_context` | patient; OWN | patient profile | ONE | saved address; R | HomeVisitRequests | FULL |
| 42 | GET `/api/demo-services/me/entitlement` | `api/home_visits.py:get_own_demo_entitlement` | patient; OWN | patient/demo entitlement | ONE | service entitlement; R | HomeVisitRequests | FULL |
| 43 | GET `/api/demo-services/entitlements` | `api/home_visits.py:list_demo_entitlements` | admin | search path aggregation; omitted-search fallback all patients + two lookups per row | PAGE with search; **U+N+1 if search omitted** | contact/entitlement; R | DemoServices always supplies search | FULL |
| 44 | GET `/api/home-visit-bookings/admin/scheduled` | `api/home_visits.py:list_scheduled_home_visits` | admin | bounded appointment aggregation/projection | PAGE+AGG | schedule identities; R | DemoServices | FULL |
| 45 | PUT `/api/demo-services/patients/{patient_id}/entitlement` | `api/home_visits.py:set_demo_entitlement` | admin | patient/user/entitlement | ONE; upsert | contact/entitlement; W | DemoServices | FULL |
| 46 | POST `/api/home-visit-requests` | `api/home_visits.py:create_home_visit_request` | patient | none | fixed 410 | none; 410 | UI uses direct booking instead | FULL |
| 47 | GET `/api/home-visit-bookings/availability` | `api/home_visits.py:get_home_visit_booking_availability` | patient; entitlement first | schedules, doctors/users, appointment aggregation stream | AGG stream; one day; no app query-per-clinician | schedule; R | HomeVisitRequests | FULL |
| 48 | POST `/api/home-visit-bookings` | `api/home_visits.py:create_home_visit_booking` | patient; OWN + entitlement | appointments/schedules/profile; unique slot claim | AGG stream or ONE; retry on candidate collision | clinical/location/billing; W | HomeVisitRequests | FULL |
| 49 | PATCH `/api/home-visit-bookings/admin/{appointment_id}/doctor` | `api/home_visits.py:assign_home_visit_doctor` | admin | appointment/doctor/user/schedule | ONE + conditional assignment + unique claim | location/schedule; W | DemoServices | FULL |
| 50 | GET `/api/home-visit-requests/me` | `api/home_visits.py:list_own_home_visit_requests` | patient; OWN | requests + per-row patient/doctor/users | **PAGE+N+1** | clinical/contact/location; R | dashboard/HomeVisitRequests | FULL |
| 51 | POST `/api/home-visit-requests/{request_id}/withdraw` | `api/home_visits.py:withdraw_home_visit_request` | patient; OWN | request/profile + conditional transition | ONE | clinical/location; W | no active direct consumer found | FULL |
| 52 | GET `/api/home-visit-requests/admin` | `api/home_visits.py:list_admin_home_visit_requests` | admin | requests + per-row related entities | **PAGE+N+1** | clinical/contact/location; R | DemoServices | FULL |
| 53 | PATCH `/api/home-visit-requests/admin/{request_id}` | `api/home_visits.py:review_home_visit_request` | admin | request + conditional transition | ONE | clinical/contact/location; W | DemoServices | FULL |
| 54 | GET `/api/home-visit-requests/reception` | `api/home_visits.py:list_reception_home_visit_requests` | receptionist; approved coordination projection | paged requests + batched identities | PAGE; batched | contact/location, no symptoms/reason | ReceptionistDashboard | FULL |
| 55 | GET `/api/home-visit-requests/doctor` | `api/home_visits.py:list_doctor_home_visit_requests` | doctor; ASSIGNED preferred doctor | requests + per-row patient/doctor/user | **PAGE+N+1** | clinical/contact/location | HomeVisits | FULL |

## Laboratory requests and PDFs (12)

| # | Method and path | Handler | Access and scope | Models / main path | Query / bound | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 56 | POST `/api/lab-requests` | `api/lab_requests.py:create_request` | patient; OWN; idempotency key optional | lab requests/patient; idempotent create | ONE; selected tests max 12 | clinical/contact/location; W | LaboratoryRequests | FULL |
| 57 | GET `/api/lab-requests/me` | `api/lab_requests.py:list_own` | patient; OWN | requests + per-row patient/user/assignee | **PAGE+N+1** | clinical/contact/location; R | dashboard/LaboratoryRequests | FULL |
| 58 | POST `/api/lab-requests/{request_id}/withdraw` | `api/lab_requests.py:withdraw` | patient; OWN | request/profile + conditional transition | ONE | clinical; W | LaboratoryRequests | FULL |
| 59 | GET `/api/lab-requests/admin` | `api/lab_requests.py:list_admin` | admin | requests + per-row related identities | **PAGE+N+1** | clinical/contact/location; R | AdminLabRequestsPanel | FULL |
| 60 | PATCH `/api/lab-requests/admin/{request_id}` | `api/lab_requests.py:review` | admin | request + conditional transition | ONE | clinical/contact; W | AdminLabRequestsPanel | FULL |
| 61 | PATCH `/api/lab-requests/admin/{request_id}/assignment` | `api/lab_requests.py:assign_laboratorian` | admin | request/user + conditional assignment | ONE | staff/clinical; W | AdminLabRequestsPanel | FULL |
| 62 | POST `/api/lab-requests/admin/{request_id}/publish-report` | `api/lab_requests.py:publish_report` | admin | request + private file state + conditional publish | ONE; compare expected storage key | PDF metadata; W | AdminLabRequestsPanel | FULL |
| 63 | GET `/api/lab-requests/laboratory/assigned` | `api/lab_requests.py:list_assigned_orders` | laboratorian; LAB-ASSIGNED | requests + per-row patient/user | **PAGE+N+1** | collection-required contact/location/clinical tests | LaboratoryDashboard | FULL |
| 64 | PUT `/api/lab-requests/laboratory/{request_id}/report` | `api/lab_requests.py:upload_finalized_report` | laboratorian; LAB-ASSIGNED | request; quarantine/scanner/private storage; conditional metadata write | streamed max 5 MiB default; PDF validation; fail closed | PDF; W | LaboratoryDashboard | FULL |
| 65 | GET `/api/lab-requests/me/reports` | `api/lab_requests.py:list_released_reports` | patient; OWN + released only | released requests | PAGE | PDF metadata; R | LaboratoryRequests | FULL |
| 66 | GET `/api/lab-requests/doctor/reports` | `api/lab_requests.py:list_assigned_patient_reports` | doctor; ASSIGNED predicate in repository | aggregation/paged reports + batched patient names | PAGE+AGG | PDF metadata/clinical tests; R | DoctorDashboard | FULL |
| 67 | GET `/api/lab-requests/{request_id}/report-file` | `api/lab_requests.py:download_report` | patient OWN, doctor ASSIGNED, laboratorian LAB-ASSIGNED, or admin; unreleased hidden from patient/doctor | request/profile/assignment predicate + private storage | ONE; basename/path isolation | PDF; R | patient/doctor/admin viewers | FULL |

## Clinician schedules (4)

| # | Method and path | Handler | Access | Models / main path | Bound / concurrency | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 68 | GET `/api/clinician-schedules/admin/{doctor_id}` | `api/clinician_schedules.py:get_admin_schedule` | admin | doctor/user/schedule | ONE; embedded audit bounded by implementation | staff schedule; R | ClinicianSchedules | FULL |
| 69 | PUT `/api/clinician-schedules/admin/{doctor_id}/draft` | `api/clinician_schedules.py:save_admin_schedule_draft` | admin | schedule | body max 56 weekly blocks, 31 exceptions, 12 blocks/exception | staff schedule; W | ClinicianSchedules | FULL |
| 70 | GET `/api/clinician-schedules/admin/{doctor_id}/preview` | `api/clinician_schedules.py:preview_admin_schedule` | admin | schedule | ONE; date/mode constrained | staff schedule; R | ClinicianSchedules | FULL |
| 71 | POST `/api/clinician-schedules/admin/{doctor_id}/publish` | `api/clinician_schedules.py:publish_admin_schedule` | admin | schedule + appointment conflict validation | expected revision compare | staff schedule; W | ClinicianSchedules | FULL |

## Payments and webhook (10)

| # | Method and path | Handler | Access and scope | Models / main path | Query / bound | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 72 | GET `/api/payments/history` | `api/payments.py:list_patient_payment_history` | patient; OWN | payment attempts, appointment per attempt | **U+N+1** | billing; R | PatientPaymentHistory | FULL |
| 73 | GET `/api/payments/readiness` | `api/payments.py:get_payment_readiness` | patient | settings only | fixed | payment mode; R | BookAppointment | FULL |
| 74 | POST `/api/appointments/{appointment_id}/payments/order` | `api/payments.py:create_appointment_payment_order` | patient; OWN | appointment/payment attempt + provider only in configured test mode | ONE; idempotent attempt/order state | billing/provider order ID; W/external when enabled | BookAppointment | FULL |
| 75 | POST `/api/appointments/{appointment_id}/payments/verify` | `api/payments.py:verify_appointment_payment` | patient; OWN; provider signature and capture verified | appointment/payment attempt/provider | ONE; conditional updates | billing/provider IDs; W/external | BookAppointment | FULL |
| 76 | GET `/api/appointments/{appointment_id}/payments` | `api/payments.py:get_appointment_payment_status` | patient; OWN | appointment | ONE | billing; R | BookAppointment | FULL |
| 77 | POST `/api/appointments/{appointment_id}/payments/abandon` | `api/payments.py:abandon_appointment_checkout` | patient; OWN | attempt/appointment conditional state | ONE | billing; W | BookAppointment | FULL |
| 78 | POST `/api/payments/admin/reconcile-captured` | `api/payments.py:reconcile_captured_payments` | admin | attempts + appointment per bounded item | bounded N+1; configured batch 1..500, default 50 | billing; W | Billing | FULL |
| 79 | GET `/api/payments/admin/captured-review` | `api/payments.py:list_captured_payment_reviews` | admin | attempts + appointment per bounded item | bounded N+1; configured batch | billing; R | Billing | FULL |
| 80 | POST `/api/appointments/{appointment_id}/payments/cancel` | `api/payments.py:cancel_appointment_checkout` | patient; OWN | attempt/appointment conditional state | ONE | billing; W | BookAppointment | FULL |
| 81 | POST `/api/webhooks/razorpay` | `api/payments.py:razorpay_webhook` | public transport; HMAC signature, event ID, provider verification | webhook events/payment attempts/appointments/provider | ONE, deduplicated; **body buffered with no app cap before signature** | billing/provider IDs; W | provider only | FULL |

## Legacy laboratory booking (6)

| # | Method and path | Handler | Access and scope | Models / main path | Query / bound | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 82 | GET `/api/laboratory/tests` | `api/laboratory.py:get_laboratory_tests` | patient | laboratory tests | **U** active catalog | prices/catalog; R | inactive legacy selection component | FULL |
| 83 | POST `/api/laboratory/bookings` | `api/laboratory.py:create_laboratory_booking` | patient; OWN | tests/booking/patient/notification | `$in` list has no schema max; date horizon 14 days; conflict query | location/billing; W | no active routed screen found | FULL |
| 84 | GET `/api/laboratory/bookings` | `api/laboratory.py:list_laboratory_bookings` | patient; OWN | bookings | PAGE | location/billing/provider IDs; R | no active routed screen found | FULL |
| 85 | GET `/api/laboratory/bookings/{booking_id}` | `api/laboratory.py:get_laboratory_booking` | patient; OWN checked | booking | ONE | location/billing/provider IDs; R | inactive legacy detail component | FULL |
| 86 | PATCH `/api/laboratory/bookings/{booking_id}/payment` | `api/laboratory.py:update_laboratory_booking_payment` | patient; OWN resolution occurs before service | service always 410; legacy repository mutator not reached | fixed 410 | none; 410 | no active consumer | FULL |
| 87 | PATCH `/api/laboratory/bookings/{booking_id}/status` | `api/laboratory.py:update_laboratory_booking_status` | admin or doctor; doctor ASSIGNED | booking + authorization predicate + notification | ONE; transition validation | clinical/location/billing IDs; W | no visible consumer | FULL |

## Clinical reports (4)

| # | Method and path | Handler | Access and scope | Models / main path | Query / bound | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 88 | GET `/api/reports` | `api/reports.py:list_reports` | patient; OWN | reports | PAGE; search max 100, escaped and DB-filtered | clinical/PDF metadata; R | PatientReports | FULL |
| 89 | GET `/api/reports/{report_id}` | `api/reports.py:get_report_details` | patient; OWN | report | ONE | clinical/PDF metadata; R | no direct active consumer | FULL |
| 90 | GET `/api/reports/{report_id}/download` | `api/reports.py:download_report_file` | patient; OWN | report + private storage | ONE; isolated path; private no-store | PDF; R | PatientReports | FULL |
| 91 | POST `/api/reports` | `api/reports.py:create_report_by_admin` | admin or doctor; doctor ASSIGNED; booking target validated | reports/booking; quarantine/scanner/private storage; transaction where supported | upload streamed by storage, max 5 MiB default | clinical/PDF; W | ReportAuthoring | FULL |

## Care plans (10)

| # | Method and path | Handler | Access and scope | Models / main path | Query / bound | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 92 | GET `/api/care-plans` | `api/care_plans.py:list_care_plans` | patient; OWN | care plans | PAGE or limit-1 active/latest | clinical; R | PatientCarePlan/Progress | FULL |
| 93 | GET `/api/care-plans/{care_plan_id}` | `api/care_plans.py:get_care_plan` | patient; OWN | care plan | ONE | clinical; R | no direct active consumer | FULL |
| 94 | POST `/api/care-plans` | `api/care_plans.py:create_care_plan` | admin or doctor; doctor ASSIGNED | care plan/history/notification | ONE; nested lists/strings lack schema maxima; multi-write | clinical; W | CarePlanManagement | FULL |
| 95 | PATCH `/api/care-plans/{care_plan_id}` | `api/care_plans.py:update_care_plan` | admin or owning/ASSIGNED doctor | care plan/history/notification | ONE; unversioned read-modify-save; nested payload unbounded | clinical; W | CarePlanManagement | FULL |
| 96 | GET `/api/care-plans/patient/{patient_id}` | `api/care_plans.py:get_patient_care_plans_by_clinician` | admin or doctor ASSIGNED | care plans | PAGE | clinical; R | care/exercise management | FULL |
| 97 | PATCH `/api/care-plans/{care_plan_id}/stages/{stage_id}` | `api/care_plans.py:update_stage_status_endpoint` | admin or owning/ASSIGNED doctor | care plan/history/notification | ONE; unversioned embedded update, multi-write | clinical; W | CarePlanManagement | FULL |
| 98 | PATCH `/api/care-plans/{care_plan_id}/goals/{goal_id}` | `api/care_plans.py:update_goal_progress_endpoint` | admin or owning/ASSIGNED doctor | care plan/history/notification | ONE; unversioned embedded update, multi-write | clinical; W | CarePlanManagement | FULL |
| 99 | GET `/api/care-plans/{care_plan_id}/history` | `api/care_plans.py:get_care_plan_history` | patient; OWN plan verified | care plan/history | PAGE | clinical audit; R | PatientCarePlan | FULL |
| 100 | GET `/api/care-plans/{care_plan_id}/exercise-summary` | `api/care_plans.py:get_patient_care_plan_exercise_summary` | patient; OWN plan verified | assignment aggregation | AGG; groups by embedded stage IDs | clinical; R | PatientCarePlan | FULL |
| 101 | GET `/api/care-plans/{care_plan_id}/exercises` | `api/care_plans.py:get_care_plan_exercises` | patient OWN, doctor ASSIGNED/owns plan, admin | assignments | PAGE | clinical; R | no direct active consumer | FULL |

## Exercises and progress (12)

| # | Method and path | Handler | Access and scope | Models / main path | Query / bound | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 102 | GET `/api/exercises` | `api/exercises.py:list_exercises` | authenticated; patients forced active-only | exercises | PAGE; search max 100, escaped | catalog; R | PatientExercises/selectors | FULL |
| 103 | GET `/api/exercises/{exercise_id}` | `api/exercises.py:get_exercise` | authenticated; inactive hidden from patient | exercise | ONE | catalog; R | no visible direct consumer | FULL |
| 104 | GET `/api/exercise-assignments` | `api/exercises.py:list_assignments` | patient OWN; admin; doctor ASSIGNED | assignments + optional two batched label queries | PAGE | clinical; R | ExerciseAssignmentManagement | FULL |
| 105 | GET `/api/exercise-assignments/me/details` | `api/exercises.py:list_my_assignment_details` | patient; OWN | assignments + exercise lookup aggregation | PAGE+AGG; projection | clinical; R | PatientExercises | FULL |
| 106 | GET `/api/exercise-assignments/{assignment_id}` | `api/exercises.py:get_assignment` | patient OWN, doctor ASSIGNED, admin | assignment + scope lookup | ONE | clinical; R | no visible direct consumer | FULL |
| 107 | POST `/api/exercise-assignments` | `api/exercises.py:create_assignment` | admin or doctor ASSIGNED and plan ownership | assignment/patient/care plan/exercise | ONE | clinical; W | ExerciseAssignmentManagement | FULL |
| 108 | PATCH `/api/exercise-assignments/{assignment_id}` | `api/exercises.py:update_assignment` | patient OWN status-only; admin; doctor ASSIGNED | assignment/profile | ONE; unversioned read-modify-save | clinical; W | ExerciseAssignmentManagement | FULL |
| 109 | POST `/api/exercise-progress` | `api/exercises.py:create_progress` | patient; OWN assignment | progress/assignment/profile | ONE; multi-write progress then assignment status | clinical notes; W | PatientExercises | FULL |
| 110 | GET `/api/exercise-progress/stats` | `api/exercises.py:get_patient_stats` | patient; OWN | assignment/progress/care-plan aggregations | AGG; recent limited, grouped output | clinical metrics; R | PatientExercises/CarePlan/Progress | FULL |
| 111 | GET `/api/exercise-progress/stats/{patient_id}` | `api/exercises.py:get_patient_stats_for_clinician` | admin or doctor ASSIGNED | same as #110 | AGG | clinical metrics; R | no visible consumer | FULL |
| 112 | GET `/api/exercise-progress` | `api/exercises.py:list_patient_progress` | patient; OWN | progress | PAGE | clinical notes; R | no visible direct consumer | FULL |
| 113 | GET `/api/exercise-progress/patient/{patient_id}` | `api/exercises.py:list_progress_for_clinician` | admin or doctor ASSIGNED | progress | PAGE | clinical notes; R | no visible direct consumer | FULL |

## Notifications (4)

| # | Method and path | Handler | Access and scope | Models / main path | Query / bound | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|---|
| 114 | GET `/api/notifications` | `api/notifications.py:list_notifications` | authenticated; RECIPIENT from session | notifications | PAGE | private notification text; R | Notifications | FULL |
| 115 | GET `/api/notifications/unread-count` | `api/notifications.py:get_unread_count` | authenticated; RECIPIENT | count query | AGG/count | private count; R | Navbar/Notifications | FULL |
| 116 | PATCH `/api/notifications/{notification_id}/read` | `api/notifications.py:mark_read` | authenticated; RECIPIENT in update filter | notification conditional update | ONE | private notification; W | Notifications | FULL |
| 117 | PATCH `/api/notifications/read-all` | `api/notifications.py:mark_all_read` | authenticated; RECIPIENT filter | bounded-by-recipient bulk update | database bulk update | private notification; W | Notifications | FULL |

## Application root and health (2)

| # | Method and path | Handler | Access | Data | Sensitive; mutation | Frontend | Status |
|---:|---|---|---|---|---|---|---|
| 118 | GET `/` | `main.py:root` | public | static message | none; R | none | FULL |
| 119 | GET `/health` | `main.py:health` | public | settings-derived environment, demo DB name only in demo modes, payment-enabled flag | operational metadata; R | launch/readiness tooling | FULL |

## Framework routes (not counted in 119)

| Method and path | Registration | Access | Assessment |
|---|---|---|---|
| GET `/openapi.json` | FastAPI default | public | Complete API schema exposed unless deployment overrides it. |
| GET `/docs` | FastAPI default | public | Swagger UI enabled. |
| GET `/docs/oauth2-redirect` | FastAPI default | public | Swagger helper. |
| GET `/redoc` | FastAPI default | public | ReDoc UI enabled. |

## Duplicate, overlapping, and unregistered surface

- Dynamic runtime inspection and prefix-aware source review found **no duplicate registered method/full-path pair**. Static paths are declared before potentially overlapping dynamic parameters where order matters (for example appointment billing before `/{appointment_id}` and notification `read-all` is distinguishable by method/order).
- All 13 API routers imported by `backend/app/main.py:9-21` are registered at `backend/app/main.py:136-148`. No decorated API router was found omitted from the application.
- Compatibility methods that can perform unbounded reads still exist behind optional `page=None` branches in several services/repositories, but registered list handlers now pass a `PageWindow` except for the four confirmed `U` paths above. They are not counted as endpoint findings unless reachable from a registered handler.
- `frontend/src/pages/admin/PatientsCreate.jsx:30` calls unregistered `POST /api/users/patients`; the screen is actively routed at `frontend/src/App.jsx:237`.
- `frontend/src/pages/patient/HomeVisitLab.jsx:31` and `LaboratoryReview.jsx:25` call unregistered `GET /api/users/me/address`, but those legacy components are not routed in the current `App.jsx` tree.
- Several registered operations have no visible current SPA consumer, as marked in the tables. They remain security-relevant because direct clients can call them.

## Frontend behavior summary

Current clinical list screens use `frontend/src/services/clinicalPagination.js` and replace the displayed page instead of accumulating an unbounded browser list. Requests are keyed/cancelled to prevent stale patient data replacing a newer selection. No repeated polling loop was found. The primary intentional full-list screen is Staff Management, whose backend endpoint is itself unbounded. Demo Services always sends the `search` parameter, so its current UI takes the bounded entitlement path; a direct API caller can omit it and reach the unbounded fallback.

## Verification limits

`FULL` means the source authorization, response model, main database path, bounds, mutation behavior, and visible frontend use were traced. It does not mean production behavior is approved. Index presence, MongoDB execution plans, representative-volume latency, transaction topology, proxy body limits, deployed OpenAPI configuration, storage permissions, scanner integration, and connected cross-role negative tests remain environment verification gates.
