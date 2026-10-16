import puppeteer from 'puppeteer';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const b = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
const p = await b.newPage();
await p.setViewport({ width: 375, height: 812, isMobile: true, hasTouch: true });
await p.goto('http://localhost:5174/login', { waitUntil: 'networkidle0', timeout: 60000 });
await p.type('#email', 'john.doe@gmail.com');
await p.type('#password', 'password123');
await Promise.all([
  p.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {}),
  p.click('button[type="submit"]'),
]);
await wait(2000);

await p.setViewport({ width: 320, height: 693, isMobile: true, hasTouch: true });
await p.goto('http://localhost:5174/patient/appointments', { waitUntil: 'networkidle2', timeout: 45000 });
await wait(400); // shortly after network idle — catch the pre-correction frame
await p.evaluate(() => {
  localStorage.setItem('theme', 'dark');
  localStorage.setItem('theme_user_selected', 'dark');
  document.documentElement.classList.remove('light', 'dark');
  document.documentElement.classList.add('dark');
});
await wait(800);

const res = await p.evaluate(() => {
  const vw = document.documentElement.clientWidth;
  const sw = document.documentElement.scrollWidth;
  const out = { vw, sw, culprits: [] };
  if (sw > vw + 1) {
    const isClipped = (el) => {
      let a = el.parentElement;
      while (a) {
        const s = getComputedStyle(a);
        if (s.overflowX === 'hidden' || s.overflow === 'hidden') return true;
        a = a.parentElement;
      }
      return false;
    };
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const s = getComputedStyle(el);
      if (s.position === 'fixed') continue;
      if (r.right > vw + 2 && !isClipped(el)) {
        out.culprits.push({
          tag: el.tagName.toLowerCase(),
          cls: String(el.className).slice(0, 90),
          text: (el.textContent || '').trim().slice(0, 40),
          left: Math.round(r.left),
          right: Math.round(r.right),
          w: Math.round(r.width),
        });
      }
    }
    out.culprits = out.culprits.slice(0, 10);
  }
  return out;
});
console.log(JSON.stringify(res, null, 1));
await b.close();
