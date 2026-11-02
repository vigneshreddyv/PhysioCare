# Phase 16 operational readiness and staging preparation

Assessment: 2026-11-01. Branch `codex/physiocare-integration-2026-10-31`; committed baseline `5eaced696a156ca74233fd04252fea52345d8af8`. This assessment used source review and offline tests. No staging, production, Atlas, Razorpay, or real scanner was contacted. No service was started or database changed.

## Decision

| Gate | Status | Evidence or limit |
|---|---|---|
| Repository and hosted CI | **PASS** | Clean committed baseline; local tracking ahead/behind `0/0`. [CI run 41280571111](https://github.com/vigneshreddyv/PhysioCare/actions/runs/41280571111) passed backend/audit, frontend/build/audit and secret scan. No live remote fetch in this assessment. |
| Local offline regression | **PASS** | Fresh results below. |
| ClamAV operations | **BLOCKED** | Adapter/fake-socket tests pass; real daemon, signatures and private socket unverified. |
| Isolated staging | **BLOCKED** | Source guards exist; no approved target or connected TLS/proxy/storage evidence. |
| Razorpay Test Mode | **BLOCKED** | Offline source/tests only; no provider connection. |
| Production release | **FAIL** | Scanner, staging, payment, clinic-policy, recovery and independent review gates remain open. |

**Overall: local offline verification PASS; staging readiness BLOCKED; production readiness FAIL.**

## Tasks 1–6: source and environment review

React/Vite produces a static frontend. FastAPI/Python 3.13 uses Beanie and MongoDB. Report creation and booking transition share a Mongo transaction. Clinical and laboratory PDFs use private filesystem quarantine and separate approved directories. Python and frontend dependency graphs are locked in `backend/requirements.lock` and `frontend/package-lock.json`.

### Scanner — configured in code, not operationally verified

`ClamAvUnixScanner` streams quarantined bytes to `clamd` over a Unix socket. Configured startup requires a bounded `PING` before database initialization. The default unavailable scanner rejects uploads; storage limits size/time, records safe audit metadata and promotes only clean files. Both clinical and laboratory paths use this boundary. On this Mac, `clamd`, `clamscan` and `freshclam` were absent from PATH; Homebrew did not list ClamAV; no private socket was found in inspected user Library locations. Process enumeration was denied by the sandbox, so a daemon elsewhere cannot be ruled out. No real health check or signature detection occurred. The staging template sets scanner mode `disabled`, so uploads remain fail-closed.

Before enabling scanning, approve daemon package/image digest, Unix socket owner/group/mode, signature update and freshness policy, `StreamMaxLength`, memory/queue limits and alert owner. In isolated staging, use approved fictional/inert fixtures to test clean, detected, malformed, timeout, crash, unavailable and concurrent cases for **both** PDF paths. No scanner infrastructure was installed.

### Staging deployment checklist

| Requirement | Existing source control | Required connected evidence |
|---|---|---|
| Mongo isolation | Startup requires `physiocare_staging`, approved non-loopback host and credentials; ordinary development is restricted to loopback `physiocare_dev`. | Attest an empty dedicated replica set, least-privilege account, network boundary, indexes and no patient/production copy. |
| Mongo TLS | Explicit `tls=true` or `ssl=true`; false, duplicates/conflicts and certificate/hostname bypass rejected. | Verify real certificate chain, hostname, negotiated TLS and invalid-CA/name rejection. |
| Browser/ingress | Exact HTTPS CORS, trusted proxy CIDRs and auth throttling required in staging. | Test real proxy forwarding/spoofing, HTTPS, Secure cookies, CSRF and security headers. |
| Clinical files | Separate absolute storage/quarantine roots under dedicated staging root. | Check 0700/0600 permissions, same-filesystem promotion, encryption, backup/restore and retention. |
| Scanner | Unix-socket adapter and startup `PING` guard. | Operate approved daemon/signatures and test detection/outage. |
| Payments | Staging startup requires Razorpay and reconciliation disabled. | Keep off for initial staging; plan separate approved Test Mode environment or reviewed guard change. |
| Operations | `/health` returns a lightweight response; cleanup reconciler is explicit. | Define dependency readiness, redacted logs, alerts, backup restore, cleanup schedule, incident and rollback owners. |

Conditional minimal topology: HTTPS static frontend; controlled API host with two FastAPI workers and co-located private `clamd` socket; dedicated transaction-capable Mongo replica set over verified TLS; encrypted persistent private PDF storage; exact trusted ingress; secret store; backup, logs and alerts. A single API/scanner/files VM best fits the current Unix socket and local filesystem architecture but has a single-host failure domain. Managed containers need proven shared socket and persistent volume semantics. A separate TCP scanner does not fit the current adapter. Hosting and cost remain **undecided**. Estimated complexity: **medium to high**, driven by scanner operations, private clinical storage, ingress/TLS and recovery.

### Razorpay Test Mode

Source requires mode `test`, a `rzp_test_` key ID, server-only secrets and explicit INR billing currency before checkout. It validates checkout/webhook signatures and checks provider order, amount, currency and capture. Webhook deduplication uses a SHA-256 digest of the verified raw body with a unique index and rejects conflicting event headers. Captured-payment reconciliation has a bounded Mongo lease, retry and clinic-review states. These controls passed offline tests but no provider behavior, actual index, order, webhook or reconciliation run was verified here.

Test Mode plan: approve a separate isolated environment, secret delivery, exact HTTPS webhook, fictional appointments, provider event subscriptions, unique indexes and cleanup owner. Verify order reuse, checkout signature, captured/failed webhooks, changed-header replay, conflicting body/header, transient retry, captured-but-cancelled review and worker restart/lease behavior. Use only Test Mode keys; do not enable live mode or refunds. **Current staging guard rejects payment configuration**, so Test Mode needs its own approved environment or a separately reviewed security-sensitive configuration change.

### Security and reliability findings

- Authentication: access/refresh secrets differ; session rotation uses compare-and-set and replay revocation; CSRF and Mongo-backed throttling exist. Two-worker/proxy behavior and login timing distributions need connected evidence. Registration still lacks email ownership verification and recovery policy.
- Clinical documents: quarantine, scoped download and cleanup intent exist. The primary/majority reference-checked cleanup reconciler has not run operationally; older approved-file sweep, failed-unlink alerts and ambiguous-commit recovery remain open.
- Payments: signatures, digest/index declarations, idempotent attempts and reconciliation are source controls. Provider delivery, actual indexes and captured-funds recovery require approved Test Mode evidence.
- Database/reliability: the dedicated Phase 15 local transaction contract passed once; staging transaction, indexes, backup/restore, worker-kill and failover remain open. `/health` is not a dependency-readiness or restore attestation. Real ingress headers, alerts and recovery drills remain untested.

No new confirmed Critical or High source defect was established in this focused review. This is not an independent security signoff; the Phase 15 findings and clinic-policy decisions remain open.

## Task 7: fresh offline verification

The existing isolated Python 3.13 environment matched **48/48 applicable lockfile pins**. Backend tests ran with an empty inherited environment, synthetic JWT values, a loopback port-1 `physiocare_dev` URI, payment reconciliation/scanner disabled, and both opt-in connected Mongo files excluded. The first harness attempts failed because `pytest-asyncio` was not loaded correctly; a later run had 11 fake-socket failures because the sandbox denied local Unix-socket bind. After loading `pytest_asyncio.plugin` and granting local socket permission, the full selected offline suite passed. These were test-harness/permission failures; no assertions were changed.

| Check | Fresh result |
|---|---|
| Backend offline | **531 passed, 0 failed, 0 skipped**; one plugin rewrite warning |
| Frontend tests | **59 passed, 0 failed, 0 skipped** |
| Frontend lint/build/bundle | **PASS**; 73 JS/CSS assets checked |
| Python compilation (`app`, `tests`) | **PASS** |
| Lock comparison | **PASS**; 48 pins, 0 mismatches |
| Dependency vulnerability audit and committed secret scan | **PASS in hosted CI for this exact baseline**; no new local network audit |
| Connected Mongo, real scanner, staging, Razorpay | **NOT TESTED in Phase 16** |

## Tasks 8–9: blockers and next action

1. Approve an exact empty staging inventory: Mongo host/database/credential and TLS CA, proxy CIDRs, two API workers, private storage, scanner owner, fictional data, backup/restore target and cleanup owner. Review cost and operational responsibility before provisioning. Provisioning or connecting needs separate approval.
2. Approve and operate a private ClamAV daemon with maintained signatures; pass real detection and outage tests on both PDF paths.
3. Run connected staging authorization, two-worker throttling, transaction/worker-failure, cleanup, TLS and proxy checks with fictional data; verify cleanup and rollback. Resolve registration ownership and clinic-policy decisions and obtain independent security review.
4. Separately approve Razorpay Test Mode environment and provider tests. Keep live payments disabled.
5. After operational gates pass, repeat CI/audits and perform release, restore and rollback review before staging or production go/no-go.

This report does not authorize installation, external connectivity, data changes, payment operations or deployment.

Final diff review found only this new report and a correction to the historical Razorpay Test Mode guide's webhook deduplication description. No application code, tests, configuration, lockfile, or generated artifact changed. `git diff --check` passed; the new report has no trailing whitespace. A local high-confidence scan of both changed documents found no private keys, GitHub tokens, live Razorpay keys, AWS access keys, or credentialed MongoDB URIs. The committed baseline's separate CI secret scan passed.
