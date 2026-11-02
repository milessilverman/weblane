# City Pretty — Round 7 research request (LA County)

You are helping build **City Pretty**, a public web map of all of Los Angeles County (6,591 Census block groups,
88 cities plus unincorporated areas). It ranks neighborhood improvements by home value added per $1, shows what
each neighborhood is missing compared with similar ones, maps zoning, and now maps **underused land** (parking
lots, golf courses, vacant parcels, lightly built commercial lots) with its assessed land value and what zoning
allows. Data is pulled by Python in **GitHub Actions** (US datacenter IPs, no login, no browser, no CAPTCHA).

This round has three goals:
1. **What is already being done:** every funded or planned public project and large private development, so the
   map doesn't recommend something already underway and can show where value is about to rise.
2. **Profitability:** the inputs to estimate which neighborhoods and which underused sites are most profitable to
   improve or develop (market land prices, construction costs, rents, sale prices, appreciation).
3. **Underused-land reality checks:** ownership, restrictions and policy for parking lots, golf courses and
   publicly owned land.

This prompt goes to several assistants. Do every part you can, in order; finish whole parts rather than skimming.

---

## Rules (strict — a previous answer failed these and most of its links did not work)

- **Open every URL before listing it.** For ArcGIS layers open `<layer URL>?f=pjson` and report real field names,
  geometry type, and record count (`/query?where=1=1&returnCountOnly=true&f=json`). For Socrata give the 4x4 ID and
  `/resource/<id>.json`. For files give the direct download URL, type and size.
- Give **3 real sample records** copied from the response, or write `NR`. **Never invent sample values, field names,
  counts or URLs.** If you cannot open something, say `LISTED` (a page links to it) or `NR` (not recovered).
- A dollar figure needs its **year**, **what it includes**, and the **document** it comes from (title, page). Prefer
  LA staff reports, adopted budgets, bid results and peer-reviewed studies. National averages must be labeled.
- Laws and programs: citation, effective date, and status **as of November 2026**. Note anything expired, paused
  or out of funds (for example, federal 25C/25D home-energy credits ended for work after 2025).
- Every row cites a `source_id` from `sources.csv` (`source_id,title,publisher,url,date_published,date_accessed,status,notes`).
- Return one CSV per part with exactly the listed columns (UTF-8, header row, every field quoted), or each CSV in
  its own fenced code block labeled with its filename.

---

## Part H — Projects already funded, planned or under construction

For each source give the endpoint, fields that hold **location** (geometry or address), **status** (planned /
funded / under construction / complete), **budget**, **schedule (opening year)** and **project type**.

H1. **Transit:** LA Metro capital projects — rail lines and stations under construction or funded (D Line extension,
Southeast Gateway Line, East San Fernando Valley Line, K Line northern extension, Foothill Gold Line, Sepulveda
Transit Corridor, NoHo–Pasadena BRT, Vermont BRT and others), with station locations and opening years; Metro
Joint Development sites; Measure M project list with schedules; Metro bus priority lane program.
H2. **City and County capital programs:** LA City Capital Improvement Program, StreetsLA / LADOT project lists
(Vision Zero, Great Streets, bike network), LA County Public Works projects, Caltrans District 7 projects;
Long Beach, Pasadena, Glendale and Santa Monica CIPs if published as data.
H3. **Parks and water:** Measure A (RPOSD) grant awards with locations; Safe Clean Water Program (Measure W) projects
with locations, budgets and status; LA River master plan projects; Prop 4 (2024) awards in LA County.
H4. **Schools:** LAUSD Measure US/RR bond project list with campus locations and budgets; other districts' bond lists.
H5. **Housing and private development:** LA City Planning case filings (Socrata) for large projects; LAHD affordable
housing pipeline; ED 1 / CHIP / SB 35 / AB 2011 project filings; **state Housing Element site inventories** (HCD's
statewide site inventory dataset — parcels each city identified as able to hold housing, with assumed units);
County EPIC-LA permits; building-permit feeds for new construction in the largest cities.
H6. **Official SB 79 transit stops and tiers** (SCAG or Caltrans) as a downloadable layer.

`partH_projects.csv` columns:
`source_id_key,program,publisher,endpoint_url,format,geometry_or_address_field,status_field,budget_field,schedule_field,type_field,record_count,update_date,license,sample_records,status,source_ids,notes`

---

## Part I — Profitability inputs

I1. **Market land value**, not Prop 13 assessed value: recent land sale prices per square foot by submarket or zip
(residential lots, commercial lots, entitled multifamily land), and any public dataset of recorded sale prices
(LA County Assessor sales, Recorder documentary transfer tax). Also the typical ratio of market to assessed land
value by how long ago the parcel last sold.
I2. **Construction cost** per unit and per square foot in LA County, 2025–2026: single-family infill, ADU,
townhome, 5-over-1 mid-rise, high-rise, 100% affordable (with soft costs and land listed separately).
Sources: Terner Center, LAHD/HCD cost reports, Census/RS Means summaries, developer pro formas in staff reports.
I3. **Rents and sale prices** for new units by submarket (studio/1BR/2BR rents, new-condo $/sq ft), and
**capitalization rates** for LA multifamily and retail.
I4. **Home price appreciation** by zip or tract: public indexes usable without a login (FHFA HPI, Zillow ZHVI CSVs),
their URLs, update cadence and license; any published forecast.
I5. **Value effect of new transit and rezoning on nearby land**: studies of land/home price changes near new LA
rail stations (Expo, Crenshaw/K, Regional Connector) and after upzoning (TOC, SB 79-style), with effect sizes.
I6. **Linkage fees, impact fees, Measure ULA transfer tax** thresholds and amounts that change development
profitability in LA City and the largest cities (November 2026 status).

`partI_profit_inputs.csv` columns:
`input_id,topic,submarket_or_geography,value,unit,dollar_year,what_it_includes,method,endpoint_or_document,status,source_ids,notes`

---

## Part J — Underused land: what can really happen on it

J1. **Golf courses in LA County:** each course's owner (city, county, private), acreage, lease or deed
restrictions, and any proposals to convert part to housing or public park (with dates and outcomes).
J2. **Parking:** LA City (LADOT) and County public parking lot inventories with locations; Metro park-and-ride
lots; state law on building housing on parking lots (AB 2011, SB 6, AB 2097, AB 1486 Surplus Land Act) and
church/faith-land housing (SB 4).
J3. **Public land:** surplus public land inventories (state Surplus Land Act / HCD, LA City and County surplus
property lists, LAUSD surplus sites, Caltrans excess land) with endpoints.
J4. **Vacant land restrictions:** datasets marking parcels that cannot be built on (conservation easements,
landslide, fault, flood, very high fire, steep slope, utility easements).
J5. **Typical outcomes:** documented LA examples of parking-lot, mall and golf-course redevelopment with units
built, land price paid, and timeline.

`partJ_underused.csv` columns:
`item_id,topic,name_or_dataset,location_or_endpoint,owner,acres,restrictions,proposal_or_outcome,units,dollar_figure,dollar_year,status,source_ids,notes`

---

## Part K — Your recommendations

`partK_ranked.csv`: the 15 most useful additions from Parts H–J, ranked, with
`rank,addition,part,why_it_matters,data_ready_now (yes/partly/no),blocking_gap,effort (S/M/L),source_ids`.
End with anything that appears not to exist or is paid/restricted, labeled as inference.
