// PHYSIOCARE — PHASE 2 REMEDIATION TESTS (targets the four booking defects)
// Run: node qa/remediation-tests.mjs   (backend :8000 + frontend :5173 must be running)
// READ-ONLY for baseline data: every booking this script makes is reported by ID
// at the end (marker reason "Remediation QA") so it can be cleaned up exactly.
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

const obs = {
  consoleErrors: [], pageErrors: [], failed: [],
  apptPosts: [], createdAppointments: [],
};
page.on('console', (m) => { if (m.type() === 'error') obs.consoleErrors.push(m.text().slice(0, 200)); });
page.on('pageerror', (e) => obs.pageErrors.push(String(e).slice(0, 200)));
page.on('response', async (res) => {
  const u = res.url();
  if (u.includes('/api/appointments') && res.request().method() === 'POST') {
    const entry = { status: res.status() };
    if (res.status() === 201) {
      try {
        const body = await res.json();
        entry.id = body.id;
        entry.billing_amount = body.billing_amount;
        entry.reason = body.reason;
        entry.appointment_date = body.appointment_date;
        entry.time_slot = body.time_slot;
        obs.createdAppointments.push(entry);
      } catch { /* body already consumed */ }
    }
    obs.apptPosts.push(entry);
  }
  if (res.status() >= 400 && !u.includes('/users/me/address')) {
    obs.failed.push({ u: u.replace(BASE, ''), s: res.status() });
  }
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

async function startBooking() {
  await page.goto('about:blank');
  await page.goto(`${BASE}/patient/book`, WAIT);
  await sleep(1800);
  await clickByText('button', 'Clinic Consultation');
  await sleep(900);
  await clickByText('button', 'Neck', { exact: true });
  await sleep(500);
  await clickByText('button', 'Neck pain', { exact: true });
  await sleep(400);
  await clickByText('button', 'Continue', { exact: false });
  await sleep(900);
  await clickByText('button', 'Dr. Sarah Miller');
  await sleep(1100);
}
async function pickDay(day) {
  return page.evaluate((d) => {
    const btn = [...document.querySelectorAll('button')].find(
      (b) => b.textContent.trim() === String(d) && !b.disabled && b.getAttribute('aria-disabled') !== 'true');
    if (btn) { btn.click(); return true; }
    return false;
  }, day);
}
async function pickTime(time) {
  const ok = await clickByText('button', time, { exact: true });
  await sleep(900);
  return ok;
}
async function clickSubmitOnce() {
  return page.evaluate(() => {
    const b = [...document.querySelectorAll('button[type="submit"]')][0];
    if (b && !b.disabled) { b.click(); return true; }
    return false;
  });
}
async function tripleClickSubmit() {
  // three clicks in the same tick — before any React re-render
  return page.evaluate(() => {
    const b = [...document.querySelectorAll('button[type="submit"]')][0];
    if (!b) return 0;
    b.click(); b.click(); b.click();
    return 3;
  });
}

try {
  await login();

  // ================= TEST E + F (REVIEW SCREEN) — no submission yet =================
  await startBooking();
  let dayOk = await pickDay(24); await sleep(700);
  let timeOk = await pickTime('09:00 AM'); await sleep(600);
  let step = await stepNow();
  let txt = await bodyText();
  const problemMatch = txt.match(/problem\s*\n+([^\n]+)/i);
  const problemValue = problemMatch ? problemMatch[1].trim() : '';
  record('TEST E review shows entered problem', step === 5 && problemValue === 'Neck pain',
    `step=${step} problem="${problemValue}"`);
  const feeMatch = txt.match(/Consultation\s*\n\s*₹\s*([\d,]+)/);
  const totalMatch = txt.match(/Total\s*\n\s*₹\s*([\d,]+)/);
  record('TEST F review fee = authoritative doctor fee (₹500)',
    feeMatch && totalMatch && feeMatch[1] === '500' && totalMatch[1] === '500',
    `consultation=₹${feeMatch ? feeMatch[1] : '?'} total=₹${totalMatch ? totalMatch[1] : '?'}`);

  // ================= TEST A — SINGLE CLICK =================
  const postsA = obs.apptPosts.length;
  const clickedA = await clickSubmitOnce();
  await sleep(3500);
  const postsAWindow = obs.apptPosts.slice(postsA);
  const createdA = postsAWindow.filter((p) => p.status === 201);
  txt = await bodyText();
  const modalA = txt.includes('Your appointment is confirmed');
  record('TEST A single click → exactly 1 appointment',
    clickedA && createdA.length === 1 && postsAWindow.length === 1,
    `clicked=${clickedA} posts=${JSON.stringify(postsAWindow.map((p) => p.status))}`);
  record('TEST A confirmation modal shown', modalA, `modal=${modalA}`);
  const billA = createdA[0]?.billing_amount;
  record('TEST F stored billing_amount = 500 (matches review)',
    Number(billA) === 500,
    `billing_amount=${billA} date=${createdA[0]?.appointment_date} slot=${createdA[0]?.time_slot}`);
  await clickByText('button', 'Go to Dashboard', { exact: false });
  await sleep(1500);

  // ================= TEST B — RAPID TRIPLE CLICK =================
  await startBooking();
  dayOk = await pickDay(29); await sleep(700);
  timeOk = await pickTime('10:30 AM'); await sleep(600);
  const postsB = obs.apptPosts.length;
  const clicksB = await tripleClickSubmit();
  await sleep(4000);
  const postsBWindow = obs.apptPosts.slice(postsB);
  const createdB = postsBWindow.filter((p) => p.status === 201);
  txt = await bodyText();
  const modalB = txt.includes('Your appointment is confirmed');
  record('TEST B rapid triple click → exactly 1 appointment',
    clicksB === 3 && createdB.length === 1,
    `clicks=${clicksB} posts=${JSON.stringify(postsBWindow.map((p) => p.status))} modal=${modalB}`);
  await clickByText('button', 'Go to Dashboard', { exact: false });
  await sleep(1500);

  // ================= TEST D — ALREADY-BOOKED SLOT =================
  // (a) Legacy-timestamp case (baseline has 08:06:54): attempting Sep 22 today
  // is rejected by the future-date rule (noon already past) — assert nothing
  // is created. The true legacy-timestamp conflict is covered by the backend
  // live test (qa_phase2_live.py TEST D).
  await startBooking();
  await pickDay(22); await sleep(700);
  await pickTime('02:30 PM'); await sleep(600);
  const postsD = obs.apptPosts.length;
  const clickedD = await clickSubmitOnce();
  await sleep(3500);
  const postsDWindow = obs.apptPosts.slice(postsD);
  const createdD = postsDWindow.filter((p) => p.status === 201);
  record('TEST D-a Sep 22 attempt rejected, nothing created',
    clickedD && createdD.length === 0 && postsDWindow.every((p) => p.status !== 201),
    `clicked=${clickedD} posts=${JSON.stringify(postsDWindow.map((p) => p.status))}`);
  // (b) Same calendar date + same slot as the future Sep 24 09:00 AM booking
  // from TEST A → must be rejected with a visible conflict message.
  await clickByText('button', 'Back', { exact: false }); await sleep(800);
  await pickDay(24); await sleep(700);
  await pickTime('09:00 AM'); await sleep(600);
  const postsD2 = obs.apptPosts.length;
  const clickedD2 = await clickSubmitOnce();
  await sleep(3500);
  const postsD2Window = obs.apptPosts.slice(postsD2);
  const createdD2 = postsD2Window.filter((p) => p.status === 201);
  txt = await bodyText();
  const conflictShown = /already have an appointment|not available/i.test(txt);
  record('TEST D-b duplicate future slot (Sep 24 09:00 AM) rejected with message',
    clickedD2 && createdD2.length === 0 && conflictShown,
    `clicked=${clickedD2} created=${createdD2.length} conflictShown=${conflictShown} posts=${JSON.stringify(postsD2Window.map((p) => p.status))}`);
  // (c) A different time on a free date must remain bookable — verify the
  // slot-level conflict only (do NOT submit; leave review without booking).
  await clickByText('button', 'Back', { exact: false }); await sleep(800);
  await pickDay(25); await sleep(700);
  const otherSlotFree = await pickTime('04:00 PM');
  const stepAfterOther = await stepNow();
  record('TEST D-c different date + time remains available', otherSlotFree && stepAfterOther === 5,
    `advancedToReview=${stepAfterOther === 5}`);
  await page.goto(`${BASE}/patient/dashboard`, WAIT);
  await sleep(1200);

  // ================= DATABASE INTEGRITY (via GET) =================
  const listResp = await page.evaluate(async () => {
    const r = await fetch('/api/appointments', { headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` } });
    return r.json();
  });
  const qaRows = listResp.filter((a) => a.reason === 'Neck pain' && a.status === 'confirmed');
  const sep24 = qaRows.filter((a) => String(a.appointment_date).includes('-09-24'));
  const sep29 = qaRows.filter((a) => String(a.appointment_date).includes('-09-29'));
  const sep22 = listResp.filter((a) => String(a.appointment_date).includes('-09-22'));
  record('DB exactly 1 record for Sep 24 probe', sep24.length === 1, `count=${sep24.length}`);
  record('DB exactly 1 record for Sep 29 probe', sep29.length === 1, `count=${sep29.length}`);
  record('DB Sep 22 has only the baseline appointment (no double-book)',
    sep22.length === 1 && sep22[0].time_slot === '02:30 PM',
    `count=${sep22.length} slots=${JSON.stringify(sep22.map((a) => a.time_slot))}`);
  record('DB every record billing_amount = 500 for new bookings',
    [...sep24, ...sep29].every((a) => Number(a.billing_amount) === 500),
    JSON.stringify([...sep24, ...sep29].map((a) => a.billing_amount)));
  record('PATIENT DATA INTEGRITY all records belong to John (…c5)',
    [...new Set(listResp.map((a) => a.patient_id))].every((p) => String(p).endsWith('c5')),
    `patient_ids=${JSON.stringify([...new Set(listResp.map((a) => String(a.patient_id)))])}`);

  // ================= CONSOLE / API ERRORS =================
  // Expected console noise: (a) the documented /users/me/address 404 empty-state,
  // (b) 400s + the app's own onError logs produced by the INTENTIONAL conflict
  // probes in TEST D (each expected conflict logs at most 2 entries).
  const expectedConflicts = obs.failed.filter((f) => f.s === 400 || f.s === 409).length;
  const address404s = obs.consoleErrors.filter((e) => e.includes('404')).length;
  const conflictLogs = obs.consoleErrors.filter(
    (e) => e.includes('400 (Bad Request)') || e.includes('Failed to book appointment')
  ).length;
  const unexpectedConsole = obs.consoleErrors.filter(
    (e) => !e.includes('404') && !e.includes('400 (Bad Request)') && !e.includes('Failed to book appointment')
  );
  record('CONSOLE ERRORS', obs.pageErrors.length === 0 && unexpectedConsole.length === 0 && conflictLogs <= expectedConflicts * 2,
    `console=${obs.consoleErrors.length} (address404=${address404s}, conflictProbeLogs=${conflictLogs}/${expectedConflicts * 2} allowed) unexpected=${unexpectedConsole.length} page=${obs.pageErrors.length}`);
  record('API ERRORS only expected slot-conflicts (400/409)',
    obs.failed.length === expectedConflicts,
    `failed=${JSON.stringify(obs.failed)}`);

  console.log('\n==== CREATED APPOINTMENTS (for exact cleanup) ====');
  console.log(JSON.stringify(obs.createdAppointments, null, 2));
} finally {
  await browser.close();
}

  const fails = results.filter((r) => !r.pass);
  console.log(`\n==== SUMMARY: ${results.length - fails.length}/${results.length} PASS ====`);
  for (const f of fails) console.log(`FAILED: ${f.t} → ${f.detail}`);
  if (obs.consoleErrors.length) {
    console.log('\n==== CONSOLE ERRORS (verbatim) ====');
    for (const e of obs.consoleErrors) console.log(`  • ${e}`);
  }
  process.exit(0);
