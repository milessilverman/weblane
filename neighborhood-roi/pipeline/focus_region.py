"""Block-level data for a focus region (first: LA Westside incl. Culver City).

Builds "blocks" = polygons enclosed by arterials, freeways, rail, creeks and city
limits (the units neighborhoods are actually made of), names them, and attaches
real local data: street-tree inventories with vacant planting sites, 1 m canopy
height (Meta/WRI), assessor parcels (vacant lots, homes, land value), LAPD crime,
Census block-group ACS, Tree Equity heat, Zillow neighborhood values, schools,
parks, plus map detail layers.

    python neighborhood-roi/pipeline/focus_region.py la_westside
"""
import io
import json
import math
import os
import re
import sys
import time
import traceback
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box, Point
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dataset as bd  # noqa: E402  (shared download helpers)

log, get, cached_download, CACHE = bd.log, bd.get, bd.cached_download, bd.CACHE

REGIONS = {
    "la_westside": {
        "label": "LA Westside & Culver City",
        "bbox": (-118.505, 33.955, -118.330, 34.090),  # W S E N
        "state": "06", "county": "037", "geofabrik": "north-america/us/california/socal",
        "zillow_county": "Los Angeles County",
        "tree_sources": ["culver-city", "beverly-hills", "santa-monica", "inglewood", "west-hollywood"],
        "la_city_wfs": True,
    },
}
OUT_ROOT = Path(__file__).resolve().parent.parent / "data" / "derived"
STATUS = {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": {}}
M = 3310  # California Albers (meters)


def stage(name):
    def deco(fn):
        def run(*a, **k):
            log(f"== {name}")
            t = time.time()
            try:
                res = fn(*a, **k)
                info = {"ok": True, "seconds": round(time.time() - t, 1)}
                if isinstance(res, (pd.DataFrame, gpd.GeoDataFrame)):
                    info["rows"] = len(res)
                    info["columns"] = list(map(str, res.columns))[:60]
                STATUS["sources"][name] = {**STATUS["sources"].get(name, {}), **info}
                return res
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                STATUS["sources"][name] = {**STATUS["sources"].get(name, {}), "ok": False, "error": str(e)[:600]}
                return None
        return run
    return deco


def note(name, **kw):
    STATUS["sources"].setdefault(name, {}).update(kw)


# ------------------------------------------------------------------ OSM layers
@stage("osm_layers")
def osm_layers(R):
    w, s, e, n = R["bbox"]
    pbf = cached_download(f"https://download.geofabrik.de/{R['geofabrik']}-latest.osm.pbf", "geofabrik_focus.osm.pbf", 25)
    cut = CACHE / "focus.pbf"
    bd._sh("osmium", "extract", "-b", f"{w},{s},{e},{n}", str(pbf), "-o", str(cut), "--overwrite", "-s", "complete_ways")
    out = {}

    def layer(name, *exprs):
        f, g = CACHE / f"focus_{name}.pbf", CACHE / f"focus_{name}.geojson"
        bd._sh("osmium", "tags-filter", str(cut), *exprs, "-o", str(f), "--overwrite")
        bd._sh("osmium", "export", str(f), "-o", str(g), "--overwrite", "-f", "geojson", "-a", "type,id")
        d = gpd.read_file(g)
        log(f"  {name}: {len(d)} features")
        return d

    out["roads"] = layer("roads", "w/highway=motorway,trunk,primary,secondary,tertiary,residential,unclassified,living_street,motorway_link,trunk_link,primary_link")
    out["water"] = layer("water", "w/waterway=river,canal,stream,drain", "wr/natural=water")
    out["rail"] = layer("rail", "w/railway=rail,light_rail,subway")
    out["parks"] = layer("parks", "wr/leisure=park,garden,nature_reserve,playground,recreation_ground,pitch,golf_course")
    out["schools"] = layer("schools", "nwr/amenity=school,college,university")
    out["places"] = layer("places", "nwr/place=neighbourhood,suburb,quarter")
    out["stations"] = layer("stations", "nwr/railway=station", "nwr/public_transport=station")
    out["landuse"] = layer("landuse", "wr/landuse=residential,commercial,retail,industrial")
    return out


# ------------------------------------------------------------------ boundaries
@stage("boundaries")
def boundaries(R):
    st = R["state"]
    pl = gpd.read_file("zip://" + str(cached_download(f"https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_{st}_place_500k.zip", f"place_{st}.zip", 300)))
    bg = gpd.read_file("zip://" + str(cached_download(f"https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_{st}_bg_500k.zip", f"bg_{st}.zip", 300)))
    clip = box(*R["bbox"])
    pl = pl.to_crs(4326)
    pl = pl[pl.intersects(clip)][["NAME", "NAMELSAD", "LSAD", "geometry"]]
    bg = bg.to_crs(4326)
    bg = bg[bg.intersects(clip) & (bg.ALAND > 0)][["GEOID", "ALAND", "geometry"]]
    lat = gpd.read_file(get("https://raw.githubusercontent.com/codeforamerica/click_that_hood/main/public/data/los-angeles.geojson").text)
    lat = lat.to_crs(4326)[["name", "geometry"]].rename(columns={"name": "la_hood"})
    lat = lat[lat.intersects(clip)]
    note("boundaries", places=len(pl), block_groups=len(bg), la_times_hoods=len(lat))
    return pl, bg, lat


# ------------------------------------------------------------------ blocks
@stage("blocks")
def build_blocks(R, osm, pl, bg, lat):
    clip = box(*R["bbox"])
    roads = osm["roads"]
    major = roads[roads.highway.isin(["motorway", "trunk", "primary", "secondary", "tertiary"])]
    lines = list(major.geometry)
    if osm.get("rail") is not None:
        lines += list(osm["rail"].geometry)
    w = osm.get("water")
    if w is not None and len(w):
        ww = w[w.get("waterway", pd.Series(index=w.index)).isin(["river", "canal"])]
        lines += list(ww.geometry)
    lines += [g.boundary for g in pl.geometry]           # city limits
    lines += [g.boundary for g in lat.geometry]          # LA Times neighborhood edges
    lines.append(clip.boundary)
    lines = [ln.intersection(clip) for ln in lines if ln is not None and not ln.is_empty]
    merged = unary_union(lines)
    polys = list(polygonize(merged))
    land = unary_union(list(bg.geometry)).intersection(clip)
    b = gpd.GeoDataFrame(geometry=polys, crs=4326)
    b["geometry"] = b.geometry.intersection(land)
    b = b[~b.geometry.is_empty & b.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    b = b.explode(index_parts=False).reset_index(drop=True)
    b["acres"] = b.to_crs(M).area / 4046.86
    # merge slivers (< 3 acres) into the neighbor they share the longest edge with
    small = b[b.acres < 3].index
    big = b[b.acres >= 3].copy()
    bsi = big.sindex
    for i in small:
        g = b.geometry[i]
        cand = list(bsi.query(g.buffer(1e-6), predicate="intersects"))
        if not cand:
            continue
        best = max(cand, key=lambda j: big.geometry.iloc[j].buffer(1e-6).intersection(g).length if True else 0)
        idx = big.index[best]
        big.at[idx, "geometry"] = unary_union([big.geometry[idx], g])
    b = big.reset_index(drop=True)
    b["acres"] = b.to_crs(M).area / 4046.86
    b["block_id"] = [f"B{i:05d}" for i in range(len(b))]
    log(f"  {len(b)} blocks (median {b.acres.median():.0f} acres)")
    return b


@stage("naming")
def name_blocks(b, osm, pl, lat):
    rep = b.copy()
    rep["geometry"] = b.to_crs(M).geometry.representative_point().to_crs(4326)
    j = gpd.sjoin(rep, pl[["NAME", "LSAD", "geometry"]], predicate="within", how="left").drop_duplicates("block_id")
    b["city"] = j.set_index("block_id").reindex(b.block_id)["NAME"].fillna("Unincorporated LA County").values
    j2 = gpd.sjoin(rep, lat, predicate="within", how="left").drop_duplicates("block_id")
    b["la_hood"] = j2.set_index("block_id").reindex(b.block_id)["la_hood"].values
    places = osm["places"].copy()
    places["geometry"] = places.geometry.representative_point()
    places = places[places["name"].notna()].to_crs(M)
    parks = osm["parks"]
    parks = parks[parks.geom_type.isin(["Polygon", "MultiPolygon"]) & parks["name"].notna()].to_crs(M)
    parks = parks[parks.get("leisure", pd.Series(index=parks.index)).isin(["park", "recreation_ground"])]
    rp = rep.to_crs(M)
    osm_name, near_park, near_park_m = [], [], []
    for g, city in zip(rp.geometry, b.city):
        # OSM neighborhood label inside or within 600 m
        d = places.distance(g)
        k = d.idxmin() if len(d) else None
        osm_name.append(places.loc[k, "name"] if k is not None and d[k] < 600 else None)
        dp = parks.distance(g)
        kp = dp.idxmin() if len(dp) else None
        near_park.append(parks.loc[kp, "name"] if kp is not None else None)
        near_park_m.append(round(float(dp[kp])) if kp is not None else None)
    b["osm_neighborhood"] = osm_name
    b["nearest_park"] = near_park
    b["nearest_park_m"] = near_park_m

    def label(r):
        if r.city == "Los Angeles" and isinstance(r.la_hood, str):
            return r.la_hood, "LA Times Mapping L.A. boundary"
        if isinstance(r.osm_neighborhood, str):
            return f"{r.osm_neighborhood}", "OpenStreetMap neighborhood label"
        if isinstance(r.nearest_park, str) and r.nearest_park_m is not None and r.nearest_park_m < 700:
            short = re.sub(r"^(Doctor|Dr\.?)\s+Paul\s+", "", r.nearest_park).replace(" Memorial", "")
            return f"Around {short}", "nearest named park (city publishes no neighborhood GIS)"
        return r.city, "city"
    lab = b.apply(label, axis=1, result_type="expand")
    b["name"], b["name_source"] = lab[0], lab[1]
    return b


# ------------------------------------------------------------------ Census block groups
ACS_BG = {"B01003_001E": "population", "B25001_001E": "housing_units", "B25002_003E": "vacant_units",
          "B25004_008E": "vacant_other_units", "B25003_001E": "occupied_units", "B25003_002E": "owner_units",
          "B25077_001E": "median_home_value", "B19013_001E": "median_household_income", "B25035_001E": "median_year_built",
          "B17010_001E": "families", "B17010_002E": "families_below_poverty"}


@stage("acs_block_groups")
def acs_bg(R, bg):
    tables = sorted({v.split("_")[0] for v in ACS_BG})
    pref = "1500000US" + R["state"] + R["county"]
    for year in (2024, 2023):
        try:
            out = None
            for t in tables:
                p = cached_download(f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{t.lower()}.dat",
                                    f"acs{year}_{t}.dat", 200)
                df = pd.read_csv(p, sep="|", dtype=str)
                df = df[df.GEO_ID.str.startswith(pref)]
                keep = {"GEO_ID": "GEO_ID"}
                for v, nm in ACS_BG.items():
                    tbl, rest = v.split("_")
                    if tbl == t and f"{tbl}_E{rest[:-1]}" in df.columns:
                        keep[f"{tbl}_E{rest[:-1]}"] = nm
                df = df[list(keep)].rename(columns=keep)
                out = df if out is None else out.merge(df, on="GEO_ID", how="outer")
            out["GEOID"] = out.GEO_ID.str[-12:]
            for c in ACS_BG.values():
                if c in out:
                    out[c] = pd.to_numeric(out[c], errors="coerce")
                    out.loc[out[c] < 0, c] = np.nan
            note("acs_block_groups", vintage=f"{year - 4}-{year} ACS 5-year block groups")
            return bg.merge(out.drop(columns="GEO_ID"), on="GEOID", how="left")
        except Exception as e:  # noqa: BLE001
            log(f"  ACS BG {year}: {e}")
    raise RuntimeError("no ACS block-group data")


@stage("tree_equity_bg")
def tes_bg(R):
    p = cached_download("https://national-tes-data-share.s3.amazonaws.com/national_tes_share/ca.zip.zip", "tes_ca.zip", 120)
    d = CACHE / "tes_ca_focus"
    d.mkdir(exist_ok=True)
    with zipfile.ZipFile(p) as z:
        z.extractall(d)
    for inner in list(d.rglob("*.zip")):
        with zipfile.ZipFile(inner) as z:
            z.extractall(inner.parent / inner.stem)
    shp = [f for f in d.rglob("*.shp")][0]
    g = gpd.read_file(shp, bbox=R["bbox"])
    keep = [c for c in ("geoid", "treecanopy", "tc_goal", "tc_gap", "avg_temp", "tes", "priority") if c in g.columns]
    g = pd.DataFrame(g[keep]).rename(columns={"geoid": "GEOID"})
    for c in keep[1:]:
        g[c] = pd.to_numeric(g[c], errors="coerce")
        g.loc[g[c] < 0, c] = np.nan
    g["GEOID"] = g.GEOID.astype(str).str.zfill(12)
    log(f"  TES sample {g.head(3).to_dict('records')}")
    return g


def areal_weights(blocks, bg):
    """Share of each block's area in each block group."""
    bm, gm = blocks[["block_id", "geometry"]].to_crs(M), bg[["GEOID", "geometry"]].to_crs(M)
    ov = gpd.overlay(bm, gm, how="intersection", keep_geom_type=True)
    ov["a"] = ov.area
    ov["bg_area"] = ov.GEOID.map(gm.set_index("GEOID").area)
    ov["share_of_bg"] = ov.a / ov.bg_area
    ov["share_of_block"] = ov.a / ov.groupby("block_id").a.transform("sum")
    return ov[["block_id", "GEOID", "share_of_bg", "share_of_block"]]


# ------------------------------------------------------------------ street trees
@stage("street_trees")
def street_trees(R):
    frames = []
    base = "https://raw.githubusercontent.com/stiles/la-trees/main/data/municipalities/all/"
    for city in R["tree_sources"]:
        try:
            p = cached_download(base + f"{city}.geojson", f"trees_{city}.geojson", 60)
            g = gpd.read_file(p, bbox=R["bbox"])
            g["source_city"] = city
            frames.append(g)
            log(f"  {city}: {len(g)} records; columns {list(g.columns)[:12]}")
        except Exception as e:  # noqa: BLE001
            log(f"  {city}: {e}")
    if R.get("la_city_wfs"):
        w, s, e, n = R["bbox"]
        url = "https://geola.daveytreekeeper.com/geoserver/Treekeeper/ows"
        feats, start = [], 0
        while True:
            try:
                r = get(url, params={"service": "WFS", "version": "2.0.0", "request": "GetFeature",
                                     "typeNames": "Treekeeper:streetsla_UFDSpeciesLabel", "outputFormat": "application/json",
                                     "srsName": "EPSG:4326", "bbox": f"{s},{w},{n},{e},urn:ogc:def:crs:EPSG::4326",
                                     "count": 50000, "startIndex": start}, timeout=300, tries=2)
                js = r.json()
            except Exception as ex:  # noqa: BLE001
                log(f"  LA Treekeeper WFS failed at {start}: {ex}")
                break
            fs = js.get("features", [])
            feats += fs
            log(f"  LA Treekeeper page {start}: {len(fs)}")
            if len(fs) < 50000:
                break
            start += 50000
        if feats:
            g = gpd.GeoDataFrame.from_features(feats, crs=4326)
            g["source_city"] = "los-angeles (StreetsLA Treekeeper, live)"
            frames.append(g)
            note("street_trees", la_city_live=len(g), la_city_columns=list(g.columns)[:25])
        else:
            try:
                p = cached_download(base + "los-angeles-city.geojson", "trees_la_city.geojson", 60)
                g = gpd.read_file(p, bbox=R["bbox"])
                g["source_city"] = "los-angeles (stiles snapshot)"
                frames.append(g)
            except Exception as e:  # noqa: BLE001
                log(f"  LA city snapshot: {e}")
    t = pd.concat(frames, ignore_index=True)
    t = gpd.GeoDataFrame(t, geometry="geometry", crs=4326)
    t = t[t.geometry.notna() & (t.geom_type == "Point")]
    txt = t.drop(columns="geometry").astype(str).agg(" ".join, axis=1).str.upper()
    t["vacant_site"] = txt.str.contains(r"VACANT|PLANTING SITE|EMPTY|NO TREE")
    t["stump"] = txt.str.contains(r"STUMP") & ~t.vacant_site
    t["palm"] = txt.str.contains(r"\bPALM\b|WASHINGTONIA|SYAGRUS|PHOENIX") & ~t.vacant_site
    note("street_trees", records=len(t), vacant_sites=int(t.vacant_site.sum()), stumps=int(t.stump.sum()),
         by_source={k: int(v) for k, v in t.source_city.value_counts().items()})
    return t[["source_city", "vacant_site", "stump", "palm", "geometry"]]


# ------------------------------------------------------------------ canopy height (Meta/WRI 1 m)
def _quadkey(x, y, z):
    q = ""
    for i in range(z, 0, -1):
        d, m = 0, 1 << (i - 1)
        if x & m:
            d += 1
        if y & m:
            d += 2
        q += str(d)
    return q


def _tile_xy(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


@stage("canopy_height")
def canopy(R, blocks, roads):
    import rasterio
    from rasterio.mask import mask as rmask
    base = "https://dataforgood-fb-data.s3.amazonaws.com/forests/v1/alsgedi_global_v6_float/"
    listing = get(base.split("forests")[0], params={"list-type": "2", "prefix": "forests/v1/alsgedi_global_v6_float/", "delimiter": "/"}).text
    log("  bucket listing: " + " ".join(re.findall(r"<(?:Key|Prefix)>([^<]+)</", listing))[:800])
    w, s, e, n = R["bbox"]
    paths = []
    for z in (9,):
        x0, y0 = _tile_xy(w, n, z)
        x1, y1 = _tile_xy(e, s, z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                paths.append(_quadkey(x, y, z))
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
    os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "4")
    keys = []
    for qk in paths:
        lst = get(base.split("forests")[0], params={"list-type": "2", "prefix": f"forests/v1/alsgedi_global_v6_float/chm/{qk[:7]}"}).text
        keys += [k for k in re.findall(r"<Key>([^<]+\.tif)</Key>", lst)
                 if Path(k).stem.startswith(qk[:len(Path(k).stem)]) or qk.startswith(Path(k).stem) or Path(k).stem.startswith(qk)]
    keys = sorted(set(keys))
    log(f"  canopy tiles: {keys}")
    tifs = ["/vsicurl/https://dataforgood-fb-data.s3.amazonaws.com/" + k for k in keys]
    res = {"canopy_pct": {}, "street_canopy_pct": {}}
    res_streets = roads[roads.highway.isin(["residential", "living_street", "unclassified", "tertiary", "secondary"])].to_crs(M)
    street_buf = unary_union(list(res_streets.geometry.buffer(9)))  # ~curb-to-curb + parkway on both sides
    for src_path in tifs:
        with rasterio.open(src_path) as src:
            bproj = blocks.to_crs(src.crs)
            sb = gpd.GeoSeries([street_buf], crs=M).to_crs(src.crs).iloc[0]
            for bid, g in zip(bproj.block_id, bproj.geometry):
                if bid in res["canopy_pct"]:
                    continue
                try:
                    arr, _ = rmask(src, [g], crop=True, filled=False)
                except ValueError:
                    continue
                a = arr[0]
                valid = ~a.mask
                if valid.sum() < 100:
                    continue
                res["canopy_pct"][bid] = round(float(((a >= 3) & valid).sum()) / float(valid.sum()) * 100, 1)
                gs = g.intersection(sb)
                if not gs.is_empty:
                    try:
                        arr2, _ = rmask(src, [gs], crop=True, filled=False)
                        a2 = arr2[0]
                        v2 = ~a2.mask
                        if v2.sum() > 50:
                            res["street_canopy_pct"][bid] = round(float(((a2 >= 3) & v2).sum()) / float(v2.sum()) * 100, 1)
                    except ValueError:
                        pass
    return pd.DataFrame({"block_id": list(res["canopy_pct"]),
                         "canopy_pct_1m": list(res["canopy_pct"].values())}).merge(
        pd.DataFrame({"block_id": list(res["street_canopy_pct"]), "street_canopy_pct": list(res["street_canopy_pct"].values())}),
        on="block_id", how="left")


# ------------------------------------------------------------------ assessor parcels
def socrata_find(domain, query, must=()):
    cat = get("https://api.us.socrata.com/api/catalog/v1", params={"domains": domain, "q": query, "limit": 40}).json()
    res = [r["resource"] for r in cat["results"] if all(m.lower() in r["resource"]["name"].lower() for m in must)]
    res.sort(key=lambda r: r.get("data_updated_at") or r.get("updatedAt") or "", reverse=True)
    log("  socrata candidates: " + "; ".join(f"{r['id']} {r['name']} ({r.get('data_updated_at', '')[:10]})" for r in res[:6]))
    return res


@stage("assessor_parcels")
def parcels(R):
    w, s, e, n = R["bbox"]
    cands = socrata_find("data.lacounty.gov", "Assessor Parcels Data", must=("parcel",))
    for c in cands[:6]:
        rid = c["id"]
        try:
            sample = get(f"https://data.lacounty.gov/resource/{rid}.json", params={"$limit": 1}).json()
        except Exception:  # noqa: BLE001
            continue
        if not sample:
            continue
        cols = list(sample[0].keys())
        latc = next((k for k in cols if k.lower() in ("center_lat", "centerlat", "lat", "latitude")), None)
        lonc = next((k for k in cols if k.lower() in ("center_lon", "centerlon", "lon", "longitude")), None)
        log(f"  {rid} columns: {cols}")
        if not latc:
            continue
        rows, off = [], 0
        while True:
            r = get(f"https://data.lacounty.gov/resource/{rid}.json",
                    params={"$where": f"{latc} between {s} and {n} and {lonc} between {w} and {e}", "$limit": 50000, "$offset": off,
                            "$order": ":id"}, timeout=300)
            page = r.json()
            rows += page
            log(f"  parcels page {off}: {len(page)}")
            if len(page) < 50000:
                break
            off += 50000
        df = pd.DataFrame(rows)
        note("assessor_parcels", dataset=c["name"], dataset_id=rid, rows=len(df))
        df["lat"] = pd.to_numeric(df[latc], errors="coerce")
        df["lon"] = pd.to_numeric(df[lonc], errors="coerce")
        return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326)
    return parcels_arcgis(R)


def arcgis_query(url, bbox, fields="*", page=2000, max_rows=400000):
    w, s, e, n = bbox
    rows, off = [], 0
    while True:
        r = get(url.rstrip("/") + "/query", params={"where": "1=1", "geometry": f"{w},{s},{e},{n}", "geometryType": "esriGeometryEnvelope",
                                                     "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": fields,
                                                     "returnGeometry": "true", "returnCentroid": "true", "outSR": 4326, "f": "geojson",
                                                     "resultOffset": off, "resultRecordCount": page}, timeout=300)
        fs = r.json().get("features", [])
        rows += fs
        if len(fs) < page or len(rows) >= max_rows:
            break
        off += page
        if off % 20000 == 0:
            log(f"    {url[-60:]} {off}")
    return gpd.GeoDataFrame.from_features(rows, crs=4326) if rows else None


def parcels_arcgis(R):
    """LA County moved open data to ArcGIS; discover a queryable parcel layer with assessor attributes."""
    found = get("https://www.arcgis.com/sharing/rest/search",
                params={"q": "(parcel OR assessor) AND (\"Los Angeles County\" OR LACounty) type:\"Feature Service\"", "num": 50, "f": "json",
                        "sortField": "modified", "sortOrder": "desc"}).json().get("results", [])
    urls = [f"{x['url']}/0" for x in found if x.get("url")]
    urls = ["https://public.gis.lacounty.gov/public/rest/services/LACounty_Dynamic/Parcel/MapServer/0",
            "https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0"] + urls
    log("  arcgis parcel candidates: " + "; ".join(urls[:12]))
    w, s, e, n = R["bbox"]
    for u in urls[:15]:
        try:
            meta = get(u, params={"f": "json"}, timeout=60, tries=1).json()
            flds = [f["name"] for f in meta.get("fields", [])]
            if not any(re.search(r"use", f, re.I) for f in flds):
                continue
            log(f"  trying {u} fields {flds[:40]}")
            g = arcgis_query(u, (w, s, e, n))
            if g is not None and len(g) > 1000:
                g["geometry"] = g.to_crs(M).geometry.representative_point().to_crs(4326)
                note("assessor_parcels", dataset=u, rows=len(g), fields=flds[:50])
                return g
        except Exception as ex:  # noqa: BLE001
            log(f"  {u}: {ex}")
    raise RuntimeError("no parcel source with use codes found")


# ------------------------------------------------------------------ LAPD crime
@stage("lapd_crime")
def crime(R):
    w, s, e, n = R["bbox"]
    cands = socrata_find("data.lacity.org", "crime data", must=())
    cands = [c for c in cands if re.search(r"crime|nibrs", c["name"], re.I)]
    since = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
    for c in cands[:6]:
        rid = c["id"]
        try:
            sample = get(f"https://data.lacity.org/resource/{rid}.json", params={"$limit": 1, "$order": ":updated_at DESC"}).json()
        except Exception:  # noqa: BLE001
            continue
        if not sample:
            continue
        cols = list(sample[0].keys())
        latc = next((k for k in cols if k.lower() in ("lat", "latitude")), None)
        lonc = next((k for k in cols if k.lower() in ("lon", "longitude")), None)
        datec = next((k for k in cols if re.search(r"date_occ|dateocc|occ_date|date_occurred|occurred", k, re.I)), None)
        log(f"  {rid} {c['name']} cols {cols[:30]}")
        if not (latc and datec):
            continue
        r = get(f"https://data.lacity.org/resource/{rid}.json",
                params={"$where": f"{datec} > '{since}' and {latc} between {s} and {n} and {lonc} between {w} and {e}",
                        "$limit": 200000}, timeout=300)
        df = pd.DataFrame(r.json())
        log(f"  crime rows last 12 months: {len(df)}")
        if len(df) < 50:
            continue
        df["lat"] = pd.to_numeric(df[latc], errors="coerce")
        df["lon"] = pd.to_numeric(df[lonc], errors="coerce")
        df = df[(df.lat != 0) & df.lat.notna()]
        txt = df.astype(str).agg(" ".join, axis=1).str.upper()
        df["violent"] = txt.str.contains(r"ASSAULT|ROBBERY|HOMICIDE|RAPE|SHOTS|BATTERY|KIDNAP")
        note("lapd_crime", dataset=c["name"], dataset_id=rid, rows=len(df))
        return gpd.GeoDataFrame(df[["violent"]], geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326)
    raise RuntimeError("no usable LAPD crime dataset")


# ------------------------------------------------------------------ assemble
def run(region):
    R = REGIONS[region]
    out = OUT_ROOT / f"focus_{region}"
    out.mkdir(parents=True, exist_ok=True)
    osm = osm_layers(R)
    pl, bg, lat = boundaries(R)
    blocks = build_blocks(R, osm, pl, bg, lat)
    blocks = name_blocks(blocks, osm, pl, lat)
    bgd = acs_bg(R, bg)
    tes = tes_bg(R)
    if tes is not None and bgd is not None:
        bgd = bgd.merge(tes, on="GEOID", how="left")
    W = areal_weights(blocks, bg)
    # extensive counts: split by area share of the block group; rates/medians: area-weighted mean
    ext = ["population", "housing_units", "vacant_units", "vacant_other_units", "occupied_units", "owner_units",
           "families", "families_below_poverty"]
    inten = ["median_home_value", "median_household_income", "median_year_built", "treecanopy", "tc_goal", "tc_gap", "avg_temp"]
    jj = W.merge(pd.DataFrame(bgd.drop(columns="geometry")), on="GEOID", how="left")
    agg = {}
    for c in ext:
        if c in jj:
            agg[c] = (jj[c] * jj.share_of_bg).groupby(jj.block_id).sum(min_count=1)
    for c in inten:
        if c in jj:
            ok = jj[c].notna()
            agg[c] = (jj[c].where(ok, 0) * jj.share_of_block).groupby(jj.block_id).sum() / (jj.share_of_block.where(ok, 0)).groupby(jj.block_id).sum()
    blocks = blocks.merge(pd.DataFrame(agg).reset_index(), on="block_id", how="left")
    if "avg_temp" in blocks:
        blocks["temp_diff_f"] = blocks.avg_temp - blocks.avg_temp.mean()

    bm = blocks[["block_id", "geometry"]].to_crs(M)
    # street trees
    trees = street_trees(R)
    if trees is not None:
        tj = gpd.sjoin(trees.to_crs(M), bm, predicate="within")
        g = tj.groupby("block_id")
        blocks = blocks.merge(pd.DataFrame({
            "street_trees": g.apply(lambda d: int((~d.vacant_site & ~d.stump).sum())),
            "vacant_planting_sites": g.vacant_site.sum().astype(int),
            "stumps": g.stump.sum().astype(int),
            "palms": g.palm.sum().astype(int)}).reset_index(), on="block_id", how="left")
        blocks["tree_inventory"] = blocks.city.isin(["Culver City", "Los Angeles", "Beverly Hills", "Santa Monica", "Inglewood", "West Hollywood"])
        vs = trees[trees.vacant_site | trees.stump]
        vs.to_file(out / "vacant_planting_sites.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    # residential street length per block
    rs = osm["roads"]
    rs = rs[rs.highway.isin(["residential", "living_street", "unclassified"])].to_crs(M)
    sj = gpd.sjoin(rs[["geometry"]], bm, predicate="intersects")
    bgeom = bm.set_index("block_id").geometry
    sj["len"] = [g.intersection(bgeom[b]).length for g, b in zip(sj.geometry, sj.block_id)]
    blocks = blocks.merge((sj.groupby("block_id")["len"].sum() / 1000).rename("res_street_km").reset_index(), on="block_id", how="left")
    # canopy
    cn = canopy(R, blocks, osm["roads"])
    if cn is not None:
        blocks = blocks.merge(cn, on="block_id", how="left")
    # parcels
    pc = parcels(R)
    if pc is not None:
        cols = {c.lower(): c for c in pc.columns}
        use = next((cols[k] for k in ("usecode", "use_code", "usetype", "use_type", "usecodedescchar1") if k in cols), None)
        units = next((cols[k] for k in ("units", "unitcount", "number_of_units") if k in cols), None)
        landv = next((cols[k] for k in ("landvalue", "land_value", "roll_landvalue") if k in cols), None)
        sqft = next((cols[k] for k in ("sqftlot", "lot_size", "land_sqft", "landsqft") if k in cols), None)
        desc = [cols[k] for k in cols if "desc" in k or "usetype" in k]
        txt = pc[[c for c in [use] + desc if c]].astype(str).agg(" ".join, axis=1).str.upper()
        pc["vacant_land"] = txt.str.contains(r"VACANT") | (pc[use].astype(str).str.upper().str.endswith("V") if use else False)
        pc["residential"] = txt.str.contains(r"RESIDENTIAL|SINGLE|MULTI|CONDO|DUPLEX") | (pc[use].astype(str).str.startswith("0") if use else False)
        pc["units_n"] = pd.to_numeric(pc[units], errors="coerce") if units else np.nan
        pc["land_value"] = pd.to_numeric(pc[landv], errors="coerce") if landv else np.nan
        pc["lot_sqft"] = pd.to_numeric(pc[sqft], errors="coerce") if sqft else np.nan
        note("assessor_parcels", use_col=use, units_col=units, land_col=landv, sqft_col=sqft,
             vacant=int(pc.vacant_land.sum()), residential=int(pc.residential.sum()))
        pj = gpd.sjoin(pc.to_crs(M), bm, predicate="within")
        g = pj.groupby("block_id")
        blocks = blocks.merge(pd.DataFrame({
            "parcels": g.size(), "residential_parcels": g.residential.sum(), "vacant_parcels": g.vacant_land.sum(),
            "vacant_parcel_sqft": pj[pj.vacant_land].groupby("block_id").lot_sqft.sum(),
            "assessor_units": pj[pj.residential].groupby("block_id").units_n.sum(min_count=1),
            "land_value_per_sqft_median": (pj.land_value / pj.lot_sqft.replace(0, np.nan)).groupby(pj.block_id).median(),
        }).reset_index(), on="block_id", how="left")
        vp = pc[pc.vacant_land]
        vp[["geometry"]].to_file(out / "vacant_parcels.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    # crime
    cr = crime(R)
    if cr is not None:
        cj = gpd.sjoin(cr.to_crs(M), bm, predicate="within")
        blocks = blocks.merge(pd.DataFrame({"crimes_12mo": cj.groupby("block_id").size(),
                                            "violent_12mo": cj.groupby("block_id").violent.sum()}).reset_index(), on="block_id", how="left")
        blocks["crime_coverage"] = blocks.city == "Los Angeles"
    # schools + scores
    sch = bd.ca_schools()
    if sch is not None:
        sg = gpd.GeoDataFrame(sch, geometry=gpd.points_from_xy(sch.lon, sch.lat), crs=4326)
        sg = sg[sg.intersects(box(*R["bbox"]).buffer(0.02))]
        sg.drop(columns="geometry").to_csv(out / "schools.csv", index=False)
        sm = sg.to_crs(M)
        scored = sm[sm.get("ela_pct_met", pd.Series(index=sm.index)).notna()]
        rp = bm.geometry.representative_point()
        near = []
        for pt in rp:
            d = scored.distance(pt).sort_values()[:3]
            near.append(json.dumps([{"name": scored.at[i, "School"], "ela": round(float(scored.at[i, "ela_pct_met"]), 1) if not pd.isna(scored.at[i, "ela_pct_met"]) else None,
                                     "math": round(float(scored.at[i, "math_pct_met"]), 1) if not pd.isna(scored.at[i, "math_pct_met"]) else None,
                                     "dist_m": int(dd)} for i, dd in d.items()]))
        blocks["schools_near3"] = near
    # park access
    pk = osm["parks"]
    pk = pk[pk.geom_type.isin(["Polygon", "MultiPolygon"]) & pk.get("leisure", pd.Series(index=pk.index)).isin(["park", "recreation_ground", "garden", "nature_reserve", "playground"])].to_crs(M)
    pu = unary_union(list(pk.geometry))
    rp = bm.geometry.representative_point()
    blocks["park_acres_half_mile"] = [round(pt.buffer(805).intersection(pu).area / 4046.86, 2) for pt in rp]
    fw = osm["roads"]
    fw = fw[fw.highway == "motorway"].to_crs(M)
    fu = unary_union(list(fw.geometry))
    blocks["freeway_m"] = [round(g.distance(fu)) for g in bm.geometry]
    # Zillow neighborhood values
    zn = bd.zillow_neighborhoods()
    if zn is not None:
        zn = zn[zn.CountyName == R["zillow_county"]]
        zn.to_csv(out / "zillow_neighborhoods.csv", index=False)
    # write
    blocks.to_file(out / "blocks.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    for k in ("roads", "water", "rail", "parks", "schools", "places", "stations"):
        d = osm.get(k)
        if d is None or not len(d):
            continue
        keep = [c for c in ("name", "highway", "waterway", "natural", "railway", "leisure", "amenity", "place", "ref") if c in d.columns]
        d = d[keep + ["geometry"]]
        d.to_file(out / f"osm_{k}.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    lat.to_file(out / "la_times_neighborhoods.geojson", driver="GeoJSON")
    pl.to_file(out / "places.geojson", driver="GeoJSON")
    STATUS["blocks"] = len(blocks)
    (out / "status.json").write_text(json.dumps(STATUS, indent=2, default=str))
    log(json.dumps({k: v.get("ok") for k, v in STATUS["sources"].items()}))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "la_westside")
