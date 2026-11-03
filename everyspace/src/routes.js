// API routes, independent of transport. Used by the Node server and by the
// single-file standalone build (which calls them directly in the browser).
import { CATEGORIES, GROUPS, MODES, TERMS } from './catalog.js';
import { BookingError, createBooking, isAnchorFor, quote, transition } from './booking.js';
import { createPackage, createProperty, createSpace, search } from './listings.js';
import { describeAddon } from './describe.js';

export class NotFound extends Error {}

// store: { db, newId(prefix), save(), reset() }
export function handleApi(store, method, path, body = {}, params = new URLSearchParams(), { spec } = {}) {
  const mutate = (fn) => { const out = fn(); store.save(); return out; };
  const routes = [
    ['GET', /^catalog$/, () => ({ terms: TERMS, groups: GROUPS, categories: CATEGORIES, modes: MODES })],
    ['GET', /^users$/, () => store.db.users],
    ['GET', /^spec$/, () => ({ html: spec ? spec() : '' })],
    ['GET', /^search$/, () => search(store.db, Object.fromEntries(params))],
    ['GET', /^properties$/, () => listProperties(store.db, params.get('hostId'))],
    ['GET', /^spaces\/([\w-]+)$/, ([, id]) => spaceDetail(store.db, id)],
    ['POST', /^properties$/, () => mutate(() => createProperty(store.db, body, store.newId))],
    ['POST', /^spaces$/, () => mutate(() => createSpace(store.db, body, store.newId))],
    ['POST', /^packages$/, () => mutate(() => createPackage(store.db, body, store.newId))],
    ['POST', /^quote$/, () => quote(store.db, body)],
    ['POST', /^bookings$/, () => mutate(() => createBooking(store.db, body, { newId: store.newId }))],
    ['GET', /^bookings$/, () => listBookings(store.db, params.get('userId'))],
    ['POST', /^bookings\/([\w-]+)\/(approve|decline|advance|cancel)$/, ([, id, action]) =>
      mutate(() => transition(store.db, id, action, body.actorId))],
    ['POST', /^reset$/, () => { store.reset(); return { ok: true }; }],
  ];
  const route = routes.find(([m, re]) => m === method && re.test(path));
  if (!route) throw new NotFound('Not found');
  return route[2](path.match(route[1]));
}

// Errors the user caused (bad input, rule broken) rather than bugs.
export function isUserError(err) {
  return err instanceof BookingError || err instanceof SyntaxError ||
    /required|not found|must|can't|Unknown|Invalid|Set at least|need/i.test(err.message);
}

function listProperties(db, hostId) {
  return db.properties.filter((p) => !hostId || p.hostId === hostId).map((p) => ({
    ...p,
    spaces: db.spaces.filter((s) => s.propertyId === p.id).map((s) => ({ ...s, addonNote: describeAddon(db, s) })),
    packages: db.packages.filter((k) => k.propertyId === p.id),
  }));
}

function spaceDetail(db, id) {
  const s = db.spaces.find((x) => x.id === id);
  if (!s) throw new BookingError('Space not found');
  return {
    ...s,
    categoryInfo: CATEGORIES[s.category],
    property: db.properties.find((p) => p.id === s.propertyId),
    addonNote: describeAddon(db, s),
    // Add-ons this space can carry (e.g. parking/lockers for an apartment)
    addons: db.spaces.filter((a) => a.policy && a.policy !== 'standalone' && isAnchorFor(a, s))
      .map((a) => ({ ...a, addonNote: describeAddon(db, a) })),
    packages: db.packages.filter((p) => p.items.some((i) => i.spaceId === id)),
  };
}

function listBookings(db, userId) {
  const title = (id) => db.spaces.find((s) => s.id === id)?.title ?? id;
  const name = (id) => db.users.find((u) => u.id === id)?.name ?? id;
  return db.bookings
    .filter((b) => !userId || b.renterId === userId || b.hostId === userId)
    .map((b) => ({ ...b, role: b.hostId === userId ? 'host' : 'renter', renterName: name(b.renterId), hostName: name(b.hostId),
      itemsLabel: b.items.map((i) => `${i.qty > 1 ? `${i.qty}× ` : ''}${title(i.spaceId)}`).join(' + '),
      packageName: db.packages.find((p) => p.id === b.packageId)?.name ?? null }))
    .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
}
