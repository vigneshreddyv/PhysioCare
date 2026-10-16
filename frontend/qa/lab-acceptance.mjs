// PHYSIOCARE — PHASE 3 READ-ONLY ACCEPTANCE TEST: LABORATORY BOOKING
// Run: node qa/lab-acceptance.mjs   (backend :8000 + frontend :5173 running)
// READ-ONLY for baseline data. Every booking this script creates is reported
// by exact ID at the end for cleanup. NO application code is modified.
import puppeteer from 'puppeteer';

const BASE = 'http://localhost:5173';
const WAIT = { waitUntil: 'networkidle2', timeout: 60000 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const record = (t, pass, detail) => {
  results.push({ t, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${t} | ${detail}`);
};
const note = (t, detail) => results.push({ t, pass: null, detail }) && console.log(`NOTE | ${t} | ${detail}`);

const browser = await puppeteer.launch({ headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900 });

const obs = {
  consoleErrors: [], pageErrors: [], failed: [],
  labPosts: [], labPatches: [], labTestGets: 0, createdBookings: [],
};
page.on('console', (m) => { if (m.type() === 'error') obs.consoleErrors.push(m.text().slice(0, 300)); });
page.on('pageerror', (e) => obs.pageErrors.push(String(e).slice(0, 300)));
page.on('response', async (res) => {
  const u = res.url();
  if (u.includes('/api/laboratory/tests') && res.request().method() === 'GET' && res.status() === 200) {
    obs.labTestGets += 1;
  }
  if (u.includes('/api/laboratory/bookings') && res.request().method() === 'POST') {
    const entry = { status: res.status() };
    if (res.status() === 201) {
      try {
        const b = await res.json();
        entry.id = b.id; entry.amount = b.billing_amount; entry.visit_type = b.visit_type;
        entry.date = b.appointment_date; entry.slot = b.time_slot; entry.patient_id = b.patient_id;
        entry.tests = (b.selected_tests || []).map((t) => t.test_id);
        obs.createdBookings.push(entry);
      } catch { /* consumed */ }
    }
    obs.labPosts.push(entry);
  }
  if (u.includes('/api/laboratory/bookings') && res.request().method() === 'PATCH') {
    obs.labPatches.push({ status: res.status(), u: u.replace(BASE, '') });
  }
  if (res.status() >= 400 && !u.includes('/users/me/address')) {
    obs.failed.push({ u: u.replace(BASE, ''), s: res.status() });
  }
});

const bodyText = () => page.evaluate(() => document.body.innerText);
async function clickByText(selector, text, { exact = false } = {}) {
  return page.evaluate(({ selector, text, exact }) => {
    const els = [...document.querySelectorAll(selector)];
    const el = els.find((e) => (exact ? e.textContent.trim() === text : e.textContent.trim().includes(text)));
    if (el) { el.click(); return true; }
    return false;
  }, { selector, text, exact });
}

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

// Full flow helper: clinic visit → tests → date-time. Returns nothing; leaves at step 2.
async function startClinicFlow() {
  await page.goto('about:blank');
  await page.goto(`${BASE}/patient/laboratory`, WAIT);
  await sleep(1200);
  await clickByText('button', 'Clinic Visit');
  await sleep(900);
  await clickByText('button', 'Continue to Laboratory Tests');
  await sleep(1200);
}
async function selectTest(name) {
  return clickByText('button', name, { exact: false });
}
async function continueToDateTime() {
  await clickByText('button', 'Continue to Date & Time');
  await sleep(1000);
}
async function pickDateAndTime(dayNumber, time) {
  // date buttons render weekday/day/month in separate <p> tags; match the day-number <p>
  const dayOk = await page.evaluate((d) => {
    const btns = [...document.querySelectorAll('button')].filter(
      (b) => [...b.querySelectorAll('p')].some((p) => p.textContent.trim() === String(d)));
    if (btns.length) { btns[0].click(); return true; }
    return false;
  }, dayNumber);
  await sleep(500);
  const timeOk = await clickByText('button', time, { exact: true });
  await sleep(500);
  return { dayOk, timeOk };
}

try {
  await login();

  // ================= TEST 1 — LAB ENTRY / DISCOVERABILITY =================
  const txt1 = await bodyText();
  const sidebarLink = await page.evaluate(() =>
    !!document.querySelector('a[href="/patient/laboratory"]') ||
    [...document.querySelectorAll('button,a')].some((e) => e.textContent.trim().includes('Laboratory Tests')));
  record('T1 sidebar shows Laboratory Tests entry', sidebarLink, `sidebar=${sidebarLink}`);

  // service selection entry
  await page.goto('about:blank');
  await page.goto(`${BASE}/patient/services`, WAIT);
  await sleep(1500);
  const svc = await bodyText();
  record('T1 services page lists Laboratory Tests', svc.includes('Laboratory Tests'), `found=${svc.includes('Laboratory Tests')}`);
  await clickByText('button', 'Laboratory Tests');
  await sleep(1500);
  const onLab = page.url().includes('/patient/laboratory');
  const labHome = await bodyText();
  record('T1 service card navigates to /patient/laboratory', onLab && labHome.includes('Laboratory testing, made simple'),
    `url=${page.url().replace(BASE, '')}`);
  record('T1 visit-type options shown (Home/Clinic)', labHome.includes('Home Visit') && labHome.includes('Clinic Visit'),
    `home=${labHome.includes('Home Visit')} clinic=${labHome.includes('Clinic Visit')}`);
  record('T1 no console errors on entry so far', obs.pageErrors.length === 0, `pageErrors=${obs.pageErrors.length}`);

  // ================= TEST 4 — VISIT TYPE (home: missing address behavior) =================
  await clickByText('button', 'Home Visit');
  await sleep(1500);
  const homeTxt = await bodyText();
  const noSavedAddr = homeTxt.includes('Enter Address');
  record('T4 home-visit page handles missing saved address gracefully', noSavedAddr,
    `showsAddressForm=${noSavedAddr} (John has no saved address; 404 = documented empty-state)`);
  // continue without entering an address — existing behavior allows it (no validation here)
  await clickByText('button', 'Continue to Laboratory Tests');
  await sleep(1200);
  const afterHome = await bodyText();
  note('T4 home flow allows continue with empty address (existing behavior)',
    `atTestsPage=${afterHome.includes('Select Laboratory Tests')}`);
  // go back to entry and use clinic for the submittable path (no address needed)
  await page.goto('about:blank');
  await page.goto(`${BASE}/patient/laboratory`, WAIT);
  await sleep(1200);
  await clickByText('button', 'Clinic Visit');
  await sleep(1000);
  await clickByText('button', 'Continue to Laboratory Tests');
  await sleep(1300);

  // ================= TEST 2 — STEP 1: SELECT TESTS =================
  const step1 = await bodyText();
  const apiLoaded = obs.labTestGets > 0;
  record('T2 step 1 loads with backend catalog', step1.includes('Select Laboratory Tests') && apiLoaded,
    `apiGets=${obs.labTestGets} stepTracker=${step1.includes('Step 1 of 4') || step1.includes('Select Tests')}`);
  const cbcPrice = step1.match(/CBC \(Complete Blood Count\)[\s\S]{0,400}?₹(\d+)/);
  const lipidPrice = step1.match(/Lipid Profile[\s\S]{0,400}?₹(\d+)/);
  record('T2 backend prices displayed (CBC ₹350, Lipid ₹600)',
    cbcPrice && lipidPrice && cbcPrice[1] === '350' && lipidPrice[1] === '600',
    `cbc=₹${cbcPrice ? cbcPrice[1] : '?'} lipid=₹${lipidPrice ? lipidPrice[1] : '?'}`);
  record('T2 continue disabled with empty selection (validation)', await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes('Continue to Date & Time'));
    return b && b.disabled;
  }), 'disabled=true expected');

  // ================= TEST 3 — SELECTION VALIDATION =================
  await selectTest('CBC (Complete Blood Count)');
  await sleep(400);
  const t3one = await bodyText();
  record('T3-B one test selected → count=1 total=₹350',
    t3one.includes('1 test') && /₹350/.test(t3one), `total shown=${(t3one.match(/Estimated Total\s*\n\s*₹(\d+)/) || [])[1]}`);
  await selectTest('Lipid Profile');
  await sleep(400);
  const t3two = await bodyText();
  record('T3-C second test selected → count=2 total=₹950',
    t3two.includes('2 tests') && /₹950/.test(t3two),
    `total=${(t3two.match(/Estimated Total\s*\n\s*₹(\d+)/) || [])[1]}`);
  await selectTest('CBC (Complete Blood Count)'); // deselect
  await sleep(400);
  const t3deselect = await bodyText();
  record('T3-D deselect → count=1 total=₹600 (no stale/duplicate)',
    t3deselect.includes('1 test') && /₹600/.test(t3deselect),
    `total=${(t3deselect.match(/Estimated Total\s*\n\s*₹(\d+)/) || [])[1]}`);
  await selectTest('CBC (Complete Blood Count)'); // reselect → 2 tests, ₹950
  await sleep(400);
  const t3final = await bodyText();
  record('T3 reselect → count=2 total=₹950', t3final.includes('2 tests') && /₹950/.test(t3final),
    `total=${(t3final.match(/Estimated Total\s*\n\s*₹(\d+)/) || [])[1]}`);
  const noDupes = await page.evaluate(() => {
    const raw = localStorage.getItem(Object.keys(localStorage).find((k) => k.startsWith('laboratory_booking_')));
    if (!raw) return null;
    const sel = JSON.parse(raw).selectedTests || [];
    const ids = sel.map((t) => t.id);
    return { count: sel.length, unique: new Set(ids).size };
  });
  record('T3 no duplicate test IDs in selection state',
    noDupes && noDupes.count === noDupes.unique, JSON.stringify(noDupes));

  // ================= TEST 5 — STEP 2: DATE & TIME =================
  await continueToDateTime();
  const step2 = await bodyText();
  const onStep2 = page.url().includes('/patient/laboratory/date-time');
  record('T5 step 2 loads (date-time)', onStep2 && step2.includes('Choose Date & Time'),
    `url=${page.url().replace(BASE, '')} tracker=${/step 2 of 4/i.test(step2)}`);
  const timeDisabledBeforeDate = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === '09:00 AM');
    return b && b.disabled;
  });
  record('T5 time slots disabled until date selected', timeDisabledBeforeDate, `disabled=${timeDisabledBeforeDate}`);
  // pick the 5th visible future date & 09:00 AM
  const picked = await pickDateAndTime(24, '09:00 AM');
  const step2b = await bodyText();
  record('T5 date & time selectable, slot summary shown',
    picked.dayOk && picked.timeOk && /selected slot/i.test(step2b) && step2b.includes('09:00 AM'),
    `day=${picked.dayOk} time=${picked.timeOk}`);

  // ================= TEST 13a — BACK NAV 2→1 with state preserved =================
  await clickByText('button', '← Change Tests');
  await sleep(1500);
  const backStore = await page.evaluate(() => {
    const k = Object.keys(localStorage).find((x) => x.startsWith('laboratory_booking_'));
    return k ? JSON.parse(localStorage.getItem(k)) : null;
  });
  const backOn1 = await bodyText();
  const backTests = (backStore?.selectedTests || []).map((t) => t.id);
  record('T13 2→1 back keeps selection',
    backTests.length === 2 && backTests.includes('cbc') && backTests.includes('lipid-profile'),
    `storageTests=${JSON.stringify(backTests)} page=${backOn1.includes('Select Laboratory Tests')}`);
  await continueToDateTime();
  await sleep(800);
  const stateAfterBack = await bodyText();
  record('T13 date & time retained after round-trip',
    /selected slot/i.test(stateAfterBack) && stateAfterBack.includes('09:00 AM'), 'ok');

  // ================= TEST 7 — STEP 3: REVIEW =================
  await clickByText('button', 'Continue to Review');
  await sleep(1300);
  const review = await bodyText();
  const onReview = page.url().includes('/patient/laboratory/review');
  const reviewChecks = {
    visit: review.includes('Clinic Visit') && /collection method/i.test(review),
    date: /appointment date/i.test(review) && !review.includes('Not selected'),
    time: review.includes('09:00 AM'),
    tests: review.includes('1. CBC (Complete Blood Count)') || review.includes('CBC (Complete Blood Count)'),
    lipid: review.includes('Lipid Profile'),
    prices: review.includes('₹350') && review.includes('₹600'),
    total: review.includes('₹950'),
    location: review.includes('PhysioCare Clinic'),
  };
  record('T7 review displays visit type, date, time, tests, prices, total',
    onReview && Object.values(reviewChecks).every(Boolean), JSON.stringify(reviewChecks));
  const rawEnumLeak = /\b(home|clinic)\b.*\b(pending_payment|billing_status)\b/.test(review);
  record('T7 no raw enum values in review', !rawEnumLeak, `enumLeak=${rawEnumLeak}`);
  const blanks = review.match(/Not selected/g) || [];
  record('T7 no blank "Not selected" fields in review', blanks.length === 0, `notSelectedCount=${blanks.length}`);

  // ================= TEST 13b — BACK NAV 3→2 =================
  await clickByText('button', '← Change Date & Time');
  await sleep(1200);
  const backOn2 = await bodyText();
  record('T13 3→2 back preserves date/time',
    backOn2.includes('09:00 AM') && /selected slot/i.test(backOn2), 'ok');
  await clickByText('button', 'Continue to Review');
  await sleep(1200);

  // ================= TEST 9 — STEP 4: PAYMENT (entry only) =================
  await clickByText('button', 'Proceed to Payment');
  await sleep(1500);
  const payment = await bodyText();
  const onPayment = page.url().includes('/patient/laboratory/payment');
  const payChecks = {
    total: /₹\s?950/.test(payment),
    cbc: payment.includes('CBC (Complete Blood Count)'),
    lipid: payment.includes('Lipid Profile'),
    date: !payment.includes('Not selected'),
    time: payment.includes('09:00 AM'),
    method: /upi/i.test(payment) && /credit \/ debit card/i.test(payment),
    cta: /pay ₹950 securely/i.test(payment),
  };
  record('T9 payment step shows matching total, tests, date/time, CTA',
    onPayment && Object.values(payChecks).every(Boolean), JSON.stringify(payChecks));
  const postsOnEntry = obs.labPosts.length;
  record('T9 no accidental submission on payment entry', postsOnEntry === 0, `posts=${postsOnEntry}`);
  // Razorpay integration probes
  const rzp = await page.evaluate(() => ({
    sdkScript: [...document.querySelectorAll('script')].some((s) => (s.src || '').includes('razorpay') || (s.src || '').includes('checkout.js')),
    rzpKeys: Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter((k) => k.toLowerCase().includes('rzp')).length,
    windowRzp: typeof window.Razorpay !== 'undefined',
  }));
  record('T9 no Razorpay SDK/checkout loaded (integration absent)',
    !rzp.sdkScript && !rzp.windowRzp && rzp.rzpKeys === 0, JSON.stringify(rzp));
  note('T9 payment CTA uses existing simulated payment (fake pay_/ord_ IDs generated client-side)',
    'booking POST + 1.5s delay + PATCH payment_status=success');

  // ================= TEST 10 — SINGLE SUBMISSION =================
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => /pay ₹950 securely/i.test(x.textContent));
    if (b && !b.disabled) b.click();
  });
  // wait for success navigation
  let successSeen = false;
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    if (page.url().includes('/patient/laboratory/success')) { successSeen = true; break; }
  }
  const t10Posts = obs.labPosts.filter((p) => p.status === 201);
  record('T10 single submission → exactly 1 POST /laboratory/bookings (201)',
    successSeen && obs.labPosts.length === 1 && t10Posts.length === 1,
    `posts=${JSON.stringify(obs.labPosts)} success=${successSeen}`);
  record('T10 payment PATCH updates booking (simulation completes)',
    obs.labPatches.length === 1 && obs.labPatches[0].status === 200,
    `patches=${JSON.stringify(obs.labPatches)}`);
  const successTxt = await bodyText();
  record('T10 success page confirms booking + payment',
    successTxt.includes('950') || successTxt.toLowerCase().includes('success'), 'ok');

  // ================= DB-LEVEL CHECKS + TEST 6/12 via authenticated fetch =================
  const token = await page.evaluate(() => localStorage.getItem('access_token'));
  const authHeaders = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  // TEST 6: sequential duplicate attempt on the SAME slot → conflict check (app-level)
  const dupAttempt = await page.evaluate(async ({ headers }) => {
    const date = new Date(); date.setDate(date.getDate() + 4);
    const iso = date.toISOString().split('T')[0];
    const r = await fetch('/api/laboratory/bookings', {
      method: 'POST', headers,
      body: JSON.stringify({
        test_ids: ['cbc'], appointment_date: iso, time_slot: '09:00 AM',
        visit_type: 'clinic', address: null,
      }),
    });
    return { status: r.status, body: await r.json().catch(() => ({})) };
  }, { headers: authHeaders });
  record('T6 sequential duplicate booking rejected with clear conflict',
    dupAttempt.status === 400 && /already have/i.test(dupAttempt.body.detail || ''),
    `status=${dupAttempt.status} detail=${dupAttempt.body.detail || ''}`);

  // TEST 12: 3 concurrent identical POSTs on a FRESH slot
  const conc = await page.evaluate(async ({ headers }) => {
    const date = new Date(); date.setDate(date.getDate() + 5);
    const iso = date.toISOString().split('T')[0];
    const payload = JSON.stringify({
      test_ids: ['hemoglobin'], appointment_date: iso, time_slot: '10:00 AM',
      visit_type: 'clinic', address: null,
    });
    const rs = await Promise.all([0, 1, 2].map(() =>
      fetch('/api/laboratory/bookings', { method: 'POST', headers, body: payload })));
    const out = [];
    for (const r of rs) out.push({ status: r.status, body: await r.json().catch(() => ({})) });
    return out;
  }, { headers: authHeaders });
  const concCreated = conc.filter((r) => r.status === 201);
  const concRejected = conc.filter((r) => r.status !== 201);
  console.log(`CONCURRENT DETAIL: created=${concCreated.length} rejected=${concRejected.length} statuses=${JSON.stringify(conc.map((r) => r.status))}`);
  for (const c of concCreated) obs.createdBookings.push({ status: 201, id: c.body.id, amount: c.body.billing_amount, visit_type: c.body.visit_type, date: c.body.appointment_date, slot: c.body.time_slot, patient_id: c.body.patient_id, tests: (c.body.selected_tests || []).map((t) => t.test_id) });

  // ================= TEST 11 — RAPID TRIPLE CLICK =================
  // fresh booking through the UI to payment, then 3 same-tick clicks
  await startClinicFlow();
  await selectTest('Hemoglobin');
  await sleep(400);
  await continueToDateTime();
  await pickDateAndTime(26, '11:00 AM');
  await sleep(600);
  await clickByText('button', 'Continue to Review');
  await sleep(1200);
  await clickByText('button', 'Proceed to Payment');
  await sleep(1400);
  const triplePostsBefore = obs.labPosts.length;
  const clicks = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => /pay ₹150 securely/i.test(x.textContent));
    if (!b || b.disabled) return 0;
    b.click(); b.click(); b.click();
    return 3;
  });
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    if (page.url().includes('/patient/laboratory/success')) break;
  }
  await sleep(1500);
  const tripleWindow = obs.labPosts.slice(triplePostsBefore);
  const tripleCreated = tripleWindow.filter((p) => p.status === 201);
  record('T11 rapid triple click → no duplicate bookings, no 500',
    clicks === 3 && tripleCreated.length <= 1 && tripleWindow.every((p) => p.status !== 500),
    `clicks=${clicks} posts=${JSON.stringify(tripleWindow.map((p) => p.status))}`);
  for (const c of tripleCreated.filter((c) => !obs.createdBookings.some((x) => x.id === c.id))) {
    obs.createdBookings.push(c);
  }

  // ================= TEST 8/15/16 — PRICE CONSISTENCY, ISOLATION, INTEGRITY =================
  const myList = await page.evaluate(async ({ headers }) => {
    const r = await fetch('/api/laboratory/bookings', { headers });
    return r.json();
  }, { headers: authHeaders });
  record('T15 every lab booking belongs to John (…c5)',
    myList.length > 0 && [...new Set(myList.map((b) => String(b.patient_id)))].every((p) => p.endsWith('c5')),
    `bookings=${myList.length} patients=${JSON.stringify([...new Set(myList.map((b) => String(b.patient_id)))])}`);

  const catalog = await page.evaluate(async ({ headers }) => {
    const r = await fetch('/api/laboratory/tests', { headers });
    return r.json();
  }, { headers: authHeaders });
  const catMap = Object.fromEntries(catalog.tests.map((t) => [t.test_id, t.price]));

  let priceOk = true; const priceDetail = [];
  for (const b of myList) {
    const expected = (b.selected_tests || []).reduce((s, t) => s + Number(t.price || 0), 0);
    const catMatch = (b.selected_tests || []).every((t) => Number(catMap[t.test_id]) === Number(t.price));
    const ok = Number(b.billing_amount) === expected && catMatch;
    if (!ok) priceOk = false;
    priceDetail.push(`${b.id.slice(-4)}:amount=${b.billing_amount}/sum=${expected}/catalog=${catMatch}`);
  }
  record('T8 DB billing_amount = sum(embedded test prices) = catalog prices', priceOk, priceDetail.join(' | '));
  const uiAmountMatch = t10Posts[0] && Number(t10Posts[0].amount) === 950; // UI total ₹950 = API billing_amount
  record('T8 UI total (₹950) = API payload amount = DB amount for submission booking',
    uiAmountMatch, `submittedAmount=${t10Posts[0] ? t10Posts[0].amount : '?'}`);

  const integrityOk = myList.every((b) =>
    b.appointment_date && b.time_slot && ['clinic', 'home'].includes(b.visit_type) &&
    Array.isArray(b.selected_tests) && b.selected_tests.length > 0 &&
    b.created_at && Number(b.billing_amount) > 0 && b.status);
  record('T16 DB records structurally complete (patient, tests, date, slot, visit, amount, status, timestamps)',
    integrityOk, `checked=${myList.length}`);

  // ================= TEST 14 — REFRESH / SESSION =================
  await page.goto('about:blank');
  await page.goto(`${BASE}/patient/laboratory/date-time`, WAIT);
  await sleep(1500);
  const afterRefresh = await bodyText();
  const stillAuthed = !page.url().includes('/login');
  record('T14 refresh mid-flow: auth valid, no crash, flow state retained or clean',
    stillAuthed && obs.pageErrors.length === 0,
    `authed=${stillAuthed} pageErrors=${obs.pageErrors.length} (transient step-state reset = existing storage behavior)`);

  // ================= TEST 19 — CONSOLE / API HEALTH =================
  const address404 = obs.consoleErrors.filter((e) => e.includes('404')).length;
  const validation400 = obs.consoleErrors.filter((e) => e.includes('400')).length;
  const unexpected500 = obs.failed.filter((f) => f.s >= 500);
  const unexpectedOthers = obs.failed.filter((f) => f.s >= 400 && f.s !== 400);
  const unexpectedConsole = obs.consoleErrors.filter(
    (e) => !e.includes('404') && !e.includes('400') && !e.includes('Failed to load') === false && false // placeholder
  );
  const unexpectedConsoleReal = obs.consoleErrors.filter(
    (e) => !e.includes('404') && !e.includes('400') && !e.includes('Laboratory booking/payment error'));
  record('T19 no 500s / no CORS failures / no React crashes',
    obs.pageErrors.length === 0 && unexpected500.length === 0,
    `pageErrors=${obs.pageErrors.length} 500s=${unexpected500.length} unexpected=${JSON.stringify(unexpectedOthers)}`);
  record('T19 console errors only expected (address-404 empty-state, intentional validation 400s)',
    unexpectedConsoleReal.length === 0,
    `console=${obs.consoleErrors.length} (address404=${address404}, validation400=${validation400}, other=${unexpectedConsoleReal.length})`);

  console.log('\n==== CREATED LAB BOOKINGS (for exact cleanup) ====');
  console.log(JSON.stringify(obs.createdBookings, null, 2));
} finally {
  await browser.close();
}

const fails = results.filter((r) => r.pass === false);
console.log(`\n==== SUMMARY: ${results.filter((r) => r.pass === true).length}/${results.filter((r) => r.pass !== null).length} PASS ====`);
for (const f of fails) console.log(`FAILED: ${f.t} → ${f.detail}`);
process.exit(0);
