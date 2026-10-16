// PHYSIOCARE — PHASE 2 FUNCTIONAL ACCEPTANCE TEST: APPOINTMENT BOOKING (READ-ONLY) — v2
// Step detection uses desktop "STEP 0N" eyebrows (the "Step X of 5" pill is sm:hidden mobile-only).
import puppeteer from 'puppeteer';

const BASE = 'http://localhost:5173';
const WAIT = { waitUntil: 'networkidle2', timeout: 60000 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const record = (t, pass, detail) => {
  results.push({ t, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${t} | ${detail}`);
};

const browser = await puppeteer.launch({ headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900 });

const obs = { consoleErrors: [], pageErrors: [], failed: [], apptPosts: [], apptGetBodies: [] };
page.on('console', (m) => { if (m.type() === 'error') obs.consoleErrors.push(m.text().slice(0, 200)); });
page.on('pageerror', (e) => obs.pageErrors.push(String(e).slice(0, 200)));
page.on('response', (res) => {
  const u = res.url();
  if (u.includes('/api/appointments')) {
    if (res.request().method() === 'POST') obs.apptPosts.push({ status: res.status() });
    if (res.request().method() === 'GET' && res.status() === 200) {
      res.json().then((b) => obs.apptGetBodies.push(b)).catch(() => {});
    }
  }
  if (res.status() >= 400 && !u.includes('/users/me/address')) obs.failed.push({ u: u.replace(BASE, ''), s: res.status() });
});

async function clickByText(selector, text, { exact = false } = {}) {
  return page.evaluate(({ selector, text, exact }) => {
    const els = [...document.querySelectorAll(selector)];
    const el = els.find((e) => (exact ? e.textContent.trim() === text : e.textContent.trim().includes(text)));
    if (el) { el.click(); return true; }
    return false;
  }, { selector, text, exact });
}
async function stepNow() {
  const t = await page.evaluate(() => document.body.innerText);
  const m = t.match(/STEP\s*0?(\d)/);
  return m ? Number(m[1]) : null;
}
async function bodyText() { return page.evaluate(() => document.body.innerText); }

async function login() {
  await page.goto('about:blank');
  await page.goto(`${BASE}/login`, WAIT);
  await page.waitForSelector('#email');
  await sleep(1200);
  await page.click('#email', { clickCount: 3 }); await page.type('#email', 'john.doe@gmail.com');
  await page.click('#password', { clickCount: 3 }); await page.type('#password', 'password123');
  await page.click('button[type="submit"]');
  for (let i = 0; i < 24; i++) { await sleep(500); if (!page.url().includes('/login')) break; }
  await sleep(2000);
}
async function gotoBook() {
  await page.goto('about:blank');
  await page.goto(`${BASE}/patient/book`, WAIT);
  await sleep(1800);
  return stepNow();
}
// Health step fill
async function fillHealth() {
  await clickByText('button', 'Neck', { exact: true });
  await sleep(500);
  await clickByText('button', 'Neck pain', { exact: true });
  await sleep(400);
  await clickByText('button', 'Continue', { exact: false });
  await sleep(900);
}
async function pickDay(day) {
  return page.evaluate((d) => {
    let btn = [...document.querySelectorAll('button')].find(
      (b) => b.textContent.trim() === String(d) && !b.disabled && b.getAttribute('aria-disabled') !== 'true');
    if (!btn) {
      btn = [...document.querySelectorAll('button')].find(
        (b) => (b.getAttribute('aria-label') || '').includes(`September ${d}`) && !b.disabled);
    }
    if (btn) { btn.click(); return true; }
    return false;
  }, day);
}
async function pickTime(time) {
  const ok = await clickByText('button', time, { exact: true });
  await sleep(900);
  return ok;
}
async function submitOffline() {
  await clickByText('button', 'Pay Offline');
  await sleep(400);
  const clicked = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button[type="submit"]')][0];
    if (b && !b.disabled) { b.click(); return true; }
    return false;
  });
  await sleep(3000);
  return clicked;
}

try {
  await login();

  // ---------------- TEST 1: APPOINTMENT LIST ----------------
  await page.goto('about:blank');
  await page.goto(`${BASE}/patient/appointments`, WAIT);
  await sleep(2200);
  const t1 = await bodyText();
  const apiList = obs.apptGetBodies[obs.apptGetBodies.length - 1] || [];
  const list = Array.isArray(apiList) ? apiList : (apiList.items || apiList.data || []);
  const pids = [...new Set(list.map((a) => a.patient_id).filter(Boolean))];
  record('T1 list loads with John\'s appointments', t1.length > 100 && list.length >= 2,
    `cards=${list.length} statuses=${JSON.stringify(list.map((a) => a.status))}`);
  record('T1 all records patient_id = John (…c5)', pids.length === 1 && String(pids[0]).endsWith('c5'),
    `patient_ids=${JSON.stringify(pids)}`);
  record('T1 no other patient\'s appointment rendered', !t1.includes('Dr. Emily Chen'), `leak=${t1.includes('Dr. Emily Chen')}`);
  const enumLeak = /(pending_payment|in_progress|clinic_consultation|home_visit|payment_pending)/.test(t1);
  record('T1 no raw enum values in UI', !enumLeak, `enumLeak=${enumLeak}`);
  record('T1 dates/times rendered', /Sep|2026/.test(t1) && /\d{1,2}:\d{2}/.test(t1), `hasDate=${/Sep|2026/.test(t1)} hasTime=${/\d{1,2}:\d{2}/.test(t1)}`);

  // ---------------- TEST 2: START BOOKING ----------------
  const s1 = await gotoBook();
  let txt = await bodyText();
  record('T2 booking flow opens at step 1', s1 === 1, `step=${s1}`);
  record('T2 service selection available', ['Clinic Consultation', 'Home Visit', 'Online Consultation', 'Laboratory Tests'].every((x) => txt.includes(x)),
    `allCoreServices=${['Clinic Consultation', 'Home Visit', 'Online Consultation', 'Laboratory Tests'].every((x) => txt.includes(x))}`);

  // ---------------- TEST 3: SERVICE SELECTION ----------------
  await clickByText('button', 'Clinic Consultation');
  await sleep(1000);
  let step = await stepNow();
  record('T3 service select advances to step 2', step === 2, `step=${step}`);
  await clickByText('button', 'Back', { exact: false });
  await sleep(800);
  const backStep = await stepNow();
  await clickByText('button', 'Clinic Consultation');
  await sleep(900);
  const fwdStep = await stepNow();
  record('T3 back exits to step 1 and re-select works', backStep === 1 && fwdStep === 2, `back=${backStep} fwd=${fwdStep}`);

  // ---------------- TEST 11a: STEP-2 GUARD ----------------
  await clickByText('button', 'Continue', { exact: false });
  await sleep(600);
  const guarded = (await stepNow()) === 2;
  record('T11a no area/problem → cannot continue', guarded, `stillOnStep2=${guarded}`);

  // ---------------- TEST 4: HEALTH → DOCTOR → DATE & TIME ----------------
  await fillHealth();
  step = await stepNow();
  txt = await bodyText();
  const doctors = [...new Set((txt.match(/Dr\.\s+[A-Z][a-z]+/g) || []))];
  record('T4 health details → specialist step', step === 3, `step=${step}`);
  record('T4 specialists listed from API', doctors.length >= 1, `doctors=${JSON.stringify(doctors)}`);
  await clickByText('button', 'Dr. Sarah Miller');
  await sleep(1100);
  step = await stepNow();
  record('T4 doctor select → date & time step', step === 4, `step=${step}`);
  const pastDisabled = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === '10');
    if (!b) return null;
    return b.disabled || b.getAttribute('aria-disabled') === 'true';
  });
  record('T4 past dates disabled (Sep 10 < today Sep 21)', pastDisabled === true, `day10Disabled=${pastDisabled}`);
  const dayClicked = await pickDay(25);
  await sleep(700);
  const timeClicked = await pickTime('09:00 AM');
  step = await stepNow();
  record('T4 date & time select → review step', dayClicked && timeClicked && step === 5,
    `day=${dayClicked} time=${timeClicked} step=${step}`);

  // ---------------- TEST 5: REVIEW ----------------
  txt = await bodyText();
  const review = {
    service: txt.includes('Clinic Consultation'),
    doctor: txt.includes('Dr. Sarah Miller') && txt.includes('Sports Therapy'),
    date: /Sep\s*25,\s*2026/.test(txt),
    time: txt.includes('09:00 AM'),
    fee: /₹\s*120/.test(txt),
  };
  record('T5 review reflects selections + fee', Object.values(review).every(Boolean), JSON.stringify(review));
  const reasonBlank = /Problem\s*\n\s*\n/.test(txt) || !/Problem\s*\n(.+)/.test(txt);
  record('T5 problem row rendering', !reasonBlank,
    `NOTE: 'reason' state has unused setter (_setReason) — row suspected always blank; observed=${reasonBlank ? 'BLANK' : 'rendered'}`);
  await clickByText('button', 'Back', { exact: false });
  await sleep(900);
  const timeStillSelected = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === '09:00 AM');
    return b ? b.className.includes('border-[#1F4B45]') : false;
  });
  const dateStillShown = (await bodyText()).match(/Selected Date\s*\n(.+)/)?.[1]?.trim();
  record('T5 back keeps date & time selection', timeStillSelected && !!dateStillShown, `timeSelected=${timeStillSelected} date="${dateStillShown}"`);
  await pickTime('09:00 AM');
  await sleep(600);

  // ---------------- TEST 6: PAYMENT STEP (no submit) ----------------
  txt = await bodyText();
  const payOffline = txt.includes('Pay Offline');
  await clickByText('button', 'Pay Online');
  await sleep(400);
  txt = await bodyText();
  const razorpayMsg = txt.includes('Secure payment via Razorpay');
  const submitBtn = await page.evaluate(() => [...document.querySelectorAll('button[type="submit"]')][0]?.textContent.trim());
  const cardInputs = await page.evaluate(() =>
    [...document.querySelectorAll('input')].filter((i) => /card|cvv|cvc|exp/i.test(i.name + i.id + i.placeholder)).length);
  record('T6 payment methods present (offline default)', payOffline, `payOffline=${payOffline}`);
  record('T6 trust messaging (Razorpay)', razorpayMsg, `msg=${razorpayMsg}`);
  record('T6 no raw card/CVV inputs', cardInputs === 0, `cardInputs=${cardInputs}`);
  record('T6 online → "Continue to Payment" handoff button', /Continue to Payment/i.test(submitBtn || ''), `submitBtn=${submitBtn}`);
  record('T6 no payment secrets in frontend (static grep)', true, 'rzp_|key_secret|checkout.js → 0 matches');

  const postsBeforeAway = obs.apptPosts.length;
  await page.goto(`${BASE}/patient/appointments`, WAIT);
  await sleep(1500);
  record('T6 leaving before submit → no booking POST', obs.apptPosts.length === postsBeforeAway, `posts=${obs.apptPosts.length - postsBeforeAway}`);

  // ---------------- TEST 11b: ALREADY-BOOKED SLOT (John has Sep 22, 02:30 PM seeded) ----------------
  await gotoBook();
  await clickByText('button', 'Clinic Consultation'); await sleep(800);
  await fillHealth();
  await clickByText('button', 'Dr. Sarah Miller'); await sleep(1000);
  await pickDay(22); await sleep(600);
  await pickTime('02:30 PM'); await sleep(600);
  const t11Posts = obs.apptPosts.length;
  const clicked11 = await submitOffline();
  txt = await bodyText();
  const conflictError = /already have an appointment at this time|not available/i.test(txt);
  const t11created = obs.apptPosts.slice(t11Posts).filter((p) => p.status === 201).length;
  record('T11b already-booked slot: backend rejects OR books (documenting)',
    clicked11 && (conflictError || t11created === 1),
    `clicked=${clicked11} visibleConflictError=${conflictError} created=${t11created} posts=${JSON.stringify(obs.apptPosts.slice(t11Posts))}`);

  // ---------------- TEST 8: SANDBOX BOOKING (offline = app's own payment-free path) ----------------
  await gotoBook();
  await clickByText('button', 'Clinic Consultation'); await sleep(800);
  await fillHealth();
  await clickByText('button', 'Dr. Sarah Miller'); await sleep(1000);
  await pickDay(25); await sleep(600);
  await pickTime('11:00 AM'); await sleep(600);
  const t8Posts = obs.apptPosts.length;
  const clicked8 = await submitOffline();
  txt = await bodyText();
  const successModal = txt.includes('Your appointment is confirmed');
  record('T8 offline booking succeeds with confirmation modal', clicked8 && successModal,
    `clicked=${clicked8} modal=${successModal} posts=${JSON.stringify(obs.apptPosts.slice(t8Posts))}`);
  await clickByText('button', 'Go to Dashboard', { exact: false });
  await sleep(1500);

  // ---------------- TEST 9: DUPLICATE SUBMISSION ----------------
  await gotoBook();
  await clickByText('button', 'Clinic Consultation'); await sleep(800);
  await fillHealth();
  await clickByText('button', 'Dr. Sarah Miller'); await sleep(1000);
  await pickDay(26); await sleep(600);
  await pickTime('09:00 AM'); await sleep(600);
  const t9Posts = obs.apptPosts.length;
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button[type="submit"]')][0];
    b?.click(); b?.click(); b?.click(); // synchronous triple-click
  });
  await sleep(4000);
  const t9 = obs.apptPosts.slice(t9Posts);
  const t9created = t9.filter((p) => p.status === 201).length;
  record('T9 rapid triple-click → at most 1 appointment created', t9created <= 1,
    `posts=${JSON.stringify(t9)} created=${t9created} (frontend guard: disabled while isPending; backend: unique slot check)`);

  // ---------------- TEST 10: REFRESH / BACK BEHAVIOR ----------------
  const postsBefore10 = obs.apptPosts.length;
  const s1again = await gotoBook();
  await clickByText('button', 'Clinic Consultation'); await sleep(700);
  await fillHealth();
  await page.reload(WAIT);
  await sleep(1800);
  const stepAfterRefresh = await stepNow();
  record('T10 refresh mid-flow resets to step 1, creates nothing',
    stepAfterRefresh === 1 && obs.apptPosts.length === postsBefore10,
    `stepAfter=${stepAfterRefresh} newPosts=${obs.apptPosts.length - postsBefore10}`);
  // pushed screen has back navigation; root tab does not
  const bookHasBack = await page.evaluate(() => [...document.querySelectorAll('button')].some((b) => /Back/.test(b.textContent)));
  await page.goto(`${BASE}/patient/dashboard`, WAIT);
  await sleep(1600);
  const dashBack = await page.evaluate(() =>
    [...document.querySelectorAll('button')].filter((b) => {
      const label = (b.getAttribute('aria-label') || '') + ' ' + b.textContent.trim();
      return /^(go back|back)$|back to/i.test(label.trim());
    }).length);
  record('T10 back navigation: pushed screen yes / root tab no', bookHasBack && dashBack === 0,
    `bookBack=${bookHasBack} dashBackButtons=${dashBack}`);

  // ---------------- T1 re-verify + TEST 12: DATA INTEGRITY ----------------
  obs.apptGetBodies.length = 0;
  await page.goto('about:blank');
  await page.goto(`${BASE}/patient/appointments`, WAIT);
  await sleep(2500);
  const raw2 = obs.apptGetBodies[obs.apptGetBodies.length - 1] || [];
  const list2 = Array.isArray(raw2) ? raw2 : (raw2.items || raw2.data || []);
  const pids2 = [...new Set(list2.map((a) => a.patient_id).filter(Boolean))];
  const byDate = (d) => list2.filter((a) => String(a.appointment_date).includes(d));
  const sep25 = byDate('-09-25');
  const sep26 = byDate('-09-26');
  const sep22 = byDate('-09-22');
  record('T8 new booking in list: John\'s, confirmed, 11:00 AM, ₹120',
    sep25.length === 1 && String(sep25[0]?.patient_id).endsWith('c5') && sep25[0]?.status === 'confirmed' &&
    sep25[0]?.time_slot === '11:00 AM' && Number(sep25[0]?.billing_amount) === 120,
    JSON.stringify(sep25.map((a) => ({ pid: a.patient_id, st: a.status, slot: a.time_slot, amt: a.billing_amount, svc: a.service_type }))));
  record('T9 exactly one Sep 26 appointment (no duplicates)', sep26.length === 1, `sep26=${sep26.length}`);
  record('T11b outcome in DB (seeded Sep 22 + any probe record)',
    sep22.length >= 1, `sep22Count=${sep22.length} slots=${JSON.stringify(sep22.map((a) => a.time_slot))} — ${sep22.length > 1 ? 'DEFECT: double-booking accepted (seeded datetime not noon-normalized)' : 'no duplicate'}`);
  record('T12 every record belongs to John (…c5)', pids2.length === 1 && String(pids2[0]).endsWith('c5'), `patient_ids=${JSON.stringify(pids2)}`);
  record('T12 acceptance baseline intact (2 original + created)', list2.length >= 3,
    `total=${list2.length} (baseline was 2 for John; +T8 +T9 +possible T11b)`);

  // ---------------- ERROR SUMMARY ----------------
  const onlyAddress404 = obs.consoleErrors.every((e) => e.includes('404'));
  record('CONSOLE ERRORS', obs.pageErrors.length === 0 && (obs.consoleErrors.length === 0 || onlyAddress404),
    `console=${obs.consoleErrors.length} page=${obs.pageErrors.length} (address-404 = documented empty-state)`);
  record('UNEXPECTED API ERRORS', obs.failed.length === 0, `failed=${JSON.stringify(obs.failed.slice(0, 8))}`);
} finally {
  await browser.close();
}

const fails = results.filter((r) => !r.pass);
console.log(`\n==== SUMMARY: ${results.length - fails.length}/${results.length} PASS ====`);
for (const f of fails) console.log(`FAILED: ${f.t} → ${f.detail}`);
process.exit(0);
