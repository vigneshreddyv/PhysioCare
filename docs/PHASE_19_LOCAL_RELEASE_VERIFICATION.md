# Phase 19 — Local release verification

Assessment date: 2026-11-01. Repository: `/Users/boddisuryakathyakeya/PhysioCare/PhysioCare`.

## Recommendation

**Offline regression: PASS on the verified worktree. Proposed release candidate: HOLD for review. Staging: BLOCKED. Production: FAIL.** The final full backend run passed 579 tests with 2 connected tests skipped; frontend passed 89 tests, lint, build and bundle budget. A subsequent PyPI vulnerability audit reported zero known findings. Gitleaks later found only synthetic test idempotency keys in the scanned local history and current changes; its limitations and classifications are recorded below. Connected registration validation and the operational gates remain open. These results are not a deployment or independent security approval.

## Repository and change inventory

- Branch: `codex/physiocare-integration-2026-10-31`.
- HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`.
- Before this report: **16 modified tracked files, 14 untracked files, no staged files and no deletions**. All work was preserved; this report is the only Phase 19 source-tree addition. No commit, push, merge or deployment was performed.
- Modified tracked: `backend/RAZORPAY_TEST_MODE.md`; `backend/app/repositories/{care_plan_repository,exercise_repository,report_repository}.py`; `backend/app/services/{appointment_service,auth_service,clinician_schedule_service,home_visit_service}.py`; `backend/tests/{test_api_contract,test_auth_rate_limiting}.py`; `frontend/src/components/common/{Navbar,Sidebar}.jsx`; `frontend/src/context/AuthContext.jsx`; `frontend/src/layouts/PatientLayout.jsx`; `frontend/src/pages/common/EmailLogin.jsx`; `frontend/src/pages/patient/LaboratoryRequests.jsx`.
- Previously untracked: `backend/app/repositories/account_registration_repository.py`; `backend/tests/{test_account_registration_transaction,test_clinical_repository_failures,test_schedule_fallback_guard}.py`; `docs/{PHASE_16_OPERATIONAL_READINESS_REPORT,PHASE_17_STAGING_INFRASTRUCTURE_PLAN,PHASE_18_LOCAL_DEVELOPMENT_REPORT}.md`; `frontend/src/context/{loginSession,logoutSession}.js`; `frontend/tests/{auth-rendered-flow,booking-rendered-flow,laboratory-partial-failures,login-session,logout-session}.test.mjs`.

The tracked diff before this report was 316 insertions and 167 deletions across 16 files; untracked content is additional. The one-line Razorpay guide correction is historical documentation. No application change outside the assessed Phase 18 authentication, registration, scheduling, clinical-repository and laboratory-page scope was identified. The Phase 16/17 reports remain planning evidence, not proof of deployed infrastructure. The Phase 18 assessment's pre-implementation findings are historical and need a status update when documentation is next reconciled.

## Phase 18 change review

| Area | Current code and review result | Remaining evidence gap |
| --- | --- | --- |
| Logout | `AuthContext` hides private state and clears the query cache before revocation, blocks protected rendering while server sign-out is unconfirmed, and offers a retry. Callers navigate to login only after confirmed revocation. The backend logout/CSRF contract was not changed. | A browser with unavailable `sessionStorage` cannot persist the retry marker; the helper fails closed, but provider startup reads `sessionStorage` without a guard. This is a lower-priority robustness follow-up. |
| Login/profile | Successful `/auth/login` is followed by a valid `/auth/me` profile before navigation. Failed or ambiguous requests retain an incomplete state and a session-only retry, avoiding a duplicate password POST. Existing cookie/CSRF and role gates remain in place. | Rendered tests cover core transitions; full browser/device journeys are not run. |
| Account registration | Patient and doctor account/profile writes, including duplicate lookup, pass the same Mongo session into `with_transaction`; a failed transaction returns a generic 503 and does not fall back to unsafe separate writes. Public duplicate response remains neutral and password hashing remains in the service. | Rollback/retry are covered by offline mocks; a connected registration transaction and driver callback-retry behavior have not been validated. The known Phase 15 connected report transaction test does not validate this registration path. |
| Schedule and booking | Demonstration slots require `ENVIRONMENT=development` plus an explicit local/demo flag. Non-demo availability returns no fallback; booking validation independently rejects an unpublished schedule, including home visits. Published schedules remain usable. | Connected authorization/booking journeys and clinic schedule policy remain unverified. |
| Clinical lookups | Malformed object IDs return missing/empty results, while database faults now propagate to safe server errors instead of masquerading as missing records. | Fault-injection coverage is offline. |
| Laboratory page | Request and released-report queries render independent loading/error/retry states; the unused home-visit-context query was removed. | Browser accessibility and device-size behavior remain unverified. |

No confirmed new cross-patient access, role bypass, CSRF bypass, demo-slot exposure in non-demo mode, file-access weakening, or secret exposure was found in this bounded source review. This is not an independent security audit.

## Verification commands and results

Tests ran with Python 3.13 from the existing pinned virtual environment at `/private/tmp/physiocare-phase14-locked.36WQ5D/venv`. The backend command used `env -i`, synthetic JWT values, `ENVIRONMENT=test`, `MONGODB_URL=mongodb://127.0.0.1:1/physiocare_dev`, `DATABASE_NAME=physiocare_dev`, payment and reconciliation disabled, scanner disabled, `PYTHONDONTWRITEBYTECODE=1`, plugin autoload disabled, and no connected-test opt-in variables. No local or external MongoDB connection was attempted. The fake ClamAV suite binds only a temporary local Unix socket; its sandbox permission was granted for the rerun. No real scanner was started.

Exact full backend invocation, run from `/private/tmp` twice:

```sh
env -i PATH=/usr/bin:/bin HOME=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/boddisuryakathyakeya/PhysioCare/PhysioCare/backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ENVIRONMENT=test MONGODB_URL=mongodb://127.0.0.1:1/physiocare_dev DATABASE_NAME=physiocare_dev JWT_SECRET=synthetic-access-secret-for-offline-auth-tests-000000 JWT_REFRESH_SECRET=synthetic-refresh-secret-for-offline-auth-tests-111111 AUTH_RATE_LIMIT_ENABLED=true RAZORPAY_MODE=disabled RAZORPAY_KEY_ID= RAZORPAY_KEY_SECRET= RAZORPAY_WEBHOOK_SECRET= PAYMENT_RECONCILIATION_ENABLED=false PDF_SCANNER_MODE=disabled /private/tmp/physiocare-phase14-locked.36WQ5D/venv/bin/python -m pytest -q -p pytest_asyncio.plugin -p no:cacheprovider -c /Users/boddisuryakathyakeya/PhysioCare/PhysioCare/backend/pytest.ini /Users/boddisuryakathyakeya/PhysioCare/PhysioCare/backend/tests
```

The three focused invocations used this exact prefix through `backend/pytest.ini`, followed by the absolute `backend/tests/` paths corresponding to each filename in the table below. All other commands in the table were run from the repository root, except `npm` commands, which were run from `frontend/`.

| Check and command | Exit | Actual result |
| --- | ---: | --- |
| Full backend: `python -m pytest -q -p pytest_asyncio.plugin -p no:cacheprovider -c backend/pytest.ini backend/tests` (first sandbox run) | 1 | 568 passed, 2 skipped, 11 failed, 1 warning. All 11 failures occurred before assertions because the sandbox denied fake Unix-socket binding (`PermissionError: [Errno 1] Operation not permitted`). |
| Same full backend command after local Unix-socket permission | 0 | **579 passed, 2 skipped, 1 warning** in 2.84 s. The two skipped tests require explicit connected Mongo opt-ins. Warning: `PytestAssertRewriteWarning` for already-imported `pytest_asyncio`. No failed assertions. |
| Focused auth: `pytest -q` on `test_auth_rate_limiting.py test_auth_session_rotation.py test_account_registration_transaction.py`, with the same sanitized flags/environment | 0 | 34 passed, 1 plugin rewrite warning. |
| Focused booking: `pytest -q` on `test_schedule_fallback_guard.py test_appointments.py test_appointment_model.py test_home_visit_demo_fixtures.py test_home_visit_demo_isolation.py test_home_visit_demo_startup.py`, same flags/environment | 0 | 43 passed, 1 plugin rewrite warning. |
| Focused clinical/security: `pytest -q` on `test_clinical_response_consistency.py test_clinical_repository_failures.py test_report_transaction.py test_reports.py test_care_plans.py test_exercises.py test_laboratory.py`, same flags/environment | 0 | 146 passed, 1 plugin rewrite warning. |
| Lock contract: `python -m pytest -q -p no:cacheprovider backend/tests/test_dependency_lock.py` | 0 | 2 passed, 2 warnings because the asyncio plugin was intentionally not loaded for this isolated invocation. The full suite includes the same tests with the plugin loaded. |
| Python source compilation: `compile()` on every `backend/**/*.py`, with bytecode disabled | 0 | 136 files compiled. |
| Python installed dependency check: `python -m pip check` | 0 | No broken requirements. Pip warned that its normal cache directory was not writable. |
| Python lock comparison: installed distribution versions against every `backend/requirements.lock` pin | 0 | The initial simple parser reported 47 matches because it missed the `PyJWT[crypto]` extra syntax. A corrected PEP 508 parser checked **48 applicable requirements: 48 installed matches, 0 missing or mismatched**. Direct/lock/CI contract tests passed. |
| Frontend: `npm test` in `frontend/` | 0 | **89 passed, 0 failed, 0 skipped**. |
| Frontend lint: `npm run lint` | 0 | Oxlint passed. |
| Production build: `npm run build -- --configLoader runner` | 0 | Vite 8.3.5; 1,835 modules transformed; built in 1.06 s. |
| Bundle: `npm run check:bundle` | 0 | 73 JS/CSS assets within budget; largest JS 364.5 KiB, largest CSS 248.4 KiB. |
| Frontend installed dependencies: `npm ls --depth=0 --offline` | 0 | Installed top-level dependency tree resolved. |
| Whitespace: `git diff --check` | 0 | No changed-line whitespace errors. A separate scan of all 30 pre-report changed files found two trailing-space lines in `Navbar.jsx`; both exist unchanged in HEAD. |

The focused results overlap with the full backend suite and must not be added to its 579-pass total. No connected test was rerun.

## Dependency and secret audits

- `npm audit --offline --json`: exit 0, zero reported vulnerabilities across 219 dependencies. `npm audit --omit=dev --audit-level=high --offline --json`: exit 0, zero reported. Offline advisory availability may be stale or incomplete; these are not a fresh online registry audit.
- Initial Phase 19 assessment: `pip-audit` was not run because advisory lookup would have crossed the then-required offline boundary. On 2026-11-01, the user separately approved **PyPI advisory lookup only**. `pip-audit 2.10.1` then ran against the unchanged pinned graph with no dependency installation or fix:

  ```sh
  /private/tmp/physiocare-phase14-locked.36WQ5D/venv/bin/python -m pip_audit -r backend/requirements.lock --no-deps --disable-pip --vulnerability-service pypi --format json --desc off --aliases off --progress-spinner off --timeout 15
  ```

  Exit **0**; **48 packages reported, 0 known vulnerabilities**. Output was parsed into counts without printing package secrets or full advisory descriptions. Before this, a no-network `--dry-run` of the same locked input exited 0 and said it *would* audit 48 packages; that dry run was not treated as a vulnerability result. `pip-audit` warned that `--no-deps` on pinned but unhashed requirements is supported but fully hashed dependencies are preferred. The result is a point-in-time PyPI advisory lookup, not proof that unknown or unpublished vulnerabilities are absent.
- The repository CI uses `gitleaks/gitleaks-action@v3` on committed history. At the initial assessment no local binary was installed. The user later approved obtaining Gitleaks from an official trusted package source; the completed Gitleaks scans are recorded in the final section below. CI cannot scan this uncommitted worktree until a future approved commit/push.
- As a supplemental local check before Gitleaks installation, a redacted Python pattern scan used `git ls-files --cached --others --exclude-standard -z` to include tracked files and non-ignored untracked changes. It scanned **349 textual repository files** and found **30 candidates**: 20 secret/password assignments and 10 credentialed database URI patterns. No private-key block, GitHub/AWS/Razorpay/OpenAI/Stripe token shape or JWT-shaped value matched. The values were not printed. All 20 assignment matches are synthetic test fixtures. Eight URI matches are synthetic test fixtures or the example staging template. The remaining two at `backend/tests/test_development_database_guard.py:155` and `backend/tests/test_staging_configuration.py:107` were subsequently reviewed as **synthetic/example values**: the first constructs a marker in a negative error-redaction test and asserts it is absent from the error; the second is a negative staging-configuration test vector on an example target. No actual credential was identified. This heuristic scan is not a substitute for Gitleaks.
- No private `.env`, database, clinical file, log, generated build asset, or credential file is among the changed paths. Build output is ignored and was not staged.

## Open work and release gates

**Unimplemented Phase 18 product decisions:** appointment rescheduling, clinic-approved laboratory catalogue/prices, home-visit travel/coverage rules, and email ownership/recovery policy. Empty `apps/*` placeholders and large shared UI components remain polish/maintenance work. No browser, keyboard, screen-reader or mobile device-size smoke run was performed.

**Connected and operational gates:** no approved Phase 17 staging owners/target, no operational ClamAV daemon/signature validation, no approved connected Mongo multi-worker/proxy/IDOR workflows, no staging TLS/ingress/private-storage/backup-restore proof, no provider-connected Razorpay Test Mode validation, and no independent security review or clinic policy signoff. The prior one-off local report transaction contract pass remains historical evidence; it was not rerun and does not cover registration transactions. Production data and real patients were not used.

**Next action at initial assessment:** review the current Phase 18 diff and this report; run a fresh dependency and Gitleaks audit in an approved CI/network setting, then add a separately approved fictional-data connected registration rollback/retry contract on an isolated transaction-capable Mongo target. Reconcile the stale Phase 18 assessment after review. Keep staging and production release decisions separate from the offline pass.

## Follow-up after report review

The Phase 18 assessment was reconciled with the six implemented local findings, while preserving its original assessment as historical evidence. A new opt-in `backend/tests/test_account_registration_connected_mongo.py` was prepared **offline only**. Its hardcoded future target is `mongodb://127.0.0.1:27020/physiocare_phase19_registration_contract?replicaSet=physiocareDevRs&directConnection=true`. Execution requires exact matching mode, URI, database, acknowledgment, `MONGODB_URL` and `DATABASE_NAME` variables. Before any write, it checks MongoDB 8.3.7, the sole local PRIMARY, dedicated data/log paths, loopback binding and an empty test database. If separately approved and run later, Beanie initialization will create a User email index; the test uses fictional patient/doctor records, checks rollback, retry and duplicate semantics, deletes its own records in `finally`, and leaves collections/indexes in place. A separate read-only post-run verification would still be required.

**No connected test was run in this follow-up.** With the opt-in variables absent, an isolated invocation of the new file exited 0 with **1 skipped** and the existing pytest plugin rewrite warning. The existing offline registration file exited 0 with **7 passed** and the same warning. An offline guard probe returned false with no opt-ins, true with the exact six values, and false after changing the target URI; it did not open a connection. The new file compiled successfully, `git diff --check` passed, and the new/edited files had no trailing whitespace. The 579-pass/2-skip full-suite result above predates this new file; it is not presented as a fresh full-suite result after the addition. The PyPI and Gitleaks audits were completed later as recorded below; the release-candidate recommendation remains **HOLD**.

## Final local Gitleaks verification

The two previously pending URI candidates were inspected without printing their literal credential portions. Both are **synthetic/example values**, not confirmed credentials: `test_development_database_guard.py:155` builds an error-redaction test marker and asserts it is not echoed; `test_staging_configuration.py:107` supplies an example-target negative configuration vector. No authentication or connection was attempted. No revocation or rotation is indicated for these two test values.

The [official Homebrew formula](https://formulae.brew.sh/formula/gitleaks) offered an Apple Silicon bottle for Gitleaks **8.30.1** with no formula dependencies. `HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 HOMEBREW_NO_ANALYTICS=1 brew install gitleaks` first exited **1** because the sandbox denied Homebrew's log directory; after the specific directory permission was granted, the identical command exited **0** and installed the official bottle. Homebrew warned that macOS 27 is a prerelease version. `gitleaks version` exited **0** and reported **8.30.1**. No application dependency was upgraded.

The raw Gitleaks JSON was captured in memory only; `--redact=100` was used and only file, line, rule and count metadata were emitted. No raw report was written to the repository or terminal. The first history attempt exited **1 before scanning** because the local `/usr/local/bin/git` executable was incompatible with this Apple Silicon process. Using `PATH=/opt/homebrew/bin:/usr/bin:/bin` selected Apple Git and resolved that environment issue.

| Scan | Exact command/scope | Exit and findings |
| --- | --- | --- |
| All local Git refs/history, read-only | `PATH=/opt/homebrew/bin:/usr/bin:/bin /opt/homebrew/bin/gitleaks git . --log-opts=--all --redact=100 --no-banner --log-level error --report-format json --report-path - --timeout 120` | Exit **1** for **5 findings**, all `generic-api-key` in historical `backend/tests/test_api_contract.py` at two local commits. No scanner error after the Git-path correction. |
| Current working-tree changes | For each of the **32** paths from `git status --porcelain=v1 -z` (16 modified, 16 untracked): `PATH=/opt/homebrew/bin:/usr/bin:/bin /opt/homebrew/bin/gitleaks dir <path> --redact=100 --no-banner --log-level error --report-format json --report-path - --timeout 30` | **32 files scanned, 0 scan errors, 6 findings**: five in current `backend/tests/test_api_contract.py` and one in untracked `backend/tests/test_schedule_fallback_guard.py`. Each finding's individual Gitleaks exit was **1**; no-finding files exited **0**. |

**Classification:** All **11 Gitleaks findings** are **synthetic test idempotency/submission keys** in home-visit booking contract tests. The five historical and five current API-contract findings are versions of the same fixture pattern; the sixth current finding is a new schedule-guard test fixture. They match the default `generic-api-key` rule because of the field name and key-like test value. **Confirmed secrets: 0; potential real credentials: 0; synthetic/example false positives: 11; further investigation required for these findings: 0.** No values were printed or used. The two earlier heuristic URI candidates are also classified synthetic/example after the contextual review.

**Limits and required next step:** History coverage includes the repository's **local** Git refs only; no remote refs were fetched. Current-file coverage includes every modified and non-ignored untracked path, while unchanged tracked content is covered by the local history scan. Ignored `.env`, generated assets and local clinical data were intentionally outside this repository scan. Gitleaks default rules cannot prove that every possible credential pattern is absent. Preserve these findings as reviewed test fixtures, rerun the CI secret job after a separately approved push, and continue the connected registration and operational gates. **Release-candidate recommendation: HOLD. Staging: BLOCKED. Production: FAIL.**
