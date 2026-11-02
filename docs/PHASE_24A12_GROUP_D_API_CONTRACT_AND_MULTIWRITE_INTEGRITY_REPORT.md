# Phase 24A.12 Group D — API Contract and Multi-Write Integrity Report

Assessment date: 2026-11-02  
Scope: offline Group D only; no Phase 24B, deployment, migration, or connected service work

## 1. Executive summary

Group D addresses the two exact Phase 24A.11 findings assigned to this milestone:

- **A11-M07** — the active administrator patient-create screen called the unregistered `POST /api/users/patients` operation.
- **A11-M08** — confirmed read-modify-save and sequential multi-write patterns in care plans, exercise assignments/progress, and the general appointment PATCH could lose concurrent changes or commit only part of a clinical mutation.

The unsupported administrator onboarding workflow was removed from active routing and launch controls. No patient-creation endpoint was invented because the repository does not establish initial-credential, activation, email-ownership, or invitation policy for administrator-created patients. The existing public patient registration transaction remains unchanged. The orphan component remains preserved but is unreachable.

Mutable care plans, exercise assignments, and appointments now expose legacy-compatible revisions. Their affected write APIs require an expected revision, use a conditional atomic update, increment the revision in the same operation, and return HTTP 409 for stale data. Care-plan primary/audit/notification writes and exercise-progress/assignment transitions use MongoDB transactions with no non-transactional fallback. Optional home-address persistence remains a separate preference write, but the existing booking idempotency path now retries and repairs it safely.

Fresh final offline verification passed **1,094 backend tests with 3 connected-only skips**, **165 frontend tests**, lint, production build, the 73-asset bundle budget, Python compilation, lock tests, `pip check`, offline npm audit, secret scanning, and whitespace checks. Mocked transaction/concurrency tests demonstrate application behavior; they do not establish replica-set transaction support.

**Group D result: PASS WITH CONDITIONS.** A11-M07 active contract drift is resolved, but clinic onboarding policy remains required before administrator patient creation can be enabled. A11-M08 is remediated in offline code and deterministic tests, while connected replica-set transaction and race verification remains blocked. This result does not authorize demonstration, staging, production, or Phase 24B.

## 2. Initial Git state

Verified before Group D edits:

| Item | Initial value |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Tracked modified paths | 101 |
| Untracked paths | 84 |
| Total dirty paths | 185 |

The historical Group C values matched the actual repository exactly. Existing Group A, B, and C implementation, tests, and reports were present in the dirty tree and were preserved. No reset, clean, stash, branch switch, commit, push, dependency change, or environment-file edit was performed.

## 3. Finding source and affected endpoints

The Phase 24A.11 register is the source of truth.

| Finding | Affected active operation at audit time | Group D disposition |
|---|---|---|
| A11-M07 | `/admin/patients-create` → `POST /api/users/patients` | Unsupported active route and launch controls removed; policy required before re-enabling |
| A11-M08 | `POST /api/care-plans`; `PATCH /api/care-plans/{id}`; stage and goal PATCH; assignment PATCH; `POST /api/exercise-progress`; general appointment PATCH; optional saved-address follow-up | Revision CAS, required expected revisions, fail-closed transactions, or idempotent compensating repair according to operation |

The review also traced neighboring appointment payment, cancellation, and home-visit assignment writes because they can change a revision observed by the general appointment editor. They now increment the appointment revision, but their established conditional status/ownership semantics were not redesigned.

## 4. Administrator patient-creation contract analysis

### Trace

The active frontend route lazy-loaded `frontend/src/pages/admin/PatientsCreate.jsx`. That form submitted name, email, password, phone, gender, and address data through Axios to `POST /users/patients`, expecting a created patient response and displaying the returned error detail on failure.

`backend/app/api/users.py` has no POST `/patients` handler. Inspection of the registered routers and route tests found no differently named administrator operation with equivalent semantics. Public registration uses the account-registration transaction and creates a patient account/profile under self-service behavior. Staff creation is administrator-only but deliberately excludes the patient role. Neither is a safe substitute for administrator patient onboarding.

### Decision

No backend endpoint was added and no existing endpoint was reused. The active `PatientsCreate` import/route was removed from `frontend/src/App.jsx`; the dashboard header no longer launches it; Quick Actions now links to the supported patient directory. A frontend contract test proves that the unsupported route and launch text are absent. A backend test proves the deliberate absence of POST `/patients`.

This is the smallest supported repair because the repository does not determine:

- how an administrator establishes initial credentials;
- whether email ownership must be verified;
- whether the account begins active;
- whether an invitation is required;
- what duplicate-account disclosure is permitted in a staff-assisted flow;
- what onboarding/audit event the clinic requires.

These remain **POLICY DECISION REQUIRED**. Re-enabling the screen before those decisions would recreate A11-M07. The dormant component is not evidence of an active supported workflow.

### Security review

The repair adds no role escalation, credential flow, password handling, email delivery, duplicate-account signal, or new patient-data response. Existing transactional public registration, administrator staff creation, login compatibility, password policy, and patient profile behavior are unchanged. Because no new creation endpoint exists, endpoint-specific password hashing and rollback claims are not applicable.

## 5. Mutation matrix and original failure modes

| Operation | Original writes / risk | Required consistency | Implemented boundary |
|---|---|---|---|
| Care-plan creation | plan insert, then mandatory history insert; history failure left an unaudited plan | Multi-document all-or-nothing | Plan and initial history in one fail-closed transaction |
| General care-plan update | unversioned embedded save; status history/notification could precede failed save | Optimistic concurrency; transaction when side effects exist | Patient/therapist/revision CAS; status + history + persisted notification in one transaction |
| Stage status update | embedded read-modify-save, then history and notification | Optimistic concurrency plus transaction | Plan revision CAS and history/notification in one transaction |
| Goal progress update | embedded read-modify-save, then history and optional notification | Optimistic concurrency plus transaction | Plan revision CAS and history/optional notification in one transaction |
| Exercise assignment PATCH | unversioned read-modify-save | Single-document optimistic concurrency | Patient/revision CAS and atomic revision increment |
| Exercise progress POST | progress insert, then one or two assignment saves | Multi-document all-or-nothing plus stale/retry protection | Assignment patient/status/revision CAS and progress insert in one transaction; progress has a stable ID per callback |
| General appointment PATCH | unversioned model save could overwrite newer status/billing/slot claim | Single-document optimistic concurrency | Patient/doctor/revision CAS with atomic `$set`/`$unset` and increment; duplicate-slot behavior retained |
| Appointment payment, cancellation, and clinician allocation writes | Existing atomic predicates, but external writes could leave a displayed revision current when it was not | Preserve existing atomic mechanisms and version visibility | Existing predicates retained; successful writes increment revision; reconciliation response refetches after a second revision change |
| Optional home-visit saved address | booking insert succeeded before preference save; retry returned existing booking without repairing address | Compensating, idempotent preference update | Initial and existing-submission paths idempotently persist the requested address; retry repairs failure without duplicate booking |

Laboratory and report mutations were assessed from the finding register but were not part of A11-M08's affected operation set. Their established conditional/transaction/quarantine controls were not changed.

## 6. Versioning, transaction, and atomic-update strategy

`Appointment`, `CarePlan`, and `ExerciseAssignment` now have `revision: int = 0`. Mutation response schemas return the current revision. Affected request schemas require a non-negative expected revision.

The repository filters include immutable ownership/assignment context in addition to identity and revision:

- appointment: `_id`, `patient_id`, `doctor_id`, revision;
- care plan: `_id`, `patient_id`, `therapist_id`, revision;
- assignment: `_id`, `patient_id`, revision;
- progress transition: assignment `_id`, `patient_id`, expected status, revision.

The matching write applies the clinical fields and `$inc: {revision: 1}` together. No match raises a domain conflict, which the API maps to a consistent 409 reload/review response. A stale mutation is not automatically replayed with old data.

Care-plan create/status/stage/goal side effects and progress/assignment changes call `with_transaction`. If session or transaction support is unavailable, the error propagates before a non-transactional fallback can run. Notifications in these care-plan flows are persisted notification documents in the same transaction, not external messages.

Transactions are appropriate here because the audit/progress document has no valid independent meaning when its primary clinical state transition fails. Pure single-document changes use CAS without a transaction.

## 7. Legacy document compatibility

No migration was run or required for safe offline compatibility. Expected revision `0` matches either explicit `revision: 0` or a missing revision field. The first successful mutation materializes revision `1` atomically. Later requests require an exact revision. A missing legacy field therefore does not permit arbitrary overwrites; it gets exactly one revision-zero transition winner.

No database record, collection, or index was inspected or changed. A future migration may choose to backfill revision zero for observability, but it is not required for correctness and was not authorized here.

## 8. Authorization, ownership, and status behavior

Existing FastAPI dependencies and service authorization checks remain in force:

- care-plan doctor writes still require assigned-patient access and ownership by the resolved doctor profile; administrators retain their existing scope;
- exercise assignment doctor writes still require assigned-patient access, and patient assignment mutations remain status-only and owner-scoped;
- progress still derives the patient profile from the authenticated user and verifies assignment ownership;
- appointment doctor writes still require the resolved assigned doctor and reject pending home-visit capacity reservations; administrators retain the existing route permission;
- billing restrictions, payment-verification checks, slot uniqueness, terminal states, stage/goal transition rules, and immutable patient/therapist relationships are preserved.

Repository CAS predicates add a second ownership/assignment check at the write boundary. They do not replace service authorization and cannot widen access.

## 9. Frontend compatibility and stale-form behavior

Only direct consumers were changed:

- care-plan status, stage, goal, and full-form PATCH requests send `selectedCarePlan.revision`;
- exercise assignment edits retain the loaded revision and send it on save;
- patient progress submissions carry the assignment revision returned by the details endpoint;
- appointment cards pass the loaded revision through the administrator/doctor status mutation;
- 409 responses show a reload/review instruction and invalidate or refetch the relevant query;
- care-plan and assignment forms do not discard their local inputs on conflict, allowing the clinician to review before retrying.

No automatic stale overwrite or broad state-management refactor was introduced.

## 10. Regression and concurrency evidence

The new backend file `backend/tests/test_phase24a12_group_d_multiwrite_integrity.py` contains 18 deterministic cases covering:

- required revision fields on all changed mutation schemas;
- missing-field legacy revision-zero compatibility and exact later matching;
- stale appointment and assignment rejection;
- two appointment writers using the same revision: exactly one winner;
- two care-plan writers using the same revision: exactly one winner, one history and one notification;
- two progress retries using the same assignment revision: exactly one progress insert;
- shared transaction session for assignment transition and progress insert;
- fail-closed behavior when transaction sessions are unavailable;
- care-plan failure before the primary write when transactions are unavailable;
- explicit appointment HTTP 409 mapping;
- idempotent saved-address repair;
- deliberate absence of an administrator patient-create backend contract.

These tests use mocked/isolated repository behavior. They verify application filters, transaction participation, conflict mapping, and side-effect counts; they are not real MongoDB transaction or rollback verification.

The new frontend file `frontend/tests/phase24a12-group-d-integrity.test.mjs` verifies inactive patient creation, revision propagation, 409 handling, preserved review instructions, and appointment revision handoff. Existing care-plan, exercise, appointment, authorization, API contract, payment, and payload-limit tests were updated only where the new required revision contract changed their inputs or persistence seam.

## 11. Fresh verification results

All backend commands used the existing locked Python 3.13 environment, a cleared environment, synthetic secrets, `ENVIRONMENT=test`, an intentionally unreachable loopback MongoDB port, disabled payment/provider/reconciliation/scanner startup, disabled automatic pytest plugins, explicit `pytest_asyncio`, no cache provider, and no connected-test opt-in.

| Verification | Fresh result |
|---|---:|
| New Group D backend file | **18 passed** |
| Affected care-plan/exercise/progress plus initial Group D selection | **71 passed** before the final three deterministic race cases were added; all are included in the final full pass |
| API/payment/response/payload compatibility selection | **198 passed** |
| Final complete backend with local fake-scanner socket permission | **1,094 passed, 3 connected-only skipped**, 1 existing plugin warning |
| Complete backend in restricted sandbox before final race additions | **1,080 passed, 11 AF_UNIX bind failures, 3 skipped**; all failures occurred at local socket bind before application assertions |
| Fake ClamAV file with temporary local Unix-socket permission | **12 passed** |
| Complete frontend | **165 passed** |
| New Group D frontend file | **4 passed** |
| Frontend lint | **PASS** |
| Vite production build | **PASS**, Vite 8.3.5, 1,837 modules |
| Asset budget | **73 JS/CSS assets**, zero violations |
| Python syntax | **170 Python files compiled**, zero failures |
| Dependency-lock tests | **2 passed** |
| `pip check` | **No broken requirements found** |
| Offline `npm audit` | **0 vulnerabilities found**; cache freshness is not connected-verified |
| Redacted Gitleaks current-tree scan | **6 existing synthetic fixture findings**, zero in new Group D files or Group D-added lines |
| `git diff --check` | **PASS** |

The three skips are the unchanged guarded connected account-registration, distributed-rate-limit, and report-transaction MongoDB contracts. The warning is the existing `pytest_asyncio` assertion-rewrite warning. The 11 restricted-sandbox failures are the known AF_UNIX permission condition; the unchanged scanner tests pass when temporary local socket binding is allowed.

## 12. Files changed or created for Group D

Core implementation:

- `backend/app/models/{appointment,care_plan,exercise}.py`
- `backend/app/schemas/{appointment,care_plan,exercise}.py`
- `backend/app/repositories/{appointment_repository,care_plan_repository,exercise_repository}.py`
- `backend/app/services/{appointment_service,care_plan_service,exercise_service,home_visit_service,payment_service}.py`
- `backend/app/api/{care_plans,exercises}.py`
- `frontend/src/App.jsx`
- `frontend/src/components/features/AppointmentCard.jsx`
- `frontend/src/pages/admin/{AdminDashboard,CarePlanManagement,ExerciseAssignmentManagement}.jsx`
- `frontend/src/pages/admin/dashboard/{DashboardHeader,QuickActions}.jsx`
- `frontend/src/pages/doctor/DoctorDashboard.jsx`
- `frontend/src/pages/patient/PatientExercises.jsx`

Tests and report:

- `backend/tests/test_phase24a12_group_d_multiwrite_integrity.py`
- `frontend/tests/phase24a12-group-d-integrity.test.mjs`
- compatibility updates in `test_api_contract.py`, `test_care_plans.py`, `test_clinical_response_consistency.py`, `test_exercise_progress.py`, `test_exercises.py`, `test_phase24a12_group_b_payload_protection.py`, and `test_razorpay_payments.py`
- this report

Several implementation files already contained uncommitted Group A/B/C and earlier milestone work. Their full working-tree diff is not attributed to Group D; the existing changes were preserved and Group D edits were made at the specific revision/transaction seams above.

## 13. Remaining decisions, dependencies, and risks

### Policy condition

Administrator-created patient onboarding remains disabled until the clinic decides credentials, invitation/verification, activation, duplicate handling, and audit semantics. The active broken workflow is gone, but administrator onboarding is not implemented.

### Connected integrity condition

The configured production architecture expects transaction-capable MongoDB, but this milestone did not connect to any MongoDB deployment. An approved empty replica set with fictional data must verify transaction commit/rollback, callback retries, two-client races, and legacy missing-revision documents. Transaction failure deliberately remains fail closed.

### Home-address condition

Saved address is a convenience preference, not booking authority. It remains a compensating idempotent follow-up rather than a cross-document transaction. Booking idempotency prevents a duplicate booking, and retry repairs the preference. A clinic decision would be needed to make address persistence a prerequisite for booking success.

### Existing open gates

The eight connected release gates remain blocked. Group B's provider/proxy 256 KiB ceiling verification and clinical text-limit approval remain open. Group C's connected explain/index/latency verification remains open. No result here establishes deployed transaction capability, production index state, provider behavior, real scanner behavior, or staging readiness.

## 14. Finding status and completion recommendation

Final repository state after documentation:

| Item | Final value |
|---|---|
| Branch / HEAD | `codex/physiocare-integration-2026-10-31` / `5eaced696a156ca74233fd04252fea52345d8af8` |
| Ahead / behind upstream | `0 / 0` |
| Tracked modified paths | 112 |
| Untracked paths | 87 |
| Total dirty paths | 199 |

The increase from the initial state includes Group D implementation/test/report paths plus edits to already-dirty shared files. All changes remain uncommitted.

| Finding | Updated status |
|---|---|
| A11-M07 | **Resolved for the active product surface with condition**: no routed or launched administrator workflow calls the missing API; onboarding remains POLICY DECISION REQUIRED before any re-enable |
| A11-M08 | **Offline remediation complete with connected condition**: affected writes use CAS, fail-closed transaction, existing conditional atomic update, or idempotent compensating repair; real replica-set verification remains blocked |

**Group D: PASS WITH CONDITIONS.**

Phase 24A.12 Groups A through D are now complete at their separately reported offline statuses. The next milestone should be an explicit independent Group D review, not Phase 24B. Phase 24B, all connected release gates, client demonstration, staging, and production remain blocked pending separate authorization and evidence.

No external service, protected database, payment provider, real ClamAV daemon, protected storage, migration, deployment, commit, or push was used.
