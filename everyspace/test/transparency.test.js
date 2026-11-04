// Price transparency (comparisons with other sites, price beat, price-match claims), taxes, and owner tools.
// Fees follow the researched PLATFORMS table (RESEARCH_RESULTS.md §1): unknown fees are null, never zero.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { seed } from '../src/seed.js';
import { handleApi } from '../src/routes.js';
import { externalTotal, platformFor, PLATFORMS, STALE_DAYS } from '../src/compare.js';

const NOW = '2026-11-03T12:00:00Z';
function app() {
  let db = seed();
  const store = { get db() { return db; }, newId: (p) => `${p}_${db.seq++}`, save() {}, reset() { db = seed(); } };
  const call = (method, path, body, query = {}) => handleApi(store, method, path, body ?? {}, new URLSearchParams(query), { now: () => NOW });
  return { store, get: (path, query) => call('GET', path, null, query), post: (path, body) => call('POST', path, body) };
}
const round = (n) => Math.round(n * 100) / 100;
const TOT = 0.1175; // San Diego TOT, lowest zone

test('links are recognized by site; known fees are added, unknown fees are never treated as zero', () => {
  assert.equal(platformFor('https://www.airbnb.com/rooms/123'), 'airbnb');
  assert.equal(platformFor('https://neighbor.com/listing/9'), 'neighbor');
  assert.equal(platformFor('https://evil.example/airbnb.com'), null);
  const fresh = { verifiedAt: '2026-11-01' };
  const t = externalTotal({ platform: 'airbnb', rates: { daily: 225 }, cleaningFee: 75, ...fresh }, 'daily', '2027-01-10', '2027-01-13', 1, NOW);
  assert.equal(t.comparable, 750, 'Airbnb single-fee plan: guest pays the listed price and cleaning, no service fee');
  const v = externalTotal({ platform: 'vrbo', rates: { daily: 230 }, ...fresh }, 'daily', '2027-01-10', '2027-01-13', 1, NOW);
  assert.equal(v.comparable, null);
  assert.equal(v.feesUnknown, true);
  const old = externalTotal({ platform: 'airbnb', rates: { daily: 225 }, verifiedAt: '2026-09-01' }, 'daily', '2027-01-10', '2027-01-13', 1, NOW);
  assert.equal(old.stale, true, `quotes older than ${STALE_DAYS} days are not used`);
  assert.equal(old.comparable, null);
});

test('checkout: compared before tax, cheaper here, tax added to the all-in total', () => {
  const a = app();
  const q = a.post('quote', { renterId: 'u_sam', term: 'daily', start: '2027-01-10', end: '2027-01-13', items: [{ spaceId: 's_maple_home', qty: 1 }] });
  assert.equal(q.comparison.ours, q.preTax);
  assert.equal(q.preTax, round(210 * 3 * 1.1));
  assert.equal(q.tax.amount, round(210 * 3 * TOT), 'San Diego TOT on the rent');
  assert.equal(q.total, round(q.preTax + q.tax.amount));
  assert.equal(q.comparison.rows[0].name, 'Airbnb');
  assert.ok(q.comparison.rows[0].difference > 0, 'Airbnb costs more');
  assert.equal(q.comparison.rows[1].feesUnknown, true, 'Vrbo is listed but not priced');
  assert.equal(q.priceBeat, undefined);
  // A month or more is exempt from San Diego TOT; parking has no tax rule yet and says so.
  const month = a.post('quote', { renterId: 'u_sam', term: 'monthly', start: '2027-01-01', end: '2027-02-01', items: [{ spaceId: 's_maple_home', qty: 1 }] });
  assert.equal(month.tax.amount, 0);
  const park = a.post('quote', { renterId: 'u_sam', term: 'daily', start: '2027-01-12', end: '2027-01-13', items: [{ spaceId: 's_maple_driveway', qty: 1 }] });
  assert.ok(park.tax.undetermined.length > 0);
});

test('cheaper on Airbnb: checkout beats it from our fees and the owner gets the same', () => {
  const a = app();
  const cart = { renterId: 'u_priya', term: 'daily', start: '2027-01-10', end: '2027-01-11', items: [{ spaceId: 's_ana_room', qty: 1 }] };
  const q = a.post('quote', cart);
  const theirs = 79 + 20; // Airbnb single fee: listed price + cleaning
  assert.equal(q.priceBeat.name, 'Airbnb');
  assert.equal(q.priceBeat.capped, false);
  assert.ok(Math.abs(q.preTax - theirs * 0.95) <= 0.01, `beat by 5%: ${q.preTax}`);
  assert.ok(q.ourCut > 0, 'we still earn something');
  assert.equal(q.hostPayout, round(95 * 0.97), 'owner payout unchanged');
  const b = a.post('bookings', cart);
  assert.equal(b.quote.priceBeat.paidBy, 'everyspace');
  // Unknown fees (Swimply) can't trigger a beat.
  const pool = a.post('quote', { renterId: 'u_priya', term: 'hourly', start: '2027-01-10T18:00:00Z', end: '2027-01-10T20:00:00Z', items: [{ spaceId: 's_elm_pool', qty: 1 }] });
  assert.equal(pool.priceBeat, undefined);
  assert.equal(pool.comparison.rows[0].feesUnknown, true);
});

test('cheaper on Spacer than our whole fee can cover: we give up all of it, never more', () => {
  const a = app();
  const q = a.post('quote', { renterId: 'u_sam', term: 'monthly', start: '2027-01-01', end: '2027-02-01', items: [{ spaceId: 's_maple_driveway', qty: 1 }] });
  const theirs = round(100 * (1 + 1 / 3)); // Spacer: host price + a third
  assert.equal(q.priceBeat.name, 'Spacer');
  assert.equal(q.priceBeat.capped, true);
  assert.equal(q.priceBeat.credit, round(140 * 0.13));
  assert.equal(q.ourCut, 0);
  assert.ok(q.schedule.recurring > theirs, 'honest: still a little more than Spacer');
  // At a closer Spacer price, the beat fits inside our fees.
  a.post('spaces/s_maple_driveway/update', { actorId: 'u_maya', changes: { externalListings: [{ url: 'https://www.spacer.com/l/maple', rates: { monthly: 110 } }] } });
  const q2 = a.post('quote', { renterId: 'u_sam', term: 'monthly', start: '2027-01-01', end: '2027-02-01', items: [{ spaceId: 's_maple_driveway', qty: 1 }] });
  assert.equal(q2.priceBeat.capped, false);
  assert.ok(Math.abs(q2.schedule.recurring - 110 * (4 / 3) * 0.95) <= 0.01);
  const plain = a.post('quote', { renterId: 'u_sam', term: 'monthly', start: '2027-01-01', end: '2027-02-01', items: [{ spaceId: 's_maple_attic', qty: 1 }] });
  assert.equal(plain.ourCut, round(55 * 0.13), 'every quote shows what Everyspace earns');
});

test('price-match claims: renter only, lower price, matched links refund at once, unknown links go to review', () => {
  const a = app();
  const b = a.post('bookings', { renterId: 'u_sam', term: 'daily', start: '2027-02-01', end: '2027-02-04', items: [{ spaceId: 's_lake_home', qty: 1 }] });
  const ours = b.quote.preTax; // claims compare before tax, like checkout
  assert.throws(() => a.post(`bookings/${b.id}/price-match`, { userId: 'u_priya', url: 'https://www.airbnb.com/rooms/1', theirTotal: 100 }), (e) => e.details.some((d) => /Only the renter/.test(d)));
  assert.throws(() => a.post(`bookings/${b.id}/price-match`, { userId: 'u_sam', url: 'https://example.com/x', theirTotal: 100 }), (e) => e.details.some((d) => /Link a listing/.test(d)));
  assert.throws(() => a.post(`bookings/${b.id}/price-match`, { userId: 'u_sam', url: 'https://www.airbnb.com/rooms/1', theirTotal: ours + 5 }), (e) => e.details.some((d) => /isn't lower/.test(d)));
  const claim = a.post(`bookings/${b.id}/price-match`, { userId: 'u_sam', url: 'https://www.vrbo.com/some-other-listing', theirTotal: 400 });
  assert.equal(claim.status, 'in_review');
  assert.equal(claim.credit, Math.min(round(ours - 400 + 400 * 0.05), round(165 * 3 * 0.13)), 'capped at our fees on the booking');
  assert.equal(claim.capped, true);
  assert.throws(() => a.post(`bookings/${b.id}/price-match`, { userId: 'u_sam', url: 'https://www.vrbo.com/x', theirTotal: 300 }), (e) => e.details.some((d) => /already/.test(d)));
  // The owner drops their Airbnb price after Priya books: her matching claim is approved instantly.
  const b2 = a.post('bookings', { renterId: 'u_priya', term: 'daily', start: '2027-03-01', end: '2027-03-03', items: [{ spaceId: 's_lake_home', qty: 1 }] });
  const url = 'https://www.airbnb.com/demo/lakeview-cottage';
  a.post('spaces/s_lake_home/update', { actorId: 'u_rosa', changes: { externalListings: [{ url, rates: { daily: 100 }, cleaningFee: 0 }] } });
  const ok = a.post(`bookings/${b2.id}/price-match`, { userId: 'u_priya', url, theirTotal: 200 });
  assert.equal(ok.status, 'approved');
  assert.match(a.get(`bookings/${b2.id}/messages`, { userId: 'u_priya' }).at(-1).text, /Price match approved.*payout is unchanged/);
  const b3 = a.post('bookings', { renterId: 'u_sam', term: 'daily', start: '2027-04-01', end: '2027-04-03', items: [{ spaceId: 's_lake_home', qty: 1 }] });
  const low = a.post(`bookings/${b3.id}/price-match`, { userId: 'u_sam', url, theirTotal: 50 });
  assert.equal(low.status, 'in_review');
  assert.match(low.note, /lower than the Airbnb price we have on file/);
});

test('owners edit prices, pause, block dates and cross-list; nobody else can', () => {
  const a = app();
  assert.throws(() => a.post('spaces/s_maple_attic/update', { actorId: 'u_sam', changes: { paused: true } }), /Only the owner/);
  a.post('spaces/s_maple_attic/update', { actorId: 'u_maya', changes: { rates: { monthly: 60, lease: 52 } } });
  assert.equal(a.get('spaces/s_maple_attic').rates.monthly, 60);
  a.post('spaces/s_maple_attic/update', { actorId: 'u_maya', changes: { paused: true } });
  assert.ok(!a.get('search').spaces.some((s) => s.id === 's_maple_attic'), 'paused listings leave search');
  assert.throws(() => a.post('bookings', { renterId: 'u_sam', term: 'monthly', start: '2027-01-01', end: '2027-02-01', items: [{ spaceId: 's_maple_attic', qty: 1 }] }), /not available/i);
  a.post('spaces/s_maple_attic/update', { actorId: 'u_maya', changes: { paused: false, blackouts: [{ start: '2027-01-01', end: '2027-02-01', reason: 'Family visiting' }] } });
  assert.throws(() => a.post('bookings', { renterId: 'u_sam', term: 'monthly', start: '2027-01-01', end: '2027-02-01', items: [{ spaceId: 's_maple_attic', qty: 1 }] }), /not available/i);
  assert.throws(() => a.post('spaces/s_maple_attic/update', { actorId: 'u_maya', changes: { externalListings: [{ url: 'https://example.com/x', rates: { monthly: 50 } }] } }), /Link must be/);
  const s = a.post('spaces/s_maple_attic/update', { actorId: 'u_maya', changes: { externalListings: [{ url: 'https://www.neighbor.com/l/1', rates: { monthly: 70 } }] } });
  assert.equal(s.externalListings[0].platform, 'neighbor');
  assert.equal(s.externalListings[0].source, 'owner');
  assert.equal(s.externalListings[0].verifiedAt, '2026-11-03', 'dated when the owner entered it');
});

test('owner view: market ranges, "cheaper elsewhere" warning, and host-terms notices', () => {
  const a = app();
  const room = a.get('spaces/s_ana_room/manage', { userId: 'u_ana' });
  assert.equal(room.parity[0].cheapest.name, 'Airbnb');
  assert.ok(room.notices.some((n) => n.name === 'Airbnb'));
  const shop = a.get('spaces/s_elm_shop/manage', { userId: 'u_luis' });
  assert.match(shop.notices.find((n) => n.name === 'Peerspace').text, /most-favored-customer/);
  const drive = a.get('spaces/s_maple_driveway/manage', { userId: 'u_maya' });
  assert.ok(drive.market.daily.count >= 1 && drive.market.daily.min <= drive.market.daily.max);
  assert.throws(() => a.get('spaces/s_elm_pool/manage', { userId: 'u_maya' }), /Only the owner/);
});

test('cards: all-in price, and a comparison badge only when the other site can be priced', () => {
  const a = app();
  const s = a.get('search').spaces;
  const home = s.find((x) => x.id === 's_maple_home');
  assert.equal(home.allIn, round(210 * 1.1));
  assert.equal(home.compare.cheaperHere, true);
  assert.equal(s.find((x) => x.id === 's_elm_pool').compare, null, 'Swimply fees unknown: no badge');
  assert.equal(s.find((x) => x.id === 's_ana_room').compare.cheaperHere, false);
});

test('owner take-home: same take-home price here is cheaper for renters; unknown fees stay unknown', () => {
  const a = app();
  const room = a.get('spaces/s_ana_room/manage', { userId: 'u_ana' }).takeHome.find((r) => r.platform === 'airbnb');
  assert.equal(room.there, round(79 * (1 - 0.155)));
  assert.equal(round(room.sameRate * 0.97), room.there, 'same take-home');
  assert.ok(room.renterAtSame < room.renterThere, 'renters pay less here at the same owner take-home');
  const pool = a.get('spaces/s_elm_pool/manage', { userId: 'u_luis' }).takeHome.find((r) => r.platform === 'swimply');
  assert.equal(pool.there, null);
  assert.deepEqual(pool.thereRange, [round(38 * 0.75), round(38 * 0.85)], 'Swimply publishes a 15–25% range');
  a.post('spaces/s_elm_pool/update', { actorId: 'u_luis', changes: { mode: 'instant' } });
  const b = a.post('bookings', { renterId: 'u_sam', term: 'hourly', start: '2027-01-10T18:00:00Z', end: '2027-01-10T19:00:00Z', items: [{ spaceId: 's_elm_pool', qty: 1 }] });
  assert.equal(b.status, 'confirmed');
  assert.throws(() => a.post('spaces/s_hill_solar/update', { actorId: 'u_luis', changes: { mode: 'instant' } }), /proposals/);
});
