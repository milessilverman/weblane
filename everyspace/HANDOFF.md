# Everyspace: handoff for the next session (or an audit)

Read `../VISION.md` first for where this is going, then `SPEC.md` (what's built and why) and `RESEARCH.md` (open questions). This file is the practical "how it works and where things live".

**Status:** a working prototype with no backend yet. It's parked for now: the owner's focus is City Pretty and StreetForge. **Don't integrate it with City Pretty or StreetForge yet.** The apps stay separate until the owner says otherwise.

## Run and check

```bash
npm test                     # 30 unit/API tests (node:test, no dependencies)
npm run build                # dist/everyspace.html: the whole app in one offline file
npm start                    # dev server on :3000 (PORT, DB_FILE env vars)
node scripts/e2e.cjs shots "file://$PWD/dist/everyspace.html"   # 31-flow Playwright click-through
```

GitHub Actions (`.github/workflows/checks.yml`) runs all of this on every push that touches `everyspace/`.

## How it's built

- **Domain logic is plain ES modules in `src/`.** There's no framework, and the modules don't depend on HTTP. `routes.js` maps API paths to them. The same routes run in the Node server (`server.js`) and inside the browser in the single-file build (`scripts/build-standalone.mjs` bundles every module into one scope per file).
  - `catalog.js`: categories, audiences (consumer vs business), terms, checklists, `TYPICAL` prices.
  - `availability.js`: quantity (peak overlap), parent/child blocking, `conflictsWith`, blackouts, paused.
  - `booking.js`: cart rules (terms, lengths, add-ons and anchors, packages, business-only rule), quotes, the state machine.
  - `pricing.js`: rates, event pricing, fees (10% renter, 3% owner), payment schedule.
  - `compare.js`: `PLATFORMS` competitor fee table (**estimates, `verified: false`**), comparisons, the automatic price beat, price-match claims. The beat is funded from our cut (service + owner fee) and capped at it; owner payout never changes.
  - `owner.js`: edit, pause, instant/request mode, blackouts, cross-listings, nearby price ranges, take-home parity.
  - `social.js` (messages, reviews), `host.js` (dashboard, payout schedule, calendar), `listings.js` (search, create), `seed.js` (demo data), `store.js` (JSON file store).
- **UI is vanilla JS modules in `public/js/`**, with a hash router in `main.js` and three sides (renting, hosting, business). `art.js` draws every illustration as SVG, so there are no image files.

## Where research plugs in (one place each)

| Research | Table / setting |
|---|---|
| Competitor renter and owner fees | `PLATFORMS` in `src/compare.js`, researched 2026-11-04 (`RESEARCH_RESULTS.md` §1). **null = unknown, never 0** |
| Price-beat percentage, claim window | `BEAT_PCT`, `CLAIM_WINDOW_HOURS` in `src/compare.js` |
| Typical local prices | `TYPICAL` in `src/catalog.js` (the listing wizard, estimator and Manage listing use it) |
| Local rules and permits | `checklist` per category in `src/catalog.js` |
| Fees | `SERVICE_FEE`, `HOST_FEE` in `src/pricing.js` |
| Taxes by city | `TAX_RULES` in `src/tax.js` (San Diego, Phoenix, Indianapolis lodging; other categories "not determined") |
| How long an owner-submitted price stays usable | `STALE_DAYS` in `src/compare.js` |
| Where each typical price came from | `TYPICAL_META` in `src/catalog.js` |

## Known gaps (on purpose, for later)

- No backend, logins, payments, photo uploads or ID checks. The JSON-file store is for the demo only.
- Competitor fees and typical prices are estimates.
- Claims marked "in review" have no reviewer workflow yet.
- Dates are UTC everywhere. There are no time zones yet.
