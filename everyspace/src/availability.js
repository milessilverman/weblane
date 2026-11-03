// Can these spaces be booked for this interval? See SPEC.md §2 "Properties and spaces".
//  - quantity: a listing may hold N identical units; bookings consume units
//  - hierarchy: booking a parent blocks its children; booking a child blocks the parent
//  - conflictsWith: spaces that overlap without nesting (driveway vs. RV pad)
import { overlaps, toMs } from './time.js';

// States that hold a space (pending requests and proposals hold too, so no one double-books).
export const HOLDING = new Set(['pending', 'proposed', 'site_assessment', 'contract', 'confirmed', 'active']);

export function ancestors(db, spaceId) {
  const out = [];
  let s = db.spaces.find((x) => x.id === spaceId);
  while (s?.parentId) {
    s = db.spaces.find((x) => x.id === s.parentId);
    if (s) out.push(s.id);
  }
  return out;
}

export function descendants(db, spaceId) {
  const out = [];
  const stack = [spaceId];
  while (stack.length) {
    const id = stack.pop();
    for (const child of db.spaces.filter((x) => x.parentId === id)) {
      out.push(child.id);
      stack.push(child.id);
    }
  }
  return out;
}

// Booked units of `spaceId` per overlapping booking: [{start, end, qty}]
function usage(db, spaceId, start, end, excludeBookingId) {
  const uses = [];
  for (const b of db.bookings) {
    if (b.id === excludeBookingId || !HOLDING.has(b.status)) continue;
    if (!overlaps(b.start, b.end, start, end)) continue;
    for (const item of b.items) if (item.spaceId === spaceId) uses.push({ start: b.start, end: b.end, qty: item.qty, bookingId: b.id });
  }
  return uses;
}

// Highest number of units in use at any moment inside [start, end).
function peakUsage(uses, start, end) {
  const s = toMs(start), e = toMs(end);
  const events = [];
  for (const u of uses) {
    events.push([Math.max(toMs(u.start), s), u.qty]);
    events.push([Math.min(toMs(u.end), e), -u.qty]);
  }
  events.sort((a, b) => a[0] - b[0] || a[1] - b[1]); // ends before starts at the same instant
  let cur = 0, peak = 0;
  for (const [, d] of events) { cur += d; peak = Math.max(peak, cur); }
  return peak;
}

export function checkAvailability(db, items, start, end, { excludeBookingId } = {}) {
  const conflicts = [];
  const cartIds = items.map((i) => i.spaceId);
  const byId = (id) => db.spaces.find((x) => x.id === id);

  for (const item of items) {
    const space = byId(item.spaceId);
    if (!space) { conflicts.push({ spaceId: item.spaceId, reason: 'Space not found' }); continue; }
    if (space.rentable === false) { conflicts.push({ spaceId: space.id, reason: `${space.title} is not rentable on its own` }); continue; }

    for (const b of space.blackouts || []) {
      if (overlaps(b.start, b.end, start, end)) conflicts.push({ spaceId: space.id, reason: `${space.title} is blocked by the host (${b.reason || 'unavailable'})` });
    }

    const qty = items.filter((i) => i.spaceId === space.id).reduce((s, i) => s + i.qty, 0);
    const peak = peakUsage(usage(db, space.id, start, end, excludeBookingId), start, end);
    if (peak + qty > (space.quantity ?? 1)) {
      const left = Math.max(0, (space.quantity ?? 1) - peak);
      conflicts.push({ spaceId: space.id, reason: `Only ${left} of ${space.quantity ?? 1} ${space.title} available for those dates` });
    }

    for (const aId of ancestors(db, space.id)) {
      const a = byId(aId);
      if (cartIds.includes(aId)) conflicts.push({ spaceId: space.id, reason: `${space.title} is already part of ${a.title} in this booking` });
      else if (usage(db, aId, start, end, excludeBookingId).length) conflicts.push({ spaceId: space.id, reason: `${a.title} (which includes ${space.title}) is booked` });
    }

    for (const dId of descendants(db, space.id)) {
      if (usage(db, dId, start, end, excludeBookingId).length) {
        conflicts.push({ spaceId: space.id, reason: `Part of ${space.title} (${byId(dId).title}) is booked` });
        break;
      }
    }

    const linked = new Set([...(space.conflictsWith || []),
      ...db.spaces.filter((x) => x.conflictsWith?.includes(space.id)).map((x) => x.id)]);
    for (const cId of linked) {
      if (cartIds.includes(cId) || usage(db, cId, start, end, excludeBookingId).length) {
        conflicts.push({ spaceId: space.id, reason: `${space.title} shares room with ${byId(cId)?.title}, which is booked` });
      }
    }
  }

  return { ok: conflicts.length === 0, conflicts: dedupe(conflicts) };
}

// Units still free for the whole interval (for search results).
export function unitsFree(db, space, start, end) {
  if (space.rentable === false) return 0;
  const { ok } = checkAvailability(db, [{ spaceId: space.id, qty: 1 }], start, end);
  if (!ok) return 0;
  return (space.quantity ?? 1) - peakUsage(usage(db, space.id, start, end), start, end);
}

function dedupe(list) {
  const seen = new Set();
  return list.filter((c) => (seen.has(c.reason) ? false : seen.add(c.reason)));
}
