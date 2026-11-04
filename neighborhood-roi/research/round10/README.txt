CITY PRETTY — ROUND 10 RESEARCH PACK
Research accessed November 3–4, 2026. This is a partial, source-auditable research catalog, not a production-qualified data feed or a complete parcel entitlement calculator.

FILES
sources.csv — source registry, retrieval status and date.
partS_land_truth.csv — completion/exclusion sources and dated redevelopment test candidates.
partS_use_codes.csv — documented use-code meanings; patterns and full codes are distinguished in the field/code cells.
partT_zoning_plain.csv — plain-language district/qualifier interpretations and numeric limits where recovered.
partU_funding.csv — funding mechanisms, city annual amounts, current program status and examples.
partU_eifds.csv — formed/proposed/expired financing districts, with related disaster districts labeled separately.
partU_project_stacks.csv — 12 project examples, one row per source of funds or explicitly unrecovered funding bucket.
partV_speed.csv — bulk/live candidates, observed retrieval limits and current hosting limits.
partW_ranked.csv — 12 prioritized additions.
validation.json — structural, source-reference and funding-scope arithmetic checks. These checks do not certify the underlying data or legal interpretation.

CSV CONVENTIONS
All CSV fields, including headers, are quoted. Encoding is UTF-8 without BOM; line endings are CRLF. Import AINs, codes, years and dollar fields as TEXT to preserve leading zeros and qualifications. Semicolons separate source IDs. Every data row cites sources.csv. No empty cell means zero: NR means not recovered. Values with units, years and qualifications are intentionally not bare numeric modeling inputs.

OPEN means the cited page/metadata/document was retrieved, not that every linked endpoint works. PARTIAL means only part of the primary evidence, or its official indexed excerpt, was recovered. LISTED means a retrieved page links the target, but the target contents were not recovered. NR means not recovered. Data-row status labels such as UNDER_CONSTRUCTION_AT_SOURCE are research classifications, not invented native status codes.

Three sample records are selected-field projections copied from actual responses where supplied; otherwise NR. Individual project articles are evidence for one site, not three API records. Source descriptions, class legends, forecasts and example calculations are not substituted for feature records. Native field names and aliases are not interchangeable.

MAIN FINDINGS
Cumulus/VOX at La Cienega and Jefferson is a real stale-use-code test: the architect reports VOX completed in 2023 with 910 units; the engineer describes 1,210 units across the wider district. The historical parent AINs recovered are 4205033007 and 4205033015. Adjacent City corridor AIN4205035900 is an easement issue, not the residential development. Current child/airspace AINs remain NR. See S010, sources R10_012–R10_014.

The Assessor roll table exposes UseCodeDescChar1–4 alongside UseCode, plus AIN, RollYear, Roll_ImpValue, Units and SQFTmain. These fields can explain a classification and support annual change detection. They do not prove completion, surplus availability or buildability. The table has 51 documented native fields in V002. The linked roll archive expressly ends in 2025 despite the catalog's present-tense title. See S066 and V001–V002.

AB116 removed the old 55% EIFD bond-election rule effective January1,2020. District formation, agency pledge approvals and PFA procedures still apply; a CFD special tax is a different mechanism. County pledges vary by district: the Artesia final2026 IFP has City75% of its ordinary/VLF-equivalent increment and County49% of its share. Those percentages are not shares of the entire1% property levy. See U001–U002 and Artesia district row, R10_112/R10_114/R10_133.

The 2023 LARIAC outline metadata is publicly readable, but iteminfo expressly says LARIAC Members Only. Public REST visibility is not permission to redistribute geometry. Capture was January–June2023, exported January2025; neither is a completion date. See S060/V023 and R10_068/R10_218. V row numbers may be read using source_key, not physical spreadsheet line number.

CURRENT ACCESS LIMITS
Every listed source URL was opened or attempted. Where contents could not be recovered, the source/row status and notes preserve that failure. For ArcGIS layers, metadata and exact returnCountOnly query paths were attempted; unavailable counts are NR, never maxRecordCount or a rounded publisher description. Several hosted services failed while other County metadata pages opened. This does not establish that those servers are offline.

Endpoint-specific Access-Control-Allow-Origin headers, JSONP execution, browser single-point medians and HTTP Range206 responses were not recovered. All median_ms values are NR. No endpoint is represented as browser-qualified. GitHub Actions complete downloads were not executed in an unrestricted external-network runner. A page fetched by the research service is not a GitHub Actions test. Free-key/browser policy is NR where it was not established.

Public reference PDFs/HTML can support curated facts and offline extraction, but their existence does not give a browser a parcel query API. File bytes are reported where the publisher/fetcher exposed them; otherwise size is NR. Many direct archives remain LISTED or NR. No complete LA County bulk extract was downloaded and parsed during this research.

For local file:// use, qualify the actual browser's Origin:null behavior in addition to a hosted origin. For hosted precompute output, use same-origin requests or explicit CORS; PMTiles also needs Range support. Current free-plan limits are documented in V, not measured deployments. GitHub Pages has a 1GB published-site cap; Cloudflare Pages has20000files/site and25MiB/asset on Free. Netlify's current300credit Free plan is not the old100GB free-bandwidth offer. See R10_227–R10_232. Actual compact shard/archive sizes remain NR.

WHAT REMAINS INCOMPLETE
S: 31 positive redevelopment candidates and10 negative candidates are included. Several positives have only a dated under-construction observation, not a verified current completion; 6401Wilshire lacks an exact original completion year. The motel case is parking converted to pool/courtyard, not added housing. All10 negatives are explicitly UNDERUSED_AT_SOURCE_NOT_CURRENTLY_CERTIFIED. They do not satisfy a claim of10 independently verified still-underused sites as of November4. Current imagery/permit/title review is still required. Complete County EPIC finals, measured Assessor lag after CofO, every possible V/X code combination, a complete utility/rail/HOA/shared-parking restriction inventory and quantified parcel-imagery offsets were not recovered.

T: 240 interpretation rows are included, but this is not the requested exhaustive current numeric entitlement table. The2020 LA summary is explicitly a historical reference. Current R1 tables and selected other current provisions are distinguished. Full Chapter1A form/use district enumeration and all current numeric limits, parking/ADU/SB9 conditions for the13othercities remain incomplete. Some city code pages were blocked or only partly recovered. Keep jurisdiction, ordinance/version, specific plan, full zone string and project type together; do not calculate parcel capacity from a base-zone label alone. A zoning overlay or hazard is not automatically a no-build designation.

U: 19 formed/proposed/expired or related districts are tracked, not an exhaustive certified register of every EIFD/CRIA/IFD. Exact PFA actions, executed shares, base AVs and current bonds are still missing for some districts. The full currently signed County policy and adopted LA City policy were not recovered; the2026 Artesia Board letter is current operational evidence and the2025 redline is labeled proposed. The2015–2026 city roll-growth panel, reassessment-event rates and recent issue-specific coverage/rates/costs remain NR. Current TRA ZIPs are listed but not parsed. Do not use Prop13's2% cap as an aggregate city growth forecast, pledge school/ERAF amounts automatically, or add bond proceeds to the present value of the same pledged tax stream.

U4: FY2026-27 Metro city local-return estimates, projected MeasureW municipal amounts and separate prior-year actual returns are reported. RPOSD study areas can cross city boundaries; balances are not annual allocations. Some grants are closed; HSIP Cycle13's explicit November2deadline has passed despite its stale active banner. NEVI GFO25-603 has a November20,2026 deadline at this cutoff. SB1/HUTA city dollar workbooks, regional SCW award data, adopted ULA/HHH availability, comprehensive impact-fee schedules and assessment/BID annual budgets remain incomplete. A grant program description is not an award, and a statutory allocation balance is not an open call.

U5: 12 project examples occupy31funding rows. The10 numeric stacks reconcile to their explicitly stated scope, not necessarily full final project cost. Flower Street and the Venice road diet have unrecovered total/splits. Houghton Park groups other financing sources; the full sub-breakdown is NR. Pomona clinic renovation has an approved2021budget but independently verified completion/current construction is NR. Taylor Yard is a revised MOU construction package, not full inception-to-closeout cost. Arroyo is the City's net capital scope and excludes Tesla equipment; one source amount is an expressly derived residual. Carson's actual total cost differs from its budget; actual spending by fund is NR. Pasadena library's CIP MeasurePL line differs from bond par authorization and is not silently explained away. Hollywood Arts Collective is residential CONSTRUCTION financing; neither permanent financing nor its separate arts building is added. Consequently this is not a claim of12 fully recovered final funding ledgers.

V: Bulk sizes, counts, native feature samples and browser/runner performance remain NR for many candidates. Hosted HPOZ/HCM/CGS/zoning endpoints that failed in this round are labeled NR; no schema was invented from their names. No faster mirror is claimed merely because its hostname contains cache. Building appearance/edit dates and release dates are not construction dates. A current footprint may also predate wildfire loss or demolition.

INFERENCE — NOT PROOF OF NONEXISTENCE
A single complete, free, anonymous Countywide feed joining completion, current child AIN, current building footprint and legal buildability was not identified. Countywide title/deed/easement/shared-parking obligations and every parcel's Q/T/D ordinance conditions appear to require multiple records and manual or project-specific checks. This is an inference from the sources recovered, not proof no agency has them.

Unrestricted LARIAC redistribution is not established and the2023 layer has an explicit member-only restriction. National Zoning Atlas material recovered points to licensed data access rather than an unrestricted public entitlement dataset. Commercial real-estate project coverage may be paid/copyrighted and does not establish automated scraping rights. OSM/Overture carry attribution/database-license obligations. None should be treated as unrestricted public-domain data merely because a page can be read.
