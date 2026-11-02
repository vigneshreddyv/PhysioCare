# Phase 24A.7 Residual Defect Remediation Report

Date: 2026-11-02

Repository: `/Users/boddisuryakathyakeya/PhysioCare/PhysioCare`

Branch: `codex/physiocare-integration-2026-10-31`

HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`

## 1. Executive summary

Phase 24A.7 fixed the confirmed Medium admin clinician-directory defect and the Low PatientCarePlan documentation discrepancy. The public-registration password finding remains **POLICY DECISION REQUIRED** because the repository explicitly records that the clinic has not approved a password, email-ownership, or recovery policy. No password boundary was silently changed.

The admin directory now uses one bounded server page, server-side literal search, stable ordering, a narrow projection, and a single User-to-Doctor aggregation. The unpaged service branches that performed one user lookup per doctor were removed. The React screen searches and navigates a single page, does not accumulate earlier pages, prevents older search results from replacing the current query, shares identical requests, and retains the existing schedule/profile-edit workflows.

Fresh verification produced **177 focused backend passes**, **7 focused frontend passes**, **149 full frontend passes**, and **969 backend passes with 3 connected skips** when excluding only the unchanged Unix-socket integration file. The complete backend run produced **970 passed, 11 failed, 3 skipped**; all 11 failures remain the known sandbox denial of AF_UNIX bind before application assertions.

Phase 24A remains conditionally closed for its offline scope rather than complete. Phase 24B was not started. Client demo, staging, and production remain unauthorized.

## 2. Initial working-tree state

Before Phase 24A.7 changes:

- Branch: `codex/physiocare-integration-2026-10-31`.
- HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`.
- Upstream: `origin/codex/physiocare-integration-2026-10-31`, ahead/behind `0/0`.
- Tracked changed paths: **87**.
- Untracked paths: **60**.
- Total changed paths: **147**.

The substantial tracked and untracked work from Phases 16–24A.6 was preserved. No reset, clean, restore, checkout, stash, commit, push, `.env` edit, credential change, migration, deployment, database connection, or external-service request occurred.

After the four new Phase 24A.7 paths and the previously clean tracked `DoctorsList.jsx` change, the final worktree contains **88 tracked changed paths, 64 untracked paths, and 152 total changed paths**.

## 3. Admin directory root cause

The browser component `frontend/src/pages/admin/DoctorsList.jsx` called `GET /users/doctors` with no search or page contract and retained the complete response. In `backend/app/api/users.py`, the absence of a `search` parameter selected `UserService.list_doctors()` rather than the existing paged search service. That service called `ProfileRepository.list_doctors()`, which used `Doctor.find().to_list()` without a limit, then called `UserRepository.get_by_id()` once per clinician. The result was both an unbounded collection read and N+1 user lookup behavior.

The existing `ProfileRepository.search_doctors()` path already supplied the correct architectural base: a User collection match, a Doctor `$lookup`, stable page operations, and output conversion. The remediation reused that contract rather than adding another pagination framework.

No active browser-side specialty or availability filter existed on the admin directory. Existing schedule navigation, profile editing, home-visit eligibility display, and public-profile fields were preserved.

## 4. Backend changes

- `backend/app/api/users.py` now always calls `UserService.search_doctors()` for the administrator directory, including a blank search. `page_window()` enforces page 1–1000 and page size 1–100, with 50 by default. The administrator `RoleChecker` remains the route dependency.
- The analogous receptionist no-search fallback was also removed, so that related clinician selector endpoint can no longer fall back to an unbounded public directory.
- `backend/app/repositories/profile_repository.py` keeps role and active-account filters at the start of the pipeline, joins the Doctor profile once, then applies escaped literal search before sort/skip/limit. Administrator search covers name, email, specialization, qualifications, and specialties. Public search still excludes email.
- Stable sort is `full_name` ascending followed by unique User `_id` ascending.
- The final projection names only the User and Doctor fields needed by `DoctorOut`/`PublicDoctorOut`; it does not return an entire User or Doctor document.
- `backend/app/services/user_service.py` no longer contains the unpaged `list_doctors()` or `list_public_doctors()` N+1 branches. The paged search service converts the joined pairs without a secondary repository lookup.
- No count query was added. An empty page remains the end signal under the existing array response contract.

## 5. Frontend changes

`frontend/src/pages/admin/DoctorsList.jsx` now:

- uses the existing `fetchClinicalPage()` helper with a 50-record page;
- sends every request through `/users/doctors?search=<escaped term>`;
- keys React Query by directory, deferred search, and page;
- resets to page 1 when the search input changes;
- renders only the current page and labels its count as page-local;
- uses `ClinicalPageNav` for direct page navigation, including records beyond the former 1,000-record browser boundary;
- sets `gcTime: 0` for the private page query;
- hides prior results while deferred search input is unsettled;
- preserves loading, empty, recoverable error, desktop, and mobile states; and
- preserves schedule navigation and the profile-edit snapshot/mutation.

The shared helper continues to deduplicate stable IDs within a page, share identical in-flight requests, reject responses after authentication-generation cancellation, and retain no earlier page. Login/logout already cancels clinical page requests and clears the query cache; those controls were not changed.

## 6. N+1 query elimination evidence

`backend/tests/test_phase24a7_admin_clinician_directory.py` verifies that:

- the route never calls the former legacy branch;
- the repository performs exactly one aggregation for the requested page;
- search, sort, skip, and limit occur before the narrow projection;
- the projection enumerates only required output fields;
- neither `find()` nor per-record `UserRepository.get_by_id()` is called;
- an empty page does not fall back to a full collection; and
- a fictional 1,250-clinician dataset returns only the requested 50-record page.

The N+1 service methods were removed rather than left as dormant route alternatives. `ProfileRepository.list_doctors()` still exists for separate internal workflows outside this finding; it is not reachable from the admin clinician-directory route.

## 7. Search and pagination behavior

The server first restricts Users to the doctor role and, where applicable, active accounts. It joins one doctor profile, applies escaped case-insensitive search across authorized fields, applies the existing home-visit eligibility filter where requested, sorts by `full_name` and `_id`, and only then applies skip/limit. Thus filters cannot be broadened or performed after pagination.

The browser retains one page. Page 25 tests return fictional clinicians 1200–1249 without retaining pages 1–24. Different search terms use distinct request keys, so a late older response cannot replace the current search. Identical path/page requests share one promise. Authentication cancellation aborts the request and rejects a later response.

The existing array contract has no `total` or `has_more`; a full 50-record page enables Next and a short page disables it. An empty page still renders navigation so an operator can return to an earlier page. Offset drift during concurrent writes and actual MongoDB query-plan efficiency remain connected limitations.

## 8. Regression test results

| Verification | Result |
|---|---:|
| New Phase 24A.7 backend directory and password-inventory modules | **8 passed**, 1 plugin warning |
| Focused admin, authorization, pagination, registration, rate-limit, session, and API-contract selection | **177 passed**, 1 plugin warning |
| New frontend directory module | **7 passed** |
| Full frontend suite | **149 passed**, 0 failed/skipped |
| Complete backend suite | **970 passed, 11 failed, 3 skipped**, 1 plugin warning |
| Backend excluding only `test_clamav_unix_scanner.py` | **969 passed, 3 skipped**, 1 plugin warning |
| Frontend lint | **Passed** |
| Production build | **Passed**, Vite 8.3.5, 1,838 modules |
| Asset budget | **74 JS/CSS assets, 0 violations**; largest JS 373,260 B, CSS 254,380 B |
| Python AST syntax | **162 backend Python files parsed** |
| Dependency recovery inventory | **48/48 locked artifacts found and valid** |
| `pip check` | **No broken requirements** |
| Gitleaks current-tree scan | **6 existing synthetic fixture findings; 0 Phase 24A.7 paths flagged** |

The warning is the unchanged `PytestAssertRewriteWarning` for explicitly loading an already-imported `pytest_asyncio` plugin. The three skips are the guarded connected account-registration, distributed rate-limit, and report-transaction tests. No connected opt-in was enabled.

## 9. Password policy investigation

Current behavior is inconsistent by flow:

- Backend public registration: `backend/app/schemas/auth.py` permits six characters.
- Frontend public registration: `frontend/src/pages/common/Register.jsx` requires eight characters.
- Backend staff creation and frontend staff management: eight characters.
- Frontend login accepts six characters; backend login has no creation-policy minimum, which is appropriate for compatibility with already-created accounts.
- Password hashing remains the existing Passlib bcrypt implementation in `backend/app/core/security.py`.
- Registration passes the validated plaintext only to the hashing/transaction path; passwords are not returned or logged.
- No password-change, reset, or recovery workflow is implemented in the current application. Production configuration does not define an approved password policy.

Existing reports explicitly state that password minimum, email ownership, and recovery policy require a clinic decision. The frontend's eight-character check is evidence of an intended UI boundary, but it is not an approved organization policy and cannot replace authoritative backend enforcement.

Changing the backend minimum later will not invalidate existing password hashes or block existing users at login, provided login remains compatible. It will affect new public registrations and any future reset/change flow. The backend must remain authoritative and frontend guidance must match it.

## 10. Password policy decision or approval dependency

Status: **POLICY DECISION REQUIRED**.

No password application code was changed. The current six-character backend minimum therefore remains an acknowledged Low risk: API clients can create a weaker password than the public web form permits, and short user-chosen passwords have less resistance to guessing or reuse-related compromise even with login throttling.

The clinic/security owner should approve a single public and staff policy covering minimum and maximum length, passphrase guidance, email verification/ownership, recovery/reset identity proofing, and treatment of existing accounts. A reasonable proposal for approval is to support long passphrases, reject only a clinic-approved minimum at the authoritative backend, allow a generous maximum, and apply the same rule to registration and future reset/change flows without retroactively breaking login. At minimum, the six-versus-eight inconsistency must be resolved. This report does not select the policy on the clinic's behalf.

`backend/tests/test_phase24a7_password_policy_inventory.py` records the present six/eight boundaries so a later approved change is explicit rather than accidental.

## 11. PatientCarePlan documentation correction

Status: **FIXED**.

The inaccurate Phase 24A.5 matrix entry named `/care-plans/me/active`. Inspection established:

- frontend consumer: `frontend/src/pages/patient/PatientCarePlan.jsx`;
- method: `GET`;
- request: `/care-plans` with `selection=active_latest`;
- backend route: `GET /api/care-plans` in `backend/app/api/care_plans.py`.

Only the affected Phase 24A.5 table cell was corrected to `GET /care-plans?selection=active_latest`. Historical PASS context and results were preserved. No application code was changed to match the inaccurate wording.

## 12. Files changed

Application code:

- `backend/app/api/users.py`
- `backend/app/repositories/profile_repository.py`
- `backend/app/services/user_service.py`
- `frontend/src/pages/admin/DoctorsList.jsx`

Tests:

- `backend/tests/test_api_contract.py`
- `backend/tests/test_phase24a7_admin_clinician_directory.py` (new)
- `backend/tests/test_phase24a7_password_policy_inventory.py` (new)
- `frontend/tests/admin-clinician-directory.test.mjs` (new)

Documentation:

- `docs/PHASE_24A5_BACKEND_TEST_ENVIRONMENT_RECOVERY_REPORT.md`
- `docs/PHASE_24A7_RESIDUAL_DEFECT_REMEDIATION_REPORT.md` (new)

No dependency, lock, environment, credential, payment, PDF/scanner, database, or deployment file was changed in this phase.

## 13. Exact test commands and outcomes

Backend commands used `/private/tmp/physiocare-phase24a5-venv/bin/python` from `/private/tmp` under `env -i`, absolute backend `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE=1`, disabled automatic pytest plugins, explicit `pytest_asyncio.plugin`, no pytest cache provider, `ENVIRONMENT=test`, synthetic distinct JWT secrets, unreachable `mongodb://127.0.0.1:1/physiocare_dev`, and disabled payment/Razorpay/scanner modes.

```text
python -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c backend/pytest.ini \
  backend/tests/test_phase24a7_admin_clinician_directory.py \
  backend/tests/test_phase24a7_password_policy_inventory.py -q
```

Result: **8 passed**, 1 plugin warning.

Two initial executions of the new tests exposed test-only mistakes: the email validator rejected a reserved `.invalid` fixture before the password assertion (2 failures), and the frontend test expected `Retry` while the existing shared error component renders `Try Again` (1 failure). Only the synthetic email addresses and expected label were corrected; no application behavior was changed to obtain the passing results above.

```text
python -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c backend/pytest.ini \
  test_phase24a7_admin_clinician_directory.py test_phase24a7_password_policy_inventory.py \
  test_clinician_directory.py test_phase24a3_admin_group_b2.py test_api_contract.py \
  test_auth_rate_limiting.py test_auth_session_rotation.py \
  test_account_registration_transaction.py -q
```

Result: **177 passed**, 1 plugin warning.

```text
python -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c backend/pytest.ini backend/tests -q
```

Result: **970 passed, 11 failed, 3 skipped**, 1 plugin warning. Each failure was in `backend/tests/test_clamav_unix_scanner.py` at `asyncio.start_unix_server()` → AF_UNIX `bind()` → `PermissionError: [Errno 1] Operation not permitted`, before its application assertion.

```text
python -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c backend/pytest.ini \
  backend/tests --ignore=backend/tests/test_clamav_unix_scanner.py -q
```

Result: **969 passed, 3 connected skips**, 1 plugin warning. This is a transparent supplemental result, not a full-suite pass.

```text
node --test tests/admin-clinician-directory.test.mjs
npm test
npm run lint
npm run build -- --configLoader runner \
  --outDir /private/tmp/physiocare-phase24a7-build-20261102 --emptyOutDir
```

Results: **7 focused frontend passes**; **149 full frontend passes**; lint passed; production build passed. The separate temporary-build budget check found 74 JS/CSS assets and zero violations of 450 KiB JS / 300 KiB CSS thresholds.

Read-only dependency/static commands produced 48/48 valid cached lock artifacts, clean `pip check`, and 162 parsed backend Python files. The final redacted Gitleaks scan returned the same six previously reviewed synthetic idempotency fixtures: five in `backend/tests/test_api_contract.py` and one in `backend/tests/test_schedule_fallback_guard.py`. No Phase 24A.7 path was flagged.

## 14. Remaining limitations

- Public password policy is still awaiting explicit clinic/security approval.
- The 11 Unix-socket integration cases remain blocked by AF_UNIX bind denial; the unchanged socket file was not weakened or skipped in the complete run.
- Actual MongoDB query plans, index selection, latency, and page behavior under concurrent writes remain unverified.
- Offset pagination can shift during concurrent writes and is bounded at page 1000.
- Separate internal unbounded clinician/profile helpers outside the admin directory still require caller-specific review; this phase did not indiscriminately alter operational schedule or home-visit calculations.
- The eight connected Phase 24A.6 release gates remain blocked.
- Browser tests are server-rendered/source/helper tests, not approved real-browser E2E journeys.
- Dependency recovery remains local-artifact reproducibility rather than a durable approved package mirror.

## 15. Updated residual defect register

| Finding | Previous severity/status | Phase 24A.7 classification | Evidence |
|---|---|---|---|
| Unbounded admin clinician directory and N+1 lookup | Medium, confirmed | **FIXED** | Bounded joined aggregation, narrow projection, one-page UI, 1,250-row/page-25 tests, role negatives, no per-row lookup |
| Six-character public-registration minimum | Low, confirmed | **POLICY DECISION REQUIRED** | Backend 6, public/staff UI 8, staff backend 8; no approved clinic policy or recovery flow |
| Incorrect PatientCarePlan endpoint wording | Low documentation discrepancy | **FIXED** | Corrected to `GET /care-plans?selection=active_latest` after frontend/backend trace |
| Socket-capable ClamAV integration | Environmental exception | **BLOCKED** | 11 unchanged cases denied AF_UNIX bind; socket-free evidence unchanged |
| Eight connected release gates | Blocked | **BLOCKED** | No infrastructure or external service was contacted |

No new Critical or High application defect was identified during this remediation.

## 16. Phase 24A offline-scope status

Phase 24A remains **Outcome B — conditional offline-scope closure**. The Medium code defect and Low documentation defect are fixed and adequately verified. The password issue prevents this phase from being marked fully complete because it still requires an explicit business/security policy decision.

All prior authentication/session, cache, PDF, storage/quarantine, role/ownership, notification, billing, appointment conflict/slot-claim, demo guard, pagination, exercise aggregation, dashboard, and 21-screen controls remained covered by the fresh backend/frontend regression runs. No connected evidence was reclassified as PASS.

Client demo: **HOLD**.

Staging: **NOT AUTHORIZED**.

Production: **NOT READY / NOT AUTHORIZED**.

Phase 24B: **NOT STARTED**.

## 17. Recommended next milestone

The next milestone may be planned, but it should be a focused Phase 24A policy/closure review rather than execution of Phase 24B. Obtain an explicit clinic decision on the public/staff password, email-ownership, and recovery policy; then implement the approved backend-authoritative rule with matching frontend and registration/reset tests. Separately retain the existing plan for socket-capable ClamAV and the eight approved connected gates.

After those decisions and evidence are independently reviewed, the project owner can decide whether Phase 24A is fully closed and whether Phase 24B planning may proceed. This report does not grant that approval.
