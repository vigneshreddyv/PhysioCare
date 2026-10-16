// Verify T5 review-fee / back-nav date rendering detail (read-only)
import puppeteer from 'puppeteer';
const BASE = 'http://localhost:5173';
const WAIT = { waitUntil: 'networkidle2', timeout: 60000 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({ headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900 });
const click = (sel, t, exact = false) => page.evaluate(({ sel, t, exact }) => {
  const el = [...document.querySelectorAll(sel)].find((e) => exact ? e.textContent.trim() === t : e.textContent.trim().includes(t));
  if (el) { el.click(); return true; } return false;
}, { sel, t, exact });

await page.goto('about:blank');
await page.goto(`${BASE}/login`, WAIT);
await page.waitForSelector('#email');
await sleep(1200);
await page.click('#email', { clickCount: 3 }); await page.type('#email', 'john.doe@gmail.com');
await page.click('#password', { clickCount: 3 }); await page.type('#password', 'password123');
await page.click('button[type="submit"]');
for (let i = 0; i < 24; i++) { await sleep(500); if (!page.url().includes('/login')) break; }
await sleep(2000);

await page.goto('about:blank');
await page.goto(`${BASE}/patient/book`, WAIT);
await sleep(1800);
await click('button', 'Clinic Consultation'); await sleep(900);
await click('button', 'Neck', true); await sleep(400);
await click('button', 'Neck pain', true); await sleep(300);
await click('button', 'Continue'); await sleep(900);
await click('button', 'Dr. Sarah Miller'); await sleep(1000);
await page.evaluate(() => {
  const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === '25' && !x.disabled);
  if (b) b.click();
});
await sleep(700);
await click('button', '11:00 AM', true); await sleep(900);
const t = await page.evaluate(() => document.body.innerText);
console.log('--- fee rows on review ---');
console.log(t.split('\n').filter((l) => /₹|fee|Total|Consultation/i.test(l)).join(' | '));
console.log('--- Problem row context ---');
console.log(JSON.stringify(t.match(/Problem[\s\S]{0,40}/)?.[0]));
// back to step 4
await click('button', 'Back'); await sleep(900);
const t4 = await page.evaluate(() => document.body.innerText);
console.log('--- after Back: Selected Date block ---');
console.log(JSON.stringify(t4.match(/Selected Date[\s\S]{0,60}/)?.[0] || 'NOT FOUND'));
await browser.close();
