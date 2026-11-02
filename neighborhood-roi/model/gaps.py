"""What each place is missing, compared with places like it, and a plan written for each named neighborhood.

Each block group is compared with its 50 most similar block groups county-wide (income, density, home value,
housing age, share of children, households without a car, single-family share). A gap is a measure where the area
is worse than at least 80% of those peers by a meaningful margin; a strength is better than 85% of them.
Gaps are matched to the fixes City Pretty already sized and costed for that block group, and to the actual nearest
named facility, park and rail station, so every neighborhood's plan cites its own places and numbers.

Reads web/county_data/bg_scored.csv + details.json + meta.json and map layers; writes web/county_data/gaps.json.
"""
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parent.parent
SRC, MOD = ROOT / "data" / "derived" / "county_la", ROOT / "web" / "county_data"
M = 3310
K = 50
MI = 1609.34

# key, label, column (or callable), better ("low"/"high"), min absolute difference to count, unit, fixes (catalog ids, best first)
METRICS = [
    ("park_ac", "park space within ½ mile", "park_acres_half_mile", "high", 2.0, "ac", ["pocket_park", "park_upgrade", "stormwater_park", "community_garden"]),
    ("park_d", "walk to the nearest park", "park_nearest_m", "low", 250, "mi", ["pocket_park", "community_garden", "vacant_lot_green"]),
    ("play_d", "walk to a playground", "playground_nearest_m", "low", 300, "mi", ["park_upgrade", "pocket_park"]),
    ("canopy", "tree canopy (points below goal)", "tc_gap", "low", 4, "pts", ["street_trees", "tiny_forest", "schoolyard_green"]),
    ("heat", "summer heat vs. county", "temp_diff_f", "low", 1.0, "°F", ["street_trees", "cool_pavement", "transit_shade", "green_street", "cooling_center"]),
    ("grocery", "distance to a supermarket", "grocery_nearest_m", "low", 400, "mi", ["grocery", "corner_store", "farmers_market"]),
    ("dining", "restaurants and cafés within ½ mile", "dining_within_800m", "high", 4, "n", ["main_street", "corner_store", "food_hall", "outdoor_dining"]),
    ("school", "distance to a public school", "fac_school_m", "low", 400, "mi", ["new_school", "school_street"]),
    ("library", "distance to a library", "fac_library_m", "low", 600, "mi", ["library"]),
    ("clinic", "distance to a clinic", "fac_clinic_m", "low", 600, "mi", ["clinic"]),
    ("center", "distance to a community or rec center", "fac_community_center_m", "low", 600, "mi", ["rec_center", "cooling_center"]),
    ("bus", "buses an hour at the busiest stop", "bus_max_tph_400m", "high", 4, "/hr", ["bus_lane", "brt", "transit_priority", "microtransit"]),
    ("rail", "distance to rail", "rail_m", "low", 800, "mi", ["bike_share", "microtransit", "rail_station"]),
    ("violent", "violent crime per 1,000 residents", "violent_per_1k", "low", 2.0, "/1k", ["street_lighting", "violence_interruption", "foot_patrol"]),
    ("property", "property crime per 1,000 residents", "property_per_1k", "low", 6.0, "/1k", ["street_lighting", "bid", "foot_patrol"]),
    ("ksi", "fatal or severe crashes on record", "crashes_ksi", "low", 2, "n", ["traffic_calming", "crosswalks", "ped_signals", "speed_cameras", "road_diet", "roundabout"]),
    ("pedbike", "crashes injuring people walking or biking", "crashes_ped_bike", "low", 3, "n", ["ped_signals", "crosswalks", "protected_bike", "slow_streets"]),
    ("dumping", "illegal-dumping reports in 12 months", "dump_n", "low", 10, "n", ["litter", "alley_gating"]),
    ("graffiti", "graffiti reports in 12 months", "graf_n", "low", 10, "n", ["graffiti", "murals", "box_art"]),
    ("freeway", "distance from the freeway", "freeway_nearest_m", "high", 150, "mi", ["noise_wall", "school_filters"]),
    ("pool", "distance to a public pool", "pool_nearest_m", "low", 800, "mi", ["pool", "splash_pad"]),
    ("ev", "distance to an EV fast charger", "dcfc_nearest_m", "low", 800, "mi", ["ev_hub"]),
]
LABEL = {m[0]: m[1] for m in METRICS}


def fmt(v, unit):
    if v is None or v != v:
        return "–"
    if unit == "mi":
        return f"{v / MI:.1f} mi"
    if unit == "ac":
        return f"{v:.1f} acres"
    if unit == "°F":
        return f"{v:+.1f}°F"
    if unit in ("/1k", "/km²"):
        return f"{v:.1f}{unit}"
    if unit == "/hr":
        return f"{v:.0f}/hr"
    if unit == "pts":
        return f"{v:.0f} pts"
    return f"{v:.0f}"


def load():
    d = pd.read_csv(MOD / "bg_scored.csv", dtype={"GEOID": str})
    details = json.loads((MOD / "details.json").read_text())
    meta = json.loads((MOD / "meta.json").read_text())
    d["rail_m"] = d[["rail_station_nearest_m", "rail_stop_nearest_m"]].min(axis=1)
    pop = d.population.clip(lower=300)
    d["ksi_1k"] = d.crashes_ksi / pop * 1000
    d["pb_1k"] = d.crashes_ped_bike / pop * 1000
    d["dump_n"] = np.where(d.in_311.fillna(False).astype(bool), d.illegal_dumping, np.nan)
    d["graf_n"] = np.where(d.in_311.fillna(False).astype(bool), d.graffiti, np.nan)
    for c in ("violent_per_1k", "property_per_1k"):
        d.loc[~d.crime_covered.fillna(False).astype(bool), c] = np.nan
    return d, details, meta


def peers(d):
    X = pd.DataFrame({
        "inc": np.log(d.median_household_income.clip(lower=10_000)),
        "dens": np.log(d.density.clip(lower=1e-5)),
        "hv": np.log(d.home_value.clip(lower=100_000)),
        "yb": d.median_year_built, "kids": d.kids_share, "nocar": d.no_car_share, "sf": d.sf_share})
    X = X.fillna(X.median())
    X = ((X - X.mean()) / X.std().replace(0, 1)).fillna(0)
    nn = NearestNeighbors(n_neighbors=K + 1).fit(X.values)
    return nn.kneighbors(X.values, return_distance=False)[:, 1:]


def nearest_named(d):
    """Actual nearest named library, school, clinic, community center, park and rail station for each block group."""
    bg = gpd.read_file(SRC / "map_block_groups.geojson")[["GEOID", "geometry"]].to_crs(M)
    pts = gpd.GeoDataFrame({"GEOID": bg.GEOID}, geometry=bg.geometry.representative_point(), crs=M)
    out = {g: {} for g in pts.GEOID}

    def attach(g, key, namecol):
        g = g[g[namecol].notna() & (g[namecol].astype(str).str.len() > 1)][[namecol, "geometry"]].to_crs(M).reset_index(drop=True)
        if not len(g):
            return
        j = gpd.sjoin_nearest(pts, g, how="left", distance_col="dist").drop_duplicates("GEOID")
        for gid, nm, dist in zip(j.GEOID, j[namecol], j.dist):
            if isinstance(nm, str):
                out[gid][key] = [nm.strip().title() if nm.isupper() else nm.strip(), round(float(dist))]

    fac = SRC / "map_facilities.geojson"
    if fac.exists():
        f = gpd.read_file(fac)
        for kind, key in (("library", "library"), ("school", "school"), ("clinic", "clinic"), ("community center", "center")):
            attach(f[f.kind == kind], key, "name")
    pk = SRC / "map_parks_all.geojson"
    if pk.exists():
        p = gpd.read_file(pk)
        p["geometry"] = p.geometry.representative_point()
        attach(p[p.kind.isin(["park", "open space"])], "park", "name")
        attach(p[p.kind.isin(["park"]) & (p.acres >= 3)], "bigpark", "name")
    st = SRC / "map_stations.geojson"
    if st.exists():
        attach(gpd.read_file(st), "station", "name")
    return out


def bg_gaps(d, idx):
    gaps, strengths = {}, {}
    cols = {}
    for key, label, col, better, mind, unit, fixes in METRICS:
        if col not in d:
            continue
        v = d[col].to_numpy(dtype=float)
        cols[key] = v
    for i in range(len(d)):
        gid, g, s = d.GEOID.iat[i], [], []
        pi = idx[i]
        for key, label, col, better, mind, unit, fixes in METRICS:
            if key not in cols:
                continue
            v = cols[key]
            x = v[i]
            pv = v[pi]
            pv = pv[~np.isnan(pv)]
            if x != x or len(pv) < 20:
                continue
            med = float(np.median(pv))
            worse = (pv < x).mean() if better == "low" else (pv > x).mean()  # share of peers doing better
            gap = abs(x - med)
            if worse >= 0.8 and gap >= mind:
                g.append([key, round(float(worse), 2), x, med])
            elif worse <= 0.15 and gap >= mind:
                s.append([key, round(float(1 - worse), 2), x, med])
        g.sort(key=lambda r: -r[1])
        s.sort(key=lambda r: -r[1])
        gaps[gid], strengths[gid] = g[:6], s[:3]
    return gaps, strengths


def pick_fix(fixes, recs, catalog, allow_u=False):
    """Best fix this place already has a costed project for: value per $1 for priced fixes, else need."""
    if not fixes:
        return None, None
    have = {r["id"]: r for r in recs}
    cands = []
    for rank, f in enumerate(fixes):
        r = have.get(f)
        if not r:
            continue
        c = catalog.get(f, {})
        if c.get("grade") == "U" and not allow_u:
            continue
        score = (r["vpd"] if c.get("kind") == "value" else 0.6 + r.get("qol", 0)) - rank * 0.05
        cands.append((score, f, r))
    if cands:
        return max(cands, key=lambda t: t[0])[1:]
    f = next((f for f in fixes if catalog.get(f, {}).get("grade") != "U"), fixes[0])
    return f, None


def describe(key, x, med, unit, near, hood=None):
    """One specific sentence for a gap, naming the actual nearest place when there is one."""
    nm = {"library": "library", "school": "school", "clinic": "clinic", "center": "center", "park_d": "park", "rail": "station"}.get(key)
    place = near.get(nm) if nm else None
    sim = "similar neighborhoods"
    noun = {"library": "library", "school": "public school", "clinic": "clinic", "center": "community or rec center", "park_d": "park",
            "play_d": "playground", "grocery": "supermarket", "pool": "public pool", "ev": "EV fast charger", "rail": "rail station"}.get(key)
    if place and unit == "mi":
        return f"The nearest {noun} is {place[0]}, {place[1] / MI:.1f} mi away; in {sim} it's about {med / MI:.1f} mi."
    if noun and unit == "mi":
        return f"The nearest {noun} is {x / MI:.1f} mi away; in {sim} it's about {med / MI:.1f} mi."
    if key == "park_ac":
        bp = near.get("bigpark")
        return f"Only {x:.1f} acres of park within ½ mile ({sim}: {med:.1f})" + (f"; the closest sizable park is {bp[0]}, {bp[1] / MI:.1f} mi away." if bp else ".")
    if key == "heat":
        return f"Summers run {x - med:.1f}°F hotter than in {sim}."
    if key == "canopy":
        return f"Tree canopy is {x:.0f} points short of the city's goal ({sim}: {med:.0f})."
    if key == "dining":
        return f"Only {x:.0f} restaurants or cafés within ½ mile ({sim}: {med:.0f})."
    if key == "bus":
        return f"The busiest nearby stop gets {x:.0f} buses an hour ({sim}: {med:.0f})."
    if key == "freeway":
        return f"Homes sit {x / MI:.2f} mi from the freeway ({sim}: {med / MI:.1f} mi), so noise and exhaust are higher."
    if key in ("violent", "property"):
        return f"{x:.1f} {'violent' if key == 'violent' else 'property'} crimes per 1,000 residents a year ({sim}: {med:.1f})."
    if key in ("ksi", "pedbike"):
        what = "fatal or severe crashes" if key == "ksi" else "crashes that injured someone walking or biking"
        return f"{x:.0f} {what} on record here ({sim}: {med:.0f})."
    if key in ("dumping", "graffiti"):
        what = "illegal-dumping" if key == "dumping" else "graffiti"
        return f"{x:.0f} {what} reports to 311 in the past year ({sim}: {med:.0f})."
    return f"{LABEL[key][0].upper() + LABEL[key][1:]}: {fmt(x, unit)} ({sim}: {fmt(med, unit)})."


def main():
    d, details, meta = load()
    cat = meta["catalog"]
    unit = {m[0]: m[5] for m in METRICS}
    fixes_for = {m[0]: m[6] for m in METRICS}
    idx = peers(d)
    gaps, strengths = bg_gaps(d, idx)
    near = nearest_named(d)
    recs_of = {g: v["recs"] for g, v in details.items()}

    out_bg = {}
    for gid in d.GEOID:
        g, s, nr = gaps.get(gid, []), strengths.get(gid, []), near.get(gid, {})
        rows = []
        for key, sev, x, med in g:
            f, r = pick_fix(fixes_for[key], recs_of.get(gid, []), cat)
            rows.append([key, LABEL[key], fmt(x, unit[key]), fmt(med, unit[key]), sev, f, describe(key, x, med, unit[key], nr, None),
                         round(r["cost"]) if r else None, round(r["vpd"], 2) if r and r.get("vpd") else None])
        out_bg[gid] = {"g": rows, "s": [[k, LABEL[k], fmt(x, unit[k]), fmt(m_, unit[k])] for k, _, x, m_ in s]}

    # ---- neighborhood plans: combine block-group gaps, weighted by homes
    plans = {}
    d = d.copy()
    d["hk"] = d.hood.fillna(d.city) + "|" + d.city
    for hk, grp in d.groupby("hk"):
        homes = grp.homes.clip(lower=1)
        tot = float(homes.sum())
        if tot < 50:
            continue
        score, examples = {}, {}
        for gid, h in zip(grp.GEOID, homes):
            for key, sev, x, med in gaps.get(gid, []):
                score[key] = score.get(key, 0) + h * sev
                if key not in examples or sev > examples[key][0]:
                    examples[key] = (sev, gid, x, med)
        sscore = {}
        for gid, h in zip(grp.GEOID, homes):
            for key, sev, x, med in strengths.get(gid, []):
                sscore[key] = sscore.get(key, 0) + h * sev
        top = sorted(((v / tot, k) for k, v in score.items() if v / tot >= 0.2), reverse=True)[:4]
        strong = [k for v, k in sorted(((v / tot, k) for k, v in sscore.items() if v / tot >= 0.3), reverse=True)[:2]]
        steps, used = [], set()
        homes_of = dict(zip(grp.GEOID, homes))
        for share, key in top:
            sev, gid, x, med = examples[key]
            affected = [g_ for g_ in grp.GEOID if any(k == key for k, *_ in gaps.get(g_, []))]
            # one concrete project, sited in the most affected part that has a costed fix not already in the plan
            choice = None
            for g_ in sorted(affected, key=lambda g_: (-max(v for k, v, *_ in gaps[g_] if k == key), -homes_of[g_])):
                f, r = pick_fix([f for f in fixes_for[key] if f not in used], recs_of.get(g_, []), cat)
                if r:
                    choice = (g_, f, r)
                    break
            if choice is None:
                f = next((f for f in fixes_for[key] if f not in used and cat.get(f, {}).get("grade") != "U"), None)
                if not f:
                    continue
                choice = (gid, f, None)
            g_, f, r = choice
            used.add(f)
            nr = near.get(g_, {})
            land = nr.get("park") or nr.get("school") or nr.get("library")
            steps.append({"gap": key, "share": round(len(affected) / len(grp), 2), "parts": len(affected),
                          "why": describe(key, x, med, unit[key], near.get(gid, {})),
                          "fix": f, "name": cat[f]["name"], "kind": cat[f]["kind"], "bg": g_,
                          "near": f"near {land[0]}" if land and land[1] < 800 else None,
                          "cost": round(r["cost"]) if r else None, "value": round(r["value"]) if r and r["value"] else None,
                          "vpd": round(r["vpd"], 2) if r and r.get("vpd") else None,
                          "project": r["project"] if r else None, "funding": (cat[f].get("funding") or [None])[0]})
        # order: cheapest first as the quick win, then the biggest return
        if steps:
            quick = min((s_ for s_ in steps if s_["cost"]), key=lambda s_: s_["cost"], default=None)
            if quick:
                steps.remove(quick)
                steps.sort(key=lambda s_: -((s_["value"] or 0) / max(s_["cost"] or 1, 1)))
                steps.insert(0, quick)
        # place-specific context: zoning near transit, existing district
        ctx = []
        rail = grp.rail_m.min()
        sf = float((grp.sf_share * homes).sum() / tot)
        st = near.get(grp.GEOID.iat[int(np.argmin(grp.rail_m.fillna(1e9).values))], {}).get("station")
        if rail == rail and rail < 805 and sf > 0.4:
            ctx.append(f"{'Parts of the area are' if st is None else 'The ' + st[0] + ' station puts parts of the area'} within ½ mile of rail, where SB 79 and AB 2097 now allow more homes "
                       f"and no parking minimums; {sf:.0%} of homes here are single-family.")
        top_val = grp.sort_values("top_vpd", ascending=False).iloc[0]
        plans[hk] = {"homes": int(tot), "bgs": int(len(grp)), "steps": steps,
                     "strong": [[k, LABEL[k]] for k in strong], "ctx": ctx,
                     "peer_note": "Compared with the 50 most similar block groups county-wide for each part of the neighborhood."}
    (MOD / "gaps.json").write_text(json.dumps({"bg": out_bg, "plans": plans}, separators=(",", ":"), default=float))
    ng = sum(1 for v in out_bg.values() if v["g"])
    print(f"{ng:,} of {len(out_bg):,} block groups have at least one gap; {len(plans):,} neighborhood plans; "
          f"{sum(1 for p in plans.values() if p['steps']):,} with steps")
    from collections import Counter
    print(Counter(k for v in out_bg.values() for k, *_ in v["g"]).most_common(25))


if __name__ == "__main__":
    main()
