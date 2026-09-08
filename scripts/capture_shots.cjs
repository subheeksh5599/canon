const { chromium } = require('/home/arch/.hermes/hermes-agent/node_modules/playwright');
const fs = require('fs');
(async () => {
  const dir = '/home/arch/canon/docs/media';
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const shots = [
    { name: 'canon-landing.png', url: 'https://canon-venue.vercel.app/', check: 'AGENTS HIRE' },
    { name: 'canon-console.png', url: 'https://canon-venue.vercel.app/console', check: 'DOCTRINE' },
  ];
  for (const s of shots) {
    await page.goto(s.url, { waitUntil: 'networkidle', timeout: 45000 });
    await page.waitForTimeout(4500);
    const text = await page.evaluate(() => document.body.innerText);
    console.log(s.name, '| dom check:', text.toUpperCase().includes(s.check.toUpperCase()), '| chars:', text.length);
    await page.screenshot({ path: dir + '/' + s.name });
  }
  // third shot: judge lab cold-start proof (real output) via direct API on the console page area
  await page.goto('https://canon-venue.vercel.app/', { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: dir + '/canon-hero-section.png' });
  await browser.close();
  const sizes = fs.readdirSync(dir).filter(f => f.endsWith('.png')).map(f => f + '=' + fs.statSync(dir + '/' + f).size);
  console.log('sizes:', sizes.join(' '));
})();
