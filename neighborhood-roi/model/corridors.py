"""Name the street and segment for every transit, bike and street-safety suggestion, and what already exists there.

For each block group with a corridor-type recommendation:
  bus lane / BRT / signal priority / bus shade  -> the arterial at the area's busiest bus stop (else its longest arterial)
  protected bike lane / road diet                -> the longest collector (else arterial) without a protected lane or path
  speed cameras                                  -> the longest arterial
  slow streets / traffic calming                 -> the longest local street
  new rail                                       -> the busiest bus corridor, linking to the nearest station
The segment runs between the cross streets where that street enters and leaves the area (plus 200 m).
"Already there / planned" uses existing bikeways (OSM), LA City bus lanes, rail under construction (OSM) and
SCAG's official SB 79 stops. City and Metro plan layers are added when round-8 research supplies them.

Reads data/derived/county_la + web/county_data/details.json; writes web/county_data/corridors.json.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent.parent
SRC, MOD = ROOT / "data" / "derived" / "county_la", ROOT / "web" / "county_data"
M = 3310
MI = 1609.34
BUS = {"bus_lane", "brt", "transit_priority", "transit_shade", "bus_shelters"}
BIKE = {"protected_bike", "road_diet"}
ART = {"speed_cameras"}
LOCAL = {"slow_streets", "traffic_calming"}
RAIL = {"rail_station"}
WANT = BUS | BIKE | ART | LOCAL | RAIL


def read(name):
    p = SRC / name
    if not p.exists():
        return None
    return gpd.read_file(f"/vsigzip/{p}" if name.endswith(".gz") else p).to_crs(M)


def pretty(n):
    return str(n).replace(" Boulevard", " Blvd").replace(" Avenue", " Ave").replace(" Street", " St").replace(" Drive", " Dr")


class Streets:
    def __init__(self, g):
        g = g[g.cls.isin([1, 2, 3]) & g.name.notna()].reset_index(drop=True)
        self.g, self.tree = g, STRtree(list(g.geometry))

    def near(self, geom, classes=(1, 2, 3)):
        idx = self.tree.query(geom)
        sub = self.g.iloc[idx]
        return sub[sub.cls.isin(classes)]

    def cross(self, pt, name, radius=90):
        """Name of the most important other street meeting this point."""
        sub = self.near(pt.buffer(radius))
        sub = sub[sub.name != name]
        if not len(sub):
            return None
        d = sub.distance(pt)
        best = sub.assign(d=d).sort_values(["cls", "d"]).iloc[0]
        return pretty(best["name"])


def pick(streets, area, classes, avoid=None):
    """Longest street (by length inside the area) among the given classes, skipping names in `avoid`."""
    sub = streets.near(area, classes)
    if not len(sub):
        return None
    clip = sub.assign(geometry=sub.geometry.intersection(area))
    clip = clip[~clip.geometry.is_empty]
    if not len(clip):
        return None
    ln = clip.groupby("name").geometry.apply(lambda s: s.length.sum()).sort_values(ascending=False)
    for n in ln.index:
        if avoid and n in avoid:
            continue
        return n
    return ln.index[0]


def segment(streets, area, name):
    sub = streets.g[streets.g.name == name]
    sub = sub[sub.intersects(area)]
    geom = unary_union([g.intersection(area) for g in sub.geometry])
    if geom.is_empty:
        return None
    if geom.geom_type == "MultiLineString":
        geom = linemerge(geom)
    parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    parts = [p for p in parts if p.geom_type == "LineString"]
    if not parts:
        return None
    ln = max(parts, key=lambda p: p.length)
    a, b = ln.interpolate(0), ln.interpolate(1, normalized=True)
    return {"line": ln, "fr": streets.cross(a, name), "to": streets.cross(b, name), "mi": round(ln.length / MI, 2)}


def main():
    details = json.loads((MOD / "details.json").read_text())
    st = read("map_streets.geojson.gz")
    streets = Streets(st)
    bg = gpd.read_file(SRC / "map_block_groups.geojson")[["GEOID", "geometry"]].to_crs(M).set_index("GEOID")
    stops = read("map_frequent_stops.geojson")
    bikes = read("map_bikeways.geojson.gz")
    buslanes = read("map_bus_lanes.geojson")
    railcon = read("map_rail_construction.geojson")
    stations = read("map_stations.geojson")
    sb79 = read("map_sb79.geojson")
    if sb79 is not None:
        sb79 = sb79[sb79.geom_type.eq("Point")]
    stop_tree = STRtree(list(stops.geometry)) if stops is not None and len(stops) else None
    bike_tree = STRtree(list(bikes.geometry)) if bikes is not None and len(bikes) else None

    def existing_bike(line):
        if bike_tree is None:
            return None, 0.0
        b = line.buffer(15)
        sub = bikes.iloc[bike_tree.query(b)]
        if not len(sub):
            return None, 0.0
        cov = sub.geometry.intersection(b).length
        share = float(min(cov.sum() / max(line.length, 1), 1))
        order = ["protected lane (Class IV)", "bike path (Class I)", "painted lane (Class II)", "sharrows (Class III)"]
        best = next((c for c in order if (sub.cls == c).any() and cov[sub.cls == c].sum() > 0.2 * line.length), None)
        return best, share

    out = {}
    for gid, d in details.items():
        ids = {r["id"] for r in d["recs"]} & WANT
        if not ids or gid not in bg.index:
            continue
        area = bg.loc[gid, "geometry"].buffer(200)
        res = {}
        # bus street: the arterial at the busiest frequent stop
        bus_name, top_tph = None, 0
        if stop_tree is not None:
            sidx = stop_tree.query(area)
            if len(sidx):
                s = stops.iloc[sidx]
                s = s[s.within(area)]
                if len(s):
                    best = s.sort_values("tph", ascending=False).iloc[0]
                    top_tph = float(best.tph)
                    near = streets.near(best.geometry.buffer(60), (1, 2))
                    if len(near):
                        bus_name = near.assign(dd=near.distance(best.geometry)).sort_values(["dd", "cls"]).iloc[0]["name"]
        art = pick(streets, area, (1,))
        bus_name = bus_name or art
        names = {}
        if ids & (BUS | RAIL) and bus_name:
            names["bus"] = bus_name
        if ids & BIKE:
            avoid = set()
            for cand_cls in ((2,), (1,)):
                n = pick(streets, area, cand_cls)
                if n:
                    sg = segment(streets, area, n)
                    if sg and existing_bike(sg["line"])[0] in ("protected lane (Class IV)", "bike path (Class I)"):
                        avoid.add(n)
                        n = pick(streets, area, cand_cls, avoid)
                    if n:
                        names["bike"] = n
                        break
        if ids & ART and art:
            names["art"] = art
        if ids & LOCAL:
            n = pick(streets, area, (3,))
            if n:
                names["local"] = n
        segs = {}
        for role, n in names.items():
            sg = segment(streets, area, n)
            if not sg:
                continue
            have, plan = [], []
            bcls, bshare = existing_bike(sg["line"])
            if bcls:
                have.append(f"{bcls} on {bshare:.0%} of this stretch")
            if buslanes is not None and len(buslanes):
                bl = buslanes[buslanes.distance(sg["line"]) < 40]
                if len(bl):
                    have.append("bus-only lane on part of it (LA City)")
            if sb79 is not None and len(sb79):
                on = sb79[sb79.distance(sg["line"]) < 60]
                if len(on):
                    tiers = sorted(set(on.get("SB79_TIER", pd.Series(dtype=str)).dropna().astype(str)))
                    plan.append(f"{len(on)} official SB 79 transit stop{'s' if len(on) > 1 else ''} on this stretch ({', '.join(tiers)}): state law already allows more homes here")
            if railcon is not None and len(railcon):
                rc = railcon[railcon.distance(sg["line"]) < 1200]
                if len(rc):
                    nm = sorted({str(x) for x in rc["name"].dropna()})[:2]
                    plan.append("rail under construction nearby" + (f" ({'; '.join(nm)})" if nm else ""))
            segs[role] = {"st": pretty(n), "fr": sg["fr"], "to": sg["to"], "mi": sg["mi"], "have": have, "plan": plan}
        if "bus" in segs and top_tph:
            segs["bus"]["tph"] = round(top_tph)
        if ids & RAIL and "bus" in segs and stations is not None and len(stations):
            c = bg.loc[gid, "geometry"].centroid
            sn = stations.assign(dd=stations.distance(c)).sort_values("dd").iloc[0]
            segs["bus"]["station"] = [str(sn["name"]) if isinstance(sn["name"], str) else None, round(float(sn.dd) / MI, 1)]
        if segs:
            out[gid] = segs
    (MOD / "corridors.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(out):,} block groups with named corridors; bikeways loaded: {bikes is not None}")
    for gid in list(out)[:5]:
        print(gid, json.dumps(out[gid])[:400])


if __name__ == "__main__":
    main()
