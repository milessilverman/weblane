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
CHUNK_KEY = 8  # block-group details are chunked by this many leading GEOID digits (state+county+tract prefix)
EVID_ORDER = "ABCDU"  # "Evidence shown" filter values, in the order of each block group's precomputed `tp` list


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


def encode_line(coords, prec=5):
    """Google encoded-polyline string for [(lon, lat), ...] (about 4-6 bytes per vertex)."""
    out, plat, plon, f = [], 0, 0, 10 ** prec
    for lon, lat in coords:
        la, lo = int(round(lat * f)), int(round(lon * f))
        for d in (la - plat, lo - plon):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1f)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = la, lo
    return "".join(out)


CELL = 0.05  # degrees; streets are grouped in ~5 km cells so the page only draws what is on screen


def streets_bundle():
    """Named streets by class (0 freeway refs, 1 arterial, 2 collector, 3 local) as encoded polylines per grid cell."""
    p = SRC / "map_streets.geojson.gz"
    if not p.exists():
        return None
    g = gpd.read_file(f"/vsigzip/{p}")
    g = g[g.geom_type == "LineString"]
    names, idx, cells, fwy = [], {}, {}, []
    for cls, nm, geom in zip(g.cls.astype(int), g.name.astype(str), g.geometry):
        if nm not in idx:
            idx[nm] = len(names)
            names.append(nm)
        if cls == 0:  # freeways: kept whole (few lines) so route shields show at any zoom
            fwy.append([0, idx[nm], encode_line(list(geom.simplify(0.0003).coords))])
            continue
        cs = list(geom.coords)
        if len(cs) < 2:
            continue
        # split long lines at cell borders so each piece lives in one cell
        piece, key = [cs[0]], None
        for a in cs[1:] + [None]:
            k = None if a is None else (int((a[0] + 180) // CELL), int((a[1] + 90) // CELL))
            k0 = (int((piece[0][0] + 180) // CELL), int((piece[0][1] + 90) // CELL))
            if a is not None and k == k0:
                piece.append(a)
                continue
            if a is not None:
                piece.append(a)
            if len(piece) >= 2:
                cells.setdefault(f"{k0[0]},{k0[1]}", []).append([int(cls), idx[nm], encode_line(piece)])
            piece = [a] if a is not None else []
    return {"cell": CELL, "names": names, "cells": cells, "fwy": fwy}


def parks_bundle():
    """All parks (any size) with kind and name, plus label points sized by acreage."""
    p = SRC / "map_parks_all.geojson"
    if not p.exists():
        return None, []
    g = gpd.read_file(p)
    g["geometry"] = g.to_crs(M).geometry.simplify(4).to_crs(4326)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    js = json.loads(g.rename(columns={"name": "n", "kind": "k", "acres": "a"})[["n", "k", "a", "geometry"]].to_json(drop_id=True))
    js = json.loads(re.sub(r"(-?\d+\.\d{5})\d+", r"\1", json.dumps(js)))
    named = g[g.name.notna()].copy()
    pts = named.to_crs(M).geometry.representative_point().to_crs(4326)
    lab = sorted([[n, round(q.y, 5), round(q.x, 5), round(float(a), 1)] for n, q, a in zip(named.name, pts, named.acres)], key=lambda r: -r[3])
    return js, lab


FAC_KINDS = ["school", "college", "library", "city hall", "fire station", "police", "post office", "hospital", "clinic",
             "community center", "museum", "courthouse"]


def facilities_bundle():
    p = SRC / "map_facilities.geojson"
    if not p.exists():
        return None
    g = gpd.read_file(p)
    g = g[g.kind.isin(FAC_KINDS) & g.geometry.notna()]
    return [[FAC_KINDS.index(k), (n if isinstance(n, str) else ""), round(q.y, 5), round(q.x, 5)]
            for k, n, q in zip(g.kind, g.get("name", pd.Series([None] * len(g), index=g.index)), g.geometry)]


ZCATS = ["single-family", "multifamily", "commercial / mixed use", "industrial", "open space / public", "agricultural", "parking", "other"]


def zoning_bundle():
    """Zoning polygons as encoded rings in grid cells (drawn only on screen at high zoom) plus one label point each."""
    p = SRC / "map_zoning.geojson.gz"
    if not p.exists():
        return None
    g = gpd.read_file(f"/vsigzip/{p}")
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    g["geometry"] = g.to_crs(M).geometry.simplify(8).to_crs(4326)
    zones, zi, cells, jur, zj = [], {}, {}, [], []
    for z, cat, juris, geom in zip(g.zone.astype(str), g.cat, g.juris, g.geometry):
        if geom is None or geom.is_empty:
            continue
        if z not in zi:
            zi[z] = len(zones)
            zones.append(z)
            if juris not in jur:
                jur.append(juris)
            zj.append(jur.index(juris))
        ci = ZCATS.index(cat) if cat in ZCATS else len(ZCATS) - 1
        pt = geom.representative_point()
        key = f"{int((pt.x + 180) // CELL)},{int((pt.y + 90) // CELL)}"
        for poly in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom]):
            rings = [encode_line(list(poly.exterior.coords))] + [encode_line(list(r.coords)) for r in poly.interiors]
            cells.setdefault(key, []).append([ci, zi[z], rings])
    return {"cell": CELL, "zones": zones, "cats": ZCATS, "cells": cells, "jur": jur, "zj": zj}


OVERLAY_CELL = 0.05  # degrees; per-house overlay polygons are clipped to this grid so a click unpacks one small cell


def overlays_bundle():
    """Point-in-polygon layers for the house panel (pipeline stage `overlays`), clipped to grid cells with holes kept.
    Returns {"layers", "attrs", "cell", "chunks": {cell: gzip+base64 JSON [[layer i, attrs i, [ring, hole...]]...]}}
    or None when the stage hasn't produced data yet (the page then queries those services live)."""
    from shapely.geometry import box
    p = SRC / "map_overlays.geojson.gz"
    if not p.exists():
        return None
    g = gpd.read_file(f"/vsigzip/{p}")
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    g["geometry"] = g.geometry.make_valid()  # simplified, merged shapes can self-touch; repair before clipping
    layers, attrs, ai, cells = [], [], {}, {}
    for lay, at, geom in zip(g["layer"], g["attrs"].fillna("{}"), g.geometry):  # g.attrs is pandas metadata, not the column
        if lay not in layers:
            layers.append(lay)
        if at not in ai:
            ai[at] = len(attrs)
            attrs.append(json.loads(at))
        x0, y0, x1, y1 = geom.bounds
        for cx in range(int((x0 + 180) // OVERLAY_CELL), int((x1 + 180) // OVERLAY_CELL) + 1):
            for cy in range(int((y0 + 90) // OVERLAY_CELL), int((y1 + 90) // OVERLAY_CELL) + 1):
                bx = box(cx * OVERLAY_CELL - 180, cy * OVERLAY_CELL - 90, (cx + 1) * OVERLAY_CELL - 180, (cy + 1) * OVERLAY_CELL - 90)
                try:
                    part = geom.intersection(bx)
                except Exception:  # noqa: BLE001  (rare topology errors: a zero-width buffer repairs them)
                    part = geom.buffer(0).intersection(bx)
                if part.is_empty:
                    continue
                polys = [q for q in getattr(part, "geoms", [part]) if q.geom_type == "Polygon" and not q.is_empty]
                for q in polys:
                    rings = [encode_line(list(q.exterior.coords))] + [encode_line(list(r.coords)) for r in q.interiors]
                    cells.setdefault(f"{cx},{cy}", []).append([layers.index(lay), ai[at], rings])
    chunks = {k: base64.b64encode(gzip.compress(json.dumps(v, separators=(",", ":")).encode(), 9)).decode() for k, v in cells.items()}
    print(f"  overlays: {', '.join(layers)}; {sum(len(v) for v in cells.values()):,} polygon pieces in {len(cells)} cells, "
          f"{sum(len(c) for c in chunks.values()) / 1e6:.1f} MB packed")
    return {"layers": layers, "attrs": attrs, "cell": OVERLAY_CELL, "chunks": chunks}


def polys_in_cells(g, attrs, tol=2, cell=None):
    """Polygons as encoded rings grouped by grid cell: {cell: [[attr..., [rings]]]} (drawn only on screen)."""
    cell = cell or CELL
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    g["geometry"] = g.to_crs(M).geometry.simplify(tol).to_crs(4326)
    cells = {}
    for row in g.itertuples():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        pt = geom.representative_point()
        key = f"{int((pt.x + 180) // cell)},{int((pt.y + 90) // cell)}"
        rings = [encode_line(list(pl.exterior.coords)) for pl in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom]) if pl.geom_type == "Polygon"]
        cells.setdefault(key, []).append([getattr(row, a) for a in attrs] + [rings])
    return cells


def facility_areas_bundle():
    p = SRC / "map_facility_areas.geojson"
    if not p.exists():
        return None
    g = gpd.read_file(p)
    g = g[g.kind.isin(FAC_KINDS)]
    g["k"] = g.kind.map(FAC_KINDS.index)
    return {"cell": CELL, "cells": polys_in_cells(g, ["k"], tol=1.5)}


def underused_bundle():
    p, q = MOD / "underused.json", MOD / "underused_sites.geojson"
    if not (p.exists() and q.exists()):
        return None, None
    u = json.loads(p.read_text())
    g = gpd.read_file(q)
    return u, {"cell": CELL, "cells": polys_in_cells(g, ["sid"], tol=1.5)}


def lines_bundle(name, keep):
    p = SRC / f"map_{name}.geojson"
    if not p.exists():
        return None
    g = gpd.read_file(p)
    out = []
    for row in g.itertuples():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == "Point":
            out.append([getattr(row, k) if isinstance(getattr(row, k, None), str) else None for k in keep] + [round(geom.y, 5), round(geom.x, 5)])
            continue
        for ln in (geom.geoms if hasattr(geom, "geoms") else [geom]):
            out.append([getattr(row, k) if isinstance(getattr(row, k, None), str) else None for k in keep] + [encode_line(list(ln.simplify(0.00005).coords))])
    return out


PJ_KINDS = ["housing completed", "housing permitted", "housing approved", "affordable housing", "new apartments", "new ADU", "new house", "new building",
            "city capital project"]


def projects_bundle():
    p = SRC / "map_projects.geojson.gz"
    if not p.exists():
        return None
    g = gpd.read_file(f"/vsigzip/{p}")
    g = g[g.kind.isin(PJ_KINDS) & g.geometry.notna()]
    u = pd.to_numeric(g.units, errors="coerce")
    # single ADUs and houses are counted per neighborhood; the map shows projects of 5+ homes and city-tracked projects
    g = g[(u >= 5) | g.kind.isin(["affordable housing", "new apartments", "new building", "city capital project"])]
    txt = lambda v: v if isinstance(v, str) and v.strip() and v.strip().lower() != "nan" else None  # noqa: E731
    out = []
    for r in g.itertuples():
        u = r.units if r.units == r.units else None
        out.append([PJ_KINDS.index(r.kind), txt(r.name), txt(r.addr), txt(r.stage), int(u) if u else None, txt(str(r.year)), round(r.geometry.y, 5), round(r.geometry.x, 5)])
    return out



def round10_bundle():
    """Round-10 research for the page: plain zoning rows, city funding amounts, EIFD register, real funding stacks."""
    R = ROOT / "research" / "round10"
    if not R.exists():
        return None
    rd = lambda n: pd.read_csv(R / n, dtype=str).fillna("").rename(columns=lambda c: c.split(" ")[0])
    nr = lambda v: "" if str(v).strip().upper() in ("NR", "NAN") else str(v).strip()
    jn = lambda j: "Unincorporated LA County" if "Unincorporated" in j else j.replace(" / guide", "")
    zp = {}
    for _, r in rd("partT_zoning_plain.csv").iterrows():
        zp.setdefault(jn(r.jurisdiction), {})[r.code.strip()] = [nr(r.plain_meaning), nr(r.max_height_ft), nr(r.max_far_or_density), nr(r.min_lot_sqft), nr(r.adu_sb9)]

    def money(v):
        m = re.match(r"\s*([\d.,]+)\s*(million)?", str(v))
        if not m:
            return None
        x = float(m.group(1).replace(",", ""))
        return round(x * 1e6 if m.group(2) else x)
    keys = {"Proposition A local return": "pa", "Proposition C local return": "pc", "Measure R local return": "mr", "Measure M local return": "mm",
            "Measure W municipal projected return": "mw"}
    city = {}
    for _, r in rd("partU_funding.csv").iterrows():
        if ":" not in r["name"] or r.amount_unit.strip() != "annual":
            continue
        head, place = [x.strip() for x in r["name"].split(":", 1)]
        k = next((v for kk, v in keys.items() if head.lower() == kk.lower()), None)
        amt = money(r.amount)
        if k and amt:
            city.setdefault(place, {})[k] = amt
    ef = [[r.eifd_name, r.jurisdiction, nr(r.status), nr(r.participants_and_shares), nr(r.projected_increment_total), nr(r.projects)]
          for _, r in rd("partU_eifds.csv").iterrows()]
    TYPE = {"bus-lane corridor": ["bus_lane", "transit_priority", "brt"], "protected bike lane": ["protected_bike"], "street-tree program": ["street_trees", "tiny_forest"],
            "park": ["park_upgrade", "pocket_park", "rec_center"], "public pool": ["pool", "splash_pad"], "community clinic": ["clinic"],
            "EV fast-charging hub": ["ev_hub"], "library": ["library"], "road diet": ["road_diet", "slow_streets"], "rail station area": ["rail_station"],
            "river path": ["corridor_trail"], "affordable housing on public parking lot": ["affordable_housing"]}
    st = {}
    for (proj, typ), g in rd("partU_project_stacks.csv").groupby(["project", "improvement_type"], sort=False):
        tot = money(g.total_cost.iloc[0])
        src = [[r.funding_source, money(r.amount)] for _, r in g.iterrows() if money(r.amount)]
        if not tot or not src:
            continue
        NAMES = {"Colorado Avenue": ("Colorado Avenue protected bikeway", "under construction 2026"), "Signal Hill": ("Signal Hill street-tree planting (510 trees)", "completed 2026"),
                 "Houghton Park": ("Houghton Park Community Center expansion", "completed 2020"), "Carson aquatic": ("Carson pool repairs (3 pools)", "completed 2023"),
                 "Pomona Community": ("Pomona community wellness clinic renovation", "approved 2021"), "Arroyo Charging": ("Arroyo EV charging depot (city capital part)", "opened 2022"),
                 "Pasadena Central Library": ("Pasadena Central Library seismic retrofit", "under construction, due 2028"), "Willowbrook": ("Willowbrook/Rosa Parks station improvements", "completed 2021"),
                 "Taylor Yard": ("Taylor Yard bike/pedestrian bridge (construction)", "opened 2022"), "Hollywood Arts": ("Hollywood Arts Collective on a city parking lot (construction loans)", "completed 2023")}
        nm, stt = next((v for k, v in NAMES.items() if k in proj), (proj, nr(g.status.iloc[0]).split(";")[0]))
        clean = lambda x: re.sub(r";?\s*full sub-breakdown NR|,? ?approximately|, derived residual estimate| budget line|Fund\s?206", "", str(x)).replace("Proposition", "Prop").strip(" ,;")
        ex = {"p": nm, "c": g.city.iloc[0], "s": stt, "t": tot, "src": [[clean(n), a] for n, a in src]}
        for cid in TYPE.get(typ, []):
            st.setdefault(cid, ex)
    print(f"  round 10: {sum(len(v) for v in zp.values())} zoning rows, {len(city)} cities with funding amounts, {len(ef)} districts, {len(st)} funding examples")
    return {"zp": zp, "city": city, "eifds": ef, "stacks": st}


def compact_corridor(v):
    """[street, from, to, miles, buses/hr, existing-bike text, bus lane 0/1, SB 79 stops, SB 79 tiers, rail names, station]"""
    import re as _re
    bike = next((h for h in v.get("have", []) if "lane" in h or "path" in h or "sharrows" in h), None)
    bus = int(any("bus-only" in h for h in v.get("have", [])))
    s79 = next((p for p in v.get("plan", []) if "SB 79" in p), None)
    n79 = int(_re.match(r"(\d+)", s79).group(1)) if s79 else 0
    t79 = (_re.search(r"\(([^)]*)\)", s79).group(1) if s79 else "")
    rc = next((p for p in v.get("plan", []) if p.startswith("rail under construction")), None)
    rcn = (_re.search(r"\((.*)\)", rc).group(1) if rc and "(" in rc else ("" if not rc else "-"))
    return [v.get("st"), v.get("fr"), v.get("to"), v.get("mi"), v.get("tph"), bike, bus, n79, t79, rcn, v.get("station"),
            v.get("metro") or [], v.get("city") or [], v.get("metro_area") or []]


MONEY = {"cost", "capex", "land", "om", "value"}


def sig3(v):
    """Round dollar figures to 3 significant figures: the same on screen, and it compresses far better."""
    if not isinstance(v, (int, float)) or v != v or v == 0:
        return v
    from math import floor, log10
    d = 3 - int(floor(log10(abs(v)))) - 1
    return int(round(v, d)) if d <= 0 else round(v, d)

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
    und = json.loads((MOD / "underused.json").read_text()) if (MOD / "underused.json").exists() else {"sites": [], "bg": {}, "profit": {}, "bg_pct": {}, "soon": {}}
    cat = meta["catalog"]
    bg = gpd.read_file(SRC / "map_block_groups.geojson")
    bg["geometry"] = bg.to_crs(M).geometry.simplify(14).to_crs(4326)
    bg = bg.merge(d, on="GEOID", how="left")
    col = lambda c: bg[c] if c in bg else pd.Series(np.nan, index=bg.index)  # noqa: E731
    props = pd.DataFrame({"id": bg.GEOID, "n": bg.hood.fillna(bg.city), "c": bg.city, "h": col("homes"), "v": col("top_vpd"), "t": col("top"),
                          "pc": col("pkg_cost"), "hv": col("home_value"), "ht": col("temp_diff_f"), "vc": col("violent_per_1k"),
                          "pa": col("park_acres_half_mile"), "bt": col("bus_max_tph_400m"), "ts": col("vacant_tree_sites")})
    props["pp"] = props["id"].map(lambda x: (und.get("bg_pct") or {}).get(x))
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
    gp = json.loads((MOD / "gaps.json").read_text()) if (MOD / "gaps.json").exists() else {"bg": {}, "plans": {}}
    sb_d = {}
    sbp = SRC / "map_sb79.geojson"
    if sbp.exists():
        sbg = gpd.read_file(sbp)
        sbg = sbg[sbg.geom_type.eq("Point") & sbg.SB79_TIER.notna()].to_crs(M) if "SB79_TIER" in sbg else sbg.iloc[:0]
        bpt = gpd.read_file(SRC / "map_block_groups.geojson")[["GEOID", "geometry"]].to_crs(M)
        bpt["geometry"] = bpt.geometry.representative_point()
        for tier in ("T1", "T2"):
            sub = sbg[sbg.SB79_TIER.astype(str).str.upper().eq(tier)]
            if len(sub):
                j = gpd.sjoin_nearest(bpt, sub[["geometry"]], how="left", distance_col="d").drop_duplicates("GEOID")
                for gid_, dd_ in zip(j.GEOID, j.d):
                    sb_d.setdefault(gid_, [None, None])[0 if tier == "T1" else 1] = round(float(dd_))
    corr = json.loads((MOD / "corridors.json").read_text()) if (MOD / "corridors.json").exists() else {}
    ef = MOD / "eifd.json"
    eifd = json.loads(ef.read_text()) if ef.exists() else {"meta": {}, "bg": {}}
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
             "pop": g_("population", 0), "inc": g_("median_household_income", 0), "rent": g_("median_gross_rent", 0), "fire": g_("fire_vh_share", 2), "yb": g_("median_year_built", 0),
             "sf": num(100 * r.sf_share, 0) if r.get("sf_share") == r.get("sf_share") else None, "nocar": num(100 * r.no_car_share, 0) if r.get("no_car_share") == r.get("no_car_share") else None,
             "st": g_("street_trees", 0), "ts": g_("vacant_tree_sites", 0), "tg": g_("tc_gap", 0),
             "pcr": g_("property_crimes", 0) if r.get("crime_covered") else None, "ksi": g_("crashes_ksi", 0), "dump": g_("illegal_dumping", 0) if r.get("in_311") else None,
             "graf": g_("graffiti", 0) if r.get("in_311") else None, "fw": g_("freeway_nearest_m", 0), "gro": g_("grocery_nearest_m", 0),
             "din": g_("dining_within_400m", 0), "ten": g_("tennis_nearest_m", 0), "dog": g_("dog_park_nearest_m", 0), "pool": g_("pool_nearest_m", 0),
             "ev": g_("ev_charger_nearest_m", 0)}
        if m["rm"] and m["rm"] >= 1e9:
            m["rm"] = None
        m = {k: v for k, v in m.items() if v is not None and not (isinstance(v, float) and np.isnan(v))}
        if gid in eifd["bg"]:
            e_ = dict(eifd["bg"][gid])
            e_["t"] = [[t_, sig3(v_)] for t_, v_ in e_.get("t", [])]
            for k_ in ("av", "avr", "avc"):
                if k_ in e_:
                    e_[k_] = sig3(e_[k_])
            m["e"] = e_
        if gid in gp["bg"]:
            gg = gp["bg"][gid]
            m["gp"] = {"g": [[r_[0]] + r_[2:8] for r_ in gg["g"]], "s": [[r_[0]] + r_[2:] for r_ in gg["s"]]}
        fc = {k: num(r[f"fac_{k.replace(' ', '_')}_m"], 0) for k in FAC_KINDS if f"fac_{k.replace(' ', '_')}_m" in r.index}
        fc = {k: v for k, v in fc.items() if v is not None}
        if fc:
            m["fc"] = fc
        if r.get("zone_coverage", 0) == r.get("zone_coverage", 0) and (r.get("zone_coverage") or 0) > 0.05:
            m["z"] = {"j": r.get("zone_juris"), "top": r.get("zone_top"), "cov": num(r.get("zone_coverage"), 2),
                      "sh": {c: num(r.get("zshare_" + re.sub(r"\W+", "_", c).strip("_")), 3) for c in ZCATS
                             if (r.get("zshare_" + re.sub(r"\W+", "_", c).strip("_")) or 0) > 0}}
        if gid in corr:
            m["co"] = {k: compact_corridor(v) for k, v in corr[gid].items()}
        if gid in sb_d:
            m["sb"] = sb_d[gid]
        m["tr"] = [num(r.get("rail_station_nearest_m"), 0), num(r.get("rail_stop_nearest_m"), 0), num(r.get("bus_max_tph_400m"), 0), num(r.get("bus_max_tph_800m"), 0)]
        det[gid] = {"r": [[sig3(rec[k]) if k in MONEY else (num(rec[k], 3) if isinstance(rec[k], float) else rec[k]) for k in keys] for rec in x["recs"]], "m": m}

    L = {"freeways": layer("freeways", 40, ["name"], {"name": "n"}, prec=4), "arterials": merged_lines("arterials", 25),
         "parks": layer("parks", 20, ["name", "acres"], {"name": "n", "acres": "a"}, min_area_ac=2, prec=5), "water": layer("water", 40, [], prec=4),
         "rail": merged_lines("rail", 25), "stations": layer("stations", None, ["name"], {"name": "n"}),
         "walls": layer("noise_walls", 10, [], prec=5), "amenities": layer("amenities", None, ["kind", "name"], {"kind": "k", "name": "n"})}
    pk_all, park_labels = parks_bundle()
    if pk_all:
        L["parks"] = pk_all
    L["park_labels"] = park_labels
    L["streets"] = streets_bundle()
    L["facilities"] = facilities_bundle()
    L["fac_kinds"] = FAC_KINDS
    L["zoning"] = zoning_bundle()
    L["projects"] = projects_bundle()
    L["pj_kinds"] = PJ_KINDS
    L["fac_areas"] = facility_areas_bundle()
    under, L["underused"] = underused_bundle()
    L["rail_con"] = lines_bundle("rail_construction", ["name"])
    L["stations_con"] = lines_bundle("stations_construction", ["name"])
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
    if L.get("streets"):
        nst = sum(len(v) for v in L["streets"]["cells"].values())
        src_rows.append(["Street names and freeway route numbers (OpenStreetMap)", '<span class="pill ok">loaded</span>',
                         f"{len(L['streets']['names']):,} named streets in {nst:,} map pieces; local streets appear from zoom 14, names from zoom 15"])
    if pk_all:
        kinds = pd.Series([f["properties"]["k"] for f in pk_all["features"]]).value_counts()
        small = sum(1 for f in pk_all["features"] if (f["properties"]["a"] or 0) < 1)
        src_rows.append(["Parks: OpenStreetMap plus LA County Countywide Parks and Open Space (DPR)", '<span class="pill ok">loaded</span>',
                         f"{len(pk_all['features']):,} parks and open spaces ({small:,} under an acre); " + ", ".join(f"{k}: {v:,}" for k, v in kinds.items())])
    if L.get("facilities"):
        kinds = pd.Series([FAC_KINDS[x[0]] for x in L["facilities"]]).value_counts()
        src_rows.append(["Public facilities: LA County Location Management System + OpenStreetMap", '<span class="pill ok">loaded</span>',
                         f"{len(L['facilities']):,} sites: " + ", ".join(f"{k} {v:,}" for k, v in kinds.items())])
    zs = st.get("zoning", {})
    if zs:
        ok_src = [k for k, v in (zs.get("sources") or {}).items() if str(v).startswith("ok")]
        src_rows.append(["Zoning: official city/County layers, SCAG 2019 parcel zoning elsewhere", '<span class="pill ok">loaded</span>' if zs.get("ok") else '<span class="pill miss">partial</span>',
                         f"live layers: {', '.join(ok_src)}; " + (f"SCAG 2019 fills {zs.get('scag_bgs_filled'):,} block groups" if zs.get("scag_bgs_filled") else "SCAG fallback not loaded")])
    ps = st.get("projects", {})
    if ps:
        bk = ps.get("by_kind", {})
        src_rows.append(["Work under way: HCD housing progress reports (all cities), LAHD affordable pipeline, LADBS new-building permits",
                         '<span class="pill ok">loaded</span>' if ps.get("ok") else '<span class="pill miss">partial</span>',
                         "; ".join(f"{k} {v:,}" for k, v in bk.items())])
        if ps.get("he_sites"):
            src_rows.append(["Housing Element site inventories (SCAG consolidated + LA County)", '<span class="pill ok">loaded</span>',
                             f"{ps['he_sites']:,} parcels cities listed for ~{ps.get('he_capacity', 0):,.0f} homes; used to flag underused sites"])
    rc = SRC / "research_check.json"
    if rc.exists():
        rr = json.loads(rc.read_text())["results"]
        for frm, lab in (("partA_audit", "Round-6 Part A audit"), ("pasted_report", "Round-6 long report")):
            sub = [x for x in rr if x["from"] == frm]
            if sub:
                src_rows.append([f"{lab}: its data links, tested from GitHub Actions", '<span class="pill ok">checked</span>',
                                 f"{sum(1 for x in sub if x.get('ok'))} of {len(sub)} links returned data"])
    em = eifd.get("meta", {})
    if em:
        src_rows.append(["EIFD calculator: Assessor roll values by parcel and tax-rate area", '<span class="pill ok">loaded</span>',
                         f"roll year {em.get('roll_year')}; net taxable value ${em.get('county_net_av', 0) / 1e12:.2f} trillion; "
                         f"{em.get('roll_value_matched_share', 0):.2%} of it matched to a tax-rate area with factors"])
        src_rows.append([f"EIFD calculator: Auditor-Controller {em.get('factor_year')} Modified ATI ratios (AF49)", '<span class="pill ok">loaded</span>',
                         f"{em.get('tras_with_factors', 0):,} tax-rate areas; {em.get('rows', 0):,} agency shares; report dated {em.get('prepared')}"])
    pr = sorted((und.get("profit") or {}).items(), key=lambda kv: -kv[1]["total"])[:30]
    profit_rows = [[k.split("|")[0], k.split("|")[1], f"${v['total'] / 1e6:,.1f}M", f"{v['pct']:.1%}" if v.get("pct") is not None else "few homes", f"${v['per_home']:,.0f}",
                    f"${v['proj'] / 1e6:,.1f}M", f"${v['land'] / 1e6:,.1f}M", ", ".join(v.get("soon") or []) or "–"] for k, v in pr]
    bg_hood = dict(zip(d.GEOID, d.hood.fillna(d.city) + ", " + d.city))
    site_rows = [[s_["k"] + (f" ({s_['nm']})" if s_.get("nm") else ""), (s_.get("ad") or bg_hood.get(s_["gid"], "")), f"{s_['ac']:,.1f}",
                  f"${s_['lav'] / 1e6:,.1f}M" if s_.get("lav") else "–", f"${s_['mkt'] / 1e6:,.1f}M" if s_.get("mkt") else "–",
                  s_.get("z") or s_.get("zc") or "–", s_["idea"]] for s_ in sorted(und.get("sites", []), key=lambda x: -(x.get("mkt") or 0))[:25]]
    from collections import Counter
    gcnt = Counter(r[1] for v in gp["bg"].values() for r in v["g"])
    gap_rows = [[k[0].upper() + k[1:], f"{v:,}", f"{v / max(len(gp['bg']), 1):.0%}"] for k, v in gcnt.most_common(22)]
    named = d.hood_source.value_counts()
    rep = {"title": "City Pretty: Los Angeles County",
           "paragraphs": [
               f"{len(d):,} Census block groups (about 1,500 people each) across all of LA County, {d.homes.sum():,.0f} homes. For each one, City Pretty checks {len(lib)} kinds of improvement, from street trees and bus lanes to pickleball courts, sound walls, foot patrols, power-line undergrounding and zoning. It sizes each to the area's actual conditions and prices the whole project: build cost, land and ten years of upkeep.",
               "Improvements with a measured effect on home prices are ranked by the home value they add per $1. Improvements without one (pools, crosswalks, litter crews, clinics) are still costed. They're ranked by how much the area needs them compared with the rest of the county.",
               "Click any area for its ranked list, the total cost, the reasoning and the sources. Use the category buttons to see just transit, safety, parks and so on."],
           "sections": [
               {"title": "Your neighborhoods", "table": {"head": ["Area", "Block groups", "Homes", "Median home value", "Best bet in its best block group", "$ per $1", "Cost of all paying projects"], "rows": focus, "num": [1, 2, 3, 5, 6]}},
               {"title": "Most profitable neighborhoods", "paragraphs": [
                   "Value created if every project that returns at least $1 per $1 were built (net of its cost), plus the rough development margin on the neighborhood's underused land. The margin uses stated assumptions for build cost and new-home prices until round-7 research replaces them. Pick <b>Profit potential</b> under 'Color areas by' to see it on the map."],
                "table": {"head": ["Neighborhood", "City", "Value created", "% of home value", "Per home", "From projects", "From underused land", "Rail coming"], "rows": profit_rows, "num": [2, 3, 4, 5, 6]}},
               {"title": "Largest underused sites", "paragraphs": [f"{len(und.get('sites', [])):,} sites of a quarter acre or more: Assessor parcels coded as parking or golf, vacant parcels of half an acre or more, commercial and industrial lots where buildings are worth less than 20% of the land, and surface lots of an acre or more mapped in OpenStreetMap. Turn on <b>Underused land</b> and click a site for details."],
                "table": {"head": ["Site", "Where", "Acres", "Assessed land", "Market land (est.)", "Zoning", "Could be"], "rows": site_rows, "num": [2, 3, 4]}},
               {"title": "What neighborhoods are missing most often", "paragraphs": ["Each block group is compared with the 50 most similar block groups in the county. A gap means it is worse than at least 80% of them by a meaningful margin. Click any area for its own gaps and a plan for its neighborhood."],
                "table": {"head": ["Gap", "Block groups with it", "Share"], "rows": gap_rows, "num": [1, 2]}},
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
                   "<b>EIFD calculator.</b> The base value is the net taxable value on the 2026 Assessor roll for every parcel in the area. City and County shares are the Auditor-Controller's FY 2026-27 tax-increment ratios for the area's actual tax-rate areas, weighted by value. They match the published West Carson plan (County 30.46%) and Pasadena's draft plan (city 21.1%, County 27.9%). Growth, interest and coverage are still your assumptions, and areas already in an EIFD are flagged.",
                   "<b>Round-6 research.</b> Two answers came back. The Part A audit's 14 data links all worked. The long report marked everything 'verified', but only 11 of its 34 links returned data, and some of its tax-credit claims were out of date. So its new improvements are graded <b>U (unverified lead)</b> and hidden unless you pick 'Also show unverified leads'. Its quality-of-life dollar values and homeowner upgrade figures are shown with that label.",
                   "<b>Round-7 research and profit math.</b> Apartment value = local rent (LA Q3 2026 averages scaled by the area's rents, plus 15% for new buildings) less 35% for costs and vacancy, divided by the 5.9% cap rate. Build cost = LA case-study hard costs ($268-334/sq ft in 2023, escalated 4% a year) plus 30% soft costs and $25k fees. Market land prices, current fee schedules and submarket rents for new buildings were not recovered, so those parts remain estimates.",
                   "<b>Zoning.</b> City of LA and unincorporated County zoning come from the official live layers. Santa Clarita's comes from the city's own layer. Other cities use SCAG's 2019 parcel dataset, which may be out of date. Standards (height, density, setbacks) are listed only for zones the research covered, and need checking against each city's code.",
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
    bundle = {"meta": {"built": date.today().isoformat(), "default_bg": default, "search": search, "rent_med": float(d.median_gross_rent.median())}, "bgs": bgs, "details": det, "catalog": lib, "funding": meta.get("funding", {}), "eifd": eifd["meta"], "r10": round10_bundle(), "upgrades": meta.get("owner_upgrades", []), "plans": gp["plans"], "gap_labels": {r_[0]: r_[1] for v in gp["bg"].values() for r_ in v["g"] + v["s"]},
              "under": {"sites": und.get("sites", []), "profit": und.get("profit", {}), "soon": und.get("soon", {}), "assumptions": und.get("assumptions", {})},
              "zone_rules": pd.read_csv(ROOT / "model" / "round6" / "zone_rules.csv").to_dict("records"),
              "layers": L, "hoods": hoods_js, "hood_labels": labels(bgn, "hood"), "cities": city_js,
              "city_labels": labels(cities.rename(columns={"name": "nm"}), "nm"), "report": rep}
    # Speed: block-group details (over half the data) are only needed when someone opens a block group,
    # so they ship as small gzip chunks keyed by the first 8 digits of the GEOID (state+county+tract prefix,
    # so nearby block groups share a chunk). The page unpacks a chunk the first time any id in it is read.
    det_all = bundle.pop("details")
    # The map colors every block group by its best improvement under the "Evidence shown" filter. Precompute that
    # for each filter setting so the page doesn't have to open every block group's details at start (retop()).
    def best_for(gid, thr):
        best, pc = None, 0
        for a in (det_all.get(gid) or {}).get("r") or []:
            c = lib.get(a[0]) or {}
            g = c.get("grade", "none")
            if c.get("kind") != "value" or not (g == "none" or g <= thr):
                continue
            if best is None or (a[8] or 0) > (best[8] or 0):
                best = a
            if (a[8] or 0) >= 1:
                pc += a[3] or 0
        return [best[0] if best and (best[8] or 0) >= 1 else None, best[8] if best else None, pc or None]
    for f in bundle["bgs"]["features"]:
        f["properties"]["tp"] = [best_for(f["properties"]["id"], thr) for thr in EVID_ORDER]
    chunks = {}
    for gid, v in det_all.items():
        chunks.setdefault(gid[:CHUNK_KEY], {})[gid] = v
    det_b64 = {k: base64.b64encode(gzip.compress(re.sub(r"\bNaN\b", "null", json.dumps(v, separators=(",", ":"), default=str)).encode(), 9)).decode()
               for k, v in chunks.items()}
    det_json = json.dumps({"key": CHUNK_KEY, "chunks": det_b64}, separators=(",", ":"))
    ov = overlays_bundle()
    ov_json = json.dumps(ov, separators=(",", ":")) if ov else "null"
    raw = json.dumps(bundle, separators=(",", ":"), default=str)
    raw = re.sub(r"\bNaN\b", "null", raw).encode()
    b64 = base64.b64encode(gzip.compress(raw, 9)).decode()
    base_css = re.search(r"<style>\n(/\* Layout.*?)</style>", (WEB / "focus.src.html").read_text(), re.S).group(1)
    html = (WEB / "county.src.html").read_text()
    html = html.replace("/*BASE_CSS*/", base_css).replace("/*LEAFLET_CSS*/", (WEB / "leaflet-1.9.4.css").read_text())
    html = html.replace("/*LEAFLET_JS*/", (WEB / "leaflet-1.9.4.js").read_text().replace("</script", "<\\/script"))
    html = html.replace("/*FFLATE_JS*/", (WEB / "fflate-0.8.3.min.js").read_text().replace("</script", "<\\/script"))
    html = html.replace("/*DETAILS*/", det_json).replace("/*OVERLAYS*/", ov_json)
    html = html.replace("/*EYEBROW*/", f"CITY PRETTY · ALL OF LOS ANGELES COUNTY · {date.today():%d %b %Y}".upper()).replace("/*BUNDLE*/", b64)
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(html)/1e6:.1f} MB; core data {len(raw)/1e6:.1f} MB raw, unpacked at start; "
          f"{len(det_all)} block-group details in {len(chunks)} chunks, unpacked on demand)")


if __name__ == "__main__":
    main()
