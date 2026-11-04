// Route-level tests for the app features: messaging, reviews, access details, host dashboard, listing checklist.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { seed } from '../src/seed.js';
import { handleApi } from '../src/routes.js';
import { CATEGORIES } from '../src/catalog.js';

const NOW = '2026-11-03T12:00:00Z';
function app() {
  let db = seed();
  const store = { get db() { return db; }, newId: (p) => `${p}_${db.seq++}`, save() {}, reset() { db = seed(); } };
  const call = (method, path, body, query = {}) => handleApi(store, method, path, body ?? {}, new URLSearchParams(query), { now: () => NOW });
  return { store, get: (path, query) => call('GET', path, null, query), post: (path, body) => call('POST', path, body) };
}

test('booking starts a conversation; only the two parties can read or post', () => {
  const a = app();
  const b = a.post('bookings', { renterId: 'u_sam', term: 'monthly', start: '2026-12-01', end: '2027-01-01', items: [{ spaceId: 's_maple_attic', qty: 1 }], note: 'Mostly holiday decorations.' });
  const msgs = a.get(`bookings/${b.id}/messages`, { userId: 'u_maya' });
  assert.equal(msgs[0].from, 'system');
  assert.match(msgs[0].text, /confirmed/);
  assert.equal(msgs[1].text, 'Mostly holiday decorations.');
  a.post(`bookings/${b.id}/messages`, { from: 'u_maya', text: 'Sounds good!' });
  assert.equal(a.get('threads', { userId: 'u_sam' })[0].last.text, 'Sounds good!');
  assert.throws(() => a.get(`bookings/${b.id}/messages`, { userId: 'u_priya' }), /Only the renter and host/);
  assert.throws(() => a.post(`bookings/${b.id}/messages`, { from: 'u_sam', text: '   ' }), /required/);
});

test('access details are hidden until a booking is confirmed', () => {
  const a = app();
  assert.equal(a.get('spaces/s_maple_home').access, undefined);
  const b = a.post('bookings', { renterId: 'u_sam', term: 'daily', start: '2027-02-10', end: '2027-02-13', items: [{ spaceId: 's_maple_home', qty: 1 }] });
  const mine = () => a.get('bookings', { userId: 'u_sam' }).find((x) => x.id === b.id);
  assert.equal(mine().status, 'pending');
  assert.equal(mine().access, null);
  a.post(`bookings/${b.id}/approve`, { actorId: 'u_maya' });
  assert.match(mine().access[0].text, /Smart lock/);
  assert.equal(a.get('bookings', { userId: 'u_priya' }).find((x) => x.id === b.id), undefined);
});

test('reviews: renter only, after the booking ends, once', () => {
  const a = app();
  const past = a.get('bookings', { userId: 'u_dev' }).find((x) => x.id === 'bk_seed_8'); // EV charging, Oct 20
  assert.equal(past.effective, 'completed');
  assert.equal(past.canReview, true);
  assert.throws(() => a.post('bookings/bk_seed_8/review', { by: 'u_jordan', rating: 5 }), /Only the renter/);
  assert.throws(() => a.post('bookings/bk_seed_8/review', { by: 'u_dev', rating: 7 }), /1–5/);
  a.post('bookings/bk_seed_8/review', { by: 'u_dev', rating: 4, text: 'Fast charger.' });
  assert.throws(() => a.post('bookings/bk_seed_8/review', { by: 'u_dev', rating: 5 }), /already/);
  assert.deepEqual(a.get('spaces/s_oak_ev').rating, { avg: 4, count: 1 });
  assert.throws(() => a.post('bookings/bk_seed_2/review', { by: 'u_sam', rating: 5 }), /once the booking has ended/);
});

test('host dashboard: requests to act on, and earnings spread over lease months', () => {
  const a = app();
  const maya = a.get('host/summary', { hostId: 'u_maya' });
  assert.deepEqual(maya.needsAction.map((b) => b.id), ['bk_seed_6']);
  assert.ok(maya.upcoming.some((b) => b.id === 'bk_seed_2'));
  // Dev's garage bay: $95/mo Oct–Dec, host keeps 97%.
  const nov = maya.earnings.byMonth.find((m) => m.month === '2026-11').amount;
  assert.ok(nov >= 92.15, `November should include the bay rent, got ${nov}`);
  const jordan = a.get('host/summary', { hostId: 'u_jordan' });
  const months = jordan.earnings.byMonth.filter((m) => m.month >= '2026-11' && m.month <= '2027-04');
  assert.ok(months.every((m) => Math.abs(m.amount - 2425) < 1), 'Priya\'s $2,500 lease pays ~$2,425/mo to the host');
});

test('calendar shows free units per day', () => {
  const a = app();
  const days = a.get('spaces/s_maple_driveway/calendar', { from: '2026-11-20', days: 3 });
  assert.deepEqual(days.map((d) => d.free), [3, 1, 3]);
});

test('publishing a listing requires the category checklist', () => {
  const a = app();
  const base = { propertyId: 'p_maple', category: 'pool', title: 'Kiddie pool', rates: { hourly: 10 } };
  assert.throws(() => a.post('spaces', base), /Confirm before publishing: County health classification/);
  const s = a.post('spaces', { ...base, checklist: CATEGORIES.pool.checklist });
  assert.equal(a.get(`spaces/${s.id}`).title, 'Kiddie pool');
});

test('a cart cannot mix hosts', () => {
  const a = app();
  assert.throws(() => a.post('bookings', { renterId: 'u_sam', term: 'monthly', start: '2027-01-01', end: '2027-02-01',
    items: [{ spaceId: 's_maple_attic', qty: 1 }, { spaceId: 's_ana_closet', qty: 1 }] }), /different hosts/);
});

test('everyday search never shows infrastructure; the business side does', () => {
  const a = app();
  const consumer = a.get('search').spaces;
  assert.ok(consumer.length > 20);
  assert.ok(consumer.every((s) => !['energy', 'commercial'].includes(s.group)), 'no solar/battery/fleet in everyday explore');
  const biz = a.get('search', { audience: 'business' }).spaces;
  assert.ok(biz.some((s) => s.id === 's_maple_roof') && biz.some((s) => s.id === 's_hill_fleet'));
  assert.ok(biz.every((s) => ['energy', 'commercial'].includes(s.group)));
  assert.equal(a.get('search', { audience: 'business' }).packages.length, 0);
});

test('only business accounts can propose on infrastructure sites', () => {
  const a = app();
  const cart = { term: 'infrastructure', start: '2027-01-01', end: '2047-01-01', items: [{ spaceId: 's_oak_roof', qty: 1 }] };
  assert.throws(() => a.post('quote', { ...cart, renterId: 'u_sam' }), (e) => e.details.some((d) => /business accounts/.test(d)));
  const b = a.post('bookings', { ...cart, renterId: 'u_sunco' });
  assert.equal(b.status, 'proposed');
  // A fleet can lease van parking monthly, also as a proposal
  const f = a.post('bookings', { term: 'monthly', start: '2026-12-01', end: '2027-03-01', renterId: 'u_greenleaf', items: [{ spaceId: 's_hill_fleet', qty: 4 }] });
  assert.equal(f.status, 'proposed');
  assert.equal(f.quote.schedule.recurring, Math.round(4 * 180 * 1.1 * 100) / 100);
});

test('saving spaces to a wishlist', () => {
  const a = app();
  assert.deepEqual(a.get('saves', { userId: 'u_sam' }).map((s) => s.id).sort(), ['s_elm_pool', 's_lake_home']);
  assert.deepEqual(a.post('saves', { userId: 'u_sam', spaceId: 's_maple_backyard' }), { saved: true });
  assert.equal(a.get('spaces/s_maple_backyard', { userId: 'u_sam' }).saved, true);
  assert.equal(a.get('search', { userId: 'u_sam', q: 'fire pit' }).spaces[0].saved, true);
  assert.deepEqual(a.post('saves', { userId: 'u_sam', spaceId: 's_maple_backyard' }), { saved: false });
  assert.throws(() => a.post('saves', { userId: 'u_nobody', spaceId: 's_maple_backyard' }), /Unknown user/);
});
