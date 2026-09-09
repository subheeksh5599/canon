const { chromium } = require('/home/arch/.hermes/hermes-agent/node_modules/playwright');
const fs = require('fs');
(async () => {
  const dir = '/home/arch/canon/docs/media';
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  // 1. landing
  await page.goto('https://canon-venue.vercel.app/', { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(4500);
  let text = await page.evaluate(() => document.body.innerText);
  console.log('canon-landing.png | dom check:', text.toUpperCase().includes('AGENTS HIRE'), '| chars:', text.length);
  await page.screenshot({ path: dir + '/canon-landing.png' });
  // 2. console overview
  await page.goto('https://canon-venue.vercel.app/console', { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(4500);
  text = await page.evaluate(() => document.body.innerText);
  console.log('canon-console.png | dom check:', text.toUpperCase().includes('DOCTRINE'), '| chars:', text.length);
  await page.screenshot({ path: dir + '/canon-console.png' });
  // 3. console Transactions — the real on-chain ledger with explorer links (distinct view)
  await page.evaluate(() => { const bt = [...document.querySelectorAll('aside button')].find((x) => x.innerText.trim() === 'Transactions'); if (bt) bt.click(); });
  await page.waitForTimeout(3500);
  text = await page.evaluate(() => document.body.innerText);
  const links = await page.evaluate(() => [...document.querySelectorAll('a[href*="basescan"]')].length);
  console.log('canon-ledger.png | dom check: ledger rows', text.includes('COMPLETED') || text.includes('CLAIMED'), '| explorer links:', links);
  await page.screenshot({ path: dir + '/canon-ledger.png' });
  await browser.close();
  const sizes = fs.readdirSync(dir).filter(f => f.endsWith('.png')).map(f => f + '=' + fs.statSync(dir + '/' + f).size);
  console.log('sizes:', sizes.join(' '));
})();
