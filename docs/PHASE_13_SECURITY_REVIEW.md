# Phase 13 Security and Privacy Review

Assessment date: 2026-10-31

Scope: authentication, authorization/IDOR, sessions, report storage/access,
payments/webhooks, logging, CORS, errors, dependencies, and expiration

This was a focused source and automated-test review. It was not a penetration
test, protected-environment log review, or infrastructure assessment. No new
Critical or High source finding was identified. The findings below are concrete
gaps; their severity assumes the current authenticated clinic application model.

## Verified controls

- Access and refresh JWTs use distinct secrets; configuration rejects short or
  equal secrets. Cookies are HttpOnly for both tokens, `Secure` in production,
  and SameSite Lax.
- Refresh state is server-side: only hashes are stored, rotation is conditional,
  detected reuse revokes the session, logout revokes it, and an expiring Mongo
  index removes expired sessions. Every authenticated request checks the active
  session and user state.
- Unsafe authenticated requests require CSRF header/cookie/persisted-hash
  agreement. Cross-site or untrusted-origin unsafe API calls are rejected, and
  credentialed CORS rejects wildcard/empty origins.
- Role dependencies are present on protected routes. Patient-owned appointments
  and payment endpoints return a uniform not-found response for other patients.
  Doctor history returns the same not-found response for missing and unassigned
  patient history. Appointment races use conditional updates and unique claims.
- Clinical/lab report paths use opaque generated names, reject traversal and
  symlinks, enforce MIME/extension/size/PDF prefix, store with private modes, and
  apply patient/clinician/admin access rules before file response.
- Checkout and webhook signatures are verified before trusted payment state is
  applied. Provider payment is fetched and matched on order, capture, amount,
  and currency. Webhook event IDs and payment-attempt uniqueness provide replay
  and duplicate-delivery controls.
- Settings diagnostics redact credential-bearing fields. Payment reconciliation
  logs aggregate/identifier/error-type data rather than secrets, provider
  payloads, or patient contact/clinical content.
- Current local audits report zero npm vulnerabilities and no known Python
  vulnerabilities.

## Findings

### SEC-13-01 — Authentication endpoints have no application rate limit

- **Severity:** Medium
- **Affected files:** `backend/app/api/auth.py` (`register`, `login`, `refresh`,
  `csrf`); `backend/app/services/auth_service.py` (`login`)
- **Evidence:** Public login/registration routes call authentication services
  directly. No limiter dependency, per-IP/account attempt counter, 429 response,
  backoff, or lockout control is present; repository search found no rate-limit
  implementation.
- **Impact:** An attacker can make repeated credential guesses, registration
  attempts, or resource-consuming session requests until an upstream control
  intervenes. Upstream rate limiting was not verified.
- **Recommended remediation:** Add privacy-safe per-IP and normalized-account
  throttles at the trusted ingress/application boundary, with bounded backoff,
  generic responses, observability, and a documented support recovery path.
  Treat proxy headers as trusted only from the configured proxy.
- **Test required:** Burst and distributed-attempt tests for login/register/
  refresh; assert 429/backoff, no user enumeration, recovery after the window,
  and no bypass via spoofed forwarding headers.

### SEC-13-02 — Registration reveals whether an email is registered

- **Severity:** Low
- **Affected files:** `backend/app/services/auth_service.py` (`_create_user`),
  `backend/app/api/auth.py` (`register`)
- **Evidence:** Both the pre-check and duplicate-key path return `400` with
  `Email already registered`, while unknown addresses can register.
- **Impact:** A remote caller can enumerate existing patient/staff email
  addresses. This is a privacy signal even though login itself uses a generic
  credential error.
- **Recommended remediation:** Choose an owner-approved registration model. For
  public self-registration, return a uniform accepted response and communicate
  existing-account recovery out of band; alternatively require verified invite
  or email ownership before disclosing account state.
- **Test required:** Compare status, body, and timing envelopes for existing and
  new addresses; assert no role or account-state detail is disclosed.

### SEC-13-03 — Some clinician object APIs expose assignment-rule differences

- **Severity:** Low
- **Affected files:** `backend/app/api/care_plans.py` and
  `backend/app/api/exercises.py` permission-error handlers; related service
  assignment checks
- **Evidence:** Several care-plan/exercise paths convert assignment
  `PermissionError` text to a distinct 403 response. The doctor-history service,
  by contrast, intentionally returns the same 404 for missing/unassigned data.
- **Impact:** An authenticated clinician with a guessed resource/patient ID may
  distinguish an existing but unassigned relationship from a missing resource.
  No record content is returned, so impact is a limited existence/relationship
  oracle rather than demonstrated record disclosure.
- **Recommended remediation:** Centralize clinician-scoped lookup and return a
  uniform 404 for missing and out-of-caseload object reads/edits. Keep detailed
  denial reason only in a privacy-safe internal audit event.
- **Test required:** Matrix every direct object endpoint with assigned,
  unassigned-existing, missing, malformed, and wrong-role IDs; require equivalent
  external responses and zero cross-caseload content or mutation.

### SEC-13-04 — PDF validation is structural only; malware/content sanitization is absent

- **Severity:** Medium
- **Affected files:** `backend/app/services/clinical_report_storage.py` and the
  corresponding lab report storage path
- **Evidence:** Uploads are bounded and must have PDF MIME/extension and begin
  with `%PDF-`, but there is no full parser validation, antivirus scan, content
  disarm/reconstruction, active-content policy, or quarantine state before an
  authorized user opens the file.
- **Impact:** A compromised or malicious authorized uploader could store a
  crafted PDF that is later opened by staff/patients. Access control and browser
  sandboxing reduce exposure but do not establish file safety.
- **Recommended remediation:** Quarantine uploads; scan with an approved engine,
  validate/rewrite with a hardened PDF pipeline where feasible, serve with
  restrictive headers from a separate origin, and define retention/deletion and
  incident response. Fail closed if scanning is unavailable.
- **Test required:** EICAR-equivalent safe scanner fixture, malformed/polyglot/
  active-content PDFs, scanner outage, quarantine access denial, sanitized-file
  rendering, and authorized/unauthorized download tests.

### SEC-13-05 — Python production dependencies are not reproducibly locked

- **Severity:** Low
- **Affected file:** `backend/requirements.txt`
- **Evidence:** Several direct packages have only lower bounds or no versions,
  and transitive versions are not locked. The current audit is clean, but a fresh
  deployment can resolve a materially different graph. A prior audit in this
  branch already required replacing a newly vulnerable JWT dependency.
- **Impact:** Builds can change without source review, producing compatibility or
  supply-chain variance and making rollback/reproduction harder.
- **Recommended remediation:** Generate a reviewed, hashed constraints/lock file
  from supported Python/platform targets; keep the human-maintained direct list,
  automate update PRs and `pip-audit`, and rebuild on a defined cadence.
- **Test required:** Clean locked install on every supported target, hash
  enforcement, dependency audit/SBOM generation, and deterministic graph diff.

## IDOR and privacy disposition

No tested endpoint demonstrated unauthorized patient-record content access. The
strongest current protections are ownership-filtered payment/appointment paths,
doctor caseload filtering, uniform doctor-history 404 behavior, and
publication/assignment checks for reports. SEC-13-03 must be resolved and a
browser/API direct-object matrix must run against an isolated database before
claiming complete IDOR resistance.

## Production security gates

1. Resolve Medium findings or document an owner-approved compensating control.
2. Run rate-limit, IDOR, session replay/rotation/logout, file quarantine, and
   payment webhook tests in isolated staging.
3. Verify exact production CORS origins, Secure cookie behavior behind the real
   proxy, HTTPS/HSTS/security headers, trusted proxy configuration, database
   least privilege/TLS, storage encryption/backup, secret rotation, and log
   access/retention.
4. Repeat dependency and full-history secret scans on the exact release commit.
5. Complete an independent security test before real patient or payment data.
