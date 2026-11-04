// Price transparency: compare a space with the same space listed on other sites, and the price-beat guarantee.
//
// Where comparison data comes from (no scraping; the major sites' terms forbid automated collection, see
// RESEARCH_RESULTS.md §2):
//   1. Owners enter their own price on other sites ("cross-listings"). We store it as an owner-submitted
//      quote with the date it was checked, and stop using it once it is older than STALE_DAYS.
//   2. Renters can submit a cheaper total for the same space after booking (a price-match claim).
//
// Other sites' renter fees come from PLATFORMS, researched 2026-11-04 (RESEARCH_RESULTS.md §1). A null fee means
// UNKNOWN (variable or unpublished), never zero: a listing on such a site can't be priced here, so it's shown
// as "fees not published" and never triggers an automatic beat or a "cheaper here" badge.
import { priceRates, SERVICE_FEE, HOST_FEE } from './pricing.js';

// The price beat comes out of Everyspace's own cut (service fee + owner fee), never the owner's payout.
// The owner earns the same here as anywhere else; we shrink our margin to be the cheapest, down to zero but
// never below. So the beat is capped at our cut on that booking, and the cap is stated wherever the promise is.
export const BEAT_PCT = 0.05; // beat a cheaper comparable total by 5% of their price, up to our whole cut
export const CLAIM_WINDOW_HOURS = 48; // claims allowed within 48h of booking, or any time before start
export const STALE_DAYS = 30; // owner-submitted quotes older than this are shown as "needs recheck" and not used
export const RESEARCHED = '2026-11-04';

// guestFeePct: what the site adds on top for renters. hostFeePct: what it keeps from the owner. null = unknown.
// perBookingFee: a renter's fixed fee per booking. hostFeeRange: published range when one rate isn't fixed.
// notice: what an owner should know before cross-listing (host terms), shown in Manage listing.
export const PLATFORMS = {
  airbnb: { name: 'Airbnb', domain: 'airbnb.com', guestFeePct: 0, hostFeePct: 0.155, perBookingFee: 0, verified: true,
    plan: 'US single-fee plan (host pays 15.5%, guest pays no service fee). Some listings still use split fees: guests ~14.1–16.5%, hosts 3%.',
    notice: "Airbnb's terms restrict steering Airbnb guests off Airbnb. Don't invite them to book you here instead." },
  vrbo: { name: 'Vrbo', domain: 'vrbo.com', guestFeePct: null, hostFeePct: 0.12, perBookingFee: null, verified: false,
    plan: 'Pay-per-booking: host 12% commission. Traveler service fee varies.',
    notice: "Vrbo can charge its commission on off-platform bookings of inquiries it introduced within 30 days." },
  furnished_finder: { name: 'Furnished Finder', domain: 'furnishedfinder.com', guestFeePct: 0, hostFeePct: 0, perBookingFee: 0, verified: true,
    plan: 'No booking fees; owners pay $199/year per listing.' },
  neighbor: { name: 'Neighbor', domain: 'neighbor.com', guestFeePct: null, hostFeePct: 0.049, perBookingFee: null, verified: false,
    plan: 'Host 4.9% plus $0.30 per monthly payout. Renter service fee varies.' },
  spothero: { name: 'SpotHero', domain: 'spothero.com', guestFeePct: null, hostFeePct: null, perBookingFee: null, verified: false,
    plan: 'Fees vary by operator; current rates not published.' },
  swimply: { name: 'Swimply', domain: 'swimply.com', guestFeePct: null, hostFeePct: null, hostFeeRange: [0.15, 0.25], perBookingFee: null, verified: false,
    plan: 'Host fee 15–25% (pools; up to 30% in some categories). Guest fee varies.' },
  peerspace: { name: 'Peerspace', domain: 'peerspace.com', guestFeePct: null, hostFeePct: 0.20, perBookingFee: null, verified: false,
    plan: 'Host 20% (on booking, cleaning and add-ons). Guest processing fee varies.',
    notice: "Peerspace's host agreement has a most-favored-customer clause: your Peerspace price must be as good as anywhere else. Check with Peerspace before offering a lower price here." },
  sniffspot: { name: 'Sniffspot', domain: 'sniffspot.com', guestFeePct: 0, hostFeePct: 0.22, perBookingFee: 0, verified: true,
    plan: 'Membership-credit bookings: no guest fee; host 22%.' },
  hipcamp: { name: 'Hipcamp', domain: 'hipcamp.com', guestFeePct: null, hostFeePct: 0.15, perBookingFee: null, verified: false,
    plan: 'Private landowners 15%. Guest fee varies ($3 minimum).' },
  giggster: { name: 'Giggster', domain: 'giggster.com', guestFeePct: null, hostFeePct: 0.19, perBookingFee: null, verified: false,
    plan: 'Host 19%. Guest processing fee varies.' },
  dockwa: { name: 'Dockwa', domain: 'dockwa.com', guestFeePct: 0, hostFeePct: 0.15, perBookingFee: 0, verified: true,
    plan: 'Dockwa Network: no boater fee; marina 15%.',
    notice: "Dockwa says marina partners agree not to charge more through Dockwa than by phone." },
  spacer: { name: 'Spacer', domain: 'spacer.com', guestFeePct: 1 / 3, hostFeePct: 0, perBookingFee: null, verified: true,
    plan: 'Renter pays the host price plus a third (Spacer keeps 25% of the renter total).' },
  liquidspace: { name: 'LiquidSpace', domain: 'liquidspace.com', guestFeePct: null, hostFeePct: 0.20, perBookingFee: null, verified: false,
    plan: 'Host 20% hourly (10% host-originated or monthly). Guest fee unknown.' },
  booking_com: { name: 'Booking.com', domain: 'booking.com', guestFeePct: null, hostFeePct: null, perBookingFee: null, verified: false,
    plan: 'Commission set per property contract.' },
  parkwhiz: { name: 'ParkWhiz', domain: 'parkwhiz.com', guestFeePct: null, hostFeePct: null, perBookingFee: null, verified: false,
    plan: 'Fees vary by operator.' },
  craigslist: { name: 'Craigslist', domain: 'craigslist.org', guestFeePct: 0, hostFeePct: 0, perBookingFee: 0, verified: true,
    plan: 'Classified ads, no booking fees ($5 posting fee in some categories).' },
  facebook: { name: 'Facebook Marketplace', domain: 'facebook.com', guestFeePct: null, hostFeePct: null, perBookingFee: null, verified: false,
    plan: 'Rental fee terms not publicly available.' },
};

const SHORT = new Set(['hourly', 'daily', 'weekly']);
const money = (n) => Math.round(n * 100) / 100;
// A site's renter total is computable when its % fee is known and, for short stays, its per-booking fee too.
const known = (p, recurring = false) => !!p && p.guestFeePct != null && (recurring || p.perBookingFee != null);
const ageDays = (iso, now) => (iso ? (Date.parse(now ?? Date.now()) - Date.parse(iso)) / 864e5 : Infinity);
export const isStale = (ext, now) => ageDays(ext.verifiedAt, now) > STALE_DAYS;

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

export function platformFor(url) {
  let host;
  try { host = new URL(url).hostname.replace(/^www\./, ''); } catch { return null; }
  return Object.entries(PLATFORMS).find(([, p]) => host === p.domain || host.endsWith(`.${p.domain}`))?.[0] ?? null;
}

// Validates and normalizes an owner's cross-listing (an owner-submitted quote, dated).
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
  return { platform, url: input.url, rates, cleaningFee: cleaning, verifiedAt: input.verifiedAt ?? null, source: 'owner', demo: !!input.demo };
}

// What a renter would pay on the other site for the same booking, before taxes. comparable is null when that
// site's renter fees are unknown (the row is still shown, labeled), or when the quote is stale.
export function externalTotal(ext, term, start, end, qty = 1, now) {
  const p = PLATFORMS[ext.platform];
  if (!p || ext.rates?.[term] == null) return null;
  const { amount, rate } = priceRates({ rates: ext.rates }, term, start, end);
  const recurring = !SHORT.has(term);
  const base = recurring ? rate * qty : amount * qty + (ext.cleaningFee ?? 0);
  const stale = isStale(ext, now);
  const total = known(p, recurring) ? base * (1 + p.guestFeePct) + (recurring ? 0 : p.perBookingFee ?? 0) : null;
  return { platform: ext.platform, name: p.name, url: ext.url, verifiedAt: ext.verifiedAt, demo: ext.demo, feePct: p.guestFeePct,
    feeVerified: p.verified, feesUnknown: !known(p, recurring), stale, ownerPrice: money(base), recurring,
    comparable: total == null || stale ? null : money(total), cleaningFee: recurring ? 0 : ext.cleaningFee ?? 0 };
}

// Compare a single-space quote with that space's cross-listings and apply the price beat if a comparable total is
// lower. Totals are compared before taxes (the same tax applies at the same address on any site).
// Mutates and returns the quote. The beat comes out of our cut; the owner's payout never changes.
export function applyComparison(space, quote, cart) {
  const short = SHORT.has(cart.term);
  quote.ourCut ??= ourCut(quote, short);
  quote.ourCutBasis = short ? 'booking' : quote.schedule.every;
  if (!space?.externalListings?.length) return quote;
  const ours = short ? quote.total : quote.schedule.recurring;
  if (ours == null) return quote;
  const qty = cart.items?.[0]?.qty ?? 1;
  const rows = space.externalListings.map((e) => externalTotal(e, cart.term, cart.start, cart.end, qty, cart.now)).filter(Boolean)
    .map((r) => ({ ...r, difference: r.comparable == null ? null : money(r.comparable - ours) }));
  if (!rows.length) return quote;
  rows.sort((a, b) => (a.comparable ?? Infinity) - (b.comparable ?? Infinity));
  quote.comparison = { ours: money(ours), basis: short ? 'total' : `per ${quote.schedule.every}`, rows, beforeTax: true };
  const cheapest = rows.find((r) => r.comparable != null);
  if (cheapest && cheapest.comparable < ours) {
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

// Per-unit comparison for cards and listing pages: our all-in price (before tax) for one unit vs. theirs.
// Rows with unknown fees or stale quotes are listed but don't count toward "cheaper here".
export function unitComparison(space, term, now) {
  const ours = space.rates?.[term];
  if (ours == null || !space.externalListings?.length) return null;
  const oursAllIn = ours * (1 + SERVICE_FEE);
  const rows = space.externalListings
    .filter((e) => e.rates?.[term] != null && PLATFORMS[e.platform])
    .map((e) => {
      const p = PLATFORMS[e.platform], stale = isStale(e, now);
      // One unit (1 hour / 1 night / 1 week / 1 month), including their cleaning and booking fees for short stays.
      const base = SHORT.has(term) ? e.rates[term] + (e.cleaningFee ?? 0) : e.rates[term];
      const theirs = known(p, !SHORT.has(term)) && !stale ? base * (1 + p.guestFeePct) + (SHORT.has(term) ? p.perBookingFee ?? 0 : 0) : null;
      return { platform: e.platform, name: p.name, theirs: theirs == null ? null : money(theirs), ownerPrice: money(base), url: e.url,
        verifiedAt: e.verifiedAt, demo: e.demo, stale, feesUnknown: !known(p, !SHORT.has(term)), cleaningFee: SHORT.has(term) ? e.cleaningFee ?? 0 : 0, feePct: p.guestFeePct };
    })
    .sort((a, b) => (a.theirs ?? Infinity) - (b.theirs ?? Infinity));
  if (!rows.length) return null;
  const priced = rows.filter((r) => r.theirs != null);
  return { term, ours: money(oursAllIn), rows, comparable: priced.length > 0, cheaperHere: priced.length > 0 && priced.every((r) => oursAllIn <= r.theirs) };
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
  const ours = short ? (booking.quote.preTax ?? booking.quote.total) : booking.quote.schedule?.recurring;
  if (theirs > 0 && theirs >= ours) errors.push(`That price isn't lower than what you're paying here before taxes (${ours})`);
  if (errors.length) return { errors };
  // Instant approval only when the link is the owner's own cross-listing, its quote is current, its site's fees
  // are known, AND the claimed total matches what that listing costs for these dates (within 3%).
  // Everything else is checked by a person.
  const ownListing = (space.externalListings ?? []).find((e) => e.url === claim.url);
  const qty = booking.items[0]?.qty ?? 1;
  const onFile = ownListing && externalTotal(ownListing, booking.term, booking.start, booking.end, qty, now);
  const matches = !!(onFile && onFile.comparable != null && theirs >= onFile.comparable * 0.97);
  // Whatever is left of our cut on this booking (after any beat at checkout) is the most we can give back.
  const cut = booking.quote.ourCut ?? ourCut(booking.quote, short);
  const b = beatCredit(ours, theirs, cut);
  const credit = b.credit;
  const capNote = b.capped ? ` That's all of Everyspace's fees on this booking, the most the guarantee covers; ${PLATFORMS[platform].name}'s price is below what the owner takes home here.` : '';
  return {
    claim: {
      platform, name: PLATFORMS[platform].name, url: claim.url, theirs, ours, credit, at: now, capped: b.capped, beaten: b.beaten,
      perPeriod: !short, status: matches ? 'approved' : 'in_review',
      note: matches
        ? `Matched to the owner's linked listing. Refund issued, paid from Everyspace's fees.${capNote}`
        : onFile && onFile.comparable != null
          ? `That's lower than the ${PLATFORMS[platform].name} price we have on file (~${onFile.comparable}). We'll check the listing and confirm within 24 hours.`
          : 'We\'re checking it\'s the same space, dates and all-in total. Usually within 24 hours.',
    },
  };
}
