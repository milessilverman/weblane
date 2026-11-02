"""City Pretty v2: county-wide block-group data for all of Los Angeles County.

Each stage runs as its own GitHub Actions job (so one failing source never blocks
the rest) and writes block-group metrics keyed by 12-digit GEOID into
data/derived/county_la/, plus simplified map layers for the web page.

    python neighborhood-roi/pipeline/county_la.py geo|osm|transit|sales|crime|requests311|crashes|trees
"""
import io
import json
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
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dataset as bd  # noqa: E402

log, get, cached_download, CACHE = bd.log, bd.get, bd.cached_download, bd.CACHE

OUT = Path(__file__).resolve().parent.parent / "data" / "derived" / "county_la"
BBOX = (-118.95, 33.70, -117.64, 34.83)  # LA County, W S E N
M = 3310  # California Albers (meters)
STATUS = {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": {}}
VIOLENT = r"ASSAULT|ROBBERY|HOMICIDE|MURDER|RAPE|SHOTS|BATTERY|KIDNAP|MANSLAUGHTER|SEX(UAL)? (ASSAULT|BATTERY)|WEAPON"
PROPERTY = r"BURGLARY|THEFT|STOLEN|VANDALISM|LARCENY|SHOPLIFT|ARSON|EMBEZZLE|FRAUD|PICKPOCKET|BIKE"


def note(name, **kw):
    STATUS["sources"].setdefault(name, {}).update(kw)


def rowtext(df):
    if df.empty:
        return pd.Series([], dtype=str, index=df.index)
    return df.astype(object).where(df.notna(), "").astype(str).agg(" ".join, axis=1).str.upper()


# ------------------------------------------------------------------ shared geography
_BG = None


def block_groups():
    """2023 Census block groups in LA County (land only, Catalina/San Clemente kept but flagged)."""
    global _BG
    if _BG is None:
        bg = gpd.read_file("zip://" + str(cached_download("https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_06_bg_500k.zip", "bg_06.zip", 300)))
        bg = bg[(bg.COUNTYFP == "037") & (bg.ALAND > 0)].to_crs(4326)
        _BG = bg[["GEOID", "ALAND", "AWATER", "geometry"]].reset_index(drop=True)
    return _BG


def bg_points():
    """Representative point of each block group (meters CRS) for distance metrics."""
    b = block_groups().to_crs(M)
    return gpd.GeoDataFrame({"GEOID": b.GEOID}, geometry=b.geometry.representative_point(), crs=M)


def count_in_bg(points, name):
    """Count points (any CRS) inside each block group."""
    if points is None or not len(points):
        return pd.Series(dtype=float, name=name)
    j = gpd.sjoin(points.to_crs(M)[["geometry"]], block_groups().to_crs(M)[["GEOID", "geometry"]], predicate="within")
    return j.groupby("GEOID").size().rename(name)


def nearest_m(feats, name, max_m=8000):
    """Distance (m) from each block group's representative point to the nearest feature."""
    p = bg_points()
    if feats is None or not len(feats):
        return pd.Series(np.nan, index=p.GEOID, name=name)
    f = feats.to_crs(M)[["geometry"]].reset_index(drop=True)
    j = gpd.sjoin_nearest(p, f, max_distance=max_m, distance_col="d", how="left")
    return j.groupby("GEOID").d.min().reindex(p.GEOID).rename(name)


def within_m(feats, name, radius):
    """Number of features within `radius` m of each block group's representative point."""
    p = bg_points()
    if feats is None or not len(feats):
        return pd.Series(0, index=p.GEOID, name=name)
    f = feats.to_crs(M)[["geometry"]].reset_index(drop=True)
    buf = gpd.GeoDataFrame({"GEOID": p.GEOID}, geometry=p.buffer(radius), crs=M)
    j = gpd.sjoin(f, buf, predicate="intersects")
    return j.groupby("GEOID").size().reindex(p.GEOID).fillna(0).astype(int).rename(name)


def save(df, name):
    df = df.reset_index() if "GEOID" not in df.columns else df
    df.to_csv(OUT / f"{name}.csv", index=False)
    log(f"  wrote {name}.csv {df.shape}")


def save_layer(g, name, tol=None, prec=5):
    g = g.to_crs(4326)
    if tol:
        g = g.copy()
        g["geometry"] = g.to_crs(M).geometry.simplify(tol).to_crs(4326)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    g.to_file(OUT / f"map_{name}.geojson", driver="GeoJSON", COORDINATE_PRECISION=prec)
    log(f"  wrote map_{name}.geojson ({len(g)} features, {(OUT / f'map_{name}.geojson').stat().st_size / 1e6:.1f} MB)")


def arcgis_all(url, where="1=1", fields="*", bbox=None, page=None, max_rows=3_000_000, geom=True):
    meta = get(url, params={"f": "json"}, timeout=90).json()
    page = page or min(2000, int(meta.get("maxRecordCount") or 1000))
    rows, off = [], 0
    while True:
        p = {"where": where, "outFields": fields, "returnGeometry": "true" if geom else "false", "outSR": 4326, "f": "geojson",
             "resultOffset": off, "resultRecordCount": page}
        if bbox:
            p.update({"geometry": ",".join(map(str, bbox)), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                      "spatialRel": "esriSpatialRelIntersects"})
        fs = get(url.rstrip("/") + "/query", params=p, timeout=300).json().get("features", [])
        rows += fs
        if len(fs) < page or len(rows) >= max_rows:
            break
        off += page
        if off % (page * 25) == 0:
            log(f"    {url.split('/services/')[-1][:50]} {off:,}")
    if not rows:
        return None
    g = gpd.GeoDataFrame.from_features(rows, crs=4326)
    return g


def socrata_find(domain, query, must=()):
    try:
        cat = get("https://api.us.socrata.com/api/catalog/v1", params={"domains": domain, "q": query, "limit": 50}).json()
    except Exception as e:  # noqa: BLE001
        log(f"  socrata catalog unavailable for {domain}: {e}")
        return []
    res = [r["resource"] for r in cat["results"] if all(m.lower() in r["resource"]["name"].lower() for m in must)]
    res.sort(key=lambda r: r.get("data_updated_at") or r.get("updatedAt") or "", reverse=True)
    log("  socrata candidates: " + "; ".join(f"{r['id']} {r['name']} ({(r.get('data_updated_at') or '')[:10]})" for r in res[:8]))
    return res


def socrata_rows(domain, rid, where, limit=50000, max_rows=1_500_000, select=None):
    rows, off = [], 0
    while off < max_rows:
        p = {"$where": where, "$limit": limit, "$offset": off, "$order": ":id"}
        if select:
            p["$select"] = select
        page = get(f"https://{domain}/resource/{rid}.json", params=p, timeout=300).json()
        rows += page
        if len(page) < limit:
            break
        off += limit
        log(f"    {rid} {off:,}")
    return pd.DataFrame(rows)


def points_from(df, latc, lonc):
    df = df.copy()
    df["lat"] = pd.to_numeric(df[latc], errors="coerce")
    df["lon"] = pd.to_numeric(df[lonc], errors="coerce")
    df = df[df.lat.between(33.3, 35.0) & df.lon.between(-119.2, -117.4)]
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326)


# ------------------------------------------------------------------ geo: block groups, ACS, heat, names
ACS = {"B01003_001E": "population", "B25001_001E": "housing_units", "B25002_003E": "vacant_units",
       "B25004_008E": "vacant_other_units", "B25003_001E": "occupied_units", "B25003_002E": "owner_units",
       "B25077_001E": "median_home_value", "B25064_001E": "median_gross_rent", "B19013_001E": "median_household_income",
       "B25035_001E": "median_year_built", "B25024_002E": "units_sf_detached", "B25024_003E": "units_sf_attached",
       "B08301_001E": "commuters", "B08301_010E": "commuters_transit", "B08301_019E": "commuters_walk",
       "B08301_018E": "commuters_bike", "B25044_003E": "owner_no_vehicle", "B25044_010E": "renter_no_vehicle",
       "B17010_001E": "families", "B17010_002E": "families_below_poverty", "B01001_001E": "pop_total_age",
       "B09001_001E": "children_under18"}


def acs_bg():
    tables = sorted({v.split("_")[0] for v in ACS})
    pref = "1500000US06037"
    for year in (2024, 2023):
        try:
            out = None
            for t in tables:
                p = cached_download(f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{t.lower()}.dat",
                                    f"acs{year}_{t}.dat", 200)
                df = pd.read_csv(p, sep="|", dtype=str)
                df = df[df.GEO_ID.str.startswith(pref)]
                keep = {"GEO_ID": "GEO_ID"}
                for v, nm in ACS.items():
                    tbl, rest = v.split("_")
                    if tbl == t and f"{tbl}_E{rest[:-1]}" in df.columns:
                        keep[f"{tbl}_E{rest[:-1]}"] = nm
                df = df[list(keep)].rename(columns=keep)
                out = df if out is None else out.merge(df, on="GEO_ID", how="outer")
            out["GEOID"] = out.GEO_ID.str[-12:]
            for c in ACS.values():
                if c in out:
                    out[c] = pd.to_numeric(out[c], errors="coerce")
                    out.loc[out[c] < 0, c] = np.nan
            note("geo", acs_vintage=f"{year - 4}-{year} ACS 5-year, block groups", acs_rows=len(out))
            return out.drop(columns="GEO_ID")
        except Exception as e:  # noqa: BLE001
            log(f"  ACS BG {year}: {e}")
    raise RuntimeError("no ACS block-group data")


def tes_bg():
    p = cached_download("https://national-tes-data-share.s3.amazonaws.com/national_tes_share/ca.zip.zip", "tes_ca.zip", 120)
    d = CACHE / "tes_ca_county"
    d.mkdir(exist_ok=True)
    with zipfile.ZipFile(p) as z:
        z.extractall(d)
    for inner in list(d.rglob("*.zip")):
        with zipfile.ZipFile(inner) as z:
            z.extractall(inner.parent / inner.stem)
    shp = [f for f in d.rglob("*.shp")][0]
    g = gpd.read_file(shp, mask=gpd.GeoSeries([box(*BBOX)], crs=4326))
    keep = [c for c in ("geoid", "treecanopy", "tc_goal", "tc_gap", "avg_temp", "tes", "priority", "lingiso", "health_nor") if c in g.columns]
    g = pd.DataFrame(g[keep]).rename(columns={"geoid": "GEOID"})
    for c in keep[1:]:
        if c != "priority":
            g[c] = pd.to_numeric(g[c], errors="coerce")
            g.loc[g[c] < 0, c] = np.nan
    g["GEOID"] = g.GEOID.astype(str).str.zfill(12)
    return g[g.GEOID.str.startswith("06037")]


HOOD_LAYERS = [  # (city or source label, ArcGIS layer, preferred name fields)
    ("Culver City", "https://gisproxy.culvercity.org/arcgis/rest/services/PropInfoData/MapServer/25", ("NAME", "NEIGHBORHOOD", "Neighborhood", "LABEL")),
    ("Santa Monica", "https://gis.santamonica.gov/server/rest/services/Neighborhood_Organizations/MapServer/0", ("NAME", "Name", "ORG_NAME", "NEIGHBORHOOD")),
    ("Pasadena", "https://services2.arcgis.com/zNjnZafDYCAJAbN0/ArcGIS/rest/services/NeighAssocCommunityResources/FeatureServer/23", ("NAME", "Name", "ASSOC_NAME", "NEIGHBORHOOD")),
    ("Long Beach", "https://services6.arcgis.com/yCArG7wGXGyWLqav/arcgis/rest/services/Neighborhoods/FeatureServer/0", ("NAME", "Name", "NEIGHBORHOOD", "NEIGH_NAME")),
    ("Glendale", "https://gismap.glendaleca.gov/arcgis/rest/services/Common/NeighborhoodZones/MapServer/1", ("NAME", "Name", "ZONE_NAME")),
    ("Torrance", "https://services1.arcgis.com/38fAqAZVRCrVtPUU/ArcGIS/rest/services/HOA_Publisher/FeatureServer/0", ("Name", "NAME", "HOA_NAME")),
]
CSA_URL = "https://dpw.gis.lacounty.gov/dpw/rest/services/GIS_Web_Services/MapServer/4"


def hood_layers():
    """Official city neighborhood polygons, LA Times Mapping L.A., and county Countywide Statistical Areas."""
    frames = []
    for label, url, names in HOOD_LAYERS:
        try:
            g = arcgis_all(url)
            if g is None:
                raise RuntimeError("empty")
            nf = next((c for c in names if c in g.columns), None) or next((c for c in g.columns if re.search("name", c, re.I)), None)
            g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
            g = gpd.GeoDataFrame({"hood": g[nf].astype(str).str.strip().str.title(), "hood_source": f"{label} (city GIS)", "geometry": g.geometry}, crs=4326)
            g = g[g.hood.str.len().between(2, 60) & ~g.hood.str.upper().isin(["NONE", "NAN"])]
            frames.append(g)
            note("geo", **{f"hoods_{label}": len(g), f"hoods_{label}_field": nf})
        except Exception as e:  # noqa: BLE001
            note("geo", **{f"hoods_{label}_error": str(e)[:200]})
    lat = None
    for u in ("https://raw.githubusercontent.com/codeforamerica/click_that_hood/main/public/data/los-angeles.geojson",):
        try:
            lat = gpd.read_file(get(u).text).to_crs(4326)
            lat = gpd.GeoDataFrame({"hood": lat["name"], "hood_source": "LA Times Mapping L.A.", "geometry": lat.geometry}, crs=4326)
            note("geo", la_times_hoods=len(lat))
        except Exception as e:  # noqa: BLE001
            note("geo", la_times_error=str(e)[:200])
    csa = None
    try:
        csa = arcgis_all(CSA_URL)
        lab = next((c for c in ("LABEL", "COMMUNITY", "LCITY", "CITY_COMM_NAME") if c in csa.columns), None)
        csa = gpd.GeoDataFrame({"csa": csa[lab].astype(str), "csa_type": csa.get("CITY_TYPE", pd.Series("", index=csa.index)).astype(str),
                                "csa_city": csa.get("LCITY", pd.Series("", index=csa.index)).astype(str),
                                "geometry": csa.geometry}, crs=4326)
        note("geo", csa_rows=len(csa), csa_field=lab)
    except Exception as e:  # noqa: BLE001
        note("geo", csa_error=str(e)[:200])
    return frames, lat, csa


def assign_names(bg, frames, lat, csa, places):
    """City from Census places; neighborhood from (1) official city layer, (2) LA Times, (3) county CSA, (4) city."""
    pts = gpd.GeoDataFrame({"GEOID": bg.GEOID}, geometry=bg.to_crs(M).geometry.representative_point(), crs=M)
    out = pd.DataFrame({"GEOID": bg.GEOID})

    def pick(poly, col):
        if poly is None or not len(poly):
            return pd.Series(np.nan, index=out.GEOID)
        j = gpd.sjoin(pts, poly.to_crs(M), predicate="within", how="left")
        return j.drop_duplicates("GEOID").set_index("GEOID")[col].reindex(out.GEOID)

    out["city"] = pick(places.rename(columns={"NAME": "city"})[["city", "geometry"]], "city").values
    out["city"] = out.city.fillna("Unincorporated LA County")
    if csa is not None:
        out["csa"] = pick(csa, "csa").values
    off = pd.concat(frames, ignore_index=True) if frames else None
    if off is not None and len(off):
        out["hood_official"] = pick(off, "hood").values
        out["hood_official_src"] = pick(off, "hood_source").values
    if lat is not None:
        out["hood_latimes"] = pick(lat, "hood").values
    nm = out.get("hood_official", pd.Series(np.nan, index=out.index))
    src = out.get("hood_official_src", pd.Series(np.nan, index=out.index))
    for col, label in (("hood_latimes", "LA Times Mapping L.A."), ("csa", "LA County Countywide Statistical Area")):
        if col in out:
            v = out[col]
            if col == "csa":
                v = v.str.replace(r"^(City of|Unincorporated|Los Angeles)\s*-\s*", "", regex=True)
            fill = nm.isna() & v.notna()
            nm, src = nm.where(~fill, v), src.where(~fill, label)
    out["hood"] = nm.fillna(out.city)
    out["hood_source"] = src.fillna("City boundary (no neighborhood map)")
    return out


def stage_geo():
    bg = block_groups()
    acs = acs_bg()
    df = pd.DataFrame({"GEOID": bg.GEOID, "aland_m2": bg.ALAND}).merge(acs, on="GEOID", how="left")
    try:
        df = df.merge(tes_bg(), on="GEOID", how="left")
        note("geo", tes_rows=int(df.tes.notna().sum()) if "tes" in df else 0)
    except Exception as e:  # noqa: BLE001
        note("geo", tes_error=str(e)[:200])
    pl = gpd.read_file("zip://" + str(cached_download("https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_06_place_500k.zip", "place_06.zip", 300))).to_crs(4326)
    pl = pl[pl.intersects(box(*BBOX)) & (pl.LSAD == "25")][["NAME", "geometry"]]  # incorporated cities only
    frames, lat, csa = hood_layers()
    names = assign_names(bg, frames, lat, csa, pl)
    df = df.merge(names, on="GEOID", how="left")
    save(df, "bg_attributes")
    save_layer(bg[["GEOID", "geometry"]], "block_groups", tol=8, prec=5)
    save_layer(pl.rename(columns={"NAME": "name"}), "cities", tol=25, prec=4)
    hoods = [f for f in frames] + ([lat] if lat is not None else [])
    if hoods:
        h = pd.concat(hoods, ignore_index=True)
        save_layer(gpd.GeoDataFrame(h, geometry="geometry", crs=4326), "hoods", tol=20, prec=5)
    note("geo", block_groups=len(df), named_official=int(names.hood_source.str.contains("city GIS").sum()),
         named_latimes=int((names.hood_source == "LA Times Mapping L.A.").sum()),
         by_source={k: int(v) for k, v in names.hood_source.value_counts().items()})


# ------------------------------------------------------------------ osm: amenities, roads, noise walls, power lines
def stage_osm():
    w, s, e, n = BBOX
    pbf = cached_download("https://download.geofabrik.de/north-america/us/california/socal-latest.osm.pbf", "geofabrik_socal.osm.pbf", 25)
    cut = CACHE / "lacounty.pbf"
    bd._sh("osmium", "extract", "-b", f"{w},{s},{e},{n}", str(pbf), "-o", str(cut), "--overwrite", "-s", "complete_ways")

    def layer(name, *exprs):
        f, g = CACHE / f"co_{name}.pbf", CACHE / f"co_{name}.geojson"
        bd._sh("osmium", "tags-filter", str(cut), *exprs, "-o", str(f), "--overwrite")
        bd._sh("osmium", "export", str(f), "-o", str(g), "--overwrite", "-f", "geojson", "-a", "type,id")
        d = gpd.read_file(g)
        log(f"  {name}: {len(d)} features")
        note("osm", **{name: len(d)})
        return d

    def col(d, c):
        return d[c] if c in d.columns else pd.Series(np.nan, index=d.index)

    def pts(d):
        d = d[d.geometry.notna()].copy()
        d["geometry"] = d.to_crs(M).geometry.representative_point().to_crs(4326)
        return d

    out = {}
    parks = layer("parks", "wr/leisure=park,nature_reserve,recreation_ground,garden")
    parks = parks[parks.geom_type.isin(["Polygon", "MultiPolygon"])]
    pm = parks.to_crs(M)
    parks = parks.assign(acres=pm.area / 4046.86)
    garden = parks[(col(parks, "leisure") == "garden") & ~col(parks, "garden:type").isin(["community"])]
    parks_main = parks.drop(garden.index)
    parks_main = parks_main[parks_main.acres >= 0.1]
    out["park_nearest_m"] = nearest_m(parks_main, "x")
    big = parks_main[parks_main.acres >= 5]
    out["big_park_nearest_m"] = nearest_m(big, "x")
    # park acres within a half mile of each block group's center
    p = bg_points()
    buf = gpd.GeoDataFrame({"GEOID": p.GEOID}, geometry=p.buffer(805), crs=M)
    ov = gpd.overlay(buf, pm.loc[parks_main.index, ["geometry"]].assign(geometry=lambda d: d.buffer(0)), how="intersection", keep_geom_type=True)
    out["park_acres_half_mile"] = (ov.area / 4046.86).groupby(ov.GEOID).sum().reindex(p.GEOID).fillna(0)

    am = layer("amenities",
               "nwr/leisure=pitch,playground,dog_park,swimming_pool,sports_centre,fitness_station,skatepark",
               "nwr/amenity=library,toilets,drinking_water,marketplace,restaurant,cafe,fast_food,bar,pub,nightclub,community_centre,school,college,university,childcare,clinic,doctors,cinema,theatre,arts_centre,charging_station",
               "nwr/shop=supermarket,greengrocer,convenience,alcohol",
               "nwr/landuse=allotments", "nwr/garden:type=community")
    am = pts(am)
    sport, leis, amen, shop = col(am, "sport").fillna(""), col(am, "leisure").fillna(""), col(am, "amenity").fillna(""), col(am, "shop").fillna("")
    acc = col(am, "access").fillna("")
    public = ~acc.isin(["private", "customers", "no"])
    kinds = {
        "tennis": (leis == "pitch") & sport.str.contains("tennis") & public,
        "pickleball": sport.str.contains("pickleball") & public,
        "basketball": (leis == "pitch") & sport.str.contains("basketball") & public,
        "playground": (leis == "playground") & public,
        "dog_park": leis == "dog_park",
        "pool": ((leis == "swimming_pool") | ((leis == "sports_centre") & sport.str.contains("swimming"))) & public & ~acc.isin(["private"]),
        "skatepark": (leis == "skatepark") | sport.str.contains("skateboard"),
        "sports_field": (leis == "pitch") & sport.str.contains("soccer|baseball|softball|football|multi") & public,
        "fitness": leis == "fitness_station",
        "library": amen == "library",
        "toilets": (amen == "toilets") & public,
        "drinking_water": amen == "drinking_water",
        "market": amen == "marketplace",
        "grocery": shop.isin(["supermarket", "greengrocer"]),
        "dining": amen.isin(["restaurant", "cafe"]),
        "fast_food": amen == "fast_food",
        "nightlife": amen.isin(["bar", "pub", "nightclub"]),
        "liquor": shop.isin(["alcohol"]),
        "community_centre": amen == "community_centre",
        "school": amen == "school",
        "childcare": amen == "childcare",
        "clinic": amen.isin(["clinic", "doctors"]),
        "culture": amen.isin(["cinema", "theatre", "arts_centre"]),
        "ev_charger": amen == "charging_station",
        "community_garden": (col(am, "landuse") == "allotments") | (col(am, "garden:type") == "community"),
    }
    for k, m in kinds.items():
        f = am[m]
        note("osm", **{f"n_{k}": int(m.sum())})
        out[f"{k}_nearest_m"] = nearest_m(f, k)
        if k in ("dining", "nightlife", "grocery", "liquor", "fast_food", "culture", "ev_charger"):
            out[f"{k}_within_400m"] = within_m(f, k, 400)
            out[f"{k}_within_800m"] = within_m(f, k, 800)
    save_layer(am[kinds["tennis"] | kinds["pickleball"] | kinds["basketball"] | kinds["playground"] | kinds["dog_park"] | kinds["pool"]
                  | kinds["skatepark"] | kinds["library"] | kinds["community_garden"]].assign(
        kind=np.select([kinds[k] for k in ("tennis", "pickleball", "basketball", "playground", "dog_park", "pool", "skatepark", "library", "community_garden")],
                       ["tennis", "pickleball", "basketball", "playground", "dog park", "pool", "skate park", "library", "community garden"], ""),
        name=col(am, "name"))[["kind", "name", "geometry"]], "amenities", prec=5)

    roads = layer("roads", "w/highway=motorway,trunk,primary,secondary,motorway_link")
    hw = col(roads, "highway")
    fw = roads[hw.isin(["motorway", "trunk"])]
    out["freeway_nearest_m"] = nearest_m(fw, "fw")
    walls = layer("walls", "w/wall=noise_barrier", "w/barrier=noise_barrier")
    # share of freeway frontage near homes that already has a sound wall: freeway length within 150 m of the BG
    bgm = block_groups().to_crs(M)
    fwm = fw.to_crs(M)
    near = gpd.GeoDataFrame({"GEOID": bgm.GEOID}, geometry=bgm.buffer(150), crs=M)
    fj = gpd.overlay(fwm[["geometry"]], near, how="intersection", keep_geom_type=True)
    out["freeway_m_within_150m"] = fj.length.groupby(fj.GEOID).sum().reindex(bgm.GEOID).fillna(0)
    if len(walls):
        wj = gpd.overlay(walls.to_crs(M)[["geometry"]], near, how="intersection", keep_geom_type=True)
        out["noise_wall_m"] = wj.length.groupby(wj.GEOID).sum().reindex(bgm.GEOID).fillna(0)
    power = layer("power", "w/power=line")
    out["hv_line_nearest_m"] = nearest_m(power, "hv")
    rail = layer("rail", "w/railway=rail,light_rail,subway")
    stations = pts(layer("stations", "nwr/railway=station", "nwr/public_transport=station"))
    stations = stations[col(stations, "railway").isin(["station"]) | col(stations, "train").eq("yes") | col(stations, "subway").eq("yes")
                        | col(stations, "light_rail").eq("yes")]
    out["rail_station_nearest_m"] = nearest_m(stations, "rs")
    water = layer("water", "w/waterway=river,canal")
    lamps = layer("lamps", "n/highway=street_lamp")
    out["street_lamps"] = count_in_bg(lamps, "lamps") if len(lamps) else pd.Series(dtype=float)
    res = layer("resroads", "w/highway=residential,living_street")
    rj = gpd.overlay(res.to_crs(M)[["geometry"]], bgm[["GEOID", "geometry"]], how="intersection", keep_geom_type=True)
    out["res_street_km"] = (rj.length / 1000).groupby(rj.GEOID).sum().reindex(bgm.GEOID).fillna(0)

    df = pd.DataFrame({k: v.reindex(bg_points().GEOID).values if hasattr(v, "reindex") else v for k, v in out.items()})
    df.insert(0, "GEOID", bg_points().GEOID.values)
    save(df, "bg_osm")
    # map layers
    save_layer(roads[hw.isin(["motorway", "trunk"])].assign(kind="freeway", name=col(roads, "ref").fillna(col(roads, "name")))[["kind", "name", "geometry"]], "freeways", tol=20)
    save_layer(roads[hw.isin(["primary", "secondary"])].assign(kind=hw, name=col(roads, "name"))[["kind", "name", "geometry"]], "arterials", tol=12)
    save_layer(parks_main[parks_main.acres >= 1].assign(name=col(parks_main, "name"), acres=lambda d: d.acres.round(1))[["name", "acres", "geometry"]], "parks", tol=10)
    save_layer(rail.assign(name=col(rail, "name"))[["name", "geometry"]], "rail", tol=15)
    save_layer(stations.assign(name=col(stations, "name"))[["name", "geometry"]], "stations")
    save_layer(water.assign(name=col(water, "name"))[["name", "geometry"]], "water", tol=15)
    if len(walls):
        save_layer(walls[["geometry"]], "noise_walls", tol=5)


# ------------------------------------------------------------------ transit frequency (GTFS)
GTFS = [
    ("LA Metro bus", "https://gitlab.com/LACMTA/gtfs_bus/-/raw/master/gtfs_bus.zip"),
    ("LA Metro rail", "https://gitlab.com/LACMTA/gtfs_rail/-/raw/master/gtfs_rail.zip"),
    ("Big Blue Bus", "https://gtfs.bigbluebus.com/current.zip"),
    ("LADOT DASH/Commuter", "https://ladotbus.com/gtfs"),
    ("Long Beach Transit", "https://drive.google.com/uc?export=download&id=1bDtwwJMShaGxvXXtgu-eeZFoJ9DhEBM-"),
    ("Culver CityBus", "https://www.culvercity.gov/files/assets/public/v/1/documents/transportation/gtfs/google_transit.zip"),
    ("Foothill Transit", "https://foothilltransit.rideralerts.com/gtfs/google_transit.zip"),
]


def gtfs_stop_freq(name, url):
    p = cached_download(url, "gtfs_" + re.sub(r"\W+", "_", name) + ".zip", 7)
    z = zipfile.ZipFile(p)

    def rd(f, **kw):
        return pd.read_csv(z.open(f), dtype=str, **kw)
    stops = rd("stops.txt")
    st = rd("stop_times.txt", usecols=lambda c: c in ("trip_id", "stop_id", "departure_time"))
    trips = rd("trips.txt")
    routes = rd("routes.txt")
    # busiest weekday service
    if "calendar.txt" in z.namelist():
        cal = rd("calendar.txt")
        wk = cal[cal.get("wednesday", "0") == "1"].service_id
        trips_w = trips[trips.service_id.isin(wk)]
        if trips_w.empty:
            trips_w = trips
    else:
        cd = rd("calendar_dates.txt")
        top = cd[cd.exception_type == "1"].groupby("date").size().idxmax()
        trips_w = trips[trips.service_id.isin(cd[(cd.date == top) & (cd.exception_type == "1")].service_id)]
    # each trip's service_id may cover the whole week; keep the single largest weekday pattern per route
    trips_w = trips_w.merge(routes[["route_id", "route_type"]], on="route_id", how="left")
    st = st[st.trip_id.isin(trips_w.trip_id)]
    hh = pd.to_numeric(st.departure_time.str.split(":").str[0], errors="coerce")
    am = st[(hh >= 7) & (hh < 9)]
    freq = am.groupby("stop_id").size() / 2.0  # departures per hour, 7-9am
    s = stops.set_index("stop_id")
    s = s.loc[s.index.intersection(freq.index)]
    g = gpd.GeoDataFrame({"tph": freq.reindex(s.index).values, "agency": name},
                         geometry=gpd.points_from_xy(pd.to_numeric(s.stop_lon), pd.to_numeric(s.stop_lat)), crs=4326)
    rail = trips_w.route_type.isin(["0", "1", "2"]).any() and "rail" in name.lower()
    g["rail"] = bool(rail)
    note("transit", **{f"{name}_stops": len(g), f"{name}_trips": int(len(trips_w))})
    return g


def stage_transit():
    frames = []
    for name, url in GTFS:
        try:
            frames.append(gtfs_stop_freq(name, url))
        except Exception as e:  # noqa: BLE001
            note("transit", **{f"{name}_error": str(e)[:200]})
            log(f"  {name}: {e}")
    if not frames:
        raise RuntimeError("no GTFS feeds")
    g = pd.concat(frames, ignore_index=True)
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=4326)
    # combine stops within 60 m (both sides of the street / several agencies)
    gm = g.to_crs(M)
    gm["cell"] = (gm.geometry.x // 60).astype(int).astype(str) + "_" + (gm.geometry.y // 60).astype(int).astype(str)
    agg = gm.groupby("cell").agg(tph=("tph", "sum"), x=("geometry", lambda s: s.x.mean()), y=("geometry", lambda s: s.y.mean()), rail=("rail", "max"))
    cells = gpd.GeoDataFrame(agg, geometry=gpd.points_from_xy(agg.x, agg.y), crs=M)
    cells["tph"] = cells.tph / 2  # two directions
    p = bg_points()
    out = pd.DataFrame({"GEOID": p.GEOID})
    for r in (400, 800):
        buf = gpd.GeoDataFrame({"GEOID": p.GEOID}, geometry=p.buffer(r), crs=M)
        j = gpd.sjoin(cells, buf, predicate="within")
        out[f"bus_max_tph_{r}m"] = j[~j.rail].groupby("GEOID").tph.max().reindex(p.GEOID).fillna(0).values
        out[f"stops_{r}m"] = j.groupby("GEOID").size().reindex(p.GEOID).fillna(0).values
    rail = cells[cells.rail]
    out["rail_stop_nearest_m"] = nearest_m(rail, "r").values
    save(out, "bg_transit")
    fr = cells[(cells.tph >= 8) & ~cells.rail].to_crs(4326)
    save_layer(fr.assign(tph=fr.tph.round(0))[["tph", "geometry"]], "frequent_stops")
    note("transit", combined_stops=len(cells), frequent_stops=int((cells.tph >= 8).sum()))


# ------------------------------------------------------------------ sales (LA County Assessor)
def stage_sales():
    url = "https://assessor.gis.lacounty.gov/assessor/rest/services/PAIS/pais_sales_parcels/MapServer/0"
    w, s, e, n = BBOX
    frames = []
    # tile the county so no single query gets too deep into pagination
    xs, ys = np.linspace(w, e, 5), np.linspace(s, n, 5)
    for i in range(4):
        for j in range(4):
            try:
                g = arcgis_all(url, fields="AIN,SALEDATE,SALEPRICE,SIZE,BEDROOMS,BATHROOMS,YEARBUILT,EFFECTIVE_YEARBUILT,USECODE,USETYPE",
                               bbox=(xs[i], ys[j], xs[i + 1], ys[j + 1]), max_rows=400000)
                if g is not None:
                    frames.append(g)
                    log(f"  tile {i},{j}: {len(g):,}")
            except Exception as ex:  # noqa: BLE001
                note("sales", **{f"tile_{i}{j}_error": str(ex)[:160]})
    g = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["AIN", "SALEDATE"])
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=4326)
    g["geometry"] = g.to_crs(M).geometry.representative_point().to_crs(4326)
    d = g.SALEDATE
    g["date"] = pd.to_datetime(d, unit="ms", errors="coerce") if np.issubdtype(pd.Series(d).dtype, np.number) else pd.to_datetime(d, errors="coerce")
    out = pd.DataFrame({"ain": g.AIN, "date": g.date.dt.strftime("%Y-%m-%d"), "price": pd.to_numeric(g.SALEPRICE, errors="coerce"),
                        "sqft": pd.to_numeric(g.SIZE, errors="coerce"), "beds": pd.to_numeric(g.BEDROOMS, errors="coerce"),
                        "baths": pd.to_numeric(g.BATHROOMS, errors="coerce"), "yearbuilt": pd.to_numeric(g.YEARBUILT, errors="coerce"),
                        "usecode": g.USECODE.astype(str), "lon": g.geometry.x.round(6), "lat": g.geometry.y.round(6)})
    j = gpd.sjoin(gpd.GeoDataFrame(out, geometry=gpd.points_from_xy(out.lon, out.lat), crs=4326).to_crs(M),
                  block_groups().to_crs(M)[["GEOID", "geometry"]], predicate="within", how="left")
    out["GEOID"] = j.groupby(level=0).GEOID.first().reindex(out.index)
    out.to_csv(OUT / "sales.csv.gz", index=False, compression="gzip")
    note("sales", rows=len(out), first=str(out.date.min()), last=str(out.date.max()))


# ------------------------------------------------------------------ crime (LAPD, LASD, Santa Monica, Long Beach, Pasadena)
def stage_crime():
    frames = []
    # LAPD: newest dataset (NIBRS since March 2024; legacy 2020-2024 file as fallback)
    cands = [{"id": "k7nn-b2ep", "name": "LAPD NIBRS Offenses"}, {"id": "2nrs-mtv8", "name": "Crime Data from 2020 to Present"}]
    cands += [c for c in socrata_find("data.lacity.org", "crime NIBRS") if re.search(r"crime|nibrs|offense", c["name"], re.I)]
    best = None
    for c in cands[:8]:
        rid = c["id"]
        try:
            sample = get(f"https://data.lacity.org/resource/{rid}.json", params={"$limit": 1}).json()
            cols = list(sample[0].keys())
            latc = next(k for k in cols if k.lower() in ("lat", "latitude"))
            lonc = next(k for k in cols if k.lower() in ("lon", "longitude", "long"))
            datec = next(k for k in cols if re.search(r"date_occ|dateocc|occ_date|date_occurred|occurred|offense_date|incident_date", k, re.I))
            mx = get(f"https://data.lacity.org/resource/{rid}.json", params={"$select": f"max({datec}) as m"}).json()[0]["m"]
            note("crime", **{f"lapd_{rid}_latest": mx[:10], f"lapd_{rid}_cols": cols[:40]})
            if best is None or mx > best[4]:
                best = (rid, latc, lonc, datec, mx, c["name"])
        except Exception as ex:  # noqa: BLE001
            note("crime", **{f"lapd_{rid}_error": str(ex)[:160]})
    if best:
        rid, latc, lonc, datec, mx, nm = best
        since = (datetime.fromisoformat(mx[:19]) - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
        df = socrata_rows("data.lacity.org", rid, f"{datec} > '{since}'")
        g = points_from(df, latc, lonc)
        txt = rowtext(g.drop(columns="geometry"))
        g["violent"], g["property"] = txt.str.contains(VIOLENT), txt.str.contains(PROPERTY)
        g["agency"] = "LAPD"
        frames.append(g[["agency", "violent", "property", "geometry"]])
        note("crime", lapd_dataset=f"{rid} {nm}", lapd_rows=len(g), lapd_window=f"{since[:10]} to {mx[:10]}")
    # LASD: Part I crimes (downloadable CSVs listed on the transparency page)
    try:
        page = get("https://lasd.org/transparency/crimeandarrest/").text
        links = sorted(set(re.findall(r'href="([^"]+\.(?:csv|xlsx?|zip))"', page, re.I)))
        note("crime", lasd_links=links[:30])
        part1 = [u for u in links if re.search(r"part.?i[^i]|part_?1|PART_I_", u, re.I)] or links
        for u in part1[:6]:
            u = u if u.startswith("http") else "https://lasd.org" + u
            try:
                raw = get(u, timeout=300).content
                df = pd.read_csv(io.BytesIO(raw), dtype=str, low_memory=False) if u.lower().endswith(".csv") else pd.read_excel(io.BytesIO(raw), dtype=str)
                cols = list(df.columns)
                latc = next((c for c in cols if re.search(r"^lat", c, re.I)), None)
                lonc = next((c for c in cols if re.search(r"^lon|^lng", c, re.I)), None)
                note("crime", **{"lasd_cols_" + u.rsplit("/", 1)[-1][:40]: cols[:30]})
                if not latc:
                    continue
                g = points_from(df, latc, lonc)
                txt = rowtext(g.drop(columns="geometry"))
                g["violent"], g["property"] = txt.str.contains(VIOLENT), txt.str.contains(PROPERTY)
                g["agency"] = "LASD"
                frames.append(g[["agency", "violent", "property", "geometry"]])
                note("crime", lasd_file=u, lasd_rows=len(g))
                break
            except Exception as ex:  # noqa: BLE001
                note("crime", **{"lasd_err_" + u.rsplit("/", 1)[-1][:40]: str(ex)[:160]})
    except Exception as ex:  # noqa: BLE001
        note("crime", lasd_error=str(ex)[:200])
    # Santa Monica (CKAN)
    try:
        rid = "ff0f4877-3731-4476-b2ca-065f5819bf12"
        base = "https://data.santamonica.gov/api/3/action/"
        meta = get(base + "datastore_search", params={"resource_id": rid, "limit": 1}).json()["result"]
        fields = [f["id"] for f in meta["fields"]]
        datec = next(f for f in fields if re.search(r"date.*occ|occ.*date", f, re.I))
        latc = next(f for f in fields if re.search(r"^lat", f, re.I))
        lonc = next(f for f in fields if re.search(r"^lon|^lng", f, re.I))
        rows, off = [], 0
        while off < 60000:
            page = get(base + "datastore_search", params={"resource_id": rid, "limit": 10000, "offset": off, "sort": f"{datec} desc"}, timeout=300).json()["result"]["records"]
            rows += page
            if len(page) < 10000:
                break
            off += 10000
        df = pd.DataFrame(rows)
        df["when"] = pd.to_datetime(df[datec], errors="coerce")
        df = df[df.when >= df.when.max() - timedelta(days=365)]
        g = points_from(df, latc, lonc)
        txt = rowtext(g.drop(columns=["geometry", "when"]))
        g["violent"], g["property"] = txt.str.contains(VIOLENT), txt.str.contains(PROPERTY)
        g["agency"] = "Santa Monica PD"
        frames.append(g[["agency", "violent", "property", "geometry"]])
        note("crime", santa_monica_rows=len(g), santa_monica_latest=str(df.when.max())[:10])
    except Exception as ex:  # noqa: BLE001
        note("crime", santa_monica_error=str(ex)[:200])
    if not frames:
        raise RuntimeError("no crime sources")
    allc = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=4326)
    j = gpd.sjoin(allc.to_crs(M), block_groups().to_crs(M)[["GEOID", "geometry"]], predicate="within")
    g = j.groupby("GEOID")
    out = pd.DataFrame({"crimes": g.size(), "violent_crimes": g.violent.sum(), "property_crimes": g.property.sum(),
                        "crime_agency": g.agency.agg(lambda s: s.mode().iat[0])})
    out = out.reindex(block_groups().GEOID)
    # which block groups are inside a covered agency's area (no records = zero only if covered)
    covered = allc.groupby("agency").size().to_dict()
    note("crime", rows_by_agency=covered)
    save(out.reset_index(), "bg_crime")


# ------------------------------------------------------------------ MyLA311 (City of LA)
def stage_requests311():
    cands = [{"id": "b7dx-7gc3", "name": "MyLA311 Service Request Data 2024"}]
    cands = [c for c in socrata_find("data.lacity.org", "MyLA311 Service Request Data") if "311" in c["name"]] + cands
    cats = {"illegal_dumping": r"ILLEGAL DUMP|BULKY|ABANDONED ITEM|DEAD ANIMAL|LITTER",
            "graffiti": r"GRAFFITI", "streetlight": r"STREETLIGHT|STREET LIGHT|SINGLE STREETLIGHT|MULTIPLE STREETLIGHT",
            "encampment": r"HOMELESS|ENCAMPMENT", "pothole": r"POTHOLE|PAVEMENT", "tree": r"TREE"}
    for c in cands[:6]:
        rid = c["id"]
        try:
            sample = get(f"https://data.lacity.org/resource/{rid}.json", params={"$limit": 1}).json()
            cols = list(sample[0].keys())
            latc = next(k for k in cols if k.lower() == "latitude")
            lonc = next(k for k in cols if k.lower() == "longitude")
            typc = next(k for k in cols if k.lower() in ("requesttype", "request_type", "type"))
            datec = next(k for k in cols if k.lower() in ("createddate", "created_date", "createddatetime"))
            mx = get(f"https://data.lacity.org/resource/{rid}.json", params={"$select": f"max({datec}) as m"}).json()[0]["m"]
            since = (datetime.fromisoformat(mx[:19]) - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
            df = socrata_rows("data.lacity.org", rid, f"{datec} > '{since}'", select=f"{typc},{latc},{lonc}", max_rows=2_500_000)
            if len(df) < 1000:
                continue
            g = points_from(df, latc, lonc)
            t = g[typc].astype(str).str.upper()
            j = gpd.sjoin(g.to_crs(M)[["geometry"]].assign(t=t.values), block_groups().to_crs(M)[["GEOID", "geometry"]], predicate="within")
            out = pd.DataFrame({k: j[j.t.str.contains(rx)].groupby("GEOID").size() for k, rx in cats.items()})
            out["requests_total"] = j.groupby("GEOID").size()
            out = out.reindex(block_groups().GEOID).fillna(0).astype(int)
            out["in_la_city_311"] = out.requests_total > 0
            save(out.reset_index(), "bg_311")
            note("requests311", dataset=f"{rid} {c['name']}", rows=len(g), window=f"{since[:10]} to {mx[:10]}",
                 types={k: int(v) for k, v in t.value_counts().head(25).items()})
            return
        except Exception as ex:  # noqa: BLE001
            note("requests311", **{f"{rid}_error": str(ex)[:200]})
    raise RuntimeError("no MyLA311 dataset usable")


# ------------------------------------------------------------------ crashes (CHP CCRS on data.ca.gov)
def stage_crashes():
    pk = get("https://data.ca.gov/api/3/action/package_search", params={"q": "CCRS crashes", "rows": 20}).json()["result"]["results"]
    res = []
    for p in pk:
        for r in p.get("resources", []):
            if re.search(r"crash", r.get("name", "") + r.get("url", ""), re.I) and r.get("format", "").upper() == "CSV":
                res.append((p["name"], r["name"], r["url"], r["id"]))
    note("crashes", candidates=[f"{a} / {b}" for a, b, *_ in res[:30]])
    yrs = sorted({int(m) for *_, u, _ in res for m in re.findall(r"20(?:1[6-9]|2[0-9])", u)}, reverse=True)
    frames = []
    for pkg, nm, url, rid in res:
        if not re.search(r"crashes", nm, re.I) or not any(str(y) in (nm + url) for y in yrs[:4]):
            continue
        try:
            p = cached_download(url, "ccrs_" + re.sub(r"\W+", "_", nm)[:60] + ".csv", 60)
            for chunk in pd.read_csv(p, dtype=str, chunksize=200000, low_memory=False):
                cols = {c.lower(): c for c in chunk.columns}
                latc = next((cols[c] for c in cols if c in ("latitude", "lat")), None)
                lonc = next((cols[c] for c in cols if c in ("longitude", "lon", "long")), None)
                if not latc:
                    break
                g = points_from(chunk, latc, lonc)
                txt = rowtext(g[[c for c in g.columns if re.search(r"sever|kill|injur|fatal|pedestrian|bicycl|motorist|collision_type", c, re.I)]])
                g["ksi"] = txt.str.contains(r"FATAL|KILLED|SEVERE")
                g["ped_bike"] = txt.str.contains(r"PEDESTRIAN|BICYCL")
                frames.append(g[["ksi", "ped_bike", "geometry"]])
            note("crashes", **{f"used_{nm[:40]}": int(sum(len(f) for f in frames))})
        except Exception as ex:  # noqa: BLE001
            note("crashes", **{f"err_{nm[:40]}": str(ex)[:160]})
        if len(frames) and sum(len(f) for f in frames) > 600000:
            break
    if not frames:
        raise RuntimeError("no CCRS crash data")
    allc = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=4326)
    j = gpd.sjoin(allc.to_crs(M), block_groups().to_crs(M)[["GEOID", "geometry"]], predicate="within")
    g = j.groupby("GEOID")
    out = pd.DataFrame({"crashes": g.size(), "crashes_ksi": g.ksi.sum(), "crashes_ped_bike": g.ped_bike.sum()}).reindex(block_groups().GEOID).fillna(0)
    save(out.reset_index(), "bg_crashes")
    note("crashes", rows=len(allc))


# ------------------------------------------------------------------ street-tree inventories
def stage_trees():
    frames = []
    base = "https://raw.githubusercontent.com/stiles/la-trees/main/data/municipalities/all/"
    try:
        lst = get("https://api.github.com/repos/stiles/la-trees/contents/data/municipalities/all").json()
        cities = [x["name"][:-8] for x in lst if x["name"].endswith(".geojson") and "los-angeles-city" not in x["name"]]
    except Exception:  # noqa: BLE001
        cities = ["culver-city", "beverly-hills", "santa-monica", "inglewood", "west-hollywood"]
    note("trees", inventory_cities=cities)
    for city in cities:
        try:
            g = gpd.read_file(cached_download(base + f"{city}.geojson", f"trees_{city}.geojson", 60))
            g = g.to_crs(4326) if g.crs else g.set_crs(4326)
            g = g[g.geometry.notna() & (g.geom_type == "Point")]
            txt = rowtext(pd.DataFrame(g.drop(columns="geometry")))
            frames.append(gpd.GeoDataFrame({"src": city, "vacant": txt.str.contains(r"VACANT|PLANTING SITE|EMPTY|NO TREE").values,
                                            "stump": txt.str.contains("STUMP").values}, geometry=g.geometry.values, crs=4326))
        except Exception as e:  # noqa: BLE001
            note("trees", **{f"{city}_error": str(e)[:120]})
    # City of LA live inventory, tiled
    url = "https://geola.daveytreekeeper.com/geoserver/Treekeeper/ows"
    w, s, e, n = (-118.67, 33.70, -118.15, 34.34)
    feats = []

    def grab(bb, depth=0):
        v = {"service": "WFS", "version": "1.1.0", "request": "GetFeature", "typeName": "Treekeeper:streetsla_UFDSpeciesLabel",
             "outputFormat": "application/json", "srsName": "EPSG:4326", "bbox": ",".join(map(str, bb)) + ",EPSG:4326", "maxFeatures": 50000}
        fs = get(url, params=v, timeout=300, tries=2).json().get("features", [])
        if len(fs) >= 49000 and depth < 4:
            x0, y0, x1, y1 = bb
            xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
            out = []
            for q in ((x0, y0, xm, ym), (xm, y0, x1, ym), (x0, ym, xm, y1), (xm, ym, x1, y1)):
                out += grab(q, depth + 1)
            return out
        return fs
    xs, ys = np.linspace(w, e, 7), np.linspace(s, n, 7)
    for i in range(6):
        for j in range(6):
            try:
                feats += grab((xs[i], ys[j], xs[i + 1], ys[j + 1]))
            except Exception as ex:  # noqa: BLE001
                note("trees", **{f"la_tile_{i}{j}": str(ex)[:100]})
    if feats:
        g = gpd.GeoDataFrame.from_features(feats, crs=4326)
        g = g[g.geom_type == "Point"]
        txt = rowtext(pd.DataFrame(g.drop(columns="geometry")))
        frames.append(gpd.GeoDataFrame({"src": "los-angeles", "vacant": txt.str.contains(r"VACANT|PLANTING SITE|EMPTY|NO TREE").values,
                                        "stump": txt.str.contains("STUMP").values}, geometry=g.geometry.values, crs=4326))
        note("trees", la_city_records=len(g))
    t = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=4326)
    j = gpd.sjoin(t.to_crs(M), block_groups().to_crs(M)[["GEOID", "geometry"]], predicate="within")
    g = j.groupby("GEOID")
    out = pd.DataFrame({"street_trees": g.apply(lambda d: int((~d.vacant & ~d.stump).sum())), "vacant_tree_sites": g.vacant.sum(),
                        "stumps": g.stump.sum(), "tree_inventory_src": g.src.agg(lambda s: s.mode().iat[0])}).reindex(block_groups().GEOID)
    save(out.reset_index(), "bg_trees")
    note("trees", records=len(t), by_source={k: int(v) for k, v in t.src.value_counts().items()})


STAGES = {"geo": stage_geo, "osm": stage_osm, "transit": stage_transit, "sales": stage_sales, "crime": stage_crime,
          "requests311": stage_requests311, "crashes": stage_crashes, "trees": stage_trees}


def main():
    name = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        STAGES[name]()
        note(name, ok=True)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        note(name, ok=False, error=f"{type(e).__name__}: {e}"[:400])
    note(name, seconds=round(time.time() - t0, 1))
    (OUT / f"status_{name}.json").write_text(json.dumps(STATUS, indent=1, default=str))
    log(json.dumps(STATUS["sources"].get(name, {}), default=str)[:3000])


if __name__ == "__main__":
    main()
