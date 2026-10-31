# PhysioCare Product Requirements and Acceptance Checklist

This document records the client-approved decisions that must remain consistent as PhysioCare is developed page by page. It is an acceptance checklist, not evidence that every item is production-ready.

## Product and design direction

- PhysioCare is the mobile app for one Nellore-based care provider. It is not a multitenant SaaS product and must not expose tenant or marketplace concepts.
- Mobile application experience is the primary deliverable; the public website remains available separately.
- Preserve existing working features unless a material workflow change is explicitly approved.
- Review and improve one page at a time against supplied references before rolling a visual system across the app.
- Use a restrained, production-quality interface: clear hierarchy, consistent typography and spacing, readable states, touch-friendly controls, keyboard focus, reduced-motion support, and responsive mobile and desktop layouts.
- Keep authenticated workflows task-focused. Do not place public-site navigation, oversized marketing heroes, internal implementation notes, QA labels, server diagnostics, provider setup details, or payment configuration commentary in patient-facing screens.
- Copy reference interaction patterns and information hierarchy only; do not copy third-party branding, people, credentials, photos, clinical claims, prices, policies, or assets.

## Booking and service decisions

- Clinic and home-visit bookings use Asia/Kolkata for dates and times.
- New clinic and home-visit bookings are limited to a configurable rolling 30-calendar-date window: the current clinic date plus the following 29 dates, inclusive. Published clinician and service schedules may narrow this window further.
- Patients may cancel clinic appointments online until exactly 24 hours before the appointment. No automatic cancellation fee is configured.
- Home visits are available in Nellore only. Server-side validation remains authoritative; location permission is optional and must not imply verified serviceability.
- Home visits are confirmed only after the patient uses the final booking action. Merely choosing a highlighted slot does not create a booking.
- Home and clinic appointments share clinician slot capacity, so one clinician cannot be booked for both at the same time.
- Patients may choose a preferred home-visit physiotherapist or select “No preference.”
- A no-preference booking confirms the patient’s date and time only when an eligible clinician’s capacity has been reserved atomically. The patient sees “Doctor assignment pending,” not the internal capacity holder.
- An administrator may assign or reassign the clinician for a confirmed home visit. A failed transfer keeps the existing capacity reservation. Receptionists cannot perform this action.
- Existing legacy home-visit requests remain legacy records and are never silently converted to confirmed appointments.
- The patient mobile bottom navigation does not include a separate Book item; clinic and home booking remain accessible from the home and services journeys.

## Role and object access

| Role | Intended access | Explicit exclusions |
| --- | --- | --- |
| Patient | Own profile, own bookings, own requests, and released reports | Other patients, staff tools, assignment controls, unreleased reports |
| Doctor | Appointments and minimum necessary treatment details for assigned patients | All-patient directory, pending internal capacity holds, unrelated lab/payment/admin data |
| Receptionist | Appointment operations and minimum patient contact details | Clinical reasons/history, staff/security settings, analytics, subscriptions, payment changes, clinician allocation |
| Laboratorian | Assigned laboratory orders, minimum identity details, and report preparation/upload | Unassigned orders, unrelated clinical notes, payment data, admin/security tools |
| Administrator | Oversight of patients, bookings, clinician allocation, schedules, entitlements, and reports | Plaintext credentials, secret access, or bypassing object authorization |

All permissions must be enforced on the server for each object, not only hidden in the UI. Sensitive administrative actions must be auditable.

## Implemented and freshly tested

- Server-enforced patient ownership for bookings and requests.
- Doctors are limited to assigned appointments and assigned-patient directory data.
- Doctors have a dedicated assigned-patient history view containing only their non-pending appointment timeline and administrator-published laboratory reports. Unassigned and missing patient identifiers return the same non-disclosing response.
- Patients may optionally record their gender in their own profile. Doctor history shows only the recorded value with a “Not recorded” fallback and never infers gender from name or other data. Age is derived from the recorded date of birth in the clinic timezone.
- Doctor report history contains only administrator-published internal PhysioCare laboratory PDFs with recorded test names and finalized/published dates. External historical report upload is not implemented.
- Receptionist views use reduced operational fields and do not include clinical reasons or billing data.
- Public registration creates patient accounts only; staff creation is administrator-managed.
- Cookie-based sessions, CSRF checks, explicit CORS, logout/revocation, and removal of browser-stored bearer tokens.
- Nellore-only home-visit validation and entitlement checks.
- Shared atomic clinician slot claims across clinic and home visits.
- Immediate confirmed home-visit booking after the final action, with idempotent retry and cancellation releasing the slot claim.
- Configurable inclusive 30-date booking window enforced by both availability and booking submission validation.
- Preferred-doctor and no-preference home bookings. No-preference bookings reserve one real eligible clinician internally while exposing assignment-pending state to the patient.
- Administrator-only home-visit clinician assignment/reassignment with atomic slot transfer and an assignment audit record.
- Administrator-only clinician schedules now support separate, non-overlapping weekly clinic and home-visit blocks, date-specific closures or changed hours, draft slot preview, deliberate publication, and revision audit history. Published schedules become authoritative for new bookings; unpublished drafts do not affect patients. Publication is blocked when the draft would exclude an existing active appointment inside the booking window.
- Pending capacity holders are excluded from doctor appointment and assigned-patient views and cannot update the pending booking directly.
- Patient-facing home-visit copy uses concise service language rather than developer or configuration notes.
- Patient appointment management separates upcoming, completed, and cancelled clinic and home visits. No-preference home bookings retain their “Doctor assignment pending” label, clinic cancellation follows the existing server policy, and the patient UI does not silently apply that clinic policy to home visits.
- Laboratorian is available as an administrator-managed staff role. Administrators can assign approved laboratory requests; Laboratorians can see only their assigned orders and upload private finalized PDFs. Only administrators can administratively publish the exact finalized file to the patient and assigned doctors. Publication is audited and explicitly does not provide medical validation.

Current automated verification: 345 backend tests and 58 frontend contract tests pass; the backend suite and frontend lint complete without warnings, and a fresh isolated exact-lock production build passes. CI now enforces per-asset budgets of 450 KiB for JavaScript and 300 KiB for CSS; the current largest assets are 364.5 KiB of JavaScript and 248.4 KiB of CSS. Dependency audits are currently clean. These automated checks did not contact the normal database or a payment provider. Mocked visual previews remain separate from live authenticated workflows.

## Pending implementation or client decisions

- A live connected laboratory rehearsal still requires separately authorized protected fictional accounts. The implemented administrator publication action is administrative workflow control, not qualified laboratory sign-off or clinical validation.
- Client must provide real clinic and home-visit working hours, clinician schedules, home-service eligibility, holidays, travel buffers, capacity rules, and exception handling before launch. Current schedule values are configurable demonstration settings.
- The scheduler prevents a clinician from being double-booked across clinic and home modes, but it does not calculate travel time between home visits. The clinic must approve a travel-buffer policy before home availability can be treated as operationally feasible.
- Client must provide real laboratory catalogue, prices, collection capacity, turnaround rules, and payment provider. Current catalogue/request flow is a demo and does not represent checkout or confirmed collection.
- Razorpay Test Mode order creation, server verification, authenticated/idempotent webhooks, persisted attempts, and captured-payment reconciliation are implemented but have not been exercised against an authorized merchant account in this checkpoint. Merchant access, prices, charge timing, cancellation/refund handling, receipts, settlement review, and which services require payment remain client decisions. Keep payment disabled and do not create credentials or process a payment until those decisions are approved.
- Real SMS and WhatsApp verification providers are not connected. Email/password remains the working authentication path.
- Cancellation fees, exercise programmes, telehealth, clinical messaging, and native app publishing remain outside the current verified phase.
- Any earlier 30–45 working-day estimate is provisional planning input, not a committed delivery deadline.

## Required verification for each reviewed page

- Mobile widths including 390 px, a wider phone layout, and desktop.
- Keyboard order, visible focus, touch targets, text scaling, contrast, and reduced motion.
- Loading, empty, unavailable, validation, network error, stale data, retry, cancellation, repeated action, back/forward, and interrupted-flow behavior.
- Server-side ownership and role-negative tests for every new data operation.
- Truthful distinction between confirmed bookings, pending assignments, legacy requests, unavailable modules, and demonstration configuration.
