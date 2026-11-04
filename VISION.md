# Vision and roadmap (read this first)

This repo holds two separate apps by the same owner. A third app, StreetForge, lives elsewhere. This file records where all three are heading, so anyone working on them (a person, Claude, or Fable) can build today's features in a way that leaves room for tomorrow's. **Don't build the "later" items yet. Just don't block them.**

## The three apps

| App | Folder / location | What it is |
|---|---|---|
| **Everyspace** (working name) | `everyspace/` | Marketplace for renting out any part of a property, for an hour or for 25 years. It has an everyday side (people) and a business side (companies leasing roofs, pads, frontage, walls, lots). Transparent all-in prices and a price-beat guarantee paid from our own cut. See `everyspace/SPEC.md` and `everyspace/RESEARCH.md`. |
| **City Pretty** | `neighborhood-roi/` (its data refresh runs from branch `claude/serene-cannon-exc9om`) | Which improvements raise property values the most per dollar, for every neighborhood. It has an evidence library, EIFD and tax-increment calculator, gaps, underused land and projects under way. LA County first; the whole US is the goal. See `neighborhood-roi/README.md` and `neighborhood-roi/research/HANDOFF.md`. |
| **StreetForge** | streetforge.app (separate code) | Design a street's before and after. It saves `streetforge-project` JSON (v1, `scenes.before` / `scenes.after`, each a list of elements with sizes in feet, about 100 element types) to its own Supabase project, with share and remix links. **Coming:** satellite imagery under the design (so "before" comes from reality), cost estimates, and AI. |

Everyspace and City Pretty are **two different apps**. They may share a style of backend, but they keep separate data and accounts.

## Where City Pretty is going (later; leave room for it)

1. **Upload anything for a specific home** (contracts, bids, plans, photos, spreadsheets, emails). AI pulls out every work item and cost, checks costs against local renovation costs, and returns the value added to that home *in the context of the whole neighborhood*, plus comparable sales. Or just ask: "how much would X add to this home?" Uploads are **deleted after processing by default**; the user can choose to keep them.
2. **Investment finder.** The strategy is **buy → improve while renting → resell → move on**. Rank individual homes, and clusters of homes in one neighborhood ("buy several properties before a planned improvement"), by return from specific improvements. Everyspace rental income is *not* counted yet (maybe later). Always show legally required disclaimers (not an appraisal, not investment advice) and follow fair-housing rules, but still give the information.
3. **AI chatbot** that answers value questions on every level (home, block, neighborhood, city):
   - The value added by a project (e.g., "a bike path along this creek that has none").
   - **Every way it could be funded**: EIFDs and other tax-increment tools, CFDs/Mello-Roos, assessment districts, BIDs, federal, state and county grants and measures, bonds, developer and impact fees, public-private partnerships, philanthropy, utilities, crowdfunding.
   - What to build alongside it for the biggest combined value (trees, lights, bike parking…), with the cost and value of each.
   - It answers from our own evidence first, and labels anything else as outside knowledge.
4. **For cities:** recommend which transit and neighborhood projects give the best *financial* return (property value and tax increment). **No ridership modeling yet.**
5. **StreetForge integration.** StreetForge draws the change and estimates its cost. City Pretty reads the project file, compares after with before (e.g. +600 ft bike lane, +24 trees, +12 lights), matches each change to the evidence library, finds the homes in range, and estimates value added and funding. Links go both ways ("See the value" / "Design this street"). Both apps should use the same cost sources, so their numbers agree.
6. **Speed at national scale.** Maps must load fast everywhere: tiled map data, load on demand, a backend for details.
7. **An API for outside users** someday. The direction is undecided, so keep the internals behind clean, documented interfaces.

## Where Everyspace is going (later; leave room for it)

- Real backend, logins, payments (marketplace payments), photos, ID checks, insurance.
- Research results plug into single tables: competitor fees (`PLATFORMS` in `everyspace/src/compare.js`), typical prices (`TYPICAL` in `everyspace/src/catalog.js`), and per-category checklists and local rules.
- Possibly, later: count Everyspace rental income in City Pretty's investment returns.

## How the work will happen

1. The owner gathers research (prompts in `everyspace/` and `neighborhood-roi/research/`) and hands it over.
2. Claude builds the research into the apps.
3. **Fable** audits and improves everything, and integrates the apps as described above.
4. StreetForge is audited and improved in parallel; AI is added to all the apps.
5. Then the "later" items above get built.

## Rules of thumb for anyone building here

- **Keep research-driven numbers in one place** (tables or config), with a source and a "verified" flag. Never scatter them through the code.
- **Keep logic in plain modules separate from screens**, so it can move behind an API and be called by the AI as tools.
- **Show estimates as estimates**, with sources and dates.
- **AI spending must be capped** (the cap amount is to be decided).
- **No API keys in the browser** once other people use an app. Route AI calls through a backend.
- **Tests and the end-to-end click-through must pass** before pushing. Each app's README says how to run them.
