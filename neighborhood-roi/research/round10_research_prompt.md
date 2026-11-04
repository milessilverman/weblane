# City Pretty — Round 10 research request: what's really built, plain-language zoning, and who pays

You are helping build **City Pretty**, a public web map of Los Angeles County. For every neighborhood (Census block
group) it ranks improvements (street trees, bus lanes, parks, pools, clinics, EV chargers, housing on underused land…)
by value added per $1, and for a single house it shows what the owner could add. The goals this round:

1. **Stop showing land as "underused" when it has already been built on.** Today the map flags parcels as parking
   lots, vacant land or lightly built using the County Assessor's use code (`UseCode`; `…V` = vacant, parking-lot
   codes, golf). The Assessor's code often lags construction by years. Example: the map shows an 11-acre "Parking lot"
   at La Cienega Blvd and Jefferson Blvd (West Adams, City of LA, near the E Line La Cienega/Jefferson station), where
   we believe a large mixed-use apartment complex has since been completed. Some "vacant" parcels are also misplaced
   or wrong (hillsides, flood channels, road or utility strips, open space).
2. **Explain zoning codes in plain words** (what "R1V2", "RD1.5-1", "(T)(Q)C2-2D-CPIO", "R-3-P" or "A-1-10000" let
   you build) for the zoning layer.
3. **Show how each project gets paid for**: how much an **EIFD** (Enhanced Infrastructure Financing District) could
   raise for a specific project, what share the city and the County would put in, and which other measures (Measure
   M/R local return, SB 1, Measure W, Measure A parks, ULA, CFDs, BIDs, state and federal grants) can pay for which
   improvements, with real amounts.
4. **Load a single house faster**, by precomputing per-parcel facts in bulk instead of querying 15 live services
   when a home is clicked.

**How the data will be used** — report both for every source:
1. **In the browser, live, at click time.** The map is a single HTML file opened locally or from a static host.
   A source is only usable here if it answers anonymous cross-origin requests (CORS `Access-Control-Allow-Origin`,
   or JSONP via `callback=` for ArcGIS) without a key, or with a free key that may be embedded in a public page.
2. **In bulk, in GitHub Actions** (US datacenter IPs, no login, no browser, no CAPTCHA), to precompute values.

This prompt goes to several assistants. Do every part you can, in order; finish whole parts rather than skimming.

---

## Rules (strict: earlier answers failed these, and many of their links did not work)

- **Open every URL before listing it.** For ArcGIS layers open `<layer URL>?f=pjson` and report the real field names,
  geometry type and record count (`/query?where=1=1&returnCountOnly=true&f=json`). For Socrata give the 4x4 ID and
  `/resource/<id>.json`. For files give the direct download URL, type and size.
- Give **3 real sample records** copied from the response. Write `NR` when you couldn't get them.
  **Never invent URLs, field names, codes, counts, dollar amounts or sample values.**
- For every field that encodes a fact (use code, status, zone, permit type), give the **code table** and where it is
  published.
- Say whether each endpoint answers **cross-origin browser requests** and whether it needs a key.
- Every dollar figure needs a year, a source and whether it is annual, total, or per capita.
- License and reuse terms for every source; flag anything paid, non-commercial only, rate-limited or behind a login.
- Every row cites a `source_id` from `sources.csv` (`source_id,title,publisher,url,date_published,date_accessed,status,notes`).
- Return one CSV per part with exactly the listed columns (UTF-8, header row, every field quoted), or each CSV in its
  own fenced code block labeled with its filename.

---

## Part S — What's actually on the land now

S1. **Recently completed buildings.** Datasets that show a parcel was built on after the Assessor's use code was set,
with the join key (AIN/APN, address or geometry) and completion date:
- LADBS **Certificates of Occupancy** (Socrata ID?), LADBS permits with status "CofO Issued" / "Permit Finaled",
  and the County EPIC-LA permit finals;
- HCD Annual Progress Report **completions** (entitled/permitted/completed by APN), LA City Housing Progress dashboards;
- **dated building footprints**: LARIAC buildings (public vintage?), Microsoft Global ML Building Footprints (capture
  dates per tile), Google Open Buildings, Overture Maps buildings (source and update date), OSM `start_date`;
- the Assessor fields that change when a building is added (`Roll_ImpValue` jump, `YearBuilt1`, `Units1`, `SQFTmain1`)
  and how fast the roll catches up after a certificate of occupancy;
- any **commercial or public lists of large projects completed since 2018** (Urbanize LA, The Real Deal, LA
  Business Journal, Metro joint development) that can be matched to parcels.

S2. **A test set.** List at least **30 real LA County sites** that were parking lots, vacant land or lightly built
commercial lots **and have been redeveloped since 2016** (completed or under construction), with address, AIN if
findable, project name, units or floor area, completion year and a source. Start with the La Cienega/Jefferson site
above (confirm its name, AIN(s), units and completion date). Also list **10 sites that are genuinely still underused**
(surface lots, vacant parcels) so we can test both ways.

S3. **Why "vacant" parcels are wrong or misplaced.** The Assessor use-code table for vacant land (every code ending
in `V`, plus `…X` or other codes for unbuildable/miscellaneous land), and which ones are really roads, alleys, flood
control channels, utility corridors, railroad right-of-way, hillside open space, common areas of condo/HOA tracts,
or landlocked slivers. Layers that rule these out, with endpoints and fields: LA County Flood Control District parcels,
Caltrans/Metro right-of-way, SCE/LADWP transmission corridors, CPAD and conservation easements, public ownership
(County, City of LA, LAUSD surplus), slope above 25–30%, and the Assessor's own "parcel type" or tax-status fields.
Also: are parcel geometries in the County layer known to be offset from imagery anywhere, and by how much?

S4. **Parking lots that are not available**: parking required for an existing building next door (shared AIN
groups), park-and-ride lots, hospital/campus parking structures recorded as lots, church lots. Any data that marks these.

`partS_land_truth.csv` columns:
`source_key,question (completed/test_site/vacant_code/exclusion/parking_use),dataset_or_site,publisher,endpoint_url_or_address,ain,format,fields,date_field,coverage,vintage,record_count,cors_or_jsonp,key_needed,license,sample_records,status,source_ids,notes`

`partS_use_codes.csv` (one row per code): `field,code,meaning,buildable (yes/no/depends),source_ids,notes`

---

## Part T — Zoning in plain words

T1. **City of Los Angeles** (Chapter 1 and the new Chapter 1A code): every base zone (OS, A1, A2, RE40…RE9, RS, R1,
R1 variation zones R1V/R1F/R1R/R1H, RD6…RD1.5, RW, R2, R3, RAS3, R4, RAS4, R5, CR, C1, C1.5, C2, C4, C5, CM, MR1, M1,
MR2, M2, M3, P, PB, PF, SL, HJ/HR/NI, and the Chapter 1A form/use districts), the height districts (1, 1L, 1VL,
1XL, 1SS, 2, 3, 4, D limits), and prefixes/suffixes ([Q], (T), D, -CPIO, -HPOZ, -O, -RIO, -CUGU, -SN, -K, -POD,
-CDO, -HS, -MU, etc.). For each: one plain sentence (what you can build), max height, max FAR or units per lot area,
parking, and whether ADUs and SB 9 apply.

T2. **Unincorporated County (Title 22)**: R-1, R-2, R-3, R-4, R-5, R-A, A-1, A-2, C-1…C-3, C-M, C-R, M-1, M-1.5,
M-2, MXD, IT, O-S, W, the `-number` minimum lot size suffix, `-P` (parking), `-DP`, and the community standards
districts (CSDs). Same fields.

T3. The **10 largest other cities** (Long Beach, Glendale, Santa Clarita, Lancaster, Palmdale, Pomona, Torrance,
Pasadena, El Monte, Downey) plus Santa Monica, Burbank and Inglewood: a link to each zoning code's district table,
the zone field in their GIS layer, and plain-language rows for their residential and mixed-use zones.

T4. Any **existing plain-language zoning guide** (LA City Planning "Zoning Summary" sheet, ZIMAS help, County DRP
zone guide, Zoning Atlas / National Zoning Atlas California data) that we may quote or link, with license.

`partT_zoning_plain.csv` columns:
`jurisdiction,code,code_type (base/height/prefix/suffix/overlay),plain_meaning,typical_uses,max_height_ft,max_far_or_density,min_lot_sqft,parking,adu_sb9,source_url,source_ids,notes`

---

## Part U — Who pays: EIFDs, local measures and grants for each kind of project

U1. **Every EIFD, CRIA and IFD formed or proposed in LA County** (for example the County's West Carson EIFD, La Verne,
Palmdale, the City of LA's San Pedro / Port and any others): formation date, area (and a boundary layer or map if
public), participating agencies and the **share of each agency's property-tax increment** they pledged (e.g. "City
100% of its share, County 50% for 45 years"), base-year assessed value, projected total increment, bonds issued,
the projects funded, and the Infrastructure Financing Plan PDF.

U2. **The County's EIFD policy**: how the Board of Supervisors decides to participate, the maximum share it pledges,
required "net fiscal benefit" tests, the County's typical match, and formation cost and time. Same for the City of LA
(its EIFD policy or CAO reports).

U3. **The arithmetic an EIFD calculator needs**, with sources:
- each agency's share of the 1% property tax by Tax Rate Area (we have TRA allocation factors from an earlier round;
  confirm the current published table and its URL);
- the effect of ERAF and VLF swap shares (can an EIFD receive the property-tax-in-lieu-of-VLF?);
- typical assessed-value growth in LA County (annual roll growth by city, 2015–2026; Prop 13 2% cap; resale and
  new-construction reassessment rates);
- bond terms: debt-service coverage ratio, interest rates on recent EIFD/tax-allocation bonds, term, issuance cost;
- the 55% voter rule for EIFD bonds and the Public Financing Authority steps.

U4. **Other money a city puts into neighborhood projects**, with the **amount per city per year** where published:
- Metro **local return** (Prop A 25%, Prop C 20%, Measure R 15%, Measure M 17%) allocations by city and what each
  can and can't fund;
- **SB 1** RMRA and HUTA gas tax by city (State Controller);
- **Measure W** (Safe Clean Water) municipal program by city, and its regional program project awards;
- **Measure A (2016 parks)** by study area/city (RPOSD), and state **Prop 68 / Prop 4 (2024)** park and climate funds;
- City of LA **Measure ULA**, Measure HHH, the General Fund capital program, Council District discretionary funds,
  Quimby/park fees, and development impact fees per new home; the County's Measure A (2024 homelessness) and
  Measure J;
- **assessment and special-tax districts**: Mello-Roos CFDs, Landscape and Lighting districts, BIDs/PBIDs (with
  annual budgets), and street-tree or sidewalk assessment programs;
- **state and federal grants** by project type: ATP, AHSC, IIG, TIRCP, HSIP, Urban Greening, Clean California,
  CalFire urban forestry, Safe Streets for All, RAISE, CDBG, EV charger programs (NEVI, CALeVIP), FQHC clinic capital;
  typical award size, local match, and who has won in LA County recently.

U5. **Real funding stacks.** For **12 completed or under-way LA County projects** that match our improvement types
(a bus-lane corridor, a protected bike lane, a street-tree program, a park, a public pool, a community clinic,
an EV fast-charging hub, a library, a road diet, a rail station area, a river path, affordable housing on a public
parking lot): total cost and each funding source with its dollar amount and share, from a staff report or budget.

`partU_funding.csv` columns:
`source_key,mechanism (eifd/cria/local_return/sb1/measure_w/parks_measure/ula/general_fund/impact_fee/cfd/bid/grant/other),name,agency,jurisdiction,eligible_project_types,amount,amount_unit (annual/total/per_capita/per_unit),year,share_or_match,term_years,decision_maker,how_a_project_qualifies,data_url,source_ids,notes`

`partU_eifds.csv` columns:
`eifd_name,jurisdiction,formed,status,boundary_url,participants_and_shares,base_year,base_av,projected_increment_total,bonds_issued,projects,ifp_pdf_url,source_ids,notes`

`partU_project_stacks.csv` columns:
`project,improvement_type,city,status,total_cost,funding_source,amount,share,year,source_ids,notes`

---

## Part V — Faster house data

V1. **Bulk files we can precompute from** in GitHub Actions, with direct download URLs, size, format, update cycle
and license: the County Assessor parcel/roll data (all fields for all ~2.4M parcels; e.g. "Assessor Parcels Data"
on the County open-data portal), LADBS permits bulk exports, PAIS sales, CAMS address points, County building
outlines, historic/hillside/fire/geologic layers as downloads.

V2. **Fast public endpoints**: for the services below, measure response time for a single point query from a browser
(or note what you observed), and name any faster mirror (Esri-hosted FeatureServer copies, vector-tile or PMTiles
versions, county "cache" services):
`public.gis.lacounty.gov/.../LACounty_Parcel/MapServer/0`, `overpass-api.de`, `data.lacity.org` (pi9x-tg5x,
d9aa-v8bm), `egispais.gis.lacounty.gov/.../pais_sales_parcels`, `services5.arcgis.com/7nsPwEMP38bSkCjy` (HPOZ, HCM),
`rpgis.isd.lacounty.gov/.../GISNET_Public/MapServer/331`, `maps.lacity.org/lahub/.../Special_Areas/MapServer/6`,
`services2.arcgis.com/zr3KAIbsRSUyARHG` (CGS zones), `services1.arcgis.com/jUJYIo9tSA7EHvfZ` (CAL FIRE).

V3. **Static hosting limits**: GitHub Pages / Cloudflare Pages / Netlify free-tier size and file-count limits for
serving per-parcel JSON shards or a PMTiles file (~2.4M parcels), and whether HTTP range requests work there.

`partV_speed.csv` columns:
`source_key,dataset,publisher,bulk_url_or_endpoint,format,size,update_cycle,median_ms,cors_or_jsonp,key_needed,license,status,source_ids,notes`

---

## Part W — Your recommendations

`partW_ranked.csv`: the 12 most useful additions from Parts S–V, ranked, with
`rank,addition,part,why_it_matters,data_ready_now (yes/partly/no),blocking_gap,effort (S/M/L),source_ids`.
End with anything that appears not to exist or is paid/restricted, labeled as inference.
