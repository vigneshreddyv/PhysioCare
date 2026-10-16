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
await p.goto('http://localhost:5174/patient/care-plan', { waitUntil: 'networkidle2', timeout: 45000 });
await wait(1500);

const leaks = await p.evaluate(() => {
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const t = walker.currentNode.textContent;
    if (/\b(in_progress|stage_activated|plan_created|goal_updated)\b/.test(t)) {
      const el = walker.currentNode.parentElement;
      let anc = el, path = [];
      while (anc && anc !== document.body && path.length < 3) {
        path.push(`${anc.tagName}.${String(anc.className).slice(0, 50)}`);
        anc = anc.parentElement;
      }
      out.push({ text: t.trim().slice(0, 60), path });
    }
  }
  return out;
});
console.log('raw enum text leaks:', leaks.length);
leaks.forEach((l) => console.log(JSON.stringify(l, null, 1)));
await b.close();
