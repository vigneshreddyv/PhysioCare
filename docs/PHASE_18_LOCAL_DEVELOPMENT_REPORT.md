# PhysioCare Phase 18 — Local Development Assessment

Assessment date: 2026-11-01. Branch: `codex/physiocare-integration-2026-10-31`; HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`.

**Decision:** Continue local quality work. Phase 17 staging remains planned and unapproved; staging is **BLOCKED** and production readiness is **FAIL**. This is a source and documentation assessment, not a fresh test run or an independent security audit. No P0 defect was confirmed during this review; absence of a confirmed P0 is not a security signoff.

**Post-assessment status (2026-11-01):** The findings and baseline counts below record the initial Phase 18 assessment. The six local findings were subsequently addressed in uncommitted code and reviewed in the [Phase 19 local release verification](PHASE_19_LOCAL_RELEASE_VERIFICATION.md). The current offline baseline is **579 backend passed, 2 connected skipped; 89 frontend passed**, with lint, build, bundle and compilation checks passing. These results do not close connected or operational gates.

| Initial finding | Current local status | Remaining validation |
| --- | --- | --- |
| Logout failure handling | Implemented: private state is hidden before revocation; failed revocation is not reported as success and has a retry. | Browser storage-unavailable behavior deserves a robustness follow-up; connected browser/session flow remains unverified. |
| Login/profile fetch | Implemented: profile confirmation gates navigation; ambiguous requests use a session-only retry. | Browser end-to-end flow remains unverified. |
| Patient/doctor account creation | Implemented with a shared Mongo transaction session and fail-closed behavior; offline rollback/retry tests pass. | A dedicated connected registration contract is prepared but has **not** been run; its database and index writes require separate approval. |
| Demo schedule fallback | Restricted to explicit local/demo development modes; booking independently rejects unpublished schedules outside those modes. | Connected booking/authorization journey and clinic policy remain open. |
| Clinical repository failures | Invalid IDs are separated from database faults, with offline fault-injection tests. | Connected outage behavior remains unverified. |
| Laboratory partial failures | Request and report sections now load and retry independently, with frontend behavior tests. | Browser accessibility and device-size checks remain open. |

The remaining Phase 18 product decisions are rescheduling, clinic-approved laboratory catalogue/prices, home-visit travel and coverage rules, and email ownership/recovery. The empty `apps/*` placeholders and dense shared UI code remain lower-priority maintenance work. The original assessment is retained below as historical evidence; its original recommended logout task has been completed.

## Scope and evidence

The active client is the React/Vite application under `frontend/`, with patient, doctor, administrator, reception and laboratorian routes in `frontend/src/App.jsx`. `backend/app/main.py` registers FastAPI routers for authentication, appointments, schedules, home visits, laboratory requests, payments, reports, care plans, exercises and notifications. Beanie/Mongo models are reached through service and repository layers. The `apps/*/package.json` files are empty placeholders, not independently runnable portals.

The latest recorded clean offline baseline is the [Phase 16 operational readiness report](PHASE_16_OPERATIONAL_READINESS_REPORT.md): **531 backend tests passed**, **59 frontend tests passed**, frontend lint/build/bundle checks and Python compilation passed, and 48 applicable lock pins matched. These counts predate this report; no tests were rerun for Phase 18. The separately approved local report transaction contract passed once in Phase 15. Browser end-to-end verification is [NOT RUN](PHASE_15_BROWSER_TEST_RESULTS.md). No staging, scanner or payment-provider validation is implied by local test results.

Three pre-existing worktree changes were present before this assessment: modified `backend/RAZORPAY_TEST_MODE.md`, and untracked `docs/PHASE_16_OPERATIONAL_READINESS_REPORT.md` and `docs/PHASE_17_STAGING_INFRASTRUCTURE_PLAN.md`. They must be preserved.

## Workflow status

| Workflow | Implemented locally | Incomplete or unverified |
| --- | --- | --- |
| Authentication | Email/password, cookie sessions, CSRF, role gates and throttling; public registration uses enumeration-neutral responses. | Phone/SMS/WhatsApp is an explicit preview (`frontend/src/pages/common/PhoneVerification.jsx`); email ownership/recovery policy remains open. Login and logout failure handling have defects below. |
| Patient and therapist | Patient booking/history, care plans, exercises and reports; assigned clinician views and mutations have scoped authorization tests. | No first-class appointment reschedule; clinic-approved policies and connected role-negative browser journeys remain open. |
| Booking and home visits | Availability, published clinician schedules, cancellations and home-visit slot claims. | Unpublished schedules fall back to demo slots; travel buffers and operational coverage rules need owner decisions and implementation. |
| Payments | Razorpay Test Mode code, webhook verification/deduplication and offline tests exist. | No approved provider-connected Test Mode validation; reconciliation stays disabled in local development. Live payment readiness is open. |
| Laboratory and reports | Demo-catalogue request/review flow, private report handling, quarantine and release controls, and a local transaction contract. | Catalogue/prices/collection capacity are not clinic-approved; no checkout or confirmed collection. Real scanner operation and connected workflow validation remain open. |

See [project requirements](PROJECT_REQUIREMENTS_CHECKLIST.md), [clinic configuration](PHASE_13_CLINIC_CONFIGURATION.md), and [Phase 16 readiness](PHASE_16_OPERATIONAL_READINESS_REPORT.md) for the pre-existing product and operational decisions.

## Confirmed local findings

| Priority | Finding and evidence | Impact and focused acceptance |
| --- | --- | --- |
| P1 | `frontend/src/context/AuthContext.jsx:16-25,50-64` ignores a false result from `/auth/me` and returns `true` after `/auth/login`; `frontend/src/pages/common/EmailLogin.jsx:32-42` then navigates. | A successful login POST followed by failed profile fetch appears successful with no user profile. Add a rendered/provider-level failure test; login should report an incomplete sign-in and avoid protected navigation. |
| P1 | `frontend/src/context/AuthContext.jsx:90-98` clears client state in `finally` even if `/auth/logout` fails. `backend/app/api/auth.py:137-154` revokes the session and clears cookies only after checks succeed. | The UI can appear signed out while the server session/cookies remain valid. Define a privacy-safe, explicit failed-logout state and retry path; test success, network error and rejected revocation without weakening CSRF. |
| P1 | `backend/app/services/auth_service.py:123-151` creates `User` and then `Patient`/`Doctor` in separate writes with no transaction or compensation. | A profile insert failure can leave a user without its required profile, and retry can hit duplicate-email handling. Add failure-injection and retry tests; make creation atomic or safely recoverable. |
| P1 | `backend/app/services/clinician_schedule_service.py:120-147` returns and validates demonstration slots when no schedule is published, with no environment gate. | A live booking can use demo availability if clinic schedules are absent. Preserve explicit local demo behavior, but require published schedules before non-demo booking; add negative configuration/booking tests. |
| P2 | `backend/app/repositories/report_repository.py:40-45`, `care_plan_repository.py:12-16` and several `exercise_repository.py` lookups/lists catch every exception and return `None`/`[]`. | A database fault can look like a missing clinical object or empty list. Catch invalid-ID parsing separately and let database failures surface through safe server errors; test both paths. |
| P2 | `frontend/src/pages/patient/LaboratoryRequests.jsx:26-28,66` treats an error in requests, released reports or home-visit context as a failure of the whole page. | One ancillary query can hide healthy lab request data and the request form. Render independent sections and retry controls; test partial failures. |

These are code-path findings. They were not reproduced in a browser or connected environment during this assessment. The schedule and account-creation risks need focused tests before a fix is treated as verified.

## UI, API and test-quality assessment

- The active frontend has form validation, loading/error states, responsive CSS breakpoints and focus/reduced-motion rules. This review found no evidence of completed interactive browser, keyboard, screen-reader or device-size validation. Do not infer accessibility or responsive quality from CSS and source inspection alone.
- The 59 frontend tests in `frontend/tests/*.test.mjs` are largely source-contract checks using text/regular expressions, plus pure utility tests. They do not render the auth provider or exercise failed network flows. Add focused behavior tests for changed workflows, then a small fictional-data browser smoke suite when an approved environment exists.
- Backend tests cover many authorization and contract paths, and the report transaction contract was separately validated against the approved local replica set. Gaps relevant to this backlog are account-create rollback, database-fault versus not-found semantics, and no-published-schedule rejection outside demo mode. Connected multi-worker/proxy and scanner checks remain operational gates.
- API authorization and object ownership should remain enforced server-side. Changes to missing-versus-unauthorized responses must preserve established enumeration-neutral contracts. No endpoint should rely on route protection alone.
- `frontend/src/pages/patient/LaboratoryRequests.jsx` combines several queries, mutations and dense JSX in one component; `frontend/src/index.css` is a large shared stylesheet. Refactor only alongside a behavior change and tests. Empty `apps/*` manifests should be labelled or retired after confirming repository intent.

## Prioritized local development backlog

| Priority | Work item | Completion evidence |
| --- | --- | --- |
| P0 — critical | No confirmed P0 from this bounded source assessment. | Reassess whenever focused tests or review reveals cross-patient access, data loss or active session exposure. |
| P1 — essential | Correct logout failure semantics first, then login/profile-fetch success semantics. | UI behavior tests for success and failure; preserved CSRF/session revocation; no false success state. |
| P1 — essential | Make account plus role-profile creation atomic or recoverable. | Forced second-write failure leaves no orphan account; retry succeeds safely; duplicate handling remains enumeration-neutral where public. |
| P1 — essential | Gate demo schedule fallback to approved local/demo modes. | Non-demo booking without a published clinician schedule fails closed; explicit local demo and published-schedule flows still pass. |
| P1 — product | Specify rescheduling, approved laboratory catalogue/prices, home-visit travel rules and email ownership/recovery with the clinic owner before implementing those flows. | Signed-off behavior, authorization rules and negative test cases. |
| P2 — reliability | Distinguish malformed IDs from DB outages in clinical repositories; isolate lab page query failures. | Focused fault-injection tests and section-level frontend behavior tests. |
| P2 — usability | Add rendered frontend workflow tests and, when separately approved, fictional-data browser/keyboard/mobile smoke checks. | Tests cover network errors, validation, navigation and responsive interaction rather than source text alone. |
| P3 — polish | Clarify/remove empty `apps/*` placeholders and break up dense lab page/style code as touched. | Documented active app path and unchanged behavior after refactor. |

## Original recommended next task (completed locally)

Approve one focused **P1 logout failure-handling** implementation. First specify the user-visible state for failed server revocation, then add behavior tests that simulate failed `/auth/logout` and successful revocation. Keep sensitive client data hidden after an attempted logout, clearly state when server sign-out is unconfirmed, and provide a safe retry. Verify backend session/CSRF contracts remain intact. Run focused frontend tests, lint and build, plus any relevant backend auth tests. Review this one change before starting the login, account creation or schedule items.

This assessment authorizes no implementation, commit, push, external connection, staging provisioning or deployment. Phase 17 staging ownership/inventory remains unapproved; the real scanner, connected staging checks, clinic policy decisions and independent review remain release blockers. **Staging: BLOCKED. Production: FAIL.**
