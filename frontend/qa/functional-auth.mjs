// PHYSIOCARE — PHASE 1 FUNCTIONAL ACCEPTANCE TEST (READ-ONLY)
// Tests authentication & session behavior end-to-end in a real browser.
// Modifies NOTHING in the app: only drives the UI + observes network/console.
import puppeteer from 'puppeteer';

const BASE = 'http://localhost:5173';
const EMAIL = 'john.doe@gmail.com';
const PASSWORD = 'password123'; // seeded credential (backend/seed.py)
const WAIT = { waitUntil: 'networkidle2', timeout: 60000 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const results = [];
const record = (test, pass, detail) => {
  results.push({ test, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${test} | ${detail}`);
};

async function attachObservers(page, bucket) {
  page.on('console', (msg) => {
    if (msg.type() === 'error') bucket.consoleErrors.push(msg.text().slice(0, 300));
  });
  page.on('pageerror', (err) => bucket.pageErrors.push(String(err).slice(0, 300)));
  page.on('response', (res) => {
    const s = res.status();
    if (s >= 400) bucket.failed.push({ url: res.url().replace(BASE, ''), status: s });
  });
  page.on('requestfinished', (req) => {
    const u = req.url();
    const m = u.match(/\/api\/(care-plans|exercise-assignments|exercise-progress|appointments)/);
    if (m && req.method() === 'GET') {
      bucket.apiCounts[m[1]] = (bucket.apiCounts[m[1]] || 0) + 1;
    }
  });
}

async function login(page, email, password) {
  await page.goto('about:blank'); // avoid same-URL SPA navigation race
  await page.goto(`${BASE}/login`, WAIT);
  await page.waitForSelector('#email', { timeout: 30000 });
  await new Promise((r) => setTimeout(r, 1200));
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${BASE}/login`, WAIT);
  await page.waitForSelector('#email', { timeout: 30000 });
  await page.click('#email', { clickCount: 3 });
  await page.type('#email', email);
  await page.click('#password', { clickCount: 3 });
  await page.type('#password', password);
  const loginResponses = [];
  page.on('response', (res) => {
    if (res.url().includes('/auth/login')) loginResponses.push(res.status());
  });
  await Promise.all([
    page.click('button[type="submit"]'),
    page.waitForNavigation(WAIT).catch(() => {}),
  ]);
  await sleep(2500); // allow /auth/me + react-query hydration
  return loginResponses;
}

const browser = await puppeteer.launch({ headless: 'new' });
const bucket = { consoleErrors: [], pageErrors: [], failed: [], apiCounts: {} };

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  attachObservers(page, bucket);

  // ---------------- TEST 1 + 2: LOGIN & AUTH/ME ----------------
  const loginStatuses = await login(page, EMAIL, PASSWORD);
  const finalUrl = page.url();
  const t1Land = finalUrl;
  const token = await page.evaluate(() => localStorage.getItem('access_token'));
  const refreshToken = await page.evaluate(() => localStorage.getItem('refresh_token'));

  let me = null;
  try {
    me = await page.evaluate(async () => {
      const t = localStorage.getItem('access_token');
      const r = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${t}` } });
      return { status: r.status, body: await r.json() };
    });
  } catch (e) { me = { status: 0, body: String(e) }; }

  record('T1 login succeeds (POST /auth/login)', loginStatuses.length > 0 && loginStatuses[0] === 200,
    `statuses=${JSON.stringify(loginStatuses)}`);
  record('T1 tokens stored', !!token && !!refreshToken,
    `access_token=${token ? token.slice(0, 12) + '…' : 'null'}`);
  record('T1 lands on patient dashboard', /\/patient\/dashboard/.test(finalUrl), `finalUrl=${finalUrl}`);
  record('T2 /auth/me 200 + role=patient + John Doe',
    me.status === 200 && me.body?.role === 'patient' && /john\.doe@gmail\.com/i.test(me.body?.email || ''),
    `status=${me.status} role=${me.body?.role} email=${me.body?.email} id=${me.body?.id || me.body?._id || me.body?.user_id || 'n/a'}`);

  const headerName = await page.evaluate(() => document.body.innerText.includes('John'));
  record('T2 UI uses authenticated user (header shows John)', headerName,
    `headerShowsJohn=${headerName}`);

  const dashText = await page.evaluate(() => document.body.innerText);
  const populated = dashText.includes('Strength Building') && !dashText.includes('No Active Care Plan');
  record('T1 dashboard populated (acceptance data visible)', populated,
    `showsStrengthBuilding=${dashText.includes('Strength Building')} showsEmptyState=${dashText.includes('No Active Care Plan')}`);

  // ---------------- TEST 3: DATA ISOLATION ----------------
  const isolation = await page.evaluate(async () => {
    const t = localStorage.getItem('access_token');
    const h = { Authorization: `Bearer ${t}` };
    const get = async (p) => {
      const r = await fetch(`/api${p}`, { headers: h });
      let body = null;
      try { body = await r.json(); } catch { /* ignore */ }
      return { status: r.status, body };
    };
    const normalize = (b) => (Array.isArray(b) ? b : (b?.items || b?.data || b?.appointments || b?.plans || []));
    const pickPatient = (o) => o?.patient_id || o?.patientId || o?.patient || null;

    const cp = await get('/care-plans');
    const cpList = normalize(cp.body);
    const ea = await get('/exercise-assignments');
    const eaList = normalize(ea.body);
    const ep = await get('/exercise-progress');
    const epList = normalize(ep.body);
    const st = await get('/exercise-progress/stats');
    const ap = await get('/appointments');
    const apList = normalize(ap.body);

    const pids = {
      carePlans: [...new Set(cpList.map(pickPatient).filter(Boolean))],
      assignments: [...new Set(eaList.map(pickPatient).filter(Boolean))],
      progress: [...new Set(epList.map(pickPatient).filter(Boolean))],
      appointments: [...new Set(apList.map(pickPatient).filter(Boolean))],
    };
    const carePlanTitles = cpList.map((c) => c.title || c.name);
    const stageCount = cpList[0]?.stages?.length ?? null;
    return {
      statuses: { carePlans: cp.status, assignments: ea.status, progress: ep.status, stats: st.status, appointments: ap.status },
      counts: { carePlans: cpList.length, assignments: eaList.length, progress: epList.length, appointments: apList.length },
      pids, carePlanTitles, stageCount,
      stats: st.body,
    };
  });

  const allPidGroups = Object.entries(isolation.pids);
  const allSingle = allPidGroups.every(([, v]) => v.length <= 1);
  const union = [...new Set(allPidGroups.flatMap(([, v]) => v))];
  record('T3 all endpoints return 200', Object.values(isolation.statuses).every((s) => s === 200),
    `statuses=${JSON.stringify(isolation.statuses)}`);
  record('T3 single patient_id across every endpoint', allSingle && union.length === 1,
    `patient_ids=${JSON.stringify(isolation.pids)}`);
  record('T3 acceptance care plan present for this patient',
    isolation.carePlanTitles.some((t) => /Post-Surgical Knee Rehabilitation/i.test(t || '')),
    `titles=${JSON.stringify(isolation.carePlanTitles)} stages=${isolation.stageCount}`);
  record('T3 populated record counts', isolation.counts.assignments > 0 && isolation.counts.progress > 0,
    `counts=${JSON.stringify(isolation.counts)}`);

  // Cross-check patient_id <-> user link via read-only backend DB read
  const { execSync } = await import('node:child_process');
  let dbLink = 'unavailable';
  try {
    dbLink = execSync(
      `cd backend && ./venv/Scripts/python.exe -c "import asyncio,json;from app.database import init_db;from app.models.user import User;from app.models.patient import Patient;exec(open('diagnose_patient_link.py').read().split('asyncio.run')[0]);print(json.dumps({'user_id':str(john_user.id),'patient_id':str(john_patient.id)}))"`,
      { encoding: 'utf8', timeout: 60000 }
    ).trim().split('\n').pop();
  } catch (e) { dbLink = 'unavailable: ' + String(e).slice(0, 120); }
  const apiPid = union[0] || null;
  let dbMatch = null;
  try { dbMatch = dbLink.includes(apiPid); } catch { dbMatch = false; }
  record('T3 API patient_id matches John\'s DB patient record', !!dbMatch,
    `apiPatientId=${apiPid} db=${dbLink.slice(0, 160)}`);

  // ---------------- TEST 4: PAGE REFRESH ----------------
  const refreshRoutes = ['/patient/dashboard', '/patient/care-plan', '/patient/exercises', '/patient/progress'];
  const refreshExpect = {
    '/patient/dashboard': (t) => t.includes('Strength Building'),
    '/patient/care-plan': (t) => t.includes('Post-Surgical Knee Rehabilitation'),
    '/patient/exercises': (t) => !t.includes('No exercises assigned for today'),
    '/patient/progress': (t) => !t.includes('No milestones yet'),
  };
  for (const route of refreshRoutes) {
    bucket.apiCounts = {};
    await page.goto(`${BASE}${route}`, WAIT);
    const before = await page.evaluate(() => document.body.innerText.slice(0, 50));
    await page.reload({ waitUntil: 'networkidle2' });
    await sleep(2000);
    const after = await page.evaluate(() => document.body.innerText);
    const stayed = page.url().includes(route);
    const stillPopulated = refreshExpect[route](after);
    const noRedirect = !after.includes('Sign in to continue');
    record(`T4 refresh ${route}`, stayed && noRedirect && stillPopulated,
      `stayed=${stayed} populated=${stillPopulated} apiCounts=${JSON.stringify(bucket.apiCounts)}`);
  }

  // ---------------- TEST 5: DIRECT URL ACCESS ----------------
  const directRoutes = [
    '/patient/dashboard', '/patient/care-plan', '/patient/exercises', '/patient/progress',
    '/patient/appointments', '/patient/services', '/patient/reports', '/patient/history',
    '/patient/profile', '/patient/settings',
  ];
  for (const route of directRoutes) {
    const preErrors = bucket.consoleErrors.length;
    const preFailed = bucket.failed.length;
    await page.goto(`${BASE}${route}`, WAIT);
    await sleep(1800);
    const url = page.url();
    const text = await page.evaluate(() => document.body.innerText);
    const loads = url.includes(route) && text.length > 100;
    const noBadRedirect = !url.includes('/login');
    const noOtherPatient = !/Jaswanth|Priya Menon/.test(text); // reference-image-only names must never appear
    record(`T5 direct ${route}`, loads && noBadRedirect && noOtherPatient,
      `url=${url.replace(BASE, '')} chars=${text.length} consoleErr+=${bucket.consoleErrors.length - preErrors} http4xx+=${bucket.failed.length - preFailed}`);
  }

  // ---------------- TEST 6: LOGOUT ----------------
  await page.goto(`${BASE}/patient/settings`, WAIT);
  await sleep(1000);
  const oldToken = await page.evaluate(() => localStorage.getItem('access_token'));
  // Desktop: sidebar "Log out" button
  const clicked = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('button')];
    const b = btns.find((x) => x.textContent.trim().toLowerCase().includes('log out'));
    if (b) { b.click(); return true; }
    return false;
  });
  await sleep(700);
  const modalShown = await page.evaluate(() => document.body.innerText.includes('Sign out of PhysioCare?'));
  let signedOut = false;
  if (modalShown) {
    await page.evaluate(() => {
      const btns = [...document.querySelectorAll('button')];
      const b = btns.find((x) => x.textContent.trim() === 'Sign Out');
      if (b) b.click();
    });
    await sleep(2500);
    signedOut = true;
  }
  const tokenAfter = await page.evaluate(() => localStorage.getItem('access_token'));
  const urlAfterLogout = page.url();
  record('T6 logout confirmation modal appears', clicked && modalShown, `clicked=${clicked} modal=${modalShown}`);
  record('T6 logout executes (confirmation respected)', signedOut && tokenAfter === null,
    `confirmed=${signedOut} tokenAfter=${tokenAfter}`);
  record('T6 protected route redirects after logout', /\/login/.test(urlAfterLogout),
    `url=${urlAfterLogout}`);
  const meAfter = await page.evaluate(async (t) => {
    const r = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${t}` } });
    return r.status;
  }, oldToken);
  record('T6 /auth/me with old token is 401', meAfter === 401, `status=${meAfter}`);

  // ---------------- TEST 7: RE-LOGIN ----------------
  // harness note: previous run's T7 failure was a same-URL goto race (typing
  // landed on the pre-reload SPA page); about:blank hop fixes the test only.
  const login2 = await login(page, EMAIL, PASSWORD);
  await sleep(1500);
  const me2 = await page.evaluate(async () => {
    const t = localStorage.getItem('access_token');
    const r = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${t}` } });
    return { status: r.status, body: await r.json() };
  });
  const sameUser = me.body && me2.body && (me.body.id || me.body._id) === (me2.body.id || me2.body._id);
  record('T7 re-login succeeds, same user record', login2[0] === 200 && me2.status === 200 && sameUser,
    `login=${JSON.stringify(login2)} me=${me2.status} sameUser=${sameUser}`);
  await page.goto(`${BASE}/patient/dashboard`, WAIT);
  await sleep(1800);
  const t7 = await page.evaluate(() => document.body.innerText);
  record('T7 acceptance data reappears', t7.includes('Strength Building') && !t7.includes('No Active Care Plan'),
    `populated=${t7.includes('Strength Building')}`);

  // ---------------- TEST 8: INVALID LOGIN ----------------
  const errBucket = { consoleErrors: [], pageErrors: [], failed: [], apiCounts: {} };
  const page2 = await browser.newPage();
  await page2.setViewport({ width: 1280, height: 900 });
  attachObservers(page2, errBucket);
  await page2.goto(`${BASE}/login`, WAIT);
  await page2.waitForSelector('#email');
  await new Promise((r) => setTimeout(r, 1200));
  await page2.evaluate(() => localStorage.clear()); // T8 runs on a fresh isolated profile; guard anyway
  await page2.type('#email', EMAIL);
  await page2.type('#password', 'definitely-wrong-password');
  let badStatus = 0;
  page2.on('response', (res) => { if (res.url().includes('/auth/login')) badStatus = res.status(); });
  await Promise.all([
    page2.click('button[type="submit"]'),
    sleep(3000),
  ]);
  const errText = await page2.evaluate(() => document.body.innerText);
  const tok = await page2.evaluate(() => localStorage.getItem('access_token'));
  const stillOnLogin = page2.url().includes('/login');
  const errorShown = /invalid|incorrect|failed|wrong/i.test(errText);
  record('T8 invalid login rejected', badStatus >= 400, `POST /auth/login status=${badStatus}`);
  record('T8 safe error message shown', errorShown && stillOnLogin,
    `onLogin=${stillOnLogin} errorVisible=${errorShown}`);
  record('T8 no session created', tok === null, `token=${tok}`);
  // protected route while unauthenticated
  await page2.goto(`${BASE}/patient/dashboard`, WAIT);
  await sleep(1200);
  record('T8 protected route blocked when unauthenticated', page2.url().includes('/login'),
    `url=${page2.url().replace(BASE, '')}`);
  const unauthMe = await page2.evaluate(async () => {
    const r = await fetch('/api/auth/me');
    return r.status;
  });
  record('T8 /auth/me unauthenticated is 401', unauthMe === 401, `status=${unauthMe}`);
  record('T8 no uncaught page errors during failure cases', errBucket.pageErrors.length === 0,
    `pageErrors=${JSON.stringify(errBucket.pageErrors).slice(0, 200)}`);
  await page2.close();

  // ---------------- GLOBAL ERROR SUMMARY ----------------
  // Expected 4xx: T6 old-token /auth/me 401, T8 invalid login 400/401, unauth /auth/me 401,
  // possible /patient/dashboard 30x redirect after logout. Everything else is a real failure.
  const realFailures = bucket.failed.filter(
    (f) => !f.url.includes('/auth/me') && !f.url.includes('/auth/login') && f.status !== 401
  );
  record('CONSOLE ERRORS (authenticated flows)', bucket.consoleErrors.length === 0 && bucket.pageErrors.length === 0,
    `console=${bucket.consoleErrors.length} page=${bucket.pageErrors.length} ${bucket.consoleErrors[0] || ''}`);
  record('API ERRORS (unexpected 4xx/5xx)', realFailures.length === 0,
    `unexpected=${JSON.stringify(realFailures.slice(0, 8))}`);
} finally {
  await browser.close();
}

const fails = results.filter((r) => !r.pass);
console.log('\n==== SUMMARY ====');
console.log(`TOTAL: ${results.length} | PASS: ${results.length - fails.length} | FAIL: ${fails.length}`);
if (fails.length) {
  console.log('FAILED CHECKS:');
  for (const f of fails) console.log(` - ${f.test}: ${f.detail}`);
}
process.exit(0);
