// Focused read-only probe: precise culprits for QA report
import puppeteer from 'puppeteer';

const BASE = 'http://localhost:5174';
const EMAIL = 'john.doe@gmail.com';
const PASSWORD = 'password123';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--force-device-scale-factor=1'],
});

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 375, height: 812 });
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.type('#email', EMAIL);
  await page.type('#password', PASSWORD);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {}),
    page.click('button[type="submit"]'),
  ]);
  await wait(2000);

  const probe = (vw) => {
    // Real overflow: element extends past viewport AND no ancestor clips it
    const isClippedByAncestor = (el) => {
      let p = el.parentElement;
      while (p) {
        const s = getComputedStyle(p);
        if (s.overflowX === 'hidden' || s.overflow === 'hidden' || s.clipPath !== 'none') return true;
        p = p.parentElement;
      }
      return false;
    };

    const realOverflow = [];
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const s = getComputedStyle(el);
      if (s.position === 'fixed') continue;
      if (r.right > vw + 2 || r.left < -2) {
        if (!isClippedByAncestor(el)) {
          realOverflow.push({
            tag: el.tagName.toLowerCase(),
            cls: String(el.className).slice(0, 70),
            text: (el.textContent || '').trim().slice(0, 30),
            right: Math.round(r.right),
            left: Math.round(r.left),
            hasText: (el.textContent || '').trim().length > 0 && el.children.length === 0,
          });
        }
      }
    }

    // Old teal renderers with identity
    const oldTeal = [];
    for (const el of document.querySelectorAll('body *')) {
      const s = getComputedStyle(el);
      const c = `${s.color}|${s.backgroundColor}|${s.borderTopColor}`;
      if (c.includes('15, 107, 99')) {
        oldTeal.push({
          tag: el.tagName.toLowerCase(),
          cls: String(el.className).slice(0, 80),
          text: (el.textContent || '').trim().slice(0, 30),
          kind: s.color.includes('15, 107, 99') ? 'text' : s.backgroundColor.includes('15, 107, 99') ? 'bg' : 'border',
        });
      }
    }

    // widest content element (for page-overflow diagnosis)
    let widest = null;
    for (const el of document.querySelectorAll('body *')) {
      if (isClippedByAncestor(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0) continue;
      if (!widest || r.right > widest.right) {
        widest = { tag: el.tagName.toLowerCase(), cls: String(el.className).slice(0, 70), text: (el.textContent || '').trim().slice(0, 30), right: Math.round(r.right) };
      }
    }

    return { realOverflow: realOverflow.slice(0, 8), realOverflowCount: realOverflow.length, oldTeal: oldTeal.slice(0, 10), oldTealCount: oldTeal.length, widest };
  };

  const targets = [
    { path: '/patient/history', vp: [320, 375] },
    { path: '/patient/appointments', vp: [375] },
    { path: '/patient/profile', vp: [375] },
    { path: '/patient/care-plan', vp: [375] },
    { path: '/patient/reports', vp: [375] },
    { path: '/patient/exercises', vp: [375] },
  ];

  for (const t of targets) {
    for (const w of t.vp) {
      await page.setViewport({ width: w, height: 812, isMobile: true, hasTouch: true });
      await page.goto(`${BASE}${t.path}`, { waitUntil: 'networkidle2', timeout: 45000 });
      await wait(1300);
      const res = await page.evaluate(probe, w);
      console.log(`\n########## ${t.path} @ ${w}px ##########`);
      console.log('realOverflow:', res.realOverflowCount);
      res.realOverflow.forEach((o) => console.log(`  <${o.tag}> ${o.cls} | text="${o.text}" | L${o.left} R${o.right}`));
      console.log('widest:', JSON.stringify(res.widest));
      console.log('oldTeal rendered:', res.oldTealCount);
      res.oldTeal.forEach((o) => console.log(`  [${o.kind}] <${o.tag}> ${o.cls} | "${o.text}"`));
    }
  }

  // Small-tap inventory for suspect screens
  console.log('\n########## SMALL TAP INVENTORY ##########');
  for (const p of ['/patient/reports', '/patient/exercises', '/patient/settings']) {
    await page.setViewport({ width: 375, height: 812, isMobile: true, hasTouch: true });
    await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle2', timeout: 45000 });
    await wait(1200);
    const taps = await page.evaluate(() => {
      const out = [];
      for (const el of document.querySelectorAll('button, a, input, [role="switch"], [role="button"]')) {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        if (r.width === 0 || r.height === 0 || s.visibility === 'hidden') continue;
        if (r.height < 44) {
          // find a larger clickable ancestor (label counts — native label toggles the control)
          let anc = el.parentElement, wrapped = false;
          while (anc && anc !== document.body) {
            const ar = anc.getBoundingClientRect();
            const clickable = anc.tagName === 'LABEL' || anc.tagName === 'BUTTON' || anc.getAttribute('role') === 'button' || anc.tagName === 'A';
            if (clickable && ar.height >= 44) { wrapped = true; break; }
            anc = anc.parentElement;
          }
          // checkbox inputs: the effective hit area is the 44px label wrapper — only flag if none
          if (el.tagName === 'INPUT' && el.type === 'checkbox' && wrapped) continue;
          out.push({
            tag: el.tagName.toLowerCase(),
            text: (el.getAttribute('aria-label') || el.textContent || el.getAttribute('placeholder') || '').trim().slice(0, 28),
            h: Math.round(r.height),
            wrappedIn44: wrapped,
            cls: String(el.className).slice(0, 50),
          });
        }
      }
      return out;
    });
    console.log(`\n${p}:`);
    taps.forEach((t) => console.log(`  <${t.tag}> h=${t.h} wrapped=${t.wrappedIn44} "${t.text}" | ${t.cls}`));
  }

  // Tiny text full inventory
  console.log('\n########## TINY TEXT (<12px) FULL ##########');
  for (const p of ['/patient/dashboard', '/patient/settings', '/patient/profile', '/patient/appointments', '/patient/reports', '/patient/history', '/patient/exercises', '/patient/care-plan', '/patient/progress']) {
    await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle2', timeout: 45000 });
    await wait(1100);
    const tiny = await page.evaluate(() => {
      const out = [];
      for (const el of document.querySelectorAll('body *')) {
        if (el.children.length > 0) continue;
        if (!el.textContent || el.textContent.trim().length < 2) continue;
        const s = getComputedStyle(el);
        if (s.visibility === 'hidden' || s.display === 'none') continue;
        const px = parseFloat(s.fontSize);
        if (px < 12) out.push(`"${el.textContent.trim().slice(0, 26)}" ${px}px`);
      }
      return [...new Set(out)];
    });
    if (tiny.length) {
      console.log(`\n${p}:`);
      tiny.forEach((t) => console.log('  ', t));
    }
  }
} finally {
  await browser.close();
}
