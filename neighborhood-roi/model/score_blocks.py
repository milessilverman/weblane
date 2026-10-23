"""Score focus-region blocks (street-bounded neighborhood pieces) on real local data.

    python3 model/score_blocks.py la_westside

Differences from the tract model:
- street trees are sized by the city's surveyed vacant planting sites and stumps, so a
  fully planted street scores ~0 (estimated from 1 m street canopy only where no inventory exists)
- vacant-lot greening, gardens and pocket parks need actual vacant parcels (LA County Assessor)
- lighting uses LAPD crime counts where covered
"""
import csv
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "model"))
from score_tracts import pv_annuity, time_factor, DISTANCE_DECAY, ACRE_SQFT  # noqa: E402

CITY_COST = 1.119  # BLS-derived LA metro factor (see regional_costs_bls.csv)
TREE_SPACING_M = 12
TARGET_STREET_CANOPY = 35


def num(v):
    try:
        f = float(v)
        return np.nan if math.isnan(f) else f
    except (TypeError, ValueError):
        return np.nan


def load_tract_values():
    """Tract value_now (ACS × ZIP Zillow trend or Zillow neighborhood index) and its ACS base."""
    d = json.loads((ROOT / "web" / "data" / "details_06037.json").read_text())
    return {g: (num(v["metrics"].get("value_now")), num(v["metrics"].get("median_home_value")), v["metrics"].get("value_source"))
            for g, v in d.items()}


def recs_for(b, lib):
    out = []
    value, homes = b["value"], b["homes"]
    if np.isnan(value) or np.isnan(homes) or homes < 20:
        return out
    hpa = homes / max(b["acres"], 1)

    def add(iid, units, unit_label, homes_hit, uplift, fit, why, capex, land=0.0, maint_units=None, note=None):
        row = lib[iid]
        if fit <= 0.02 or units <= 0:
            return
        gain = homes_hit * value * uplift * fit * time_factor(float(row["time_to_full_effect_yrs"]))
        maint = pv_annuity(float(row["annual_maint_usd"]) * (maint_units if maint_units is not None else units) * CITY_COST)
        cost = capex + land + maint
        out.append({"id": iid, "project": f"{units:,.0f} {unit_label}", "homes": int(round(homes_hit)), "fit": round(fit, 2),
                    "why": why, "capex": round(capex), "land": round(land), "maint_pv": round(maint), "cost": round(cost),
                    "value": round(gain), "vpd": round(gain / cost, 2) if cost else 0, "note": note})

    lo = lambda iid: float(lib[iid]["uplift_pct_low"]) / 100  # noqa: E731
    mid_cost = lambda iid: (float(lib[iid]["unit_cost_low_usd"]) + float(lib[iid]["unit_cost_high_usd"])) / 2 * CITY_COST  # noqa: E731

    # --- street trees: plant the city's own vacant sites (or estimate where no inventory)
    sites = b["vacant_planting_sites"] + b["stumps"]
    if b["tree_inventory"] and not np.isnan(sites):
        stock = b["street_trees"] / max(b["street_trees"] + sites, 1)
        why = (f"City inventory: {b['street_trees']:,.0f} street trees and {sites:,.0f} vacant sites/stumps here "
               f"({stock*100:.0f}% of planting sites filled)")
        n = min(sites, 400)
        if n >= 3:
            gain_frac = 0.03 * 0.5 + 2 * 0.006
            add("street_tree", n, "trees on vacant sites", n * 2, gain_frac / 2, 1.0, why, mid_cost("street_tree") * n,
                note="sized to surveyed vacant sites")
    else:
        sc = b["street_canopy_pct"]
        km = b["res_street_km"]
        if not np.isnan(sc) and not np.isnan(km) and km > 0:
            gap = max(0.0, (TARGET_STREET_CANOPY - sc) / TARGET_STREET_CANOPY)
            n = round(km * 1000 / TREE_SPACING_M * 2 * gap * 0.4)
            if n >= 5:
                add("street_tree", min(n, 400), "trees (estimated open sites)", min(n, 400) * 2, (0.03 * 0.5 + 2 * 0.006) / 2, 0.8,
                    f"No city inventory here; street canopy {sc:.0f}% (1 m canopy map) vs {TARGET_STREET_CANOPY}% target",
                    mid_cost("street_tree") * min(n, 400), note="estimated from canopy")

    # --- blight / vacant land (needs actual vacant parcels)
    vp = b["vacant_parcels"]
    low_market = b["value_ratio"] <= 1.0 and b["income_ratio"] <= 1.0
    if not np.isnan(vp) and vp >= 1:
        r = float(lib["vacant_lot_greening"]["radius_ft"])
        area = math.pi * r * r / ACRE_SQFT * min(vp, 20) * (1 if vp == 1 else 0.5)
        hh = min(homes * 1.5, area * hpa)
        if low_market:
            add("vacant_lot_greening", min(vp, 20), "vacant lots", hh, lo("vacant_lot_greening") * DISTANCE_DECAY, 1.0,
                f"{vp:.0f} vacant parcels (LA County Assessor); values/incomes at or below the county median",
                mid_cost("vacant_lot_greening") * min(vp, 20))
        # community garden or pocket park on one vacant lot
        lot_sqft = b["vacant_parcel_sqft"] / vp if not np.isnan(b["vacant_parcel_sqft"]) and vp else 6000
        land_cost = lot_sqft * (b["land_psf"] if not np.isnan(b["land_psf"]) else value * 0.5 / 6000)
        gap = max(0.0, 1 - b["park_acres"] / 8) if not np.isnan(b["park_acres"]) else 0.5
        r2 = float(lib["pocket_park"]["radius_ft"])
        hh2 = min(homes * 1.5, math.pi * r2 * r2 / ACRE_SQFT * hpa)
        if gap > 0.1:
            add("pocket_park", 1, "pocket park on a vacant lot", hh2, lo("pocket_park") * DISTANCE_DECAY, gap,
                f"{b['park_acres']:.1f} park acres within ½ mile; uses one of {vp:.0f} vacant parcels",
                mid_cost("pocket_park") * 0.5, land=land_cost)
        if b["income_ratio"] <= 0.8 and gap > 0.2:
            r3 = float(lib["community_garden"]["radius_ft"])
            hh3 = min(homes * 1.5, math.pi * r3 * r3 / ACRE_SQFT * hpa)
            add("community_garden", 1, "community garden", hh3, lo("community_garden") * DISTANCE_DECAY, gap,
                f"Lower-income area with few parks; uses a vacant parcel", mid_cost("community_garden"), land=land_cost * 0.3)

    # --- schoolyard greening (nearest LAUSD/CCUSD campus)
    if b["school_score"] is not None:
        heat = 0.5 if np.isnan(b["temp_diff_f"]) else min(1.0, max(0.0, (b["temp_diff_f"] + 2) / 8))
        parkp = 0.5 if np.isnan(b["park_acres"]) else max(0.0, 1 - b["park_acres"] / 10)
        canp = 0.5 if np.isnan(b["canopy"]) else max(0.0, 1 - b["canopy"] / 30)
        schp = min(1.0, max(0.2, (70 - b["school_score"]) / 50))
        fit = 0.3 * heat + 0.3 * parkp + 0.2 * canp + 0.2 * schp
        r = float(lib["green_schoolyard"]["radius_ft"])
        hh = min(homes * 3, math.pi * r * r / ACRE_SQFT * hpa)
        add("green_schoolyard", 1, "schoolyard", hh, lo("green_schoolyard") * DISTANCE_DECAY, fit,
            f"Nearest schools {b['school_score']:.0f}% meet standards; canopy {b['canopy']:.0f}%; {b['park_acres']:.1f} park acres within ½ mile"
            if not np.isnan(b["canopy"]) and not np.isnan(b["park_acres"]) else "Nearby campus", mid_cost("green_schoolyard"))

    # --- lighting (LAPD data where available)
    if b["crime_coverage"] and not np.isnan(b["violent_per_1k"]):
        f = min(1.0, max(0.0, (b["violent_per_1k"] - 2) / 10))
        r = float(lib["street_lighting"]["radius_ft"])
        hh = min(homes, math.pi * r * r / ACRE_SQFT * 50 * 0.5 * hpa)
        add("street_lighting", 50, "lights", hh, lo("street_lighting") * DISTANCE_DECAY, f,
            f"{b['violent_12mo']:.0f} violent crimes in the last 12 months ({b['violent_per_1k']:.1f} per 1,000 residents, LAPD)",
            mid_cost("street_lighting") * 50)

    # --- freeway noise
    if not np.isnan(b["freeway_m"]) and b["freeway_m"] < 150:
        hh = min(homes, 2 * 500 * 5280 / ACRE_SQFT * 0.5 * hpa)
        add("noise_barrier", 1, "mile of soundwall", hh, lo("noise_barrier") * DISTANCE_DECAY, 1 - b["freeway_m"] / 150 * 0.7,
            f"Freeway {b['freeway_m']:.0f} m away", mid_cost("noise_barrier"))
    return sorted(out, key=lambda r: r["vpd"], reverse=True)


def main(region="la_westside"):
    src = DATA / "derived" / f"focus_{region}"
    lib = {r["id"]: r for r in csv.DictReader(open(DATA / "interventions.csv", newline=""))}
    b = gpd.read_file(src / "blocks.geojson")
    tv = load_tract_values()
    zn = pd.read_csv(src / "zillow_neighborhoods.csv") if (src / "zillow_neighborhoods.csv").exists() else None
    zlook = {str(r.RegionName).lower(): (r.zhvi, r.RegionName) for r in zn.itertuples()} if zn is not None else {}

    def col(c):
        return b[c] if c in b else pd.Series(np.nan, index=b.index)

    # value: Zillow neighborhood index > BG ACS median × tract trend > tract value
    rep = b.to_crs(3310).geometry.representative_point().to_crs(4326)
    tracts = gpd.read_file(DATA / "derived" / "tracts.geojson")
    tj = gpd.sjoin(gpd.GeoDataFrame(b[["block_id"]], geometry=rep, crs=4326), tracts[["GEOID", "geometry"]], predicate="within", how="left")
    b["tract"] = tj.drop_duplicates("block_id").set_index("block_id").reindex(b.block_id).GEOID.values
    vals, srcs = [], []
    for _, r in b.iterrows():
        z = zlook.get(str(r["name"]).lower())
        t = tv.get(r["tract"], (np.nan, np.nan, None))
        acs = num(r.get("median_home_value"))
        if z and not np.isnan(z[0]):
            vals.append(z[0]); srcs.append(f"Zillow index for {z[1]}")
        elif not np.isnan(acs) and acs < 2_000_000 and not np.isnan(t[0]) and not np.isnan(t[1]) and t[1] > 0:
            vals.append(acs * min(1.6, t[0] / t[1])); srcs.append("Census block-group median × local Zillow trend")
        elif not np.isnan(t[0]):
            vals.append(max(t[0], acs if not np.isnan(acs) else 0)); srcs.append(t[2] or "tract estimate")
        else:
            vals.append(acs); srcs.append("Census block-group median")
    b["value"], b["value_source"] = vals, srcs
    b["homes"] = np.where(col("assessor_units").fillna(0) > 0, col("assessor_units"), col("housing_units"))
    b["homes_source"] = np.where(col("assessor_units").fillna(0) > 0, "LA County Assessor units", "Census (block-group share)")
    b["value_ratio"] = b.value / b.value.median()
    b["income_ratio"] = col("median_household_income") / col("median_household_income").median()
    b["violent_per_1k"] = col("violent_12mo") / (col("population").clip(lower=50) / 1000)
    b["canopy"] = col("canopy_pct_1m").fillna(col("treecanopy") * (100 if col("treecanopy").max() <= 1.5 else 1))

    results, props = {}, []
    for _, r in b.iterrows():
        schools = json.loads(r["schools_near3"]) if isinstance(r.get("schools_near3"), str) else []
        sc = [x for x in schools if x.get("ela") is not None]
        t = {k: num(r.get(k)) for k in ("value", "homes", "acres", "vacant_planting_sites", "stumps", "street_trees",
                                         "street_canopy_pct", "res_street_km", "vacant_parcels", "vacant_parcel_sqft",
                                         "value_ratio", "income_ratio", "temp_diff_f", "canopy", "violent_12mo",
                                         "violent_per_1k", "freeway_m")}
        t["park_acres"] = num(r.get("park_acres_half_mile"))
        t["land_psf"] = num(r.get("land_value_per_sqft_median"))
        for k in ("vacant_planting_sites", "stumps", "street_trees", "vacant_parcels"):
            t[k] = 0.0 if np.isnan(t[k]) and bool(r.get("tree_inventory")) else t[k]
        t["tree_inventory"] = bool(r.get("tree_inventory")) and not np.isnan(num(r.get("street_trees")))
        t["crime_coverage"] = bool(r.get("crime_coverage"))
        t["school_score"] = float(np.mean([(x["ela"] + (x["math"] or x["ela"])) / 2 for x in sc])) if sc else None
        recs = recs_for(t, lib)
        top = recs[0] if recs else None
        results[r.block_id] = {"recs": recs, "metrics": {k: (None if (isinstance(v, float) and np.isnan(v)) else (round(v, 2) if isinstance(v, float) else v))
                                                         for k, v in r.drop(labels=["geometry"]).items()}}
        props.append({"block_id": r.block_id, "top": top["id"] if top else None, "top_vpd": top["vpd"] if top else None})
    b = b.merge(pd.DataFrame(props), on="block_id")
    out = src / "scored"
    out.mkdir(exist_ok=True)
    keep = ["block_id", "name", "city", "la_hood", "name_source", "top", "top_vpd", "value", "homes", "canopy", "street_canopy_pct",
            "vacant_planting_sites", "street_trees", "vacant_parcels", "violent_per_1k", "temp_diff_f", "park_acres_half_mile", "acres", "geometry"]
    b[[c for c in keep if c in b]].to_file(out / "blocks_scored.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    (out / "block_details.json").write_text(json.dumps(results, default=str, separators=(",", ":")))
    print(len(b), "blocks scored;", pd.Series([p["top"] for p in props]).value_counts().to_dict())


if __name__ == "__main__":
    main(*(sys.argv[1:] or []))
