# Everyspace (working name)

A marketplace app for renting out **any part of a property, for any length of time**. Examples: a backyard for a night, a driveway spot on fair weekend, a garage bay for a month, the whole house like a vacation rental, a front-yard garden plot, or a roof leased for 20 years to a company that installs solar. It also handles **apartment buildings**: a renter can take just a unit, or a unit plus parking and storage, under rules the owner sets.

**Read [`SPEC.md`](SPEC.md) first.** It covers what can be rented, how bookings, pricing, add-ons and packages work, trust and legal requirements, and the build plan. The same plan is inside the app under Profile → The plan.

## Try it

**Without installing anything:** open `dist/everyspace.html` in any browser, on a phone or a computer. The whole app runs inside that one file and works offline. Your changes are saved in that browser.

**With the dev server** (Node 20+, no dependencies). It serves the app as an installable web app with an offline cache:

```bash
npm start        # http://localhost:3000, data saved to data/db.json
npm test         # rules and API tests
npm run build    # rebuild dist/everyspace.html after changing anything
```

## What's in the app

The app has three sides: **renting** and **hosting** for people, and **Everyspace for Business**, where companies lease roofs, pads, frontage, walls and lots. Solar, batteries, chargers, telecom, fleet lots, signs and parcel lockers never show up in everyday Explore.

**Renting (Explore, Saved, Trips, Inbox):**
- Search with a category bar, one-tap ideas ("Park for the game", "Throw a party", "Dock your boat"…), dates, and rental length. Toggle between a list and a map.
- "Coming up nearby" shows event pricing, such as the Harvest Festival and stadium home games. "Guest favorites" collects the best-rated spaces.
- Heart any space to keep it in **Saved**.
- Bundles, such as an apartment plus parking.
- **Earn from your place:** an estimator that turns what you have (spots, bays, yard hours, roof area…) into monthly and yearly income, split into money from people and money from companies.
- Listing pages with photos-style illustrations, prices for every rental length, event rates, add-ons, an availability calendar, reviews, and other spaces at the same address.
- Checkout adapts to the rental length:
  - **Hourly:** a time slot.
  - **Nightly or weekly:** a calendar range picker.
  - **Monthly:** a start date and a number of months.
  - **Lease:** 6–24 months.
  - **Solar and other infrastructure:** 5–25 years.
- Checkout also covers quantity, add-ons with tenant pricing, switching to a bundle, a live price breakdown and payment schedule, and a message to the host.
- Trips show a status timeline. Access codes appear once the booking is confirmed. You can cancel or withdraw, and leave a review once the stay has ended.
- Each booking has a chat with the host.

**Hosting (Today, Listings, Inbox, Earnings):**
- **Today:** requests to approve or decline, solar proposals to move forward (site visit, then contract, then confirmed), and upcoming check-ins.
- **Listings:** grouped by property, with nesting (building → units, garage → bays).
- **Earnings:** payouts by month, with leases spread across their months, and a breakdown per listing.
- **New listing wizard:** first choose **Rent to people** or **Lease to companies**, then what → where → details → prices (with typical local prices and optional event pricing) → who can rent it (anyone, add-on only, or cheaper as an add-on) → the required checklist and access instructions → publish.

**Business (Sites, Pipeline, Inbox):**
- **Sites:** every roof, pad, frontage, wall and lot open for lease, with the facts companies need (roof size and age, system estimate, electrical service, traffic, access) and the asking rent. Filter by site type; list or map.
- **Pipeline:** your proposals by stage (proposed → site assessment → contract → active) with active rent per year.
- People who open the business side see a landing page instead. Only verified business accounts can send proposals.

**Demo people:** use Profile → "Try it as someone else":

| Person | Role | Things to try |
|---|---|---|
| Sam | Renter | Book festival parking, rent the pool by the hour, review the past pool booking. |
| Priya | Renter | Already leases Unit 1B. Add parking later, or get a locker at the tenant price. |
| Maya | Host, house by the fairgrounds | Kim's holiday request is waiting for an answer. |
| Jordan | Host, 6-unit apartment building | Tenants-only parking, lockers, bundles. |
| Luis | Host, bungalow and ranch | Pool, woodshop, ADU with a guest-only parking spot, RV lot, barn roof. |
| Ana | Host, condo near the stadium | Game-day parking prices. |
| Rosa | Host, Lakeview cottage | Cottage stays, boat slips, pickleball court. |
| SunCo Solar | Business | Opens on the business side. Send a 20-year proposal on the barn roof. |
| VoltWay Charging | Business | A charger-site proposal is in site assessment. |
| ParcelPoint, Greenleaf Delivery | Business | Parcel-locker walls; overnight van lots. |

## Code map

| Path | What it does |
|---|---|
| `src/catalog.js` | Rentable categories, allowed rental lengths, booking modes, and host checklists |
| `src/availability.js` | Quantity (peak overlap), parent/child blocking, `conflictsWith`, blackouts |
| `src/booking.js` | Cart rules (lengths, add-on anchors and caps, packages), quotes, booking states |
| `src/pricing.js` | Rates, event pricing, add-on and package pricing, fees, payment schedule |
| `src/social.js` | Messages, reviews, and display status (active or completed) |
| `src/host.js` | Host dashboard, payout schedule, availability calendar |
| `src/listings.js` | Search, and creating properties, spaces (checklist enforced), and packages |
| `src/routes.js` | API routes, shared by the server and the single-file build |
| `src/server.js` | Node HTTP server |
| `public/js/` | The app: `main.js` (router and navigation for the three sides), `explore`, `space`, `book`, `trips`, `inbox`, `host`, `wizard`, `biz` (business side), `earn` (estimator and Saved), `profile`, `calendar`, `art` (drawn illustrations), `core` (shared helpers) |
| `scripts/build-standalone.mjs` | Bundles everything into `dist/everyspace.html` |
| `scripts/e2e.cjs` | Playwright click-through of 25 flows: `node scripts/e2e.cjs shots http://localhost:3000/` |

This is a prototype. Logins, real payments, a database, photo uploads, and identity verification are Phase 1 in the spec.
