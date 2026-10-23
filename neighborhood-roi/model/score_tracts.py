"""Score every tract in data/derived/tract_metrics.csv and write the map's data files.

    python3 model/score_tracts.py

Reads the evidence library (data/interventions.csv), real tract metrics from the
pipeline, regional costs, and hand-researched local notes. Writes per-county
files to web/data/: tracts_<fips>.geojson (shapes + map metrics) and
details_<fips>.json (full ranking with the math, per tract).
"""
import csv
import json
import math
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DERIVED = DATA / "derived"
WEB = ROOT / "web" / "data"
WEB.mkdir(parents=True, exist_ok=True)

DISCOUNT_RATE = 0.05
HORIZON_YRS = 10
ACRE_SQFT = 43560
DISTANCE_DECAY = 1 / 3
FALLBACK_CANOPY_GOAL = 35

PROJECT_UNITS = {
    "street_tree": 100, "vacant_lot_greening": 20, "abandoned_house_fix": 20, "blight_demolition": 10,
    "community_garden": 1, "pocket_park": 1, "green_schoolyard": 1, "street_lighting": 50,
    "sidewalk_walkability": 10, "noise_barrier": 1, "protected_bikeway": 2, "power_undergrounding": 1,
}
LINEAR = {"noise_barrier", "protected_bikeway", "power_undergrounding"}
POCKET_PARK_ACRES = 0.25
GARDEN_ACRES = 0.1

DROP_COLS = {"STATEFP", "COUNTYFP", "NAMELSAD", "ALAND", "hpi_series", "county", "fips", "tes_block_groups",
             "zip_zhvi_date", "osm_neighborhoods"}
COUNTY_METRO = {"06037": "Los Angeles CA", "42101": "Philadelphia PA", "17031": "Chicago IL", "48113": "Dallas TX",
                "26163": "Detroit MI", "13121": "Atlanta GA", "53033": "Seattle WA", "36047": "New York NY",
                "48201": "Houston TX", "18097": "Indianapolis IN"}


def num(v, default=np.nan):
    try:
        f = float(v)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def pv_annuity(amount, years=HORIZON_YRS, r=DISCOUNT_RATE):
    return amount * (1 - (1 + r) ** -years) / r


def time_factor(years):
    """Share of the full effect buyers price in today when it ramps up over `years`."""
    if years <= 0:
        return 1.0
    yrs = int(math.ceil(years))
    return sum((t / yrs) * (1 + DISCOUNT_RATE) ** -t for t in range(1, yrs + 1)) / yrs * 0.5 + 0.5


def load_cost_factors():
    out = {}
    with open(DATA / "regional_cost_factors.csv", newline="") as f:
        approx = {r["metro"]: float(r["cost_factor"]) for r in csv.DictReader(f)}
    bls = DERIVED / "regional_costs_bls.csv"
    bls_df = pd.read_csv(bls, dtype={"county_fips": str}) if bls.exists() else None
    for fips, metro in COUNTY_METRO.items():
        f, src = approx.get(metro, 1.0), "approximate metro index"
        if bls_df is not None:
            row = bls_df[bls_df.county_fips == fips]
            if len(row) and not pd.isna(row.cost_factor.iloc[0]):
                f, src = float(row.cost_factor.iloc[0]), "BLS OEWS 2024 landscaping/construction wages vs national"
        out[fips] = (round(f, 3), src)
    return out


def land_value_per_acre(value, homes_per_acre):
    """Rough residential land value: home value x land share x density."""
    share = min(0.75, max(0.2, 0.15 + 0.3 * math.log10(max(value, 1e5) / 1e5)))
    return value * share * max(homes_per_acre, 1)


def fit_and_reason(iid, t):
    """0-1 share of the published effect this tract can expect, plus a plain-language reason."""
    canopy = t["canopy_pct"]
    goal = t["canopy_goal_pct"] if not np.isnan(t["canopy_goal_pct"]) else FALLBACK_CANOPY_GOAL
    heat = t["temp_diff_f"]
    vac = t["vacancy_rate"]
    park_d = t["nearest_park_m"]
    park_ac = t["park_acres_within_half_mile"]
    inc = t["income_ratio"]
    walk = t["walk_index"]
    if iid == "street_tree":
        gap_pts = t["canopy_gap_pct"]
        if np.isnan(canopy) and np.isnan(gap_pts):
            return 0.5, "Canopy not measured here; assumed an average gap."
        if np.isnan(canopy):
            gap = min(1.0, gap_pts / goal)
            heat_boost = 0.0 if np.isnan(heat) else min(1.0, max(0.0, heat / 8))
            return gap * (0.75 + 0.25 * heat_boost), f"Canopy {gap_pts:.0f} points below the Tree Equity goal" + (f"; {heat:+.1f}° vs. county average" if not np.isnan(heat) else "")
        gap = max(0.0, goal - canopy) / max(goal, 1)
        heat_boost = 0.0 if np.isnan(heat) else min(1.0, max(0.0, heat / 8))
        f = gap * (0.75 + 0.25 * heat_boost)
        return f, f"Canopy {canopy:.0f}% vs a {goal:.0f}% goal" + (f"; {heat:+.1f}°F vs. area average" if not np.isnan(heat) else "")
    if iid in ("vacant_lot_greening", "blight_demolition", "abandoned_house_fix"):
        if np.isnan(vac) or vac < 0.08:
            return 0.0, "Vacancy too low to have many derelict lots."
        f = min(1.0, (vac - 0.05) / 0.15)
        if iid == "abandoned_house_fix":
            f *= 0.8
        return f, f"{vac*100:.0f}% of homes vacant (ACS)"
    if iid == "community_garden":
        if np.isnan(inc):
            return 0.0, "No income data."
        low = 1.0 if inc <= 0.6 else max(0.0, 1 - (inc - 0.6) * 2)
        gap = 1.0 if np.isnan(park_ac) else max(0.0, 1 - park_ac / 10)
        vac_ok = 1.0 if (not np.isnan(vac) and vac >= 0.06) else 0.4
        f = low * gap * vac_ok
        return f, f"Income {inc*100:.0f}% of county median; {0 if np.isnan(park_ac) else park_ac:.1f} park acres within ½ mile"
    if iid == "pocket_park":
        if np.isnan(park_d):
            return 0.3, "Park distance unknown."
        if park_d <= 400 and park_ac >= 2:
            return 0.0, f"Already {park_d:.0f} m from a park."
        f = min(1.0, max(0.0, (park_d - 300) / 700)) * 0.7 + max(0.0, 1 - (park_ac or 0) / 8) * 0.3
        return f, f"Nearest park {park_d:.0f} m away; {park_ac:.1f} park acres within ½ mile"
    if iid == "green_schoolyard":
        heat_part = 0.5 if np.isnan(heat) else min(1.0, max(0.0, (heat + 2) / 8))
        park_part = 0.5 if np.isnan(park_ac) else max(0.0, 1 - park_ac / 10)
        canopy_part = 0.5 if np.isnan(canopy) else max(0.0, 1 - canopy / 30)
        score = t["school_score"]
        school_part = 0.5 if np.isnan(score) else min(1.0, max(0.2, (70 - score) / 50))
        f = 0.3 * heat_part + 0.3 * park_part + 0.2 * canopy_part + 0.2 * school_part
        bits = []
        if not np.isnan(score):
            bits.append(f"nearby schools {score:.0f}% met standards")
        if not np.isnan(canopy):
            bits.append(f"canopy {canopy:.0f}%")
        if not np.isnan(park_ac):
            bits.append(f"{park_ac:.1f} park acres within ½ mile")
        return f, "; ".join(bits) or "Limited data"
    if iid == "street_lighting":
        # no crime layer yet: proxy with poverty + vacancy
        pov = t["poverty_rate"]
        if np.isnan(pov):
            return 0.3, "No crime data yet; poverty proxy unavailable."
        f = min(1.0, max(0.0, (pov - 0.1) / 0.3)) * 0.8 + (0.2 if (not np.isnan(vac) and vac > 0.12) else 0)
        return f, f"Crime data not loaded yet; proxy: {pov*100:.0f}% poverty"
    if iid == "sidewalk_walkability":
        if np.isnan(walk):
            return 0.0, "Walkability not measured."
        f = max(0.0, (12 - walk) / 10)
        return f, f"EPA walkability index {walk:.1f} of 20"
    if iid == "protected_bikeway":
        if np.isnan(walk):
            return 0.3, "Walkability not measured."
        dense = min(1.0, t["homes_per_acre"] / 10)
        f = dense * (0.5 if walk >= 14 else 0.8)
        return f, f"{t['homes_per_acre']:.0f} homes/acre; walk index {walk:.1f}"
    if iid == "noise_barrier":
        fd = t["nearest_freeway_m"]
        if np.isnan(fd) or fd > 400:
            return 0.0, "No freeway within 400 m."
        return 1.0 - fd / 400 * 0.7, f"Freeway {fd:.0f} m away"
    if iid == "power_undergrounding":
        return 1.0, "Applies anywhere with overhead lines."
    return 0.0, ""


def score_tract(t, lib, cost_factor):
    value = t["value_now"]
    homes_total = t["housing_units"]
    hpa = t["homes_per_acre"]
    out = []
    if np.isnan(value) or np.isnan(homes_total) or homes_total < 50:
        return out
    for iid, units in PROJECT_UNITS.items():
        row = lib[iid]
        fit, why = fit_and_reason(iid, t)
        if fit <= 0.02:
            continue
        uplift = float(row["uplift_pct_low"]) / 100
        if iid == "street_tree":
            homes = units * 2
            gain = units * value * (0.03 * 0.5 + 2 * 0.006)
        else:
            r = float(row["radius_ft"])
            if iid in LINEAR:
                area = 2 * r * 5280 * units / ACRE_SQFT * (0.5 if iid == "noise_barrier" else 1)
            else:
                area = math.pi * r * r / ACRE_SQFT * units * (1 if units == 1 else 0.5)
            homes = min(homes_total * 1.5, area * hpa)  # may spill into the neighboring tract
            gain = homes * value * uplift * DISTANCE_DECAY
        gain *= fit * time_factor(float(row["time_to_full_effect_yrs"]))
        unit_cost = (float(row["unit_cost_low_usd"]) + float(row["unit_cost_high_usd"])) / 2
        capex = unit_cost * units * cost_factor
        land = 0.0
        if iid == "pocket_park":
            land = POCKET_PARK_ACRES * land_value_per_acre(value, hpa)
        if iid == "community_garden":
            land = GARDEN_ACRES * land_value_per_acre(value, hpa) * 0.3  # usually a city-owned or donated lot
        maint = pv_annuity(float(row["annual_maint_usd"]) * units * cost_factor)
        cost = capex + land + maint
        out.append({
            "id": iid, "name": row["intervention"], "project": f"{units} {row['unit']}{'s' if units > 1 else ''}",
            "homes": int(round(homes)), "fit": round(fit, 2), "why": why,
            "uplift_pct": float(row["uplift_pct_low"]), "uplift_pct_high": float(row["uplift_pct_high"]),
            "capex": round(capex), "land": round(land), "maint_pv": round(maint), "cost": round(cost),
            "value": round(gain), "vpd": round(gain / cost, 2) if cost else 0,
            "evidence": row["evidence_strength"], "basis": row["uplift_basis"], "sources": row["key_sources"],
        })
    return sorted(out, key=lambda r: r["vpd"], reverse=True)


def write_context(index, geo, parks):
    """Per-county basemap substitutes: parks, major roads, neighborhood labels."""
    roads = gpd.read_file(DERIVED / "osm_roads.geojson") if (DERIVED / "osm_roads.geojson").exists() else None
    pts = gpd.read_file(DERIVED / "osm_points.geojson") if (DERIVED / "osm_points.geojson").exists() else None
    for c in index["counties"]:
        area = geo[geo.GEOID.str.startswith(c["fips"])]
        hull = area.union_all() if hasattr(area, "union_all") else area.unary_union
        ctx = {}
        if parks is not None:
            pk = parks[parks.intersects(hull)].copy()
            pk = pk[pk.to_crs(5070).area > 4000]  # ~1 acre and up
            pk["geometry"] = pk.to_crs(5070).geometry.simplify(12).to_crs(4326)
            ctx["parks"] = json.loads(pk[["name", "geometry"]].to_json(to_wgs84=True, drop_id=True))
        if roads is not None:
            rd = roads[roads.intersects(hull) & roads.kind.isin(["motorway", "trunk", "primary"])].copy()
            rd["geometry"] = rd.to_crs(5070).geometry.simplify(25).to_crs(4326)
            from shapely.ops import linemerge, unary_union
            merged = []
            for k, grp in rd.groupby("kind"):
                g = linemerge(unary_union(list(grp.geometry)))
                parts = list(g.geoms) if hasattr(g, "geoms") else [g]
                merged += [{"k": k, "geometry": x} for x in parts if x.length > 0.0005]
            rd = gpd.GeoDataFrame(merged, geometry="geometry", crs=4326)
            rd["geometry"] = rd.to_crs(5070).geometry.simplify(25).to_crs(4326)
            ctx["roads"] = json.loads(rd.to_json(drop_id=True))
        if pts is not None:
            nb = pts[(pts.kind == "neighborhood") & pts.within(hull)]
            ctx["labels"] = [[n, round(g.y, 5), round(g.x, 5)] for n, g in zip(nb.name, nb.geometry) if isinstance(n, str)]
        txt = json.dumps(ctx, separators=(",", ":"))
        txt = re.sub(r"(\d+\.\d{5})\d+", r"\1", txt)
        (WEB / f"context_{c['fips']}.json").write_text(txt)


def main():
    lib = {r["id"]: r for r in csv.DictReader(open(DATA / "interventions.csv", newline=""))}
    m = pd.read_csv(DERIVED / "tract_metrics.csv", dtype={"GEOID": str, "STATEFP": str, "COUNTYFP": str, "zip": str})
    geo = gpd.read_file(DERIVED / "tracts.geojson")
    geo["GEOID"] = geo.GEOID.astype(str)
    costs = load_cost_factors()
    research = json.loads((DATA / "local_research.json").read_text())

    def col(name):
        return m[name] if name in m else pd.Series(np.nan, index=m.index)

    m["fips"] = m.STATEFP + m.COUNTYFP
    m["homes_per_acre"] = col("housing_units") / col("land_acres").clip(lower=1)
    m["vacancy_rate"] = col("vacant_units") / col("housing_units")
    m["poverty_rate"] = col("people_below_poverty") / col("population")
    m["owner_share"] = col("owner_units") / col("occupied_units")
    county_inc = m.groupby("fips")["median_household_income"].transform("median") if "median_household_income" in m else np.nan
    m["income_ratio"] = col("median_household_income") / county_inc
    # Bring ACS (5-yr, centered ~2 yrs back) up to today with the ZIP's Zillow trend when available.
    acs_mid = None
    adj = []
    for _, r in m.iterrows():
        v = num(r.get("median_home_value"))
        f = 1.0
        s = r.get("zip_zhvi_series")
        if isinstance(s, str) and not np.isnan(v):
            ser = {int(k): x for k, x in json.loads(s).items() if x}
            if ser:
                last = max(ser)
                base_year = last - 3
                if base_year in ser and ser[base_year]:
                    f = ser[last] / ser[base_year]
        adj.append(v * f if not np.isnan(v) else num(r.get("zip_zhvi")))
    m["value_now"] = adj
    sch = col("school_ela_pct_met_near3")
    mat = col("school_math_pct_met_near3")
    m["school_score"] = pd.concat([sch, mat], axis=1).mean(axis=1)
    for c in ("canopy_pct", "canopy_goal_pct", "canopy_gap_pct", "temp_diff_f", "nearest_park_m", "park_acres_within_half_mile",
              "walk_index", "nearest_freeway_m"):
        if c not in m:
            m[c] = np.nan
    for c in ("canopy_pct", "canopy_goal_pct", "canopy_gap_pct"):
        m.loc[m[c] < 0, c] = np.nan  # TES uses negative codes for missing

    index = {"counties": [], "generated_from": "data/derived/tract_metrics.csv"}
    for fips, sub in m.groupby("fips"):
        cf, cf_src = costs.get(fips, (1.0, "default"))
        details, props = {}, []
        for _, r in sub.iterrows():
            t = {k: num(r.get(k)) for k in ("value_now", "housing_units", "homes_per_acre", "canopy_pct", "canopy_goal_pct", "canopy_gap_pct",
                                            "temp_diff_f", "vacancy_rate", "nearest_park_m", "park_acres_within_half_mile",
                                            "income_ratio", "walk_index", "school_score", "poverty_rate", "nearest_freeway_m")}
            recs = score_tract(t, lib, cf)
            nbhds = json.loads(r["osm_neighborhoods"]) if isinstance(r.get("osm_neighborhoods"), str) else []
            top = recs[0] if recs else None
            props.append({"GEOID": r.GEOID, "nb": ", ".join(nbhds[:3]), "top": top["id"] if top else None,
                          "top_vpd": top["vpd"] if top else None,
                          "value": None if np.isnan(t["value_now"]) else round(t["value_now"]),
                          "canopy": None if np.isnan(t["canopy_pct"]) else round(t["canopy_pct"], 1),
                          "gap": None if np.isnan(t["canopy_gap_pct"]) else round(t["canopy_gap_pct"], 1),
                          "heat": None if np.isnan(t["temp_diff_f"]) else round(t["temp_diff_f"], 1),
                          "park_m": None if np.isnan(t["nearest_park_m"]) else int(t["nearest_park_m"]),
                          "vacancy": None if np.isnan(t["vacancy_rate"]) else round(t["vacancy_rate"] * 100, 1),
                          "school": None if np.isnan(t["school_score"]) else round(t["school_score"], 1),
                          "growth10": None if pd.isna(r.get("zip_zhvi_growth_10y_pct")) else round(float(r["zip_zhvi_growth_10y_pct"]), 1),
                          "walk": None if np.isnan(t["walk_index"]) else round(t["walk_index"], 1)})
            raw = {k: (None if (isinstance(v, float) and np.isnan(v)) else (round(v, 2) if isinstance(v, float) else v))
                   for k, v in r.items() if k not in DROP_COLS and not (isinstance(v, float) and np.isnan(v))}
            details[r.GEOID] = {"metrics": raw, "recs": recs, "neighborhoods": nbhds}
        gsub = geo[geo.GEOID.isin(sub.GEOID)].merge(pd.DataFrame(props), on="GEOID")
        gsub.to_file(WEB / f"tracts_{fips}.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
        (WEB / f"details_{fips}.json").write_text(json.dumps(details, default=str, separators=(",", ":")))
        b = gsub.total_bounds.tolist()
        index["counties"].append({"fips": fips, "name": sub.county.iloc[0], "tracts": len(sub), "bounds": b,
                                  "cost_factor": cf, "cost_source": cf_src})
        print(f"{fips} {sub.county.iloc[0]}: {len(sub)} tracts, cost factor {cf} ({cf_src})")
    # research notes -> tracts (by OSM neighborhood name or a named park inside the tract)
    parks = gpd.read_file(DERIVED / "osm_parks.geojson") if (DERIVED / "osm_parks.geojson").exists() else None
    for r in research["neighborhoods"]:
        want = r["match"].get("osm_neighborhood", "").lower()
        fips = r.get("county_fips", "")
        hits = [g for g, nb in zip(m.GEOID, m.get("osm_neighborhoods", pd.Series(["[]"] * len(m))))
                if want and g.startswith(fips) and want in [x.lower() for x in json.loads(nb if isinstance(nb, str) else "[]")]]
        pk = r["match"].get("osm_park")
        if not hits and pk and parks is not None:
            cand = parks[parks.name.fillna("").str.contains(pk, case=False)]
            if len(cand):
                j = gpd.sjoin(geo, cand[["geometry"]], predicate="intersects")
                hits = sorted(g for g in set(j.GEOID) if g.startswith(fips))
        if not hits and r.get("point_approx"):
            from shapely.geometry import Point
            lat, lon = r["point_approx"]
            hits = list(geo[geo.contains(Point(lon, lat))].GEOID)
            r["matched_by"] = "approximate point"
        r["tracts"] = hits
    index["research"] = research
    first = next((r["tracts"][0] for r in research["neighborhoods"] if r.get("tracts")), None)
    index["default_tract"] = next((r["tracts"][0] for r in research["neighborhoods"] if r["id"] == "beverlywood" and r.get("tracts")), first)
    write_context(index, geo, parks)
    fed = DERIVED / "federal_projects.csv"
    if fed.exists():
        f = pd.read_csv(fed, dtype={"county_fips": str, "Place of Performance Zip5": str})
        for c in index["counties"]:
            sub = f[f.county_fips == c["fips"]].sort_values("Award Amount", ascending=False)
            c["federal"] = [{"amount": float(x["Award Amount"]), "recipient": x.get("Recipient Name"),
                             "desc": x.get("Description"), "agency": x.get("Awarding Agency"),
                             "start": str(x.get("Start Date"))[:4],
                             "zip": None if pd.isna(x.get("Place of Performance Zip5")) else str(x.get("Place of Performance Zip5"))[:5]}
                            for _, x in sub.head(60).iterrows()]
    status = DERIVED / "pipeline_status.json"
    if status.exists():
        index["pipeline_status"] = json.loads(status.read_text())
    (WEB / "index.json").write_text(json.dumps(index, default=str, indent=1))


if __name__ == "__main__":
    main()
