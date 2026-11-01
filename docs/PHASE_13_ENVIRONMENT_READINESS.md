# Phase 13 Environment and Credential Readiness

Assessment date: 2026-10-31

Branch: `codex/physiocare-integration-2026-10-31`

Assessed commit: `49d3636d98f5ca5f94f41e4c85e2d847fd1c1c9a`

## Scope and evidence boundary

This is a source/configuration audit. No credential value was printed, no
credential was rotated, no database was contacted, and no payment provider was
contacted. The repository contains example configuration but no repository-local
runtime `.env` file. Consequently, settings that depend on a deployment secret
store or a protected environment are classified as **Cannot be verified** or
**Needs external authorization**, even when the application validates them at
startup.

Status meanings:

- **Configured**: a safe repository default or checked-in non-secret template is
  present and validated.
- **Missing**: a required owner-supplied value is absent from the checked-in
  template or cannot start from the template as-is.
- **Invalid**: the checked-in value is unsuitable for the stated environment.
- **Needs external authorization**: validation requires access to an external
  secret store, provider, or protected environment.
- **Cannot be verified**: source defines the requirement, but the runtime value
  was intentionally not inspected.

## Configuration checklist

### Core backend and authentication

| Setting | Repository state | Production expectation | Status |
|---|---|---|---|
| `MONGODB_URL` | Loopback development default; treated as secret by diagnostics | Protected URI supplied from secret storage, least-privilege account, TLS as appropriate | Cannot be verified |
| `DATABASE_NAME` | `physiocare` development default | Explicit authorized database name; must match preflight/migration runbooks | Cannot be verified |
| `JWT_SECRET` | Required, minimum 32 characters; blank in example | Unique high-entropy access-token secret | Missing |
| `JWT_REFRESH_SECRET` | Required, minimum 32 characters; blank in example and must differ from access secret | Unique high-entropy refresh-token secret | Missing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validated integer; default/example 15 | Owner-approved short access lifetime | Configured |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Validated integer; default/example 7 | Owner-approved refresh lifetime | Configured |
| `ENVIRONMENT` | Development default | Must be `production` to enable Secure cookies | Invalid for production |
| `HOST`, `PORT` | Development listener values provided | Deployment-specific bind address/port | Cannot be verified |
| `CORS_ORIGINS` | Explicit local origins; wildcard/empty values rejected | Exact HTTPS frontend origin(s), no wildcard | Invalid for production |
| `CLINIC_TIMEZONE` | Valid IANA zone required; `Asia/Kolkata` template value | Clinic-approved IANA timezone | Cannot be verified |
| `BOOKING_HORIZON_DAYS` | Range 1–365; template value 30 | Clinic-approved booking horizon | Cannot be verified |

### Schedules, home visits, storage, and frontend

| Setting | Repository state | Required decision/control | Status |
|---|---|---|---|
| `DEMO_SCHEDULE_START`, `DEMO_SCHEDULE_END`, `DEMO_SLOT_MINUTES` | Validated demo fallback, 30-minute grid | Not clinic-approved operating hours; published clinician schedules are the operational source | Cannot be verified |
| `DEMO_HOME_VISIT_REQUESTS_ENABLED` | Enabled in example | Decide whether provisional request capability is offered | Cannot be verified |
| `DEMO_HOME_SERVICE_CITY` | Explicitly provisional demo city | Clinic-approved geographic boundary; current support is one normalized city string | Cannot be verified |
| `DEMO_HOME_SCHEDULE_START`, `DEMO_HOME_SCHEDULE_END`, `DEMO_HOME_SLOT_MINUTES` | Validated demo fallback aligned to clinic grid | Clinic-approved home-visit hours and travel policy | Cannot be verified |
| `LAB_REPORT_STORAGE_DIR`, `LAB_REPORT_MAX_BYTES` | Private local path pattern and bounded size | Durable encrypted storage, backup/retention policy, capacity, malware controls | Cannot be verified |
| `CLINICAL_REPORT_STORAGE_DIR`, `CLINICAL_REPORT_MAX_BYTES` | Private local path pattern and bounded size | Durable encrypted storage, backup/retention policy, capacity, malware controls | Cannot be verified |
| `VITE_API_URL` | Local API URL in frontend example; dedicated home-visit demo file is non-secret and tracked intentionally | Exact deployment API origin; no secrets in any `VITE_*` value | Cannot be verified |

### Razorpay and reconciliation

| Setting | Repository state | Test Mode requirement | Status |
|---|---|---|---|
| `RAZORPAY_MODE` | Safe default `disabled`; absent from example | Explicit `test`; live mode is outside Phase 13 | Needs external authorization |
| `RAZORPAY_KEY_ID` | Empty default; only `rzp_test_` IDs pass readiness | Authorized Test Mode public key ID | Needs external authorization |
| `RAZORPAY_KEY_SECRET` | Empty default; redacted by settings diagnostics | Authorized Test Mode secret, backend only | Needs external authorization |
| `RAZORPAY_WEBHOOK_SECRET` | Empty default; redacted by settings diagnostics | Authorized Test Mode webhook secret, backend only | Needs external authorization |
| `APPOINTMENT_BILLING_CURRENCY` | Empty default | Owner must confirm stored amounts are major-unit INR, then set `INR` | Missing |
| `PAYMENT_RECONCILIATION_ENABLED` | Validated default `true`; worker still refuses to start unless Test Mode is ready | Enable only after Test Mode and database validation | Needs external authorization |
| `PAYMENT_RECONCILIATION_INTERVAL_SECONDS` | Valid range 5–3600; default 30 | Operations-approved polling interval | Configured |
| `PAYMENT_RECONCILIATION_BATCH_SIZE` | Valid range 1–500; default 50 | Capacity-approved batch limit | Configured |
| `PAYMENT_RECONCILIATION_LEASE_SECONDS` | Valid range 15–3600 and at least twice the interval; default 120 | Deployment-approved lease | Configured |

### Demo isolation

| Setting | Repository state | Status |
|---|---|---|
| `LAB_DEMO_MODE` and `PHYSIOCARE_ENV_FILE` | Lab demo validates a dedicated DB name, loopback Mongo listener, loopback server, dedicated origin/storage, development mode, and disabled payments | Configured |
| `HOME_VISIT_DEMO_MODE` and `PHYSIOCARE_HOME_VISIT_ENV_FILE` | Home-visit demo validates a different DB/listener/port/origin and disables payment credentials/reconciliation | Configured |
| Demo JWT values | Generated into private demo configuration by the launch scripts, not committed | Cannot be verified until an isolated demo launch is authorized |

## Environment profiles

| Profile | Database | Credentials | Payments | Browser/API origins | Readiness |
|---|---|---|---|---|---|
| Unit test | Test doubles/mocks; no normal DB required | Ephemeral test-only JWT strings in `backend/tests/conftest.py` | Provider methods mocked | No deployed origin | Ready for local automated tests |
| Local development | Local Mongo default unless explicitly changed | Developer-supplied untracked `.env` | Disabled by default | Localhost origins/API | Ready with configuration |
| Lab demo | Dedicated `physiocare_lab_demo` and loopback listener | Generated private demo config | Forced disabled | Dedicated loopback origin | Ready with restrictions; launch not performed in Phase 13 |
| Home-visit demo | Dedicated `physiocare_home_visit_demo` and separate loopback listener | Generated private demo config | Forced disabled | Dedicated loopback origin/API | Ready with restrictions; launch not performed in Phase 13 |
| Protected staging | Must be explicitly authorized and identified | External secret store | Test Mode only after authorization | Exact HTTPS origins | Blocked by external authorization |
| Production | Protected DB and storage | Rotated production secrets | Live payments not approved or validated | Exact HTTPS origins, Secure cookies | Not ready |

## Secret handling and token review

- `.env`, `.env.*`, frontend environment variants, private keys, generated
  uploads, database dumps, and local state are ignored. Safe examples are
  allow-listed. `frontend/.env.home-visit-demo` contains only a loopback API URL.
- `Settings.__repr_args__`, `model_dump`, and `model_dump_json` redact the Mongo
  URI, both JWT secrets, and both Razorpay secrets. The preflight also suppresses
  connection detail on errors. No current payment worker log includes provider
  payloads, patient contact data, or credentials.
- Access/refresh tokens are signed with different secrets. Access and refresh
  JWTs carry a session ID; the server persists hashed refresh/CSRF material,
  rotates refresh tokens atomically, revokes detected reuse, and checks session
  expiry on each authenticated request.
- Access and refresh tokens use HttpOnly cookies. Production mode enables
  `Secure`; SameSite is `Lax`. Unsafe requests require the CSRF header, cookie,
  and persisted hash to match. Logout revokes the session and clears all cookies.
- No real credential was found in the inspected configuration or application
  code. The historical GitHub full-history Gitleaks check passed, but credential
  rotation remains an external owner action because previously exposed values
  cannot be made safe by source changes.

## Required owner/external actions

1. Rotate any previously exposed MongoDB, JWT, Razorpay, and webhook secrets in
   their authoritative systems; do not communicate values in chat or Git.
2. Confirm an authorized staging database name, read-only preflight account, and
   network boundary before any appointment preflight.
3. Confirm clinic timezone, operating policies, booking horizon, currency/amount
   convention, origins, and storage/retention requirements.
4. Provide Test Mode authorization through the deployment secret mechanism,
   then follow `PHASE_13_PAYMENT_VALIDATION_PLAN.md`.
5. Run an environment smoke check that reports only presence/validity—not values—
   before deployment.
