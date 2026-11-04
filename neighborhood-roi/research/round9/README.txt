City Pretty — Round 9: house-level LA County data
Research accessed 2026-11-04 UTC. This is a partial, qualified source catalog, not a claim that every integration works.

DELIVERABLES
Six UTF-8 CSVs use the exact requested column names and quote every field:
  partO_building_data.csv — 25 building-data sources, methods and explicit gaps
  partO_code_tables.csv — 76 code/value entries (including explicit unrecovered definitions)
  partP_parcel_rules.csv — 38 permit, sales, restriction and zoning entries
  partQ_map_identity.csv — 12 address, parcel and imagery entries
  partR_ranked.csv — 12 ranked additions
  sources.csv — 105 source records

HOW TO READ THE EVIDENCE
OPEN means the research fetcher returned readable content. It does not prove an upstream live HTTP request, a browser CORS grant, a license to republish, or successful GitHub Actions execution. Some retrieved content was cached/indexed by the research service. Use row vintage and status, not access date, as the data date.
METADATA_ONLY means schema/capabilities were recovered, but record retrieval was not established. PARTIAL means some content was recovered, often a service directory or official indexed text. LISTED means a publisher/configuration/catalog linked a resource whose data bytes were not recovered. NR means not recovered. NR never means zero, absent, safe, unregulated, or nonexistent.

All listed source URLs were opened or opening was attempted. Dynamic ArcGIS count requests were attempted, but no exact ArcGIS count response was recovered. Page limits such as 1,000/2,000/16,000 were not reported as total counts. Approximate publisher counts are labeled separately. File sizes that could not be recovered remain NR; a ZIP link alone is not a successful download.

No endpoint-specific upstream CORS headers were available. A direct Origin-header request from this research environment was rejected by the environment's network gateway, not by an identified County CORS policy. ArcGIS callback and Socrata $jsonp requests did not yield recoverable responses. Therefore browser-access cells remain NR, including sources whose platform documentation supports CORS. No source was tested from a GitHub-hosted runner. This is a substantial remaining verification gap.

Socrata's public read-only CORS/$jsonp support and tokenless queries are documented (S033/S034). That platform documentation is kept distinct from actual per-endpoint verification. Shared-IP throttling can affect both browser users and datacenter runners. Seeing an ordinary web search form does not establish a no-login, no-CAPTCHA machine API.

SAMPLES
AINs 4256012034, 2004005005 and 8735022018 were attempted against Assessor/portal/CAMS paths without recovering record responses. No conclusion about their existence follows.
Three real records were recovered from each LADBS JSON feed. sample_records contains copied selected native fields, not fabricated complete rows. Missing fields are omitted, not replaced with invented null values. Alternative current-feed APNs: 2506031038, 4225005*** (masked), 7425036028. Alternative legacy-feed AINs: 7347010016, 5522017016, 2274023017. These are not claimed to be the same three homes across sources.

PRINCIPAL FINDINGS
Assessor: UseCode 0106/0107 identifies recorded SFR+ADU/JADU; pool flags also exist. DesignType01xx's third character describes heating, not stories. Quality class concerns construction, quality and perimeter complexity, not roof pitch or story count. Slots1–5 are labeled building records; a validated mapping to distinct physical footprints was not found. A design code can describe a subpart. See S001–S006/S095 and the code table. Published decoder subset is not a validation of current completeness. Compact GIS quality strings still need a documented normalization rule.

Footprints/heights: newer County services expose HEIGHT/ELEV and polygons, but a corresponding2023 item explicitly says LARIAC Members only (S011). One service's name2023, description2017 and item2023 capture text conflict. Height units and a reliable single/two-story threshold were not recovered. A pitched single-story roof can overlap a two-story height distribution. Microsoft supplies an older ODbL alternative without story counts. Google's Open Buildings v3 published scope excludes the USA.

Roofs/solar: NREL PVRDB has roof planes/aspect, but its Los Angeles source lidar is2007, and suitable PV planes are not all roof surfaces. Google Solar supplies roof pitch/orientation/area fields but requires billing/key and restrictive storage/map-display terms (S023–S026). It is not an open countywide export. Roof shape does not establish structural capacity for a deck.

Permits: current LADBS JSON has ADU/JADU changes, APN, status and occupancy dates. Legacy JSON exposes of_stories on some permits. Permit changes must be reconciled with completed work, supplemental records, demolition and conversion. A garage conversion can invalidate an older garage fact. County and other city portals remain mostly portal-only or unqualified in this review; the CSV does not imply countywide structured permit coverage.

Restrictions: retain full zone strings and intersect all relevant overlays. A base zone is not an executable building envelope. County/LA historic layers distinguish proposed/eligible/designated resources. CAL FIRE's2025 LRA recommendations need local adoption checks; SRA's identified effective date is2024-04-01. CGS zones indicate investigation requirements and must distinguish unmapped terrain from no mapped hazard. The recovered Coastal Zone source is a line, so point-intersects-line is not a valid inclusion test. NavigateLA easement lines are not a complete recorded utility-rights inventory.

Historic inventory: OHP publishes a direct LA County BERD CSV and a2026 guide documenting Parcel Num. CSV bytes/header/samples were not recovered. Preserve all pipe-separated historical evaluations rather than selecting only the first status. The2026 guide has a newer status-code table than the separately linked2020 sheet; missing resources do not imply no historic review (S102–S105).

Identity/imagery: CAMS supplies house-number points and AIN, but omits some units/subaddresses. LA City's PIN is not County AIN. The County parcel cache lists LOD0–20, with no verified vector-tile release recovered. USGS National Map imagery has explicit public-domain reuse, but actual LA roof export, CORS and acquisition-date checks remain open. The USGS cached imagery service lists LOD0–23 while advertising maxScale aroundz16; high zoom must be tested. Esri and LARIAC public display does not itself establish unrestricted reuse.

Postfire reconciliation: pre2025 footprints/elevation can describe houses no longer standing. Public Eaton DINS has a single-story/multistory structure type, but exposes only four attribute fields. Roof/deck/APN fields mentioned in editing templates are not public-view fields. County parcel+DINS uses AIN_1/APN_1 and assigns the worst-damaged structure to a parcel; it does not establish that the main home was destroyed or its present reconstruction status (S096–S099).

REPEATABLE ACCESS CHECKS
verify_access.py uses only Python's standard library and anonymous GET requests. Example:
  python verify_access.py --sources sources.csv --output access_results.json
Run it in GitHub Actions to test that environment. It records status, CORS headers, metadata, count results, JSONP wrapping, native fields and sample responses. It has not been run successfully against upstream public services in this research. Defaults cover eight priority sources; --source-ids accepts a comma-separated list. It does not certify a license or download whole county datasets.

Open browser_access_probe.html locally or from the intended static HTTPS host and click Run checks. It tests count-query fetches and callback execution. The browser supplies the real Origin (null for many local-file contexts). A fetch failure may be CORS, DNS, TLS, network policy, or service failure; it is not automatically a definitive CORS=no. No browser test results have been inserted into the research CSVs. Imagery/WebGL texture access requires an additional image-specific test.

IMPLEMENTATION RECOMMENDATION
Store each fact with source, source date, target structure/parcel, method and unknown state. Positive Assessor feature flags, completed permits and current observations can disagree. Ask for correction or show uncertainty instead of filling missing stories with1 or missing pools/ADUs withfalse. Match address to the appropriate parcel/roof; condominium parcels, address ranges and multiple structures need explicit handling. Parcel-minus-roof area is unroofed area, not automatically yard, permeable land or legal building area.

INFERENCES / UNRECOVERED OR RESTRICTED OPTIONS
Inference: no complete, current, openly reusable countywide table was recovered for every home's story count, roof material/pitch, garage spaces, fireplace, basement, A/C, deck, pool, ADU, frontage/depth and legal buildable yard. This does not establish that internal or paid Assessor/utility products lack those facts (S001–S006/S023/S067).
Inference: a complete anonymous API equivalent to ZIMAS with every ordinance's Q/T/D conditions, all88 cities' overlays and executable parcel-envelope rules was not recovered. Some city sources remain portal-only; even recovered base-zone layers do not encode every applicable condition (S048/S051/S054/S069–S075/S100/S101).
Inference: the publicly reachable2023 LARIAC outline is unsuitable as an assumed unrestricted republication source while its member-only notice remains unresolved;2020 terms and imagery releases require separate review (S011–S013/S085–S088).
Inference: Google Solar cannot serve as the unrestricted bulk cache behind an arbitrary static non-Google map under the recovered policies. It has paid tiers after free usage thresholds. Esri World Imagery was not qualified here as a free unrestricted commercial/public basemap (S023–S026/S089/S090).
