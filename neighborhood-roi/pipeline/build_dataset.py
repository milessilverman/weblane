"""Fetch public data for the configured counties and write tract-level outputs.

Runs in GitHub Actions (open internet). Every source is fetched independently:
a failure is logged in pipeline_status.json and the rest still build.

    python neighborhood-roi/pipeline/build_dataset.py
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
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import Point, Polygon, shape

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("PIPELINE_CACHE", ROOT / ".cache"))
OUT = ROOT / "data" / "derived"
CACHE.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "neighborhood-roi-data-pipeline/0.1 (+https://github.com/milessilverman/weblane)"}

# state fips, county fips, label, BLS MSA code
COUNTIES = [
    ("06", "037", "Los Angeles County, CA", "31080"),
    ("42", "101", "Philadelphia County, PA", "37980"),
    ("17", "031", "Cook County, IL", "16980"),
    ("48", "113", "Dallas County, TX", "19100"),
    ("26", "163", "Wayne County, MI", "19820"),
    ("13", "121", "Fulton County, GA", "12060"),
    ("53", "033", "King County, WA", "42660"),
    ("36", "047", "Kings County (Brooklyn), NY", "35620"),
    ("48", "201", "Harris County, TX", "26420"),
    ("18", "097", "Marion County, IN", "26900"),
]
STATE_ABBR = {"06": "CA", "42": "PA", "17": "IL", "48": "TX", "26": "MI", "13": "GA",
              "53": "WA", "36": "NY", "18": "IN"}
ONLY = os.environ.get("ONLY_COUNTIES")  # e.g. "06037" for quick runs
if ONLY:
    COUNTIES = [c for c in COUNTIES if c[0] + c[1] in ONLY.split(",")]

ROADS = None
STATUS = {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": {}}


def log(*a):
    print(f"[{datetime.now().strftime('%H:%M:%S')}]", *a, flush=True)


def get(url, *, params=None, timeout=300, tries=3, stream_to=None, method="GET", json_body=None):
    for i in range(tries):
        try:
            r = requests.request(method, url, params=params, headers=UA, timeout=timeout,
                                 json=json_body, stream=bool(stream_to))
            if r.status_code == 200:
                if stream_to:
                    with open(stream_to, "wb") as f:
                        for chunk in r.iter_content(1 << 20):
                            f.write(chunk)
                    return stream_to
                return r
            log(f"  HTTP {r.status_code} {url} :: {r.text[:200]!r}")
            if r.status_code in (400, 403, 404):
                break
        except Exception as e:  # noqa: BLE001
            log(f"  error {url}: {e}")
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"failed: {url}")


def cached_download(url, name, max_age_days=25):
    path = CACHE / name
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_days * 86400 and path.stat().st_size > 0:
        log(f"  cache hit {name}")
        return path
    log(f"  download {url}")
    get(url, stream_to=path, timeout=900)
    log(f"  -> {path.stat().st_size/1e6:.1f} MB")
    return path


def source(name):
    def deco(fn):
        def run(*a, **k):
            log(f"== {name}")
            t = time.time()
            try:
                res = fn(*a, **k)
                info = {"ok": True, "seconds": round(time.time() - t, 1)}
                if isinstance(res, pd.DataFrame):
                    info["rows"] = len(res)
                    info["columns"] = list(map(str, res.columns))[:80]
                STATUS["sources"][name] = {**STATUS["sources"].get(name, {}), **info}
                return res
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                STATUS["sources"][name] = {**STATUS["sources"].get(name, {}), "ok": False, "error": str(e)[:500]}
                return None
        return run
    return deco


def note(name, **kw):
    STATUS["sources"].setdefault(name, {}).update(kw)


# ---------------------------------------------------------------- geometry
@source("census_tract_boundaries")
def tracts():
    frames = []
    for st in sorted({c[0] for c in COUNTIES}):
        p = cached_download(f"https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_{st}_tract_500k.zip",
                            f"cb_2023_{st}_tract_500k.zip", 300)
        g = gpd.read_file(f"zip://{p}")
        keep = [c[1] for c in COUNTIES if c[0] == st]
        frames.append(g[g.COUNTYFP.isin(keep)])
    g = pd.concat(frames, ignore_index=True)
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=frames[0].crs).to_crs(4326)
    g = g[g.ALAND > 0][["GEOID", "STATEFP", "COUNTYFP", "NAMELSAD", "ALAND", "geometry"]]
    return g


# ---------------------------------------------------------------- ACS
ACS_VARS = {
    "B01003_001E": "population",
    "B25001_001E": "housing_units",
    "B25002_003E": "vacant_units",
    "B25003_001E": "occupied_units",
    "B25003_002E": "owner_units",
    "B25077_001E": "median_home_value",
    "B25064_001E": "median_gross_rent",
    "B19013_001E": "median_household_income",
    "B25035_001E": "median_year_built",
    "B25024_002E": "units_single_family_detached",
    "B08301_001E": "commuters",
    "B08301_010E": "commuters_transit",
    "B08301_019E": "commuters_walk",
    "B17001_002E": "people_below_poverty",
    "B15003_022E": "adults_bachelors",
    "B15003_001E": "adults_25plus",
}


@source("census_acs_5yr")
def acs():
    key = os.environ.get("CENSUS_API_KEY")
    for year in (2024, 2023):
        try:
            rows = []
            for st, co, *_ in COUNTIES:
                params = {"get": "NAME," + ",".join(ACS_VARS), "for": "tract:*", "in": [f"state:{st}", f"county:{co}"]}
                if key:
                    params["key"] = key
                r = get(f"https://api.census.gov/data/{year}/acs/acs5", params=params, timeout=120)
                data = r.json()
                rows += [dict(zip(data[0], d)) for d in data[1:]]
            df = pd.DataFrame(rows)
            df["GEOID"] = df.state + df.county + df.tract
            df = df.rename(columns=ACS_VARS)
            for c in ACS_VARS.values():
                df[c] = pd.to_numeric(df[c], errors="coerce")
                df.loc[df[c] < 0, c] = np.nan
            note("census_acs_5yr", vintage=f"{year - 4}-{year} ACS 5-year")
            return df[["GEOID"] + list(ACS_VARS.values())]
        except Exception as e:  # noqa: BLE001
            log(f"  ACS {year} failed: {e}")
    raise RuntimeError("no ACS vintage worked")


# ---------------------------------------------------------------- Tree Equity Score
def _first(cols, *cands):
    low = {c.lower(): c for c in cols}
    for c in cands:
        if c in low:
            return low[c]
    return None


@source("tree_equity_score")
def tree_equity():
    frames = []
    for st in sorted({c[0] for c in COUNTIES}):
        ab = STATE_ABBR[st].lower()
        p = None
        for url in (f"https://national-tes-data-share.s3.amazonaws.com/national_tes_share/{ab}.zip.zip",
                    f"https://national-tes-data-share.s3.amazonaws.com/national_tes_share/{ab}.zip"):
            try:
                p = cached_download(url, f"tes_{ab}.zip", 120)
                break
            except Exception:  # noqa: BLE001
                continue
        if p is None:
            raise RuntimeError(f"no TES file for {ab}")
        d = CACHE / f"tes_{ab}"
        d.mkdir(exist_ok=True)
        with zipfile.ZipFile(p) as z:
            z.extractall(d)
        for inner in list(d.rglob("*.zip")):
            with zipfile.ZipFile(inner) as z:
                z.extractall(inner.parent / inner.stem)
        vec = [f for f in d.rglob("*") if f.suffix.lower() in (".shp", ".gpkg", ".geojson")]
        log(f"  TES files for {ab}: {[str(v.relative_to(d)) for v in vec]}")
        g = gpd.read_file(vec[0], ignore_geometry=True)
        log(f"  TES columns: {list(g.columns)}")
        note("tree_equity_score", columns_raw=list(map(str, g.columns)))
        frames.append(pd.DataFrame(g))
    raw = pd.concat(frames, ignore_index=True)
    cols = raw.columns
    gid = _first(cols, "geoid", "geoid20", "bgid", "id")
    out = pd.DataFrame({"bg": raw[gid].astype(str).str.zfill(12)})
    mapping = {
        "tes": ("tes", "tree_equity_score", "treeequityscore"),
        "canopy_pct": ("canopy", "treecanopy", "tree_canopy", "tc_canopy", "canopy_pct"),
        "canopy_goal_pct": ("tc_goal", "goal", "canopy_goal"),
        "canopy_gap_pct": ("tc_gap", "gap", "canopy_gap"),
        "temp_diff_f": ("temp_diff", "tempdiff", "heat_diff", "temp_diff_f"),
        "tes_pop": ("total_pop", "pop", "population", "totalpop"),
    }
    for k, cands in mapping.items():
        c = _first(cols, *cands)
        if c is not None:
            out[k] = pd.to_numeric(raw[c], errors="coerce")
    out["GEOID"] = out.bg.str[:11]
    prefixes = tuple(c[0] + c[1] for c in COUNTIES)
    out = out[out.GEOID.str.startswith(prefixes)]
    # fractions -> percent if needed
    for k in ("canopy_pct", "canopy_goal_pct", "canopy_gap_pct"):
        if k in out and out[k].max() <= 1.5:
            out[k] = out[k] * 100
    w = out["tes_pop"].fillna(1).clip(lower=1) if "tes_pop" in out else 1
    agg = {}
    for k in ("tes", "canopy_pct", "canopy_goal_pct", "canopy_gap_pct", "temp_diff_f"):
        if k in out:
            agg[k] = (out[k] * w).groupby(out.GEOID).sum() / (w * out[k].notna()).groupby(out.GEOID).sum()
    res = pd.DataFrame(agg).reset_index()
    res["tes_block_groups"] = out.groupby("GEOID").size().reindex(res.GEOID).values
    return res


# ---------------------------------------------------------------- FHFA tract HPI
@source("fhfa_tract_hpi")
def fhfa():
    p = None
    for url in ("https://www.fhfa.gov/hpi/download/annually/hpi_at_bdl_tract.csv",
                "https://www.fhfa.gov/DataTools/Downloads/Documents/HPI/HPI_AT_BDL_tract.csv"):
        try:
            p = cached_download(url, "hpi_at_bdl_tract.csv", 60)
            break
        except Exception:  # noqa: BLE001
            continue
    if p is None:
        raise RuntimeError("FHFA tract file unavailable")
    df = pd.read_csv(p, dtype={"tract": str})
    log(f"  FHFA columns {list(df.columns)}")
    df["tract"] = df["tract"].str.zfill(11)
    prefixes = tuple(c[0] + c[1] for c in COUNTIES)
    df = df[df.tract.str.startswith(prefixes)]
    df["hpi"] = pd.to_numeric(df["hpi"], errors="coerce")
    piv = df.pivot_table(index="tract", columns="year", values="hpi")
    last = int(piv.columns.max())
    res = pd.DataFrame({"GEOID": piv.index})
    for yrs in (1, 5, 10, 20):
        if last - yrs in piv.columns:
            res[f"hpi_growth_{yrs}y_pct"] = ((piv[last] / piv[last - yrs] - 1) * 100).values
    series_years = [y for y in piv.columns if y >= 2000]
    res["hpi_series"] = [json.dumps({int(y): (None if pd.isna(v) else round(float(v), 1)) for y, v in row.items()})
                         for _, row in piv[series_years].iterrows()]
    note("fhfa_tract_hpi", latest_year=last)
    return res


# ---------------------------------------------------------------- FEMA NRI
@source("fema_national_risk_index")
def nri():
    p = cached_download("https://hazards.fema.gov/nri/Content/StaticDocuments/DataDownload//NRI_Table_CensusTracts/NRI_Table_CensusTracts.zip",
                        "NRI_Table_CensusTracts.zip", 120)
    with zipfile.ZipFile(p) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".csv") and "dictionary" not in n.lower()][0]
        df = pd.read_csv(z.open(name), dtype={"TRACTFIPS": str}, low_memory=False)
    df["GEOID"] = df.TRACTFIPS.str.zfill(11)
    prefixes = tuple(c[0] + c[1] for c in COUNTIES)
    df = df[df.GEOID.str.startswith(prefixes)]
    keep = {"RISK_SCORE": "nri_risk_score", "RISK_RATNG": "nri_risk_rating", "EAL_VALB": "nri_eal_building_usd",
            "SOVI_SCORE": "nri_social_vulnerability", "RESL_SCORE": "nri_resilience",
            "HWAV_RISKS": "nri_heatwave_risk", "RFLD_RISKS": "nri_river_flood_risk",
            "CFLD_RISKS": "nri_coastal_flood_risk", "WFIR_RISKS": "nri_wildfire_risk",
            "ERQK_RISKS": "nri_earthquake_risk"}
    have = {k: v for k, v in keep.items() if k in df.columns}
    return df[["GEOID"] + list(have)].rename(columns=have)


# ---------------------------------------------------------------- CDC PLACES
@source("cdc_places")
def places():
    cat = get("https://api.us.socrata.com/api/catalog/v1",
              params={"domains": "data.cdc.gov", "q": "PLACES Census Tract Data GIS Friendly Format", "limit": 50}).json()
    cands = [r["resource"] for r in cat["results"]
             if "census tract" in r["resource"]["name"].lower() and "gis friendly" in r["resource"]["name"].lower()]
    cands.sort(key=lambda r: r["name"], reverse=True)
    log("  PLACES candidates: " + "; ".join(f"{c['id']} {c['name']}" for c in cands[:5]))
    if not cands:
        raise RuntimeError("no PLACES dataset found")
    ds = cands[0]
    rows = []
    for st, co, *_ in COUNTIES:
        r = get(f"https://data.cdc.gov/resource/{ds['id']}.json", params={"countyfips": st + co, "$limit": 5000})
        rows += r.json()
    df = pd.DataFrame(rows)
    note("cdc_places", dataset=ds["name"], dataset_id=ds["id"])
    measures = {"mhlth_crudeprev": "poor_mental_health_pct", "lpa_crudeprev": "no_leisure_activity_pct",
                "casthma_crudeprev": "asthma_pct", "obesity_crudeprev": "obesity_pct",
                "depression_crudeprev": "depression_pct", "ghlth_crudeprev": "poor_general_health_pct",
                "isolation_crudeprev": "social_isolation_pct", "lacktrpt_crudeprev": "lack_transport_pct"}
    df["GEOID"] = df["tractfips"].astype(str).str.zfill(11)
    have = {k: v for k, v in measures.items() if k in df.columns}
    out = df[["GEOID"] + list(have)].rename(columns=have)
    for c in have.values():
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


# ---------------------------------------------------------------- Zillow
ZILLOW = "https://files.zillowstatic.com/research/public_csvs/zhvi/"


def _zillow_summary(df, id_cols):
    date_cols = [c for c in df.columns if re.match(r"\d{4}-\d{2}-\d{2}", str(c))]
    last = date_cols[-1]
    out = df[id_cols].copy()
    out["zhvi"] = df[last]
    out["zhvi_date"] = last
    for yrs in (1, 5, 10):
        idx = len(date_cols) - 1 - 12 * yrs
        if idx >= 0:
            out[f"zhvi_growth_{yrs}y_pct"] = (df[last] / df[date_cols[idx]] - 1) * 100
    yearly = [c for c in date_cols if c[5:7] == last[5:7]][-15:]
    out["zhvi_series"] = [json.dumps({c[:4]: (None if pd.isna(v) else int(v)) for c, v in row.items()})
                          for _, row in df[yearly].iterrows()]
    return out


@source("zillow_zhvi_neighborhood")
def zillow_neighborhoods():
    p = cached_download(ZILLOW + "Neighborhood_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv", "zillow_nbhd.csv", 25)
    df = pd.read_csv(p)
    names = {c[2].split(",")[0].replace(" (Brooklyn)", "") for c in COUNTIES}
    df = df[df.CountyName.isin(names) & df.State.isin(STATE_ABBR.values())]
    return _zillow_summary(df, ["RegionID", "RegionName", "City", "CountyName", "State", "Metro"])


@source("zillow_zhvi_zip")
def zillow_zips():
    p = cached_download(ZILLOW + "Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv", "zillow_zip.csv", 25)
    df = pd.read_csv(p, dtype={"RegionName": str})
    names = {c[2].split(",")[0].replace(" (Brooklyn)", "") for c in COUNTIES}
    df = df[df.CountyName.isin(names) & df.State.isin(STATE_ABBR.values())]
    df["RegionName"] = df.RegionName.str.zfill(5)
    return _zillow_summary(df, ["RegionName", "City", "CountyName", "State"])


@source("census_zcta_boundaries")
def zctas():
    p = cached_download("https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_zcta520_500k.zip", "zcta.zip", 300)
    return gpd.read_file(f"zip://{p}")[["ZCTA5CE20", "geometry"]].to_crs(4326)


# ---------------------------------------------------------------- OpenStreetMap
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]


def overpass(q, name):
    path = CACHE / f"osm_{name}.json"
    if path.exists() and time.time() - path.stat().st_mtime < 25 * 86400:
        return json.loads(path.read_text())
    last = None
    for ep in OVERPASS:
        try:
            r = requests.post(ep, data={"data": q}, headers=UA, timeout=420)
            if r.status_code == 200:
                path.write_text(r.text)
                return r.json()
            last = f"{ep} HTTP {r.status_code} {r.text[:200]}"
            log("  " + last)
        except Exception as e:  # noqa: BLE001
            last = f"{ep} {e}"
            log("  " + last)
        time.sleep(20)
    raise RuntimeError(last)


def _way_poly(el):
    pts = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
    if len(pts) >= 4 and pts[0] == pts[-1]:
        try:
            return Polygon(pts).buffer(0)
        except Exception:  # noqa: BLE001
            return None
    return None


def _rel_poly(el):
    polys = []
    for m in el.get("members", []):
        if m.get("role") == "outer" and m.get("geometry"):
            pts = [(p["lon"], p["lat"]) for p in m["geometry"]]
            if len(pts) >= 4 and pts[0] == pts[-1]:
                polys.append(Polygon(pts).buffer(0))
    if not polys:
        return None
    from shapely.ops import unary_union
    return unary_union(polys)


@source("openstreetmap")
def osm(tract_gdf):
    parks, points, roads = [], [], []
    for st, co, label, _ in COUNTIES:
        sub = tract_gdf[(tract_gdf.STATEFP == st) & (tract_gdf.COUNTYFP == co)]
        w, s, e, n = sub.total_bounds
        bbox = f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}"
        q_parks = f"""[out:json][timeout:400];
        (way["leisure"~"^(park|garden|nature_reserve|playground|recreation_ground)$"]({bbox});
         relation["leisure"~"^(park|nature_reserve|recreation_ground)$"]({bbox}););
        out geom;"""
        q_pts = f"""[out:json][timeout:400];
        (nwr["place"~"^(neighbourhood|suburb|quarter)$"]({bbox});
         nwr["amenity"="school"]({bbox});
         nwr["railway"="station"]({bbox});
         nwr["public_transport"="station"]({bbox});
         nwr["amenity"="library"]({bbox});
         nwr["shop"~"^(supermarket|grocery)$"]({bbox}););
        out center tags;"""
        q_roads = f"""[out:json][timeout:400];
        (way["highway"~"^(motorway|trunk|primary)$"]({bbox});
         way["waterway"~"^(river|canal)$"]["name"]({bbox}););
        out geom tags;"""
        key = st + co
        try:
            rj = overpass(q_roads, f"roads_{key}")
            from shapely.geometry import LineString
            for el in rj.get("elements", []):
                pts = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
                if len(pts) >= 2:
                    t = el.get("tags", {})
                    roads.append({"kind": t.get("highway") or "water", "name": t.get("name") or t.get("ref"),
                                  "geometry": LineString(pts)})
        except Exception as e:  # noqa: BLE001
            note("openstreetmap", roads_error=str(e)[:300])
        time.sleep(10)
        pj = overpass(q_parks, f"parks_{key}")
        for el in pj.get("elements", []):
            geom = _way_poly(el) if el["type"] == "way" else _rel_poly(el)
            if geom is not None and not geom.is_empty:
                parks.append({"name": el.get("tags", {}).get("name"), "kind": el.get("tags", {}).get("leisure"),
                              "osm_id": f"{el['type']}/{el['id']}", "geometry": geom})
        time.sleep(10)
        qj = overpass(q_pts, f"points_{key}")
        for el in qj.get("elements", []):
            t = el.get("tags", {})
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is None:
                continue
            if "place" in t:
                kind = "neighborhood"
            elif t.get("amenity") == "school":
                kind = "school"
            elif t.get("amenity") == "library":
                kind = "library"
            elif "shop" in t:
                kind = "grocery"
            else:
                kind = "rail_station"
            points.append({"kind": kind, "name": t.get("name"), "osm_id": f"{el['type']}/{el['id']}",
                           "geometry": Point(lon, lat)})
        time.sleep(10)
    parks = gpd.GeoDataFrame(parks, geometry="geometry", crs=4326) if parks else None
    points = gpd.GeoDataFrame(points, geometry="geometry", crs=4326)
    if roads:
        global ROADS
        ROADS = gpd.GeoDataFrame(roads, geometry="geometry", crs=4326)
    note("openstreetmap", parks=0 if parks is None else len(parks),
         points={k: int(v) for k, v in points.kind.value_counts().items()})
    return parks, points


def osm_metrics(tr, parks, points):
    """Per-tract park access, schools, stations and neighborhood names."""
    t = tr.to_crs(3857).copy()
    rep = t.geometry.representative_point()
    res = pd.DataFrame({"GEOID": t.GEOID.values})
    if parks is not None:
        pk = parks.to_crs(3857)
        pk = pk[pk.geometry.area > 200]  # drop slivers
        pk["acres"] = pk.geometry.area / 4046.86
        sindex = pk.sindex
        within_half_mile, nearest_d, nearest_name, nearest_acres, park_share = [], [], [], [], []
        for geom, pt in zip(t.geometry, rep):
            buf = pt.buffer(805)  # 0.5 mile ~ 10-minute walk
            idx = list(sindex.intersection(buf.bounds))
            acres = sum(pk.geometry.iloc[i].intersection(buf).area for i in idx) / 4046.86 if idx else 0
            within_half_mile.append(round(acres, 2))
            near = list(sindex.nearest(pt, return_all=False)[1]) if len(pk) else []
            if near:
                j = near[0]
                nearest_d.append(round(pk.geometry.iloc[j].distance(pt)))
                nearest_name.append(pk.name.iloc[j])
                nearest_acres.append(round(pk.acres.iloc[j], 2))
            else:
                nearest_d.append(None); nearest_name.append(None); nearest_acres.append(None)
            idx2 = list(sindex.intersection(geom.bounds))
            inter = sum(pk.geometry.iloc[i].intersection(geom).area for i in idx2) if idx2 else 0
            park_share.append(round(100 * inter / geom.area, 2) if geom.area else 0)
        res["park_acres_within_half_mile"] = within_half_mile
        res["nearest_park_m"] = nearest_d
        res["nearest_park_name"] = nearest_name
        res["nearest_park_acres"] = nearest_acres
        res["park_pct_of_tract"] = park_share
    pts = points.to_crs(3857)
    for kind in ("school", "rail_station", "library", "grocery"):
        sub = pts[pts.kind == kind].reset_index(drop=True)
        if not len(sub):
            continue
        si = sub.sindex
        d, nm = [], []
        for pt in rep:
            j = list(si.nearest(pt, return_all=False)[1])[0]
            d.append(round(sub.geometry.iloc[j].distance(pt)))
            nm.append(sub.name.iloc[j])
        res[f"nearest_{kind}_m"] = d
        res[f"nearest_{kind}_name"] = nm
        res[f"{kind}s_in_tract"] = gpd.sjoin(sub, t[["GEOID", "geometry"]], predicate="within").groupby("GEOID").size().reindex(res.GEOID).fillna(0).astype(int).values
    rd = ROADS
    if rd is not None:
        fw = rd[rd.kind == "motorway"].to_crs(3857)
        if len(fw):
            fsi = fw.sindex
            res["nearest_freeway_m"] = [round(fw.geometry.iloc[list(fsi.nearest(pt, return_all=False)[1])[0]].distance(pt)) for pt in rep]
            res["freeway_through_tract"] = [bool(len(fsi.query(g, predicate="intersects"))) for g in t.geometry]
    nb = pts[pts.kind == "neighborhood"]
    j = gpd.sjoin(nb, t[["GEOID", "geometry"]], predicate="within")
    names = j.groupby("GEOID")["name"].apply(lambda s: sorted({x for x in s if isinstance(x, str)}))
    res["osm_neighborhoods"] = res.GEOID.map(names).apply(lambda v: v if isinstance(v, list) else [])
    return res


# ---------------------------------------------------------------- California schools (CDE + CAASPP)
@source("ca_school_scores")
def ca_schools():
    if not any(c[0] == "06" for c in COUNTIES):
        return None
    d = cached_download("https://www.cde.ca.gov/schooldirectory/report?rid=dl1&tp=txt", "ca_pubschls.txt", 60)
    sch = pd.read_csv(d, sep="\t", dtype=str, encoding="latin-1", on_bad_lines="skip")
    log(f"  CDE columns {list(sch.columns)[:30]}")
    sch = sch[(sch.StatusType == "Active")]
    sch["lat"] = pd.to_numeric(sch.Latitude, errors="coerce")
    sch["lon"] = pd.to_numeric(sch.Longitude, errors="coerce")
    scores = None
    for yr in (2025, 2024):
        for v in ("v1", "v2", "v3"):
            try:
                p = cached_download(f"https://caaspp-elpac.ets.org/caaspp/researchfiles/sb_ca{yr}_1_csv_{v}.zip",
                                    f"caaspp_{yr}.zip", 120)
                with zipfile.ZipFile(p) as z:
                    name = [n for n in z.namelist() if n.lower().endswith((".txt", ".csv")) and "entit" not in n.lower()][0]
                    raw = z.read(name).decode("latin-1")
                sep = "^" if raw.count("^") > raw.count(",") else ","
                sc = pd.read_csv(io.StringIO(raw), sep=sep, dtype=str)
                log(f"  CAASPP {yr} columns {list(sc.columns)}")
                scores = (yr, sc)
                break
            except Exception as e:  # noqa: BLE001
                log(f"  CAASPP {yr} {v}: {e}")
        if scores:
            break
    out = sch[["CDSCode", "School", "District", "County", "SOCType", "lat", "lon"]].dropna(subset=["lat"])
    if scores:
        yr, sc = scores
        cols = {c.lower().strip(): c for c in sc.columns}
        def col(*names):
            for n in names:
                if n in cols:
                    return cols[n]
            return None
        cc, dc, scode = col("county code"), col("district code"), col("school code")
        grp, grade, test = col("student group id", "subgroup id"), col("grade"), col("test id")
        pct = col("percentage standard met and above")
        sc = sc[(sc[grp].astype(str).str.lstrip("0") == "1") & (sc[grade].astype(str).str.lstrip("0") == "13")]
        sc["CDSCode"] = sc[cc].str.zfill(2) + sc[dc].str.zfill(5) + sc[scode].str.zfill(7)
        sc["pct"] = pd.to_numeric(sc[pct], errors="coerce")
        p = sc.pivot_table(index="CDSCode", columns=test, values="pct", aggfunc="mean")
        p.columns = ["ela_pct_met" if str(c).lstrip("0") == "1" else "math_pct_met" for c in p.columns]
        out = out.merge(p.reset_index(), on="CDSCode", how="left")
        note("ca_school_scores", caaspp_year=f"{yr - 1}-{str(yr)[2:]}")
    return out


def school_metrics(tr, sch):
    """Average test scores of the 3 nearest scored public schools + nearest school info."""
    s = sch.dropna(subset=["lat"]).copy()
    if "ela_pct_met" in s:
        s = s[s.ela_pct_met.notna() | s.math_pct_met.notna()]
    sg = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s.lon, s.lat), crs=4326).to_crs(3857).reset_index(drop=True)
    t = tr[tr.STATEFP == "06"].to_crs(3857)
    rep = t.geometry.representative_point()
    xy = np.c_[sg.geometry.x, sg.geometry.y]
    rows = []
    for gid, pt in zip(t.GEOID, rep):
        d = np.hypot(xy[:, 0] - pt.x, xy[:, 1] - pt.y)
        order = np.argsort(d)[:3]
        near = sg.iloc[order]
        rows.append({"GEOID": gid,
                     "school_ela_pct_met_near3": round(near.ela_pct_met.mean(), 1) if "ela_pct_met" in near else None,
                     "school_math_pct_met_near3": round(near.math_pct_met.mean(), 1) if "math_pct_met" in near else None,
                     "schools_near3": json.dumps([{"name": r.School, "district": r.District, "type": r.SOCType,
                                                   "ela": None if pd.isna(r.get("ela_pct_met")) else round(r.ela_pct_met, 1),
                                                   "math": None if pd.isna(r.get("math_pct_met")) else round(r.math_pct_met, 1),
                                                   "dist_m": int(dd)} for (_, r), dd in zip(near.iterrows(), d[order])])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- USAspending (current & past federal projects)
@source("usaspending_projects")
def usaspending():
    rows = []
    keywords = ["urban forest", "tree planting", "street trees", "park", "greening", "trail", "schoolyard",
                "complete streets", "green infrastructure", "stormwater", "vacant lot", "reconnecting communities",
                "brownfield", "pedestrian", "bicycle"]
    for st, co, label, _ in COUNTIES:
        body = {"filters": {"award_type_codes": ["02", "03", "04", "05"],
                            "place_of_performance_locations": [{"country": "USA", "state": STATE_ABBR[st], "county": co}],
                            "time_period": [{"start_date": "2019-10-01", "end_date": datetime.now().strftime("%Y-%m-%d")}],
                            "keywords": keywords},
                "fields": ["Award ID", "Recipient Name", "Award Amount", "Description", "Start Date", "End Date",
                           "Awarding Agency", "Awarding Sub Agency", "Place of Performance Zip5", "generated_internal_id"],
                "sort": "Award Amount", "order": "desc", "limit": 100, "page": 1}
        for page in (1, 2):
            body["page"] = page
            r = get("https://api.usaspending.gov/api/v2/search/spending_by_award/", method="POST", json_body=body, timeout=120)
            res = r.json().get("results", [])
            for x in res:
                x["county_label"] = label
                x["county_fips"] = st + co
            rows += res
            if len(res) < 100:
                break
            time.sleep(2)
    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------- BLS wages -> regional cost factor
@source("bls_oews_cost_factor")
def bls_costs():
    occ = {"37-3011": "landscaping_worker", "37-3013": "tree_trimmer", "47-2061": "construction_laborer",
           "47-2073": "equipment_operator"}
    frames = {}
    for kind, url in (("msa", "https://www.bls.gov/oes/special-requests/oesm24ma.zip"),
                      ("nat", "https://www.bls.gov/oes/special-requests/oesm24nat.zip")):
        p = cached_download(url, f"oesm24{kind}.zip", 200)
        with zipfile.ZipFile(p) as z:
            name = [n for n in z.namelist() if n.lower().endswith(".xlsx")][0]
            frames[kind] = pd.read_excel(z.open(name), dtype=str)
    msa, nat = frames["msa"], frames["nat"]
    msa.columns = [c.upper() for c in msa.columns]
    nat.columns = [c.upper() for c in nat.columns]
    rows = []
    for st, co, label, code in COUNTIES:
        r = {"county_fips": st + co, "county": label, "msa": code}
        ratios = []
        for o, nm in occ.items():
            m = msa[(msa.AREA == code) & (msa.OCC_CODE == o)]
            n = nat[nat.OCC_CODE == o]
            mv = pd.to_numeric(m.H_MEAN, errors="coerce").mean() if len(m) else np.nan
            nv = pd.to_numeric(n.H_MEAN, errors="coerce").mean() if len(n) else np.nan
            r[f"{nm}_hourly"] = mv
            if mv and nv and not np.isnan(mv) and not np.isnan(nv):
                ratios.append(mv / nv)
        labor = float(np.mean(ratios)) if ratios else np.nan
        r["labor_ratio"] = labor
        # ~60% labor, ~40% materials/equipment priced near national level
        r["cost_factor"] = round(0.6 * labor + 0.4, 3) if not np.isnan(labor) else np.nan
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- EPA walkability
@source("epa_walkability")
def walkability(tr):
    p = cached_download("https://edg.epa.gov/EPADataCommons/public/OA/WalkabilityIndex.zip", "walkability.zip", 300)
    d = CACHE / "walk"
    if not d.exists():
        with zipfile.ZipFile(p) as z:
            z.extractall(d)
    gdb = [f for f in d.rglob("*.gdb")]
    src = gdb[0] if gdb else [f for f in d.rglob("*.shp")][0]
    import pyogrio
    layers = pyogrio.list_layers(src)
    log(f"  walkability layers {layers}")
    where = " OR ".join(f"(STATEFP='{st}' AND COUNTYFP='{co}')" for st, co, *_ in COUNTIES)
    g = gpd.read_file(src, layer=layers[0][0], where=where, columns=["STATEFP", "COUNTYFP", "NatWalkInd", "TotPop"])
    g = g.to_crs(3857)
    g["geometry"] = g.geometry.representative_point()
    j = gpd.sjoin(g, tr.to_crs(3857)[["GEOID", "geometry"]], predicate="within")
    j["w"] = j.TotPop.clip(lower=1)
    out = (j.NatWalkInd * j.w).groupby(j.GEOID).sum() / j.w.groupby(j.GEOID).sum()
    return out.rename("walk_index").reset_index()


# ---------------------------------------------------------------- assemble
def stage_out(name, df):
    if df is not None and len(df):
        df.to_csv(OUT / f"stage_{name}.csv", index=False)


def run_stage(stage):
    """Each stage writes its own files so stages can run as parallel CI jobs."""
    tr = tracts() if stage not in ("federal", "bls", "merge") else None
    if stage == "base":
        metrics = tr[["GEOID", "STATEFP", "COUNTYFP", "NAMELSAD", "ALAND"]].copy()
        metrics["county"] = metrics.apply(lambda r: next(c[2] for c in COUNTIES if c[0] == r.STATEFP and c[1] == r.COUNTYFP), axis=1)
        metrics["land_acres"] = metrics.ALAND / 4046.86
        a = acs()
        if a is not None:
            metrics = metrics.merge(a, on="GEOID", how="left")
        metrics.to_csv(OUT / "stage_base.csv", index=False)
        geo = tr[["GEOID", "geometry"]].to_crs(5070)
        geo["geometry"] = geo.geometry.simplify(12, preserve_topology=True)
        geo.to_crs(4326).to_file(OUT / "tracts.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    elif stage == "tes":
        stage_out("tes", tree_equity())
    elif stage == "fhfa":
        stage_out("fhfa", fhfa())
    elif stage == "nri":
        stage_out("nri", nri())
    elif stage == "places":
        stage_out("places", places())
    elif stage == "walk":
        stage_out("walk", walkability(tr))
    elif stage == "osm":
        o = osm(tr)
        if o is not None:
            parks, points = o
            stage_out("osm", osm_metrics(tr, parks, points).assign(
                osm_neighborhoods=lambda d: d.osm_neighborhoods.apply(json.dumps)))
            if parks is not None:
                pk = parks.copy()
                pk["geometry"] = pk.to_crs(5070).geometry.simplify(5).to_crs(4326)
                pk.to_file(OUT / "osm_parks.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
            points.to_file(OUT / "osm_points.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
            if ROADS is not None:
                rd = ROADS.copy()
                rd["geometry"] = rd.to_crs(5070).geometry.simplify(15).to_crs(4326)
                rd.to_file(OUT / "osm_roads.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    elif stage == "schools":
        sch = ca_schools()
        if sch is not None and len(sch):
            sch.to_csv(OUT / "ca_schools.csv", index=False)
            stage_out("schools", school_metrics(tr, sch))
    elif stage == "zillow":
        zz, zc = zillow_zips(), zctas()
        if zc is not None:
            rep = gpd.GeoDataFrame(tr[["GEOID"]], geometry=tr.to_crs(3857).geometry.representative_point().to_crs(4326), crs=4326)
            j = gpd.sjoin(rep, zc, predicate="within")[["GEOID", "ZCTA5CE20"]].drop_duplicates("GEOID")
            out = j.rename(columns={"ZCTA5CE20": "zip"})
            if zz is not None:
                z2 = zz.rename(columns={"RegionName": "zip"}).drop(columns=["CountyName", "State"])
                z2.columns = ["zip"] + [f"zip_{c}" for c in z2.columns[1:]]
                out = out.merge(z2, on="zip", how="left")
            stage_out("zillow", out)
        zn = zillow_neighborhoods()
        if zn is not None:
            zn.to_csv(OUT / "zillow_neighborhoods.csv", index=False)
    elif stage == "federal":
        us = usaspending()
        if us is not None:
            us.to_csv(OUT / "federal_projects.csv", index=False)
    elif stage == "bls":
        bl = bls_costs()
        if bl is not None:
            bl.to_csv(OUT / "regional_costs_bls.csv", index=False)
    elif stage == "merge":
        metrics = pd.read_csv(OUT / "stage_base.csv", dtype={"GEOID": str, "STATEFP": str, "COUNTYFP": str})
        for f in sorted(OUT.glob("stage_*.csv")):
            if f.name == "stage_base.csv":
                continue
            df = pd.read_csv(f, dtype={"GEOID": str, "zip": str})
            df = df.drop(columns=[c for c in df.columns if c in metrics.columns and c != "GEOID"])
            metrics = metrics.merge(df, on="GEOID", how="left")
            log(f"  merged {f.name}: {len(df.columns) - 1} columns")
        metrics.to_csv(OUT / "tract_metrics.csv", index=False)
        status = {"generated_at": STATUS["generated_at"], "sources": {}, "tracts": len(metrics),
                  "counties": [c[2] for c in COUNTIES]}
        for f in sorted(OUT.glob("status_*.json")):
            status["sources"].update(json.loads(f.read_text()).get("sources", {}))
        (OUT / "pipeline_status.json").write_text(json.dumps(status, indent=2, default=str))
        log(json.dumps({k: v.get("ok") for k, v in status["sources"].items()}, indent=1))
        return
    (OUT / f"status_{stage}.json").write_text(json.dumps(STATUS, indent=2, default=str))
    log(json.dumps(STATUS, indent=1, default=str)[:4000])


def main():
    stages = sys.argv[1:] or ["base", "tes", "fhfa", "nri", "places", "walk", "osm", "schools", "zillow",
                              "federal", "bls", "merge"]
    for st in stages:
        run_stage(st)


if __name__ == "__main__":
    main()
