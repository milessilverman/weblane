"""Build City Pretty v2: one self-contained .html for all of LA County (map + report).

    python3 web/build_county_html.py

Reads model output (web/county_data/) and map layers (data/derived/county_la/),
inlines Leaflet and gzip+base64 data so the file opens offline.
"""
import base64
import gzip
import json
import re
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
WEB, SRC, MOD = ROOT / "web", ROOT / "data" / "derived" / "county_la", ROOT / "web" / "county_data"
M = 3310
OUT = ROOT / "reports" / "city-pretty-la-county.html"


def num(v, nd=None):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return round(float(v), nd) if nd is not None else float(v)
    return v


def layer(name, tol=None, keep=(), rename=None, min_area_ac=None, prec=5):
    p = SRC / f"map_{name}.geojson"
    if not p.exists():
        return None
    g = gpd.read_file(p)
    if min_area_ac and "acres" in g:
        g = g[g.acres >= min_area_ac]
    if tol:
        g["geometry"] = g.to_crs(M).geometry.simplify(tol).to_crs(4326)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    g = g[[c for c in keep if c in g] + ["geometry"]].rename(columns=rename or {})
    js = json.loads(g.to_json(drop_id=True))
    return json.loads(re.sub(r"(-?\d+\.\d{%d})\d+" % prec, r"\1", json.dumps(js)))


def merged_lines(name, tol, prec=4):
    """Dissolve many small OSM ways into long merged lines (far fewer vertices than per-way simplification)."""
    from shapely.ops import linemerge, unary_union
    p = SRC / f"map_{name}.geojson"
    if not p.exists():
        return None
    g = gpd.read_file(p).to_crs(M)
    g = g[g.geom_type.isin(["LineString", "MultiLineString"])]
    u = linemerge(unary_union(list(g.geometry)))
    parts = [x.simplify(tol) for x in (u.geoms if hasattr(u, "geoms") else [u]) if x.length > 150]
    out = gpd.GeoDataFrame(geometry=parts, crs=M).to_crs(4326)
    return json.loads(re.sub(r"(-?\d+\.\d{%d})\d+" % prec, r"\1", out.to_json(drop_id=True)))


def labels(g, col):
    g = g[g[col].notna()].copy()
    g["a"] = g.to_crs(M).area
    g = g.sort_values("a", ascending=False).drop_duplicates(col)
    pts = g.to_crs(M).geometry.representative_point().to_crs(4326)
    return [[n, round(p.y, 5), round(p.x, 5)] for n, p in zip(g[col], pts)]


def main():
    d = pd.read_csv(MOD / "bg_scored.csv", dtype={"GEOID": str})
    details = json.loads((MOD / "details.json").read_text())
    meta = json.loads((MOD / "meta.json").read_text())
    cat = meta["catalog"]
    bg = gpd.read_file(SRC / "map_block_groups.geojson")
    bg["geometry"] = bg.to_crs(M).geometry.simplify(14).to_crs(4326)
    bg = bg.merge(d, on="GEOID", how="left")
    col = lambda c: bg[c] if c in bg else pd.Series(np.nan, index=bg.index)  # noqa: E731
    props = pd.DataFrame({"id": bg.GEOID, "n": bg.hood.fillna(bg.city), "c": bg.city, "h": col("homes"), "v": col("top_vpd"), "t": col("top"),
                          "pc": col("pkg_cost"), "hv": col("home_value"), "ht": col("temp_diff_f"), "vc": col("violent_per_1k"),
                          "pa": col("park_acres_half_mile"), "bt": col("bus_max_tph_400m"), "ts": col("vacant_tree_sites")})
    feats = []
    for (_, p), geom in zip(props.iterrows(), bg.geometry):
        q = {k: num(v, 2) for k, v in p.items()}
        q["t"] = p.t if isinstance(p.t, str) else None
        feats.append({"type": "Feature", "properties": q, "geometry": geom.__geo_interface__})
    bgs = json.loads(re.sub(r"(-?\d+\.\d{5})\d+", r"\1", json.dumps({"type": "FeatureCollection", "features": feats})))

    # per-block-group details: compact rec arrays + profile metrics
    keys = ["id", "project", "homes", "cost", "capex", "land", "om", "value", "vpd", "pct", "why", "qol"]
    acres = bg.set_index("GEOID").to_crs(M).area / 4046.86
    det = {}
    dd = d.set_index("GEOID")
    for gid, x in details.items():
        r = dd.loc[gid] if gid in dd.index else None
        if r is None:
            continue
        g_ = lambda c, nd=1: num(r[c], nd) if c in r.index else None  # noqa: E731
        m = {"acres": num(acres.get(gid), 0), "ns": r.get("hood_source"), "csa": r.get("csa") if isinstance(r.get("csa"), str) else None,
             "hv": g_("home_value", 0), "hvs": r.get("value_source"), "homes": g_("homes", 0),
             "own": num(100 * r.owner_units / r.occupied_units, 0) if r.get("occupied_units", 0) and r.get("occupied_units") == r.get("occupied_units") else None,
             "ht": g_("temp_diff_f"), "vc": g_("violent_per_1k") if r.get("crime_covered") else None, "ag": r.get("crime_agency") if isinstance(r.get("crime_agency"), str) else None,
             "pa": g_("park_acres_half_mile"), "pn": g_("park_nearest_m", 0), "bt": g_("bus_max_tph_400m", 0),
             "rm": num(min(r.get("rail_stop_nearest_m", np.nan) if r.get("rail_stop_nearest_m") == r.get("rail_stop_nearest_m") else 1e9,
                           r.get("rail_station_nearest_m", np.nan) if r.get("rail_station_nearest_m") == r.get("rail_station_nearest_m") else 1e9), 0),
             "pop": g_("population", 0), "inc": g_("median_household_income", 0), "rent": g_("median_gross_rent", 0), "yb": g_("median_year_built", 0),
             "sf": num(100 * r.sf_share, 0) if r.get("sf_share") == r.get("sf_share") else None, "nocar": num(100 * r.no_car_share, 0) if r.get("no_car_share") == r.get("no_car_share") else None,
             "st": g_("street_trees", 0), "ts": g_("vacant_tree_sites", 0), "tg": g_("tc_gap", 0),
             "pcr": g_("property_crimes", 0) if r.get("crime_covered") else None, "ksi": g_("crashes_ksi", 0), "dump": g_("illegal_dumping", 0) if r.get("in_311") else None,
             "graf": g_("graffiti", 0) if r.get("in_311") else None, "fw": g_("freeway_nearest_m", 0), "gro": g_("grocery_nearest_m", 0),
             "din": g_("dining_within_400m", 0), "ten": g_("tennis_nearest_m", 0), "dog": g_("dog_park_nearest_m", 0), "pool": g_("pool_nearest_m", 0),
             "ev": g_("ev_charger_nearest_m", 0)}
        if m["rm"] and m["rm"] >= 1e9:
            m["rm"] = None
        m = {k: v for k, v in m.items() if v is not None and not (isinstance(v, float) and np.isnan(v))}
        det[gid] = {"r": [[num(rec[k], 3) if isinstance(rec[k], float) else rec[k] for k in keys] for rec in x["recs"]], "m": m}

    L = {"freeways": layer("freeways", 40, ["name"], {"name": "n"}, prec=4), "arterials": merged_lines("arterials", 25),
         "parks": layer("parks", 20, ["name", "acres"], {"name": "n", "acres": "a"}, min_area_ac=2, prec=5), "water": layer("water", 40, [], prec=4),
         "rail": merged_lines("rail", 25), "stations": layer("stations", None, ["name"], {"name": "n"}),
         "walls": layer("noise_walls", 10, [], prec=5), "amenities": layer("amenities", None, ["kind", "name"], {"kind": "k", "name": "n"})}
    fs = SRC / "map_frequent_stops.geojson"
    if fs.exists():
        s = gpd.read_file(fs)
        s = s[s.tph >= 12]
        L["stops"] = json.loads(re.sub(r"(-?\d+\.\d{5})\d+", r"\1", s.rename(columns={"tph": "t"}).to_json(drop_id=True)))
    hoods = gpd.read_file(SRC / "map_hoods.geojson") if (SRC / "map_hoods.geojson").exists() else None
    cities = gpd.read_file(SRC / "map_cities.geojson")
    hoods_js = None
    if hoods is not None:
        hoods = hoods[hoods.hood.isin(set(d.hood))]
        hoods["geometry"] = hoods.to_crs(M).geometry.boundary.simplify(25).to_crs(4326)
        hoods_js = json.loads(re.sub(r"(-?\d+\.\d{4})\d+", r"\1", hoods[["geometry"]].to_json(drop_id=True)))
    bgn = bg.dissolve(by="hood").reset_index()[["hood", "geometry"]]
    city_js = json.loads(re.sub(r"(-?\d+\.\d{4})\d+", r"\1", cities.assign(geometry=cities.to_crs(M).geometry.boundary.simplify(40).to_crs(4326))[["geometry"]].to_json(drop_id=True)))

    # ---------------- report
    lib = {k: v for k, v in cat.items()}
    top = d[d.top.notna()]
    cnt = top.groupby("top").agg(n=("GEOID", "size"), med=("top_vpd", "median")).sort_values("n", ascending=False)
    top_rows = [[lib[k]["name"], lib[k]["category"], f"{int(r.n):,}", f"${r.med:.1f}"] for k, r in cnt.iterrows()]
    by_city = d.groupby("city").agg(bgs=("GEOID", "size"), homes=("homes", "sum"), hv=("home_value", "median"),
                                    best=("top", lambda s: s.mode().iat[0] if s.notna().any() else None),
                                    cost=("pkg_cost", "sum"), val=("pkg_value", "sum")).sort_values("homes", ascending=False)
    city_rows = [[c, f"{int(r.bgs):,}", f"{r.homes:,.0f}", f"${r.hv/1e6:.2f}M" if r.hv == r.hv else "–",
                  lib[r.best]["name"] if isinstance(r.best, str) else "nothing pays back", f"${r.cost/1e6:,.0f}M", f"${r.val/1e6:,.0f}M"]
                 for c, r in by_city.head(45).iterrows()]
    focus = []
    for want in ("Carlson Park", "Beverlywood", "Cheviot Hills", "Palms", "Mar Vista", "Culver City", "Boyle Heights", "Pasadena", "Long Beach", "Lancaster"):
        g = d[d.hood.str.contains(want, case=False, na=False) | (d.city == want)]
        if not len(g):
            continue
        b = g.sort_values("top_vpd", ascending=False).iloc[0]
        focus.append([want, f"{len(g)}", f"{g.homes.sum():,.0f}", f"${g.home_value.median()/1e6:.2f}M" if g.home_value.notna().any() else "–",
                      lib[b.top]["name"] if isinstance(b.top, str) else "nothing pays back", f"${b.top_vpd:.1f}" if b.top_vpd == b.top_vpd else "–",
                      f"${g.pkg_cost.sum()/1e6:,.1f}M"])
    lib_rows = [[v["name"], v["category"], v.get("grade", "none").replace("none", "–"), {"value": "ranked by value per $1", "regional": "regional, local share", "qol": "quality of life", "policy": "policy", "owner": "homeowner"}[v["kind"]],
                 v["evidence"], (v.get("caveat") or "") + ("<br>" if v.get("caveat") else "") + "<br>".join(v["sources"])] for v in lib.values()]
    st = meta.get("pipeline", {})
    labels_src = {"geo": "Block groups, Census ACS 2020-24, Tree Equity heat, neighborhood names", "osm": "OpenStreetMap amenities, parks, freeways, sound walls, power lines",
                  "transit": "Bus and rail frequency (GTFS, 19 agencies)", "sales": "LA County Assessor recorded sales", "crime": "LAPD, LASD, Long Beach PD and Santa Monica PD crime",
                  "requests311": "MyLA311 service requests (City of LA)", "crashes": "CHP crash records (CCRS)", "trees": "City street-tree surveys",
                  "parcels": "LA County Assessor vacant parcels",
                  "assets": "Bus lanes, LADWP power lines, streetlights, fire zones, LAUSD green space, EV fast chargers"}
    src_rows = []
    for k, lab in labels_src.items():
        s = st.get(k, {})
        ok = s.get("ok")
        det_txt = {kk: vv for kk, vv in s.items() if kk not in ("ok", "seconds", "error") and not isinstance(vv, (list, dict))}
        src_rows.append([lab, '<span class="pill ok">loaded</span>' if ok else '<span class="pill miss">missing</span>',
                         "; ".join(f"{a.replace('_', ' ')}: {b}" for a, b in list(det_txt.items())[:6]) or (s.get("error") or "")[:200]])
    named = d.hood_source.value_counts()
    rep = {"title": "City Pretty: Los Angeles County",
           "paragraphs": [
               f"{len(d):,} Census block groups (about 1,500 people each) across all of LA County, {d.homes.sum():,.0f} homes. For each one, City Pretty checks {len(lib)} kinds of improvement, from street trees and bus lanes to pickleball courts, sound walls, foot patrols, power-line undergrounding and zoning. It sizes each to the area's actual conditions and prices the whole project: build cost, land and ten years of upkeep.",
               "Improvements with a measured effect on home prices are ranked by the home value they add per $1. Improvements without one (pools, crosswalks, litter crews, clinics) are still costed. They're ranked by how much the area needs them compared with the rest of the county.",
               "Click any area for its ranked list, the total cost, the reasoning and the sources. Use the category buttons to see just transit, safety, parks and so on."],
           "sections": [
               {"title": "Your neighborhoods", "table": {"head": ["Area", "Block groups", "Homes", "Median home value", "Best bet in its best block group", "$ per $1", "Cost of all paying projects"], "rows": focus, "num": [1, 2, 3, 5, 6]}},
               {"title": "What comes out on top, county-wide", "paragraphs": ["How many block groups each improvement ranks first in (counting only where it returns at least $1 per $1)."],
                "table": {"head": ["Improvement", "Category", "Block groups where #1", "Median $ per $1 there"], "rows": top_rows, "num": [2, 3]}},
               {"title": "By city", "paragraphs": ["The 45 largest cities and areas by homes. Cost and value cover every project returning at least $1 per $1 in each block group."],
                "table": {"head": ["City", "Block groups", "Homes", "Median home value", "Most common best bet", "Cost of paying projects", "Value they add"], "rows": city_rows, "num": [1, 2, 3, 5, 6]}},
               {"title": "The improvement library", "paragraphs": ["Every improvement the model checks, how it's ranked and the evidence behind it, from the City Pretty evidence sourcebooks."],
                "table": {"head": ["Improvement", "Category", "Grade", "Ranked as", "Evidence", "Caveats and sources"], "rows": lib_rows}},
               {"title": "Evidence grades", "list": [
                   "<b>A: measured on LA sales.</b> City Pretty's own estimate from recorded Westside sales (street trees).",
                   "<b>B: studied elsewhere.</b> A study of the same kind of improvement, usually outside LA (sound walls, vacant-lot greening, BRT, school bonds, grocery stores, ADUs, undergrounding).",
                   "<b>C: transferred.</b> Borrowed from a related study, or chained through a crime-to-price link (park renovations, speed humps, lighting, foot patrols, EV chargers).",
                   "<b>D: assumption.</b> Scaled from a different improvement (bus lanes, dog parks, farmers markets, main-street grants, schoolyards).",
                   "Use the <b>Evidence shown</b> menu at the top to hide lower grades; the map and every ranking update to match. An outside accuracy audit (City Pretty V2.1 review) supplied the caveat shown with each estimate."]},
               {"title": "Data in this build", "paragraphs": [f"Neighborhood names: {', '.join(f'{k} ({v:,})' for k, v in named.items())}."],
                "table": {"head": ["Source", "Status", "Detail"], "rows": src_rows}},
               {"title": "Read the numbers carefully", "list": [
                   "<b>Value added isn't profit.</b> It sums the gain across every nearby home. An owner captures only their own share.",
                   "<b>Low-end effects.</b> Each price effect is the low end of the best study found. Street trees use City Pretty's own estimate from 3,386 Westside sales. Crime programs are converted to prices with the New York repeat-sales link (1% less violent crime raises prices ~0.12%).",
                   "<b>Crime coverage.</b> LAPD covers the City of LA, the Sheriff covers unincorporated areas and contract cities, and Long Beach and Santa Monica police publish their own maps (Santa Monica's public feed stops in May 2024). Other cities with their own police (Pasadena, Glendale, Culver City, Burbank and others) publish no incident data, so they show 'no data' and safety programs aren't ranked there.",
                   "<b>What the research says isn't worth claiming.</b> LA's own camera evaluations found no crime effect, so cameras carry no price effect. No study prices graffiti or litter removal, so those rank by need, not value per $1. Bus lanes use a modeled share of measured bus-rapid-transit effects.",
                   "<b>Home values</b> come from recorded single-family sales in each block group (2022-24) where there are at least 5, then from the surrounding tract, then from the Census. Census values stop at $2M.",
                   "<b>Regional projects</b> (rail stations, freeway caps) show this area's rough share of a much larger project. Treat them as a signal, not a budget.",
                   "<b>Dollars.</b> Costs are in 2024 dollars (CPI-U) where the source year is known; costs marked as estimates in the caveats have no matched LA record yet.",
                   "<b>Policy changes</b> such as rezoning cost the public little to adopt, so no per-dollar return is shown for them.",
                   "<b>Unknowns are left out, not guessed.</b> Where the research has no price effect (pools, crosswalks, litter crews), the item gets no value number. Where a cost isn't on record, the estimate is flagged in its sources."]}]}

    default = None
    for want in ("Carlson Park", "Beverlywood", "Culver City"):
        g = d[(d.hood == want) | (d.city == want)].sort_values("homes", ascending=False)
        if len(g):
            default = g.GEOID.iat[0]
            break
    # search: each name points to its most central block group
    search = {}
    cent = bg.to_crs(M).geometry.representative_point()
    for key in ("hood", "city"):
        for nm, idx in bg.groupby(key).groups.items():
            pts = cent.loc[idx]
            c = pts.union_all().centroid if hasattr(pts, "union_all") else pts.unary_union.centroid
            search[nm] = bg.GEOID.loc[pts.distance(c).idxmin()]
    bundle = {"meta": {"built": date.today().isoformat(), "default_bg": default, "search": search}, "bgs": bgs, "details": det, "catalog": lib, "funding": meta.get("funding", {}),
              "layers": L, "hoods": hoods_js, "hood_labels": labels(bgn, "hood"), "cities": city_js,
              "city_labels": labels(cities.rename(columns={"name": "nm"}), "nm"), "report": rep}
    raw = json.dumps(bundle, separators=(",", ":"), default=str)
    raw = re.sub(r"\bNaN\b", "null", raw).encode()
    b64 = base64.b64encode(gzip.compress(raw, 9)).decode()
    base_css = re.search(r"<style>\n(/\* Layout.*?)</style>", (WEB / "focus.src.html").read_text(), re.S).group(1)
    html = (WEB / "county.src.html").read_text()
    html = html.replace("/*BASE_CSS*/", base_css).replace("/*LEAFLET_CSS*/", (WEB / "leaflet-1.9.4.css").read_text())
    html = html.replace("/*LEAFLET_JS*/", (WEB / "leaflet-1.9.4.js").read_text().replace("</script", "<\\/script"))
    html = html.replace("/*EYEBROW*/", f"CITY PRETTY · ALL OF LOS ANGELES COUNTY · {date.today():%d %b %Y}".upper()).replace("/*BUNDLE*/", b64)
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(html)/1e6:.1f} MB; data {len(raw)/1e6:.1f} MB raw)")


if __name__ == "__main__":
    main()
