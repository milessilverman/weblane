// Time helpers. All times are UTC; intervals are half-open [start, end).

export const HOUR = 3_600_000;
export const DAY = 24 * HOUR;

export function toMs(value) {
  const ms = typeof value === 'number' ? value : Date.parse(value);
  if (Number.isNaN(ms)) throw new Error(`Invalid date: ${value}`);
  return ms;
}

export function overlaps(aStart, aEnd, bStart, bEnd) {
  return toMs(aStart) < toMs(bEnd) && toMs(bStart) < toMs(aEnd);
}

export function addMonths(ms, n) {
  const d = new Date(ms);
  const day = d.getUTCDate();
  const target = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + n, 1,
    d.getUTCHours(), d.getUTCMinutes()));
  const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(day, lastDay));
  return target.getTime();
}

// Whole months from start to end, plus leftover days.
export function monthsBetween(start, end) {
  const s = toMs(start), e = toMs(end);
  let months = 0;
  while (addMonths(s, months + 1) <= e) months++;
  const extraDays = Math.round((e - addMonths(s, months)) / DAY);
  return { months, extraDays };
}

// Each UTC calendar day (as YYYY-MM-DD) that a daily booking covers.
export function eachDay(start, end) {
  const days = [];
  for (let t = toMs(start); t < toMs(end); t += DAY) days.push(new Date(t).toISOString().slice(0, 10));
  return days;
}

// How long a booking is, in the units its term is priced in.
export function duration(term, start, end) {
  const s = toMs(start), e = toMs(end);
  if (e <= s) throw new Error('End must be after start');
  switch (term) {
    case 'hourly':
      return { hours: Math.ceil((e - s) / HOUR) };
    case 'daily':
      return { days: Math.ceil((e - s) / DAY) };
    case 'weekly': {
      const days = Math.ceil((e - s) / DAY);
      return { weeks: Math.floor(days / 7), extraDays: days % 7 };
    }
    case 'monthly':
    case 'lease':
      return monthsBetween(s, e);
    case 'infrastructure': {
      const { months } = monthsBetween(s, e);
      return { years: months / 12 };
    }
    default:
      throw new Error(`Unknown term: ${term}`);
  }
}
