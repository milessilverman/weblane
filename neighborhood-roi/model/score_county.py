"""City Pretty v2: score every LA County block group for ~50 improvement types.

For each block group and improvement:
    value created = homes reached x typical unit value x price effect x ramp
    total cost    = build cost + land + 10-year upkeep (present value)
    value per $1  = value created / total cost

Price effects use the low end of the studies in the City Pretty evidence
sourcebooks (rounds 1 and 2); crime-cutting programs are converted to home value
with measured crime-price elasticities. Items without a measured home-value effect
are still listed and costed, ranked by quality-of-life need instead.

    python3 model/score_county.py
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "derived" / "county_la"
OUT = ROOT / "web" / "county_data"
PV10 = sum(1 / 1.03 ** t for t in range(1, 11))  # 10 years of upkeep at 3%
LA_COST = 1.13  # national cost data -> Los Angeles (applied only where the cost is not already an LA figure)
EL_VIOLENT, EL_PROPERTY = 0.116, 0.0097  # Schwartz, Susin & Voicu 2003 (repeat sales); property: panel estimate
_cal = ROOT / "data" / "calibration_trees_la_westside.json"
TREE_50M_PCT = json.loads(_cal.read_text())["trees_within_50m"]["ci95_pct"][0] if _cal.exists() else 0.24

# Cities with their own police department (no LAPD / LASD records there)
OWN_POLICE = {"Alhambra", "Arcadia", "Azusa", "Baldwin Park", "Bell", "Bell Gardens", "Beverly Hills", "Burbank", "Claremont",
              "Covina", "Culver City", "Downey", "El Monte", "El Segundo", "Gardena", "Glendale", "Glendora", "Hawthorne",
              "Hermosa Beach", "Huntington Park", "Inglewood", "Irwindale", "La Verne", "Long Beach", "Manhattan Beach", "Monrovia",
              "Montebello", "Monterey Park", "Palos Verdes Estates", "Pasadena", "Pomona", "Redondo Beach", "San Fernando",
              "San Gabriel", "San Marino", "Santa Monica", "Sierra Madre", "Signal Hill", "South Gate", "South Pasadena",
              "Torrance", "Vernon", "West Covina", "Whittier", "Los Angeles"}

S = {  # sources, cited by key in the catalog
    "local_trees": "City Pretty local hedonic: 3,386 Westside sales 2022-24, block fixed effects; each street tree within 50 m +0.51% (95% CI 0.24-0.79)",
    "lamc_tree": "LAMC 62.177 in-lieu fee: $1,945 per public-works tree incl. planting and 3-yr establishment",
    "usfs_tree": "USFS / California street-tree costing: $52-79 per tree-year upkeep",
    "lin": "Lin, Jensen & Wachter 2023 (Philadelphia): +4.3% nearby after year 1",
    "landcare": "Philadelphia LandCare: $1,500 initial / $300 a year per lot (2008$)",
    "branas": "Branas et al. 2018 RCT: gun violence -29% in poor neighborhoods",
    "ganduri": "Ganduri & Maturana 2024: neighbors +2.3 pts after REO rehab; Rossi-Hansberg, Sarte & Owens 2010: $2-6 land value per $1",
    "voicu": "Voicu & Been 2008 (NYC): +1.5 pts at 1,000 ft, larger in poorer areas",
    "pasadena_pna": "Pasadena Parks Needs Assessment 2016: community garden $300k; Robinson Park rec center $6.3M",
    "crompton": "Crompton & Nicholls 2020 review: +8-10% adjacent to passive parks; small-park effect within ~100 m (Laszkiewicz 2022)",
    "fiftyparks": "LA 50 Parks Initiative: 5,000-20,000 sq ft parks $250k-700k to develop, land extra",
    "albouy": "Albouy, Christensen & Sarmiento-Barbieri: park value falls where homicide risk is high",
    "livy": "Livy & Klaiber 2016: playground replacement among the most capitalized park upgrades; Brasington 2023: park-maintenance levy renewal +11.6%",
    "culver_play": "Culver City, Culver West Alexander playground, Nov 2025: $759,353",
    "pickle": "Redondo Beach Alta Vista 2026: tennis resurfacing + 1 court to 4 pickleball $107,408; Cerritos 2 pickleball courts $134k",
    "pna_bball": "LA County PNA 2016: one full basketball court $436,250",
    "minneapolis": "Minneapolis 2014 park-facility study: passive features add value; some active/skate facilities lower nearby values",
    "dogpark": "2025 park-attribute study: dog parks positively associated with nearby values (coefficient not recovered)",
    "rap_pools": "LA CAO 2022 program estimate: $100M capital / $2.08M yearly O&M for new pools",
    "juntos": "LA RAP Juntos Park splash pad: $642,021 (2017)",
    "skate": "LA CAO 2022: skate-park program $30M capital / $800k yearly O&M",
    "turf": "Sunnyvale 2023: natural-grass field $516,150 vs synthetic $2.03M; Culver City PNA field replacement $2.8M",
    "restroom": "LA County Measure A: South LA replacement restroom building $990,000",
    "stap": "LA Sidewalk & Transit Amenities Program: provisional $180,842 per shelter (city memo, 2025)",
    "wilshire": "Metro Wilshire bus lanes: $31.5M for 9.9 miles (2013); Culver City Robertson bus/bike lanes $1.22M (2025)",
    "flower": "Metro Flower St bus lane: buses up to 30% faster",
    "brt": "Beaudoin & Tyndall 2024 (Vancouver WA BRT): +5-7% home prices; FTA Capital Cost Database for BRT costs",
    "rail": "Debrezion, Pels & Rietveld 2007 meta-analysis: +4.2% residential within station area; Keeler & Stephens 2023 (LA Gold/Expo)",
    "humps": "LADOT 2025: $5,958 per speed hump, up to 25-year life",
    "polloni": "Polloni 2019 (Portland): traffic calming that cuts flow 16% raises treated-street values ~1%",
    "smbulb": "Santa Monica Blvd Safety Study 2026: ADA ramp $9,000; bulb-out $11,000-18,000",
    "fhwa": "FHWA: refuge islands -46% pedestrian crashes; road diets -29% crashes",
    "sidewalk": "LA Controller 2021 sidewalk audit: $51 per sq ft incl. soft costs",
    "bsl": "LA Bureau of Street Lighting: ~$5,000 per 50-ft residential lot to build; ~$90 a year upkeep assessment",
    "chalfin": "Chalfin et al. (NYC RCT): street lighting -36% nighttime outdoor index crime",
    "schwartz": "Schwartz, Susin & Voicu 2003 (NYC): 1% less violent crime -> +0.116% home prices",
    "cctv": "Piza et al. 2019 meta-analysis: CCTV -13% crime; LA Civic Center 2024 quote ~$8,148 per camera; RAP camera upkeep",
    "ratcliffe": "Ratcliffe et al. 2011 (Philadelphia RCT): foot patrol -23% violent crime",
    "gryd": "LA GRYD budget $41M a year (FY2023-24); Cure Violence review: 32.5% of findings show significant drops",
    "bid": "MacDonald et al. 2010 (30 LA BIDs): robbery -12%",
    "litter": "MacDonald et al. 2026 street-cleaning RCT: litter -16%; LA CARE cleanup team ~$1.4M a year",
    "gibbons": "Gibbons 2004 (London): 5 fewer criminal-damage incidents per km2 a year -> +1.56% prices; LA graffiti crews $11.7M / 95 crews",
    "bhandari": "Bhandari 2024 (LA): encampments within 0.2 mi -> -1.41% sale prices; RAND Housing for Health: ~20% net public savings",
    "ladwp": "LADWP 2019: $2.8M per circuit-mile undergrounding (contracts $2.2-4.5M); CPUC Rule 20: $1.8-6.1M/mile",
    "mcnair": "McNair & Abelson 2010 (Canberra): underground power +2.9% house prices",
    "ev": "Liang et al. 2023 (14M California sales): +3.3% within 1 km of EV chargers; CARB 2025: 8-port DC fast site $800,473",
    "microgrid": "LA County CPUC filing 2021: community microgrids $3.25-3.6M each",
    "solar": "Berkeley Lab 2015: ~$4/W premium for owned solar; DOE 2025 benchmark $2.95/W installed",
    "adu": "Brueckner et al. 2024 (LA): ADU raises host parcel +9.2% (95% CI 6.6-11.9); Tanrisever 2025: neighbors -3% per +0.5 pt ADU density within 300 m; LA County median ADU cost $100k (2020)",
    "moretti": "Moretti & Wheeler 2025: new noise barrier +6.8% within 100 m; Caltrans soundwall costs",
    "cap": "Klyde Warren Park cap $110M for 5 acres (2012); Hollywood Central Park proposal $250M + $780k a year",
    "schoolgreen": "LAUSD / Green Schoolyards America projects (Pacoima MS 2024: 107 trees, 14,000 sq ft asphalt removed)",
    "cellini": "Cellini, Ferreira & Rothstein 2010 (California school bonds): +6% prices; >= $1.50 home value per $1 of school capital",
    "grocery": "Worcester DiD: +7% within 400 m, +4% at 400-800 m after a grocery opens; Saengchote 2020: Whole Foods +6.7%",
    "parklet": "SF Controller: parklet businesses +29% revenue; LA Al Fresco corridors +$12M sales",
    "retail": "Ghorbani & Meltzer 2024 (NYC): more nearby retail raises 1-4 family values, lowers condo values; Teh 2007 (LA): liquor stores raise nearby crime",
    "market": "Farmers-market studies (Maryland 2020; Edmonton 2024): positive, inverted-U with distance",
    "library": "Gilpin, Karger & Nencka: library capital spending +21% visits; no detectable home-price change",
    "lihtc": "Diamond & McQuade 2019: LIHTC +6.5% within 0.1 mi in low-income areas, -2.5% in high-income; LA HHH ~$597k per unit",
    "upzone": "Kuhlmann 2021 (Minneapolis): +3-5% affected single-family prices; Kestelman 2025 (LA TOC); HCD SB 79 (eff. July 2026)",
    "coolpave": "Pacoima / Covina cool-pavement studies: surface -5 C, air -0.2 to -1.9 C; Middel 2020: midday radiant heat +4 C for pedestrians",
    "greenalley": "Avalon Green Alley North phase II (2015): $1.83M",
    "filters": "Gilraine 2020 (LA, Porter Ranch): classroom air filters raised test scores",
    "clinic": "Bailey & Goodman-Bacon 2015: community health centers -2% mortality 50+",
}

# id, name, category, kind, evidence, sources, qol dims (need scores that make it matter), years to full effect
CAT = [
    ("street_trees", "Plant street trees on open sites", "Greening", "value", "strong (local)", ["local_trees", "lamc_tree", "usfs_tree"], ["heat"], 6),
    ("schoolyard_green", "Green a schoolyard (asphalt to trees and grass)", "Greening", "value", "limited", ["schoolgreen", "crompton"], ["heat", "kids"], 3),
    ("vacant_lot_green", "Clean and green vacant lots", "Greening", "value", "strong", ["lin", "landcare", "branas"], ["blight", "safety"], 1),
    ("community_garden", "Community garden", "Greening", "value", "moderate", ["voicu", "pasadena_pna"], ["food", "parks"], 5),
    ("green_alley", "Green alley (permeable paving, trees)", "Greening", "qol", "limited", ["greenalley"], ["heat"], 2),
    ("cool_pavement", "Cool pavement coating on hot streets", "Greening", "qol", "limited", ["coolpave"], ["heat"], 0),
    ("pocket_park", "Pocket park on a new lot", "Parks & recreation", "value", "strong", ["crompton", "fiftyparks", "albouy"], ["parks", "kids"], 2),
    ("park_upgrade", "Renovate the nearby park (new playground, paths)", "Parks & recreation", "value", "moderate", ["livy", "culver_play"], ["kids", "parks"], 1),
    ("pickleball", "Convert a tennis court to 4 pickleball courts", "Parks & recreation", "qol", "limited", ["pickle", "minneapolis"], ["rec"], 0),
    ("tennis", "Build 2 public tennis courts", "Parks & recreation", "qol", "limited", ["pickle", "minneapolis"], ["rec"], 0),
    ("basketball", "Build a public basketball court", "Parks & recreation", "qol", "limited", ["pna_bball", "minneapolis"], ["rec", "kids"], 0),
    ("dog_park", "Dog park", "Parks & recreation", "value", "limited", ["dogpark"], ["rec"], 1),
    ("pool", "Public swimming pool", "Parks & recreation", "qol", "limited", ["rap_pools"], ["heat", "kids"], 0),
    ("splash_pad", "Splash pad", "Parks & recreation", "qol", "limited", ["juntos"], ["heat", "kids"], 0),
    ("skate_park", "Skate park", "Parks & recreation", "qol", "limited", ["skate", "minneapolis"], ["kids"], 0),
    ("sports_field", "Natural-grass sports field", "Parks & recreation", "qol", "limited", ["turf"], ["kids", "rec"], 0),
    ("rec_center", "Recreation center", "Parks & recreation", "qol", "limited", ["pasadena_pna"], ["kids", "rec"], 0),
    ("restroom", "Park restroom and drinking fountains", "Parks & recreation", "qol", "limited", ["restroom"], ["parks"], 0),
    ("bus_lane", "Peak-hour bus lanes on the busy corridor", "Transit", "value", "limited", ["wilshire", "flower", "brt"], ["transit"], 1),
    ("brt", "Bus rapid transit (stations, lanes, signal priority)", "Transit", "value", "moderate", ["brt"], ["transit"], 2),
    ("rail_station", "New rail station (regional project, local share)", "Transit", "regional", "strong", ["rail"], ["transit"], 5),
    ("bus_shelters", "Bus shelters with shade at busy stops", "Transit", "qol", "limited", ["stap"], ["heat", "transit"], 0),
    ("traffic_calming", "Speed humps and traffic calming", "Streets & safety", "value", "moderate", ["humps", "polloni"], ["traffic"], 0),
    ("crosswalks", "Safer crossings (bulb-outs, ramps, refuges)", "Streets & safety", "qol", "strong", ["smbulb", "fhwa"], ["traffic"], 0),
    ("road_diet", "Road diet with protected bike lanes", "Streets & safety", "qol", "moderate", ["wilshire", "fhwa"], ["traffic"], 0),
    ("sidewalks", "Repair broken sidewalks", "Streets & safety", "qol", "limited", ["sidewalk"], ["walk"], 0),
    ("street_lighting", "Brighter pedestrian street lighting", "Streets & safety", "value", "strong (crime) / modeled (value)", ["chalfin", "bsl", "schwartz"], ["safety"], 0),
    ("cameras", "Security cameras at hot spots", "Streets & safety", "value", "moderate (crime) / modeled (value)", ["cctv", "schwartz"], ["safety"], 0),
    ("foot_patrol", "Foot patrols on hot-spot blocks", "Streets & safety", "value", "strong (crime) / modeled (value)", ["ratcliffe", "schwartz"], ["safety"], 0),
    ("violence_interruption", "Violence interruption (GRYD-style)", "Streets & safety", "value", "limited", ["gryd", "schwartz"], ["safety"], 1),
    ("bid", "Business improvement district (cleaning, ambassadors)", "Streets & safety", "value", "moderate (crime) / modeled (value)", ["bid", "schwartz"], ["safety", "litter"], 1),
    ("litter", "Weekly litter and illegal-dumping cleanup", "Clean streets", "qol", "moderate (litter) / not measured (value)", ["litter"], ["litter"], 0),
    ("graffiti", "Fast graffiti removal", "Clean streets", "value", "modeled", ["gibbons"], ["litter"], 0),
    ("encampment", "Housing-first outreach for encampments", "Clean streets", "value", "limited", ["bhandari"], ["safety", "litter"], 1),
    ("blight_rehab", "Rehab or replace blighted homes", "Housing", "value", "strong", ["ganduri"], ["blight"], 2),
    ("affordable_housing", "Affordable housing on underused land", "Housing", "value", "moderate", ["lihtc"], ["housing"], 3),
    ("adu", "Add a backyard home (ADU), owner-level", "Housing", "owner", "strong", ["adu"], [], 1),
    ("solar", "Rooftop solar, owner-level", "Energy", "owner", "moderate", ["solar"], [], 0),
    ("undergrounding", "Underground the overhead power lines", "Energy", "value", "moderate", ["ladwp", "mcnair"], ["outage"], 2),
    ("ev_hub", "EV fast-charging hub", "Energy", "value", "moderate (possibly overstated)", ["ev"], ["ev"], 1),
    ("microgrid", "Solar + battery resilience hub", "Energy", "qol", "limited", ["microgrid"], ["outage", "heat"], 0),
    ("noise_wall", "Freeway sound wall", "Environment", "value", "strong", ["moretti"], ["noise"], 0),
    ("freeway_cap", "Freeway cap park (regional project, local share)", "Environment", "regional", "limited", ["cap", "crompton"], ["noise", "parks"], 5),
    ("school_filters", "Air filters in classrooms near freeways", "Environment", "qol", "moderate", ["filters"], ["kids", "noise"], 0),
    ("school_bond", "School modernization (bond-funded)", "Schools & services", "value", "strong", ["cellini"], ["kids"], 3),
    ("library", "Library upgrade and longer hours", "Schools & services", "qol", "moderate (use) / none (value)", ["library"], ["kids"], 0),
    ("clinic", "Community health clinic", "Schools & services", "qol", "moderate", ["clinic"], ["health"], 0),
    ("grocery", "Attract a full grocery store", "Amenities & economy", "value", "moderate", ["grocery"], ["food"], 1),
    ("main_street", "Main-street revival (facade grants, small-business help)", "Amenities & economy", "value", "limited", ["retail", "bid"], ["economy"], 2),
    ("outdoor_dining", "Outdoor dining and parklets", "Amenities & economy", "qol", "moderate (business) / not measured (value)", ["parklet"], ["economy"], 0),
    ("farmers_market", "Weekly farmers market", "Amenities & economy", "value", "limited", ["market"], ["food"], 1),
    ("upzone_transit", "Allow more homes near transit (SB 79 / TOC zoning)", "Zoning", "policy", "moderate", ["upzone"], ["housing"], 3),
]
CATALOG = {c[0]: dict(zip(("id", "name", "category", "kind", "evidence", "sources", "qol", "years"), c)) for c in CAT}


def load():
    def rd(name):
        p = SRC / f"{name}.csv"
        return pd.read_csv(p, dtype={"GEOID": str}) if p.exists() else None
    d = rd("bg_attributes")
    if d is None:
        raise SystemExit("county data not built yet")
    status = {}
    for name in ("bg_osm", "bg_transit", "bg_crime", "bg_311", "bg_crashes", "bg_trees", "bg_parcels"):
        x = rd(name)
        status[name] = x is not None
        if x is not None:
            d = d.merge(x, on="GEOID", how="left")
    sales = None
    if (SRC / "sales.csv.gz").exists():
        sales = pd.read_csv(SRC / "sales.csv.gz", dtype={"GEOID": str, "usecode": str})
    st = {}
    for p in SRC.glob("status_*.json"):
        st.update(json.loads(p.read_text())["sources"])
    return d, sales, status, st


def refine_names(d):
    """Inside cities with no neighborhood map, name block groups for the nearest OSM / city neighborhood label,
    else the nearest named park ("Around X Park"), else the city."""
    import geopandas as gpd
    bgp = SRC / "map_block_groups.geojson"
    generic = d.hood_source.str.contains("Statistical Area|City boundary", na=True) & (d.hood == d.city)
    if not bgp.exists() or not generic.any():
        return d
    bg = gpd.read_file(bgp).set_index("GEOID").loc[d.GEOID[generic]]
    pts = gpd.GeoDataFrame(geometry=bg.to_crs(3310).geometry.representative_point(), crs=3310).reset_index()
    got = pd.Series(dtype=str)
    labs = [gpd.read_file(SRC / f) for f in ("map_labels_city.geojson", "map_places.geojson") if (SRC / f).exists()]
    if labs:
        lab = pd.concat([x[["label", "geometry"]] for x in labs], ignore_index=True)
        lab = gpd.GeoDataFrame(lab, geometry="geometry", crs=4326).to_crs(3310)
        lab = lab[lab.label.notna()]
        j = gpd.sjoin_nearest(pts, lab, max_distance=700, how="left").drop_duplicates("GEOID").set_index("GEOID")
        got = j.label.dropna()
        m = d.GEOID.isin(got.index)
        d.loc[m, "hood"] = d.loc[m, "GEOID"].map(got)
        d.loc[m, "hood_source"] = "nearest neighborhood label (OpenStreetMap / city map)"
    left = generic & ~d.GEOID.isin(got.index)
    if left.any() and (SRC / "map_parks.geojson").exists():
        pk = gpd.read_file(SRC / "map_parks.geojson")
        pk = pk[pk["name"].notna() & (pk.acres >= 1.5)].to_crs(3310)
        p2 = pts[pts.GEOID.isin(d.GEOID[left])]
        j = gpd.sjoin_nearest(p2, pk[["name", "geometry"]], max_distance=600, how="left").drop_duplicates("GEOID").set_index("GEOID")
        got2 = j["name"].dropna()
        m = d.GEOID.isin(got2.index)
        d.loc[m, "hood"] = "Around " + d.loc[m, "GEOID"].map(got2)
        d.loc[m, "hood_source"] = "nearest named park (no neighborhood map for this city)"
    return d


def home_values(d, sales):
    """Typical owner-home value: recorded sales (2022-24) beat the Census median, which tops out at $2M."""
    acs = d.median_home_value
    d["acs_topcoded"] = acs >= 2_000_000
    v, src = acs.copy(), pd.Series("Census ACS median (owner estimate)", index=d.index)
    if sales is not None:
        s = sales[sales.usecode.astype(str).str.startswith("01") & sales.price.between(150_000, 40_000_000) & sales.GEOID.notna()]
        bg = s.groupby("GEOID").price.agg(["median", "size"])
        tr = s.assign(t=s.GEOID.str[:11]).groupby("t").price.agg(["median", "size"])
        m_bg = d.GEOID.map(bg["median"].where(bg["size"] >= 5))
        m_tr = d.GEOID.str[:11].map(tr["median"].where(tr["size"] >= 8))
        n_bg = d.GEOID.map(bg["size"]).fillna(0)
        use_bg, use_tr = m_bg.notna(), m_bg.isna() & m_tr.notna()
        v = v.where(~use_bg, m_bg).where(~use_tr, m_tr)
        src = src.where(~use_bg, "median of " + n_bg.astype(int).astype(str) + " recorded home sales here, 2022-24 (County Assessor)")
        src = src.where(~use_tr, "median of recorded home sales in the surrounding Census tract, 2022-24")
        # Census medians stop at $2M: if no sales, keep $2M as a floor and say so
        src = src.where(~(d.acs_topcoded & ~use_bg & ~use_tr), "Census median (capped at $2M+; true value higher)")
    d["home_value"], d["value_source"] = v, src
    rent_val = d.median_gross_rent * 12 / 0.045  # rental unit value at a 4.5% gross yield
    own = d.owner_units.fillna(0)
    rent = (d.occupied_units - d.owner_units).clip(lower=0).fillna(0)
    rv = rent_val.where(rent_val.notna(), d.home_value * 0.55).clip(upper=d.home_value * 0.9)
    d["unit_value"] = ((own * d.home_value + rent * rv) / (own + rent).replace(0, np.nan)).fillna(d.home_value)
    return d


def prep(d, crime_agencies):
    d["area_km2"] = d.aland_m2 / 1e6
    d["homes"] = d.housing_units.fillna(0)
    d["density"] = d.homes / d.aland_m2.replace(0, np.nan)  # homes per m2
    d["sf_share"] = ((d.units_sf_detached.fillna(0) + d.units_sf_attached.fillna(0)) / d.homes.replace(0, np.nan)).clip(0, 1)
    d["pop_n"] = d.population.fillna(0)
    d["kids_share"] = d.children_under18 / d.pop_n.replace(0, np.nan)
    d["no_car_share"] = (d.owner_no_vehicle.fillna(0) + d.renter_no_vehicle.fillna(0)) / d.occupied_units.replace(0, np.nan)
    d["other_vacant_rate"] = d.vacant_other_units / d.homes.replace(0, np.nan)
    has = lambda a: any(a in k for k in crime_agencies)  # noqa: E731
    city = d.city.fillna("")
    lapd, lasd, sm = has("LAPD"), has("LASD"), has("Santa Monica")
    d["crime_covered"] = ((city == "Los Angeles") & lapd) | ((city == "Santa Monica") & sm) | ((~city.isin(OWN_POLICE)) & lasd)
    for c in ("crimes", "violent_crimes", "property_crimes"):
        if c not in d:
            d[c] = np.nan
        d[c] = d[c].where(~d.crime_covered, d[c].fillna(0)).where(d.crime_covered)
    # per 1,000 residents, with a floor so near-empty commercial block groups don't explode
    base = np.maximum(d["pop_n"], 400) / 1000
    d["violent_per_1k"] = d.violent_crimes / base
    d["property_per_1k"] = d.property_crimes / base
    for c in ("illegal_dumping", "graffiti", "streetlight", "encampment", "requests_total"):
        if c not in d:
            d[c] = np.nan
    d["in_311"] = d.requests_total.fillna(0) > 0
    for c in ("crashes", "crashes_ksi", "crashes_ped_bike"):
        if c not in d:
            d[c] = np.nan
    # county reference points
    ref = {"value": d.home_value.median(), "income": d.median_household_income.median(),
           "violent": d.loc[d.crime_covered, "violent_per_1k"].median(), "other_vacant": d.other_vacant_rate.median()}

    def pct(s, invert=False):
        r = s.rank(pct=True)
        return (1 - r) if invert else r
    need = pd.DataFrame(index=d.index)
    need["heat"] = pct(d.avg_temp if "avg_temp" in d else pd.Series(np.nan, index=d.index))
    need["parks"] = pct(d.park_acres_half_mile, invert=True) if "park_acres_half_mile" in d else 0.5
    need["kids"] = pct(d.kids_share)
    need["safety"] = pct(d.violent_per_1k)
    need["traffic"] = pct(d.crashes_ksi / d.area_km2.clip(lower=0.05))
    need["litter"] = pct((d.illegal_dumping + d.graffiti) / d.area_km2.clip(lower=0.05))
    need["transit"] = pct(d.no_car_share)
    need["walk"] = pct(d.res_street_km / d.area_km2.clip(lower=0.05)) if "res_street_km" in d else 0.5
    need["rec"] = pct(d.get("tennis_nearest_m", pd.Series(np.nan, index=d.index)))
    need["food"] = pct(d.get("grocery_nearest_m", pd.Series(np.nan, index=d.index)))
    need["blight"] = pct(d.other_vacant_rate)
    need["housing"] = pct(d.median_gross_rent / d.median_household_income.replace(0, np.nan))
    need["outage"] = pct(-d.median_year_built)
    need["ev"] = pct(d.get("ev_charger_nearest_m", pd.Series(np.nan, index=d.index)))
    need["noise"] = pct(-d.get("freeway_nearest_m", pd.Series(np.nan, index=d.index)))
    need["health"] = pct(d.families_below_poverty / d.families.replace(0, np.nan))
    need["economy"] = pct(d.get("dining_within_400m", pd.Series(np.nan, index=d.index)))
    return d, ref, need.fillna(0.5)


def reach(r, density, homes):
    """Homes within r meters of a project, using the block group's density, capped at the block group's homes x 1.5."""
    return float(min(density * math.pi * r * r, max(homes, 1) * 1.5)) if density == density else 0.0


def land_psf(r):
    """Land value per sq ft: 60% of home value spread over its share of land, or the Assessor's roll value for
    vacant lots here if higher (roll values lag the market under Prop 13, so they only ever raise the estimate)."""
    units_per_acre = max(r.homes / max(r.aland_m2 / 4046.86, 0.1), 0.5) * 1.35  # gross -> net residential land
    est = 0.6 * r.home_value * units_per_acre / 43560
    roll = r.get("vacant_land_psf_median", np.nan)
    if roll == roll and roll is not None:
        est = max(est, roll)
    return float(np.clip(est, 15, 600))


def g(r, k, default=np.nan):
    v = r.get(k, default)
    return default if v is None or (isinstance(v, float) and math.isnan(v)) else v


def size_projects(r, ref, tree_rate):
    """Return {id: project dict} for every improvement that applies to this block group."""
    P = {}
    H, dens, V = r.homes, r.density, r.unit_value
    if not (H >= 20 and V == V and V > 0):
        return P
    poor = g(r, "median_household_income", ref["income"]) < ref["income"]
    res_km = g(r, "res_street_km", 0)
    heat = g(r, "temp_diff_f", 0)

    def add(pid, n, project, homes, pct, capex, om=0.0, land=0.0, why="", fit=1.0):
        if n <= 0 or capex + om + land <= 0:
            return
        P[pid] = dict(n=n, project=project, homes=homes, pct=pct, capex=capex, om=om, land=land, why=why, fit=fit)

    # --- street trees: sized to the city's surveyed open sites, else estimated from the canopy gap
    sites = g(r, "vacant_tree_sites", np.nan)
    inv = isinstance(r.get("tree_inventory_src"), str) and g(r, "street_trees", 0) > 20
    if inv:
        n, how = int(sites or 0), f"{int(sites or 0)} open planting sites in the city's tree survey"
    else:
        n = int(round(res_km * tree_rate(g(r, "tc_gap", np.nan))))
        how = f"~{n} open sites estimated from the canopy gap (no city tree survey here)"
    n = min(n, 3000)
    if n >= 5:
        hn = max(1.0, dens * math.pi * 50 ** 2 * 0.5)
        add("street_trees", n, f"{n:,} street trees", n * hn, TREE_50M_PCT / 100, 1945 * n, 65 * n,
            why=f"{how}; each tree lifts ~{hn:.0f} homes within 50 m by {TREE_50M_PCT}% (local sales estimate, low end)")

    # --- schoolyard greening
    if g(r, "school_nearest_m") < 400 and (g(r, "tc_gap", 0) > 15 or heat > 1):
        add("schoolyard_green", 1, "1 campus, ~1 acre of asphalt replaced", reach(400, dens, H), 0.01, 1_500_000, 15_000,
            why="public school within 400 m in a hot, low-canopy area; open after hours as a park", fit=0.8)

    # --- blight: vacant lots (Assessor vacant parcels) and long-vacant homes, only below county median values and incomes
    ov = g(r, "vacant_other_units", 0)
    vlots = g(r, "vacant_parcels", np.nan)
    low = r.home_value < ref["value"] and poor
    if low and vlots == vlots and vlots >= 2:
        lots = int(min(15, vlots))
        add("vacant_lot_green", lots, f"{lots} vacant lots cleaned and greened", lots * reach(150, dens, H) / max(1, lots ** 0.5), 0.043,
            2400 * lots, 480 * lots, why=f"{int(vlots)} small vacant parcels on the Assessor roll; values and incomes below county median")
    if low and g(r, "other_vacant_rate", 0) > max(2 * ref["other_vacant"], 0.05) and ov >= 8:
        houses = int(min(8, max(1, ov * 0.2)))
        add("blight_rehab", houses, f"{houses} homes rehabbed", houses * reach(150, dens, H) / max(1, houses ** 0.5), 0.023,
            110_000 * houses, why=f"{int(ov)} long-term vacant homes (Census 'other vacant'); rehab lifts neighbors' values (land-value gains of $2-6 per $1 in Richmond)",
            fit=0.4)

    # --- community garden
    if g(r, "community_garden_nearest_m") > 800 and dens > 0.0015:
        pct = 0.015 if poor else 0.005
        if not g(r, "vacant_parcels", 0) > 0:
            pct *= 0.7  # no vacant lot here: land must be bought and cleared
        add("community_garden", 1, "6,000 sq ft garden", reach(300, dens, H), pct, 400_000, 10_000, land=6000 * land_psf(r),
            why=f"no community garden within 800 m; {'below' if poor else 'above'}-median income (effect is larger in poorer areas)")

    # --- pocket park (park-poor, dense)
    pn = g(r, "park_nearest_m")
    if pn > 600 and dens > 0.0012:
        crime_pen = 0.7 if g(r, "violent_per_1k", 0) > 2 * (ref["violent"] or 99) else 1.0
        add("pocket_park", 1, "0.25-acre pocket park", reach(150, dens, H), 0.03 * crime_pen, 850_000, 25_000, land=10_890 * land_psf(r),
            why=f"nearest park {pn:,.0f} m away; dense" + ("; reduced for high violent crime" if crime_pen < 1 else ""))
    if pn < 400:
        add("park_upgrade", 1, "new playground and paths at the nearest park", reach(400, dens, H), 0.01, 760_000, 0,
            why=f"park {pn:,.0f} m away; renovations capitalize within ~400 m", fit=0.8)

    # --- recreation facilities (quality-of-life items; value not measured)
    if g(r, "pickleball_nearest_m") > 2000 and g(r, "tennis_nearest_m") < 1200:
        add("pickleball", 1, "1 tennis court → 4 pickleball courts", reach(800, dens, H), 0, 110_000, 2_000,
            why=f"no pickleball within 2 km; tennis courts {g(r, 'tennis_nearest_m', 0):,.0f} m away")
    if g(r, "tennis_nearest_m") > 2500 and pn < 800:
        add("tennis", 2, "2 tennis courts in the nearest park", reach(800, dens, H), 0, 260_000, 4_000,
            why=f"nearest public tennis court {g(r, 'tennis_nearest_m', 0):,.0f} m away")
    if g(r, "basketball_nearest_m") > 1500 and pn < 800:
        add("basketball", 1, "1 full court", reach(800, dens, H), 0, 580_000, 3_000,
            why=f"nearest public basketball court {g(r, 'basketball_nearest_m', 0):,.0f} m away")
    if g(r, "dog_park_nearest_m") > 2000 and dens > 0.0025:
        add("dog_park", 1, "0.5-acre dog park in an existing park", reach(400, dens, H), 0.005, 350_000, 15_000,
            why=f"nearest dog park {g(r, 'dog_park_nearest_m', 0)/1609:,.1f} mi away; dense area")
    if g(r, "pool_nearest_m") > 3000 and dens > 0.002:
        add("pool", 1, "1 public pool", reach(2000, dens, H), 0, 20_000_000, 1_000_000,
            why=f"nearest public pool {g(r, 'pool_nearest_m', 0)/1609:,.1f} mi away")
    if heat > 1 and g(r, "playground_nearest_m") < 800:
        add("splash_pad", 1, "1 splash pad at the nearest playground", reach(800, dens, H), 0, 850_000, 40_000,
            why=f"{heat:+.1f}°F hotter than average; playground nearby")
    if g(r, "skatepark_nearest_m") > 4000 and g(r, "kids_share", 0) > 0.2:
        add("skate_park", 1, "1 neighborhood skate park", reach(1500, dens, H), 0, 1_500_000, 40_000,
            why=f"nearest skate park {g(r, 'skatepark_nearest_m', 0)/1609:,.1f} mi away; many kids")
    if g(r, "sports_field_nearest_m") > 2000 and pn < 1000:
        add("sports_field", 1, "1 natural-grass field", reach(1500, dens, H), 0, 550_000, 25_000,
            why=f"nearest public field {g(r, 'sports_field_nearest_m', 0)/1609:,.1f} mi away")
    if g(r, "community_centre_nearest_m") > 2500 and poor:
        add("rec_center", 1, "1 recreation center", reach(2000, dens, H), 0, 8_400_000, 400_000,
            why=f"no community or rec center within {g(r, 'community_centre_nearest_m', 0)/1609:,.1f} mi")
    if pn < 500 and g(r, "toilets_nearest_m") > 800:
        add("restroom", 1, "restroom building + fountains", reach(800, dens, H), 0, 990_000, 60_000, why="park nearby has no mapped public restroom")

    # --- greening for heat
    if heat > 1.5 and poor and dens > 0.002:
        add("green_alley", 1, "~0.25 mile of alleys", reach(200, dens, H), 0, 2_400_000, 10_000, why=f"{heat:+.1f}°F hotter than average")
        add("cool_pavement", 1, "~1 lane-mile coated", reach(200, dens, H), 0, 250_000, 0, why=f"{heat:+.1f}°F hotter than average; cools surfaces, not always people")

    # --- transit
    tph = g(r, "bus_max_tph_400m", 0)
    rail_m = min(g(r, "rail_stop_nearest_m"), g(r, "rail_station_nearest_m"))
    if tph >= 12 and rail_m > 800:
        add("bus_lane", 1, "0.5 mile of peak bus lanes (both directions)", reach(400, dens, H), 0.01, 1_000_000, 20_000,
            why=f"{tph:.0f} buses an hour at the busiest nearby stop (7-9am); no rail within 800 m")
    if tph >= 15 and rail_m > 1500:
        add("brt", 1, "0.5 mile of BRT corridor (local share)", reach(800, dens, H), 0.05, 7_500_000, 100_000,
            why=f"{tph:.0f} buses an hour; nearest rail {rail_m/1609:,.1f} mi away")
    if rail_m > 2000 and dens > 0.004 and tph >= 10:
        add("rail_station", 1, "this area's share of a new station", reach(800, dens, H), 0.042, 40_000_000, 300_000,
            why=f"dense area {rail_m/1609:,.1f} mi from rail with busy bus service; a station costs ~$300M+ shared across ~8 block groups")
    if tph >= 8 and heat > 0.5:
        add("bus_shelters", 4, "4 shelters with shade", reach(400, dens, H), 0, 4 * 180_842, 4 * 2_500, why=f"{tph:.0f} buses an hour; hot")

    # --- streets
    ksi, pb = g(r, "crashes_ksi", 0), g(r, "crashes_ped_bike", 0)
    if res_km > 1 and r.sf_share > 0.3:
        humps = int(max(2, res_km * 2))
        add("traffic_calming", humps, f"{humps} speed humps", H * r.sf_share * 0.4, 0.01, 5958 * humps, 0,
            why=f"{res_km:.1f} km of residential streets; calming that cuts through-traffic ~16% adds ~1% on treated streets", fit=0.7)
    if pb >= 2:
        k = int(min(8, pb))
        add("crosswalks", k, f"{k} intersections upgraded", reach(300, dens, H), 0, 58_000 * k, 0,
            why=f"{int(pb)} pedestrian or bike crashes recorded here")
    if ksi >= 2:
        add("road_diet", 1, "~1 mile road diet (local share)", reach(400, dens, H), 0, 600_000, 10_000, why=f"{int(ksi)} fatal or severe crashes recorded here")
    if res_km > 0.5:
        sq = res_km * 3280
        add("sidewalks", 1, f"~{sq:,.0f} sq ft of broken sidewalk (10% of walks)", H, 0, 51 * sq, 0, why="LA's sidewalks are ~40% damaged citywide; local survey not loaded")

    # --- safety (only where crime data cover this block group)
    if r.crime_covered and r.violent_per_1k == r.violent_per_1k:
        vrel = r.violent_per_1k / max(ref["violent"], 0.1)
        if vrel > 1.5 or g(r, "streetlight", 0) > 10:
            m = res_km * 1000 * 0.3
            v_drop = 0.36 * 0.3
            add("street_lighting", 1, f"~{m/1000:.1f} km of streets relit", H * 0.5, EL_VIOLENT * v_drop + EL_PROPERTY * v_drop,
                656 * m, 12 * m, why=f"violent crime {vrel:.1f}x the county median; lighting cuts nighttime outdoor crime 36% (~30% of crime)")
        if vrel > 2:
            add("cameras", 10, "10 cameras at hot spots", H * 0.25, EL_VIOLENT * 0.13 + EL_PROPERTY * 0.13, 81_480, 87_000,
                why=f"violent crime {vrel:.1f}x county median; CCTV cuts crime ~13% in view")
        if vrel > 2.5:
            add("foot_patrol", 1, "2 officers on foot, 10 years", H, EL_VIOLENT * 0.23, 0, 400_000,
                why=f"violent crime {vrel:.1f}x county median; foot patrols cut violent crime 23% while they run")
            add("violence_interruption", 1, "street outreach team (local share), 10 years", H, EL_VIOLENT * 0.05, 0, 70_000,
                why=f"violent crime {vrel:.1f}x county median")
        if g(r, "dining_within_400m", 0) >= 10:
            add("bid", 1, "BID cleaning + ambassadors (local share)", reach(400, dens, H), EL_VIOLENT * 0.12 * 0.3, 0, 250_000,
                why=f"{int(g(r, 'dining_within_400m', 0))} restaurants/cafes within 400 m; LA BIDs cut robbery 12%")
    # --- clean streets (City of LA 311)
    if r.in_311:
        dump, graf, enc = g(r, "illegal_dumping", 0), g(r, "graffiti", 0), g(r, "encampment", 0)
        dd = dump / max(r.area_km2, 0.05)
        if dd > 200:
            add("litter", 1, "weekly cleanup crew (local share)", H, 0, 0, 60_000, why=f"{int(dump)} dumping/litter reports a year ({dd:,.0f} per km²)")
        gd = graf / max(r.area_km2, 0.05)
        if gd > 50:
            pct = min(0.015, 0.00031 * 0.5 * gd / 10)
            add("graffiti", 1, "48-hour graffiti removal", H, pct, 0, max(5_000, 123_000 * graf / 3000),
                why=f"{int(graf)} graffiti reports a year ({gd:,.0f} per km²); assumes 1 in 10 reports is a criminal-damage incident (Gibbons)")
        if enc >= 25:
            add("encampment", 1, "outreach + housing for ~10 people, 10 years", reach(320, dens, H), 0.0141 * 0.5, 0, 300_000,
                why=f"{int(enc)} encampment reports a year; homes within 0.2 mi sell ~1.4% lower (counts a 50% success rate)")

    # --- housing
    if poor and r.home_value < ref["value"]:
        add("affordable_housing", 50, "50 affordable homes", reach(160, dens, H), 0.065, 30_000_000, 0,
            why="below-median income area: new affordable housing raised nearby prices 6.5% within 0.1 mi")
    P_owner_v = r.home_value
    if r.sf_share > 0.4:
        add("adu", 1, "1 ADU on a typical lot", 1, 0.092, 130_000, 0, why=f"single-family area; typical home {P_owner_v/1e6:.2f}M")
        add("solar", 1, "6 kW system", 1, 6000 * 4 / max(P_owner_v, 1), 17_700, 0, why="owned solar sells for ~$4/W more")

    # --- energy
    yb = g(r, "median_year_built", 2000)
    if yb <= 1975 and r.sf_share > 0.3 and res_km > 0.5:
        miles = res_km * 0.621
        add("undergrounding", 1, f"{miles:.1f} miles of lines undergrounded", H, 0.029, 2_800_000 * miles, 0,
            why=f"homes built ~{int(yb)} (overhead lines likely); LADWP target $2.8M per circuit-mile")
    if g(r, "ev_charger_within_800m", 1) == 0 and dens > 0.002:
        add("ev_hub", 1, "8-port fast-charging hub", reach(500, dens, H), 0.01, 800_000, 40_000,
            why="no public charger mapped within 800 m; uses 1% (the study's +3.3% is likely partly where chargers get built)")
    if heat > 1 and poor:
        add("microgrid", 1, "1 resilience hub (solar + battery)", reach(1500, dens, H), 0, 3_400_000, 30_000, why=f"{heat:+.1f}°F hotter; cooling center during outages")

    # --- environment
    fw = g(r, "freeway_m_within_150m", 0)
    walls = g(r, "noise_wall_m", 0)
    open_fw = max(0.0, fw - walls)
    if open_fw > 150:
        homes100 = min(H, dens * open_fw * 100)
        add("noise_wall", 1, f"{open_fw:,.0f} m of sound wall", homes100, 0.068, 2485 * open_fw, 5_000,
            why=f"{open_fw:,.0f} m of freeway within 150 m without a mapped wall; walls add ~6.8% within 100 m")
    if fw > 400 and dens > 0.005 and r.home_value > ref["value"]:
        add("freeway_cap", 1, "this area's share of a cap park", reach(400, dens, H), 0.05, 50_000_000, 200_000,
            why="dense, valuable area along a freeway; caps cost $110M-250M+")
    if g(r, "freeway_nearest_m") < 500 and g(r, "school_nearest_m") < 500:
        add("school_filters", 30, "30 classrooms", reach(500, dens, H), 0, 30_000, 6_000, why="school within 500 m of a freeway")

    # --- schools & services
    if g(r, "school_nearest_m") < 800 and yb <= 1970:
        homes = reach(800, dens, H)
        cost = homes * r.home_value * 0.06 / 1.5  # Cellini: >= $1.50 of value per $1 of school capital
        add("school_bond", 1, "modernize the nearby school (local share)", homes, 0.06, cost, 0,
            why="older area served by a nearby public school; California bond passage raised prices ~6%")
    if g(r, "library_nearest_m") > 2000 and dens > 0.002:
        add("library", 1, "branch upgrade + Sunday hours, 10 years", reach(2000, dens, H), 0, 2_000_000, 250_000, why="no library within 2 km")
    if g(r, "clinic_nearest_m") > 2500 and poor:
        add("clinic", 1, "1 community clinic", reach(3000, dens, H), 0, 5_000_000, 0, why="no clinic mapped within 2.5 km; below-median income")

    # --- amenities & economy
    if g(r, "grocery_nearest_m") > 1600 and dens > 0.002:
        add("grocery", 1, "1 supermarket (incentive package)", reach(800, dens, H), 0.04, 2_000_000, 0,
            why=f"nearest supermarket {g(r, 'grocery_nearest_m', 0)/1609:,.1f} mi away")
    din = g(r, "dining_within_400m", 0)
    if 2 <= din <= 15 and g(r, "nightlife_within_400m", 0) <= 3:
        add("main_street", 1, "10 facade grants + small-business help", reach(400, dens, H) * r.sf_share, 0.01, 750_000, 150_000,
            why=f"{int(din)} restaurants/cafes within 400 m: a corridor that could grow (single-family homes gain; condos can lose)")
    if din >= 8:
        add("outdoor_dining", 5, "5 parklets", reach(400, dens, H), 0, 125_000, 5_000, why=f"{int(din)} restaurants/cafes within 400 m")
    if g(r, "market_nearest_m") > 2000 and dens > 0.003:
        add("farmers_market", 1, "weekly market, 10 years", reach(800, dens, H), 0.005, 0, 40_000, why="no market mapped within 2 km")

    # --- zoning (policy: almost no public cost)
    if (rail_m < 800 or tph >= 15) and r.sf_share > 0.5:
        add("upzone_transit", 1, "rezone single-family lots near transit", H * r.sf_share, 0.03, 300_000, 0,
            why="single-family lots near rail or frequent bus; land value rises 3-5% (owners gain; some neighbors object)")
    return P


def tree_rate_fn(d):
    """Open street-tree sites per km of residential street vs. canopy gap, learned where inventories exist."""
    inv = d[d.tree_inventory_src.notna() & (d.get("street_trees", 0) > 20) & (d.res_street_km > 0.3)] if "tree_inventory_src" in d else d.iloc[0:0]
    if len(inv) < 50 or "tc_gap" not in d:
        return lambda gap: 15.0, {"n": len(inv)}
    inv = inv.assign(rate=inv.vacant_tree_sites / inv.res_street_km, q=pd.qcut(inv.tc_gap.rank(method="first"), 5, labels=False))
    tab = inv.groupby("q").agg(gap=("tc_gap", "median"), rate=("rate", "median"))
    xs, ys = tab.gap.values, tab.rate.values

    def f(gap):
        if gap != gap:
            return float(np.median(ys))
        return float(np.interp(gap, xs, ys))
    return f, {"n": int(len(inv)), "gap": [round(float(x), 1) for x in xs], "sites_per_km": [round(float(y), 1) for y in ys]}


def score():
    d, sales, status, st = load()
    if "tc_gap" in d and d.tc_gap.max() <= 1.5:
        d["tc_gap"] = d.tc_gap * 100  # Tree Equity stores the canopy gap as a fraction
    d = refine_names(d)
    d = home_values(d, sales)
    agencies = list((st.get("crime", {}) or {}).get("rows_by_agency", {}).keys())
    d, ref, need = prep(d, agencies)
    if "avg_temp" in d:
        d["temp_diff_f"] = d.avg_temp - d.avg_temp.median()
    tree_rate, tree_cal = tree_rate_fn(d)
    rows, details = [], {}
    for i, r in d.iterrows():
        P = size_projects(r, ref, tree_rate)
        recs = []
        for pid, p in P.items():
            c = CATALOG[pid]
            cost = p["capex"] + p["land"] + p["om"] * PV10
            ramp = 1 / 1.03 ** c["years"]
            value = p["homes"] * r.unit_value * p["pct"] * ramp * p["fit"] if pid not in ("adu", "solar") else r.home_value * p["pct"]
            qol = max([need.at[i, q] for q in c["qol"]], default=0)
            recs.append({"id": pid, "project": p["project"], "homes": round(p["homes"]), "cost": round(cost), "capex": round(p["capex"]),
                         "land": round(p["land"]), "om": round(p["om"]), "value": round(value), "vpd": round(value / cost, 3) if cost else 0,
                         "pct": round(p["pct"] * 100, 3), "why": p["why"], "qol": round(float(qol), 2)})
        val = sorted([x for x in recs if CATALOG[x["id"]]["kind"] in ("value", "regional")], key=lambda x: -x["vpd"])
        top = next((x for x in val if CATALOG[x["id"]]["kind"] == "value"), None)
        pkg = [x for x in val if x["vpd"] >= 1 and CATALOG[x["id"]]["kind"] == "value"]
        details[r.GEOID] = {"recs": recs}
        rows.append({"GEOID": r.GEOID, "top": top["id"] if top and top["vpd"] >= 1 else None, "top_vpd": top["vpd"] if top else None,
                     "pkg_cost": sum(x["cost"] for x in pkg), "pkg_value": sum(x["value"] for x in pkg), "pkg_n": len(pkg)})
    sc = pd.DataFrame(rows)
    d = d.merge(sc, on="GEOID", how="left")
    OUT.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT / "bg_scored.csv", index=False)
    (OUT / "details.json").write_text(json.dumps(details, separators=(",", ":")))
    meta = {"ref": {k: (None if v != v else float(v)) for k, v in ref.items()}, "tree_calibration": tree_cal, "tree_pct": TREE_50M_PCT,
            "elasticities": {"violent": EL_VIOLENT, "property": EL_PROPERTY}, "pv10": PV10, "status": status,
            "catalog": {k: {**v, "sources": [S[s] for s in v["sources"]]} for k, v in CATALOG.items()},
            "pipeline": st}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1, default=str))
    pd.DataFrame([{**{k: v for k, v in c.items() if k != "sources"}, "sources": " | ".join(S[s] for s in c["sources"])} for c in CATALOG.values()]).to_csv(
        ROOT / "data" / "interventions_v2.csv", index=False)
    print(f"{len(d):,} block groups; top counts:\n{sc.top.value_counts().head(20)}")
    print("median top value per $1:", sc.top_vpd.median())
    return d


if __name__ == "__main__":
    score()
