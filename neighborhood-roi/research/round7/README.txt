CITY PRETTY — ROUND 7, LOS ANGELES COUNTY
Research cutoff: November 2, 2026

CONTENTS
sources.csv                 106 source/audit entries
partH_projects.csv           41 project-source entries
partI_profit_inputs.csv      37 profitability inputs and explicit gaps
partJ_underused.csv          50 land, policy, inventory and example entries
partK_ranked.csv             15 ranked additions

Each CSV uses the exact requested column names, UTF-8, a header row and
double quotes around every field. Embedded JSON is CSV-escaped. Multiple
source_ids are separated with | and refer to sources.csv. NR means not
recovered; it never means zero, no projects, no restriction or no effect.

THIS IS A PARTIAL RESEARCH INVENTORY
The package does not establish coverage of every public project, private
development, golf course or parcel restriction. It identifies recovered
sources and makes incomplete requirements explicit. A source row is not a
project row: counts in this package must not be used as County project totals.
The County golf subset has 18 facilities, covering a system with 20 courses;
it is not a complete inventory of all municipal and private courses.

ACCESS AND EVIDENCE
All external URLs listed were attempted through retrieval tools before
inclusion. An unsuccessful attempt is not a working-endpoint certification.
No GitHub Actions runner, US datacenter deployment, browser session, login
or CAPTCHA workflow was tested. Retrieval errors may reflect the research
environment rather than source-side availability.

OPEN / OPEN_PAGE / OPEN_DOCUMENT: readable page or document content opened.
OPEN_DATA: actual records returned; this applies to the two Socrata feeds.
OPEN_METADATA / SERVICE_METADATA_ONLY: schema or service description was
recovered, but records/counts were not. LEGACY_METADATA is also stale.
LISTED: an official page linked the asset, but usable bytes/records were not
recovered. LISTED_WITH_SCHEMA additionally has catalog schema information.
LISTED_BROKEN: official link was found, but the attempted path returned 404.
NR: requested content or endpoint was not recovered. Candidate unverified
URLs are explicitly flagged rather than represented as official datasets.
PARTLY: mixed recovery or fallback coverage; inspect the notes.
Other statuses describe the item, such as historical-only, a working paper,
a proposal or a surplus notice. They do not certify dataset completeness.

ArcGIS metadata/count/sample requests were attempted where described.
Failed responses are recorded as NR. Real field names and geometry are
reported only where recovered. The GSD service description is distinguished
from unrecovered layer metadata. No ArcGIS count is fabricated.

Three projected source records appear in each populated H sample_records
cell: H24 (award-table rows), H31 (LAHD) and H32 (LADBS). Values are copied
from the response, with a selected subset of fields. H32 samples happen to
be alterations; they do not demonstrate a new-construction filter. J02-J04
are actual golf name/address entries; J33-J35 are actual parcel records from
the Lake Hughes surplus notice. Where no 3-record sample was recovered,
sample_records is NR. Document-derived example rows are not bulk API data.

File type and size are reported where recovered. Most file sizes remain NR.
The APR file size of 281.1 MiB and statewide count of 927006 are catalog
claims, not measured download size or an LA County query result. Short-lived
signed redirect URLs are excluded from the deliverable.

DATA USE
1. Start with H31 and H32. They returned records; count, license and anonymous
   GitHub Actions compatibility still need verification. Deduplicate project
   sites and supplemental permits before aggregating units or valuations.
2. Recover the HCD APR file (H37) for annual all-jurisdiction project events.
   Preserve event types and do not add approvals, permits and completions
   together as distinct housing units.
3. Obtain the underlying official SB 79 services (H41), and check local
   implementing ordinances and alternative plans. A station-distance buffer
   alone is not a verified tier or parcel entitlement.
4. Geocode Measure A awards (H24), retaining planning/design versus
   construction categories and grant amount versus total project budget.
5. Use Part K for the remaining prioritized acquisition and validation work.

Readiness 'yes' in Part K means returned records are usable for initial
engineering; it does not mean access, completeness or redistribution rights
have been certified. Missing licenses are NR, not assumed permission.

MODELING BOUNDARIES
Funded design, an adopted plan, an appropriation, an issued permit, actual
construction and an open facility are separate events. Housing Element
capacity is an assumption, not a development approval. A surplus notice does
not prove a sale. Agency operation of a golf facility does not prove fee title.

Profitability inputs retain their dollar year, scope and document/page.
The CalHFA land example is a 2024 appraisal, not a closed land sale. The
2026 Santa Monica acquisition budget is not a market land purchase price.
The Terner table is a 2023 cost basis, and the recovered Long Beach fees are
effective October 2025; neither is a verified November 2026 schedule.
Construction, land, soft costs and financing must not be double counted.
The builder ADU allowance is commercial self-report, not a government survey.
Broker rents cover all stock; they do not establish new-unit submarket rents.

The recovered TOC working paper's baseline price estimate is not robust to
the stronger comparisons described in the paper. Do not use it as a default
10% land-value uplift or as evidence for SB 79. Numerical Expo/Gold effects
were not recovered from the opened abstract. NR is not a zero-effect result.

Laws are described against guidance recovered on November 2, 2026. Dates
and unresolved points remain explicit, including the SB 4 effective-date
discrepancy and the unrecovered original AB 1486 effective date. Current ULA
amounts and a complete current local fee matrix remain NR. Original statutes,
current amendments and local implementation still need checking where NR.

Hazards generally trigger investigation, mitigation or design requirements;
they do not form a universal no-build mask. Conservation and utility
easements require the recorded instruments. Slope is physical terrain;
legal exclusions depend on the applicable local rules and site conditions.

REMAINING GAPS AND INFERENCES
No single verified free, anonymous, County-wide bulk source was recovered
for all funded projects/private development; closed entitled-land sales;
market-to-assessed land ratios by ownership tenure; all golf fee titles and
deed/lease restrictions; or all utility easements. This is an inference from
the retrieval results, not proof that such sources do not exist.

The rail study explicitly describes DataQuick data as proprietary. The
recovered broker summaries do not establish access or redistribution rights
for the underlying CoStar records. A complete market-sales, title or site-
specific cost layer may require agency exports or licensed data (inference).
