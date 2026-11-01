# Phase 15 release evidence checklist

Assessment: 2026-11-01. A checked box means only the stated local gate was observed; unchecked release gates require new evidence. Evidence is recorded in the linked Phase 15 reports and Phase 14 remediation record. **Deployment is blocked.**

## Local preparation

- [x] Branch/HEAD/remote tip and all 33 previously modified tracked plus 30 previously untracked files inventoried before Phase 15 edits; eight Phase 13 and eleven Phase 14 documents preserved. No commit or push.
- [x] Current offline backend regression passed locally: **531 passed, 0 failed, 0 skipped**. Both opt-in connected Mongo test files were excluded; TCP socket access was denied during this run. Focused staging/development/target-guard tests: **99 passed**.
- [x] One separately approved dedicated local MongoDB report transaction contract passed: ownership, both rollback cases and concurrent one-winner assertions. `finally` cleanup and independent read-only checks found zero records; the member remained PRIMARY. No staging connected contract ran.
- [x] Payment webhook replay source regressions passed: **47 payment tests**, including four new digest/header cases. No provider endpoint was contacted.
- [x] Private cleanup intent and explicit reference-checked reconciliation passed nine local cases across clinical and laboratory storage; no operational reconciliation was run.
- [x] API contract cases were included in the current **531-pass** offline backend run; the earlier focused count was **109 passed** before the staging TLS fixture update.
- [x] Frontend tests **59 passed**; lint, production build and 73-asset bundle budget passed.
- [x] Python compilation passed for **132 files** and Git whitespace check passed after the staging TLS fix.
- [x] Earlier Python `pip-audit -r requirements.lock` reported no known vulnerabilities and frontend production/full `npm audit --audit-level=low` reported zero; these audits were not rerun after the latest test/configuration edits. The current Python environment matches all **48 applicable lock entries**.
- [ ] Secret scan release signoff: the current no-network-verification scan of **336 tracked and untracked files** found **46 candidates in 14 files** (test fixtures, synthetic example/demo configuration and frontend password-field code). Paths/types were triaged; an authorized reviewer must confirm values and rescan the final commit.
- [ ] Hosted CI passed on the final reviewed commit; current work is uncommitted.

## Security and operations

- [ ] Independent external security review completed; no unresolved Critical or High findings.
- [ ] S15-1 staging worker-kill and commit-ambiguity recovery verified; open Medium findings S15-2 and S15-3 resolved or formally accepted with owner evidence; S15-5 cleanup reconciliation, alerting and older-file sweep validated operationally; S15-6 digest index and replay behavior verified in approved Test Mode; S15-7 staging Mongo TLS certificate/transport verified operationally.
- [ ] Previously exposed credentials rotated and independent staging/production secrets securely injected.
- [ ] Private operational PDF scanner with current signatures, health, resource limits and both-path test matrix passed. Local adapter code and fake-socket tests alone do not close this.
- [ ] Empty staging identity, separate credentials, storage, TLS and ingress approved and validated.
- [ ] Connected Mongo unique/TTL indexes, two-worker throttling, refresh replay, appointment/report races and failure recovery passed.
- [ ] Real browser role/IDOR/loading/error/mobile/keyboard workflows passed with fictional data; unsupported journeys explicitly deferred by owner.
- [ ] Razorpay Test Mode order, webhook, retries, reconciliation and capture-after-cancellation matrix passed under separate authorization. Live mode and refunds remain out of scope.
- [ ] Appointment legacy preflight and migration/conflict policy approved; required production indexes reviewed and applied under separate authorization.
- [ ] Clinic operating rules, clinician schedules, travel buffers, lab catalogue/prices, cancellations/refunds and retention approved; incomplete configuration cannot expose invalid slots.
- [ ] HTTPS, CORS, cookie, CSRF and security headers verified at actual ingress; logging/monitoring/alerts configured without sensitive data.
- [ ] Database/file backup restoration, downtime procedure, incident response and rollback rehearsal passed.
- [ ] Deployment architecture, operational owner, budget and final production go/no-go approved.

Any unchecked item remains open. Do not convert a prepared plan, local unit test, synthetic scanner response or vendor documentation into a checked connected release gate.
