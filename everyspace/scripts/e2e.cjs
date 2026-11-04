// End-to-end click-through of the app with Playwright.
// Usage: node scripts/e2e.cjs <screenshot dir> <url>   (url: http://localhost:3000/ or file:///…/dist/everyspace.html)
// Needs Playwright with Chromium installed. Exits non-zero if any step fails or the page logs errors.
const { chromium } = require('playwright');
const path = require('node:path');
const fs = require('node:fs');

const [outDir = 'e2e-shots', URL = 'http://localhost:3000/'] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push(`pageerror: ${e.message}`));
  // 400s are expected: the quote endpoint answers rule violations (e.g. add-on without an anchor) with 400.
  p.on('console', (m) => { if (m.type() === 'error' && !/status of 400/.test(m.text())) errs.push(`console: ${m.text()}`); });
  const shot = (n) => p.screenshot({ path: path.join(outDir, `${n}.png`) });
  const overflow = async (n) => { const w = await p.evaluate(() => document.documentElement.scrollWidth); const vw = p.viewportSize().width; if (w > vw) errs.push(`horizontal overflow on ${n}: ${w}px`); };
  const go = async (h) => { await p.evaluate((x) => { location.hash = x; }, h); await p.waitForTimeout(450); };
  const step = async (name, fn) => {
    try { await fn(); console.log('ok  ', name); } catch (e) { console.log('FAIL', name, '-', e.message.split('\n')[0]); errs.push(`step failed: ${name}`); }
  };
  const pickDay = async (date) => {
    for (let i = 0; i < 14 && !(await p.$(`.day[data-date="${date}"]`)); i++) { await p.click('[data-nav="1"]'); await p.waitForTimeout(150); }
    await p.click(`.day[data-date="${date}"]`);
  };

  await p.goto(URL);
  await p.evaluate(() => { try { localStorage.clear(); } catch {} });
  await p.goto(URL);
  await p.waitForSelector('.space-card', { timeout: 10000 });
  // Start from clean demo data so the run is repeatable.
  p.on('dialog', (d) => d.accept()); // accept confirm() prompts (reset, decline, cancel)
  await go('#/profile'); await p.click('#reset'); await p.waitForTimeout(300);
  await go('#/explore'); await p.waitForSelector('.space-card');

  await step('explore', async () => { await shot('01-explore'); await overflow('explore'); });
  await step('everyday explore has no infrastructure', async () => {
    const text = await p.textContent('#explore-body');
    if (/Rooftop solar|Battery site|Fleet & van|parcel locker/i.test(text)) throw new Error('business listings leaked into everyday explore');
  });
  await step('save a space (heart) and see it in Saved', async () => {
    await p.click('.grid [data-save="s_maple_backyard"]'); await p.waitForTimeout(300);
    await go('#/saved'); await p.waitForSelector('.space-card');
    if (!(await p.$('[data-save="s_maple_backyard"].on'))) throw new Error('backyard not in Saved');
    await shot('01b-saved'); await overflow('saved');
  });
  await step('earnings estimator', async () => {
    await go('#/earn'); await p.waitForSelector('#total-month');
    const before = await p.textContent('#total-month');
    await p.click('[data-stepper="yard"] [data-step="1"]'); await p.click('[data-stepper="sign"] [data-step="1"]'); await p.waitForTimeout(100);
    if ((await p.textContent('#total-month')) === before) throw new Error('total did not change');
    await shot('01c-earn'); await overflow('earn');
  });
  await step('business landing for people', async () => { await go('#/biz'); await p.waitForSelector('.biz-hero.landing'); await shot('01d-biz-landing'); await overflow('biz landing'); });
  await go('#/explore'); await p.waitForSelector('.space-card');
  await step('group filter', async () => { await p.click('[data-group="parking"]'); await p.waitForTimeout(400); await shot('02-parking'); await p.click('[data-group=""]'); });
  await step('map', async () => {
    await p.click('#toggle-view'); await p.waitForSelector('.pin'); await p.click('.pin >> nth=1'); await p.waitForTimeout(200);
    await shot('03-map'); await overflow('map'); await p.click('#toggle-view');
  });
  await step('space detail', async () => { await go('#/space/s_maple_driveway'); await p.waitForSelector('.cal-grid'); await shot('04-space'); await overflow('space'); });
  await step('checkout with festival pricing', async () => {
    await go('#/book/s_maple_driveway');
    await p.click('[data-term="daily"]'); await p.waitForSelector('.day[data-date]');
    await pickDay('2026-11-21'); await p.waitForTimeout(100); await pickDay('2026-11-22');
    await p.waitForTimeout(500); await shot('05-checkout'); await overflow('checkout');
    const q = await p.textContent('#quote');
    if (!/Harvest Festival/.test(q)) throw new Error(`no festival rate in quote: ${q.slice(0, 120)}`);
    await p.fill('#note', 'Arriving at 9am'); await p.click('#confirm'); await p.waitForSelector('.success'); await shot('06-success');
  });
  await step('trip shows access + chat works', async () => {
    await p.click('text=View trip'); await p.waitForSelector('.access'); await shot('07-trip'); await overflow('trip');
    await p.click('.host-row >> text=Message'); await p.waitForSelector('#composer');
    await p.fill('#text', 'See you Saturday!'); await p.click('.send'); await p.waitForTimeout(300);
    if (!(await p.textContent('#chat')).includes('See you Saturday')) throw new Error('sent message not shown');
    await shot('08-chat'); await overflow('chat');
  });
  await step('price match claim on an unknown link goes to review', async () => {
    const id = await p.evaluate(() => location.hash.split('/').pop());
    await go(`#/trip/${id}`); await p.waitForSelector('#pm-url');
    await p.fill('#pm-url', 'https://www.spothero.com/parking/other-lot-near-fair'); await p.fill('#pm-total', '30'); await p.click('#pm-send');
    await p.waitForSelector('#pm-url', { state: 'detached' }); if (!/in review/.test(await p.textContent('.quote'))) throw new Error('claim not shown as in review'); await shot('08b-price-match');
  });
  await step('listing shows price check, money breakdown and guarantee', async () => {
    await go('#/space/s_maple_home'); await p.waitForSelector('.compare');
    if (!/Cheapest here/.test(await p.textContent('.compare-verdict'))) throw new Error('expected cheapest-here verdict');
    if (!(await p.$('.money-flow')) || !(await p.$('.guarantee'))) throw new Error('missing breakdown or guarantee');
    await shot('08c-price-check'); await overflow('price check');
  });
  await step('checkout beats a cheaper price elsewhere', async () => {
    await go('#/book/s_ana_room'); await p.waitForSelector('#quote .qline'); await p.waitForTimeout(400);
    if (!(await p.$('#quote .qline.beat'))) throw new Error('no price beat line for the guest room (cheaper on Airbnb)');
    if (!/occupancy tax/i.test(await p.textContent('#quote'))) throw new Error('no lodging tax line');
    await shot('08d-price-beat');
  });
  await step('how pricing works page', async () => { await go('#/fair-price'); await p.waitForSelector('.money-flow'); await overflow('fair price'); await shot('08e-fair-price'); });
  await step('add-on-only parking explains the rule', async () => {
    await go('#/book/s_oak_parking'); await p.waitForTimeout(700);
    const q = await p.textContent('#quote'); if (!/only available with/.test(q)) throw new Error(q.slice(0, 100));
  });
  await step('bundle checkout (lease request)', async () => {
    await go('#/book/pkg/pk_1a_2park'); await p.waitForSelector('[data-term="lease"]'); await p.click('[data-term="lease"]'); await p.waitForTimeout(500);
    await shot('09-bundle');
    const t = await p.textContent('#confirm'); if (!/Request/.test(t)) throw new Error(`button says ${t}`);
    await p.click('#confirm'); await p.waitForSelector('.success');
  });
  await step('apartment + add-ons get tenant price', async () => {
    await go('#/book/s_oak_2a'); await p.waitForSelector('[data-term="monthly"]'); await p.click('[data-term="monthly"]'); await p.waitForTimeout(300);
    await p.click('[data-stepper="addon:s_oak_parking"] [data-step="1"]'); await p.click('[data-stepper="addon:s_oak_locker"] [data-step="1"]'); await p.waitForTimeout(600);
    const q = await p.textContent('#quote'); if (!/tenant price/.test(q)) throw new Error('no tenant price line');
    await shot('10-addons');
  });
  await step('trips', async () => { await go('#/trips'); await shot('11-trips'); await overflow('trips'); await p.click('[data-t="past"]'); await p.waitForTimeout(300); await shot('12-trips-past'); });
  await step('leave a review', async () => {
    await p.click('.trip-card'); await p.waitForSelector('#stars'); await p.click('[data-star="5"]');
    await p.fill('#review-text', 'Great pool!'); await p.click('#send-review'); await p.waitForSelector('.notice.ok');
  });
  await step('inbox', async () => { await go('#/inbox'); await p.waitForSelector('.thread'); await shot('13-inbox'); await overflow('inbox'); });
  await step('Jordan approves the lease', async () => {
    await go('#/profile'); await shot('14-profile'); await p.click('[data-user="u_jordan"]'); await p.waitForSelector('.greeting');
    await shot('15-host-today'); await overflow('host today');
    await p.click('.request [data-act="approve"]'); await p.waitForTimeout(500);
    if ((await p.$$('.request')).length) throw new Error('request still waiting');
  });
  await step('listings + earnings', async () => {
    await go('#/host/listings'); await p.waitForTimeout(300); await shot('16-listings'); await overflow('listings');
    await go('#/host/earnings'); await p.waitForTimeout(300); await shot('17-earnings'); await overflow('earnings');
    const [dl] = await Promise.all([p.waitForEvent('download'), p.click('#csv')]);
    if (!dl.suggestedFilename().endsWith('.csv')) throw new Error('earnings export is not a CSV');
  });
  await step('Maya lists a new space with the wizard', async () => {
    await go('#/profile'); await p.click('[data-user="u_maya"]'); await p.waitForSelector('.greeting');
    await go('#/host/new?fresh=1'); await p.click('[data-cat="parking_spot"]'); await shot('18-wizard-what'); await p.click('#next');
    await p.click('[data-prop="p_maple"]'); await p.click('#next');
    await p.fill('#w-title', 'Side-yard parking'); await p.click('[data-stepper="quantity"] [data-step="1"]'); await p.click('#next');
    await shot('19-wizard-prices');
    await p.fill('#ev-name', 'Parade'); await p.fill('#ev-start', '2026-12-05'); await p.fill('#ev-end', '2026-12-05'); await p.fill('#ev-daily', '35');
    await p.click('#next'); await p.click('#next');
    for (const c of await p.$$('[data-check]')) await c.check();
    await p.fill('#w-access', 'Gravel pad left of the gate.'); await p.click('#next'); await shot('20-wizard-review');
    await p.click('#next'); await p.waitForTimeout(700);
    const t = await p.textContent('.page-title'); if (t !== 'Side-yard parking') throw new Error(`landed on "${t}"`);
    await shot('21-new-listing');
  });
  await step('Maya manages a listing: price, pause, block dates, cross-list', async () => {
    await go('#/host/space/s_maple_attic'); await p.waitForSelector('#save-prices'); await shot('21b-manage'); await overflow('manage');
    await p.fill('[data-rate="monthly"]', '58'); await p.click('#save-prices'); await p.waitForSelector('#save-prices');
    if ((await p.inputValue('[data-rate="monthly"]')) !== '58') throw new Error('price not saved');
    await p.click('label.switch'); await p.waitForTimeout(500);
    if (!/Paused/.test(await p.textContent('.manage'))) throw new Error('did not pause');
    await p.click('label.switch'); await p.waitForTimeout(500);
    await p.fill('#ext-url', 'https://www.neighbor.com/l/attic-123'); await p.fill('#ext-price', '65'); await p.click('#add-ext'); await p.waitForTimeout(500);
    if (!/Neighbor/.test(await p.textContent('#ext-list'))) throw new Error('cross-listing not added');
  });
  await step('Ana sees the "cheaper elsewhere" warning and matches her take-home', async () => {
    await go('#/profile'); await p.click('[data-user="u_ana"]'); await p.waitForSelector('.greeting');
    await go('#/host/space/s_ana_room'); await p.waitForSelector('.notice.warn'); await shot('21c-parity');
    for (let i = 0; i < 4 && (await p.$('[data-same]')); i++) { await p.click('[data-same]'); await p.waitForTimeout(500); } // match every length
    if (await p.$('.notice.warn')) throw new Error('still cheaper elsewhere after matching take-home');
    if (!(await p.$('#instant'))) throw new Error('no instant-book switch');
    await shot('21d-matched');
    await go('#/profile'); await p.click('[data-user="u_maya"]'); await p.waitForSelector('.greeting');
  });
  await step('Maya approves Kim from the chat', async () => {
    await go('#/chat/bk_seed_6'); await p.waitForSelector('.action-bar'); await shot('22-host-chat');
    await p.click('[data-reply]'); await p.click('.send'); await p.waitForTimeout(300);
    if (!/Thanks for booking/.test(await p.textContent('#chat'))) throw new Error('quick reply not sent');
    await p.click('[data-act="approve"]'); await p.waitForTimeout(500);
    if (await p.$('.action-bar')) throw new Error('still pending');
  });
  await step('Maya can list a roof under "Lease to companies"', async () => {
    await go('#/host/new?fresh=1'); await p.click('[data-aud="business"]'); await p.waitForSelector('[data-cat="rooftop_solar"]');
    if (await p.$('[data-cat="backyard"]')) throw new Error('consumer categories shown on the companies tab');
    await shot('22b-wizard-business');
  });
  await step('SunCo lands on the business side and sends a proposal', async () => {
    await go('#/profile'); await p.click('[data-user="u_sunco"]'); await p.waitForSelector('.site-list');
    await shot('23a-biz-sites'); await overflow('biz sites');
    await go('#/explore'); await p.waitForTimeout(300);
    if (!(await p.evaluate(() => location.hash)).startsWith('#/biz')) throw new Error('business account reached everyday explore');
    await go('#/space/s_hill_solar'); await p.waitForSelector('.specs'); await shot('23b-site');
    await go('#/book/s_hill_solar'); await p.waitForSelector('#w-years'); await p.waitForTimeout(500); await shot('23-solar');
    await p.click('#confirm'); await p.waitForSelector('.success');
    await go('#/biz/pipeline'); await p.waitForSelector('.kanban'); await shot('23c-pipeline'); await overflow('pipeline');
  });
  await step('plan + catalog', async () => {
    await go('#/plan'); await p.waitForSelector('#plan-body h2'); await overflow('plan');
    await go('#/catalog'); await p.waitForTimeout(200); await shot('24-catalog'); await overflow('catalog');
  });
  await step('desktop', async () => {
    await p.setViewportSize({ width: 1280, height: 860 });
    await go('#/profile'); await p.click('[data-user="u_sam"]'); await p.waitForTimeout(500); await shot('25-desktop');
    await go('#/space/s_elm_pool'); await p.waitForTimeout(500); await shot('26-desktop-space');
    await go('#/biz'); await p.waitForTimeout(300); await shot('26b-desktop-biz-landing');
  });
  await step('dark mode', async () => {
    await p.emulateMedia({ colorScheme: 'dark' }); await p.setViewportSize({ width: 390, height: 844 });
    await go('#/explore'); await p.waitForTimeout(400); await shot('27-dark');
  });

  console.log(errs.length ? `\n${errs.length} problem(s):\n${errs.join('\n')}` : '\nNo errors.');
  await browser.close();
  process.exit(errs.length ? 1 : 0);
})();
