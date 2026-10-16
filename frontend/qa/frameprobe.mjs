import puppeteer from 'puppeteer';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const b = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
const p = await b.newPage();
await p.setViewport({ width: 320, height: 693, isMobile: true, hasTouch: true });
await p.goto('http://localhost:5174/login', { waitUntil: 'networkidle0', timeout: 60000 });
await p.type('#email', 'john.doe@gmail.com');
await p.type('#password', 'password123');
await Promise.all([
  p.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {}),
  p.click('button[type="submit"]'),
]);
await wait(2000);

await p.evaluate(() => {
  localStorage.setItem('theme', 'dark');
  localStorage.setItem('theme_user_selected', 'dark');
});

// Inject an early poller that records the first overflowing frame's culprits
await p.evaluateOnNewDocument(() => {
  window.__ovLog = [];
  const scan = () => {
    const vw = document.documentElement.clientWidth;
    const sw = document.documentElement.scrollWidth;
    if (sw > vw + 1 && !window.__ovDone) {
      window.__ovDone = true;
      const isClipped = (el) => {
        let a = el.parentElement;
        while (a) {
          const s = getComputedStyle(a);
          if (s.overflowX === 'hidden' || s.overflow === 'hidden') return true;
          a = a.parentElement;
        }
        return false;
      };
      const culprits = [];
      for (const el of document.querySelectorAll('body *')) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        const s = getComputedStyle(el);
        if (s.position === 'fixed') continue;
        if (r.right > vw + 2 && !isClipped(el)) {
          culprits.push({
            tag: el.tagName.toLowerCase(),
            cls: String(el.className).slice(0, 90),
            text: (el.textContent || '').trim().slice(0, 30),
            right: Math.round(r.right),
          });
        }
      }
      window.__ovLog.push({ sw, vw, culprits: culprits.slice(0, 8) });
    }
  };
  setInterval(scan, 30);
});

await p.goto('http://localhost:5174/patient/appointments', { waitUntil: 'networkidle2', timeout: 45000 });
await wait(3000);

const log = await p.evaluate(() => window.__ovLog);
console.log('overflow frames captured:', log.length);
log.forEach((f, i) => {
  console.log(`\nframe ${i}: sw=${f.sw} vw=${f.vw}`);
  f.culprits.forEach((c) => console.log(`  <${c.tag}> ${c.cls} | "${c.text}" | R${c.right}`));
});
await b.close();
