// Price transparency: compare a space with the same space listed on other sites, and the price-beat guarantee.
//
// Where comparison data comes from (no scraping; most sites forbid it in their terms):
//   1. Owners link their own listings elsewhere ("cross-listings") with the price they charge there.
//      We re-verify those links on a schedule (in production: a person or an approved data feed).
//   2. Renters can submit a cheaper listing for the same space after booking (a price-match claim).
//
// Other sites add their own renter fees on top of the owner's price. PLATFORMS holds our best
// estimate of each site's fee so totals compare like for like. These are ASSUMPTIONS to verify
// before launch (see RESEARCH.md) and the UI always labels comparisons as estimates.
import { priceRates, SERVICE_FEE, HOST_FEE } from './pricing.js';

// The price beat comes out of Everyspace's own cut (service fee + owner fee), never the owner's payout.
// The owner earns the same here as anywhere else; we shrink our margin to be the cheapest. We'll cut
// our margin all the way to zero if needed, but never below it, so the beat is capped at our cut.
export const BEAT_PCT = 0.05; // we beat a cheaper verified total by 5% of their price (up to our whole cut)
export const CLAIM_WINDOW_HOURS = 48; // claims allowed within 48h of booking, or any time before start

// guestFeePct: what the site adds on top for renters. hostFeePct: what it keeps from the owner.
// All are estimates until verified (RESEARCH.md §1.1); verified:false keeps the "estimate" label on.
export const PLATFORMS = {
  airbnb: { name: 'Airbnb', domain: 'airbnb.com', guestFeePct: 0.142, hostFeePct: 0.03, perBookingFee: 0, verified: false },
  vrbo: { name: 'Vrbo', domain: 'vrbo.com', guestFeePct: 0.12, hostFeePct: 0.08, perBookingFee: 0, verified: false },
  furnished_finder: { name: 'Furnished Finder', domain: 'furnishedfinder.com', guestFeePct: 0, hostFeePct: 0, perBookingFee: 0, verified: false },
  neighbor: { name: 'Neighbor', domain: 'neighbor.com', guestFeePct: 0.10, hostFeePct: 0.049, perBookingFee: 0, verified: false },
  spothero: { name: 'SpotHero', domain: 'spothero.com', guestFeePct: 0, hostFeePct: 0.30, perBookingFee: 2.5, verified: false },
  swimply: { name: 'Swimply', domain: 'swimply.com', guestFeePct: 0.10, hostFeePct: 0.15, perBookingFee: 0, verified: false },
  peerspace: { name: 'Peerspace', domain: 'peerspace.com', guestFeePct: 0.15, hostFeePct: 0.15, perBookingFee: 0, verified: false },
  sniffspot: { name: 'Sniffspot', domain: 'sniffspot.com', guestFeePct: 0.10, hostFeePct: 0.20, perBookingFee: 0, verified: false },
  craigslist: { name: 'Craigslist', domain: 'craigslist.org', guestFeePct: 0, hostFeePct: 0, perBookingFee: 0, verified: true },
  facebook: { name: 'Facebook Marketplace', domain: 'facebook.com', guestFeePct: 0, hostFeePct: 0, perBookingFee: 0, verified: true },
};

// Our cut on a quote: per booking for short stays, per period for monthly/lease/infrastructure.
export function ourCut(quote, short) {
  if (short) return money((quote.serviceFee ?? 0) + (quote.hostFee ?? (quote.rent - quote.hostPayout)));
  const rentPerPeriod = quote.schedule.recurring / (1 + SERVICE_FEE);
  return money(rentPerPeriod * (SERVICE_FEE + HOST_FEE));
}

// Credit for a cheaper total: difference + 5% of theirs, but never more than our own cut.
export function beatCredit(ours, theirs, cut) {
  const wanted = money(ours - theirs + theirs * BEAT_PCT);
  const credit = Math.min(wanted, cut);
  return { credit: money(credit), wanted, capped: wanted > cut, beaten: ours - credit < theirs, matched: ours - credit <= theirs };
}

const SHORT = new Set(['hourly', 'daily', 'weekly']);
const money = (n) => Math.round(n * 100) / 100;

export function platformFor(url) {
  let host;
  try { host = new URL(url).hostname.replace(/^www\./, ''); } catch { return null; }
  return Object.entries(PLATFORMS).find(([, p]) => host === p.domain || host.endsWith(`.${p.domain}`))?.[0] ?? null;
}

// Validates and normalizes an owner's cross-listing.
export function normalizeExternal(input, allowedTerms) {
  const platform = platformFor(input.url);
  if (!platform) throw new Error(`Link must be a listing on ${Object.values(PLATFORMS).map((p) => p.name).join(', ')}`);
  if (input.platform && input.platform !== platform) throw new Error(`That link is not a ${PLATFORMS[input.platform]?.name ?? input.platform} listing`);
  const rates = {};
  for (const [t, v] of Object.entries(input.rates ?? {})) {
    if (v === '' || v == null) continue;
    if (!allowedTerms.includes(t)) throw new Error(`Unknown length for this space: ${t}`);
    if (!(Number(v) > 0)) throw new Error('Prices on other sites must be positive');
    rates[t] = Number(v);
  }
  if (!Object.keys(rates).length) throw new Error('Enter the price you charge on that site');
  const cleaning = Number(input.cleaningFee ?? 0);
  if (cleaning < 0) throw new Error('Fees must be positive');
  return { platform, url: input.url, rates, cleaningFee: cleaning, verifiedAt: input.verifiedAt ?? null, demo: !!input.demo };
}

// What a renter would pay on the other site for the same booking (estimate), or null if that term isn't offered there.
export function externalTotal(ext, term, start, end, qty = 1) {
  const p = PLATFORMS[ext.platform];
  if (!p || ext.rates?.[term] == null) return null;
  const { amount, rate } = priceRates({ rates: ext.rates }, term, start, end);
  const recurring = !SHORT.has(term);
  const base = recurring ? rate * qty : amount * qty + (ext.cleaningFee ?? 0);
  const total = base * (1 + p.guestFeePct) + p.perBookingFee;
  return { platform: ext.platform, name: p.name, url: ext.url, verifiedAt: ext.verifiedAt, demo: ext.demo, feePct: p.guestFeePct,
    feeVerified: p.verified, recurring, comparable: money(total), cleaningFee: recurring ? 0 : ext.cleaningFee ?? 0 };
}

// Compare a single-space quote with that space's cross-listings and apply the price beat if anything is cheaper.
// Mutates and returns the quote. The beat comes out of our cut; the owner's payout never changes.
export function applyComparison(space, quote, cart) {
  const short = SHORT.has(cart.term);
  quote.ourCut ??= ourCut(quote, short);
  quote.ourCutBasis = short ? 'booking' : quote.schedule.every;
  if (!space?.externalListings?.length) return quote;
  const ours = short ? quote.total : quote.schedule.recurring;
  if (ours == null) return quote;
  const qty = cart.items?.[0]?.qty ?? 1;
  const rows = space.externalListings.map((e) => externalTotal(e, cart.term, cart.start, cart.end, qty)).filter(Boolean)
    .map((r) => ({ ...r, difference: money(r.comparable - ours) }));
  if (!rows.length) return quote;
  rows.sort((a, b) => a.comparable - b.comparable);
  quote.comparison = { ours: money(ours), basis: SHORT.has(cart.term) ? 'total' : `per ${quote.schedule.every}`, rows };
  const cheapest = rows[0];
  if (cheapest.comparable < ours) {
    const cut = quote.ourCut;
    const b = beatCredit(ours, cheapest.comparable, cut);
    const credit = b.credit;
    quote.priceBeat = { platform: cheapest.platform, name: cheapest.name, theirs: cheapest.comparable, credit, paidBy: 'everyspace',
      capped: b.capped, beaten: b.beaten, matched: b.matched, cutBefore: cut, cutAfter: money(cut - credit) };
    quote.ourCut = money(cut - credit);
    if (short) {
      quote.total = money(quote.total - credit);
      quote.schedule.dueNow = money(quote.schedule.dueNow - credit);
    } else {
      const periods = quote.total / quote.schedule.recurring;
      quote.total = money(quote.total - credit * periods);
      quote.schedule.recurring = money(quote.schedule.recurring - credit);
      quote.schedule.dueNow = money(quote.schedule.dueNow - (cart.term === 'infrastructure' ? 0 : credit));
    }
  }
  return quote;
}

// Per-unit, all-in comparison for cards and listing pages: our price for one unit of a term vs. theirs.
export function unitComparison(space, term) {
  const ours = space.rates?.[term];
  if (ours == null || !space.externalListings?.length) return null;
  const oursAllIn = ours * (1 + SERVICE_FEE);
  const rows = space.externalListings
    .filter((e) => e.rates?.[term] != null && PLATFORMS[e.platform])
    .map((e) => {
      const p = PLATFORMS[e.platform];
      // One unit (1 hour / 1 night / 1 week / 1 month), including their cleaning and booking fees for short stays.
      const theirs = SHORT.has(term)
        ? (e.rates[term] + (e.cleaningFee ?? 0)) * (1 + p.guestFeePct) + p.perBookingFee
        : e.rates[term] * (1 + p.guestFeePct);
      return { platform: e.platform, name: p.name, theirs: money(theirs), url: e.url, verifiedAt: e.verifiedAt, demo: e.demo,
        cleaningFee: SHORT.has(term) ? e.cleaningFee ?? 0 : 0, feePct: p.guestFeePct };
    })
    .sort((a, b) => a.theirs - b.theirs);
  if (!rows.length) return null;
  return { term, ours: money(oursAllIn), rows, cheaperHere: rows.every((r) => oursAllIn <= r.theirs) };
}

// A renter found the same space cheaper after booking.
export function evaluateClaim(space, booking, claim, now) {
  const errors = [];
  if (booking.renterId !== claim.userId) errors.push('Only the renter can claim a price match');
  if (['cancelled', 'declined'].includes(booking.status)) errors.push('This booking is not active');
  if (booking.priceMatch) errors.push('This booking already has a price-match claim');
  const age = (Date.parse(now) - Date.parse(booking.createdAt)) / 3600e3;
  const started = Date.parse(now) >= Date.parse(booking.start);
  if (started && age > CLAIM_WINDOW_HOURS) errors.push(`Claims must be made within ${CLAIM_WINDOW_HOURS} hours of booking or before it starts`);
  const platform = platformFor(claim.url ?? '');
  if (!platform) errors.push(`Link a listing on ${Object.values(PLATFORMS).map((p) => p.name).join(', ')}`);
  const theirs = Number(claim.theirTotal);
  if (!(theirs > 0)) errors.push('Enter the total price shown on that site, including its fees');
  const short = SHORT.has(booking.term);
  const ours = short ? booking.quote.total : booking.quote.schedule?.recurring;
  if (theirs > 0 && theirs >= ours) errors.push(`That price isn't lower than what you're paying here (${ours})`);
  if (errors.length) return { errors };
  // Instant approval only when the link is the owner's own cross-listing AND the claimed total matches
  // what that listing costs for these dates (within 3%). Anything else is checked by a person.
  const known = (space.externalListings ?? []).find((e) => e.url === claim.url);
  const qty = booking.items[0]?.qty ?? 1;
  const onFile = known && externalTotal(known, booking.term, booking.start, booking.end, qty);
  const matches = onFile && theirs >= onFile.comparable * 0.97;
  // Whatever is left of our cut on this booking (after any beat at checkout) is the most we can give back.
  const cut = booking.quote.ourCut ?? ourCut(booking.quote, short);
  const b = beatCredit(ours, theirs, cut);
  const credit = b.credit;
  const capNote = b.capped ? ` That's our entire cut on this booking; ${PLATFORMS[platform].name}'s price is below what the owner takes home here.` : '';
  return {
    claim: {
      platform, name: PLATFORMS[platform].name, url: claim.url, theirs, ours, credit, at: now, capped: b.capped, beaten: b.beaten,
      perPeriod: !short, status: matches ? 'approved' : 'in_review',
      note: matches
        ? `Matched to the owner's linked listing. Refund issued, paid from Everyspace's cut.${capNote}`
        : known
          ? `That's lower than the ${PLATFORMS[platform].name} price we have on file (~${onFile ? onFile.comparable : '?'}). We'll check the listing and confirm within 24 hours.`
          : 'We\'re checking it\'s the same space, dates and all-in total. Usually within 24 hours.',
    },
  };
}
