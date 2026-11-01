# Phase 15 browser workflow validation

Assessment: 2026-11-01. **Result: NOT RUN.** No approved isolated staging frontend/API or fictional connected dataset exists. Unit/contract tests and a production build are not browser evidence.

## Execution matrix for approved staging

| Role | Positive paths | Negative and UX checks |
|---|---|---|
| Patient | Register/login/logout; own profile; doctor discovery; published appointment booking/cancellation; care/exercise progress; demo laboratory request/withdrawal and released report; own clinical report; notifications; enabled home-visit flow | Invalid fields, missing/foreign IDs, stale slots, payment-disabled state, loading/retry/error states, mobile viewport, keyboard-only focus and screen-reader labels |
| Clinician | Login; assigned directory/history; own appointments; care-plan and exercise mutations; authorized report upload/review after scanner approval | Unassigned/missing/malformed patient/booking IDs, stale updates, rejected upload, no content leak, mobile and keyboard access |
| Admin/lab staff | Staff/patient management, draft/publish schedules, appointment/laboratory review, finalized upload/publication, audit and notifications | Role segregation, stale revisions, invalid catalogue/records, unpublished file access, errors/retry, responsive tables/forms and accessible dialogs |

For every supported journey record browser/device/viewport, route, fictional account, API request ID, expected/actual status, visible state, focus order, accessibility observations and cleanup. Use real browser sessions against the approved staging target, not mocks. Compare missing and unauthorized direct objects for status/body and visible content. Test actual cookie flags, CSRF, proxy and scanner behavior. Capture redacted screenshots only; no secrets, patient content or tokens.

Unsupported or gated behavior must be reported honestly: **first-class rescheduling is not implemented**; the active laboratory flow is a demo coordination request, not priced confirmed booking; home-visit travel buffers and coverage policy are incomplete; payments are disabled until separate Test Mode authorization. These are blocked product decisions, not successful journeys.

**Pass criteria:** every required supported journey and negative/accessibility state works on approved staging with zero foreign data exposure and no unapproved transaction. Any failed workflow, missing environment, real data, or rejected PDF becoming downloadable stops the gate. Current result remains **NOT RUN / BLOCKED**.
