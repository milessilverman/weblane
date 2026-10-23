"""Build one self-contained .html (map + report) for a focus region.

    python3 web/build_focus_html.py la_westside

Inlines Leaflet and every data layer (gzip + base64), so the file opens offline.
"""
import base64
import csv
import gzip
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point
from shapely.ops import linemerge, unary_union

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
M = 3310
MAJOR = ["motorway", "trunk", "primary", "secondary", "tertiary"]


def rnd(obj, nd=5):
    txt = json.dumps(obj, separators=(",", ":"), default=str)
    return json.loads(re.sub(r"(-?\d+\.\d{%d})\d+" % nd, r"\1", txt))


def lines_layer(gdf, key, simplify_m, min_len_m=0):
    out = []
    g = gdf.to_crs(M)
    for (k, n), grp in g.groupby([key, g["name"].fillna("")], dropna=False):
        u = unary_union(list(grp.geometry))
        geom = linemerge(u) if u.geom_type == "MultiLineString" else u
        parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        for p in parts:
            if p.length >= min_len_m:
                out.append({"k": k, "n": n or None, "geometry": p.simplify(simplify_m)})
    return gpd.GeoDataFrame(out, geometry="geometry", crs=M).to_crs(4326) if out else None


def labels_along(gdf_m, every_m=1400, min_len=500):
    labs = []
    for _, r in gdf_m.iterrows():
        if not isinstance(r.n, str) or not r.n or r.geometry.length < min_len:
            continue
        L = r.geometry.length
        for d in np.arange(min(every_m / 2, L / 2), L, every_m):
            a, b = r.geometry.interpolate(max(0, d - 30)), r.geometry.interpolate(min(L, d + 30))
            pt = gpd.GeoSeries([r.geometry.interpolate(d)], crs=M).to_crs(4326).iloc[0]
            pa, pb = gpd.GeoSeries([a, b], crs=M).to_crs(4326)
            ang = math.degrees(math.atan2(-(pb.y - pa.y), (pb.x - pa.x) * math.cos(math.radians(pt.y))))
            if ang > 90:
                ang -= 180
            if ang < -90:
                ang += 180
            labs.append([r.n, round(pt.y, 5), round(pt.x, 5), round(ang, 1)])
    return labs


def main(region="la_westside"):
    src = ROOT / "data" / "derived" / f"focus_{region}"
    sc = ROOT / "web" / "focus_data" / region
    blocks = gpd.read_file(sc / "blocks_scored.geojson")
    for c in ("street_trees", "vacant_planting_sites", "vacant_parcels", "violent_per_1k", "street_canopy_pct", "canopy", "temp_diff_f"):
        if c not in blocks:
            blocks[c] = np.nan
    details = json.loads((sc / "block_details.json").read_text())
    status = json.loads((src / "status.json").read_text()) if (src / "status.json").exists() else {"sources": {}}
    lib = {r["id"]: {"name": r["intervention"], "evidence": r["evidence_strength"], "basis": r["uplift_basis"], "sources": r["key_sources"]}
           for r in csv.DictReader(open(ROOT / "data" / "interventions.csv", newline=""))}
    keep_m = {"value", "value_source", "homes", "homes_source", "acres", "name_source", "street_trees", "vacant_planting_sites", "stumps",
              "palms", "street_canopy_pct", "canopy_pct_1m", "temp_diff_f", "park_acres_half_mile", "nearest_park", "nearest_park_m",
              "schools_near3", "population", "median_household_income", "median_year_built", "owner_units", "occupied_units",
              "res_street_km", "vacant_parcels", "residential_parcels", "land_value_per_sqft_median", "crimes_12mo", "violent_12mo", "freeway_m"}
    for k, v in details.items():
        v["metrics"] = {a: b for a, b in v.get("metrics", {}).items() if a in keep_m and b is not None}

    layers = {}
    roads = gpd.read_file(src / "osm_roads.geojson")
    maj = lines_layer(roads[roads.highway.isin(MAJOR)], "highway", 4)
    res = lines_layer(roads[roads.highway.isin(["residential", "living_street", "unclassified"])], "highway", 3)
    order = {k: i for i, k in enumerate(reversed(MAJOR))}
    maj = maj.assign(o=maj.k.map(order)).sort_values("o").drop(columns="o")
    layers["roads"] = {"major": json.loads(maj.to_json(drop_id=True)), "residential": json.loads(res[["geometry"]].to_json(drop_id=True))}
    layers["road_labels"] = labels_along(maj[maj.k.isin(["primary", "secondary", "tertiary", "trunk"])].to_crs(M))
    w = gpd.read_file(src / "osm_water.geojson")
    wl = w[w.geom_type.isin(["LineString", "MultiLineString"])]
    wl = lines_layer(wl.assign(k=wl.get("waterway", "stream").fillna("stream")), "k", 4, 40)
    wp = w[w.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    wp["geometry"] = wp.to_crs(M).geometry.simplify(4).to_crs(4326)
    layers["water"] = {"type": "FeatureCollection", "features": json.loads(wl.to_json(drop_id=True))["features"] + json.loads(wp[["geometry"]].to_json(drop_id=True))["features"]}
    layers["water_labels"] = [[a, b, c] for a, b, c, _ in labels_along(wl.to_crs(M), every_m=2500, min_len=800)]
    rail = gpd.read_file(src / "osm_rail.geojson")
    rail = lines_layer(rail.assign(k=rail.railway), "k", 5)
    layers["rail"] = json.loads(rail[["k", "geometry"]].to_json(drop_id=True))
    pk = gpd.read_file(src / "osm_parks.geojson")
    pk = pk[pk.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    pk = pk[pk.to_crs(M).area > 600]
    pk["geometry"] = pk.to_crs(M).geometry.simplify(3).to_crs(4326)
    layers["parks"] = json.loads(pk.rename(columns={"name": "n"})[["n", "geometry"]].to_json(drop_id=True))
    if (src / "schools.csv").exists():
        s = pd.read_csv(src / "schools.csv")
        s = s[s.lat.notna()]
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(r.lon, 5), round(r.lat, 5)]},
                  "properties": {"n": r.School, "ela": None if pd.isna(r.get("ela_pct_met")) else round(r.ela_pct_met),
                                 "math": None if pd.isna(r.get("math_pct_met")) else round(r.math_pct_met)}} for _, r in s.iterrows()]
        layers["schools"] = {"type": "FeatureCollection", "features": feats}
    for name, f in (("sites", "vacant_street_sites.geojson"), ("lots", "vacant_parcels.geojson")):
        if (src / f).exists():
            g = gpd.read_file(src / f)
            layers[name] = json.loads(g[["geometry"]].to_json(drop_id=True))

    # neighborhood outlines + labels (dissolved block names)
    blocks["geometry"] = blocks.geometry.make_valid()
    hoods = blocks.dissolve(by="name").reset_index()[["name", "geometry"]]
    hoods["geometry"] = hoods.to_crs(M).geometry.simplify(3).to_crs(4326)
    hood_labels = [[r["name"], round(p.y, 5), round(p.x, 5)] for r, p in
                   zip(hoods.to_dict("records"), hoods.to_crs(M).geometry.representative_point().to_crs(4326))]

    # research notes -> blocks
    research = json.loads((ROOT / "data" / "local_research.json").read_text())["neighborhoods"]
    rep = blocks.to_crs(M).geometry.representative_point().to_crs(4326)
    for r in research:
        nm = r["name"].lower()
        hits = list(blocks[blocks.name.str.lower().str.contains(re.escape(nm.split(" (")[0].split(" /")[0]))].block_id)
        if not hits and r.get("point_approx"):
            lat, lon = r["point_approx"]
            hits = list(blocks[blocks.contains(Point(lon, lat))].block_id)
        r["blocks"] = hits
    research = [r for r in research if r["blocks"]]

    # report
    bt = blocks.copy()
    bt["value_created"] = [details[b]["recs"][0]["value"] if details[b]["recs"] else 0 for b in bt.block_id]
    bt["best"] = [lib[t]["name"] if isinstance(t, str) else "—" for t in bt.top]
    hood_tbl = []
    for n, g in bt.groupby("name"):
        homes = g.homes.sum()
        if homes < 150:
            continue
        trees = g.street_trees.sum(min_count=1)
        sites = g.vacant_planting_sites.sum(min_count=1)
        best = g.best.value_counts().index[0]
        hood_tbl.append([n, g.city.iloc[0], f"{homes:,.0f}", f"${np.nanmedian(g.value)/1e6:.2f}M" if g.value.notna().any() else "–",
                         f"{100*trees/(trees+sites):.0f}%" if pd.notna(trees) and pd.notna(sites) and trees + sites > 0 else "no inventory",
                         f"{sites:,.0f}" if pd.notna(sites) else "–", best, round(float(np.nanmax(g.top_vpd)), 1) if g.top_vpd.notna().any() else "–"])
    hood_tbl.sort(key=lambda r: (r[1] != "Culver City", r[0]))
    src_rows = []
    labels = {"osm_layers": "OpenStreetMap (Geofabrik): streets, creeks, rail, parks, schools", "boundaries": "Census places & block groups; LA Times neighborhoods",
              "blocks": "Street-bounded blocks (arterials, freeways, rail, creeks, city limits)", "naming": "Block names",
              "acs_block_groups": "Census ACS 5-yr, block groups", "tree_equity_bg": "Tree Equity Score (heat, canopy goal)",
              "street_trees": "City street-tree inventories (incl. vacant sites)", "canopy_height": "Meta/WRI 1 m canopy height",
              "assessor_parcels": "LA County Assessor parcels", "lapd_crime": "LAPD crime, last 12 months"}
    for k, v in status.get("sources", {}).items():
        extra = ", ".join(f"{a}={b}" for a, b in v.items() if a in ("rows", "records", "vacant_sites", "la_city_live", "tiles_found", "dataset", "vintage", "vacant", "residential") and b is not None)
        src_rows.append([labels.get(k, k), '<span class="pill ok">working</span>' if v.get("ok") else '<span class="pill miss">missing</span>',
                         (extra or "")[:160] if v.get("ok") else str(v.get("error", ""))[:160]])
    counts = pd.Series([lib[t]["name"] for t in blocks.top.dropna()]).value_counts()
    default = None
    for want in ("Carlson", "Beverlywood"):
        m = blocks[blocks.name.str.contains(want, case=False, na=False)]
        if len(m):
            default = m.sort_values("homes", ascending=False).block_id.iloc[0]
            break
    sites_total = int(blocks.vacant_planting_sites.sum()) if "vacant_planting_sites" in blocks else 0
    trees_total = int(blocks.street_trees.sum()) if "street_trees" in blocks else 0
    focus_rows = []
    for want in ("Carlson Park", "Beverlywood", "Palms", "Lindberg Park", "Cheviot Hills"):
        g = bt[bt.name.str.contains(want, case=False, na=False)]
        if not len(g):
            continue
        trees, sites = g.street_trees.sum(min_count=1), g.vacant_planting_sites.sum(min_count=1)
        best = g.sort_values("top_vpd", ascending=False).iloc[0]
        rec = details[best.block_id]["recs"][0] if details[best.block_id]["recs"] else None
        focus_rows.append([want, f"{len(g)}", f"{g.homes.sum():,.0f}",
                           f"{trees:,.0f} trees, {sites:,.0f} open sites ({100*trees/(trees+sites):.0f}% planted)" if pd.notna(trees) and pd.notna(sites) and trees + sites > 0 else "no inventory",
                           f"{np.nanmedian(g.street_canopy_pct):.0f}%" if g.street_canopy_pct.notna().any() else "–",
                           f"{lib[rec['id']]['name']} · {rec['project']}" if rec else "nothing clears the bar",
                           f"${rec['vpd']:.1f}" if rec else "–"])
    rep_obj = {"title": "What this map shows",
               "paragraphs": [
                   f"{len(blocks):,} street-bounded blocks across the {region.replace('_', ' ').title().replace('La ', 'LA ')} area. Arterials, freeways, rail lines, creeks and city limits draw the boundaries. Each block is ranked by the nearby home value an improvement creates per $1, using real local data.",
                   f"Street trees are sized to the cities' own surveys: {trees_total:,} inventoried street trees and {sites_total:,} vacant planting sites or stumps in this area. A fully planted street now scores near zero for tree planting.",
                   "Click any block for its ranking, the math and the evidence. Turn layers on above the map. The street-map underlay needs an internet connection; everything else is inside this file."],
               "sections": [
                   {"title": "What changed since the first draft", "list": [
                       "<b>Real neighborhoods instead of census tracts.</b> Blocks are bounded by actual arterials, freeways, rail, creeks and city limits. LA blocks carry LA Times neighborhood names; Culver City blocks are named for the park they surround (Carlson, Lindberg, Tellefson, Veterans, Blanco…) or an OpenStreetMap label (Sunkist Park, Fox Hills, Culver Garden…).",
                       "<b>Street trees come from the cities' own tree surveys.</b> The model now plants only the surveyed vacant sites and stumps. Where a street is already mostly planted, the effect is scaled down. Blocks with no inventory use Meta/WRI's 1 m canopy map, calibrated to streets the inventories show as fully planted.",
                       "<b>Vacant lots, gardens and pocket parks need an actual vacant parcel</b> from the LA County Assessor. Blight fixes only rank where values and incomes are below the LA County median.",
                       "<b>Lighting uses police data</b> (LAPD 2024 incidents with coordinates; Santa Monica PD where loaded).",
                       "<b>The map has the detail you asked for:</b> arterials and residential streets with names, Ballona Creek and other channels, rail, parks, schools with test scores, open tree sites and vacant lots. All of it is inside this one file."]},
                   {"title": "Your neighborhoods", "table": {"head": ["Neighborhood", "Blocks", "Homes", "Street trees (city inventory)", "Canopy over streets", "Best bet in its best block", "$ per $1"], "rows": focus_rows, "num": [1, 2, 4, 6]}},
                   {"title": "Neighborhoods at a glance", "paragraphs": ["Blocks grouped by name. In Los Angeles the names follow the LA Times Mapping L.A. boundaries. Culver City publishes no neighborhood GIS file, so its blocks are named for the park they surround."],
                    "table": {"head": ["Neighborhood", "City", "Homes", "Median value", "Street sites planted", "Open tree sites", "Most common best bet", "Best $/$1"],
                              "rows": hood_tbl, "num": [2, 3, 4, 5, 7]}},
                   {"title": "How often each improvement comes out on top", "table": {"head": ["Improvement", "Blocks where it ranks #1"], "rows": [[k, f"{v:,}"] for k, v in counts.items()], "num": [1]}},
                   {"title": "Data in this build", "table": {"head": ["Source", "Status", "Detail"], "rows": src_rows}},
                   {"title": "Read the numbers carefully", "list": [
                       "<b>Value created isn't profit.</b> It counts every nearby home. You capture only the share on property you own.",
                       "<b>Conservative but uncalibrated.</b> The model uses the low end of each study and a ⅓ distance decay. The next step is testing it against past projects.",
                       "<b>Tree inventories age.</b> City surveys date from 2019–2025. LA's comes live from StreetsLA when that service answers.",
                       "<b>Crime</b> covers the City of LA only (LAPD). Culver City, Santa Monica and Beverly Hills police data aren't loaded yet.",
                       "<b>Block values</b> start from Census block-group medians, scaled by the local Zillow trend. Zillow's own neighborhood index is used where names match."]},
               ]}
    bundle = rnd({"meta": {"region": region, "cost_factor": 1.119, "default_block": default, "built": date.today().isoformat()},
                  "blocks": json.loads(blocks.drop(columns=[c for c in ("value_created", "best") if c in blocks]).to_json(drop_id=True)),
                  "details": details, "library": lib, "layers": layers, "hoods": json.loads(hoods.to_json(drop_id=True)),
                  "hood_labels": hood_labels, "research": research, "report": rep_obj})
    raw = re.sub(r"\bNaN\b", "null", json.dumps(bundle, separators=(",", ":"))).encode()
    b64 = base64.b64encode(gzip.compress(raw, 9)).decode()
    html = (WEB / "focus.src.html").read_text()
    html = html.replace("/*LEAFLET_CSS*/", (WEB / "leaflet-1.9.4.css").read_text())
    html = html.replace("/*LEAFLET_JS*/", (WEB / "leaflet-1.9.4.js").read_text().replace("</script", "<\\/script"))
    html = html.replace("/*TITLE*/", "Westside Neighborhood ROI Map").replace("/*EYEBROW*/", f"NEIGHBORHOOD ROI · LA WESTSIDE & CULVER CITY · {date.today():%d %b %Y}".upper())
    html = html.replace("/*H1*/", "Which improvements raise home values most per dollar, block by block")
    html = html.replace("/*BUNDLE*/", b64)
    out = ROOT / "reports" / f"{region.replace('_', '-')}-neighborhood-map.html"
    out.write_text(html)
    print(f"wrote {out} ({len(html)/1e6:.1f} MB; data {len(raw)/1e6:.1f} MB raw)")


if __name__ == "__main__":
    main(*(sys.argv[1:] or []))
