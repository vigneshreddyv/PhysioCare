# Phase 14 Security Remediation

Assessment date: 2026-10-31

## Independent-review remediation update — 2026-11-01

- **H1 fixed locally:** diagnostic report creation now binds the supplied booking
  to the exact patient and explicitly authenticated admin/primary clinician. Only
  a matching `confirmed` booking can be atomically claimed; stale claims prevent
  report insertion and failed inserts trigger a conditional state restoration.
- **H2 fixed locally:** staging now has fail-closed startup validation for its
  environment value, deployment identity, database host/name/credentials, private
  absolute storage tree, HTTPS origins, proxy CIDRs, enabled distributed throttling,
  disabled payments/reconciliation and disabled scanner mode.
- **M1 fixed locally:** the reviewed appointment and laboratory direct-object paths
  now use identical generic 404 responses for missing and unauthorized objects.
- Scanner audit metadata is bounded, cleanup failures are safely visible, exact
  lock versions are compared, and sensitive service mutations require explicit
  actor context.

The detailed finding disposition and clinician access policy are recorded in
`PHASE_14_REMEDIATION_PASS.md`.

## Remediation summary

| Phase 13 finding | Phase 14 state | Source outcome | Remaining gate |
|---|---|---|---|
| Authentication rate limiting | Implemented locally | Shared atomic Mongo buckets, pre-verification account reservations, HMAC identifiers, TTL, safe 429/503, trusted-proxy resolver | Connected multi-worker staging and approved indexes |
| PDF malware quarantine | Implemented locally | Clinical and laboratory uploads quarantine separately, structurally validate, scan through one abstraction, fail closed, audit and promote only clean files | Approved operational scanner and staging storage validation |
| Registration enumeration | Implemented locally | Public new/existing/race cases return identical accepted body without email; expensive password hash precedes lookup | Email ownership/verification product decision and staging timing review |
| Clinician assignment oracle | Implemented locally after remediation | Primary-clinician mutations and appointment-scoped read access are separately defined; reviewed appointment, report and laboratory paths return generic resource 404s | Connected IDOR matrix across every direct-object route |
| Python dependency reproducibility | Implemented locally | Exact direct pins, fully pinned Python 3.13 lock, CI install/audit from lock; PyJWT raised to 2.15.0 after audit | Reviewed regeneration process and clean CI on final commit |

## Important implementation details

- Authorization checks were not removed. Only externally visible doctor denial
  responses were normalized. Clinician create paths authorize scope before
  existence validation, while unexpected infrastructure failures still surface
  as server errors. Admin access remains role-scoped; patient ownership checks
  remain intact; malformed patient IDs fail as nondisclosing denials.
- Staff creation remains an authenticated admin workflow and can report duplicate
  staff email to that administrator. Public patient registration does not.
- No password-reset/account-recovery endpoint exists in the current backend, so
  there was no reset route to throttle; any future recovery route must receive
  its own neutral-response and distributed-limit policy before release.
- Public registration preserves 422 field validation. It does not claim email
  delivery or ownership verification; those are not implemented.
- Throttling does not use an in-memory production counter and does not trust
  arbitrary forwarding headers. Atomic account reservations prevent a
  concurrent guess burst; per-client and per-token refresh limits prevent
  unique-token bypass. Mongo first-upsert duplicate races retry once safely.
- Quarantine does not treat filename, MIME, or `%PDF-` alone as proof of safety.
  Scanner calls have a bounded configurable timeout; exceptions and malformed
  scanner results become audited fail-closed 503 responses. The implementation
  does not call or pretend to provide an operational scanner.
- The lock was clean-installed into a temporary Python 3.13 target and the full
  backend suite passed from that target. `pip-audit` then reported no known
  vulnerabilities; the frontend audit reported zero vulnerabilities.
- A full working-tree `detect-secrets 1.5.0` scan produced 35 candidates. Every
  candidate was reviewed as a synthetic test value, validation copy, reserved
  object ID, cache tag, or non-secret demo volume identifier. No credential was
  identified. Cache/build/dependency directories were excluded from scanning.

## Changed surfaces

- Configuration: rate-limit values, trusted proxies, clinical quarantine path,
  safe staging templates.
- Data model: opaque `auth_rate_limit_buckets` with unique/TTL indexes.
- Authentication API/service: shared throttling and enumeration-neutral public
  registration.
- Clinical authorization APIs: generic doctor-scoped 404 behavior.
- Clinical and laboratory report storage: separate quarantine/scanner/audit
  lifecycles with cleanup on failed or concurrent database transitions.
- Dependencies/CI: direct exact pins, `requirements.lock`, locked install/audit.
- Frontend: registration success copy no longer asserts account existence.
- Tests: focused security, dependency, clinician-response and quarantine cases.

## Remaining security issues

1. **Medium:** no approved operational malware scanner; all report uploads fail
   closed until one is configured.
2. **Medium until staging evidence:** distributed throttling indexes and atomic
   behavior have not been exercised against an approved connected MongoDB.
3. **Low:** public registration has no email ownership verification or recovery
   flow; neutral responses reduce enumeration but do not prevent unusable/abusive
   address claims by themselves.
4. **Low:** registration paths still differ after lookup because successful creation
   must insert user/profile records; perfect timing equivalence is not claimed.
5. **Low:** the object-level response matrix is not yet executed in a connected
   browser/API environment.

No protected database, cloud resource, payment provider, or normal patient data
was accessed. No migration or index operation was run.
