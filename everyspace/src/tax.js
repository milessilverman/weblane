// Taxes in the all-in price (RESEARCH_RESULTS.md §4). Only rules the research verified are encoded; everything
// else is reported as "not determined", never as 0%. Needs CPA / tax-counsel sign-off before real bookings.
import { addMonths, toMs } from './time.js';

const money = (n) => Math.round(n * 100) / 100;
const LODGING = new Set(['entire_home', 'apartment_unit', 'adu', 'private_room']);

// By city. `lodging` applies to LODGING categories on stays shorter than the exemption length.
export const TAX_RULES = {
  'San Diego': {
    lodging: {
      rate: 0.1175, name: 'San Diego transient occupancy tax',
      note: 'San Diego TOT is 11.75%, 12.75% or 13.75% depending on the zone (effective May 1, 2025). The lowest zone is used until address lookup is built. Stays of one calendar month or more are exempt.',
      exemptMonths: 1, source: 'https://www.sandiego.gov/treasurer/taxesfees/tot',
    },
  },
  Phoenix: {
    lodging: { rate: 0.1307, name: 'Phoenix transient lodging tax (city + state + county)', note: 'Combined 13.07% (Jan 1, 2026 chart) on stays of 29 days or less.', exemptDays: 30,
      source: 'https://www.phoenix.gov/content/dam/phoenix/financesite/documents/Combined-Tax-Rate-Chart-0126.pdf' },
  },
  Indianapolis: {
    lodging: { rate: 0.17, name: 'Marion County innkeeper\'s tax + Indiana sales tax', note: '10% county innkeeper\'s tax plus 7% state sales tax (17% calculated) on stays under 30 days.', exemptDays: 30,
      source: 'https://www.in.gov/dor/resources/tax-rates-and-reports/rates-fees-and-penalties/county-innkeepers-tax/' },
  },
};

function exempt(rule, start, end) {
  if (rule.exemptMonths) return addMonths(toMs(start), rule.exemptMonths) <= toMs(end);
  if (rule.exemptDays) return (toMs(end) - toMs(start)) / 864e5 >= rule.exemptDays;
  return false;
}

// Adds tax to a quote. lines: the quote's lines, spaces: matching space objects, city: the property's city.
// Tax base is the rent on lodging lines (whether platform fees are taxable is an open question for a CPA).
export function applyTax(quote, spaces, city, cart) {
  const rule = TAX_RULES[city]?.lodging;
  quote.preTax = quote.total;
  let base = 0, lodging = false, other = false;
  quote.lines.forEach((l, i) => {
    const cat = spaces[i]?.category;
    if (LODGING.has(cat)) { lodging = true; base += l.amount; } else other = true;
  });
  const out = { amount: 0, items: [], undetermined: [] };
  if (lodging && rule) {
    if (exempt(rule, cart.start, cart.end)) out.items.push({ name: rule.name, amount: 0, note: 'Exempt: stay of one month or more.', source: rule.source });
    else {
      // Platform-funded price beats don't lower the taxable rent in this estimate.
      const amt = money(base * rule.rate);
      out.amount += amt;
      out.items.push({ name: rule.name, rate: rule.rate, amount: amt, note: rule.note, source: rule.source });
    }
  } else if (lodging) out.undetermined.push(`Lodging tax for ${city || 'this city'} isn't set up yet.`);
  if (other) out.undetermined.push('Taxes on parking, storage, events and other spaces aren\'t determined yet (pending tax review).');
  quote.tax = out;
  if (out.amount) {
    quote.total = money(quote.total + out.amount);
    if (!quote.schedule.recurring) quote.schedule.dueNow = money(quote.schedule.dueNow + out.amount);
  }
  return quote;
}
