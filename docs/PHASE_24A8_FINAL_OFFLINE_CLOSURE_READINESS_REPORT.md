# Phase 24A.8 Final Offline Closure Readiness Report

Assessment date: 2026-11-02

Branch: `codex/physiocare-integration-2026-10-31`

HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

Upstream at assessment: `origin/codex/physiocare-integration-2026-10-31`, ahead 0 / behind 0

## 1. Executive summary

Phase 24A remains **Outcome B — Conditional Offline-Scope Closure**. Phase 24A.7's admin clinician-directory and PatientCarePlan documentation fixes remain intact. The fresh ordinary backend regression is clean when the unchanged Unix-socket integration file is excluded, the full frontend suite is clean, and the previous offline security protections remain covered.

The remaining password/email/recovery issue is **POLICY DECISION REQUIRED**. No authoritative clinic approval exists, so Phase 24A.8 made no application behavior change. The decision package is `docs/PHASE_24A8_PASSWORD_POLICY_DECISION_PACKAGE.md`.

This is not connected, demonstration, staging, or production readiness. All eight connected release gates remain **BLOCKED**. Phase 24B remains **BLOCKED / NOT STARTED**.

## 2. Initial worktree state

Before Phase 24A.8 documentation was created:

- branch: `codex/physiocare-integration-2026-10-31`;
- HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`;
- upstream: `origin/codex/physiocare-integration-2026-10-31`, ahead 0 / behind 0;
- tracked modifications: **88**;
- untracked paths: **64**;
- total changed paths: **152**.

This independently matches the supplied Phase 24A.7 historical state. The Phase 24A.7 implementation/test/report paths were present, including `backend/app/api/users.py`, `backend/app/repositories/profile_repository.py`, `backend/app/services/user_service.py`, `frontend/src/pages/admin/DoctorsList.jsx`, `backend/tests/test_phase24a7_admin_clinician_directory.py`, `backend/tests/test_phase24a7_password_policy_inventory.py`, `frontend/tests/admin-clinician-directory.test.mjs`, and `docs/PHASE_24A7_RESIDUAL_DEFECT_REMEDIATION_REPORT.md`.

No tracked or untracked work was discarded, stashed, reset, cleaned, committed, or pushed. No `.env` or credential was modified. No database, external service, migration, payment, deployment, or infrastructure was contacted.

## 3. Password-policy findings

The repository contains no approved clinic policy. Current behavior is:

- backend public patient registration: minimum **6** (`backend/app/schemas/auth.py:9-12`);
- frontend public patient registration: minimum **8** plus confirmation (`frontend/src/pages/common/Register.jsx:9-17`);
- backend staff creation: minimum **8** (`backend/app/schemas/auth.py:14-19`);
- frontend staff creation: minimum **8** plus confirmation (`frontend/src/utils/staffManagement.js:20-31`);
- login: no creation-policy minimum in the backend schema, preserving verification of existing credentials (`backend/app/schemas/auth.py:36-38`);
- hashing/verification: Passlib bcrypt (`backend/app/core/security.py:8-20`);
- password change/reset: **NOT IMPLEMENTED**.

A direct client can bypass the public UI's 8-character rule and submit 6 or 7 characters to the API. Existing credentials are not invalidated, and Phase 24A.8 did not change any minimum, hash, login, session, or registration behavior.

Classification: **POLICY DECISION REQUIRED**.

## 4. Decision package reference

`docs/PHASE_24A8_PASSWORD_POLICY_DECISION_PACKAGE.md` separately records existing behavior, recommendations, approval points, risks, compatibility, and the implementation scope that would follow an approved decision. Recommendations are explicitly **NOT APPROVED** and **NOT IMPLEMENTED**.

## 5. Frontend/backend validation inconsistency

The public patient flow is inconsistent at 8 frontend / 6 backend. The staff flow is consistent at 8 / 8. Login's lack of a creation minimum is compatible with existing hashes and should not be silently changed. No reset or change flow exists to assess.

The focused Phase 24A.8 selection passed **232 backend tests** and **83 frontend tests**, including the policy-inventory tests, public/staff registration contracts, authentication throttling/session rotation, admin directory, API contracts, cache/PDF headers, production configuration, staff validation, and rendered login/logout behavior.

## 6. Email verification assessment

**NOT IMPLEMENTED.** `User` has unique email and active state but no verification state (`backend/app/models/user.py:9-16`). Successful accounts are active immediately and can authenticate. Registration relies on email syntax, uniqueness, and neutral duplicate handling, not proof of ownership. No email verification/resend token or email-change/reverification endpoint was found.

This is a clinic policy and infrastructure decision, not an offline implementation approval.

## 7. Account recovery assessment

**NOT IMPLEMENTED.** No forgot-password, password reset/change, recovery code, recovery token, SMS, or administrator-assisted recovery flow was found. Therefore reset-token expiry, single use, recovery enumeration resistance, staff recovery, and reset-triggered session revocation do not exist to verify.

Recovery design depends on approved ownership and identity-proofing decisions. No provider integration was attempted.

## 8. Staff onboarding assessment

Only an administrator can create staff (`backend/app/api/users.py:47-57`). Both boundaries require 8 characters. The administrator establishes the initial password; the account is immediately active and the UI instructs secure sharing (`frontend/src/pages/admin/StaffManagement.jsx:44-50,106-108`). There is no invitation, first-login setup, forced change, email verification, or in-application password change/recovery. Inactive users are rejected on login and refresh (`backend/app/services/auth_service.py:156-169,307-316`), but no staff deactivation action was found in the reviewed staff-management route/UI.

## 9. Phase 24A.7 regression results

Fresh Phase 24A.8 regression retained the Phase 24A.7 baseline:

| Scope | Fresh result |
|---|---:|
| Password/admin/auth/API/cache/production focused backend selection | **232 passed**, 1 plugin warning |
| Admin/auth/staff/navigation focused frontend selection | **83 passed** |
| Full frontend suite | **149 passed**, 0 failed/skipped |
| Complete backend suite | **970 passed, 11 failed, 3 skipped**, 1 plugin warning |
| Backend excluding only `test_clamav_unix_scanner.py` | **969 passed, 3 skipped**, 1 plugin warning |

The 11 complete-suite failures are all unchanged `test_clamav_unix_scanner.py` cases failing at `asyncio.start_unix_server(...).sock.bind(path)` with `PermissionError: [Errno 1] Operation not permitted`. The tests were not weakened or skipped. The three skips are guarded connected account-registration, distributed-rate-limit, and report-transaction tests. The warning is the unchanged explicit `pytest_asyncio` plugin rewrite warning.

## 10. Admin clinician directory verification

The fix remains intact:

- `GET /users/doctors` is server-enforced admin-only and always calls bounded search (`backend/app/api/users.py:78-90`).
- Search input is regex-escaped and covers name, email, specialization, qualifications, and specialties (`backend/app/repositories/profile_repository.py:49-71`).
- The single aggregation joins profiles, applies filters before paging, sorts stably by `full_name` and `_id`, and narrowly projects required fields (`profile_repository.py:53-96`).
- Default page size is 50; general route validation permits no more than 100 and page 1,000 (`backend/app/core/pagination.py:8-35`). The admin UI uses the default 50-record page.
- The browser retains one page, keys queries by search/page, resets to page 1 on search, sets `gcTime: 0`, and preserves profile edit and schedule navigation (`frontend/src/pages/admin/DoctorsList.jsx:11-35,99-111,204-206`).
- The fresh focused tests cover a fictional result beyond the former 1,000-record browser boundary, a 1,250-row page-25 repository case, one aggregation/no per-row lookups, escaped search, role negatives, shared identical requests, rejection of stale/auth-cancelled responses, one-page rendering, and retained edit/schedule contracts.

Connected MongoDB query plans, index use, latency, and concurrent offset drift remain **NOT VERIFIED**.

## 11. PatientCarePlan documentation verification

The Phase 24A.5 report correctly states `GET /care-plans?selection=active_latest` at `docs/PHASE_24A5_BACKEND_TEST_ENVIRONMENT_RECOVERY_REPORT.md:255`. This matches the frontend call (`frontend/src/pages/patient/PatientCarePlan.jsx:31`) and the backend route/selection (`backend/app/api/care_plans.py:21,38-50`). The previous documentation discrepancy remains fixed.

## 12. Previous security regression results

The fresh focused and full offline suites preserve test coverage for:

- inactive-account rejection, generic login failures, registration enumeration resistance, login/registration throttling, session persistence and rotation;
- HttpOnly access/refresh cookies, CSRF validation, `/auth/me` private cache controls, unsafe-origin cache controls, logout failure handling, and login profile loading;
- PDF `no-store`, patient/doctor/admin ownership, patient-switch and authentication-change viewer invalidation;
- private storage, quarantine, fail-closed scanner behavior through socket-free units, and authorized report/laboratory downloads;
- doctor-to-patient assignment, patient ownership, role checks, notification-recipient isolation, billing authorization;
- appointment conflicts and unique slot-claim behavior;
- production demo-mode guard;
- clinical pagination, exercise aggregation, and dashboard summaries; and
- all 21 Phase 24A.3 screen contracts plus the Phase 24A.7 admin directory.

These are offline source/unit/contract results, not connected infrastructure or browser E2E evidence.

## 13. Exact backend and frontend test results

| Verification | Fresh Phase 24A.8 result |
|---|---:|
| Focused backend | **232 passed**, 1 warning, 2.27 s |
| Focused frontend | **83 passed**, 0 failed/skipped, 0.699 s |
| Full backend | **970 passed, 11 environment-failed, 3 connected-skipped**, 1 warning, 5.97 s |
| Backend excluding only Unix-socket integration file | **969 passed, 3 skipped**, 1 warning, 5.71 s |
| Full frontend | **149 passed**, 0 failed/skipped, 3.30 s |
| Frontend lint | **PASS** (`oxlint`) |
| Production build | **PASS**, Vite 8.3.5, **1,838 modules** |
| Asset budget | **74 JS/CSS assets**, 0 violations; largest JS 364.5 KiB, CSS 248.4 KiB |
| Python AST syntax | **162 backend Python files parsed**, 0 failures |
| Dependency lock tests | **2 passed**, 1 plugin warning |
| `pip check` in recovered environment | **No broken requirements found** |
| `npm audit --offline --audit-level=low` | **0 locally cached vulnerabilities**; advisory-cache freshness not verified |

The recovered environment was isolated with loopback-only nonresponsive MongoDB settings, disabled payments, disabled scanner mode, test secrets, no external service calls, and no connected-test opt-in. No ClamAV assertion was weakened.

## 14. Gitleaks results

A final redacted Gitleaks 8.30.1 current-tree directory scan ran after both Phase 24A.8 reports were present. It scanned approximately 8.46 MB and exited 1 with exactly **six** findings:

- `backend/tests/test_api_contract.py`: **5** `submission_key` synthetic fixture findings;
- `backend/tests/test_schedule_fallback_guard.py`: **1** `submission_key` synthetic fixture finding; and
- Phase 24A.8 paths flagged: **0**.

This matches the previously reviewed synthetic-fixture baseline and is not a zero-finding result. Secret values were redacted and were not reproduced in this report. Remote Git history is **NOT VERIFIED**, and online secret-service checks were **NOT PERFORMED**.

## 15. All 21 screen status summary

`PASS` means the current offline frontend/backend contract is covered by executed tests. It does not mean connected database, real-browser, storage/scanner, provider, or production verification.

| Group | Screens | Offline status |
|---|---|---:|
| Patient (9) | `BookAppointment`, `HomeVisitRequests`, `PatientAppointments`, `PatientCarePlan`, `PatientDashboard`, `PatientExercises`, `PatientHistory`, `PatientProgress`, `PatientReports` | **9 PASS** |
| Admin (9) | `AdminDashboard`, `AdminPatientHistory`, `AppointmentBooking`, `Billing`, `CarePlanManagement`, `DemoServices`, `ExerciseAssignmentManagement`, `Notifications`, `ReportAuthoring` | **9 PASS** |
| Doctor (2) | `DoctorDashboard`, `DoctorPatientHistory` | **2 PASS** |
| Reception (1) | `ReceptionistDashboard` | **1 PASS** |

Summary: **21 PASS, 0 PARTIAL, 0 FAIL, 0 BLOCKED for offline screen contracts**. The admin clinician directory is an additional Phase 24A.7 screen/path and also passes its focused offline checks. Connected gates remain separate.

## 16. Remaining policy decisions

The clinic/security owner must approve:

1. the new-password minimum/maximum and passphrase/compromised-password rules;
2. treatment and migration triggers for existing credentials;
3. email ownership, activation, resend, address change, exception, and audit policy;
4. patient recovery channel, identity proofing, token/session and support policy;
5. staff invitation, identity/role approval, activation, recovery, deactivation and emergency access; and
6. provider, privacy, retention, monitoring and operational ownership.

Until those decisions are authoritative and verified, the issue remains **POLICY DECISION REQUIRED**.

## 17. All eight connected release gates

| Gate | Status | Required evidence still absent |
|---|---|---|
| 1. Connected multi-clinician authorization | **BLOCKED** | Approved isolated identities/data and deliberately mismatched connected authorization cases |
| 2. MongoDB query plans and realistic-scale performance | **BLOCKED** | Approved database/dataset, `explain`, latency and concurrency evidence |
| 3. Actual database index verification | **BLOCKED** | Deployed index inventory including unique partial appointment slot claims |
| 4. Socket-capable ClamAV protocol and scanning | **BLOCKED** | Socket-permitted environment, daemon interoperability, real scan and timeout evidence |
| 5. Private storage integration and access verification | **BLOCKED** | Deployed private permissions, quarantine/approval movement, cleanup and authorized downloads |
| 6. Browser end-to-end journeys | **BLOCKED** | Approved real-browser multi-role/auth/booking/PDF/account-switch journeys |
| 7. Production proxy, TLS, cookie and cache verification | **BLOCKED** | Production-like ingress/TLS/Secure-cookie/Host/security-header/cache evidence |
| 8. Backup and restore testing | **BLOCKED** | Approved infrastructure, backup artifact, restore exercise and verification |

No gate was exercised or cleared in Phase 24A.8.

## 18. Updated Phase 24A status

**Outcome B — Conditional Offline-Scope Closure.**

Verified application implementation and offline test evidence remain acceptable for the bounded offline scope. Password/email/recovery/staff policy approval remains unresolved. Connected infrastructure, client demonstration, staging, and production authorization are independent and not established.

- Client demonstration: **HOLD / NOT AUTHORIZED**.
- Staging: **NOT AUTHORIZED**.
- Production: **NOT READY / NOT AUTHORIZED**.
- Phase 24B: **BLOCKED / NOT STARTED**.

## 19. Recommended next milestone

Stop after Phase 24A.8. Obtain explicit written clinic/security decisions on every item in the decision package, verify the decision-maker's authority, and conduct an independent review of this report. Only then prepare a separately approved implementation plan and targeted tests. Do not begin Phase 24B, connect providers or protected databases, provision staging, migrate data, or authorize a client demonstration from this report.
