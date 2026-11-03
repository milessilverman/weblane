// Carts, add-on/package rules, quotes, and booking state. See SPEC.md §2–3.
import { category, CATEGORIES, MODES, TERMS } from './catalog.js';
import { checkAvailability, HOLDING } from './availability.js';
import { priceLine, totals } from './pricing.js';
import { duration, toMs } from './time.js';
import { withArticle } from './describe.js';

export class BookingError extends Error {
  constructor(message, details = []) { super(message); this.details = details; }
}

const spaceById = (db, id) => db.spaces.find((s) => s.id === id);

// Does `anchor` qualify to carry add-on space `addon`?
export function isAnchorFor(addon, anchor) {
  const rule = addon.addon;
  if (!rule || anchor.id === addon.id) return false;
  if (rule.anchorIds?.includes(anchor.id)) return true;
  return !!rule.anchorCategories?.includes(anchor.category) && anchor.propertyId === addon.propertyId;
}

// Expand a package into items, or return the cart's items.
function resolveItems(db, cart) {
  if (!cart.packageId) return { items: cart.items || [], pkg: null };
  const pkg = db.packages.find((p) => p.id === cart.packageId);
  if (!pkg) throw new BookingError('Package not found');
  return { items: pkg.items.map((i) => ({ ...i })), pkg };
}

export function modeFor(space, term) {
  let mode = space.mode ?? category(space.category).mode;
  if (term === 'lease' && mode === 'instant') mode = 'request';
  if (term === 'infrastructure') mode = 'proposal';
  return mode;
}

// Validates the cart and returns priced lines. Throws BookingError listing every problem.
export function evaluateCart(db, cart) {
  const { term, start, end, renterId } = cart;
  if (!TERMS[term]) throw new BookingError(`Unknown term: ${term}`);
  if (toMs(end) <= toMs(start)) throw new BookingError('End must be after start');
  const { items, pkg } = resolveItems(db, cart);
  if (!items.length) throw new BookingError('Choose at least one space');

  const errors = [];
  const spaces = items.map((i) => spaceById(db, i.spaceId));
  if (spaces.some((s) => !s)) throw new BookingError('Space not found');

  // 1. Term allowed and priced.
  for (const s of spaces) {
    const cat = category(s.category);
    if (s.rentable === false) errors.push(`${s.title} is not rentable on its own`);
    else if (!cat.terms.includes(term)) errors.push(`${s.title} can't be rented ${TERMS[term].label.toLowerCase()} (allowed: ${cat.terms.map((t) => TERMS[t].label).join(', ') || 'none'})`);
    else if (s.rates?.[term] == null && s.addonRates?.[term] == null) errors.push(`${s.title} has no ${TERMS[term].label.toLowerCase()} price`);
  }

  // 1b. Infrastructure and commercial sites are leased to businesses only.
  const renter = db.users.find((u) => u.id === renterId);
  if (spaces.some((s) => category(s.category).audience === 'business') && renter?.kind !== 'business') {
    errors.push('Only verified business accounts can lease infrastructure and commercial sites');
  }

  // 2. Length limits.
  const d = duration(term, start, end);
  if (term === 'lease' && (d.months < TERMS.lease.min || d.months > TERMS.lease.max)) {
    errors.push(`A fixed lease runs ${TERMS.lease.min}–${TERMS.lease.max} months`);
  }
  if (term === 'infrastructure') {
    for (const s of spaces) {
      const min = Math.max(TERMS.infrastructure.min, category(s.category).minYears ?? 0);
      if (d.years < min || d.years > TERMS.infrastructure.max) errors.push(`${s.title} agreements run ${min}–${TERMS.infrastructure.max} years`);
    }
  }
  for (const s of spaces) {
    const min = s.minDuration?.[term];
    if (min == null) continue;
    const [k] = Object.keys(d).filter((x) => x !== 'extraDays');
    if (d[k] < min) errors.push(`${s.title} needs at least ${min} ${TERMS[term].unit}${min === 1 ? '' : 's'}`);
  }

  // 3. Add-on rules: anchors in this cart, or the renter's existing bookings covering the whole interval.
  const existing = db.bookings.filter((b) => b.renterId === renterId && HOLDING.has(b.status) && b.id !== cart.excludeBookingId);
  const addonInfo = new Map();
  for (const [idx, s] of spaces.entries()) {
    if (!s.addon || s.policy === 'standalone') continue;
    let anchors = 0;
    items.forEach((it, j) => { if (j !== idx && isAnchorFor(s, spaces[j])) anchors += it.qty; });
    for (const b of existing) {
      if (toMs(b.start) > toMs(start) || toMs(b.end) < toMs(end)) continue;
      for (const it of b.items) { const a = spaceById(db, it.spaceId); if (a && isAnchorFor(s, a)) anchors += it.qty; }
    }
    const wanted = items[idx].qty;
    const alreadyHeld = existing
      .filter((b) => toMs(b.start) < toMs(end) && toMs(start) < toMs(b.end))
      .flatMap((b) => b.items).filter((it) => it.spaceId === s.id).reduce((n, it) => n + it.qty, 0);
    const limit = (s.addon.maxPerAnchor ?? Infinity) * anchors;
    const anchorNames = describeAnchors(db, s);

    if (s.policy === 'addon') {
      if (anchors === 0) errors.push(`${s.title} is only available with ${anchorNames}`);
      else if (wanted + alreadyHeld > limit) errors.push(`${s.title}: max ${s.addon.maxPerAnchor} per ${anchorNames.replace(/^an? /, '').replace(/ here$/, '')} (you'd have ${wanted + alreadyHeld})`);
    }
    addonInfo.set(idx, anchors > 0 && wanted + alreadyHeld <= limit);
  }

  if (errors.length) throw new BookingError('This booking breaks a rule', errors);

  const lines = items.map((it, idx) => priceLine(spaces[idx], it.qty, term, start, end, { asAddon: addonInfo.get(idx) ?? false }));
  const mode = MODES[Math.max(...spaces.map((s) => MODES.indexOf(modeFor(s, term))))];
  return { items, spaces, pkg, lines, mode };
}

function describeAnchors(db, addon) {
  const parts = [];
  for (const c of addon.addon.anchorCategories || []) parts.push(`${withArticle(CATEGORIES[c].label)} here`);
  for (const id of addon.addon.anchorIds || []) parts.push(spaceById(db, id)?.title ?? id);
  return parts.join(' or ') || 'another rental';
}

export function quote(db, cart) {
  const ev = evaluateCart(db, cart);
  const availability = checkAvailability(db, ev.items, cart.start, cart.end, { excludeBookingId: cart.excludeBookingId });
  return { mode: ev.mode, package: ev.pkg?.name ?? null, availability, ...totals(ev.lines, cart.term, cart.start, cart.end, ev.pkg) };
}

const INITIAL = { instant: 'confirmed', request: 'pending', proposal: 'proposed' };

export function createBooking(db, cart, { now = new Date().toISOString(), newId } = {}) {
  if (!db.users.some((u) => u.id === cart.renterId)) throw new BookingError('Unknown renter');
  const q = quote(db, cart);
  if (!q.availability.ok) throw new BookingError('Not available', q.availability.conflicts.map((c) => c.reason));
  const { items } = resolveItems(db, cart);
  const hostIds = new Set(items.map((i) => hostOf(db, i.spaceId)));
  if (hostIds.has(cart.renterId)) throw new BookingError("You can't book your own space");
  if (hostIds.size > 1) throw new BookingError('Book spaces from different hosts separately');
  const booking = {
    id: newId ? newId('bk') : `bk_${Date.now()}`,
    renterId: cart.renterId,
    hostId: [...hostIds][0],
    packageId: cart.packageId ?? null,
    items,
    term: cart.term,
    start: cart.start,
    end: cart.end,
    mode: q.mode,
    status: INITIAL[q.mode],
    quote: { total: q.total, rent: q.rent, serviceFee: q.serviceFee, hostPayout: q.hostPayout, packageDiscount: q.packageDiscount, deposit: q.deposit, schedule: q.schedule, lines: q.lines },
    note: cart.note ?? '',
    history: [{ at: now, status: INITIAL[q.mode], by: cart.renterId }],
    createdAt: now,
  };
  db.bookings.push(booking);
  return booking;
}

export function hostOf(db, spaceId) {
  const s = spaceById(db, spaceId);
  return db.properties.find((p) => p.id === s?.propertyId)?.hostId;
}

// action -> { from: [...], to, who: 'host' | 'renter' | 'either' }
const TRANSITIONS = {
  approve: { from: ['pending'], to: 'confirmed', who: 'host' },
  decline: { from: ['pending', 'proposed', 'site_assessment', 'contract'], to: 'declined', who: 'host' },
  advance: { from: ['proposed', 'site_assessment', 'contract'], who: 'host' },
  cancel: { from: ['pending', 'proposed', 'site_assessment', 'contract', 'confirmed', 'active'], to: 'cancelled', who: 'either' },
};
const PROPOSAL_NEXT = { proposed: 'site_assessment', site_assessment: 'contract', contract: 'confirmed' };

export function transition(db, bookingId, action, actorId, { now = new Date().toISOString() } = {}) {
  const b = db.bookings.find((x) => x.id === bookingId);
  if (!b) throw new BookingError('Booking not found');
  const t = TRANSITIONS[action];
  if (!t) throw new BookingError(`Unknown action: ${action}`);
  const allowed = t.who === 'host' ? [b.hostId] : [b.hostId, b.renterId];
  if (!allowed.includes(actorId)) throw new BookingError(`Only the ${t.who === 'host' ? 'host' : 'host or renter'} can ${action} this booking`);
  if (!t.from.includes(b.status)) throw new BookingError(`Can't ${action} a ${b.status} booking`);
  b.status = action === 'advance' ? PROPOSAL_NEXT[b.status] : t.to;
  b.history.push({ at: now, status: b.status, by: actorId });
  return b;
}
