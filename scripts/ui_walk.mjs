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

  // 1. decimal amount now works
  await nav('New transaction');
  await p.fill('#amt', '0.55');
  await p.waitForTimeout(400);
  out.push('amount field now: ' + (await p.inputValue('#amt')));
  await p.evaluate(() => [...document.querySelectorAll('main button')].find((x) => x.innerText.includes('Evaluate')).click());
  await p.waitForTimeout(6000);
  let body = await p.evaluate(() => document.body.innerText);
  const m = body.match(/UPFRONT\s*\$([\d.]+)/);
  out.push('evaluated upfront on $0.55 job: ' + (m ? '$' + m[1] : 'MISSING') + (m ? ' (expect ~$0.14 = 25% cap... doctrine v2) ' : ''));

  // 2. Integrity section renders real data
  await nav('Integrity');
  body = await p.evaluate(() => document.body.innerText);
  out.push('integrity: ' + ['Memory journal', 'Settlement chain', 'Deletion gate'].map((s) => body.includes(s) ? 'ok' : 'MISSING-' + s).join(' '));
  out.push('deals settled count shown: ' + (body.includes('Deals settled') ? 'yes' : 'no'));

  // 3. run deletion test from the UI
  await p.evaluate(() => [...document.querySelectorAll('main button')].find((x) => x.innerText.includes('Run the deletion test')).click());
  await p.waitForTimeout(9000);
  body = await p.evaluate(() => document.body.innerText);
  out.push('deletion UI result: ' + (body.includes('PASS — venue refused to rule') ? 'PASS' : 'checking') + ' | doctrine before: ' + ((body.match(/doctrine before wipe: v(\d+)/) || [])[1] || '?'));

  console.log(out.join('\n'));
  await b.close();
})();
