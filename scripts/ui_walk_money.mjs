import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require('/home/arch/.hermes/hermes-agent/node_modules/playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const out = [];
  await p.goto('https://canon-venue.vercel.app/console', { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(5000);
  const nav = async (label) => {
    await p.evaluate((l) => { const bt = [...document.querySelectorAll('aside button')].find((x) => x.innerText.trim() === l); if (bt) bt.click(); }, label);
    await p.waitForTimeout(2500);
  };
  const clickBtn = async (txt, waitMs) => {
    await p.evaluate((t) => { const bt = [...document.querySelectorAll('main button')].find((x) => x.innerText.includes(t)); if (bt) bt.click(); }, txt);
    await p.waitForTimeout(waitMs || 8000);
  };
  const links = () => p.evaluate(() => [...document.querySelectorAll('a[href*="basescan"]')].map((a) => a.innerText.trim()));

  await nav('New transaction');
  await p.fill('#amt', '0.55');
  await p.waitForTimeout(400);
  await clickBtn('Evaluate against doctrine', 6000);
  await clickBtn('Create & fund on Base', 18000);      // registers on-chain
  let body = await p.evaluate(() => document.body.innerText);
  out.push('after create: TERMED=' + body.includes('TERMED') + ' lock-button=' + body.includes('Lock escrow'));
  await clickBtn('Lock escrow + bond', 30000);          // REAL USDC pull
  body = await p.evaluate(() => document.body.innerText);
  out.push('after escrow: FUNDED=' + body.includes('FUNDED') + ' links=' + JSON.stringify(await links()));
  await clickBtn('Provider failed', 25000);              // fail + markCompleted on-chain
  body = await p.evaluate(() => document.body.innerText);
  out.push('after fail: FAILED=' + body.includes('FAILED'));
  await clickBtn('File & resolve claim', 30000);         // real payout, adjudicator-signed
  body = await p.evaluate(() => document.body.innerText);
  out.push('after claim: CLAIMED=' + body.includes('CLAIMED') + ' links=' + JSON.stringify(await links()));
  console.log(out.join('\n'));
  await b.close();
})();
