// End-to-end checks for the LA County page (reports/city-pretty-la-county.html), run offline with Playwright.
// Usage: node tests/e2e.cjs [path-to-page]          Needs Playwright with Chromium (npm i playwright).
//
// Every request leaving the page is answered here: LA County's parcel service is faked (slow lot-line tiles,
// with and without a pre-drawn tile cache); everything else is blocked. Exits non-zero on any failure.
const { chromium } = require('playwright');
const path = require('node:path');

const PAGE = path.resolve(process.argv[2] || path.join(__dirname, '..', 'reports', 'city-pretty-la-county.html'));
const BOOT_BUDGET_MS = Number(process.env.BOOT_BUDGET_MS || 12000); // generous: CI machines are slow
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
const CACHE_INFO = { singleFusedMapCache: true, tileInfo: { rows: 256, cols: 256, origin: { x: -20037508.342787, y: 20037508.342787 },
  spatialReference: { wkid: 102100, latestWkid: 3857 }, lods: Array.from({ length: 20 }, (_, level) => ({ level, resolution: 156543.03392800014 / 2 ** level })) } };

const results = [];
const check = (name, ok, extra = '') => { results.push(ok); console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}${extra ? ` (${extra})` : ''}`); };

async function run({ cached }) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
  const errors = [], lotUrls = [], overlayCalls = [];
  page.on('pageerror', (e) => errors.push(e.message));
  const OVERLAY_HOSTS = /Historic_Preservation|Historic_Cultural|GISNET_Public\/MapServer\/331|Special_Areas\/MapServer\/6|CGS_|FHSZ|FHSALRA/;
  const ring = (lat, lng, d = 0.0002) => [[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d], [lng - d, lat - d]];
  await page.route('**/*', async (route) => {
    const url = route.request().url();
    if (url.startsWith('file:') || url.startsWith('data:')) return route.continue();
    if (OVERLAY_HOSTS.test(url)) { overlayCalls.push(url); return route.fulfill({ contentType: 'application/json', body: '{"features":[]}' }); }
    if (url.includes('LACounty_Parcel/MapServer/0/query')) { // the County parcel lookup (hover and click)
      const m = /geometry=(-?[\d.]+),(-?[\d.]+)/.exec(decodeURIComponent(url)) || [];
      const lng = +m[1], lat = +m[2];
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ features: [{ geometry: { rings: [ring(lat, lng)] },
        attributes: { AIN: '5555012345', SitusFullAddress: '123 TEST ST', SitusHouseNo: '123', SitusStreet: 'TEST ST', UseCode: '0100', UseType: 'Residential',
          Roll_LandValue: 500000, Roll_ImpValue: 200000, YearBuilt1: '1950', SQFTmain1: 1400, Units1: 1, Bedrooms1: 3, Bathrooms1: 2, DesignType1: '0100' } }] }) });
    }
    if (url.includes('overpass') || url.includes('kumi.systems')) { await new Promise((r) => setTimeout(r, 900)); return route.fulfill({ contentType: 'application/json', body: '{"elements":[]}' }); }
    if (url.includes('data.lacity.org') || url.includes('pais_sales_parcels')) {
      await new Promise((r) => setTimeout(r, 600));
      return route.fulfill({ contentType: 'application/json', body: url.includes('data.lacity.org') ? '[]' : '{"features":[]}' });
    }
    if (url.includes('LACounty_Parcel/MapServer?f=json')) {
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(cached ? CACHE_INFO : { singleFusedMapCache: false }) });
    }
    if (url.includes('LACounty_Parcel/MapServer/export') || url.includes('LACounty_Parcel/MapServer/tile/')) {
      lotUrls.push(url);
      await new Promise((r) => setTimeout(r, 2000)); // slower than LOTS_NOTE_MS, so the note must show
      return route.fulfill({ contentType: 'image/png', body: PNG });
    }
    return route.abort();
  });

  const t0 = Date.now();
  await page.goto(`file://${PAGE}`);
  await page.waitForFunction(() => document.querySelector('#loading')?.hidden === true, null, { timeout: 60000 });
  const boot = Date.now() - t0;
  const label = cached ? '[pre-drawn tiles]' : '[server-drawn tiles]';
  check(`${label} map opens within ${BOOT_BUDGET_MS / 1000}s`, boot < BOOT_BUDGET_MS, `${(boot / 1000).toFixed(1)}s`);

  // Block-group details are unpacked on demand: opening one must still fill the panel.
  const panel = await page.evaluate(() => { select(D.meta.default_bg, true); return document.querySelector('#panel').textContent.length; });
  check(`${label} block-group panel opens from on-demand details`, panel > 500, `${panel} chars`);

  // Zoom in to parcel level: the "Loading property lines…" note shows while tiles load, then hides.
  await page.waitForTimeout(800); // let the fly-to animation from select() and the cache check finish
  await page.evaluate(() => map.setView([34.0195, -118.3905], 17.5, { animate: false }));
  const shown = await page.waitForSelector('#lots-note:not([hidden])', { timeout: 4000 }).then(() => true, () => false);
  check(`${label} "Loading property lines…" note appears while lines load`, shown);
  const gone = await page.waitForSelector('#lots-note', { state: 'hidden', timeout: 10000 }).then(() => true, () => false);
  check(`${label} note hides once lines have loaded`, gone);
  const want = cached ? '/tile/' : '/export?';
  check(`${label} lot lines use ${cached ? 'the pre-drawn tile cache' : '512 px server renders'}`,
    lotUrls.length > 0 && lotUrls.every((u) => u.includes(want)) && (cached || lotUrls.every((u) => u.includes('size=512,512'))), `${lotUrls.length} requests`);

  // "Explore this neighborhood" from the note selects the block group under the map center.
  await page.evaluate(() => { selected = null; map.setView([34.0205, -118.392], 17.5, { animate: false }); });
  await page.waitForSelector('#lots-note:not([hidden])', { timeout: 4000 }).catch(() => {});
  if (await page.$('#lots-note:not([hidden])')) {
    await page.click('#lots-hood');
    check(`${label} "explore this neighborhood" opens the area under the map`, await page.evaluate(() => !!selected));
  } else check(`${label} "explore this neighborhood" opens the area under the map`, false, 'note did not show');

  // House panel: with overlay polygons shipped in the page, the nine map checks make no network calls,
  // and hovering a lot first means the click finds the remaining checks already done.
  if (process.env.OVERLAY_FIXTURE) {
    const fx = JSON.parse(process.env.OVERLAY_FIXTURE); // {inside:[lat,lng], hole:[lat,lng], layer:"liq"}
    const r = await page.evaluate(async (fx) => {
      const a = { AIN: '5555012345' };
      const inZone = await lotChecks(L.latLng(...fx.inside), a), inHole = await lotChecks(L.latLng(...fx.hole), a);
      return { inZone: inZone[fx.layer].v.length, local: !!inZone[fx.layer].local, inHole: inHole[fx.layer].v.length };
    }, fx);
    check(`${label} overlay checks answered in the page (point in zone)`, r.inZone === 1 && r.local, JSON.stringify(r));
    check(`${label} overlay checks respect holes in zones`, r.inHole === 0);
    check(`${label} no live requests for the nine overlay layers`, overlayCalls.length === 0, `${overlayCalls.length} calls`);
    // hover, then click: the panel should be complete within a moment of the click
    const t = await page.evaluate(async (fx) => {
      map.setView(fx.inside, 18, { animate: false });
      const ll = L.latLng(...fx.inside);
      hoverParcel({ latlng: ll });
      await new Promise((r) => setTimeout(r, 2500)); // the mouse rests on the lot
      const t0 = performance.now(); houseAt(ll);
      while (!document.querySelector('#house') || /Pulling/.test(document.querySelector('#house').textContent)) {
        await new Promise((r) => setTimeout(r, 25)); if (performance.now() - t0 > 8000) break; }
      return Math.round(performance.now() - t0);
    }, fx);
    check(`${label} house panel complete soon after click when hovered first`, t < 400, `${t} ms`);
  }

  check(`${label} no page errors`, errors.length === 0, errors.slice(0, 2).join(' | '));
  await browser.close();
}

(async () => {
  await run({ cached: false });
  await run({ cached: true });
  const failed = results.filter((r) => !r).length;
  console.log(failed ? `\n${failed} check(s) failed` : '\nAll checks passed');
  process.exit(failed ? 1 : 0);
})();
