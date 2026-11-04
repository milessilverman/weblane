# City Pretty — handoff for the next session

Branch: `claude/serene-cannon-exc9om` (repo `milessilverman/weblane`, folder `neighborhood-roi/`).
Current deliverable: `reports/city-pretty-la-county.html` (V2.3: real EIFD inputs).

## How it's built
- Data: `.github/workflows/neighborhood-data.yml` runs `pipeline/county_la.py` stages in GitHub Actions
  (geo, osm, transit, sales, crime, requests311, crashes, trees, parcels, assets, tra, assessed, basemap, research_check, zoning, underused, projects, sb79) and commits
  `data/derived/county_la/`. Dispatch with input `county_only=true` to skip the slow tract/Westside jobs, and
  `county_stages=tra,assessed` (comma list) to run only some county stages; the rest keep their last data.
  This sandbox can't reach County/ArcGIS hosts, so data pulls must run in Actions.
- Model: `python3 model/score_county.py`, `python3 model/eifd_tra.py`, `python3 model/gaps.py`,
  `python3 model/underused.py`, then `python3 model/corridors.py` → `web/county_data/`.
- Page: `python3 web/build_county_html.py` → `reports/city-pretty-la-county.html`.

## Research in this folder
- `City_Pretty_Evidence_Sourcebook*.html`: rounds 1-3 (ChatGPT). Already used.
- `round5_*`: overnight research (EIFD tax-rate-area data, corridor right-of-way layers,
  FCC broadband, cost verification). Part 1 (EIFD inputs) used in V2.3; parts 2-4 not yet used.
- Gemini passes (pasted in chat, not saved here): used only for program rules confirmed by
  both audits; its costs are labeled "unverified" in the model; none of its price effects are used.

## EIFD data (done in V2.3)
- `tra` stage keeps the Auditor-Controller files in `data/derived/county_la/raw/`: AF49 (FY 2026-27 Modified ATI
  ratios: every agency's share of tax increment in each of 13,392 TRAs), AF91 (countywide agency totals), the
  TRA lookup CSV (voter-approved debt rates, not shares), and the BOE TRA-district table.
- `assessed` stage pulls all 2.43M parcels (2026 roll) with TRA and values → `bg_assessed.csv`, `bg_tra_av.csv.gz`.
- `model/eifd_tra.py` parses AF49 (001.05 = County General; 1xx/2xx.01 = city general levy; 400+ = schools/ERAF;
  rest = other districts), weights by each block group's net taxable value per TRA, flags TRAs already in an EIFD
  (Carson, West Carson, Covina, Lakewood, Norwalk, La Verne, Palmdale) → `web/county_data/eifd.json`.
- Checks: TRA 01519 County share 30.46% = West Carson IFP; Pasadena 21.0%/27.9% vs draft IFP 21.09%/27.88%.
- Still assumptions: growth, new development, pledge %, rate, coverage; base year = 2026 roll, not formation year.

## Map orientation (done in V2.4)
- `basemap` stage: every named OSM street merged per name and class (`map_streets.geojson.gz`), and all parks of any
  size from OSM plus the LA County DPR "Countywide Parks and Open Space" layer, which OSM lacks
  (`map_parks_all.geojson`). The County layer also has amenity fields (TENIS, BSKTB, POOLS, PLGND, DGPRK, RSTRM...)
  that aren't used yet.
- Page: streets are encoded polylines in 0.05° cells, drawn only on screen (collectors from z13, locals from z14).
  Rotated street names (arterials z13, collectors z14, locals z15), freeway shields from z10.5, park names sized by
  acreage, scale bar, "Find me" (geolocation, opens your block group).
- Round 6 research prompt: `research/round6_research_prompt.md` (zoning, new improvements, QoL pricing, per-house).

## Round 6 (done in V2.5)
- Research received: `research/round6/partA_audit/` (careful; its 14 links all work) and a long pasted report
  (Parts A-G; only 11 of its 34 links worked, and it said the expired federal 25C/25D credits were still active). `research_check` stage
  re-tests every link → `data/derived/county_la/research_check.json`. Treat the long report as leads.
- Facilities (in `basemap`): LA County LMS layers + OSM → `map_facilities.geojson`, `bg_facilities.csv` (nearest of each kind).
- `zoning` stage: LA City (Zoning/FeatureServer/15), unincorporated (DRP Open_Data/3), Santa Clarita (NEWCODE);
  SCAG 2019 parcel land use (services5.../2019_Regional_Land_Use_Information_for_Los_Angeles_County) fills the rest
  as block-group summaries only. `zone_category()` maps codes to broad categories. Official SB 79 layer not found yet.
- Model: 19 round-6 improvements graded **U** (hidden unless the viewer opts in, excluded from county summaries);
  `model/round6/qol_benefits.csv` (yearly public benefit shown on QoL cards), `owner_upgrades.csv` (homeowner table,
  rebates corrected), `zone_rules.csv` (base-zone standards for a few zones; unverified).
- Fixed: park/street canvases blocked clicks → now in pointer-events:none panes. Parcel tiles split and retry on 500s.

## Neighborhood gaps and plans (done in V2.6)
- `model/gaps.py`: each block group vs. its 50 nearest peers (income, density, home value, year built, kids,
  no-car, single-family share) on 22 measures. Gap = worse than >=80% of peers by a set margin; strength = better
  than 85%. Each gap maps to fixes already costed for that block group. Per named neighborhood: the top gaps by
  share of homes, one concrete project each, sited in the most affected block group, naming the nearest actual
  park, school, library and rail station. Cheapest step first ("quick win"), then by return. `web/county_data/gaps.json`.
- Planned: rewrite these plans monthly with Claude in the pipeline (needs an ANTHROPIC_API_KEY secret) and add an
  on-page assistant once the map is hosted.

## Profit, underused land, facility footprints (done in V2.7)
- `underused` stage: Assessor parcels coded parking / golf, vacant >= 0.5 ac, commercial lots whose buildings are
  < 20% of land value (all with roll values); `basemap` adds OSM surface lots >= 1 acre, facility footprints
  (`map_facility_areas.geojson`), rail lines and stations under construction.
- `model/underused.py`: merges stacked (condo) parcels, drops airport land and active industrial uses, keeps vacant
  land only in built-up areas; per site: assessed land, market land estimate (never below assessed), zone, rail
  distance (incl. stations under construction), homes possible (zone densities; SB 79 assumption near rail), rough
  margin = homes x (new-unit price - build cost) - land. Assumptions are in `ASSUMPTIONS` and shown on the page;
  replace with round-7 research (`research/round7_research_prompt.md`). Neighborhood profit = paying projects net
  of cost + positive site margins.
- Page: per-type facility switches + footprints (z14+), underused layer (z13+, click for details; also selects the
  area), "Profit potential" map color and report ranking, rail under construction in the transit layer.

## Round 7 (done in V2.8)
- Research: `research/round7/` (honest: H31/H32 Socrata returned data; most other items listed or NR).
- `projects` stage: HCD APR table A2 (all LA County cities, 2021+; completed homes = sum of CO_* columns; one row per
  project at its furthest stage), LAHD affordable pipeline (mymu-zi3s), LADBS new-building permits since 2024
  (pi9x-tg5x), Housing Element sites (SCAG consolidated + County) → `map_projects.geojson.gz`, `map_he_sites.geojson.gz`.
- `model/underused.py`: apartment value from rents and cap rate, cost from LA hard-cost case studies (round 7 Part I);
  sites flagged when in a Housing Element inventory; neighborhood "already under way" counts.
- Still missing: market land sale prices, current fee schedules, official SB 79 layer, Metro project geometry.

## Per-house analysis and loose ends (done in V2.9)
- Per house: at zoom 17+ a click on a block group also queries the Assessor parcel layer live from the page
  (fetch, JSONP fallback; needs internet) → parcel outline, lot area from the outline, building, year, beds/baths,
  zone from the embedded zoning, eligibility (detached ADU / JADU / SB 9 / pool / solar / seismic / repiping /
  bathroom / fire hardening) and upgrades ranked by net value for that house (area home value and rents).
  Code: `houseAt`, `houseChecks`, `houseUpgrades` in `web/county.src.html`. Map max zoom raised to 19.
- `sb79` stage: discovers SCAG's official SB 79 service (maps.scag.ca.gov/scaggis/rest/services/SB79/SB79/MapServer:
  0 = stops with SB79_TIER T1/T2, 1 = tier buffers) → `map_sb79.geojson`. Underused sites and panels use distance to
  the nearest Tier 1/Tier 2 stop; densities per tier/band are approximations (`SB79_TIERS` in model/underused.py).
- Event venues (conference/convention) no longer count as community centers; profit share only for 500+ homes and
  missing home values filled with the county median; lots of 10+ acres count half for housing; rent factor <= 1.6.

## Upgrades and named corridors (done in V2.10)
- `model/round6/owner_upgrades.csv` rewritten: 46 upgrades with 2025 LA estimates (second stories ~$600/sq ft all-in,
  additions ~$500/sq ft, bathroom $60k, ADU $300k, solar+battery without federal credit) plus rooftop deck, decks,
  pergola, outdoor kitchen, spa, sport court, native/vegetable gardens, fruit trees, lighting, office, gym. Marked
  "est" until round-8 research (`research/round8_research_prompt.md`) confirms. Tables show value per $1.
  Per house (`houseUpgrades`): space additions valued at area value/sq ft (home value / 1,800) x 0.8; second story
  sized to the footprint, only for likely one-story houses where the zone height allows.
- `basemap` adds OSM bikeways by class (`map_bikeways.geojson.gz`). `model/corridors.py` names the street and
  segment (cross streets) for bus/BRT/signal priority/shade (arterial at the busiest stop), bike/road diet (longest
  collector, else arterial, skipping streets with protected lanes or paths), speed cameras (arterial), slow streets
  and calming (local), rail (busiest bus corridor + nearest station); notes existing bikeways, LA bus lanes, SB 79
  stops and rail under construction. City/Metro plan layers to be joined when round 8 returns.

## Next steps
1. (done) EIFD tax-rate-area data.
2. Add corridor right-of-way layers (abandoned rail, transmission, flood channels, Class I paths)
   so rail/creek trails can be sited.
3. Add FCC broadband data so fiber/5G is only suggested where service is poor.
4. Replace "unverified" costs with the sourced figures from round 5's Part 4.
5. Map orientation: remaining items are mini-map, breadcrumb, hover outline, shareable link.
6. Per-house: add HPOZ/historic and very-high-fire checks per parcel (live queries), and a sales-based value estimate.
7. Verify round-6 effect sizes against their cited studies before promoting any U item to D or better.
8. Official SB 79 stop/tier layer (SCAG) and CPAD access types; FCC broadband (the BDC download page returned 403).
