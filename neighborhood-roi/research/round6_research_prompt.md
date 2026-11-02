# City Pretty — Round 6 research request (LA County)

You are helping build **City Pretty**, a public web map of all of Los Angeles County (6,591 Census block groups,
88 cities plus unincorporated areas). For every area it ranks neighborhood improvements (street trees, bus lanes,
parks, lighting, etc.) by **home value added per $1 spent**. It prices each one (build cost, land, 10 years of
upkeep), cites the evidence, says who could pay for it, and includes a tax-increment (EIFD) calculator. The data is
pulled by Python scripts that run in **GitHub Actions** (US datacenter IPs, no login, no browser, no CAPTCHA),
so every data source you give me must be reachable that way.

The next versions will:
1. make the map easier to read (named streets, every park drawn clearly);
2. show **zoning: what can legally be built on each parcel**;
3. add many more improvements (rain gardens, permeable pavement, a neighborhood restaurant, a new school, ...);
4. put a **dollar value on the quality-of-life projects** that have no measured home-price effect today;
5. go down to **individual houses**: what each owner can do to raise their own home's value (ADU, EV charger,
   landscaping, repainting, ...), and whether their parcel allows it.

This prompt is going to several research assistants. **Do every part you can, in order.** If you run out of room,
finish whole parts rather than skimming all of them, and say which parts you did not reach.

---

## Rules (apply to every part)

- **Verify, don't recall.** Open each URL. For ArcGIS layers, open `<layer URL>?f=pjson` and report the real field
  names, geometry type, `maxRecordCount`, and last-edit date. For Socrata, give the 4x4 dataset ID and its
  `/resource/<id>.json` endpoint. For files, give the direct download URL, file type and size.
- Give **3 real sample records** (actual values) for every dataset, or write `NR` if you could not retrieve them.
- `NR` = not recovered. Never fill a gap with a guess or a "typical" number unless you label it `ESTIMATE` and
  explain how you got it. **Unknown is better than invented.**
- Label each source `VERIFIED` (you opened it and saw the stated content), `LISTED` (a publisher page lists it
  but you couldn't open it), or `NR`.
- **Money:** give the dollar amount, the **year the price is from**, and what it includes (design, land,
  utilities, contingency, O&M). Prefer LA County/LA City records (staff reports, bid tabs, adopted budgets, grant
  applications) over national averages. If you only have a national figure, say so.
- **Effects on home value:** give the % effect, how far it reaches (meters), the study location and years, sample
  size, confidence interval, method (hedonic, repeat-sales, difference-in-differences, ...), and a grade:
  **A** = measured on LA sales; **B** = a rigorous study of the same intervention elsewhere; **C** = transferred
  from a related intervention or chained through another effect; **D** = assumption. Prefer low-end estimates.
  Note negative effects (e.g. displacement, noise, parking loss).
- **Law and policy:** cite the code section or bill number and its effective date, and say whether it is in force
  as of **November 2026**. Separate adopted rules from drafts and proposals.
- **Licensing:** for every dataset or map service, state the license or terms of use and whether a free public
  website can use it (and what attribution it needs). Flag anything paid, rate-limited, or "non-commercial only".
- Keep identifiers as text with leading zeros (AIN/APN, TRA, GEOID, zone codes).

## Deliverable format

Return **one CSV per part** (UTF-8, header row, every field quoted) with exactly the columns listed below, plus a
short notes section per part. If you can't attach files, put each CSV in its own fenced code block labeled with
its filename. Also return `sources.csv` with columns:
`source_id,title,publisher,url,date_published,date_accessed,status,notes`. Every other row cites `source_id`s.

---

## Part A — Map orientation: streets and parks

The map currently draws only freeways and major arterials (no street names), and only parks of 2+ acres.
I need named streets at every zoom level and every public park, including small ones.

**A1. Street centerlines with names and road class**, county-wide. Candidates to verify: LA County Street
Centerline (CAMS / LA County Enterprise GIS), City of LA Street Centerline (BOE/StreetsLA), Caltrans State
Highway Network, OpenStreetMap extracts. For each: endpoint, name field(s), road class/hierarchy field, coverage
(does it cover all 88 cities?), update date, license.

**A2. Basemap and label overlays that a free public site may use** (raster or vector tiles): for example
OpenFreeMap, Protomaps/PMTiles, OSM-based vector tiles, CARTO, Stadia, Esri label overlays, MapTiler, USGS
National Map. For each: tile URL template, whether an API key is needed, free-tier limits, attribution text, and
whether it can sit as a **labels-only layer on top of** my own colored polygons.

**A3. Freeway and highway route numbers** (to draw I-405, US-101, SR-110 shields): a source with route number
and type per segment.

**A4. Complete public park and open-space inventory** for LA County, including pocket parks, plazas, beaches,
regional open space, joint-use schoolyards, community gardens, and trails. Candidates to verify: LA County Parks &
Open Space / Countywide Parks layer, California Protected Areas Database (CPAD, GreenInfo Network), LA City
Recreation & Parks boundaries, County DPR facilities, LA County Park Needs Assessment (PNA/PNA+) layers, the
Community Schoolyards / joint-use agreement lists, Safe Clean Water project sites. For each: endpoint, fields
(name, acres, owner, access, type, amenities), how many features in LA County, smallest park size included,
update date, license. Say which **one** source is the most complete for a county-wide "every park" layer, and
which second source fills its gaps.

**A5. Park amenities:** sources listing what each park has (playground, pool, courts, restrooms, fields, dog
park) county-wide or for the largest cities.

`partA_map_layers.csv` columns:
`layer_id,purpose,dataset_name,publisher,endpoint_url,format,geometry,key_fields,feature_count_LA,coverage,update_date,license,attribution,api_key_needed,sample_records,status,source_ids,notes`

---

## Part B — Zoning: what can be built on each parcel

Goal: click any parcel and see its zone, what the zone allows (uses, units, height, floor-area ratio, lot coverage,
setbacks, parking), which state laws add rights on top (ADUs, SB 9, density bonus, transit upzoning), and which
overlays restrict it.

**B1. Zoning polygons for every jurisdiction.** Make a row for **each of the 88 cities and for unincorporated LA
County** (County Title 22 zoning, including Community Standards Districts). Give the zoning layer endpoint, zone
code field, and update date, or `NR` if the city publishes none. Also verify the regional fallbacks: the **SCAG
regional zoning and general plan land use datasets** (latest vintage), and any state compilation (e.g. the
California Statewide Zoning Atlas / HCD datasets). Give coverage counts.

**B2. Zone code dictionary.** For LA City (including the new Chapter 1A zoning code: say which community plan
areas use it and which still use Chapter 1), unincorporated County, and the **15 largest cities by housing units**
(Long Beach, Glendale, Santa Clarita, Lancaster, Palmdale, Pasadena, Torrance, Pomona, El Monte, Downey, Inglewood,
West Covina, Burbank, Norwalk, Carson are likely; verify the ranking). For every zone code give: allowed housing
types, max units (per lot or per acre), max height (ft and stories), FAR, lot coverage, minimum lot size, front,
side and rear setbacks, parking minimums, and the code section. Machine-readable, one row per jurisdiction × zone.

**B3. State laws that override local zoning**, with their current (Nov 2026) rules and what a parcel needs to
qualify: ADU/JADU law (Gov. Code 66310 et seq., including 2024-2026 amendments), SB 9 (two-unit and lot split),
SB 684 / SB 1123 (small starter-home subdivisions), the State Density Bonus Law, AB 2097 (no parking near transit),
AB 2011 and SB 6 (housing on commercial land), **SB 79 (2025) transit-oriented upzoning**: its tiers, distances,
heights and densities, effective dates, and any LA local implementation plan, SB 35/SB 423 streamlining, and
AB 1033 (selling ADUs separately, where adopted). Also LA City programs: ED 1, the Citywide Housing Incentive
Program (CHIP), and what replaced TOC. For each: the rule in plain words, parcel eligibility tests that a map could
check (zone, distance to a transit stop, lot size, fire zone, historic status, tenant history), and any dataset
that maps eligibility (e.g. the official SB 79 transit stop list, high-quality transit areas).

**B4. Overlays that restrict building**, each with an endpoint: historic districts (LA HPOZs, County and city
historic districts, National Register), specific plans, Coastal Zone, hillside areas, Very High Fire Hazard
Severity Zones (and the ADU/SB 9 limits there), Alquist-Priolo fault zones, liquefaction and landslide zones,
FEMA flood zones, airport land-use zones, Significant Ecological Areas, the Mills Act contract list.

**B5. What's already on each parcel**, to work out remaining capacity: building footprints with height (LARIAC),
Assessor parcel characteristics (units, square feet, year built, bedrooms; the field list of the Assessor parcel
layer at `public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0` and any richer
table), and building permit feeds (LADBS, County EPIC-LA, the largest cities' permit portals) with endpoints and the
fields that show ADUs, additions, solar, EV chargers and pools.

`partB_zoning_sources.csv` columns:
`jurisdiction,layer_type,dataset_name,endpoint_url,format,zone_field,other_key_fields,feature_count,update_date,license,sample_records,status,source_ids,notes`

`partB_zone_rules.csv` columns:
`jurisdiction,code_version,zone_code,zone_name,allowed_housing_types,max_units_per_lot,max_units_per_acre,max_height_ft,max_stories,max_far,max_lot_coverage_pct,min_lot_sqft,setback_front_ft,setback_side_ft,setback_rear_ft,parking_per_unit,code_section,effective_date,status,source_ids,notes`

`partB_state_laws.csv` columns:
`law_id,name,citation,effective_date,in_force_nov_2026,what_it_allows,parcel_eligibility_tests,exclusions,local_implementation_LA,eligibility_dataset_url,status,source_ids,notes`

---

## Part C — New neighborhood improvements

Research each item below and **add any other improvement with real evidence** that a city, County or community
group could do in LA (aim for 25+ new rows). Already in the model, so skip them unless you have better LA cost or
effect data: street trees, schoolyard greening, vacant-lot greening, community gardens, pocket parks, park
upgrades, dog parks, bus lanes, BRT, traffic calming, street lighting, foot patrols, violence interruption, BIDs,
encampment response, blight rehab, affordable housing, power-line undergrounding, EV fast-charging hubs, sound
walls, school bonds, grocery stores, main-street grants, farmers markets, green alleys, cool pavement, pickleball,
tennis, basketball, pools, splash pads, skate parks, sports fields, rec centers, public restrooms, bus shelters,
crosswalks, road diets, sidewalks, cameras, litter crews, graffiti removal, microgrids, school air filters,
libraries, clinics, outdoor dining, protected bike lanes, rail/creek trails, transit signal priority, speed cameras,
roundabouts, pedestrian signals, school streets, murals, tiny forests, fiber/5G, rail stations, freeway caps,
transit upzoning.

Must cover: **rain gardens and bioswales**, **permeable pavement** (streets, alleys, parking), stormwater
capture parks, daylighted creeks, **a neighborhood restaurant or café** (what can a city actually do: corner-store
and restaurant zoning reform, commercial-space subsidies, food halls, kiosks in parks; and the price effect of
nearby restaurants/cafés), **building a new public school** (LAUSD and other districts' cost per seat, land,
timelines, and the price effect of a new or better-rated school), charter/magnet access, neighborhood
wayfinding/street-name signs, shade structures, cooling centers, public plazas/street-to-plaza conversions,
parklets, slow streets, bike share stations, e-bike libraries, alley activation, public art/lighting, street
furniture, drinking fountains, utility-box art, sidewalk vending zones, night markets, community land trusts,
neighborhood microtransit, school-zone safety, noise reduction (quiet pavement), air-quality buffers (vegetation
barriers near freeways), urban heat measures, and anything else you find with strong evidence.

For each: LA cost (unit and what's included, with price year), upkeep per year, lifespan, home-value effect
(with all the evidence fields from the Rules), how far the effect reaches, years to full effect, quality-of-life
outcomes, where it fits (what data would site it on the map: e.g. impervious surface, slope, soil infiltration,
flood risk), and who could pay for it (Measure W / Safe Clean Water Program, Measure A parks, Prop 4 (2024), state
and federal grants, BIDs, EIFDs, CDBG) with current program status.

Also give **data layers to site them**: impervious surface / land cover, soil infiltration (hydrologic soil
groups), stormwater drainage and catch basins, Safe Clean Water project inventory, LA Stormwater "Green Streets"
potential maps, land surface temperature, and commercial vacancy / storefront data.

`partC_improvements.csv` columns (same as the round-5 file):
`id,name,category,scale,maturity,capex_per_unit,unit,capex_dollar_year,capex_includes,annual_om,lifespan_years,home_value_effect_pct,effect_reach_m,effect_years_to_full,effect_grade,effect_CI,effect_N,effect_study_location,negative_effects,quality_of_life_outcomes,fits_where,data_needed_to_site_it,LA_cost_source,funding_sources,status,source_ids,notes`

---

## Part D — Putting a dollar value on quality-of-life projects

These are in the model but ranked only by local need because there is **no measured home-price effect**:
green alleys, cool pavement, pickleball, tennis, basketball, pools, splash pads, skate parks, sports fields, rec
centers, public restrooms, bus shelters, crosswalks, road diets, sidewalks, security cameras, litter crews, graffiti
removal, microgrids, school air filters, libraries, clinics, outdoor dining, protected bike lanes, rail/creek
trails, transit signal priority, speed cameras, roundabouts, pedestrian signals, school streets, murals, tiny
forests, fiber/5G.

For each, find the best way to put a dollar value on it, in this order of preference:
1. a **home-price study** of that exact item (any location);
2. a **willingness-to-pay or contingent-valuation** study;
3. **avoided costs or benefits** with standard values: crashes avoided × FHWA/USDOT crash costs; heat deaths or
   ER visits avoided; asthma cases; physical activity → health costs (WHO HEAT method); time saved × USDOT value of
   travel time; energy saved; stormwater fees avoided; crime avoided × crime cost estimates;
4. a **benefit-cost analysis** already done by a public agency (Caltrans, Metro, LA DOT, CDC, EPA, a
   state grant program's benefit calculator) that City Pretty could reuse.

Give the official current unit values the method needs (USDOT value of a statistical life and crash costs by
severity, value of travel time, EPA social cost of carbon, etc.) with their year. Say whether the benefit goes to
nearby homeowners, everyone, or the public budget. A method-only answer (no numbers) is still useful; mark it so.

`partD_qol_valuation.csv` columns:
`item_id,item_name,method,benefit_unit,value_per_unit_usd,dollar_year,quantity_per_project,annual_benefit_usd_per_project,who_benefits,study_location,grade,CI_or_range,status,source_ids,notes`

`partD_unit_values.csv` columns:
`parameter,value,unit,dollar_year,publisher,status,source_ids,notes`

---

## Part E — Per-house analysis: what each owner can do

Goal: pick any house and see a ranked list of upgrades, each with cost, resale value added, savings, rebates,
property-tax effect, permit needs, and **whether this parcel qualifies** (lot size, zone, setbacks, fire zone,
historic district, existing ADU).

**E1. Upgrades.** Already researched (round 5), so only improve these if you find **LA-specific** resale
evidence or newer rebate status: detached ADU, garage-conversion ADU, JADU, prefab ADU, SB 9 lot split, solar,
home battery, heat-pump HVAC, heat-pump water heater, induction cooking, panel upgrade, Level 2 EV charger, attic
insulation, vinyl and wood windows, cool roof, turf replacement, laundry-to-landscape greywater, rain barrels,
smart irrigation, front-yard trees, seismic Brace + Bolt, soft-story retrofit, wildfire Zone 0 hardening,
kitchen and bath remodels, garage door, entry door, stone veneer, fiber-cement siding, wood deck, home office,
accessibility, smart home, fiber hookup, Mills Act, PACE.

**Research these new ones:** exterior repainting, interior repainting, curb-appeal landscaping (front yard,
lighting, walkway), professional landscaping vs drought-tolerant, hardscape/patio and outdoor kitchen, fencing
and gates, driveway replacement or permeable driveway, pool addition and pool removal, adding a bedroom, adding
a bathroom, room addition ($ per sq ft added in LA), second-story addition, garage to living space without ADU
status, roof replacement, new flooring, refinishing hardwood, lighting upgrades, whole-house repiping, sewer lateral
replacement, foundation repair, mold/termite remediation, staging before sale, home energy score/certifications,
backup generator, water softener/filtration, security systems, permitting unpermitted work, and any other upgrade
with LA evidence.

For every upgrade: LA cost (with price year), resale value added (LA/West region data preferred: Cost vs. Value
report Los Angeles figures, NAR/NARI Remodeling Impact, peer-reviewed hedonic studies of LA sales; flag licensing
for any paid report), energy/water savings per year, rebates and tax credits **with their status in November
2026** (which federal credits expired, which state/utility programs are open, paused or out of funds: LADWP,
SoCalGas, SCE, TECH Clean California, HEEHRA/HOMES, Metropolitan Water District turf rebate, CalHFA ADU grant),
whether it triggers a property-tax reassessment (Prop 13 new-construction rules, the solar exclusion, the seismic
exclusion), permit needed and typical fee/time in LA City and unincorporated County, and the **parcel tests** that
decide eligibility (e.g. ADU: lot size, setbacks, fire zone, existing ADU count; pool: lot space; solar: roof
orientation/shade).

**E2. Parcel-level data to run those tests** county-wide, with endpoints: parcel polygons and Assessor attributes
(fields for units, beds, baths, sq ft, year built, pool, last sale), building footprints and heights, roof
area/orientation or solar potential (LA County Solar Map, NREL, Google Solar API: say what is free to use and
show), parcel slope, tree canopy by parcel, setback geometry (street frontage), existing ADU/permit records, LADWP
or SCE service type if public, recent sale prices by parcel (Assessor sales, other public sources) and any free
automated valuation or price index usable per house.

**E3. Square-foot and feature values from LA sales:** published estimates of what an extra bedroom, bathroom,
square foot, pool, garage, view, or lot square foot adds in LA County submarkets (hedonic studies, appraisal
guides), with location and year.

`partE_owner_upgrades.csv` columns (same as round 5, with three added at the end):
`id,name,category,typical_cost_LA,cost_dollar_year,resale_value_added,value_source,annual_savings,rebates_and_credits,property_tax_effect,permit_needed,payback_years,grade,sources,parcel_eligibility_tests,data_needed_per_parcel,status_nov_2026`

`partE_parcel_data.csv`: same columns as `partA_map_layers.csv`.

`partE_feature_values.csv` columns:
`feature,value_added,unit,submarket,study_period,method,grade,status,source_ids,notes`

---

## Part F — Open gaps from round 5 (do these if you have room)

1. **Corridor right-of-way layers** to site rail and creek trails: abandoned or inactive rail lines (Metro-owned
   rights-of-way with legal parcels), LADWP and SCE transmission corridors with widths, flood-control channels
   with maintenance roads (LA County Public Works), and existing and planned Class I bike paths county-wide.
   Endpoints, fields and 3 sample records each.
2. **FCC Broadband Data Collection** for LA County: the exact public download or API that gives availability by
   location or hexagon (technology, max speeds, provider), its file names for the latest vintage, whether an
   account/API token is needed, and how to aggregate to block groups. Also any LA County or City small-cell/5G
   permit data.
3. **LA costs still missing:** curb-separated bike lanes per mile, painted bus lanes per mile, speed-camera
   capital vs. operations, leading-pedestrian-interval retiming per intersection, school-street setup and yearly
   cost, murals per sq ft (LA DCA), a fully loaded tiny forest per 0.1 acre, fiber cost per home passed, power-
   corridor trail per mile. Use LA staff reports, bid results and grant applications.

`partF_gaps.csv` columns:
`gap_id,item,answer,value,unit,dollar_year,endpoint_url,key_fields,sample_records,status,source_ids,notes`

---

## Part G — Your recommendations

`partG_ranked.csv`: the **25 highest-value additions** to City Pretty from everything above, ranked by usefulness
to someone deciding what to build or buy, with columns:
`rank,addition,part,why_it_matters,data_ready_now (yes/partly/no),blocking_gap,effort (S/M/L),source_ids`

Finish with a short list of **anything that looks like it does not exist** (e.g. "no county-wide zoning layer"),
labeled as your inference, and anything **paid or restricted** I should not plan around.
