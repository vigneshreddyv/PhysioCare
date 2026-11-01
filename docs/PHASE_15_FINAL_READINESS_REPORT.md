# Phase 15 pre-deployment readiness report

Assessment: 2026-11-01. Branch `codex/physiocare-integration-2026-10-31`; local HEAD `49d3636d98f5ca5f94f41e4c85e2d847fd1c1c9a`. Phase 13/14 and new Phase 15 changes remain **uncommitted**. The dedicated local MongoDB transaction contract was run once with fictional records. No deployment, staging database, scanner daemon or payment provider was contacted.

## Outcome

**Local offline regression: PASS. Dedicated local Mongo transaction contract: PASS. Isolated staging: NOT PROVISIONED. Connected staging/browser/payment: NOT RUN. Production deployment: NOT AUTHORIZED.** The earlier Phase 14 independent review failed; local source fixes and this re-review do not replace an external signoff.

## Work performed

- Inventoried the local branch/HEAD, tracked/untracked files and preserved Phase 13/14 documents. The current final review found 40 modified tracked paths and 45 untracked files, with no credential, clinical PDF, database or generated build artifact in the change list. The no-network-verification secret scan found 46 candidates in 14 files; final value-level reviewer signoff remains open.
- Re-reviewed authentication, registration, clinical authorization, PDF paths and Test Mode payment source. Prior cross-patient booking and staging-startup High defects remain locally corrected. Unknown-account login performs synthetic bcrypt verification. The booked-report path uses one Mongo transaction; the dedicated local contract passed ownership, both rollback cases and concurrent one-winner assertions. A worker-kill/commit-ambiguity rehearsal remains open. Report and laboratory storage journal cleanup intent before deletion and defer deletion after an ambiguous database error. The explicit majority-primary reference-checked reconciler has not run against a database. Webhook deduplication uses a verified-body digest; provider behavior remains unvalidated. Scanner, ownership-verification and broader orphan-cleanup questions are detailed in `PHASE_15_SECURITY_REVIEW.md`.
- Added a **private Unix-socket ClamAV protocol adapter**, startup `PING` guard, configuration and fake-daemon tests. Default remains disabled/fail-closed. No operational scanner or EICAR detection was validated.
- Prepared isolated staging/Mongo, browser, payment and clinic/deployment validation plans. One approved connected report transaction contract ran against MongoDB 8.3.7 on the dedicated local `physiocareDevRs` PRIMARY at `127.0.0.1:27020`, using only `physiocare_phase15_txn_contract`. The database had zero collections before the run; test cleanup and independent read-only verification found zero records afterward in `laboratory_bookings` and `reports`, and the member remained PRIMARY. No other connected test ran. The Task 7 review found that staging accepted `tls=false`; the approved fix now requires explicit verified MongoDB TLS, rejects conflicting or insecure URI options, and updates the synthetic staging template. No real staging TLS connection has been tested.

## Fresh verification

| Gate | Result | Limit |
|---|---:|---|
| Backend offline regression, Python 3.13 | **531 passed, 0 failed, 0 skipped** | Both opt-in connected Mongo test files excluded; TCP socket access denied during this run |
| Focused staging/development/target-guard tests | **99 passed** | Synthetic configuration only; no staging connection |
| Dedicated local report transaction contract | **1 passed** | One approved run; fictional records, both rollback cases, cross-patient rejection and concurrent one-winner assertions passed; cleanup left zero records |
| Other connected Mongo contract | **Not run** | Multi-worker rate limiting remains unverified |
| Frontend contracts | **59 passed** | Not a browser E2E run |
| Frontend lint, build, bundle budget | **Passed** | 73 JS/CSS assets checked |
| Python compilation; Git whitespace | **132 files compiled; passed** | Local source check |
| Python lock match | **48 applicable pins matched** | Existing isolated Python environment; no install or upgrade in this pass |
| Earlier dependency audits | **Previously reported no known Python vulnerabilities and 0 npm vulnerabilities** | Not rerun after the latest test/configuration changes |
| Current full tracked/untracked secret scan | **46 candidates / 14 files** | No online verification; candidates are in synthetic examples, tests, demo configuration and password-field code; value-level reviewer signoff pending |
| Hosted CI | **Not run** | Changes uncommitted |

The earlier Python audit and `pip check` refer to the Phase 14 exact-pinned lock. The current Python environment matched all 48 applicable lock entries. Fake Unix-socket scanner tests passed locally; no operational scanner or signature engine was used.

The existing development branch was retained: its large uncommitted Phase 13/14 worktree makes an automatic branch/commit split ambiguous. A release-preparation branch may be created after the intended file set is reviewed; no files were staged or committed here.

## Release blockers and next authority

1. Repeat transaction and authorization workflows in approved isolated staging, including worker-kill/commit ambiguity and Mongo indexes/two-worker/proxy tests; validate cleanup reconciliation, alerting and older-file sweep, and resolve or formally accept account ownership. Verify webhook digest index and replay handling with approved Test Mode; obtain an independent external security review.
2. Approve and operate a private scanner, then pass real signature, timeout/crash, storage and false-positive tests for clinical and laboratory paths.
3. Authorize the exact empty isolated staging target; validate Mongo indexes and two-worker/proxy/session/booking races, backup restore and connected IDOR/browser workflows using fictional accounts.
4. Supply and approve clinic schedules, home-visit policy/buffers, lab catalogue/prices, cancellation/refund and retention rules. Incomplete demo defaults are not deployment configuration.
5. Separately authorize Razorpay Test Mode validation; do not enable live payments/refunds. Run hosted CI, final audits/secret review, release/rollback rehearsal and owner go/no-go on a reviewed commit.

The conditional hosting options in `PHASE_15_DEPLOYMENT_ARCHITECTURE.md` are planning alternatives, not a deployment selection. The evidence checklist in `PHASE_15_RELEASE_CHECKLIST.md` controls the decision. **PhysioCare is not ready for its first real website deployment.**
