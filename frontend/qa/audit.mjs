// PHYSIOCARE — VISUAL QA AUDIT (read-only; QA tooling, not app code)
// Renders every patient screen at 4 viewports in light + dark mode,
// saves full-page screenshots and emits a rendered-DOM audit:
// overflow, clipped elements, tap-target sizes, sub-12px text,
// palette token usage, section counts, console errors.
import puppeteer from 'puppeteer';
import fs from 'node:fs';
import path from 'node:path';

const BASE = 'http://localhost:5174';
const OUT_DIR = 'qa/screenshots';
const EMAIL = 'john.doe@gmail.com';
const PASSWORD = 'password123';

const VIEWPORTS = [
  { name: 'm320', width: 320, height: 693, mobile: true },
  { name: 'm375', width: 375, height: 812, mobile: true },
  { name: 'm430', width: 430, height: 932, mobile: true },
  { name: 'd1280', width: 1280, height: 900, mobile: false },
];

// [id, route, extra]
const SCREENS = [
  { id: '01-home', path: '/patient/dashboard' },
  { id: '02-care-plan', path: '/patient/care-plan' },
  { id: '03-exercises', path: '/patient/exercises' },
  { id: '04-progress', path: '/patient/progress' },
  { id: '05-more', path: '/patient/dashboard', moreSheet: true },
  { id: '06-services', path: '/patient/services' },
  { id: '07-appointments', path: '/patient/appointments' },
  { id: '08-lab-entry', path: '/patient/laboratory' },
  { id: '09-lab-flow', path: '/patient/laboratory', labFlow: true },
  { id: '10-reports', path: '/patient/reports' },
  { id: '11-history', path: '/patient/history' },
  { id: '12-profile', path: '/patient/profile' },
  { id: '13-settings', path: '/patient/settings' },
];

const AUDIT_FN = () => {
  const vw = document.documentElement.clientWidth;
  const issues = [];

  // 1. Horizontal overflow
  if (document.documentElement.scrollWidth > vw + 1) {
    issues.push({ type: 'page-overflow', detail: `scrollWidth ${document.documentElement.scrollWidth} > viewport ${vw}` });
  }

  // 2. Elements wider than viewport
  const all = [...document.querySelectorAll('body *')];
  const wide = all.filter((el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const s = getComputedStyle(el);
    if (s.position === 'fixed') return false;
    return r.right > vw + 2 || r.left < -2;
  }).slice(0, 5).map((el) => ({
    type: 'element-overflows-viewport',
    detail: `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)} right=${Math.round(el.getBoundingClientRect().right)}`,
  }));
  issues.push(...wide);

  // 3. Clipped text (scrollWidth > clientWidth with hidden overflow)
  const clipped = all.filter((el) => {
    if (!el.textContent || el.textContent.trim().length < 4) return false;
    if (el.children.length > 0) return false;
    const s = getComputedStyle(el);
    if (s.overflowX !== 'hidden' && s.textOverflow !== 'ellipsis' && s.webkitLineClamp === 'none') return false;
    return el.scrollWidth > el.clientWidth + 2;
  }).slice(0, 5).map((el) => ({
    type: 'clipped-text',
    detail: `"${el.textContent.trim().slice(0, 30)}" clipped ${el.scrollWidth}>${el.clientWidth}`,
  }));
  issues.push(...clipped);

  // 4. Tap targets < 44px on interactive elements (mobile only).
  // A control wrapped in a >=44px clickable ancestor (label/button/a/role=button)
  // has an adequate hit area, so only unwrapped controls are flagged.
  const hasBigClickableAncestor = (el) => {
    let anc = el.parentElement;
    while (anc && anc !== document.body) {
      const ar = anc.getBoundingClientRect();
      const clickable = anc.tagName === 'LABEL' || anc.tagName === 'BUTTON' || anc.tagName === 'A' || anc.getAttribute('role') === 'button';
      if (clickable && ar.height >= 44) return true;
      anc = anc.parentElement;
    }
    return false;
  };
  const smallTaps = all.filter((el) => {
    if (!['BUTTON', 'A', 'INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return false;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none') return false;
    if (r.height >= 44) return false;
    if (hasBigClickableAncestor(el)) return false;
    return true;
  }).slice(0, 6).map((el) => ({
    type: 'small-tap-target',
    detail: `${el.tagName} "${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 24)}" h=${Math.round(el.getBoundingClientRect().height)}`,
  }));
  issues.push(...smallTaps);

  // 5. Rendered text smaller than 12px
  const tiny = all.filter((el) => {
    if (el.children.length > 0) return false;
    if (!el.textContent || el.textContent.trim().length < 2) return false;
    const s = getComputedStyle(el);
    const px = parseFloat(s.fontSize);
    return px < 12 && s.visibility !== 'hidden';
  }).slice(0, 6).map((el) => ({
    type: 'text-below-12px',
    detail: `"${el.textContent.trim().slice(0, 24)}" ${getComputedStyle(el).fontSize}`,
  }));
  issues.push(...tiny);

  // 6. Palette tokens actually rendered
  const palette = { deepPine: 0, clay: 0, sage: 0, cream: 0, oldTeal: 0 };
  for (const el of all) {
    const s = getComputedStyle(el);
    const c = `${s.color} ${s.backgroundColor} ${s.borderTopColor}`;
    if (c.includes('31, 75, 69')) palette.deepPine++;
    if (c.includes('193, 105, 74')) palette.clay++;
    if (c.includes('238, 245, 241')) palette.sage++;
    if (c.includes('247, 244, 237')) palette.cream++;
    if (c.includes('15, 107, 99')) palette.oldTeal++;
  }

  // 7. Composition census
  const h1 = [...document.querySelectorAll('h1')].map((h) => h.textContent.trim().slice(0, 40));
  const h2 = [...document.querySelectorAll('h2')].map((h) => h.textContent.trim().slice(0, 40));
  const buttons = document.querySelectorAll('button').length;

  return { issues, palette, h1, h2Count: h2.length, h2Sample: h2.slice(0, 6), buttons };
};

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

fs.mkdirSync(path.join(OUT_DIR, 'light'), { recursive: true });
fs.mkdirSync(path.join(OUT_DIR, 'dark'), { recursive: true });

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--force-device-scale-factor=1'],
});

const report = [];
const consoleErrors = [];

try {
  // ---- Login once per context ----
  const page = await browser.newPage();
  await page.setViewport({ width: 375, height: 812 });
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 200));
  });
  page.on('pageerror', (err) => consoleErrors.push(`PAGEERROR: ${String(err).slice(0, 200)}`));

  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.type('#email', EMAIL);
  await page.type('#password', PASSWORD);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {}),
    page.click('button[type="submit"]'),
  ]);
  await wait(2500);

  const authState = await page.evaluate(() => ({
    hasToken: !!localStorage.getItem('access_token'),
    url: location.pathname,
  }));
  console.log('AUTH:', JSON.stringify(authState));
  if (!authState.hasToken) throw new Error('Login failed — no token in localStorage');

  await page.close();

  // ---- Capture every screen × viewport × theme ----
  for (const vp of VIEWPORTS) {
    for (const theme of ['light', 'dark']) {
      const page = await browser.newPage();
      await page.setViewport({
        width: vp.width,
        height: vp.height,
        isMobile: vp.mobile,
        hasTouch: vp.mobile,
        deviceScaleFactor: 1,
      });
      page.on('pageerror', (err) => consoleErrors.push(`PAGEERROR ${vp.name}/${theme}: ${String(err).slice(0, 160)}`));

      // Prime theme before app loads
      await page.evaluateOnNewDocument((t) => {
        window.__qa_theme = t;
      }, theme);

      await page.goto(`${BASE}/patient/dashboard`, { waitUntil: 'networkidle2', timeout: 60000 });
      await page.evaluate((t) => {
        localStorage.setItem('theme', t);
        localStorage.setItem('theme_user_selected', t);
        document.documentElement.classList.remove('light', 'dark');
        document.documentElement.classList.add(t);
      }, theme);
      await wait(1200);

      for (const screen of SCREENS) {
        try {
          await page.goto(`${BASE}${screen.path}`, { waitUntil: 'networkidle2', timeout: 45000 });
          await wait(1400);

          if (screen.moreSheet) {
            const btns = await page.$$('div.lg\\:hidden.fixed.bottom-0 button');
            if (btns.length > 0) { await btns[btns.length - 1].click(); await wait(700); }
          }
          if (screen.labFlow) {
            const clicked = await page.evaluate(() => {
              const b = [...document.querySelectorAll('button')].find((x) => /home visit/i.test(x.textContent));
              if (b) { b.click(); return true; }
              return false;
            });
            if (clicked) { await wait(1400); }
          }

          const audit = await page.evaluate(AUDIT_FN);

          const pageH = await page.evaluate(() => document.documentElement.scrollHeight);
          await page.screenshot({
            path: path.join(OUT_DIR, theme, `${screen.id}__${vp.name}.png`),
            fullPage: true,
          });

          report.push({
            screen: screen.id,
            viewport: vp.name,
            theme,
            pageHeight: pageH,
            issueCount: audit.issues.length,
            issues: audit.issues,
            palette: audit.palette,
            h1: audit.h1,
            h2Count: audit.h2Count,
            h2Sample: audit.h2Sample,
            buttons: audit.buttons,
          });
          console.log(`OK ${screen.id} ${vp.name} ${theme} (h=${pageH}, issues=${audit.issues.length})`);
        } catch (e) {
          report.push({ screen: screen.id, viewport: vp.name, theme, error: String(e).slice(0, 200) });
          console.log(`FAIL ${screen.id} ${vp.name} ${theme}: ${String(e).slice(0, 120)}`);
        }
      }
      await page.close();
    }
  }
} finally {
  await browser.close();
}

fs.writeFileSync('qa/audit-report.json', JSON.stringify({ report, consoleErrors: [...new Set(consoleErrors)].slice(0, 30) }, null, 2));
console.log(`\nDONE. ${report.length} captures. Report: qa/audit-report.json`);
