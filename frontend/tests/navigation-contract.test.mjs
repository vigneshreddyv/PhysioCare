import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


const source = async (relativePath) => readFile(new URL(`../${relativePath}`, import.meta.url), 'utf8');


test('admin activity links to the registered authenticated notifications route', async () => {
  const [appSource, activitySource] = await Promise.all([
    source('src/App.jsx'),
    source('src/pages/admin/dashboard/RecentActivity.jsx'),
  ]);

  assert.match(appSource, /path="\/notifications"/);
  assert.match(activitySource, /navigate\('\/notifications'\)/);
  assert.doesNotMatch(activitySource, /\/admin\/notifications/);
});


test('patient history placeholder returns to the registered patient directory', async () => {
  const [appSource, historySource] = await Promise.all([
    source('src/App.jsx'),
    source('src/pages/admin/AdminPatientHistory.jsx'),
  ]);

  assert.match(appSource, /<Route path="patients" element={<PatientsList \/>} \/>/);
  assert.match(historySource, /navigate\('\/admin\/patients'\)/);
  assert.doesNotMatch(historySource, /\/admin\/patients\/\$\{/);
});


test('session client uses cookies and removes legacy bearer storage', async () => {
  const [apiSource, authSource] = await Promise.all([
    source('src/services/api.js'),
    source('src/context/AuthContext.jsx'),
  ]);

  assert.match(apiSource, /withCredentials:\s*true/);
  assert.match(apiSource, /X-CSRF-Token/);
  assert.doesNotMatch(apiSource, /Authorization/);
  assert.doesNotMatch(apiSource, /localStorage\.setItem/);
  assert.match(authSource, /localStorage\.removeItem\('access_token'\)/);
  assert.match(authSource, /api\.post\('\/auth\/logout'\)/);
});


test('analytics UI does not scale or fall back to fabricated metrics', async () => {
  const [analyticsSource, chartsSource] = await Promise.all([
    source('src/pages/admin/Analytics.jsx'),
    source('src/pages/admin/dashboard/DashboardCharts.jsx'),
  ]);

  assert.doesNotMatch(analyticsSource, /total_appointments\s*\*\s*4/);
  assert.doesNotMatch(analyticsSource, /total_revenue\s*\*\s*5\.9/);
  assert.doesNotMatch(chartsSource, /appointmentsToday\s*\*\s*0\.[24]/);
  assert.match(analyticsSource, /no payment provider connected/i);
  assert.match(chartsSource, /doctor_specializations/);
});


test('patient cancellation uses the dedicated endpoint and refreshes patient state', async () => {
  const [dashboardSource, bookingSource] = await Promise.all([
    source('src/pages/patient/PatientDashboard.jsx'),
    source('src/pages/patient/BookAppointment.jsx'),
  ]);

  assert.match(dashboardSource, /api\.post\(`\/appointments\/\$\{appointmentId\}\/cancel`\)/);
  assert.match(dashboardSource, /Inside that window, contact the clinic/);
  assert.match(dashboardSource, /no automatic cancellation fee/i);
  assert.match(dashboardSource, /queryKey: \['patientHistory'\]/);
  assert.match(bookingSource, /format\(selectedDate, 'yyyy-MM-dd'\)/);
  assert.match(bookingSource, /India Standard Time/);
});


test('patient profile edit is limited to own name phone and recorded gender', async () => {
  const [profileSource, authSource] = await Promise.all([
    source('src/pages/patient/PatientProfile.jsx'),
    source('src/context/AuthContext.jsx'),
  ]);

  assert.match(profileSource, /api\.patch\('\/users\/me\/patient-profile'/);
  assert.match(profileSource, /full_name: formData\.full_name/);
  assert.match(profileSource, /phone: formData\.phone/);
  assert.match(profileSource, /gender: formData\.gender/);
  assert.match(profileSource, /Gender is optional and patient-recorded/);
  assert.match(profileSource, /Email, date of birth, role, and care status remain read-only/);
  assert.match(authSource, /refreshUserProfile: fetchUserProfile/);
});


test('admin booking selects an existing patient and uses the admin-only workflow', async () => {
  const bookingSource = await source('src/pages/admin/AppointmentBooking.jsx');

  assert.match(bookingSource, /isReceptionist \? '\/users\/reception\/patients' : '\/users\/patients'/);
  assert.match(bookingSource, /isReceptionist \? '\/appointments\/reception' : '\/appointments\/admin'/);
  assert.match(bookingSource, /if \(!isReceptionist\) appointmentData\.reason = reason\.trim\(\)/);
  assert.match(bookingSource, /patient_id: selectedPatient\.id/);
  assert.match(bookingSource, /api\.get\('\/appointments\/availability'/);
  assert.match(bookingSource, /availability\?\.configuration_label/);
  assert.match(bookingSource, /startMonth=\{bookingWindow\?\.earliest_date/);
  assert.match(bookingSource, /endMonth=\{bookingWindow\?\.latest_date/);
  assert.match(bookingSource, /disabled={!slot\.available/);
  assert.match(bookingSource, /format\(selectedDate, 'yyyy-MM-dd'\)/);
});


test('patient booking uses server availability and refreshes occupied slots', async () => {
  const bookingSource = await source('src/pages/patient/BookAppointment.jsx');

  assert.match(bookingSource, /api\.get\('\/appointments\/availability'/);
  assert.match(bookingSource, /Published clinician schedule/);
  assert.match(bookingSource, /availability\?\.configuration_label/);
  assert.match(bookingSource, /disabled={!slot\.available/);
  assert.match(bookingSource, /Occupied/);
  assert.match(bookingSource, /Passed/);
  assert.match(bookingSource, /refetchAvailability\(\)/);
  assert.match(bookingSource, /appointmentAvailability/);
});


test('doctor patient directory renders assigned minimum fields without admin actions', async () => {
  const patientsSource = await source('src/pages/admin/PatientsList.jsx');

  assert.match(patientsSource, /queryKey: \['patients', user\?\.role\]/);
  assert.match(patientsSource, /Review only the patients linked to appointments assigned to you/);
  assert.match(patientsSource, /Patients will appear here only after an appointment is assigned to you/);
  assert.match(patientsSource, /\(isAdmin \|\| isReceptionist\) && <th className="p-4">Email<\/th>/);
  assert.match(patientsSource, /!isReceptionist && <th className="p-4">Date of Birth<\/th>/);
  assert.match(patientsSource, /isAdmin && <th className="p-4">Subscription<\/th>/);
  assert.match(patientsSource, /isAdmin && <div className="portal-mobile-record__actions">/);
});


test('doctor assigned-patient history is route-scoped and renders published reports only', async () => {
  const [appSource, patientsSource, historySource] = await Promise.all([
    source('src/App.jsx'),
    source('src/pages/admin/PatientsList.jsx'),
    source('src/pages/doctor/DoctorPatientHistory.jsx'),
  ]);

  assert.match(appSource, /<Route path="patients\/:patientId" element={<DoctorPatientHistory \/>} \/>/);
  assert.match(patientsSource, /navigate\(`\/doctor\/patients\/\$\{patient\.id\}`\)/);
  assert.match(historySource, /api\.get\(`\/users\/doctor\/patients\/\$\{patientId\}\/history`\)/);
  assert.match(historySource, /Published report history/);
  assert.match(historySource, /Reports shown here were completed through PhysioCare and published by an administrator/);
  assert.match(historySource, /External historical documents are not available in this record/);
  assert.match(historySource, /patient\.gender \|\| 'Not recorded'/);
  assert.match(historySource, /calculateRecordedAge\(patient\.date_of_birth\)/);
  assert.match(historySource, /api\.get\(`\/lab-requests\/\$\{report\.request_id\}\/report-file`/);
  assert.match(historySource, /Patient history is not available/);
  assert.doesNotMatch(historySource, /billing_(?:amount|status)|subscription_status|report_storage_path/);
});


test('public doctor directory uses privacy-safe staff profiles and truthful states', async () => {
  const [homeSource, doctorsSource, bookingSource, homeVisitsSource] = await Promise.all([
    source('src/pages/common/PublicHome.jsx'),
    source('src/pages/admin/DoctorsList.jsx'),
    source('src/pages/patient/BookAppointment.jsx'),
    source('src/pages/patient/HomeVisitRequests.jsx'),
  ]);

  assert.match(homeSource, /api\.get\('\/users\/public\/doctors'\)/);
  assert.match(homeSource, /No public clinician profiles are available yet/);
  assert.match(homeSource, /Clinician profiles are temporarily unavailable/);
  assert.match(homeSource, /doctor\.specialization/);
  assert.match(homeSource, /doctor\.bio/);
  assert.match(homeSource, /doctor\.qualifications/);
  assert.match(homeSource, /doctor\.years_experience/);
  assert.match(homeSource, /selectedDoctor\.linkedin_url/);
  assert.match(homeSource, /Only details published by the clinic administrator/);
  assert.match(homeSource, /final booking action confirms the selected available slot/);
  assert.doesNotMatch(homeSource, /doctor\.email/);
  assert.doesNotMatch(homeSource, /doctor\.is_active_today/);
  assert.match(doctorsSource, /api\.patch\(`\/users\/doctors\/\$\{doctorId\}`/);
  assert.match(doctorsSource, /Publish only clinic-verified qualifications/);
  assert.match(doctorsSource, /Personal LinkedIn URL/);
  assert.match(bookingSource, /api\.get\('\/users\/public\/doctors'\)/);
  assert.match(homeVisitsSource, /api\.get\('\/users\/public\/doctors'\)/);
});


test('public clinician choice survives authentication without persistent or sensitive storage', async () => {
  const [homeSource, loginSource, emailSource, verificationSource, codeSource, registerSource, bookingSource] = await Promise.all([
    source('src/pages/common/PublicHome.jsx'),
    source('src/pages/common/Login.jsx'),
    source('src/pages/common/EmailLogin.jsx'),
    source('src/pages/common/PhoneVerification.jsx'),
    source('src/pages/common/PhoneCodePreview.jsx'),
    source('src/pages/common/Register.jsx'),
    source('src/pages/patient/BookAppointment.jsx'),
  ]);

  assert.match(homeSource, /bookingPreference: \{ doctorId: selectedDoctor\.id \}/);
  assert.match(homeSource, /pathname: '\/patient\/book'/);
  assert.match(emailSource, /state: destinationState/);
  assert.match(loginSource, /to="\/register" state=\{location\.state\}/);
  assert.match(loginSource, /navigate\('\/verify-phone', \{ state: location\.state \}\)/);
  assert.match(verificationSource, /state: location\.state/);
  assert.match(codeSource, /state=\{location\.state\}/);
  assert.match(registerSource, /to="\/login" state=\{location\.state\}/);
  assert.match(bookingSource, /location\.state\?\.bookingPreference\?\.doctorId/);
  assert.match(bookingSource, /navigate\(location\.pathname, \{ replace: true, state: null \}\)/);
  assert.doesNotMatch(homeSource + loginSource + emailSource + verificationSource + codeSource + registerSource + bookingSource, /(?:localStorage|sessionStorage)\.setItem/);
});


test('phase one confirmations state outcome, timezone, and next action', async () => {
  const [bookingSource, dashboardSource, homeVisitSource] = await Promise.all([
    source('src/pages/patient/BookAppointment.jsx'),
    source('src/pages/patient/PatientDashboard.jsx'),
    source('src/pages/patient/HomeVisitRequests.jsx'),
  ]);

  assert.match(bookingSource, /Your clinic appointment is scheduled/);
  assert.match(bookingSource, /No payment was taken in this app/);
  assert.match(bookingSource, /View upcoming appointment/);
  assert.match(bookingSource, /\} IST/);
  assert.match(dashboardSource, /time_slot\} IST with Dr/);
  assert.match(homeVisitSource, /Home visit confirmed for/);
  assert.match(homeVisitSource, /Earlier home-visit requests/);
});


test('modal traps keyboard focus, closes with escape, and restores focus', async () => {
  const modalSource = await source('src/components/common/Modal.jsx');

  assert.match(modalSource, /event\.key === 'Escape'/);
  assert.match(modalSource, /event\.key !== 'Tab'/);
  assert.match(modalSource, /lastControl\.focus\(\)/);
  assert.match(modalSource, /firstControl\.focus\(\)/);
  assert.match(modalSource, /previouslyFocused\.focus\(\)/);
  assert.match(modalSource, /aria-labelledby=\{titleId\}/);
});


test('role screens are route-split with accessible loading and recovery states', async () => {
  const appSource = await source('src/App.jsx');

  assert.match(appSource, /lazy\(\(\) => import\('\.\/pages\/common\/PublicHome'\)\)/);
  assert.match(appSource, /lazy\(\(\) => import\('\.\/pages\/patient\/BookAppointment'\)\)/);
  assert.match(appSource, /lazy\(\(\) => import\('\.\/pages\/admin\/Analytics'\)\)/);
  assert.match(appSource, /<Suspense fallback=\{<RouteLoading \/>\}>/);
  assert.match(appSource, /role="status" aria-live="polite" aria-busy="true"/);
  assert.match(appSource, /role="alert"/);
  assert.match(appSource, /No form was submitted/);
  assert.match(appSource, /window\.location\.reload\(\)/);
  assert.match(appSource, /import\.meta\.env\.DEV/);
});


test('clinician discovery is searchable without inventing profile data', async () => {
  const [homeSource, bookingSource] = await Promise.all([
    source('src/pages/common/PublicHome.jsx'),
    source('src/pages/patient/BookAppointment.jsx'),
  ]);

  for (const pageSource of [homeSource, bookingSource]) {
    assert.match(pageSource, /doctor\.full_name/);
    assert.match(pageSource, /doctor\.specialization/);
    assert.match(pageSource, /doctor\.qualifications/);
    assert.match(pageSource, /doctor\.specialties/);
    assert.match(pageSource, /Search by name, specialty, or focus area/);
    assert.match(pageSource, /aria-live="polite"/);
    assert.match(pageSource, /Clear search/);
  }
});


test('booking clears a stale occupied slot while preserving clinician and date', async () => {
  const bookingSource = await source('src/pages/patient/BookAppointment.jsx');

  assert.match(bookingSource, /availability\.slots\.find\(\(slot\) => slot\.time_slot === selectedTime\)/);
  assert.match(bookingSource, /if \(!currentSlot\?\.available\)/);
  assert.match(bookingSource, /setSelectedTime\(''\)/);
  assert.match(bookingSource, /setStep\(3\)/);
  assert.match(bookingSource, /Your specialist and date are still selected/);
  assert.match(bookingSource, /aria-live="assertive"/);
});


test('clinician directory errors provide in-place retry actions', async () => {
  const [homeSource, bookingSource] = await Promise.all([
    source('src/pages/common/PublicHome.jsx'),
    source('src/pages/patient/BookAppointment.jsx'),
  ]);

  assert.match(homeSource, /refetch: refetchDoctors/);
  assert.match(homeSource, /onClick=\{\(\) => refetchDoctors\(\)\}/);
  assert.match(homeSource, /Try loading profiles again/);
  assert.match(bookingSource, /refetch: refetchDoctors/);
  assert.match(bookingSource, /onRetry=\{\(\) => \{ refetchDoctors\(\); refetchBookingWindow\(\); \}\}/);
});


test('lazy public routes restore direct hash navigation after mount', async () => {
  const homeSource = await source('src/pages/common/PublicHome.jsx');

  assert.match(homeSource, /useLocation\(\)/);
  assert.match(homeSource, /decodeURIComponent\(location\.hash\.slice\(1\)\)/);
  assert.match(homeSource, /document\.getElementById\(targetId\)\?\.scrollIntoView/);
  assert.match(homeSource, /window\.cancelAnimationFrame\(frame\)/);
});


test('reception routes and navigation expose only least-privilege operations', async () => {
  const [appSource, sidebarSource, guardSource] = await Promise.all([
    source('src/App.jsx'),
    source('src/components/common/Sidebar.jsx'),
    source('src/routes/RoleProtectedRoute.jsx'),
  ]);

  assert.match(appSource, /path="\/reception"/);
  assert.match(appSource, /allowedRoles={\['receptionist'\]}/);
  assert.match(appSource, /path="dashboard" element={<ReceptionistDashboard \/>}/);
  assert.match(appSource, /path="appointment-booking" element={<AppointmentBooking \/>}/);
  assert.match(sidebarSource, /receptionist: \[/);
  assert.match(sidebarSource, /\/reception\/appointment-booking/);
  assert.match(sidebarSource, /Patient contacts/);
  assert.doesNotMatch(sidebarSource.match(/receptionist: \[[\s\S]*?\n    \]/)?.[0] || '', /analytics|billing|settings|staff/i);
  assert.match(guardSource, /receptionist: '\/reception\/dashboard'/);
});


test('reception booking and schedule omit clinical and billing fields', async () => {
  const [bookingSource, dashboardSource, patientsSource] = await Promise.all([
    source('src/pages/admin/AppointmentBooking.jsx'),
    source('src/pages/receptionist/ReceptionistDashboard.jsx'),
    source('src/pages/admin/PatientsList.jsx'),
  ]);

  assert.match(bookingSource, /isReceptionist \? '\/appointments\/reception' : '\/appointments\/admin'/);
  assert.match(bookingSource, /isReceptionist \? '\/users\/reception\/doctors' : '\/users\/doctors'/);
  assert.match(bookingSource, /isReceptionist \? '\/users\/reception\/patients' : '\/users\/patients'/);
  assert.match(bookingSource, /Reception does not collect or display clinical reasons/);
  assert.match(dashboardSource, /api\.get\('\/appointments\/reception'\)/);
  assert.match(dashboardSource, /api\.post\(`\/appointments\/reception\/\$\{appointmentId\}\/cancel`\)/);
  assert.doesNotMatch(dashboardSource, /appointment\.reason|billing_amount|billing_status|subscription_status|date_of_birth/);
  assert.match(patientsSource, /Clinical history, reasons, birth dates, subscriptions, and billing details are not available in reception/);
  assert.match(patientsSource, /!isReceptionist && <th className="p-4">Date of Birth<\/th>/);
  assert.match(patientsSource, /api\.patch\(`\/users\/reception\/patients\/\$\{patientId\}`/);
  assert.match(patientsSource, /Email is the patient’s account identity and remains read-only/);
  assert.match(patientsSource, /updates: \{ full_name: contactDraft\.full_name\.trim\(\), phone:/);
  assert.doesNotMatch(patientsSource, /updates: \{[^}]*email:/);
});


test('home visits use explicit slot confirmation while legacy requests stay separate', async () => {
  const [appSource, patientSource, adminSource, doctorSource, receptionSource] = await Promise.all([
    source('src/App.jsx'),
    source('src/pages/patient/HomeVisitRequests.jsx'),
    source('src/pages/admin/DemoServices.jsx'),
    source('src/pages/doctor/HomeVisits.jsx'),
    source('src/pages/receptionist/ReceptionistDashboard.jsx'),
  ]);

  assert.match(appSource, /path="home-visits" element={<HomeVisitRequests \/>}/);
  assert.match(appSource, /path="demo-services" element={<DemoServices \/>}/);
  assert.match(patientSource, /api\.get\('\/demo-services\/me\/entitlement'\)/);
  assert.match(patientSource, /api\.get\('\/home-visit-bookings\/availability'/);
  assert.match(patientSource, /api\.post\('\/home-visit-bookings'/);
  assert.match(patientSource, /Confirm home visit/);
  assert.match(patientSource, /Earlier home-visit requests/);
  assert.match(patientSource, /submission_key/);
  assert.match(patientSource, /No preference — clinic assigns/);
  assert.match(patientSource, /Doctor assignment pending/);
  assert.doesNotMatch(patientSource, /Payments are not configured|server rejects|configuration/i);
  assert.doesNotMatch(patientSource, /api\.(?:post|put)\(['"]\/(?:payments|checkout)/i);
  assert.match(adminSource, /api\.put\(`\/demo-services\/patients\/\$\{patientId\}\/entitlement`/);
  assert.match(adminSource, /api\.patch\(`\/home-visit-requests\/admin\/\$\{requestId\}`/);
  assert.match(adminSource, /api\.patch\(`\/home-visit-bookings\/admin\/\$\{appointmentId\}\/doctor`/);
  assert.match(adminSource, /Payments are unconfigured/);
  assert.match(doctorSource, /api\.get\('\/home-visit-requests\/doctor'\)/);
  assert.match(doctorSource, /request\.reason/);
  assert.match(receptionSource, /api\.get\('\/home-visit-requests\/reception'\)/);
  assert.doesNotMatch(receptionSource, /request\.reason/);
});


test('laboratory submissions use a stable idempotency key for safe retries', async () => {
  const laboratorySource = await source('src/pages/patient/LaboratoryRequests.jsx');

  assert.match(laboratorySource, /submissionRef = useRef\(null\)/);
  assert.match(laboratorySource, /'Idempotency-Key': submissionKey/);
  assert.match(laboratorySource, /submissionRef\.current\?\.fingerprint !== fingerprint/);
  assert.match(laboratorySource, /if \(create\.isPending\) return/);
  assert.match(laboratorySource, /submissionRef\.current = null/);
});

test('published laboratory reports open in the browser PDF viewer instead of forcing a download', async () => {
  const [helperSource, patientSource, doctorHistorySource, doctorDashboardSource, adminSource] = await Promise.all([
    source('src/utils/openPdfBlob.js'),
    source('src/pages/patient/LaboratoryRequests.jsx'),
    source('src/pages/doctor/DoctorPatientHistory.jsx'),
    source('src/pages/doctor/DoctorDashboard.jsx'),
    source('src/pages/admin/AdminLabRequestsPanel.jsx'),
  ]);

  assert.match(helperSource, /window\.open\('', '_blank'\)/);
  assert.match(helperSource, /viewer\.location\.replace\(url\)/);
  assert.match(helperSource, /viewer\.opener = null/);
  assert.match(helperSource, /PDF viewer was blocked/);
  assert.doesNotMatch(helperSource, /\.download\s*=/);
  for (const pageSource of [patientSource, doctorHistorySource, doctorDashboardSource, adminSource]) {
    assert.match(pageSource, /preparePdfViewer\(\)/);
    assert.match(pageSource, /showPdfBlob\(viewer, response\.data\)/);
    assert.match(pageSource, /closePdfViewer\(viewer\)/);
    assert.doesNotMatch(pageSource, /anchor\.download/);
  }
});


test('mobile patient navigation and clinic-review controls retain product safeguards', async () => {
  const [layoutSource, laboratorySource, adminSource, adminLabSource] = await Promise.all([
    source('src/layouts/PatientLayout.jsx'),
    source('src/pages/patient/LaboratoryRequests.jsx'),
    source('src/pages/admin/DemoServices.jsx'),
    source('src/pages/admin/AdminLabRequestsPanel.jsx'),
  ]);

  assert.equal(layoutSource.match(/mobile: true/g)?.length, 3);
  assert.match(layoutSource, /mobileNavItems = navItems\.filter\(\(item\) => item\.mobile\)/);
  assert.match(layoutSource, /\{ to: '\/patient\/book', label: 'Book', icon: 'calendar_month' \}/);
  assert.doesNotMatch(layoutSource, /to: '\/patient\/book'[^\n]*mobile: true/);
  assert.match(laboratorySource, /patient-lab__selection--empty/);
  assert.match(adminLabSource, /labRequests\.isLoading \|\| laboratorians\.isLoading \? <Skeleton/);
  assert.match(adminLabSource, /disabled=\{labReviewMutation\.isPending\}/);
  assert.match(adminSource, /Payments are unconfigured/);
});

test('patient home benchmark keeps one truthful next action and compact service paths', async () => {
  const [dashboardSource, layoutSource, iconSource] = await Promise.all([
    source('src/pages/patient/PatientDashboard.jsx'),
    source('src/layouts/PatientLayout.jsx'),
    source('src/components/common/PatientIcon.jsx'),
  ]);

  assert.match(dashboardSource, /patient-dashboard--benchmark/);
  assert.match(dashboardSource, /laterAppointments = upcoming\.slice\(1\)/);
  assert.match(dashboardSource, /This is not a confirmed appointment/);
  assert.match(dashboardSource, /Book an available home-visit time in Nellore/);
  assert.match(dashboardSource, /Demo catalogue; no checkout or confirmed collection/);
  assert.match(dashboardSource, /nextAppointment\.can_patient_cancel/);
  assert.match(dashboardSource, /openCancellation\(nextAppointment\)/);
  assert.doesNotMatch(dashboardSource, /material-symbols-outlined/);

  assert.match(layoutSource, /<PatientIcon name=/);
  assert.match(iconSource, /aria-hidden="true"/);
  assert.match(iconSource, /focusable="false"/);
});


test('patient booking stays task-focused while preserving all four selections', async () => {
  const [bookingSource, homeVisitSource, clinicDateSource] = await Promise.all([
    source('src/pages/patient/BookAppointment.jsx'),
    source('src/pages/patient/HomeVisitRequests.jsx'),
    source('src/utils/clinicDate.js'),
  ]);

  assert.match(bookingSource, /Book an appointment/);
  assert.match(bookingSource, /step === 1/);
  assert.match(bookingSource, /step === 2 && selectedDoctor/);
  assert.match(bookingSource, /step === 3 && selectedDate/);
  assert.match(bookingSource, /step === 4 && selectedTime/);
  assert.match(bookingSource, /appointmentSlots\.filter\(\(slot\) => slot\.available\)/);
  assert.match(bookingSource, /Unavailable times are already booked or have passed/);
  assert.match(bookingSource, /No times are available for this date/);
  assert.match(bookingSource, /aria-describedby=\{!slot\.available \? 'booking-unavailable-help'/);
  assert.match(bookingSource, /Configurable demo schedule|Demo schedule/);
  assert.match(bookingSource, /Confirm booking/);
  assert.match(bookingSource, /No payment taken/);
  assert.match(bookingSource, /isOutsideBookingWindow/);
  assert.match(homeVisitSource, /min=\{bookingWindow\.data\?\.earliest_date\}/);
  assert.match(homeVisitSource, /max=\{bookingWindow\.data\?\.latest_date\}/);
  assert.match(clinicDateSource, /timeZone: CLINIC_TIMEZONE/);
  assert.doesNotMatch(homeVisitSource, /2030-01-10/);
});


test('app-first login separates phone entry from working email authentication', async () => {
  const [loginSource, emailSource] = await Promise.all([
    source('src/pages/common/Login.jsx'),
    source('src/pages/common/EmailLogin.jsx'),
  ]);

  assert.match(loginSource, /type="tel"/);
  assert.match(loginSource, /autoComplete="tel-national"/);
  assert.match(loginSource, /navigate\('\/verify-phone', \{ state: location\.state \}\)/);
  assert.match(loginSource, /to="\/login\/email" state=\{location\.state\}/);
  assert.match(loginSource, /Continue with email/);
  assert.match(loginSource, /to="\/register" state=\{location\.state\}/);
  assert.doesNotMatch(loginSource, /Public website|Back to website|to="\/"/);

  assert.match(emailSource, /login\(data\.email, data\.password\)/);
  assert.match(emailSource, /type="email"/);
  assert.match(emailSource, /autoComplete="email"/);
  assert.match(emailSource, /autoComplete="current-password"/);
  assert.match(emailSource, /aria-invalid=\{Boolean\(errors\.email\)\}/);
  assert.match(emailSource, /aria-describedby=\{errors\.password \? 'login-password-error'/);
  assert.match(emailSource, /aria-label=\{showPassword \? 'Hide password' : 'Show password'\}/);
  assert.match(emailSource, /aria-busy=\{submitting\}/);
  assert.match(emailSource, /to="\/login" state=\{location\.state\}/);
  assert.doesNotMatch(emailSource, /Public website|Back to website|to="\/"/);
  assert.doesNotMatch(`${loginSource}\n${emailSource}`, /api\.(?:get|post).*otp|verifyOtp|oneTimeCode/i);
});


test('phone verification uses separate provider-gated channel and code screens', async () => {
  const [appSource, loginSource, verificationSource, codeSource] = await Promise.all([
    source('src/App.jsx'),
    source('src/pages/common/Login.jsx'),
    source('src/pages/common/PhoneVerification.jsx'),
    source('src/pages/common/PhoneCodePreview.jsx'),
  ]);

  assert.match(appSource, /lazy\(\(\) => import\('\.\/pages\/common\/PhoneVerification'\)\)/);
  assert.match(appSource, /lazy\(\(\) => import\('\.\/pages\/common\/PhoneCodePreview'\)\)/);
  assert.match(appSource, /path="\/login\/email" element={<EmailLogin \/>}/);
  assert.match(appSource, /path="\/verify-phone" element={<PhoneVerification \/>}/);
  assert.match(appSource, /path="\/verify-phone\/code" element={<PhoneCodePreview \/>}/);
  assert.match(loginSource, /navigate\('\/verify-phone', \{ state: location\.state \}\)/);
  assert.match(verificationSource, /Provider not connected—no code will be sent/);
  assert.match(verificationSource, /Your number was not submitted or saved/);
  assert.match(verificationSource, /Preview verification/);
  assert.match(verificationSource, /Continue with email/);
  assert.match(codeSource, /Verification code digit \$\{index \+ 1\}/);
  assert.match(codeSource, /auth-flow--\$\{channelKey\}/);
  assert.match(codeSource, /no code was sent/);
  assert.match(codeSource, /className="auth-flow__primary" disabled/);
  assert.match(codeSource, /Change phone number/);
  assert.doesNotMatch(`${verificationSource}\n${codeSource}`, /api\.|fetch\(|axios|localStorage|sessionStorage|setTimeout|verification_success|access_token/i);
  assert.doesNotMatch(`${verificationSource}\n${codeSource}`, /Public website|Back to website|to="\/"/);
});

test('patient appointment timeline separates lifecycle states and limits self-service cancellation', async () => {
  const historySource = await source('src/pages/patient/PatientHistory.jsx');

  assert.match(historySource, /value: 'upcoming'.*\['scheduled', 'in_progress'\]/s);
  assert.match(historySource, /value: 'completed'.*\['completed'\]/s);
  assert.match(historySource, /value: 'cancelled'.*\['cancelled'\]/s);
  assert.match(historySource, /service_mode === 'home_visit'/);
  assert.match(historySource, /doctor_assignment_pending/);
  assert.match(historySource, /Doctor assignment pending/);
  assert.match(historySource, /api\.post\(`\/appointments\/\$\{appointmentId\}\/cancel`\)/);
  assert.match(historySource, /!isHomeVisit && isScheduled && appointment\.can_patient_cancel/);
  assert.match(historySource, /Contact the clinic to change or cancel this home visit\./);
  assert.match(historySource, /exactly 24 hours before a clinic appointment/);
  assert.match(historySource, /No automatic cancellation fee is applied/);
  assert.doesNotMatch(historySource, /server rejects|payments? (?:is|are) not configured|visual qa|submissions disabled/i);
});


test('laboratory workflow keeps assignment, finalized upload, admin publication, and released-report access role scoped', async () => {
  const [appSource, adminSource, adminLabSource, laboratorySource, patientSource, doctorSource] = await Promise.all([
    source('src/App.jsx'),
    source('src/pages/admin/DemoServices.jsx'),
    source('src/pages/admin/AdminLabRequestsPanel.jsx'),
    source('src/pages/laboratorian/LaboratoryDashboard.jsx'),
    source('src/pages/patient/LaboratoryRequests.jsx'),
    source('src/pages/doctor/DoctorDashboard.jsx'),
  ]);

  assert.match(appSource, /allowedRoles=\{\['laboratorian'\]\}/);
  assert.match(appSource, /path="\/laboratory"/);
  assert.match(adminSource, /AdminLabRequestsPanel/);
  assert.match(adminLabSource, /\/users\/laboratorians/);
  assert.match(adminLabSource, /\/lab-requests\/admin\/\$\{requestId\}\/assignment/);
  assert.match(adminLabSource, /\/lab-requests\/admin\/\$\{requestId\}\/publish-report/);
  assert.match(adminLabSource, /Publish report to patient/);
  assert.match(adminLabSource, /does not provide medical validation/);
  assert.match(adminLabSource, /I intend to publish this exact finalized PDF/);
  assert.match(laboratorySource, /\/lab-requests\/laboratory\/assigned/);
  assert.match(laboratorySource, /'Content-Type': 'application\/pdf'/);
  assert.match(laboratorySource, /Upload finalized report/);
  assert.match(laboratorySource, /remains private until an administrator publishes it/);
  assert.doesNotMatch(laboratorySource, /publish-report|Publish report to patient/);
  assert.match(patientSource, /\/lab-requests\/me\/reports/);
  assert.match(patientSource, /Reports appear here only after they are reviewed and released to you/);
  assert.match(doctorSource, /\/lab-requests\/doctor\/reports/);
  assert.match(doctorSource, /Only released reports for patients assigned to you appear here/);
});


test('administrator clinician schedules remain draft-first, role-scoped, and conflict aware', async () => {
  const [appSource, doctorsSource, scheduleSource, sidebarSource] = await Promise.all([
    source('src/App.jsx'),
    source('src/pages/admin/DoctorsList.jsx'),
    source('src/pages/admin/ClinicianSchedules.jsx'),
    source('src/components/common/Sidebar.jsx'),
  ]);

  assert.match(appSource, /ClinicianSchedules = lazy/);
  assert.match(appSource, /<Route path="schedules\/:doctorId" element={<ClinicianSchedules \/>} \/>/);
  assert.match(appSource, /allowedRoles=\{\['admin'\]\}/);
  assert.match(doctorsSource, /navigate\(`\/admin\/schedules\/\$\{doc\.id\}`\)/);
  assert.match(scheduleSource, /\/clinician-schedules\/admin\/\$\{doctorId\}\/draft/);
  assert.match(scheduleSource, /\/clinician-schedules\/admin\/\$\{doctorId\}\/preview/);
  assert.match(scheduleSource, /\/clinician-schedules\/admin\/\$\{doctorId\}\/publish/);
  assert.match(scheduleSource, /Drafts never change patient booking availability/);
  assert.match(scheduleSource, /clinic and home-visit blocks cannot overlap/);
  assert.match(scheduleSource, /existing appointments/);
  assert.match(scheduleSource, /travel-time policy/);
  assert.match(scheduleSource, /min=\{bookingWindow\.data\?\.earliest_date\}/);
  assert.match(scheduleSource, /max=\{bookingWindow\.data\?\.latest_date\}/);
  assert.doesNotMatch(sidebarSource, /reception[^]*clinician schedule/i);
});
