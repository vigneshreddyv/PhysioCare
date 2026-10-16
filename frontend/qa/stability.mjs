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

for (let trial = 1; trial <= 5; trial++) {
  await p.goto('http://localhost:5174/patient/appointments', { waitUntil: 'networkidle2', timeout: 45000 });
  const samples = [];
  for (let i = 0; i < 6; i++) {
    const sw = await p.evaluate(() => document.documentElement.scrollWidth);
    samples.push(sw);
    await wait(250);
  }
  console.log(`trial ${trial}: scrollWidth samples =`, samples.join(' → '), samples.every((s) => s <= 321) ? 'STABLE' : 'OVERFLOW');
}
await b.close();
