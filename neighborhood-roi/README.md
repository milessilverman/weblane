# Neighborhood ROI

Find the neighborhood improvements that raise property values the most per dollar spent, for any neighborhood in the US. Examples are planting street trees, greening vacant lots, opening green schoolyards, and adding lighting. The finished product is a clickable map. Click a neighborhood to see its ranked list of improvements, what each costs there, how much value it should create, and what is already being done nearby.

## Core idea

Each recommendation multiplies four things:

```
value created  = homes in range × median home value × published uplift % × fit for this neighborhood
cost           = unit cost × regional cost factor (+ land, if needed) + 10-yr maintenance (present value)
value per $    = value created / cost
```

* **Published uplift:** this comes from the evidence library (`data/interventions.csv`). Every row cites before/after or hedonic studies, such as the effect of street trees on sale prices in Portland or of vacant-lot greening in Philadelphia.
* **Fit:** this is how much of the published effect applies to this neighborhood. Trees score high where there is little canopy and a lot of heat. Lot greening only counts where vacancy is high, and schoolyards score high where campuses are mostly asphalt and parks are scarce. This is why the best choice changes from place to place.
* **Regional cost:** the same project costs about 30% more in NYC than in Dallas (`data/regional_cost_factors.csv`). Land matters even more: a quarter-acre pocket park is cheap to buy in Philadelphia and very expensive in LA.

Run the prototype on three example neighborhood types:

```
python3 model/roi.py                # conservative (low-end effects, distance decay)
python3 model/roi.py --optimistic   # midpoint effects
```

| Example neighborhood | #1 | #2 | Why |
|---|---|---|---|
| Rowhouse tract with many vacant lots (Philadelphia-like) | Clean & green vacant lots (~58× value per $) | Community garden | Lots are cheap, there are many of them, and the effect is well measured |
| Dense, hot, park-poor tract (South LA-like) | Community garden | Street trees (~10×) | Home values are high and canopy is nearly absent, while trees cost about the same everywhere |
| Car-oriented suburb (Dallas-like) | Community garden (smaller effect) | Street trees (~2×) | Few problems to fix, so the returns are low everywhere |

These three neighborhoods are made-up inputs, not measured data for real tracts. Phase 1 replaces them with real data.

## Caveats the tool must show

1. **Value created is not profit captured.** Most of the gain goes to surrounding owners. If you are the spender, you capture (a) the gain on parcels you own nearby, (b) higher property-tax revenue if you are a city, or (c) value capture through a TIF district, BID assessment or a land-banked parcel. The UI should let you enter "I own X parcels within Y ft" and show your captured share.
2. **Effects don't stack linearly.** Ten projects in one block do not produce ten times the uplift. The model uses overlap and distance decay; Phase 2 calibrates these.
3. **Green gentrification.** The interventions that create the most value (the BeltLine, the 606) also displaced renters. Show a displacement-risk flag next to large-uplift projects in low-income tracts.
4. **Some effects are modeled, not measured.** For lighting, board-ups and schoolyards, the studies measured crime or test-score changes, and the value effect is inferred from them. The evidence column says which.

## Your research this builds on

These come from your Drive. Claude can't open your past claude.ai chats from here, so this list was rebuilt from the documents those chats produced.

* **Planting Greenery in Schools** (Oct 2026): LAUSD schoolyards are about 80% asphalt and reach 142°F. Every 1°F hotter school year costs about 1% of learning. Only tree cover, not grass, predicted higher test scores in Chicago. Measure US sets aside $1.25B for schoolyard greening, and CAL FIRE has spent $156M+ on green schoolyards. Tree care runs about $13–65 per tree per year, and street trees die at 3.5–5.1% per year. All of this is in the `green_schoolyard` and `street_tree` rows. Your partner contact at TreePeople is a natural first data and pilot partner.
* **Grounded in Green** (Apr 2026): 1.5M Angelenos live more than a 10-minute walk from a park, and LA ranks 88th in ParkScore. Lighting cut nighttime outdoor crime 36% in NYC. Seating, water features and programming are cheap add-ons once land is secured. These feed the `pocket_park`, `community_garden` and `street_lighting` rows and the land-cost logic.
* **Greenery in Schools essay**: covers the equity angle. The poorest schools have the least shade and suffer the most heat damage to learning.

## Data the tool needs (all refreshable)

The full catalog is in `data/data_sources.csv`. The core layers:

| Need | Source | Refresh |
|---|---|---|
| Home values | Zillow ZHVI, FHFA tract HPI, Census ACS | monthly / annual |
| Homes per area | ACS housing units + TIGER tracts | annual |
| Tree canopy gap + heat | American Forests Tree Equity Score, Landsat land-surface temperature | ~2 yr / each summer |
| Park access | TPL ParkServe | annual |
| Vacancy | HUD-USPS vacancy | quarterly |
| Schools | NCES + Stanford SEDA | annual |
| Brownfields / environment | EPA ACRES, EJScreen (via the PEDP mirror; EPA took the original offline in Feb 2025) | irregular |
| What's already being done | USAspending API, Grants.gov, city capital-improvement plans, state programs | daily to quarterly |
| Costs | BLS OEWS wages (to build our own regional index), AEI/FHFA land prices | annual |

## Game plan

**Phase 0: done (this commit).** Evidence library (15 interventions plus a rail-station "coming soon" signal), data-source catalog, regional cost factors, and a working ranking model.

**Phase 1: real data for one metro (LA).** Write ingest scripts for ACS, Tree Equity Score, ParkServe, HUD vacancy and LAUSD schools. Every LA tract gets a real set of inputs, and the model runs on all of them. Output goes to one GeoJSON/PMTiles file.

**Phase 2: calibrate against history.** For past projects (LandCare lots, LA street-tree plantings, the 606, the BeltLine, Green Schoolyards sites), compare FHFA/Zillow values before and after against similar control tracts. This replaces the guessed overlap, decay and fit factors with measured ones. It is also the "what has been done and what did it do" layer.

**Phase 3: the map.** Use MapLibre GL with PMTiles on static hosting (Netlify works). Click a tract to see its ranked list, a cost breakdown, the evidence behind each number, nearby current projects, and the captured-value calculator.

**Phase 4: national rollout.** Run the same pipeline across all ~85k tracts.

**Phase 5: keep it fresh.** A scheduled GitHub Action re-pulls each source on its own schedule and rebuilds the tiles. A scheduled Claude task scans news, CIPs and grant awards for new projects and flags evidence rows that new studies should update.

## Files

```
data/interventions.csv          evidence library: uplift, radius, cost, maintenance, sources
data/data_sources.csv           every data layer, where it comes from, how often it updates
data/regional_cost_factors.csv  metro cost multipliers (approximate; to be replaced in Phase 1)
data/example_neighborhoods.json three made-up neighborhood types for testing
model/roi.py                    ranking model
```
