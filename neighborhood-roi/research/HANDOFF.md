# City Pretty — handoff for the next session

Branch: `claude/serene-cannon-exc9om` (repo `milessilverman/weblane`, folder `neighborhood-roi/`).
Current deliverable: `reports/city-pretty-la-county.html` (V2.3: real EIFD inputs).

## How it's built
- Data: `.github/workflows/neighborhood-data.yml` runs `pipeline/county_la.py` stages in GitHub Actions
  (geo, osm, transit, sales, crime, requests311, crashes, trees, parcels, assets, tra, assessed) and commits
  `data/derived/county_la/`. Dispatch with input `county_only=true` to skip the slow tract/Westside jobs, and
  `county_stages=tra,assessed` (comma list) to run only some county stages; the rest keep their last data.
  This sandbox can't reach County/ArcGIS hosts, so data pulls must run in Actions.
- Model: `python3 model/score_county.py` and `python3 model/eifd_tra.py` → `web/county_data/`.
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

## Next steps
1. (done) EIFD tax-rate-area data.
2. Add corridor right-of-way layers (abandoned rail, transmission, flood channels, Class I paths)
   so rail/creek trails can be sited.
3. Add FCC broadband data so fiber/5G is only suggested where service is poor.
4. Replace "unverified" costs with the sourced figures from round 5's Part 4.
5. Map-orientation features (street labels overlay, freeway shields, scale bar, locate-me,
   mini-map, breadcrumb, hover outline, shareable link).
