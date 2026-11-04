# City Pretty — Round 8 research request (LA County)

You are helping build **City Pretty**, a public web map of all of Los Angeles County (6,591 Census block groups,
88 cities plus unincorporated areas). It ranks neighborhood improvements by home value added per $1, shows what
each neighborhood is missing, maps zoning, underused land and work already under way, and now lets a user click a
single home to see which upgrades pay off for that house. Data is pulled by Python in **GitHub Actions**
(US datacenter IPs, no login, no browser, no CAPTCHA).

This round has two goals:
1. **Home upgrades:** correct, LA-specific costs and resale values for every upgrade a homeowner might make,
   including large ones (second stories, additions) and "nice to have" ones (rooftop decks, gardens, outdoor
   living), so each house can be shown cost, value added, and **value added per $1**.
2. **Transit and bike recommendations on specific streets:** when City Pretty suggests a bike lane, bus lane, BRT,
   rail line or commuter-rail improvement, it must name the **street, corridor and segment**, and say whether the
   city, Metro or another agency **already plans** it (and at what stage).

This prompt goes to several assistants. Do every part you can, in order; finish whole parts rather than skimming.

---

## Rules (strict: earlier answers failed these and many of their links did not work)

- **Open every URL before listing it.** For ArcGIS layers open `<layer URL>?f=pjson` and report the real field names,
  geometry type, and record count (`/query?where=1=1&returnCountOnly=true&f=json`). For Socrata give the 4x4 ID and
  `/resource/<id>.json`. For files give the direct download URL, type and size.
- Give **3 real sample records** copied from the response, or write `NR`. **Never invent URLs, field names, counts,
  sample values or dollar figures.** Use `LISTED` when a page links to something you couldn't open, `NR` when you
  found nothing.
- Every dollar figure needs its **year**, **what it includes** (hard cost, design, engineering, permits, soft costs,
  contingency, temporary housing), the **geography** (LA County, City of LA, Westside, Valley…) and the **source
  document** (title and page). Prefer LA permit data, contractor bid data, appraisal studies, recorded-sale studies
  and government reports. National averages must be labeled as national.
- Give **low / typical / high** where costs vary, and say what drives the spread.
- Laws and incentives: citation, effective date and status **as of November 2026**. Note anything expired, paused or
  out of funds (the federal 25C and 25D home-energy credits ended for work after 2025).
- Every row cites a `source_id` from `sources.csv` (`source_id,title,publisher,url,date_published,date_accessed,status,notes`).
- Return one CSV per part with exactly the listed columns (UTF-8, header row, every field quoted), or each CSV in its
  own fenced code block labeled with its filename.

---

## Part L — Home upgrades: real LA costs, value added and eligibility

L1. **Large projects**: full second-story addition (whole floor, 800–1,500 sq ft), partial second story (one room or a
primary suite, 300–600 sq ft), ground-floor room addition, primary-suite addition, garage conversion to living
space, basement or under-house space, detached ADU (450 / 800 / 1,200 sq ft), attached ADU, garage-to-ADU, junior
ADU, prefab ADU, SB 9 lot split plus a second home, tear-down and rebuild. For second stories and additions, give
cost **per square foot and per project** in LA in 2025–2026, separating structural engineering, foundation/seismic
upgrades, roof, staircase, permits/plan check, design and temporary housing. Include the City of LA's and County's
height and Baseline Mansionization / hillside limits that commonly block second stories.

L2. **Outdoor living and "nice" upgrades**: rooftop deck (on a flat roof or a garage; structural and permit
requirements), balcony, ground-level deck, paver patio, covered patio or pergola, outdoor kitchen, fire pit,
hot tub or spa, pool and pool removal, sport court, play structure, outdoor lighting, privacy hedges and fencing,
artificial turf, drought-tolerant or native garden, vegetable garden and raised beds, fruit trees, front-yard
curb-appeal landscaping, shade trees.

L3. **Interior and systems**: kitchen remodel (minor / major / upscale), bathroom remodel and adding a bathroom,
adding a bedroom inside the existing house, home office, home gym, home theater, wine room, skylights, window and
door replacement, flooring, interior and exterior paint, roof replacement, siding, insulation, heat-pump HVAC and
water heater, electrical panel upgrade, EV charger, solar and battery (with no federal credit after 2025), smart
home and security, seismic bolting/bracing and soft-story retrofit, repiping, sewer lateral, foundation repair,
accessibility and aging-in-place work.

For every upgrade:
- LA cost (low / typical / high, per sq ft where it applies) and what drives the range;
- **resale value added in LA**: Cost vs. Value 2025/2026 Los Angeles recoup percentages (cite the figures you can
  read; don't copy the paid report), NAR/NARI Remodeling Impact, appraisal guides, and studies of LA recorded sales;
- extra rental income where it applies (ADUs, junior ADUs, room additions), with LA rent figures by size;
- yearly upkeep or savings; permit type and typical City of LA / County fee and approval time;
- property-tax effect under Prop 13 (what is and isn't reassessed; the solar and seismic exclusions);
- incentives open in November 2026 (LADWP, SCE, SoCalGas, TECH Clean California, MWD turf rebate, Brace + Bolt,
  CalHFA ADU program);
- the **parcel tests** that decide whether a given house can do it (lot size, yard depth, setbacks, height limit,
  roof type and slope, flat roof, fire zone, historic district, hillside, existing pool or ADU), and the public
  dataset that answers each test (with endpoint).

`partL_upgrades.csv` columns:
`upgrade_id,name,category,unit,cost_low,cost_typical,cost_high,cost_per_sqft_typical,dollar_year,cost_includes,cost_drivers,resale_value_added_typical,resale_recoup_pct,value_method,rent_added_per_month,annual_upkeep_or_savings,permit_type,permit_fee_and_time,prop13_effect,incentives_nov_2026,parcel_tests,data_for_parcel_tests,geography,status,source_ids,notes`

L4. **Per-house value**: public sources for a house-level value estimate without a paid API — recorded sale prices
by parcel (LA County Assessor sales, recorder data), sale price per square foot by ZIP or neighborhood, and the
marginal value of an extra bedroom, bathroom, square foot, pool, garage and view by LA submarket, with method and
year.

`partL_value_inputs.csv` columns:
`input_id,item,submarket,value,unit,period,method,endpoint_or_document,status,source_ids,notes`

---

## Part M — Bike, bus, rail and commuter-rail: specific streets, corridors and existing plans

M1. **Bike networks, existing and planned**, as data with geometry: City of LA Mobility Plan 2035 bicycle networks
(Bicycle Enhanced Network, Bicycle Lane Network, Neighborhood Enhanced Network) and its existing bikeway inventory;
LA County bikeway inventory and planned network (Step by Step / County bicycle master plan); Metro Active
Transportation Strategic Plan corridors; and the bike plans of Long Beach, Pasadena, Glendale, Santa Monica,
Burbank, Culver City, West Hollywood and other large cities. For each: endpoint, the fields for **street name,
segment limits, facility class (I–IV), status (existing / planned / funded / under construction) and plan name**.

M2. **Bus priority**: Metro's planned and funded bus-lane and bus-priority corridors (Bus Priority / Better Bus
program, NextGen Tier 1 "Tier 1 frequent" corridors), LADOT and city bus-lane plans, existing bus lanes outside the
City of LA; with street, segment limits, status and schedule. Also **stop-level ridership and bus speed / delay by
segment** if published, so the busiest slow corridors can be named.

M3. **Rail, BRT and commuter rail**: alignment geometry and stations for every Measure M / Long Range Transportation
Plan project (planned, in environmental review, funded, under construction), with mode, corridor name, streets
followed, status and opening year; Metrolink SCORE projects (double track, new stations, service frequency); High
Desert / Palmdale–Burbank high-speed rail segments; corridors studied but not funded. Prefer GIS layers; if only PDFs
exist, give the document and page with the route description.

M4. **Safety and street data that justify a specific street**: City of LA Vision Zero High Injury Network, County
and other cities' high-injury networks, traffic volume counts (ADT), street right-of-way and curb-to-curb widths,
number of lanes, speed limits, and Measure HLA (City of LA, 2024) implementation and compliance status. Endpoints and
fields for each.

M5. **What the law and plans require**: Measure HLA's requirement to build Mobility Plan improvements when streets
are repaved (status, lawsuits, current compliance), Complete Streets rules, and any 2025–2026 changes to Metro's
plan or funding that cancelled or delayed corridors.

`partM_corridor_sources.csv` columns:
`source_key,topic,dataset_or_document,publisher,endpoint_url,geometry,street_field,segment_limits_fields,class_or_mode_field,status_field,plan_or_program_field,schedule_field,record_count,update_date,license,sample_records,status,source_ids,notes`

`partM_named_corridors.csv` (corridors the plans name; one row per corridor or segment you can document):
`corridor_id,mode (bike/bus lane/BRT/light rail/heavy rail/commuter rail),corridor_name,streets,from,to,cities,agency,plan_name,status (existing/planned/environmental/funded/construction/cancelled),opening_year,budget,dollar_year,ridership_or_demand,why_this_corridor,status_check,source_ids,notes`

---

## Part N — Your recommendations

`partN_ranked.csv`: the 12 most useful additions from Parts L and M, ranked, with
`rank,addition,part,why_it_matters,data_ready_now (yes/partly/no),blocking_gap,effort (S/M/L),source_ids`.
End with anything that appears not to exist or is paid/restricted, labeled as inference.
