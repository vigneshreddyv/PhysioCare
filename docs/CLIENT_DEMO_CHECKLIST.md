# PhysioCare Phase 1 Client Demo Checklist

Use this checklist for a local Phase 1 walkthrough. It demonstrates the current product truthfully; it is not a production-readiness or compliance sign-off.

## Safe demo setup

- Run the frontend, API, and database on loopback only. Do not expose the demo to the public internet.
- Use only clearly fictional demo accounts, names, phone numbers, health reasons, and home addresses.
- Never show or paste passwords, tokens, signing secrets, environment files, or browser storage during the demo.
- Do not enter real patient, clinician, clinic, payment, or home-address data.
- Keep payments unconfigured for this local walkthrough. Test Mode code exists, but do not describe the walkthrough as a Razorpay sandbox transaction, purchase, or paid subscription unless a separately authorized provider rehearsal has actually been completed.
- Before presenting, confirm the API and preview are healthy and use a clean fictional demo dataset.

## Recommended walkthrough

### 1. Public discovery

1. Open the public home page on desktop.
   - Expected: the main patient journey, services, clinic-appointment versus home-request distinction, and clear sign-in/create-account actions are visible.
2. Open the clinician directory and one clinician profile.
   - Expected: search and specialty filters work; the profile shows only approved public fields such as photo, qualifications, experience, specialties, biography, and correctly labelled professional links.
   - Call out: seeded clinician data is fictional. Real photos, qualifications, experience, biographies, and links require client verification.
3. Repeat the public home and clinician view at a phone width.
   - Expected: no horizontal scrolling, readable controls, visible focus states, and touch-sized actions.

### 2. Patient registration and sign-in

1. Create a new fictional patient account.
   - Expected: public registration always creates a patient; it cannot create a doctor, receptionist, or admin.
2. Sign in through the standard login form.
   - Expected: the patient dashboard loads without a token in browser storage; account/session cookies are used.
3. Edit the fictional patient's name and phone number.
   - Expected: name and phone update; email and role remain unchanged.

### 3. Patient clinic booking

1. Start from a clinician profile or choose **Book a session**.
   - Expected: the selected clinician is preserved through sign-in/registration when applicable.
2. Select a future date and an available demo time.
   - Expected: the app shows configurable demo hours of 9:00 AM–6:00 PM IST in 30-minute slots. These are demo defaults, not verified clinic or clinician working hours.
3. Review and confirm the booking.
   - Expected: the confirmation clearly names the clinician, calendar date, time, and `Asia/Kolkata` timezone.
4. Open appointment history.
   - Expected: the new clinic appointment appears with its recorded status.
5. Cancel an appointment more than 24 hours before it starts.
   - Expected: cancellation succeeds and the slot becomes available again.
6. Show the cancellation message for an appointment inside 24 hours.
   - Expected: self-service cancellation is blocked with truthful contact-the-clinic guidance. No fee is charged or promised.

### 4. Reception workflow

1. Sign out, then sign in as a fictional receptionist.
2. Open the patient directory and update a fictional patient's contact details.
   - Expected: only minimal operational contact fields are visible. Date of birth, subscription metadata, clinical reasons/history, billing, analytics, staff, and security settings remain restricted.
3. Book an available clinic slot for an existing fictional patient.
   - Expected: booking succeeds without exposing a clinical reason to reception.
4. Try the same clinician/date/time for another patient.
   - Expected: the occupied slot is rejected; simultaneous booking attempts cannot double-book it.
5. Cancel an eligible future booking.
   - Expected: the same 24-hour cutoff applies; reception has no silent override.

### 5. Doctor workflow

1. Sign out, then sign in as the fictional doctor assigned to the rehearsal appointment.
2. Open appointments and patient details.
   - Expected: only patients linked to that doctor's assigned appointments are listed; an unassigned doctor receives an empty or isolated view.
3. Move the appointment from **Scheduled** to **In progress**, then **Completed**.
   - Expected: valid clinical status updates succeed for the assigned doctor.
4. Confirm privacy boundaries.
   - Expected: billing amount/status, patient cancellation controls, unrelated appointments, admin analytics, and staff settings are not returned to the doctor.

### 6. Admin workflow

1. Sign out, then sign in as a fictional admin.
2. Review patients, clinicians, appointments, analytics, and demo services.
   - Expected: recorded totals are based on available records; unavailable comparisons are not fabricated. Payment remains explicitly unconfigured.
3. Edit a fictional clinician profile.
   - Expected: optional public profile fields can be updated without changing unrelated records.
4. Review schedule availability.
   - Expected: occupied slots and cancellations are reflected; demo hours remain visibly provisional/configurable.

### 7. Demo entitlement and home-visit request

1. As admin, grant a fictional patient the temporary demo home-request entitlement.
   - Expected: it is labelled demo-only, purchase unavailable, and payment unconfigured.
2. As the patient, submit a home-visit request with a fictional preferred clinician, address, and reason.
   - Expected: the request is **Pending clinic confirmation**, is not a confirmed appointment, and reserves no capacity.
3. Before approval, check reception and doctor queues.
   - Expected: the pending request is not exposed to either operational queue.
4. As admin, approve it for coordination.
   - Expected: this changes coordination status only; it does not promise a visit time, coverage, price, or capacity.
5. Check role-specific views.
   - Expected: the assigned clinician sees the clinical reason and address; reception sees only operational contact/address fields and not the clinical reason.
6. As the patient, withdraw the request.
   - Expected: it leaves doctor and reception coordination queues. No clinic cancellation or refund policy is implied.

### 8. Session and recovery checks

1. Sign out from a protected dashboard.
   - Expected: the session is revoked and browser Back does not restore usable protected content.
2. Refresh a protected route after sign-out.
   - Expected: the app returns to sign-in.
3. Demonstrate one occupied-slot or stale-availability error.
   - Expected: the page explains the issue and allows a safe retry without duplicate booking.
4. Repeat one submit/cancel action.
   - Expected: the result remains idempotent and does not create duplicate state.

## Provisional demo policies to state aloud

- Clinic timezone: `Asia/Kolkata`.
- Demo clinic hours: 9:00 AM–6:00 PM, 30-minute slots; configurable and not yet confirmed per clinician/day.
- Patient self-service clinic cancellation: allowed until exactly 24 hours before the appointment; inside 24 hours, contact the clinic.
- No automatic cancellation fees or refunds. Payment processing remains disabled in this local demo even though guarded Razorpay Test Mode integration code exists.
- Home visits are requests pending clinic confirmation, not confirmed appointments, and do not reserve capacity.
- Demo entitlement is not a paid subscription.

## Client decisions and real data still required

- Verified clinic name, address, contact details, opening days/hours, holidays, breaks, and service areas.
- Verified clinician photos, names, qualifications, registrations, experience, specialties, biographies, and true professional-link destinations.
- Actual clinician schedules, leave rules, slot lengths, and appointment capacity.
- Subscription plans, limits, prices, duration, eligibility, and renewal rules.
- Home-visit coverage, scheduling, travel/capacity rules, cancellation policy, and staff exception policy.
- Payment provider, currency/receipts, failure/refund handling, reconciliation, and financial permissions.
- Cancellation/no-show fees and emergency exception policy.
- Pediatric guardian, consent, and data-retention decisions.
- Receptionist access details beyond the current least-privilege Phase 1 scope.
- Production hosting, monitoring, backups, data migration, privacy notices, legal review, and security/compliance assessment.

## Deferred beyond Phase 1

- Exercise programmes and instructional videos.
- Pain/progress tracking and clinical outcome tools.
- Patient-clinician messaging and telehealth.
- Laboratory-test browsing or booking.
- Native mobile packaging and app-store release.
- Real payment collection.
