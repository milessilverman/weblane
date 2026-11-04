CITY PRETTY — ROUND 7: H–K RESEARCH RECOVERY PACK
Status as of November 3, 2026, America/Los_Angeles

This is a PARTIAL sourcebook, not a complete inventory of every LA County
project, golf course, restriction, or current underwriting input. Unknown
values are deliberately NR. Failed downloads are not presented as working
machine-readable feeds. The 15 ranked additions are in partK_ranked.csv.

FILES AND COVERAGE
sources.csv: 128 source entries, including GAP00, an explicit research-gap
marker with no external source. Source entries include opened documents,
partially recovered sources, listed downloads and failed attempts.
partH_projects.csv: 40 source/program rows, not 40 individual construction
projects. Covers H1–H6 and explicitly records unrecovered subparts.
partI_profit_inputs.csv: 38 inputs, including historical comparators and
explicit missing current inputs. It is not a ready-to-run valuation model.
partJ_underused.csv: 59 rows. Includes the County's 18 golf facilities
(20 courses), selected proposals, laws, land inventories and constraints.
The complete city-owned and private golf-course roster and parcel-specific
deed/lease restrictions remain unrecovered.
partK_ranked.csv: exactly 15 ranked recommendations.

Every CSV uses the requested column order, UTF-8, one header row, and quotes
every field. K uses the literal parenthetical column names in the request.
Source IDs are linked by semicolons. Internal IDs identify sources and
research rows; they are not government project IDs.

EVIDENCE STATUS
OPENED / OPENED_DOCUMENT / OPENED_HTML: inspectable source content recovered.
PARTIAL / PARTIAL_METADATA: only a schema, abstract, or other limited content
was recovered. Read notes; this is not a successfully tested bulk feed.
LISTED: an identified/linked endpoint or download was attempted, but its
records or file contents were not inspectable. This includes unsupported
CSV/XLSX/ZIP responses and JavaScript-only viewers.
NR: not recovered, including inaccessible, restricted, oversized, missing,
or timed-out sources and unresearched details. NR is never numeric zero.
HISTORICAL: preserve the observation/cost year; do not rebrand as 2026.

AUTOMATION LIMITS
The exact endpoints were attempted through research retrieval, but were NOT
tested in a US GitHub Actions runner. No claim is made that a source will
accept datacenter requests, remain anonymous, or support unattended bulk
downloads merely because its webpage opened. Ordinary local network access
was restricted. ArcGIS pjson schemas were recovered for BOE CIP points,
County and SCAG housing-element sites, Assessor sales, and CCED. Required
count and sample query attempts did not return inspectable results here:
their counts and three-record samples remain NR. No ArcGIS row is fully
verified for the user's complete metadata/count/sample acceptance test.
MaxRecordCount is never treated as the dataset record count.

The LAHD mymu-zi3s, LADBS pi9x-tg5x and historical Planning 5aw2-jx4k
Socrata JSON endpoints returned real records. Three field projections are
included in H. Bare endpoints return bounded pages; full counts and complete
pagination were not recovered. The 2016 Planning feed is explicitly not a
current development pipeline. Current Planning case reports are separate.

SAMPLE AND FILE CONVENTIONS
Samples are copied field projections, not fabricated complete records.
HTML/PDF projections are labelled as such and do not imply an API schema.
Where no three-record set was recovered, samples are NR; a scalar report
statistic or law summary is not a three-record dataset sample. The City
declared-surplus PDF contains only two records; both are described, with
the three-sample requirement explicitly NR. No synthetic third row is added.
PDF page references use one-based PDF pages unless a printed page is also
specified. File byte sizes are NR except where the retrieval or catalog
reported a size; catalog KB values are not claimed as exact byte counts.
Downloaded source bytes are not bundled in this pack.

HIGH-VALUE FINDINGS AND LIMITS
* LAHD JSON contains site-level and project-level fields. Deduplicate before
  summing units or costs; its date_stamp is newer than the retrieved metadata.
* Metro D Line Section 1 is explicitly open; later sections remain in
  construction. Opening forecasts are not guarantees or proof of full funding.
* SCAG's official SB79 map was updated October 29, 2026. Its underlying
  downloadable service was not recovered. Unofficial SB79 layers were not
  substituted. Generic station radii are insufficient for official tiers.
* FY26–27 Safe Clean Water recommendations are distinct from Board-approved
  funding. The recovered LLAR table includes withdrawn projects and reported
  end dates; a past forecast is not proof of completion.
* The RPOSD 2026 award list is actual grant evidence. Planning/design grant
  dollars are not construction budgets or total project costs.
* LAHD's 2025 affordable/supportive cohort TDC is above $782,000 per unit in
  constant 2024 dollars, from its March 20, 2026 report p9. Hard/soft/land
  components are not recovered. Older Terner prototype costs are labelled
  2023-adjusted comparators, not 2025–26 bids. Current local SFR, ADU,
  townhome, podium and high-rise cost matrices remain NR.
* CBRE and Kidder rent measures describe different publisher samples.
  Bedroom, submarket and vintage marginal tables cannot be combined into
  an invented new-unit/bedroom/submarket cross-tab. Cap rates are observed
  publisher benchmarks, not parcel-specific guarantees.
* Assessor recent-sales help describes unverified single-parcel, DTT-derived
  indicated prices and limited history. It is not evidence of exact complete
  transaction consideration or a market/assessed land ratio. The TOC paper's
  land appreciation conversion is an assumption, not a measured tenure ratio.
* Current ULA thresholds and fee amounts remain NR because the authoritative
  fee pages/documents did not open. LADBS confirms AHLF system changes in
  August 2026 and LAUSD fee changes effective August 11, 2026, but amounts
  were not recovered. Old rates are not silently carried forward.
* SB4's original January 1, 2024 effective date is supported by the Governor's
  December 2023 announcement. The April 2026 HCD fact sheet prints July 2,
  2024; the discrepancy is retained. An ownership cut-off and a statute's
  operative date are different facts. Other legal summaries flag limits to
  amendment reconciliation and do not certify every parcel's eligibility.
* Public ownership, declared surplus, offered property, developer selection,
  secured financing, construction and completion are different stages.
  LAUSD's October 2026 proposals and LACDA's superseding October notice
  demonstrate why stage and document dates belong in the map.
* A minimum auction bid is not a land sale. Caltrans' Glendale brochure
  discloses a reserved highway easement and no utilities; the Lake Hughes
  notice discloses a mineral reservation. These are concrete title concerns.
* Conservation, flood, seismic, fire and slope layers are screening evidence.
  They do not establish one countywide binary legal buildability rule.
  Local adoption, site-specific studies, easement instruments and zoning
  exceptions need separate review.

EXPLICIT REMAINING GAPS
No complete all-agency/all-88-city funded-project feed was recovered.
StreetsLA/LADOT dedicated future-project inventories; current geocoded
Planning/ED1/CHIP/SB35/AB2011 filing feeds; the official SB79 downloadable
layer; the complete LAUSD school-bond list; most other-city permit feeds;
and a complete Prop4 LA award inventory remain NR or partial. Housing
element capacity sites are not funded projects. Complete current golf title,
acreage and lease restrictions remain NR. Price-paid evidence for the
redevelopment examples remains NR. No causal numeric K Line, Regional
Connector or SB79 land-value uplift was recovered.

RECOMMENDATION READINESS
In K, yes means the cited opened evidence can support the described small
addition now (for example, two declared-surplus parcels); it does not mean
all ingestion, legal or GitHub runner checks passed. Partly means important
data or implementation checks are still missing. S/M/L are researcher's
relative effort judgments, not measured staff hours.

INFERENCES — NOT VERIFIED CLAIMS OF NONEXISTENCE OR ACCESS
* A single complete public machine-readable inventory of all LA County
  funded/planned public and private projects appears unlikely from the
  fragmented sources recovered; this search does not prove none exists.
* A standard public, current market-to-assessed LAND ratio by ownership
  duration, and an exhaustive public parcel utility-easement layer, were not
  recovered. They may require custom estimation, title work or agency data.
* Fine-grained transaction/rent/cap-rate data may require commercial licenses;
  broker summaries do not establish permission to republish the underlying
  CoStar records. Zillow redistribution/commercial terms were not recovered.
* Some academic full texts are restricted, and some downloads failed only
  in this research environment. A failed fetch does not prove a paid source,
  authentication requirement, permanent outage, or failure in GitHub Actions.
