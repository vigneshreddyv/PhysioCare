# Phase 14 End-to-End Validation

Assessment date: 2026-10-31

Remediation update: 2026-11-01. H1, H2 and the reviewed direct-object response
differences were corrected locally. Connected execution remains unperformed.

Connected execution status: **Not executed — isolated staging is not approved or provisioned**

## Historical locally executed evidence (before final remediation edits)

| Gate | Result |
|---|---|
| Focused authentication/authorization/PDF/dependency tests | 45 passed |
| API contract tests | 109 passed |
| Full backend tests from the clean locked Python 3.13 target | 382 passed |
| Frontend tests | 59 passed |
| Frontend lint | Passed |
| Production build | Passed |
| Bundle budget | Passed; 73 JS/CSS assets checked |
| Python compilation | Passed |
| npm audit | 0 vulnerabilities |
| pip-audit against `requirements.lock` | No known vulnerabilities |
| Secret scan | 35 candidates reviewed as synthetic/non-secret; no credential identified |

These are local source and simulated-contract results. They do not prove proxy,
multi-worker Mongo, operational scanner, browser, webhook, object-storage or
payment-provider behavior.

On the current uncommitted tree, the focused, API contract and full backend
commands stopped before collection because `pytest_asyncio` is absent and the
offline cache lacks 38 exact lock pins. Fresh frontend tests passed (59), as
did lint, build, the 73-asset budget, Python compilation and whitespace check.
See `PHASE_14_REMEDIATION_PASS.md` for the exact gap. The historical backend
counts above are not current-tree acceptance evidence.

A later approved clean Python 3.13 locked run on 2026-11-01 passed **89**
focused security/remediation tests, **109** API contract tests, and **424**
full backend tests, with **1** opt-in connected Mongo test skipped. This
supersedes the earlier offline local backend block. Hosted CI remains unrun.

## Connected staging matrix

The detailed role/journey matrix and stop rules are maintained in
`PHASE_14_WORKFLOW_TEST_PLAN.md`. Required connected coverage includes:

- patient registration/login/session rotation/logout/CSRF, profile, discovery,
  booking, cancellation, care, exercises, laboratory and report access;
- clinician assignment, appointments, care plans, exercises, report uploads and
  history, including assigned/unassigned/nonexistent/malformed object IDs;
- administrator patient/staff, scheduling, appointment, laboratory, audit and
  payment-visibility workflows;
- concurrent authentication, appointment and report-replacement attempts across
  at least two backend workers;
- clean, malicious-test, malformed, timed-out and unavailable-scanner PDF cases.

## Entry and stop conditions

Entry requires an approved empty staging identity, fictional dataset, exact
proxy/CORS configuration, private storage, operational scanner and sanitized
evidence location. Payment cases require separate Razorpay Test Mode approval.

Stop immediately if the target is ambiguous, startup accepts a database/storage/
payment identity outside the approved staging inventory, normal data appears, a secret or
clinical value reaches logs/client output, forwarded headers bypass limits,
missing and unauthorized resources differ observably, rejected content becomes
downloadable, duplicate active slots appear, or any live payment credential or
event is detected.

## Current conclusion

Current local backend regression is **verified in a clean locked environment**.
Connected E2E validation
remains blocked by external provisioning and approval and is not represented as
passed. The detailed prepared gate sequence is in
`PHASE_14_WORKFLOW_TEST_PLAN.md`.

The opt-in Mongo rate-limit contract is skipped unless all explicit loopback test
database guards are satisfied. It was prepared but not executed during remediation.
