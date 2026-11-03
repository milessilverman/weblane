// API routes, independent of transport. Used by the Node server and by the
// single-file standalone build (which calls them directly in the browser).
import { AUDIENCES, CATEGORIES, GROUPS, GROUP_ICONS, MODES, TERMS, TYPICAL } from './catalog.js';
import { BookingError, createBooking, isAnchorFor, quote, transition } from './booking.js';
import { createPackage, createProperty, createSpace, search } from './listings.js';
import { describeAddon } from './describe.js';
import { addReview, canReview, effectiveStatus, messagesFor, postMessage, ratingFor, systemMessage, threadsFor } from './social.js';
import { calendar, hostSummary } from './host.js';
import { BEAT_PCT, CLAIM_WINDOW_HOURS, evaluateClaim, PLATFORMS, unitComparison } from './compare.js';
import { marketFor, ownerView, updateSpace } from './owner.js';
import { HOST_FEE, SERVICE_FEE } from './pricing.js';

export class NotFound extends Error {}

const SHOW_ACCESS = new Set(['confirmed', 'active']);
const ACTION_TEXT = {
  confirmed: 'Host approved the booking. Access details are now in your trip.',
  declined: 'Host declined the request.',
  cancelled: 'Booking was cancelled.',
  site_assessment: 'Proposal accepted, site assessment is next.',
  contract: 'Site assessment passed, contract sent for signature.',
};

// store: { db, newId(prefix), save(), reset() }
export function handleApi(store, method, path, body = {}, params = new URLSearchParams(), { spec, now = () => new Date().toISOString() } = {}) {
  const db = store.db;
  const opts = () => ({ now: now(), newId: store.newId });
  const mutate = (fn) => { const out = fn(); store.save(); return out; };
  const routes = [
    ['GET', /^catalog$/, () => ({ terms: TERMS, groups: GROUPS, groupIcons: GROUP_ICONS, categories: CATEGORIES, modes: MODES, audiences: AUDIENCES, typical: TYPICAL })],
    ['GET', /^users$/, () => db.users],
    ['GET', /^spec$/, () => ({ html: spec ? spec() : '' })],
    ['GET', /^search$/, () => search(db, Object.fromEntries(params))],
    ['GET', /^properties$/, () => listProperties(db, params.get('hostId'))],
    ['GET', /^spaces\/([\w-]+)$/, ([, id]) => spaceDetail(db, id, params.get('userId'))],
    ['GET', /^spaces\/([\w-]+)\/calendar$/, ([, id]) => calendar(db, id, params.get('from') ?? now().slice(0, 10), Number(params.get('days') ?? 42))],
    ['POST', /^properties$/, () => mutate(() => createProperty(db, body, store.newId))],
    ['POST', /^spaces$/, () => mutate(() => createSpace(db, body, store.newId))],
    ['POST', /^packages$/, () => mutate(() => createPackage(db, body, store.newId))],
    ['POST', /^quote$/, () => quote(db, body)],
    ['POST', /^bookings$/, () => mutate(() => {
      const b = createBooking(db, body, opts());
      const what = listBookings(db, b.renterId, now()).find((x) => x.id === b.id).itemsLabel;
      const renter = db.users.find((u) => u.id === b.renterId)?.name;
      systemMessage(db, b.id, b.status === 'confirmed' ? `Booking confirmed: ${what}.`
        : b.status === 'pending' ? `${renter} requested ${what}. The host has 24 hours to respond.`
          : `${renter} sent a proposal for ${what}.`, opts());
      if (body.note?.trim()) postMessage(db, b.id, b.renterId, body.note, opts());
      return b;
    })],
    ['GET', /^bookings$/, () => listBookings(db, params.get('userId'), now())],
    ['POST', /^bookings\/([\w-]+)\/(approve|decline|advance|cancel)$/, ([, id, action]) => mutate(() => {
      const b = transition(db, id, action, body.actorId, opts());
      if (ACTION_TEXT[b.status]) systemMessage(db, b.id, ACTION_TEXT[b.status], opts());
      return b;
    })],
    ['GET', /^bookings\/([\w-]+)\/messages$/, ([, id]) => messagesFor(db, id, params.get('userId'))],
    ['POST', /^bookings\/([\w-]+)\/messages$/, ([, id]) => mutate(() => postMessage(db, id, body.from, body.text, opts()))],
    ['POST', /^bookings\/([\w-]+)\/review$/, ([, id]) => mutate(() => addReview(db, id, body.by, body.rating, body.text, opts()))],
    ['GET', /^threads$/, () => threadsFor(db, params.get('userId'))],
    ['GET', /^host\/summary$/, () => hostSummary(db, params.get('hostId'), now())],
    ['GET', /^saves$/, () => {
      const userId = params.get('userId');
      return ['consumer', 'business'].flatMap((audience) => search(db, { userId, audience }).spaces).filter((x) => x.saved);
    }],
    ['POST', /^saves$/, () => mutate(() => toggleSave(db, body.userId, body.spaceId))],
    // Owner tools
    ['GET', /^spaces\/([\w-]+)\/manage$/, ([, id]) => ownerView(db, id, params.get('userId'))],
    ['POST', /^spaces\/([\w-]+)\/update$/, ([, id]) => mutate(() => updateSpace(db, id, body.actorId, body.changes ?? {}, opts()))],
    ['GET', /^market$/, () => marketFor(db, params.get('category'), params.get('exclude'))],
    // Pricing transparency
    ['GET', /^pricing$/, () => ({ serviceFee: SERVICE_FEE, hostFee: HOST_FEE, beatPct: BEAT_PCT, claimWindowHours: CLAIM_WINDOW_HOURS, platforms: PLATFORMS })],
    ['POST', /^bookings\/([\w-]+)\/price-match$/, ([, id]) => mutate(() => {
      const b = db.bookings.find((x) => x.id === id);
      if (!b) throw new BookingError('Booking not found');
      const space = db.spaces.find((s) => s.id === b.items[0].spaceId);
      const result = evaluateClaim(space, b, body, now());
      if (result.errors) throw new BookingError("We can't match that price", result.errors);
      b.priceMatch = result.claim;
      systemMessage(db, b.id, result.claim.status === 'approved'
        ? `Price match approved: ${result.claim.name} was cheaper, so Everyspace refunded $${result.claim.credit.toFixed(2)}${result.claim.perPeriod ? ` per ${b.quote.schedule.every}` : ''}. The owner's payout is unchanged.`
        : `Price-match claim received for a ${result.claim.name} listing. We'll confirm it within 24 hours.`, opts());
      return result.claim;
    })],
    ['POST', /^reset$/, () => { store.reset(); return { ok: true }; }],
  ];
  const route = routes.find(([m, re]) => m === method && re.test(path));
  if (!route) throw new NotFound('Not found');
  return route[2](path.match(route[1]));
}

// Errors the user caused (bad input, rule broken) rather than bugs.
export function isUserError(err) {
  return err instanceof BookingError || err instanceof SyntaxError ||
    /required|not found|must|can't|Unknown|Invalid|Set at least|need|Confirm before/i.test(err.message);
}

function listProperties(db, hostId) {
  return db.properties.filter((p) => !hostId || p.hostId === hostId).map((p) => ({
    ...p,
    spaces: db.spaces.filter((s) => s.propertyId === p.id).map((s) => ({ ...s, addonNote: describeAddon(db, s), rating: ratingFor(db, s.id) })),
    packages: db.packages.filter((k) => k.propertyId === p.id),
  }));
}

function toggleSave(db, userId, spaceId) {
  if (!db.users.some((u) => u.id === userId)) throw new BookingError('Unknown user');
  if (!db.spaces.some((s) => s.id === spaceId)) throw new BookingError('Space not found');
  db.saves ??= [];
  const i = db.saves.findIndex((x) => x.userId === userId && x.spaceId === spaceId);
  if (i >= 0) db.saves.splice(i, 1); else db.saves.push({ userId, spaceId });
  return { saved: i < 0 };
}

function spaceDetail(db, id, userId) {
  const s = db.spaces.find((x) => x.id === id);
  if (!s) throw new BookingError('Space not found');
  const property = db.properties.find((p) => p.id === s.propertyId);
  const { access, ...publicFields } = s; // access details are only shown after booking
  const userName = (uid) => db.users.find((u) => u.id === uid);
  return {
    ...publicFields,
    categoryInfo: CATEGORIES[s.category],
    property,
    host: userName(property.hostId),
    parent: s.parentId ? db.spaces.find((x) => x.id === s.parentId)?.title : null,
    addonNote: describeAddon(db, s),
    rating: ratingFor(db, s.id),
    saved: !!userId && (db.saves ?? []).some((x) => x.userId === userId && x.spaceId === id),
    // Same space on other sites, one unit of each length, all-in on both sides.
    comparisons: CATEGORIES[s.category].terms.map((t) => unitComparison(s, t)).filter(Boolean),
    pricing: { serviceFee: SERVICE_FEE, hostFee: HOST_FEE, beatPct: BEAT_PCT },
    reviews: db.reviews.filter((r) => r.spaceId === id).sort((a, b) => (a.at < b.at ? 1 : -1))
      .map((r) => ({ ...r, author: userName(r.by) })),
    // Add-ons this space can carry (e.g. parking/lockers for an apartment)
    addons: db.spaces.filter((a) => a.policy && a.policy !== 'standalone' && isAnchorFor(a, s))
      .map(({ access: _a, ...a }) => ({ ...a, addonNote: describeAddon(db, a) })),
    packages: db.packages.filter((p) => p.items.some((i) => i.spaceId === id)),
    // Other spaces at the same place (for "More at this address")
    nearby: db.spaces.filter((x) => x.propertyId === s.propertyId && x.id !== id && x.rentable !== false && (x.policy ?? 'standalone') !== 'addon')
      .map((x) => ({ id: x.id, title: x.title, category: x.category, rates: x.rates })),
  };
}

function listBookings(db, userId, now) {
  const space = (id) => db.spaces.find((s) => s.id === id);
  const user = (id) => db.users.find((u) => u.id === id);
  return db.bookings
    .filter((b) => !userId || b.renterId === userId || b.hostId === userId)
    .map((b) => {
      const first = space(b.items[0].spaceId);
      const prop = db.properties.find((p) => p.id === first?.propertyId);
      const party = userId === b.renterId || userId === b.hostId;
      return {
        ...b,
        role: b.hostId === userId ? 'host' : 'renter',
        effective: effectiveStatus(b, now),
        renterName: user(b.renterId)?.name, hostName: user(b.hostId)?.name,
        renter: user(b.renterId), host: user(b.hostId),
        primary: { id: first?.id, title: first?.title, category: first?.category },
        property: prop && { title: prop.title, city: prop.city },
        itemsLabel: b.items.map((i) => `${i.qty > 1 ? `${i.qty}× ` : ''}${space(i.spaceId)?.title}`).join(' + '),
        packageName: db.packages.find((p) => p.id === b.packageId)?.name ?? null,
        access: party && SHOW_ACCESS.has(effectiveStatus(b, now))
          ? b.items.map((i) => ({ title: space(i.spaceId)?.title, text: space(i.spaceId)?.access ?? 'The host will message you access details.' }))
          : null,
        canReview: canReview(db, b, userId, now),
        reviewed: db.reviews.some((r) => r.bookingId === b.id),
      };
    })
    .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
}
