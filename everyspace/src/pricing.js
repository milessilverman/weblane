// Pricing for one space, a cart of spaces, or a package. See SPEC.md §2 "Pricing".
import { category, TERMS } from './catalog.js';
import { duration, eachDay, toMs, HOUR } from './time.js';

export const SERVICE_FEE = 0.10; // charged to the renter
export const HOST_FEE = 0.03; // taken from the host payout

const money = (n) => Math.round(n * 100) / 100;

function eventRateOn(space, day, term) {
  const ev = (space.eventRates || []).find((e) => day >= e.start && day <= e.end && e[term] != null);
  return ev ? { rate: ev[term], name: ev.name } : null;
}

// Price `qty` units of something with `rates` (and optional eventRates) for a term + interval.
export function priceRates(rated, term, start, end, rateOverride) {
  const rate = rateOverride ?? rated.rates?.[term];
  if (rate == null) throw new Error(`No ${TERMS[term]?.label ?? term} rate for ${rated.title ?? rated.id}`);
  const d = duration(term, start, end);
  const events = new Set();
  let amount = 0;
  let detail;
  switch (term) {
    case 'hourly': {
      for (let t = toMs(start), i = 0; i < d.hours; i++, t += HOUR) {
        const ev = eventRateOn(rated, new Date(t).toISOString().slice(0, 10), 'hourly');
        if (ev) events.add(ev.name);
        amount += ev ? ev.rate : rate;
      }
      detail = `${d.hours} hr`;
      break;
    }
    case 'daily': {
      for (const day of eachDay(start, end)) {
        const ev = eventRateOn(rated, day, 'daily');
        if (ev) events.add(ev.name);
        amount += ev ? ev.rate : rate;
      }
      detail = `${d.days} day${d.days === 1 ? '' : 's'}`;
      break;
    }
    case 'weekly': {
      const dayRate = rated.rates?.daily ?? rate / 7;
      amount = d.weeks * rate + d.extraDays * dayRate;
      detail = `${d.weeks} wk${d.extraDays ? ` + ${d.extraDays} days` : ''}`;
      break;
    }
    case 'monthly':
    case 'lease':
      amount = d.months * rate + (d.extraDays * rate) / 30;
      detail = `${d.months} mo${d.extraDays ? ` + ${d.extraDays} days` : ''}`;
      break;
    case 'infrastructure':
      amount = d.years * rate;
      detail = `${d.years} yr`;
      break;
  }
  const periodic = ['monthly', 'lease', 'infrastructure'].includes(term)
    ? { every: TERMS[term].unit, amount: rate }
    : null;
  return { rate, amount, detail, periodic, events: [...events] };
}

// One line of a quote. `asAddon` uses the cheaper add-on rate when the space has one.
export function priceLine(space, qty, term, start, end, { asAddon = false } = {}) {
  const override = asAddon ? space.addonRates?.[term] : undefined;
  const p = priceRates(space, term, start, end, override);
  return {
    spaceId: space.id,
    title: space.title,
    qty,
    term,
    asAddon: asAddon && override != null,
    unitRate: p.rate,
    detail: p.detail,
    events: p.events,
    amount: money(p.amount * qty),
    periodic: p.periodic && { every: p.periodic.every, amount: money(p.periodic.amount * qty) },
    deposit: (category(space.category).deposit ?? 0) * qty,
  };
}

// Totals for a set of lines, with an optional package price applied.
export function totals(lines, term, start, end, pkg) {
  const subtotal = money(lines.reduce((s, l) => s + l.amount, 0));
  let periodicSum = lines.some((l) => l.periodic)
    ? money(lines.reduce((s, l) => s + (l.periodic?.amount ?? 0), 0))
    : null;

  let discount = 0;
  if (pkg?.pricing?.type === 'fixed') {
    const p = priceRates({ ...pkg, rates: pkg.pricing.rates }, term, start, end);
    discount = money(subtotal - p.amount);
    if (periodicSum != null) periodicSum = money(p.rate);
  } else if (pkg?.pricing?.type === 'percent') {
    discount = money((subtotal * pkg.pricing.percent) / 100);
    if (periodicSum != null) periodicSum = money(periodicSum * (1 - pkg.pricing.percent / 100));
  }

  const rent = money(subtotal - discount);
  const serviceFee = money(rent * SERVICE_FEE);
  const hostFee = money(rent * HOST_FEE);
  const deposit = lines.reduce((s, l) => s + l.deposit, 0);
  const unit = TERMS[term].unit;

  let schedule;
  if (term === 'infrastructure') {
    schedule = { dueNow: 0, recurring: money(periodicSum * (1 + SERVICE_FEE)), every: unit,
      note: 'Paid by the partner each year once the system is commissioned.' };
  } else if (periodicSum != null) {
    const first = money(periodicSum * (1 + SERVICE_FEE));
    schedule = { dueNow: money(first + deposit), recurring: first, every: unit,
      note: 'First period plus deposit now, then autopay each period.' };
  } else {
    schedule = { dueNow: money(rent + serviceFee), recurring: null, every: null,
      note: deposit ? `Deposit of $${deposit} held, not charged.` : 'Charged in full at booking.' };
  }

  return {
    lines,
    subtotal,
    packageDiscount: discount,
    rent,
    serviceFee,
    total: money(rent + serviceFee),
    hostFee,
    hostPayout: money(rent - hostFee),
    deposit,
    schedule,
  };
}
