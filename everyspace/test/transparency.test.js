// Price transparency (comparisons with other sites, price beat, price-match claims) and owner tools.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { seed } from '../src/seed.js';
import { handleApi } from '../src/routes.js';
import { externalTotal, platformFor, PLATFORMS } from '../src/compare.js';

const NOW = '2026-11-03T12:00:00Z';
function app() {
  let db = seed();
  const store = { get db() { return db; }, newId: (p) => `${p}_${db.seq++}`, save() {}, reset() { db = seed(); } };
  const call = (method, path, body, query = {}) => handleApi(store, method, path, body ?? {}, new URLSearchParams(query), { now: () => NOW });
  return { store, get: (path, query) => call('GET', path, null, query), post: (path, body) => call('POST', path, body) };
}
const round = (n) => Math.round(n * 100) / 100;

test('links are recognized by site; other sites\' fees are added to their price', () => {
  assert.equal(platformFor('https://www.airbnb.com/rooms/123'), 'airbnb');
  assert.equal(platformFor('https://neighbor.com/listing/9'), 'neighbor');
  assert.equal(platformFor('https://evil.example/airbnb.com'), null);
  const t = externalTotal({ platform: 'airbnb', rates: { daily: 225 }, cleaningFee: 75 }, 'daily', '2027-01-10', '2027-01-13');
  assert.equal(t.comparable, round((225 * 3 + 75) * (1 + PLATFORMS.airbnb.guestFeePct)));
});

test('checkout shows the comparison when we are cheaper, with no price beat', () => {
  const a = app();
  const q = a.post('quote', { renterId: 'u_sam', term: 'daily', start: '2027-01-10', end: '2027-01-13', items: [{ spaceId: 's_maple_home', qty: 1 }] });
  assert.equal(q.comparison.ours, q.total);
  assert.deepEqual(q.comparison.rows.map((r) => r.name), ['Airbnb', 'Vrbo']);
  assert.ok(q.comparison.rows.every((r) => r.difference > 0), 'other sites cost more');
  assert.equal(q.priceBeat, undefined);
});

test('cheaper elsewhere: the price is beaten automatically and Everyspace pays for it', () => {
  const a = app();
  const cart = { renterId: 'u_priya', term: 'hourly', start: '2027-01-10T18:00:00Z', end: '2027-01-10T20:00:00Z', items: [{ spaceId: 's_elm_pool', qty: 1 }] };
  const q = a.post('quote', cart);
  const theirs = round(38 * 2 * 1.10);
  const cut = round(90 * 0.10 + 90 * 0.03); // our service fee + owner fee
  assert.equal(q.priceBeat.name, 'Swimply');
  assert.equal(q.priceBeat.theirs, theirs);
  // The owner charges much less on Swimply, so even our whole cut can't fully beat it: we give all of it up, never more.
  assert.equal(q.priceBeat.capped, true);
  assert.equal(q.priceBeat.credit, cut);
  assert.equal(q.total, round(99 - cut));
  assert.equal(q.ourCut, 0);
  assert.equal(q.hostPayout, round(90 * 0.97), 'owner payout unchanged');
  const b = a.post('bookings', cart);
  assert.equal(b.quote.priceBeat.paidBy, 'everyspace');
});

test('slightly cheaper elsewhere: we shrink our cut and come out below them', () => {
  const a = app();
  // Maya lists the driveway on SpotHero at $13/day (+ SpotHero's booking fee); here it's $15 + our 10%.
  a.post('spaces/s_maple_driveway/update', { actorId: 'u_maya', changes: { externalListings: [{ url: 'https://www.spothero.com/l/maple', rates: { daily: 13 } }] } });
  const q = a.post('quote', { renterId: 'u_sam', term: 'daily', start: '2027-01-12', end: '2027-01-13', items: [{ spaceId: 's_maple_driveway', qty: 1 }] });
  const theirs = 13 + PLATFORMS.spothero.perBookingFee;
  assert.equal(q.priceBeat.capped, false);
  assert.ok(Math.abs(q.total - theirs * 0.95) <= 0.01, `beat by 5%: ${q.total}`);
  assert.ok(q.total < theirs);
  assert.ok(q.ourCut > 0 && q.ourCut < round(15 * 0.13), 'we still earn a little');
  assert.equal(q.hostPayout, round(15 * 0.97));
  // Without any cross-listing, the receipt still shows what we earn.
  const plain = a.post('quote', { renterId: 'u_sam', term: 'monthly', start: '2027-01-01', end: '2027-02-01', items: [{ spaceId: 's_maple_attic', qty: 1 }] });
  assert.equal(plain.ourCut, round(55 * 0.13));
});

test('price-match claims: renter only, lower price, matched links refund at once, unknown links go to review', () => {
  const a = app();
  const b = a.post('bookings', { renterId: 'u_sam', term: 'daily', start: '2027-02-01', end: '2027-02-04', items: [{ spaceId: 's_lake_home', qty: 1 }] });
  const ours = b.quote.total;
  assert.throws(() => a.post(`bookings/${b.id}/price-match`, { userId: 'u_priya', url: 'https://www.airbnb.com/rooms/1', theirTotal: 100 }), (e) => e.details.some((d) => /Only the renter/.test(d)));
  assert.throws(() => a.post(`bookings/${b.id}/price-match`, { userId: 'u_sam', url: 'https://example.com/x', theirTotal: 100 }), (e) => e.details.some((d) => /Link a listing/.test(d)));
  assert.throws(() => a.post(`bookings/${b.id}/price-match`, { userId: 'u_sam', url: 'https://www.airbnb.com/rooms/1', theirTotal: ours + 5 }), (e) => e.details.some((d) => /isn't lower/.test(d)));
  const claim = a.post(`bookings/${b.id}/price-match`, { userId: 'u_sam', url: 'https://www.vrbo.com/some-other-listing', theirTotal: 400 });
  assert.equal(claim.status, 'in_review');
  // Difference + 5% would be $164.50, but the beat never exceeds our own cut on the booking.
  assert.equal(claim.credit, Math.min(round(ours - 400 + 400 * 0.05), round(165 * 3 * 0.13)));
  assert.equal(claim.capped, true);
  assert.throws(() => a.post(`bookings/${b.id}/price-match`, { userId: 'u_sam', url: 'https://www.vrbo.com/x', theirTotal: 300 }), (e) => e.details.some((d) => /already/.test(d)));
  // The owner drops their Airbnb price after Priya books: her matching claim is approved instantly.
  const b2 = a.post('bookings', { renterId: 'u_priya', term: 'daily', start: '2027-03-01', end: '2027-03-03', items: [{ spaceId: 's_lake_home', qty: 1 }] });
  const url = 'https://www.airbnb.com/demo/lakeview-cottage';
  a.post('spaces/s_lake_home/update', { actorId: 'u_rosa', changes: { externalListings: [{ url, rates: { daily: 100 }, cleaningFee: 0 }] } });
  const onFile = round(200 * (1 + PLATFORMS.airbnb.guestFeePct));
  const ok = a.post(`bookings/${b2.id}/price-match`, { userId: 'u_priya', url, theirTotal: onFile });
  assert.equal(ok.status, 'approved');
  const msgs = a.get(`bookings/${b2.id}/messages`, { userId: 'u_priya' });
  assert.match(msgs.at(-1).text, /Price match approved.*payout is unchanged/);
  // Claiming far below what that listing actually costs is not approved automatically.
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
});

test('owner view shows market ranges and warns when it is cheaper elsewhere', () => {
  const a = app();
  const pool = a.get('spaces/s_elm_pool/manage', { userId: 'u_luis' });
  assert.equal(pool.parity[0].cheapest.name, 'Swimply');
  const drive = a.get('spaces/s_maple_driveway/manage', { userId: 'u_maya' });
  assert.deepEqual(drive.parity, []);
  assert.ok(drive.market.daily.count >= 1 && drive.market.daily.min <= drive.market.daily.max);
  assert.throws(() => a.get('spaces/s_elm_pool/manage', { userId: 'u_maya' }), /Only the owner/);
});

test('cards carry the all-in price and the comparison badge', () => {
  const a = app();
  const s = a.get('search').spaces;
  const home = s.find((x) => x.id === 's_maple_home');
  assert.equal(home.allIn, round(210 * 1.1));
  assert.equal(home.compare.cheaperHere, true);
  assert.equal(s.find((x) => x.id === 's_elm_pool').compare.cheaperHere, false);
});

test('owner take-home: the price here that pays the same as elsewhere is cheaper for renters', () => {
  const a = app();
  const pool = a.get('spaces/s_elm_pool/manage', { userId: 'u_luis' });
  const row = pool.takeHome.find((r) => r.platform === 'swimply');
  assert.equal(row.there, round(38 * (1 - PLATFORMS.swimply.hostFeePct)));
  assert.equal(round(row.sameRate * 0.97), row.there, 'same take-home');
  assert.ok(row.renterAtSame < row.renterThere, 'renters pay less here at the same owner take-home');
  // Owners pick instant book or approval; business sites can't.
  a.post('spaces/s_elm_pool/update', { actorId: 'u_luis', changes: { mode: 'instant' } });
  const b = a.post('bookings', { renterId: 'u_sam', term: 'hourly', start: '2027-01-10T18:00:00Z', end: '2027-01-10T19:00:00Z', items: [{ spaceId: 's_elm_pool', qty: 1 }] });
  assert.equal(b.status, 'confirmed');
  assert.throws(() => a.post('spaces/s_hill_solar/update', { actorId: 'u_luis', changes: { mode: 'instant' } }), /proposals/);
});
