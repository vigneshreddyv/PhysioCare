# Phase 22 — Comprehensive PhysioCare Security Audit

**Date:** 2026-11-01  
**Branch / HEAD:** `codex/physiocare-integration-2026-10-31` / `5eaced696a156ca74233fd04252fea52345d8af8`  
**Assessment:** **HOLD for client demonstration; FAIL for production release.** This is a bounded source and offline-test audit, not an independent penetration test or connected staging signoff.

## Executive summary

The current worktree contains 22 tracked modifications and 23 untracked paths before this report. These include Phase 16–21 documents, production configuration hardening, Phase 18 authentication and schedule changes, and tests. They were preserved. No application source, `.env`, credential, database, service, or Git state was changed for this audit.

The application has substantive controls: database-backed sessions and revocation, CSRF checks, role and ownership checks, neutral public registration, fail-closed PDF quarantine, verified payment signatures, and staging/production configuration guards. Source inspection found **no confirmed Critical or High application-code vulnerability** in the reviewed paths. It did find three actionable Medium issues, one Low issue, and major operational verification gaps. Passing offline tests cannot establish cross-patient isolation, scanner behavior, proxy correctness, payment behavior, or storage security in the intended deployment.

The fresh full backend run in this sandbox was **640 passed, 11 failed, 3 skipped, 1 warning**. All 11 failures were fake ClamAV Unix-socket tests blocked at socket bind by `EPERM`; this is an environment limit, not evidence that those tests passed. A focused auth/API run passed 136 tests. Frontend tests passed 95; lint and a temporary production build passed. Gitleaks found 5 historical and 6 current-worktree candidates; the reviewed matches are synthetic `submission_key` fixtures, not credentials. No current online Python advisory lookup was authorized.

## Scope and method

- Read the current Git status and source for the FastAPI startup/configuration path, authentication and session middleware, principal API routers and services, Beanie repositories, PDF storage/scanner, payments, and frontend auth state. Reviewed Phase 16–21 and production-readiness documentation as context, without accepting prior test counts as current evidence.
- Inspected route dependencies and service-side object checks for patient, clinician, administrator, receptionist and laboratorian workflows. This was code-path review, not an exhaustive formal proof for every branch.
- Ran offline tests with `ENVIRONMENT=test`, synthetic JWT secrets, MongoDB pointed at unreachable loopback port 1, Razorpay and reconciliation disabled, scanner disabled, and opt-in connected tests skipped by their own guards. No MongoDB or provider connection was made.
- Ran redacted Gitleaks scans of Git history and the current directory. Reviewed candidate *context* without printing candidate values. Did not inspect real `.env` values.

## Findings

### Critical — none confirmed

No Critical defect was demonstrated. This does not certify that none exists.

### High — no confirmed application-code defect; release blockers remain

**H1 — Connected operational security remains unverified (High release risk; not a demonstrated code exploit).** The real ClamAV daemon and private storage configuration have not been validated together; MongoDB multi-worker/proxy behavior, connected role-negative workflows, backups/restoration, and approved staging topology/owners remain open. Source: `backend/app/core/config.py:231-233,478-499`, `backend/app/main.py:29-62`, `backend/app/services/clinical_report_storage.py:230-320`, `docs/PHASE_21_STAGING_APPROVAL_CHECKLIST.md`, `docs/PRODUCTION_READINESS_FINAL_REPORT.md`. **Impact:** the deployed safety properties are unknown, and clinical report upload cannot be considered operationally ready. **Verification:** approved isolated staging with fictional records, negative authorization journeys, real scanner failure modes, private storage/backup restore, proxy chain, and multi-worker tests. **Remediation:** assign owners, approve exact infrastructure/data scope, and require recorded PASS evidence before any real-data deployment. Do not treat an unavailable scanner as a reason to disable scanning.

### Medium

**M1 — Inactive accounts can receive a new login session.** `backend/app/services/auth_service.py:157-188` verifies password and persists an `AuthSession` without checking `user.is_active`. Protected requests and refresh do check activity (`backend/app/middleware/auth.py:103`; `backend/app/services/auth_service.py:307-315`), so this review did **not** find an inactive-user authorization bypass. **Impact:** a disabled account receives cookies and a misleading successful login; session records are unnecessarily created. **Safe verification:** offline service test with an inactive user and valid synthetic password, asserting no session insert and the same generic login failure shape. **Remediation:** include activity in the generic invalid-credentials branch before session creation; preserve timing and enumeration-neutral behavior.

**M2 — Clinical PDF and authenticated PHI responses have no explicit no-store policy in the application.** `backend/app/api/reports.py:69-104` and `backend/app/api/lab_requests.py:134-144` return `FileResponse` after ownership checks but set no `Cache-Control`. No global cache-control middleware was found in `backend/app/main.py:62-100`. **Impact:** browser or intermediary caching could retain private clinical files after logout, subject to deployment proxy behavior. **Safe verification:** offline response-header test for authorized fictional PDF download; inspect the staging ingress cache policy. **Remediation:** set `Cache-Control: private, no-store` (and an appropriate content disposition) for clinical downloads and other sensitive authenticated responses; disallow shared caching at ingress. Preserve authorization checks.

**M3 — Several clinical collection queries are unbounded.** `backend/app/repositories/lab_request_repository.py:33-54`, `backend/app/repositories/report_repository.py:46-50`, and `backend/app/repositories/appointment_repository.py:252-293` use `.to_list()` without a visible limit; the admin lab query loads all requests. **Impact:** a growing database can produce large PHI responses, excess memory use, and slow requests. This is a scalability and potential resource-exhaustion risk, not a demonstrated data leak. **Safe verification:** offline query-contract tests plus an approved load test using fictional data. **Remediation:** enforce bounded server-side pagination and stable ordering; keep patient/clinician scoping on every page.

### Low

**L1 — Public registration accepts a six-character password.** `backend/app/schemas/auth.py:9-16` sets `min_length=6` for `UserRegister` while staff creation uses eight. Authentication throttling reduces online guessing, but the policy is weak for clinical accounts. **Impact:** user-chosen weak passwords can be more easily compromised, especially if reused elsewhere. **Safe verification:** schema-only test of the current boundary. **Remediation:** set a clinic-approved minimum and maximum with clear user guidance and tests; preserve existing hash and enumeration-neutral registration contracts. Account email ownership/recovery policy also needs a clinic decision.

### Informational and deployment-dependent observations

- **I1 — Security headers and host enforcement depend on deployment controls.** The application configures CORS and rejects untrusted unsafe request origins (`backend/app/main.py:69-90`), but no application-level `TrustedHostMiddleware`, HSTS, CSP, frame, referrer, or `X-Content-Type-Options` policy was found there. An ingress may provide them; none was inspected. Define and test the actual ingress policy before release. No Host-header exploit was demonstrated.
- **I2 — Environment intent cannot be inferred from code alone.** Direct ASGI imports require `ENVIRONMENT`, production requires process `ENVIRONMENT=production`, and production/staging URI/TLS guards run (`backend/app/core/config.py:290-299,478-604,721-733`; `backend/app/main.py:29-30`; `backend/run_production.py`). An operator who explicitly provides a complete development identity on a host intended for production can still select development behavior. Deployment admission must enforce the approved profile, origins, TLS and lifespan. Unknown unrelated-looking process-variable typos may escape the settings-family validator (`backend/app/core/config.py:273-288`).
- **I3 — Provider and file controls are implemented but not operationally proven.** Payment amount is derived server-side and provider amount/signatures are checked (`backend/app/services/payment_service.py:140-227,541-578,658-755`); webhook raw-body signature is verified before processing and body digest supports deduplication. No Razorpay Test Mode call or refund validation occurred in Phase 22. Clinical PDF storage validates size/structure, uses opaque keys/private paths, quarantines, scans fail-closed, audits and reconciles cleanup (`backend/app/services/clinical_report_storage.py:73-79,166-331,384-452`). No real daemon or storage integration was tested here.
- **I4 — Secret-scanner candidates are synthetic fixtures.** Gitleaks 8.30.1 returned five `generic-api-key` history matches in `backend/tests/test_api_contract.py` and six current-tree matches: five in that file and one at `backend/tests/test_schedule_fallback_guard.py:181`. Redacted historical/current context confirms these are fictional `submission_key` values used by booking tests; no credential key context was found. **Classification:** synthetic/example values, not confirmed secrets. This is a classification of these eleven candidates only, not proof that the repository contains no secrets. Preserve redaction in future scans.

## Control review by workflow

| Area | Source evidence | Assessment / limit |
| --- | --- | --- |
| Auth/session/CSRF | `backend/app/middleware/auth.py:38-120`; `backend/app/api/auth.py:91-157`; `backend/app/services/auth_service.py:157-316` | JWT/session binding, DB revocation, unsafe-method CSRF and refresh rotation are present. Logout and profile-fetch failures hide private frontend state and expose retry (`frontend/src/context/AuthContext.jsx:87-201`). M1 remains. No browser or multi-worker replay test here. |
| Authorization/IDOR | `backend/app/api/appointments.py:28-100`; `backend/app/api/users.py:29-145`; `backend/app/api/reports.py:33-110`; `backend/app/api/lab_requests.py:23-144`; `backend/app/api/payments.py:21-90` | Roles are enforced on sensitive routes; patient report download resolves ownership server-side. Booking, care-plan, exercise and lab services have object checks. Negative connected cross-patient journeys remain required; source review does not prove every IDOR path safe. |
| Other route families | `backend/app/api/care_plans.py:32-373`; `backend/app/api/exercises.py:29-412`; `backend/app/api/clinician_schedules.py:16-44`; `backend/app/api/home_visits.py:26-148`; `backend/app/api/laboratory.py:19-252`; `backend/app/api/notifications.py:10-59`; `backend/app/api/analytics.py:7-10` | Sensitive endpoints declare role or authenticated-user dependencies; the services must still enforce object scope. The laboratory patient-supplied payment update route delegates to a service that returns 410, so it was not classified as a payment-state bypass. Per-route connected negative testing is outstanding. |
| Account creation | `backend/app/repositories/account_registration_repository.py:20-47`; `backend/app/services/auth_service.py:96-154` | User and role profile use one Mongo transaction; duplicate handling is present. Connected registration rollback/retry test remains opt-in and was not run. |
| Booking/demo | `backend/app/services/clinician_schedule_service.py:35-42,129-157`; `backend/app/services/appointment_service.py` | Demo fallback is gated to explicit development demo identity and booking checks schedule eligibility. No live workflow was exercised. |
| File handling | `backend/app/services/clinical_report_storage.py:73-79,166-331`; `backend/app/api/lab_requests.py:83-144` | Private, size-limited, scanned/quarantined paths are implemented; M2 and real-scanner gate remain. |
| Payments | `backend/app/api/payments.py:35-91`; `backend/app/services/payment_service.py:140-227,541-578,658-755` | Ownership, server-side amount and signatures are checked. Provider callback, reconciliation, refunds and operational replay need approved connected validation. |
| Production config | `backend/app/core/config.py:290-299,478-604,721-733`; `backend/app/main.py:29-30`; `backend/run_production.py` | Explicit selection and URI/TLS guards exist. Actual deployment environment and ingress are unverified. |

Input review found Pydantic request models, explicit `PydanticObjectId` conversion in the clinical repositories, opaque report storage keys, and server-derived payment amounts. No confirmed Mongo operator injection or path traversal was established in the inspected paths. The absence of a confirmed exploit is bounded by source inspection and offline tests; request-size enforcement at the actual ingress, API response caching, pagination, and error/log redaction still need deployment checks. For patient privacy, administrator and assigned-clinician access should be tested with deliberately mismatched fictional patient IDs, including list, detail, mutation and download routes.

## Tests and audit-tool results

All commands were run from this repository unless a working directory is specified. For backend pytest, the environment was cleared with `env -i` and only `PATH`, `HOME=/private/tmp`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=backend`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `ENVIRONMENT=test`, an unreachable loopback Mongo URI at port 1, `DATABASE_NAME=physiocare_dev`, synthetic JWT secrets, `AUTH_RATE_LIMIT_ENABLED=true`, `RAZORPAY_MODE=disabled`, `PAYMENT_RECONCILIATION_ENABLED=false`, and `PDF_SCANNER_MODE=disabled` were supplied. The interpreter was `/private/tmp/physiocare-phase14-locked.36WQ5D/venv/bin/python` with `-m pytest -q -rs -p pytest_asyncio.plugin -p no:cacheprovider -c backend/pytest.ini`.

| Check | Result |
| --- | --- |
| Full `backend/tests` offline pytest | **Exit 1:** 640 passed, 11 failed, 3 skipped, 1 warning. All failures were fake ClamAV tests blocked by Unix-socket `bind()` `EPERM` in this sandbox. The three skips are opt-in connected account registration, auth throttling, and report transaction tests. Plugin warning: `pytest_asyncio` already imported for assertion rewriting. Full suite is **not a fresh pass** here. |
| Focused `test_auth_session_rotation.py`, `test_auth_rate_limiting.py`, `test_api_contract.py` with same isolated pytest environment | **Exit 0:** 136 passed, 1 plugin warning. |
| `npm test` in `frontend/` | **Exit 0:** 95 passed, 0 failed, 0 skipped. |
| `npm run lint` in `frontend/` | **Exit 0.** |
| `npm run build` in `frontend/` | **Exit 1:** Vite could not write its temporary config under read-only `node_modules` (`EPERM`). |
| `npm run build -- --configLoader runner --outDir /private/tmp/physiocare-phase22-dist` | **Exit 0:** 1,835 modules transformed; temporary production build succeeded. Vite warned that the external output directory would not be emptied. |
| Fresh temporary-build asset check: 450 KiB JS / 300 KiB CSS limits | **Exit 0:** 73 JS/CSS assets, zero violations. `npm run check:bundle` also exited 0 on the pre-existing `frontend/dist` assets, so its result alone was not taken as a fresh-build check. |
| Python `ast.parse` of `backend/app` and `backend/tests` | **Exit 0:** 134 files parsed, zero syntax errors. |
| Installed-version comparison against `backend/requirements.lock` | **Exit 0:** 47 exact `==` pins parsed; zero missing or mismatched in the test venv. This is consistency, not a vulnerability audit. |
| `npm audit --offline --json` (summary only) | **Exit 0:** zero reported vulnerabilities. Offline advisory cache freshness is unknown. |
| `pip-audit` 2.10.1 | Available but **not run for current advisories**: this tool has no offline mode that establishes fresh advisory completeness, and external lookup was not approved for Phase 22. Phase 19 reported zero known vulnerabilities for 48 pins at that earlier time; that is historical evidence only. |
| Gitleaks 8.30.1: `gitleaks git . --log-opts=--all --redact=100 --no-banner --log-level error --report-format json --report-path - --timeout 120` | **Exit 1:** 5 historical candidates. `PATH` was pinned to `/usr/bin:/bin:/opt/homebrew/bin` so Gitleaks used the working macOS Git binary. See I4. |
| Gitleaks 8.30.1: `gitleaks dir . --redact=100 --no-banner --log-level error --report-format json --report-path - --timeout 120` | **Exit 1:** 6 current-tree candidates. See I4. Raw matches were not printed. |
| `git diff --check` | **Exit 0** before this report. |

## Priority and release gates

1. **Before a client demo:** resolve M1 and M2, decide whether M3 needs paging for demo-scale fictional data, rerun the full offline suite in a socket-capable local sandbox, and execute a fictional-data authenticated browser smoke test in an expressly approved isolated target. Do not use real patient documents or enable payments/scanning by bypassing their guards. Obtain explicit approval for any connected target.
2. **Before staging validation:** approve Phase 17/20/21 topology, owners, budget, retention, ingress, private storage, real ClamAV, TLS Mongo target, backup/restore and fictional-data cleanup scope. Staging remains **BLOCKED**.
3. **Before production:** close all Medium findings, run connected negative IDOR and multi-worker/proxy tests, registration/report transaction and recovery checks, scanner and storage failure tests, backup restoration, and Razorpay Test Mode/reconciliation if payments are in scope. Complete independent security review and explicit release approval. Production remains **FAIL**.

No Phase 23 fix, commit, push, deployment, connected test or infrastructure action is authorized by this report.
