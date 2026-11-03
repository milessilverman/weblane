// Host dashboard numbers and the per-day availability calendar.
import { unitsFree } from './availability.js';
import { effectiveStatus } from './social.js';
import { addMonths, DAY, toMs } from './time.js';
import { SERVICE_FEE, HOST_FEE } from './pricing.js';

const EARNING = new Set(['confirmed', 'active', 'completed']);
const NEEDS_HOST = new Set(['pending', 'proposed', 'site_assessment', 'contract']);
const monthKey = (ms) => new Date(ms).toISOString().slice(0, 7);
const money = (n) => Math.round(n * 100) / 100;

// When the host gets paid for a booking: [{ month: 'YYYY-MM', amount }]
export function payoutSchedule(b) {
  const q = b.quote;
  if (!q) return [];
  const s = toMs(b.start), e = toMs(b.end);
  if (q.schedule?.recurring) {
    const perPeriod = (q.schedule.recurring / (1 + SERVICE_FEE)) * (1 - HOST_FEE);
    const step = b.term === 'infrastructure' ? 12 : 1;
    const out = [];
    for (let t = s; t < e; t = addMonths(t, step)) out.push({ month: monthKey(t), amount: money(perPeriod) });
    return out;
  }
  return [{ month: monthKey(s), amount: q.hostPayout ?? money(q.rent * (1 - HOST_FEE)) }];
}

export function hostSummary(db, hostId, now = Date.now()) {
  const nowMs = toMs(now);
  const mine = db.bookings.filter((b) => b.hostId === hostId);
  const label = (b) => db.packages.find((p) => p.id === b.packageId)?.name
    ?? b.items.map((i) => `${i.qty > 1 ? `${i.qty}× ` : ''}${db.spaces.find((s) => s.id === i.spaceId)?.title}`).join(' + ');
  const withNames = (b) => {
    const first = db.spaces.find((s) => s.id === b.items[0].spaceId);
    return { ...b, effective: effectiveStatus(b, nowMs), itemsLabel: label(b), primary: { id: first?.id, category: first?.category, title: first?.title },
      renterName: db.users.find((u) => u.id === b.renterId)?.name };
  };

  // Earnings by month, from 3 months ago to 8 months ahead.
  const months = [];
  for (let i = -3; i <= 8; i++) months.push(monthKey(addMonths(Date.UTC(new Date(nowMs).getUTCFullYear(), new Date(nowMs).getUTCMonth(), 1), i)));
  const byMonth = Object.fromEntries(months.map((m) => [m, 0]));
  const perSpace = {};
  let allTime = 0;
  for (const b of mine.filter((x) => EARNING.has(x.status))) {
    const schedule = payoutSchedule(b);
    const lineSum = b.quote.lines.reduce((s, l) => s + l.amount, 0) || 1;
    for (const p of schedule) {
      if (p.month in byMonth) byMonth[p.month] = money(byMonth[p.month] + p.amount);
      allTime += p.amount;
      for (const l of b.quote.lines) perSpace[l.spaceId] = money((perSpace[l.spaceId] ?? 0) + (p.amount * l.amount) / lineSum);
    }
  }
  const thisMonth = monthKey(nowMs);
  const next6 = months.filter((m) => m > thisMonth).slice(0, 6).reduce((s, m) => s + byMonth[m], 0);

  const spaces = db.spaces.filter((s) => db.properties.find((p) => p.id === s.propertyId)?.hostId === hostId && s.rentable !== false);
  return {
    needsAction: mine.filter((b) => NEEDS_HOST.has(b.status)).map(withNames).sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1)),
    upcoming: mine.filter((b) => b.status === 'confirmed' && toMs(b.start) > nowMs && toMs(b.start) - nowMs < 45 * DAY)
      .map(withNames).sort((a, b) => (a.start < b.start ? -1 : 1)),
    active: mine.filter((b) => effectiveStatus(b, nowMs) === 'active').map(withNames),
    earnings: {
      thisMonth: money(byMonth[thisMonth] ?? 0),
      next6: money(next6),
      allTime: money(allTime),
      byMonth: months.map((m) => ({ month: m, amount: byMonth[m] })),
      perSpace: Object.entries(perSpace).map(([spaceId, amount]) => ({ spaceId, title: db.spaces.find((s) => s.id === spaceId)?.title, amount }))
        .sort((a, b) => b.amount - a.amount),
    },
    listingCount: spaces.length,
    unitsListed: spaces.reduce((s, x) => s + (x.quantity ?? 1), 0),
  };
}

// Free units per day for `days` days starting at `from` (YYYY-MM-DD).
export function calendar(db, spaceId, from, days = 42) {
  const space = db.spaces.find((s) => s.id === spaceId);
  if (!space) throw new Error('Space not found');
  const out = [];
  for (let i = 0, t = toMs(from); i < Math.min(days, 400); i++, t += DAY) {
    const date = new Date(t).toISOString().slice(0, 10);
    out.push({ date, free: unitsFree(db, space, t, t + DAY), total: space.quantity ?? 1 });
  }
  return out;
}
