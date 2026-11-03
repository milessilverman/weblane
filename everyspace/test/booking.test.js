import { test } from 'node:test';
import assert from 'node:assert/strict';
import { seed } from '../src/seed.js';
import { createBooking, quote, transition, BookingError } from '../src/booking.js';
import { checkAvailability, unitsFree } from '../src/availability.js';
import { search } from '../src/listings.js';

let n = 0;
const newId = (p) => `${p}_t${++n}`;
const book = (db, cart) => createBooking(db, cart, { newId });
const rejects = (fn, match) => assert.throws(fn, (e) => e instanceof BookingError && (!match || [e.message, ...e.details].some((m) => match.test(m))));

test('event-day parking: quantity is shared and the festival rate applies', () => {
  const db = seed(); // Sam already holds 2 of 3 driveway spots on Nov 21
  const day = { term: 'daily', start: '2026-11-21', end: '2026-11-22' };
  assert.equal(unitsFree(db, db.spaces.find((s) => s.id === 's_maple_driveway'), day.start, day.end), 1);
  rejects(() => book(db, { ...day, renterId: 'u_priya', items: [{ spaceId: 's_maple_driveway', qty: 2 }] }), /Only 1 of 3/);
  const b = book(db, { ...day, renterId: 'u_priya', items: [{ spaceId: 's_maple_driveway', qty: 1 }] });
  assert.equal(b.status, 'confirmed'); // parking is instant-book
  assert.equal(b.quote.rent, 40); // Harvest Festival rate, not the usual $15
  const normal = quote(db, { term: 'daily', start: '2026-11-25', end: '2026-11-26', renterId: 'u_priya', items: [{ spaceId: 's_maple_driveway', qty: 1 }] });
  assert.equal(normal.rent, 15);
});

test('capacity counts peak overlap, not every overlapping booking', () => {
  const db = seed();
  const bays = (start, end) => ({ term: 'weekly', start, end, renterId: 'u_sam', items: [{ spaceId: 's_maple_bay', qty: 3 }] });
  book(db, bays('2027-01-01', '2027-01-08'));
  book(db, bays('2027-01-08', '2027-01-15'));
  // Each week is full on its own, so a 2-week request for 1 bay overlapping both must fail...
  rejects(() => book(db, bays('2027-01-05', '2027-01-12')), /Only 0 of 3/);
  // ...but two back-to-back full weeks never stack to 6.
  assert.ok(checkAvailability(db, [{ spaceId: 's_maple_bay', qty: 3 }], '2027-01-15', '2027-01-22').ok);
});

test('spaces that share room conflict (driveway vs RV pad)', () => {
  const db = seed();
  rejects(() => book(db, { term: 'weekly', start: '2026-11-18', end: '2026-11-25', renterId: 'u_priya', items: [{ spaceId: 's_maple_rv', qty: 1 }] }), /shares room/);
});

test('hierarchy: renting part blocks the whole, renting the whole blocks the parts', () => {
  const db = seed();
  const span = { term: 'daily', start: '2026-12-10', end: '2026-12-13' };
  book(db, { ...span, term: 'hourly', start: '2026-12-11T18:00:00Z', end: '2026-12-11T22:00:00Z', renterId: 'u_sam', items: [{ spaceId: 's_maple_backyard', qty: 1 }] });
  rejects(() => book(db, { ...span, renterId: 'u_priya', items: [{ spaceId: 's_maple_home', qty: 1 }] }), /Part of Whole house/);

  const db2 = seed();
  book(db2, { ...span, renterId: 'u_priya', items: [{ spaceId: 's_maple_home', qty: 1 }] });
  rejects(() => book(db2, { ...span, renterId: 'u_sam', items: [{ spaceId: 's_maple_room', qty: 1 }] }), /Whole house .* is booked/);
  // The roof is independent of the house: solar can be leased while the house is rented.
  assert.ok(checkAvailability(db2, [{ spaceId: 's_maple_roof', qty: 1 }], '2026-12-01', '2046-12-01').ok);
});

test('whole-home stays are request-to-book and hold the dates while pending', () => {
  const db = seed();
  const cart = { term: 'daily', start: '2026-12-20', end: '2026-12-23', renterId: 'u_sam', items: [{ spaceId: 's_maple_home', qty: 1 }] };
  const b = book(db, cart);
  assert.equal(b.status, 'pending');
  rejects(() => book(db, { ...cart, renterId: 'u_priya' }), /available/);
  rejects(() => transition(db, b.id, 'approve', 'u_sam'), /Only the host/);
  assert.equal(transition(db, b.id, 'approve', 'u_maya').status, 'confirmed');
  rejects(() => book(db, { ...cart, start: '2026-12-01', end: '2026-12-02' }), /at least 2 days/);
});

test('apartment parking is add-on only, capped at 2 per unit', () => {
  const db = seed();
  const lease = { term: 'lease', start: '2027-01-01', end: '2028-01-01', renterId: 'u_sam' };
  rejects(() => book(db, { ...lease, items: [{ spaceId: 's_oak_parking', qty: 1 }] }), /only available with/);
  rejects(() => book(db, { ...lease, items: [{ spaceId: 's_oak_1a', qty: 1 }, { spaceId: 's_oak_parking', qty: 3 }] }), /max 2 per apartment/);
  const b = book(db, { ...lease, items: [{ spaceId: 's_oak_1a', qty: 1 }, { spaceId: 's_oak_parking', qty: 2 }] });
  assert.equal(b.status, 'pending');
  assert.equal(b.quote.schedule.recurring, Math.round((1950 + 2 * 140) * 1.1 * 100) / 100);
});

test('an existing tenant can add parking later; the locker is cheaper for tenants', () => {
  const db = seed(); // Priya leases 1B Sep 2026 – Sep 2027
  const later = { term: 'monthly', start: '2027-01-01', end: '2027-04-01' };
  const p = book(db, { ...later, renterId: 'u_priya', items: [{ spaceId: 's_oak_parking', qty: 2 }] });
  assert.equal(p.quote.rent, 2 * 150 * 3);
  rejects(() => book(db, { ...later, renterId: 'u_priya', items: [{ spaceId: 's_oak_parking', qty: 1 }] }), /you'd have 3/);
  // Add-on can't outlast the anchor lease
  rejects(() => book(db, { term: 'monthly', start: '2027-08-01', end: '2027-11-01', renterId: 'u_priya', items: [{ spaceId: 's_oak_parking', qty: 1 }] }), /only available with/);

  const tenant = quote(db, { ...later, renterId: 'u_priya', items: [{ spaceId: 's_oak_locker', qty: 1 }] });
  const outsider = quote(db, { ...later, renterId: 'u_sam', items: [{ spaceId: 's_oak_locker', qty: 1 }] });
  assert.equal(tenant.rent, 180);
  assert.equal(outsider.rent, 270);
});

test('packages: fixed-price and percent-off bundles', () => {
  const db = seed();
  const q = quote(db, { term: 'lease', start: '2027-01-01', end: '2028-01-01', renterId: 'u_sam', packageId: 'pk_1a_2park' });
  assert.equal(q.schedule.recurring, Math.round(2190 * 1.1 * 100) / 100);
  assert.equal(q.rent, 2190 * 12);
  const b = book(db, { term: 'lease', start: '2027-01-01', end: '2028-01-01', renterId: 'u_sam', packageId: 'pk_1a_2park' });
  assert.deepEqual(b.items.map((i) => i.spaceId), ['s_oak_1a', 's_oak_parking']);
  // 1B is already leased to Priya, so its package is unavailable for the same period.
  const q2 = quote(db, { term: 'monthly', start: '2027-01-01', end: '2027-02-01', renterId: 'u_sam', packageId: 'pk_1b_park_locker' });
  assert.equal(q2.availability.ok, false);
  assert.equal(q2.packageDiscount, Math.round((2750 + 150 + 60) * 0.1 * 100) / 100);
});

test('rooftop solar: proposal flow and minimum term', () => {
  const db = seed();
  const cart = { term: 'infrastructure', renterId: 'u_sunco', items: [{ spaceId: 's_maple_roof', qty: 1 }] };
  rejects(() => book(db, { ...cart, start: '2027-01-01', end: '2032-01-01' }), /10–25 years/);
  const b = book(db, { ...cart, start: '2027-01-01', end: '2047-01-01' });
  assert.equal(b.status, 'proposed');
  assert.equal(b.quote.schedule.dueNow, 0);
  for (const next of ['site_assessment', 'contract', 'confirmed']) assert.equal(transition(db, b.id, 'advance', 'u_maya').status, next);
});

test('terms, containers and self-booking are enforced', () => {
  const db = seed();
  rejects(() => quote(db, { term: 'hourly', start: '2027-01-01T10:00:00Z', end: '2027-01-01T12:00:00Z', renterId: 'u_sam', items: [{ spaceId: 's_maple_attic', qty: 1 }] }), /can't be rented hourly/);
  rejects(() => quote(db, { term: 'lease', start: '2027-01-01', end: '2027-04-01', renterId: 'u_sam', items: [{ spaceId: 's_oak_1a', qty: 1 }] }), /6–24 months/);
  rejects(() => book(db, { term: 'monthly', start: '2027-01-01', end: '2027-02-01', renterId: 'u_maya', items: [{ spaceId: 's_maple_attic', qty: 1 }] }), /own space/);
  rejects(() => quote(db, { term: 'monthly', start: '2027-01-01', end: '2027-02-01', renterId: 'u_sam', items: [{ spaceId: 's_maple_garage', qty: 1 }] }), /not rentable/);
});

test('search hides containers and filters by term and dates', () => {
  const db = seed();
  const all = search(db, {});
  assert.ok(!all.spaces.some((s) => s.rentable === false));
  const hourlyParking = search(db, { group: 'parking', term: 'hourly' }).spaces.map((s) => s.id);
  assert.deepEqual(hourlyParking.sort(), ['s_maple_driveway', 's_oak_ev']);
  const fest = search(db, { category: 'parking_spot', start: '2026-11-21', end: '2026-11-22' }).spaces;
  assert.equal(fest.find((s) => s.id === 's_maple_driveway').unitsFree, 1);
  assert.match(fest.find((s) => s.id === 's_oak_parking').addonNote, /Only with/);
});
