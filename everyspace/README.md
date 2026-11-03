# Everyspace (working name)

A marketplace for renting out **any part of a property, for any length of time**. Examples: a backyard for a night, a driveway spot on fair weekend, a garage bay for a month, the whole house like a vacation rental, a front-yard garden plot, or a roof leased for 20 years to a company that installs solar. It also handles **apartment buildings**: a renter can take just a unit, or a unit plus parking and storage, under rules the owner sets.

**Read [`SPEC.md`](SPEC.md) first.** It covers what can be rented, how bookings, pricing, add-ons and packages work, trust and legal requirements, and the build plan.

## Run it

Needs Node 20+ and has no dependencies.

```bash
npm start        # http://localhost:3000 (data saved to data/db.json)
npm test         # rule tests: quantity, hierarchy, add-ons, packages, solar flow…
npm run build    # dist/everyspace.html: plan + full demo in one file, no server needed
```

Use the "Acting as" menu to switch between demo users:

- **Sam / Priya** (renters). Book festival parking (event pricing), the backyard by the hour, or Unit 1A with 2 parking spaces and a locker. Priya already leases 1B, so she can add parking later and gets the tenant price on lockers.
- **Maya** hosts a house with 11 spaces: whole home, backyard, room, driveway, RV pad, garage bays, attic, garden plots, roof for solar, and a battery pad.
- **Jordan** hosts a 6-unit building with tenants-only parking (max 2 per unit), lockers with a tenant discount, EV chargers, and two packages.
- **SunCo Solar** is an infrastructure partner. Send a 20-year roof proposal, then advance it as Maya: site assessment, contract, confirmed.

"Reset demo" restores the seed data.

## Code map

| File | What it does |
|---|---|
| `src/catalog.js` | Rentable categories, allowed terms, booking modes, and host checklists |
| `src/availability.js` | Quantity (peak overlap), parent/child blocking, `conflictsWith`, blackouts |
| `src/booking.js` | Cart rules (terms, lengths, add-on anchors and caps, packages), quotes, booking state machine |
| `src/pricing.js` | Rates per term, event pricing, add-on rates, package pricing, fees, payment schedule |
| `src/listings.js` | Search, and creating properties, spaces, and packages |
| `src/routes.js` | API routes, shared by the server and the single-file build |
| `src/server.js` | Node HTTP server for the API and the UI |
| `scripts/build-standalone.mjs` | Builds `dist/everyspace.html` (the API runs in the browser; data is saved in localStorage) |
| `public/` | Demo web UI (vanilla JS) |

This is a prototype. Auth, payments, a real database, photos, and maps are Phase 1 in the spec.
