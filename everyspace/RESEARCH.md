# Research to do before launch

These are the questions only you can answer, or that need a lawyer, an insurance broker, an accountant, or conversations with real owners and companies. They're in priority order. Each one says why it matters to the app and what to bring back so it can be built in.

Anything below marked *(verify)* is my current understanding and must be checked against the official source. Laws and competitor fees change often.

---

## 1. The price-beat guarantee (do first: it's the promise the brand is built on)

| # | Question | Why it matters | How to find out | Bring back |
|---|---|---|---|---|
| 1.1 | **What does each competitor actually charge renters and owners today?** Airbnb, Vrbo, Furnished Finder, Neighbor, SpotHero, Swimply, Peerspace, Sniffspot. | Comparisons add the other site's fees to the owner's price. The fee table in `src/compare.js` holds **placeholders** today, and the app labels them "estimate". If they're wrong, a comparison could be misleading. | Each site's help center or fee page, plus a test checkout to a real listing on each, screenshotting every fee line. Repeat quarterly. | The renter fee %, any per-booking fee, the owner fee %, and any cleaning or other fees for each site. |
| 1.2 | **Can we legally show competitor names and prices next to ours?** | Comparative advertising is generally allowed in the US when it's truthful and backed up *(verify: FTC comparative advertising policy; Lanham Act false-advertising risk)*. Using their trademarks and logos has limits. | A startup lawyer (1–2 hours). | Wording rules: whether we can name them or should say "another site", how we must label estimates, and how fresh the data must be. |
| 1.3 | **Can we collect their prices automatically?** | Most of these sites ban scraping in their terms. That's why the app uses only links owners add and links renters send. | Read each site's terms of service and robots rules; ask the lawyer. Check for official partner APIs or data feeds. | A yes or no per site. If no, we keep the current owner-link and renter-claim approach. |
| 1.4 | **Who pays for the beat, and is there a cap?** | Today Everyspace pays 100% of the difference plus 5%, uncapped, and owners' payouts never change. That's very owner-friendly but can get expensive. Example: an owner charges $45/hr here and $38/hr on Swimply, and we pay about $19.58 on every 2-hour booking. A fee-free classified site (Craigslist, Facebook) is always about 10% cheaper on paper than any site with a service fee. | Build a simple spreadsheet: expected bookings × share that's cross-listed × average gap. Decide on a policy. | A policy, for example: "beat by 5%, up to $X per booking"; or "match only, no extra"; or "booking sites only, not free classifieds". Also: whether owners should agree to keep their price here no higher than elsewhere (see 1.6). |
| 1.5 | **Guarantee terms and fraud.** | People will try to claim with fake or different listings. The app now auto-approves only when the link is the owner's own cross-listing *and* the price matches what we have on file. Everything else goes to review. | The lawyer for the terms; look at how other companies word their price-match guarantees. | Final wording: time window (now 48 h or before start), proof required (screenshot, total with fees), and exclusions (members-only prices, coupons, different dates or rooms). |
| 1.6 | **Do owners have rate-parity clauses with other sites?** | Some sites' host agreements limit advertising a lower price elsewhere *(verify; parity clauses were restricted in the EU for hotel sites)*. Owners need to know whether linking their other listing breaks another agreement. | Read the host terms of Airbnb, Vrbo, Neighbor, SpotHero and Swimply. | A short note we can show owners when they add a link. |

## 2. Being transparent the way the law requires

| # | Question | Why it matters | Bring back |
|---|---|---|---|
| 2.1 | **All-in pricing rules.** The FTC fee rule requires the total price up front for short-term lodging *(verify: effective May 2025)*. California's SB 478 requires all-in prices for nearly everything *(verify)*. Other states have similar laws. | The app already shows all-in prices everywhere. We need to confirm what has to be in the headline price (taxes? deposits?) for each kind of rental. | A checklist: what must be in the first price shown, and what can be listed separately. |
| 2.2 | **Taxes.** Occupancy or lodging tax on stays; possibly sales tax on parking and storage in some places. Is Everyspace the "marketplace facilitator" that must collect it? | Tax changes the all-in price and the receipt. | A table by city and state and by type of space: tax rate, who collects, how it's filed. Ask an accountant. |
| 2.3 | **Income reporting.** Payment platforms must send 1099-K forms to owners above a threshold *(verify the current threshold; it has changed several times since 2021)*. | Owner-friendly means simple tax season: we'd give owners a yearly earnings summary. | The current threshold and what we must report. |

## 3. Local rules for the launch city (pick one city first)

| # | Question | Bring back |
|---|---|---|
| 3.1 | **Which city launches first?** Look for big events (fairs, stadiums, concerts), tight parking, expensive storage, and lots of houses with driveways and yards. | 2–3 candidate cities with: event calendars, typical parking prices near venues, self-storage $/month, and short-term-rental rules. |
| 3.2 | **Short-term-rental rules** in that city: permits, night caps, primary-residence rules. | What owners must have, so the listing checklist asks for the right permit number. |
| 3.3 | **Is renting a driveway or garage legal there?** Some cities or HOAs restrict commercial use of residential parking. | Yes, no, or conditions, so we know which parking listings are allowed. |
| 3.4 | **Pools, backyards and events:** noise ordinances, occupancy limits, pool rules. | Defaults for guest caps and quiet hours on those listings. |
| 3.5 | **HOAs:** how many homes in the area are in HOAs, and do HOAs commonly ban this? | Whether to ask "Are you in an HOA, and does it allow this?" during listing. |
| 3.6 | **Business side:** zoning for fleet parking on residential land; sign permits; solar and battery permits and interconnection with the local utility. | Which business categories can launch in that city at all. |

## 4. Insurance and safety

| # | Question | Bring back |
|---|---|---|
| 4.1 | What protection can we offer owners (damage) and renters (injury), and at what cost per booking? Pools and backyards are the riskiest. | Quotes from 2–3 insurance brokers who cover "sharing economy" platforms, and what that does to our fee. |
| 4.2 | Do homeowners' policies exclude renting out parts of the home? | A plain-language note for owners. |
| 4.3 | ID checks: which provider, and at what cost? | Provider and cost per check. |

## 5. Payments

| # | Question | Bring back |
|---|---|---|
| 5.1 | A payment provider for marketplaces (for example Stripe Connect) so we don't need our own money-transmitter licenses *(verify with the provider)*. | The provider, its fees (these come out of our 10% + 3%), and payout timing. |
| 5.2 | Holding deposits (pre-authorizations) for long stays and storage. | What's possible and for how long. |
| 5.3 | Refunds for price beats and claims: how fast, and who eats the processing fee. | The policy. |

## 6. Owners and renters (talk to real people)

The goal is to be the easiest site for both sides. **Interview 10 owners and 10 renters.** Try to include an apartment landlord, someone with a pool, someone near a stadium or fairgrounds, and someone who already rents on Airbnb, Neighbor or SpotHero.

Ask owners:
- What do you hate about the sites you use now? Fees, payout delays, damage disputes, too much messaging, calendar double-bookings?
- Would you list your driveway, garage or yard? What would stop you? Strangers, liability, HOA, effort?
- Would you link your listings on other sites so we can show renters a comparison? Why or why not?
- What price would make it worth it?

Ask renters:
- How do you find parking for events or storage today, and what do you pay?
- What makes you trust a listing? Reviews, photos, ID checks, the guarantee?
- Would a price-beat guarantee make you book here instead of somewhere else?

Bring back: the top 5 frustrations on each side, plus real prices people pay today. These replace the made-up "typical prices" in `src/catalog.js` (`TYPICAL`).

## 7. The business side

| # | Question | Bring back |
|---|---|---|
| 7.1 | Talk to 3–5 companies: a community-solar developer, an EV charging network, a tower or small-cell company, a parcel-locker network, a delivery fleet manager. How do they find sites today, what do they pay, and what facts do they need first? | Their must-have site facts (which become the "Site facts" fields), typical rents, contract lengths, and who signs. |
| 7.2 | Would they pay to be on the business side (a subscription or a finder's fee) instead of a per-booking fee? | The business-side pricing model. |

## 8. Name and brand

| # | Question | Bring back |
|---|---|---|
| 8.1 | Is "Everyspace" free to use? Check the USPTO trademark search, the domain, and app store names. | Available, or 3 backup names. |

---

### What's already built to make this easy once you have answers

- Competitor fees live in one table (`PLATFORMS` in `src/compare.js`). Update the numbers and set `verified: true`, and the "(estimate)" labels disappear.
- The beat amount (`BEAT_PCT`) and claim window (`CLAIM_WINDOW_HOURS`) are single settings.
- Typical local prices are one table (`TYPICAL` in `src/catalog.js`), used by the listing wizard and the earnings estimator.
- Listing checklists (permits, insurance, HOA) are per category in `src/catalog.js`, so new local requirements are a one-line change.
