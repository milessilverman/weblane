# City Pretty — handoff for the next session

Branch: `claude/serene-cannon-exc9om` (repo `milessilverman/weblane`, folder `neighborhood-roi/`).
Current deliverable: `reports/city-pretty-la-county.html` (V2.2).

## How it's built
- Data: `.github/workflows/neighborhood-data.yml` runs `pipeline/county_la.py` stages in GitHub Actions
  (geo, osm, transit, sales, crime, requests311, crashes, trees, parcels, assets) and commits
  `data/derived/county_la/`. Dispatch with input `county_only=true` to skip the slow tract/Westside jobs.
- Model: `python3 model/score_county.py` → `web/county_data/`.
- Page: `python3 web/build_county_html.py` → `reports/city-pretty-la-county.html`.

## Research in this folder
- `City_Pretty_Evidence_Sourcebook*.html`: rounds 1-3 (ChatGPT). Already used.
- `round5_*`: overnight research (EIFD tax-rate-area data, corridor right-of-way layers,
  FCC broadband, cost verification). NOT yet reviewed or used.
- Gemini passes (pasted in chat, not saved here): used only for program rules confirmed by
  both audits; its costs are labeled "unverified" in the model; none of its price effects are used.

## Next steps
1. Review `round5_*`: load the Auditor-Controller TRA allocation factors + TRA boundaries +
   parcel assessed values into a new pipeline stage, and replace the EIFD calculator's placeholder
   tax shares and 55%-of-market base value.
2. Add corridor right-of-way layers (abandoned rail, transmission, flood channels, Class I paths)
   so rail/creek trails can be sited.
3. Add FCC broadband data so fiber/5G is only suggested where service is poor.
4. Replace "unverified" costs with the sourced figures from round 5's Part 4.
5. Map-orientation features (street labels overlay, freeway shields, scale bar, locate-me,
   mini-map, breadcrumb, hover outline, shareable link).
