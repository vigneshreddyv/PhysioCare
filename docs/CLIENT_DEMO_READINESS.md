# PhysioCare Connected Demo Readiness

Status date: 2026-10-25 (Asia/Kolkata)

This checkpoint distinguishes connected local application flows from mock previews, informational pages, and planned work. The delivery target is a client-review demo before 2026-10-31, not a production launch or Play Store release.

## Connected and verified locally

| Journey | Current status | Evidence in source |
| --- | --- | --- |
| Email/password authentication and role protection | Connected | Cookie sessions, CSRF, refresh rotation, logout/revocation, and server role guards are implemented in `backend/app/services/auth_service.py`, `backend/app/middleware/auth.py`, and `frontend/src/App.jsx`. |
| Patient clinic booking | Connected | Server availability, atomic clinician slot claims, stale-slot conflict handling, Asia/Kolkata timestamps, and the 30-calendar-date window are implemented in the appointment API/service and patient booking page. |
| Patient home-visit booking | Connected demonstration flow | Entitled patients can choose a Nellore address, clinician or no preference, date, time, and final confirmation. Clinic and home visits share clinician capacity. Demonstration schedules remain configuration, not verified operating hours. |
| Administrator allocation for no-preference home visits | Connected | A no-preference booking reserves eligible clinician capacity atomically; the administrator can assign or reassign while failed transfers preserve the prior claim. |
| Administrator clinician schedules | Connected and contract-tested | Administrators can save weekly clinic/home blocks and date exceptions as a draft, preview 30-minute slots inside the 30-date window, and publish deliberately. Clinic and home blocks cannot overlap; publication rejects drafts that exclude existing active appointments. Unpublished drafts never affect patient availability. |
| Patient appointment history | Connected | Upcoming, completed, and cancelled clinic/home visits are separated. Clinic self-cancellation follows the existing 24-hour rule; the UI does not invent a home-visit cancellation policy. |
| Assigned doctor agenda and status updates | Connected but narrower than the demo target | Doctors receive only assigned appointments and can update their clinical status. Pending internal capacity holds are excluded. |
| Assigned doctor patient directory and history | Connected and contract-tested | Doctors see only patients linked to their assigned appointments. A dedicated doctor-only history route returns minimum patient fields, that doctor’s non-pending appointment timeline, and administrator-published laboratory reports. Missing and unassigned records use the same non-disclosing response. |
| Patient laboratory request and administrator coordination | Connected | Patients can submit idempotent clinic/home-collection requests, see their own requests, and withdraw eligible requests. Administrators can approve coordination, decline, and assign an approved request to an active Laboratorian. |
| Laboratorian finalized-report upload and administrator publication | Connected and isolated-test verified | Laboratorian is an administrator-managed role. Assigned Laboratorians receive minimum required order/patient fields and can upload or replace a private finalized PDF. Only an administrator can administratively publish that exact file, and publication is recorded in the request audit history. Cross-order access is rejected. |
| Patient and assigned-doctor released-report views | Connected and isolated-test verified | APIs and UI return only administratively published reports owned by the patient or belonging to a doctor’s assigned patients. Publication is a workflow action and is explicitly not medical validation. |

Fresh checkpoint verification: 95 backend contract/security tests, 32 frontend contract tests, frontend lint, and a fresh exact-lock production build passed. Schedule coverage includes admin-only routes, 30-minute alignment, cross-mode overlap rejection, date exceptions/closures, published mode-specific slots, existing-appointment publication conflicts, and clinic/home booking regression. Mock visual harnesses remain separate from live authenticated behavior.

PDF limitation: protected upload, administrator publication, and role-scoped report visibility passed through isolated API/UI checks. Automated browser control could not complete native filename selection, and it could not capture the rendered contents of a `blob:` PDF tab. A synthetic check confirmed that the corrected synchronous viewer opens a second blob tab and fetches the PDF, but filename selection and visible page rendering remain manual browser checks. Do not describe those two checks as verified.

## Partial, informational, or absent

- **Connected laboratory rehearsal:** a disposable four-role rehearsal verified patient request, administrator assignment, Laboratorian protected upload through the API, administrator publication, and patient/assigned-doctor visibility. Browser-controlled native file selection and visual inspection of rendered PDF page contents remain unverified. The disposable database, files, sessions, and credentials were removed after the run.
- **Payment gateway:** no provider SDK/API, payment-attempt model, server verification, authenticated webhook, or idempotent payment state machine exists. The Billing screen changes an appointment billing-status field only; it does not process or verify money.
- **SMS/WhatsApp verification:** presentation exists, but no provider is connected. Email/password is the working authentication path.
- **Demo authentication:** no persistent fictional Laboratorian account is provisioned. The disposable rehearsal accounts and credentials were removed, so the current lab screenshots remain isolated mock previews rather than reusable demo logins.
- **Native Android/PWA packaging:** the repository is a React/Vite mobile web application. There is no Capacitor/Cordova project, Android project, web app manifest, or service worker. The `apps/*/package.json` portal placeholders are empty.
- **Operational home routing:** clinician slot conflicts are protected, but no approved travel-time or routing buffer exists. Published home hours therefore express declared availability, not proof that adjacent home visits are geographically feasible.

## Recommended delivery path

Use the responsive mobile web app as the primary client demo. It already exercises the real local API, database, session, role, booking, and allocation paths. An installable Android wrapper is a stretch task only after the connected browser demo passes its rehearsal. The Mac has `adb`, but the repository has no native wrapper or Gradle project, so an APK adds packaging, network-policy, device, lifecycle, and regression work without improving the core clinical demo.

## Dated critical path through 2026-10-31

The earlier 3–4 day estimate is a preferred target, not a promise. This sequence starts from the verified 2026-10-24 checkpoint, keeps 2026-10-31 as the latest client-demo target, and preserves time for a rehearsal rather than treating the deadline as a feature-completion day.

### 2026-10-24 — verified foundation

- Laboratorian is administrator-managed only.
- Server-enforced order assignment, assignment audit fields, administrator allocation, minimum-field assigned queue, and private finalized-report upload are implemented.
- Patient-own and assigned-doctor released-report read paths are implemented.
- Cross-patient, cross-Laboratorian, unauthorized-role, file-type/size, private-permission, traversal, and unpublished-report regression checks pass.

### 2026-10-25 — administrator publication workflow

- The approved rule is implemented: the assigned Laboratorian uploads the finalized PDF and only an administrator administratively publishes it. Administrative publication is a workflow action, not medical validation or a replacement for qualified laboratory sign-off.
- Publication is auditable, idempotent, bound to the exact reviewed storage key, and rejects changed or missing files. Laboratorian, patient, and doctor roles cannot invoke publication.
- The remaining connected-demo step is authorization to provision one protected fictional Laboratorian account and a safe fictional patient authentication path, then run the real local patient → administrator → Laboratorian → administrator publication → patient/assigned-doctor journey.

### 2026-10-26 — doctor history and payment decision

- The assigned-doctor longitudinal patient-history view is implemented without broadening access beyond assigned patients; guarded mobile and desktop states are visually verified with fictional data.
- If a payment provider and test merchant credentials are supplied: begin provider test mode with server-created payment attempts, authenticated webhook verification, idempotency, and booking/payment reconciliation.
- If provider inputs are absent: use only an explicitly labelled local payment simulation for the walkthrough. It must not be described as a sandbox integration and must not record a live charge.

### 2026-10-27 — connected cross-role rehearsal

- Rehearse patient clinic/home booking, admin allocation, assigned doctor status/history, Laboratorian assigned-order/report preparation, patient released-report access, and payment outcome handling.
- Exercise negative role/object access, repeated submissions, stale slots, logout/back navigation, cold restart, mobile widths, loading/error/empty states, and the 30-date/Nellore rules.
- Save a deterministic fictional-data demo script and evidence. No real patient data or charges.

### 2026-10-28 to 2026-10-29 — defect correction and repeat rehearsal

- Fix only defects found in the connected rehearsal, rerun affected role/security tests, and repeat the cold-start walkthrough.
- Freeze the demonstration dataset and keep every fictional state reproducible.

### 2026-10-30 — client-ready rehearsal

- Run the complete demo from clean startup with the actual intended device/browser presentation.
- Confirm every screen’s connected versus simulated status and save a concise presenter checklist.

### 2026-10-31 — contingency, not planned feature work

- Fix integration defects found during rehearsal.
- Package an Android wrapper only if the mobile-web demo is already stable, the Android toolchain and app identifier/signing/network configuration are ready, and the client specifically requires an APK. Do not pursue Play Store publishing for this milestone.

## Inputs required from the client

1. **Payment path:** provider name plus test merchant credentials/webhook secret, or approval to use a clearly identified local payment simulation for the client demo.
2. **Demo charge amount and timing:** a fictional test amount and whether payment occurs before or after booking confirmation. No clinic price should be invented.
3. **Fictional Laboratorian account:** approval to create one local-only demo staff account using protected local credentials. No password belongs in documentation or chat.

## Demo acceptance boundary

Static service cards, disabled verification screens, mock-only visual harnesses, and manually edited billing labels do not count as connected demo flows. A flow counts only when it crosses the protected UI/API boundary, enforces object ownership and role permissions, persists fictional state, handles retry/error paths, and passes its regression checks.

## Current review-only laboratory previews

- Patient laboratory view: `http://127.0.0.1:5174/lab-workflow-qa.html?role=patient`
- Laboratorian assigned-order view: `http://127.0.0.1:5174/lab-workflow-qa.html?role=laboratorian`
- Administrator publication view: `http://127.0.0.1:5174/lab-workflow-qa.html?role=admin`
- Patient released-report view: `http://127.0.0.1:5174/lab-workflow-qa.html?role=patient&state=released`
- Doctor assigned-patient history: `http://127.0.0.1:5174/doctor-patient-history-qa.html?state=history`
- Administrator clinician schedules: `http://127.0.0.1:5174/qa/clinician-schedule-qa.html?state=draft`

These are guarded fictional-data visual previews with mutations disabled. They demonstrate the current mobile presentation only; they are not evidence of live authentication, persisted assignment, upload, publication, or report delivery. The preview listener and all four views were visually verified at a 390 px mobile viewport on 2026-10-25.
