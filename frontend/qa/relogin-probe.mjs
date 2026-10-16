// Verifies re-login works when typing is properly settled (read-only)
import puppeteer from 'puppeteer';
const BASE = 'http://localhost:5173';
const WAIT = { waitUntil: 'networkidle2', timeout: 60000 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({ headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900 });

async function robustLogin(page, email, password) {
  await page.goto(`${BASE}/login`, WAIT);
  await page.waitForSelector('#email', { timeout: 30000 });
  await sleep(1200); // let dev-mode form fully mount
  await page.click('#email', { clickCount: 3 });
  await page.type('#email', email, { delay: 30 });
  await page.click('#password', { clickCount: 3 });
  await page.type('#password', password, { delay: 30 });
  // verify values stuck
  const vals = await page.evaluate(() => ({
    e: document.querySelector('#email')?.value,
    p: document.querySelector('#password')?.value?.length,
  }));
  console.log('field values before submit:', JSON.stringify(vals));
  let loginStatus = 0;
  const onResponse = (res) => { if (res.url().includes('/auth/login')) loginStatus = res.status(); };
  page.on('response', onResponse);
  await page.click('button[type="submit"]');
  for (let i = 0; i < 20; i++) {
    await sleep(500);
    if (!page.url().includes('/login')) break;
  }
  page.off('response', onResponse);
  await sleep(2000);
  return { loginStatus, url: page.url() };
}

// 1. first login
let r = await robustLogin(page, 'john.doe@gmail.com', 'password123');
console.log('LOGIN-1:', JSON.stringify(r));

// 2. logout via UI
await page.goto(`${BASE}/patient/settings`, WAIT);
await sleep(1000);
await page.evaluate(() => {
  const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim().toLowerCase().includes('log out'));
  if (b) b.click();
});
await sleep(700);
await page.evaluate(() => {
  const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Sign Out');
  if (b) b.click();
});
await sleep(2500);
console.log('after logout:', page.url(), 'token=', await page.evaluate(() => localStorage.getItem('access_token')));

// 3. re-login
r = await robustLogin(page, 'john.doe@gmail.com', 'password123');
console.log('LOGIN-2 (re-login):', JSON.stringify(r));
const t = await page.evaluate(() => localStorage.getItem('access_token'));
console.log('token after re-login:', t ? t.slice(0, 15) + '…' : null);
await page.goto(`${BASE}/patient/dashboard`, WAIT);
await sleep(2500);
const txt = await page.evaluate(() => document.body.innerText);
console.log('dashboard populated:', txt.includes('Strength Building'), '| empty-state:', txt.includes('No Active Care Plan'));

await browser.close();
