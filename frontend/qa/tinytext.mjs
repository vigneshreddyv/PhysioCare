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
await p.goto('http://localhost:5174/patient/dashboard', { waitUntil: 'networkidle2', timeout: 45000 });
await wait(1200);

// open the More sheet
const opened = await p.evaluate(() => {
  const btns = [...document.querySelectorAll('div.lg\\:hidden.fixed.bottom-0 button')];
  const more = btns[btns.length - 1];
  if (more) { more.click(); return true; }
  return false;
});
console.log('More sheet opened:', opened);
await wait(800);

const tiny = await p.evaluate(() => {
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.children.length > 0 || !el.textContent || el.textContent.trim().length < 2) continue;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden') continue;
    const px = parseFloat(s.fontSize);
    if (px < 12) {
      let anc = el.parentElement, path = [];
      while (anc && anc !== document.body && path.length < 4) {
        path.push(`${anc.tagName}.${String(anc.className).slice(0, 40)}`);
        anc = anc.parentElement;
      }
      out.push({ text: el.textContent.trim().slice(0, 30), px, ancestors: path });
    }
  }
  return out;
});
console.log(JSON.stringify(tiny, null, 1));
await b.close();
