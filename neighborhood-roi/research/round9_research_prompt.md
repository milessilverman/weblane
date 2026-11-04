# City Pretty — Round 9 research request: house-level data (LA County)

You are helping build **City Pretty**, a public web map of Los Angeles County. A user can zoom to street level and
click a single home; the page then looks up that parcel and shows what the owner could add (ADU, second story,
pool, rooftop deck, garden, solar…) with cost, value added and value per $1. The analysis is only as good as the
facts about that one house, and today several are guessed (for example, whether the house has one or two stories,
its footprint, its yard, whether it already has a pool or an ADU).

This round finds **accurate, public, house-level data** for every parcel in LA County, and the map layers that let a
user tell which house is which (address labels, parcel lines, building outlines).

**How the data will be used** — two ways, so report both for every source:
1. **In the browser, live, at click time.** The map is a single HTML file opened locally or from a static host. It
   calls public APIs directly from the page (`fetch`, or JSONP via `callback=` for ArcGIS). A source is only usable
   here if it answers anonymous cross-origin requests (CORS `Access-Control-Allow-Origin`, or JSONP) without a key
   or with a free key that may be embedded in a public page.
2. **In bulk, in GitHub Actions** (US datacenter IPs, no login, no browser, no CAPTCHA), to precompute per-parcel or
   per-area values.

This prompt goes to several assistants. Do every part you can, in order; finish whole parts rather than skimming.

---

## Rules (strict: earlier answers failed these, and many of their links did not work)

- **Open every URL before listing it.** For ArcGIS layers open `<layer URL>?f=pjson` and report the real field names,
  geometry type and record count (`/query?where=1=1&returnCountOnly=true&f=json`). For Socrata give the 4x4 ID and
  `/resource/<id>.json`. For files give the direct download URL, type and size.
- Give **3 real sample records** copied from the response, ideally for the **same three parcels** across sources
  (use AINs 4256012034, 2004005005 and 8735022018 if they exist; otherwise say which you used). Write `NR` when you
  couldn't get them. **Never invent URLs, field names, codes, counts or sample values.**
- For every field that encodes a fact (stories, design type, roof type, quality class, pool, use code), give the
  **code table** (what each code means) and where that table is published.
- Say whether each endpoint answers **cross-origin browser requests** (test with a CORS check or note the response
  headers; say whether `callback=` JSONP works), and whether it needs a key.
- License and reuse terms for every source; flag anything paid, "non-commercial only", rate-limited or requiring
  a login.
- Every row cites a `source_id` from `sources.csv` (`source_id,title,publisher,url,date_published,date_accessed,status,notes`).
- Return one CSV per part with exactly the listed columns (UTF-8, header row, every field quoted), or each CSV in its
  own fenced code block labeled with its filename.

---

## Part O — Building facts for each parcel

O1. **LA County Assessor building characteristics.** The parcel layer
`https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0` has DesignType1–5,
YearBuilt1–5, EffectiveYear1–5, Units1–5, Bedrooms1–5, Bathrooms1–5, SQFTmain1–5, QualityClass1–5. Find the
**published code tables** for DesignType and QualityClass (do they encode **number of stories**, construction class,
pool, view, condition?), and explain what the 1–5 slots mean (separate buildings on the lot?). Find any richer
Assessor table with **stories, pool, garage/parking spaces, fireplace, roof, basement, A/C, lot frontage/depth** —
e.g. the Assessor's Property Information portal data, the "Assessor Parcels Data" tables on the County open-data
portal, or the secured-roll extract — with endpoints and field lists.

O2. **Building footprints and heights.** LARIAC (LA Region Imagery Acquisition Consortium) building outlines with
roof height / elevation from LiDAR (find the current public layer and its fields: height, ground elevation, roof
type?), Microsoft or Google open building footprints for LA County, OpenStreetMap buildings (`building:levels`,
`height`) coverage in LA. Which one lets us tell **one-story from two-story** reliably, and how (height threshold,
levels field)? Give coverage and vintage.

O3. **Roof type and shape** (flat vs. pitched, for rooftop decks and solar), **roof area and orientation**, and
**solar potential** per building: LA County Solar Map, NREL datasets, Google Solar API (terms and cost), any LiDAR
derived roof-plane data.

O4. **Pools, ADUs and other existing features**: datasets or methods that show whether a parcel already has a pool
(Assessor field? LARIAC imagery classification? OSM `leisure=swimming_pool`?), an ADU or second unit (Assessor Units,
permits), a garage (detached/attached), a deck.

O5. **Lot shape and buildable area**: lot frontage and depth, setbacks actually built, slope (USGS 3DEP or County
LiDAR DEM), and any public layer of "buildable area" or yard area per parcel.

`partO_building_data.csv` columns:
`source_key,fact (stories/footprint/height/roof/pool/garage/ADU/units/beds/baths/sqft/lot/slope/solar),dataset,publisher,endpoint_url,format,key_field_join (AIN/APN/geometry),fact_fields,code_table_url,coverage,vintage,record_count,cors_or_jsonp (yes/no/NR),key_needed,license,sample_records,status,source_ids,notes`

`partO_code_tables.csv` (one row per code value you can document):
`field,code,meaning,source_ids,notes`

---

## Part P — Permits, sales and restrictions for each parcel

P1. **Building permits by parcel**: LADBS (City of LA; Socrata `pi9x-tg5x` and any others) and the County's
EPIC-LA/Building and Safety permits, plus permit portals of Long Beach, Glendale, Pasadena, Santa Monica, Burbank,
Torrance and other large cities. The fields that show ADUs, additions, second stories, pools, solar, re-roofs, and
the join key to the parcel (APN/AIN or address). Can they be queried for one parcel from a browser?

P2. **Sales history by parcel**: last sale date and price (Assessor recent-sales layer, documentary transfer tax,
any public recorder index), with what is and isn't included.

P3. **Restrictions that decide what a house can build**: historic designation per parcel (LA HPOZs and Historic-
Cultural Monuments, County and other cities' historic districts, National Register), Very High Fire Hazard Severity
Zone (current CAL FIRE LRA/SRA maps), hillside areas (LA Hillside Ordinance), Baseline Mansionization / residential
floor-area limits (LA R1 variation zones), Coastal Zone, specific plans, liquefaction/landslide/fault zones, flood
zones, and utility/sewer easements. For each: endpoint, the field that flags it, and whether it can be checked for a
single point from a browser.

P4. **Zoning details per parcel**: LA City ZIMAS-equivalent data (height district, specific plan, overlays, Q/T/D
conditions) as a queryable layer; equivalent layers for the County (Title 22) and the largest cities.

`partP_parcel_rules.csv` columns:
`source_key,topic (permits/sales/historic/fire/hillside/floor_area/coastal/specific_plan/geohazard/flood/easement/zoning_detail),dataset,publisher,endpoint_url,format,flag_or_value_fields,join_key,coverage,vintage,cors_or_jsonp,key_needed,license,sample_records,status,source_ids,notes`

---

## Part Q — Telling houses apart on the map

Q1. **Address points** with house numbers and street names (LA County CAMS address points; City of LA address
layer; OSM addresses), so the map can label each house with its number at high zoom.
Q2. **Parcel outline tiles** or a fast parcel layer to draw lot lines at zoom 17–19 (LA County parcel map tile
service, vector tiles, or the MapServer export), with terms.
Q3. **Free imagery or basemaps** that show individual roofs at zoom 18–20 and may be shown on a public page
(NAIP via USGS, LARIAC orthoimagery public tiles, Esri World Imagery terms, others), with tile URLs and attribution.

`partQ_map_identity.csv` columns:
`source_key,purpose (address labels/parcel lines/imagery),dataset,publisher,endpoint_or_tile_url,format,fields,max_zoom,cors_or_jsonp,key_needed,license_and_attribution,sample_records,status,source_ids,notes`

---

## Part R — Your recommendations

`partR_ranked.csv`: the 12 most useful additions from Parts O–Q for an accurate one-house analysis, ranked, with
`rank,addition,part,why_it_matters,data_ready_now (yes/partly/no),blocking_gap,effort (S/M/L),source_ids`.
End with anything that appears not to exist or is paid/restricted, labeled as inference.
