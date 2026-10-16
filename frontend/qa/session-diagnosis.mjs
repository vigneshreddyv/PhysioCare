// READ-ONLY session diagnosis — reproduces the user's browser flow and captures
// the ACTUAL API responses the React app receives for the four clinical endpoints.
import puppeteer from 'puppeteer';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const BASE = 'http://localhost:5174';

const b = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
const p = await b.newPage();

const captured = [];
p.on('response', async (res) => {
  const url = res.request().url();
  if (/\/api\/(care-plans|exercise-assignments|exercise-progress\/stats|appointments|auth\/me)/.test(url)) {
    let body;
    try { body = await res.json(); } catch { body = '<non-json>'; }
    captured.push({
      url: url.replace(BASE, ''),
      status: res.status(),
      summary: Array.isArray(body)
        ? `${body.length} records; first patient_id=${body[0]?.patient_id ?? 'n/a'}`
        : (body && typeof body === 'object')
        ? `keys=${Object.keys(body).slice(0, 8).join(',')}; completed=${body.completed ?? '?'}; active=${body.active_assignments ?? '?'}`
        : String(body).slice(0, 80),
    });
  }
});

await p.setViewport({ width: 375, height: 812, isMobile: true, hasTouch: true });
await p.goto(`${BASE}/login`, { waitUntil: 'networkidle0', timeout: 60000 });
await p.type('#email', 'john.doe@gmail.com');
await p.type('#password', 'password123');
await Promise.all([
  p.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {}),
  p.click('button[type="submit"]'),
]);
await wait(2500);

const session = await p.evaluate(() => ({
  url: location.pathname,
  hasToken: !!localStorage.getItem('access_token'),
}));
console.log('SESSION:', JSON.stringify(session));

for (const route of ['/patient/dashboard', '/patient/care-plan', '/patient/progress', '/patient/exercises']) {
  captured.length = 0;
  await p.goto(`${BASE}${route}`, { waitUntil: 'networkidle2', timeout: 45000 });
  await wait(1800);

  const ui = await p.evaluate(() => {
    const txt = (sel) => [...document.querySelectorAll(sel)].map((e) => e.textContent.trim().slice(0, 60));
    return {
      h1: txt('h1'),
      h2: txt('h2').slice(0, 6),
      bodyHas: {
        noActiveCarePlan: /no active care plan/i.test(document.body.innerText),
        overallZero: /overall recovery[\s\S]{0,40}0%/i.test(document.body.innerText),
        noExercises: /no exercises assigned/i.test(document.body.innerText),
        postSurgical: /post-surgical knee rehabilitation/i.test(document.body.innerText),
        strengthBuilding: /strength building/i.test(document.body.innerText),
      },
    };
  });

  console.log(`\n===== ${route} =====`);
  console.log('UI:', JSON.stringify(ui, null, 1));
  console.log('API traffic:');
  captured.forEach((c) => console.log(`  [${c.status}] ${c.url} → ${c.summary}`));
}

await b.close();
