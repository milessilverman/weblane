// Owner tools: edit prices, pause, block dates, manage cross-listings, and see what similar spaces charge.
import { BookingError } from './booking.js';
import { category, TYPICAL } from './catalog.js';
import { normalizeExternal, unitComparison } from './compare.js';
import { toMs } from './time.js';

function ownSpace(db, spaceId, actorId) {
  const s = db.spaces.find((x) => x.id === spaceId);
  if (!s) throw new BookingError('Space not found');
  const prop = db.properties.find((p) => p.id === s.propertyId);
  if (prop?.hostId !== actorId) throw new BookingError('Only the owner can change this listing');
  return s;
}

// Partial update. Only the fields present in `changes` are touched.
export function updateSpace(db, spaceId, actorId, changes, { now = new Date().toISOString() } = {}) {
  const s = ownSpace(db, spaceId, actorId);
  const cat = category(s.category);
  if (changes.title !== undefined) {
    if (!String(changes.title).trim()) throw new BookingError('Title is required');
    s.title = String(changes.title).trim().slice(0, 80);
  }
  if (changes.description !== undefined) s.description = String(changes.description).slice(0, 1000);
  if (changes.rates !== undefined) {
    const rates = {};
    for (const [t, v] of Object.entries(changes.rates)) {
      if (v === '' || v == null) continue;
      if (!cat.terms.includes(t)) throw new BookingError(`${cat.label} can't be rented ${t}`);
      if (!(Number(v) > 0)) throw new BookingError('Prices must be positive');
      rates[t] = Number(v);
    }
    if (!Object.keys(rates).length && !s.addonRates) throw new BookingError('Keep at least one price');
    s.rates = rates;
  }
  if (changes.paused !== undefined) s.paused = !!changes.paused;
  if (changes.blackouts !== undefined) {
    s.blackouts = changes.blackouts.map((b) => {
      if (!b.start || !b.end || toMs(b.end) <= toMs(b.start)) throw new BookingError('Blocked dates need a start before the end');
      return { start: b.start, end: b.end, reason: String(b.reason ?? 'Blocked by owner').slice(0, 80) };
    });
  }
  if (changes.externalListings !== undefined) {
    s.externalListings = changes.externalListings.map((e) => {
      try { return normalizeExternal({ ...e, verifiedAt: e.verifiedAt ?? now.slice(0, 10) }, cat.terms); } catch (err) { throw new BookingError(err.message); }
    });
  }
  s.updatedAt = now;
  return s;
}

// What similar spaces nearby charge, per term: { daily: { min, median, max, count, typical } }
export function marketFor(db, categoryKey, excludeId) {
  const out = {};
  const peers = db.spaces.filter((s) => s.category === categoryKey && s.id !== excludeId && s.rentable !== false && !s.paused);
  for (const t of category(categoryKey).terms) {
    const vals = peers.map((s) => s.rates?.[t]).filter((v) => v != null).sort((a, b) => a - b);
    const typical = TYPICAL[categoryKey]?.[t] ?? null;
    if (!vals.length && typical == null) continue;
    out[t] = vals.length
      ? { min: vals[0], median: vals[Math.floor(vals.length / 2)], max: vals.at(-1), count: vals.length, typical }
      : { min: null, median: typical, max: null, count: 0, typical };
  }
  return out;
}

// Owner view of a listing: everything they can change, plus how it compares.
export function ownerView(db, spaceId, actorId) {
  const s = ownSpace(db, spaceId, actorId);
  const cat = category(s.category);
  const upcoming = db.bookings.filter((b) => b.items.some((i) => i.spaceId === s.id) && ['pending', 'proposed', 'site_assessment', 'contract', 'confirmed', 'active'].includes(b.status));
  const parity = cat.terms.map((t) => unitComparison(s, t)).filter(Boolean)
    .filter((c) => !c.cheaperHere)
    .map((c) => ({ term: c.term, ours: c.ours, cheapest: c.rows[0] }));
  return { ...s, categoryInfo: cat, market: marketFor(db, s.category, s.id), upcomingCount: upcoming.length, parity };
}
