"""City Pretty v2: county-wide block-group data for all of Los Angeles County.

Each stage runs as its own GitHub Actions job (so one failing source never blocks
the rest) and writes block-group metrics keyed by 12-digit GEOID into
data/derived/county_la/, plus simplified map layers for the web page.

    python neighborhood-roi/pipeline/county_la.py geo|osm|transit|sales|crime|requests311|crashes|trees|parcels|assets|tra|assessed
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


def lines_only(g):
    g = g[g.geometry.notna()].explode(index_parts=False)
    return g[g.geom_type.isin(["LineString", "MultiLineString"])]


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
    ("Santa Monica", "https://gis.santamonica.gov/server/rest/services/Neighborhood_Organizations/MapServer/0", ("neighbor", "NEIGHBOR", "NAME", "Name")),
    ("West Hollywood", "https://gis.weho.org/arcgis/rest/services/NeighborhoodWatchGroups/FeatureServer/0", ("Name", "NAME")),
    ("Lancaster", "https://maps.cityoflancasterca.org/server/rest/services/Map_Details/MapServer/8", ("name", "NAME", "city_comm_name")),
    ("Pasadena", "https://services2.arcgis.com/zNjnZafDYCAJAbN0/ArcGIS/rest/services/NeighAssocCommunityResources/FeatureServer/23", ("NAME", "Name", "ASSOC_NAME", "NEIGHBORHOOD")),
    ("Long Beach", "https://services6.arcgis.com/yCArG7wGXGyWLqav/arcgis/rest/services/Neighborhoods/FeatureServer/0", ("NAME", "Name", "NEIGHBORHOOD", "NEIGH_NAME")),
    ("Glendale", "https://gismap.glendaleca.gov/arcgis/rest/services/Common/NeighborhoodZones/MapServer/1", ("NAME", "Name", "ZONE_NAME")),
    ("Torrance", "https://services1.arcgis.com/38fAqAZVRCrVtPUU/ArcGIS/rest/services/HOA_Publisher/FeatureServer/0", ("Name", "NAME", "HOA_NAME")),
]
CSA_URL = "https://dpw.gis.lacounty.gov/dpw/rest/services/GIS_Web_Services/MapServer/4"


def label_points():
    """Neighborhood labels: OSM place nodes plus Culver City's neighborhood annotation layer."""
    frames = []
    try:
        g = arcgis_all("https://gisproxy.culvercity.org/arcgis/rest/services/PropInfoData/MapServer/25")
        txt = next((c for c in ("TextString", "TEXTSTRING", "Text", "NAME") if c in g.columns), None)
        note("geo", culver_label_fields=list(g.columns)[:20])
        if txt:
            g = gpd.GeoDataFrame({"label": g[txt].astype(str).str.replace(r"\s+", " ", regex=True).str.strip().str.title(), "label_source": "Culver City neighborhood map"},
                                 geometry=g.to_crs(M).geometry.representative_point().to_crs(4326).values, crs=4326)
            frames.append(g[g.label.str.len().between(3, 40)])
            note("geo", culver_labels=len(frames[-1]), culver_label_sample=frames[-1].label.head(20).tolist())
    except Exception as e:  # noqa: BLE001
        note("geo", culver_label_error=str(e)[:200])
    return frames


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
                v = v.str.replace(r"^(Unincorporated|Los Angeles)\s*-\s*", "", regex=True).str.replace(r"^City of\s+", "", regex=True)
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
    lp = label_points()
    if lp:
        save_layer(pd.concat(lp, ignore_index=True), "labels_city")
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
    pclean = pm.loc[parks_main.index, ["geometry"]].copy()
    pclean["geometry"] = pclean.geometry.make_valid().buffer(0)
    pclean = pclean.explode(index_parts=False)
    pclean = pclean[pclean.geom_type.isin(["Polygon", "MultiPolygon"]) & ~pclean.is_empty]
    ov = gpd.overlay(buf, pclean, how="intersection", keep_geom_type=True)
    out["park_acres_half_mile"] = (ov.area / 4046.86).groupby(ov.GEOID).sum().reindex(p.GEOID).fillna(0)

    am = layer("amenities",
               "nwr/leisure=pitch,playground,dog_park,swimming_pool,sports_centre,fitness_station,skatepark",
               "nwr/amenity=library,toilets,drinking_water,marketplace,restaurant,cafe,fast_food,bar,pub,nightclub,community_centre,school,college,university,childcare,clinic,doctors,cinema,theatre,arts_centre,charging_station",
               "nwr/shop=supermarket,greengrocer,convenience,alcohol",
               "nwr/landuse=allotments", "nwr/garden:type=community")
    am = pts(am)
    sport, leis, amen, shop = col(am, "sport").fillna(""), col(am, "leisure").fillna(""), col(am, "amenity").fillna(""), col(am, "shop").fillna("")
    acc = col(am, "access").fillna("")
    # OSM maps thousands of backyard pools and private complex courts: count a facility as public only if it is
    # tagged public or sits inside a mapped park / recreation ground
    pk_m = parks_main.to_crs(M)[["geometry"]]
    inpark = gpd.sjoin(am.to_crs(M)[["geometry"]], pk_m, predicate="within").index.unique()
    public = (acc.isin(["yes", "public", "permissive"]) | am.index.isin(inpark)) & ~acc.isin(["private", "customers", "no"])
    kinds = {
        "tennis": (leis == "pitch") & sport.str.contains("tennis") & public,
        "pickleball": sport.str.contains("pickleball") & public,
        "basketball": (leis == "pitch") & sport.str.contains("basketball") & public,
        "playground": (leis == "playground") & public,
        "dog_park": leis == "dog_park",
        "pool": ((leis == "swimming_pool") | ((leis == "sports_centre") & sport.str.contains("swimming"))) & public,
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
    shown = ["tennis", "pickleball", "basketball", "playground", "dog_park", "pool", "skatepark", "library", "community_garden"]
    kind = pd.Series(np.select([kinds[k].values for k in shown], [k.replace("_", " ") for k in shown], ""), index=am.index)
    sel = kind != ""
    save_layer(gpd.GeoDataFrame({"kind": kind[sel], "name": col(am, "name")[sel]}, geometry=am.geometry[sel], crs=am.crs), "amenities", prec=5)
    roads = layer("roads", "w/highway=motorway,trunk,primary,secondary,motorway_link")
    hw = col(roads, "highway")
    fw = roads[hw.isin(["motorway", "trunk"])]
    out["freeway_nearest_m"] = nearest_m(fw, "fw")
    walls = layer("walls", "w/wall=noise_barrier", "w/barrier=noise_barrier")
    # share of freeway frontage near homes that already has a sound wall: freeway length within 150 m of the BG
    bgm = block_groups().to_crs(M)
    fwm = lines_only(fw.to_crs(M))
    near = gpd.GeoDataFrame({"GEOID": bgm.GEOID}, geometry=bgm.buffer(150), crs=M)
    fj = gpd.overlay(fwm[["geometry"]], near, how="intersection", keep_geom_type=True)
    out["freeway_m_within_150m"] = fj.length.groupby(fj.GEOID).sum().reindex(bgm.GEOID).fillna(0)
    if len(walls):
        wj = gpd.overlay(lines_only(walls.to_crs(M)[["geometry"]]), near, how="intersection", keep_geom_type=True)
        out["noise_wall_m"] = wj.length.groupby(wj.GEOID).sum().reindex(bgm.GEOID).fillna(0)
    power = layer("power", "w/power=line")
    out["hv_line_nearest_m"] = nearest_m(power, "hv")
    rail = layer("rail", "w/railway=rail,light_rail,subway")
    stations = pts(layer("stations", "nwr/railway=station", "nwr/public_transport=station"))
    stations = stations[col(stations, "railway").isin(["station"]) | col(stations, "train").eq("yes") | col(stations, "subway").eq("yes")
                        | col(stations, "light_rail").eq("yes")]
    out["rail_station_nearest_m"] = nearest_m(stations, "rs")
    water = layer("water", "w/waterway=river,canal")
    places = pts(layer("places", "nwr/place=neighbourhood,suburb,quarter"))
    if len(places):
        save_layer(places.assign(label=col(places, "name"), kind=col(places, "place"))[["label", "kind", "geometry"]].dropna(subset=["label"]), "places")
    lamps = layer("lamps", "n/highway=street_lamp")
    out["street_lamps"] = count_in_bg(lamps, "lamps") if len(lamps) else pd.Series(dtype=float)
    res = layer("resroads", "w/highway=residential,living_street")
    rj = gpd.overlay(lines_only(res.to_crs(M)[["geometry"]]), bgm[["GEOID", "geometry"]], how="intersection", keep_geom_type=True)
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
    ("Culver CityBus", "https://web.culvercity.org/gtfs/gtfsexport.zip"),
    ("Foothill Transit", "https://foothilltransit.rideralerts.com/myStop/gtfs-zip.ashx"),
    ("Torrance Transit", "https://transit.torranceca.gov/gtfs_feed"),
    ("Norwalk Transit", "https://nts.rideralerts.com/InfoPoint/gtfs-zip.ashx"),
    ("Montebello Bus Lines", "https://mbl.rideralerts.com/infopoint/gtfs-zip.ashx"),
    ("Gardena GTrans", "https://ridegtrans.com/gtfs.zip"),
    ("Santa Clarita Transit", "http://apps.santaclaritatransit.com/rtt/public/utility/gtfs.aspx"),
    ("Antelope Valley Transit", "https://www.avta.com/userfiles/files/AVTA_GTFS.zip"),
    ("Pasadena Transit", "https://rt.pasadenatransit.net/rtt/public/resource/gtfs.zip"),
    ("Glendale Beeline", "https://www.glendaleca.gov/home/showdocument?id=29549"),
    ("BurbankBus", "https://rideburbankbus.com/gtfs"),
    ("Commerce Municipal Bus", "https://citycommbus.com/gtfs"),
    ("El Monte Transit", "https://rapid.nationalrtap.org/GTFSFileManagement/UserUploadFiles/11664/Google_Transit.zip"),
    ("Long Beach Transit", "https://rapid.nationalrtap.org/GTFSFileManagement/UserUploadFiles/14866/google_transit.zip"),
    ("Monterey Park Spirit Bus", "https://passio3.com/montereyp/passioTransit/gtfs/google_transit.zip"),
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
    rail = trips_w.route_type.isin(["0", "1", "2"]).mean() > 0.5
    g["rail"] = bool(rail)
    note("transit", **{f"{name}_stops": len(g), f"{name}_trips": int(len(trips_w))})
    return g


def stage_transit():
    frames = []
    feeds = list(GTFS)  # explicit agency list; the Mobility Database catalog duplicated feeds
    for name, url in feeds:
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
            note("crime", **{f"lapd_{rid}_cols": cols[:40]})
            latc = next(k for k in cols if re.search(r"^lat$|latitude|_lat$", k, re.I))
            lonc = next(k for k in cols if re.search(r"^lon$|longitude|_lon$|^lng$", k, re.I))
            datec = next(k for k in cols if re.search(r"date_occ|dateocc|occ_date|date_occurred|occurred|offense_date|incident_date|date_?time|^date", k, re.I))
            mx = get(f"https://data.lacity.org/resource/{rid}.json", params={"$select": f"max({datec}) as m"}).json()[0]["m"]
            note("crime", **{f"lapd_{rid}_latest": mx[:10], f"lapd_{rid}_cols": cols[:40]})
            if re.search(r"2010 to 2019|20\d\d to 20(0|1)\d", c.get("name", "")):
                continue
            since_c = (datetime.fromisoformat(mx[:19]) - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
            n = int(get(f"https://data.lacity.org/resource/{rid}.json", params={"$select": "count(*) as n", "$where": f"{datec} > '{since_c}'"}).json()[0]["n"])
            note("crime", **{f"lapd_{rid}_rows12mo": n})
            if n > 20000 and (best is None or mx > best[4]):
                best = (rid, latc, lonc, datec, mx, c["name"])
        except Exception as ex:  # noqa: BLE001
            note("crime", **{f"lapd_{rid}_error": str(ex)[:160]})
    if best:
        rid, latc, lonc, datec, mx, nm = best
        since = (datetime.fromisoformat(mx[:19]) - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
        df = socrata_rows("data.lacity.org", rid, f"{datec} > '{since}'")
        if "caseno" in df.columns:  # NIBRS rows are offenses: keep one row per case, flagged violent if any offense is
            df = df.assign(_t=rowtext(df.drop(columns=[c for c in df.columns if c in (latc, lonc)])))
            df = df.groupby("caseno").agg({latc: "first", lonc: "first", "_t": " ".join}).reset_index()
        g = points_from(df, latc, lonc)
        txt = rowtext(g.drop(columns="geometry"))
        g["violent"], g["property"] = txt.str.contains(VIOLENT), txt.str.contains(PROPERTY)
        g["agency"] = "LAPD"
        frames.append(g[["agency", "violent", "property", "geometry"]])
        note("crime", lapd_dataset=f"{rid} {nm}", lapd_rows=len(g), lapd_window=f"{since[:10]} to {mx[:10]}")
    # LASD: Part I crimes (downloadable CSVs listed on the transparency page)
    try:
        page = get("https://lasd.org/transparency/crimeandarrest/").text
        links = sorted(set(re.findall(r'href=["\']([^"\']+\.(?:csv|xlsx?|zip)(?:\?[^"\']*)?)["\']', page, re.I)))
        note("crime", lasd_page_len=len(page), lasd_links=links[:30],
             lasd_hrefs=re.findall(r'href=["\']([^"\']+)["\']', page)[:60])
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
    if not any(f.agency.iat[0] == "LASD" for f in frames if len(f)):
        try:
            found = get("https://www.arcgis.com/sharing/rest/search", params={"q": "(Sheriff OR LASD) crime incidents \"Los Angeles\" type:\"Feature Service\"",
                                                                             "num": 20, "f": "json", "sortField": "modified", "sortOrder": "desc"}).json().get("results", [])
            note("crime", lasd_arcgis_candidates=[f"{x.get('title')} | {x.get('url')}" for x in found[:12]])
            since = datetime.now() - timedelta(days=400)
            best_g = None
            for x in found[:8]:
                if not x.get("url") or not re.search(r"crime", x.get("title", "") + x["url"], re.I):
                    continue
                u = x["url"].rstrip("/") + "/0"
                try:
                    g = arcgis_all(u, max_rows=600000)
                    if g is None or len(g) < 1000:
                        continue
                    datec = next((c for c in g.columns if re.search(r"date", c, re.I)), None)
                    if datec is not None:
                        dt = pd.to_datetime(g[datec], unit="ms", errors="coerce") if np.issubdtype(g[datec].dtype, np.number) else pd.to_datetime(g[datec], errors="coerce")
                        if dt.max() < since:
                            note("crime", **{f"lasd_stale_{x.get('title', '')[:30]}": str(dt.max())[:10]})
                            continue
                        g = g[dt >= dt.max() - timedelta(days=365)]
                        note("crime", **{f"lasd_window_{x.get('title', '')[:30]}": f"{str(dt.min())[:10]} to {str(dt.max())[:10]}"})
                    note("crime", **{f"lasd_rows_{x.get('title', '')[:30]}": len(g)})
                    if best_g is None or len(g) > len(best_g[0]):
                        best_g = (g, x.get("title"), u)
                except Exception as ex:  # noqa: BLE001
                    note("crime", **{f"lasd_arc_err_{x.get('title', '')[:30]}": str(ex)[:120]})
            if best_g is not None:
                g, title, u = best_g
                g = g[g.geometry.notna()]
                g["geometry"] = g.to_crs(M).geometry.representative_point().to_crs(4326)
                txt = rowtext(pd.DataFrame(g.drop(columns="geometry")))
                g["violent"], g["property"] = txt.str.contains(VIOLENT), txt.str.contains(PROPERTY)
                g["agency"] = "LASD"
                frames.append(g[["agency", "violent", "property", "geometry"]])
                note("crime", lasd_dataset=f"{title} {u}", lasd_rows=len(g))
        except Exception as ex:  # noqa: BLE001
            note("crime", lasd_arcgis_error=str(ex)[:200])
    try:
        g = arcgis_all("https://services6.arcgis.com/yCArG7wGXGyWLqav/ArcGIS/rest/services/Police_Crime_Mapping/FeatureServer/0", max_rows=200000)
        g = g[g.geometry.notna()]
        txt = rowtext(pd.DataFrame(g.drop(columns="geometry")))
        g["violent"], g["property"] = txt.str.contains(VIOLENT), txt.str.contains(PROPERTY)
        g["agency"] = "Long Beach PD"
        g["weight"] = 2.0  # six-month rolling map -> per-year rate
        frames.append(g[["agency", "violent", "property", "weight", "geometry"]])
        note("crime", long_beach_rows=len(g))
    except Exception as ex:  # noqa: BLE001
        note("crime", long_beach_error=str(ex)[:200])
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
    allc["weight"] = allc.get("weight", pd.Series(1.0, index=allc.index)).fillna(1.0)
    j = gpd.sjoin(allc.to_crs(M), block_groups().to_crs(M)[["GEOID", "geometry"]], predicate="within")
    j["v_w"], j["p_w"] = j.violent * j.weight, j.property * j.weight
    g = j.groupby("GEOID")
    out = pd.DataFrame({"crimes": g.weight.sum(), "violent_crimes": g.v_w.sum(), "property_crimes": g.p_w.sum(),
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
    cands.sort(key=lambda c: max([int(y) for y in re.findall(r"20\d\d", c["name"])] or [0]), reverse=True)
    cats = {"illegal_dumping": r"ILLEGAL DUMP|ABANDONED|LITTER", "bulky_items": r"BULKY|METAL/HOUSEHOLD|ELECTRONIC WASTE",
            "graffiti": r"GRAFFITI", "streetlight": r"STREETLIGHT|STREET LIGHT|SINGLE STREETLIGHT|MULTIPLE STREETLIGHT",
            "encampment": r"HOMELESS|ENCAMPMENT", "pothole": r"POTHOLE|PAVEMENT", "tree": r"TREE"}
    for c in cands[:6]:
        rid = c["id"]
        try:
            sample = get(f"https://data.lacity.org/resource/{rid}.json", params={"$limit": 1}).json()
            cols = list(sample[0].keys())
            note("requests311", **{f"{rid}_cols": cols[:40]})
            latc = next(k for k in cols if re.search(r"^lat", k, re.I))
            lonc = next(k for k in cols if re.search(r"^lon|^lng", k, re.I))
            typc = next(k for k in cols if re.search(r"request_?type|^type$|srtype|service_?type", k, re.I))
            datec = next(k for k in cols if re.search(r"created", k, re.I))
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


# ------------------------------------------------------------------ vacant parcels (LA County Assessor)
def stage_parcels():
    url = "https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0"
    meta = get(url, params={"f": "json"}, timeout=90).json()
    flds = [f["name"] for f in meta.get("fields", [])]
    landc = next((f for f in flds if re.search(r"land.?value", f, re.I)), None)
    areac = next((f for f in flds if re.search(r"shape.*area|starea", f, re.I)), None)
    note("parcels", fields=flds[:80], land_field=landc, area_field=areac)
    fields = ",".join([f for f in ("AIN", "UseCode", "UseType", "UseDescription", landc, areac) if f])
    frames = []
    w, s, e, n = BBOX
    xs, ys = np.linspace(w, e, 4), np.linspace(s, n, 4)
    for i in range(3):
        for j in range(3):
            try:
                g = arcgis_all(url, where="UseCode LIKE '%V'", fields=fields, bbox=(xs[i], ys[j], xs[i + 1], ys[j + 1]), max_rows=600000)
                if g is not None:
                    frames.append(g)
                    log(f"  tile {i},{j}: {len(g):,}")
            except Exception as ex:  # noqa: BLE001
                note("parcels", **{f"tile_{i}{j}_error": str(ex)[:160]})
    g = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=4326).drop_duplicates("AIN")
    gm = g.to_crs(M)
    g["sqft"] = gm.area * 10.7639
    g["land_value"] = pd.to_numeric(g[landc], errors="coerce") if landc else np.nan
    code = g.UseCode.astype(str)
    g["kind"] = np.where(code.str.startswith("0"), "residential", np.where(code.str.match(r"^[12]"), "commercial", "other"))
    small = g[(g.sqft.between(1500, 43560)) & g.kind.isin(["residential", "commercial"])]
    pts = gpd.GeoDataFrame(small[["kind", "sqft", "land_value"]], geometry=small.to_crs(M).geometry.representative_point(), crs=M)
    j = gpd.sjoin(pts, block_groups().to_crs(M)[["GEOID", "geometry"]], predicate="within")
    grp = j.groupby("GEOID")
    out = pd.DataFrame({"vacant_parcels": grp.size(), "vacant_res_parcels": grp.kind.apply(lambda k: int((k == "residential").sum())),
                        "vacant_sqft": grp.sqft.sum(), "vacant_land_psf_median": (j.land_value / j.sqft).groupby(j.GEOID).median()})
    out = out.reindex(block_groups().GEOID)
    out[["vacant_parcels", "vacant_res_parcels", "vacant_sqft"]] = out[["vacant_parcels", "vacant_res_parcels", "vacant_sqft"]].fillna(0)
    save(out.reset_index(), "bg_parcels")
    save_layer(pts.to_crs(4326).assign(sqft=pts.sqft.round(0))[["kind", "sqft", "geometry"]], "vacant_lots")
    note("parcels", vacant_all=len(g), vacant_small_urban=len(small), by_kind={k: int(v) for k, v in g.kind.value_counts().items()})


def length_by_bg(lines, name):
    if lines is None or not len(lines):
        return pd.Series(dtype=float, name=name)
    l = lines_only(lines.to_crs(M)[["geometry"]])
    ov = gpd.overlay(l, block_groups().to_crs(M)[["GEOID", "geometry"]], how="intersection", keep_geom_type=True)
    return (ov.length / 1000).groupby(ov.GEOID).sum().rename(name)


def stage_assets():
    out = pd.DataFrame({"GEOID": block_groups().GEOID}).set_index("GEOID")
    jobs = {
        "bus_lanes": "https://maps.lacity.org/arcgis/rest/services/Mapping/NavigateLA/MapServer/158",
        "ladwp_overhead": "https://maps.lacity.org/arcgis/rest/services/Mapping/NavigateLA/MapServer/109",
        "ladwp_underground": "https://maps.lacity.org/arcgis/rest/services/Mapping/NavigateLA/MapServer/110",
    }
    for key, url in jobs.items():
        try:
            g = arcgis_all(url, max_rows=1_500_000)
            note("assets", **{f"{key}_rows": 0 if g is None else len(g)})
            if g is None:
                continue
            if key == "bus_lanes":
                save_layer(g.assign(name=g.get("Proj_Name"))[["name", "geometry"]], "bus_lanes", tol=10)
                out["bus_lane_nearest_m"] = nearest_m(g, "bl").values
            else:
                out[f"{key}_km"] = length_by_bg(g, key)
        except Exception as e:  # noqa: BLE001
            note("assets", **{f"{key}_error": str(e)[:200]})
    try:
        g = arcgis_all("https://maps.lacity.org/lahub/rest/services/Bureau_of_Street_Lighting/MapServer/0", fields="OBJECTID,STATUS", max_rows=400000)
        note("assets", streetlights=len(g))
        out["streetlights"] = count_in_bg(g, "sl")
    except Exception as e:  # noqa: BLE001
        note("assets", streetlights_error=str(e)[:200])
    try:
        frames = []
        for u in ("https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/ArcGIS/rest/services/FHSZSRA_23_3/FeatureServer/0",
                  "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/FHSALRA25_v1_All/FeatureServer/0"):
            g = arcgis_all(u, bbox=BBOX, max_rows=200000)
            if g is not None:
                frames.append(g)
        fz = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=4326)
        desc = fz.get("FHSZ_Description", fz.get("FHSZ")).astype(str)
        vh = fz[desc.str.contains("Very High", case=False) | (desc == "3")]
        vh = vh.to_crs(M)
        vh["geometry"] = vh.geometry.make_valid()
        vh = vh[vh.geom_type.isin(["Polygon", "MultiPolygon"])]
        bgm = block_groups().to_crs(M)[["GEOID", "geometry"]]
        ov = gpd.overlay(bgm, vh[["geometry"]], how="intersection", keep_geom_type=True)
        out["fire_vh_share"] = (ov.area.groupby(ov.GEOID).sum() / bgm.set_index("GEOID").area).clip(0, 1)
        note("assets", fire_polygons=len(fz), very_high=len(vh))
    except Exception as e:  # noqa: BLE001
        note("assets", fire_error=str(e)[:200])
    try:
        g = arcgis_all("https://services1.arcgis.com/ZIL9uO234SBBPGL7/ArcGIS/rest/services/c2022_LAUSD_Greening_Index_Republished/FeatureServer/89")
        g["green"] = pd.to_numeric(g.get("Percent_Green_Space"), errors="coerce")
        low = g[g.green < 15]
        out["low_green_school_nearest_m"] = nearest_m(low, "lg").values
        out["lausd_school_green_pct_nearest"] = gpd.sjoin_nearest(bg_points(), g.to_crs(M)[["green", "geometry"]], how="left").drop_duplicates("GEOID").set_index("GEOID").green
        note("assets", lausd_schools=len(g), low_green=len(low))
    except Exception as e:  # noqa: BLE001
        note("assets", lausd_error=str(e)[:200])
    try:
        g = arcgis_all("https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/Alternative_Fueling_Stations/FeatureServer/0",
                       where="fuel_type_code='ELEC' AND state='CA'", bbox=BBOX, max_rows=200000)
        dc = g[pd.to_numeric(g.get("ev_dc_fast_num"), errors="coerce").fillna(0) > 0]
        pub = dc[dc.get("access_code", pd.Series("public", index=dc.index)).astype(str).str.lower().eq("public")]
        out["dcfc_nearest_m"] = nearest_m(pub, "dc").values
        out["dcfc_within_800m"] = within_m(pub, "dc", 800).values
        note("assets", ev_stations=len(g), dc_fast_public=len(pub))
    except Exception as e:  # noqa: BLE001
        note("assets", afdc_error=str(e)[:200])
    save(out.reset_index(), "bg_assets")


# ------------------------------------------------------------------ EIFD inputs: tax-rate areas and assessed values
AUDITOR = "https://auditor.lacounty.gov"
TRA_FILES = {  # fallbacks if the report pages can't be scraped (round-5 research, 2026-11-02)
    "af91": AUDITOR + "/wp-content/uploads/2026/10/AF91.zip",
    "af49": AUDITOR + "/wp-content/uploads/2026/09/AF49PRPT.YR26.zip",
    "tra_lookup": AUDITOR + "/wp-content/uploads/2026/09/TRA-2026-2027.zip",
}
BOE_TRA = "https://services7.arcgis.com/iwxhJVOFEKDxO7gk/ArcGIS/rest/services/Los_Angeles_2026_Roll_Year/FeatureServer"
RAW = OUT / "raw"


def _latest_link(page, pattern):
    try:
        html = get(page, timeout=90).text
        hits = sorted(set(re.findall(r'href="([^"]*' + pattern + r'[^"]*)"', html, re.I)))
        return hits[-1] if hits else None
    except Exception as e:  # noqa: BLE001
        log(f"  could not read {page}: {e}")
        return None


def _keep_zip(key, url):
    """Download a zip, record its members and first lines, and keep every text member (gzipped) in raw/."""
    import gzip
    path = cached_download(url, f"tra_{key}.zip", max_age_days=10)
    info = {"url": url, "bytes": path.stat().st_size, "members": []}
    with zipfile.ZipFile(path) as z:
        for m in z.infolist():
            data = z.read(m)
            head = data[:6000].decode("latin-1", "replace").splitlines()[:25]
            info["members"].append({"name": m.filename, "bytes": m.file_size, "head": head})
            if m.file_size and m.file_size < 400e6:
                safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(m.filename).name)
                with gzip.open(RAW / f"{key}__{safe}.gz", "wb") as f:
                    f.write(data)
    return info


def stage_tra():
    """Auditor-Controller AB8 apportionment factors (AF91), companion AF49, TRA lookup, BOE TRA district table."""
    RAW.mkdir(parents=True, exist_ok=True)
    probe = {}
    links = {
        "af91": _latest_link(AUDITOR + "/property-tax-report-central/", r"AF91[^\"]*\.zip"),
        "af49": _latest_link(AUDITOR + "/property-tax-report-central/", r"AF49[^\"]*\.zip"),
        "tra_lookup": _latest_link(AUDITOR + "/tax-rate-area-lookup/", r"TRA-\d{4}-\d{4}\.zip"),
    }
    for key, url in TRA_FILES.items():
        url = links.get(key) or url
        try:
            probe[key] = _keep_zip(key, url)
            note("tra", **{f"{key}_url": url, f"{key}_members": [m["name"] for m in probe[key]["members"]]})
        except Exception as e:  # noqa: BLE001
            probe[key] = {"url": url, "error": str(e)[:300]}
            note("tra", **{f"{key}_error": str(e)[:200]})
    # BOE TRA district table: which districts (city, county, special districts, schools) levy in each TRA
    try:
        meta = get(BOE_TRA + "/2", params={"f": "json"}, timeout=90).json()
        probe["boe_table_fields"] = [f["name"] for f in meta.get("fields", [])]
        rows, off = [], 0
        while True:
            r = get(BOE_TRA + "/2/query", params={"where": "1=1", "outFields": "*", "f": "json", "resultOffset": off,
                                                  "resultRecordCount": 2000}, timeout=300).json()
            fs = [f["attributes"] for f in r.get("features", [])]
            rows += fs
            if len(fs) < 2000 and not r.get("exceededTransferLimit"):
                break
            off += len(fs)
            if not fs:
                break
        df = pd.DataFrame(rows)
        df.to_csv(RAW / "boe_tra_districts.csv.gz", index=False)
        probe["boe_table_rows"] = len(df)
        probe["boe_table_sample"] = df.head(15).astype(str).to_dict("records")
        note("tra", boe_district_rows=len(df))
    except Exception as e:  # noqa: BLE001
        probe["boe_table_error"] = str(e)[:300]
        note("tra", boe_error=str(e)[:200])
    (OUT / "tra_probe.json").write_text(json.dumps(probe, indent=1, default=str))


ROLL_FIELDS = ["AIN", "TaxRateArea", "TaxRateCity", "UseCode", "Roll_Year", "Roll_LandValue", "Roll_ImpValue",
               "Roll_PersPropValue", "Roll_FixtureValue", "Roll_HomeOwnersExemp", "Roll_RealEstateExemp",
               "Roll_PersPropExemp", "Roll_FixtureExemp", "Roll_LandBaseYear", "Roll_ImpBaseYear"]


def _roll_tile(url, fields, bb, want_geom, page):
    rows, off = [], 0
    while True:
        p = {"where": "1=1", "outFields": ",".join(fields), "returnGeometry": "true" if want_geom else "false",
             "outSR": 4326, "f": "json", "resultOffset": off, "resultRecordCount": page,
             "geometry": ",".join(map(str, bb)), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
             "spatialRel": "esriSpatialRelIntersects"}
        if want_geom:
            p.update({"maxAllowableOffset": 0.00005, "geometryPrecision": 5})
        js = get(url + "/query", params=p, timeout=300).json()
        if "error" in js:
            raise RuntimeError(str(js["error"])[:200])
        for f in js.get("features", []):
            a = f["attributes"]
            if want_geom:
                ring = ((f.get("geometry") or {}).get("rings") or [[]])[0]
                if ring:
                    a["_lon"] = sum(x for x, _ in ring) / len(ring)
                    a["_lat"] = sum(y for _, y in ring) / len(ring)
            rows.append(a)
        n = len(js.get("features", []))
        if n == 0 or (n < page and not js.get("exceededTransferLimit")):
            break
        off += n
    return rows


def stage_assessed():
    """Every parcel's secured-roll value and tax-rate area, summed to block groups (EIFD base value)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    url = "https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0"
    meta = get(url, params={"f": "json"}, timeout=90).json()
    flds = [f["name"] for f in meta.get("fields", [])]
    lat = next((f for f in flds if re.fullmatch(r"center_?lat", f, re.I)), None)
    lon = next((f for f in flds if re.fullmatch(r"center_?lon", f, re.I)), None)
    fields = [f for f in ROLL_FIELDS if f in flds] + ([lat, lon] if lat and lon else [])
    page = min(2000, int(meta.get("maxRecordCount") or 1000))
    note("assessed", all_fields=flds, used=fields, centroid_fields=bool(lat and lon), page=page)
    w, s, e, n = BBOX
    k = 8
    xs, ys = np.linspace(w, e, k + 1), np.linspace(s, n, k + 1)
    tiles = [(xs[i], ys[j], xs[i + 1], ys[j + 1]) for i in range(k) for j in range(k)]
    rows, errs = [], {}

    def fetch(t, depth=0):
        """A tile the server can't answer (HTTP 500 on very dense areas) is split into quarters and retried."""
        try:
            return _roll_tile(url, fields, t, not (lat and lon), page)
        except Exception as e:  # noqa: BLE001
            if depth >= 3:
                errs[str(tuple(round(float(v), 5) for v in t))] = str(e)[:160]
                return []
            time.sleep(5)
            x0, y0, x1, y1 = t
            xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
            return sum((fetch(q, depth + 1) for q in [(x0, y0, xm, ym), (xm, y0, x1, ym), (x0, ym, xm, y1), (xm, ym, x1, y1)]), [])

    with ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(fetch, t): t for t in tiles}
        for i, fu in enumerate(as_completed(futs)):
            r = fu.result()
            rows += r
            log(f"  tile {i + 1}/{len(tiles)}: {len(r):,} (total {len(rows):,})")
    if errs:
        raise RuntimeError(f"{len(errs)} parcel tiles failed even after splitting; keeping the previous data: {list(errs.items())[:3]}")
    df = pd.DataFrame(rows).drop_duplicates("AIN")
    if lat and lon:
        df["_lat"], df["_lon"] = pd.to_numeric(df[lat], errors="coerce"), pd.to_numeric(df[lon], errors="coerce")
    num = [c for c in fields if c.startswith("Roll_") and ("Value" in c or "Exemp" in c)]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["gross"] = df[[c for c in num if "Value" in c]].sum(axis=1)
    df["exempt"] = df[[c for c in num if "Exemp" in c]].sum(axis=1)
    df["net"] = (df.gross - df.exempt).clip(lower=0)
    df["tra"] = df["TaxRateArea"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.zfill(5)
    df["kind"] = np.where(df.UseCode.astype(str).str.startswith("0"), "res",
                          np.where(df.UseCode.astype(str).str.match(r"^[12]"), "com", "other"))
    df["ry"] = pd.to_numeric(df.get("Roll_Year"), errors="coerce")
    note("assessed", parcels=len(df), roll_years={str(k2): int(v) for k2, v in df.ry.value_counts().head(5).items()},
         net_total=float(df.net.sum()), tras=int(df.tra.nunique()))
    pts = points_from(df[["AIN", "tra", "kind", "gross", "exempt", "net", "Roll_LandValue", "Roll_ImpValue",
                          "Roll_HomeOwnersExemp", "_lat", "_lon"]], "_lat", "_lon")
    j = gpd.sjoin(pts.to_crs(M), block_groups().to_crs(M)[["GEOID", "geometry"]], predicate="within")
    note("assessed", parcels_in_bg=len(j))
    g = j.groupby("GEOID")
    out = pd.DataFrame({"av_parcels": g.size(), "av_land": g.Roll_LandValue.sum(), "av_imp": g.Roll_ImpValue.sum(),
                        "av_gross": g.gross.sum(), "av_exempt": g.exempt.sum(), "av_net": g.net.sum(),
                        "av_net_res": j[j.kind == "res"].groupby("GEOID").net.sum(),
                        "av_net_com": j[j.kind == "com"].groupby("GEOID").net.sum(),
                        "av_hox_parcels": j[j.Roll_HomeOwnersExemp > 0].groupby("GEOID").size()})
    out = out.reindex(block_groups().GEOID).fillna(0)
    out["roll_year"] = int(df.ry.mode().iloc[0]) if df.ry.notna().any() else None
    save(out.reset_index(), "bg_assessed")
    # net taxable value by block group and TRA: joined to the Auditor's apportionment factors in the model
    by = j.groupby(["GEOID", "tra"]).agg(parcels=("net", "size"), net=("net", "sum")).reset_index()
    by.to_csv(OUT / "bg_tra_av.csv.gz", index=False)
    log(f"  wrote bg_tra_av.csv.gz {by.shape}")
    df.groupby("tra").agg(parcels=("net", "size"), net=("net", "sum"), city=("TaxRateCity", "first")).reset_index() \
        .to_csv(OUT / "tra_av.csv", index=False)


# ------------------------------------------------------------------ basemap: named streets, all parks, route numbers
STREET_CLASS = {"motorway": 0, "trunk": 0, "primary": 1, "secondary": 1, "tertiary": 2, "unclassified": 3,
                "residential": 3, "living_street": 3}


def _agol_find(query, must):
    """Find a public ArcGIS Online feature layer by title (used for layers whose URL isn't fixed)."""
    try:
        r = get("https://www.arcgis.com/sharing/rest/search", params={"q": query + ' type:"Feature Service"', "num": 25, "f": "json"},
                timeout=60).json()
        hits = [x for x in r.get("results", []) if all(m.lower() in (x.get("title") or "").lower() for m in must)]
        hits.sort(key=lambda x: (x.get("owner", "").lower().find("lacounty") < 0, -(x.get("modified") or 0)))
        log("  agol candidates: " + "; ".join(f"{x['title']} ({x.get('owner')}) {x.get('url')}" for x in hits[:6]))
        return [x["url"] for x in hits if x.get("url")]
    except Exception as e:  # noqa: BLE001
        log(f"  agol search failed: {e}")
        return []


def stage_basemap():
    from shapely.ops import linemerge, unary_union
    import gzip
    w, s, e, n = BBOX
    pbf = cached_download("https://download.geofabrik.de/north-america/us/california/socal-latest.osm.pbf", "geofabrik_socal.osm.pbf", 25)
    cut = CACHE / "lacounty.pbf"
    bd._sh("osmium", "extract", "-b", f"{w},{s},{e},{n}", str(pbf), "-o", str(cut), "--overwrite", "-s", "complete_ways")

    def layer(name, *exprs):
        f, g = CACHE / f"bm_{name}.pbf", CACHE / f"bm_{name}.geojson"
        bd._sh("osmium", "tags-filter", str(cut), *exprs, "-o", str(f), "--overwrite")
        bd._sh("osmium", "export", str(f), "-o", str(g), "--overwrite", "-f", "geojson", "-a", "type,id")
        d = gpd.read_file(g)
        note("basemap", **{name: len(d)})
        return d

    county = block_groups().to_crs(M).union_all() if hasattr(gpd.GeoSeries, "union_all") else block_groups().to_crs(M).unary_union
    county = county.buffer(300)

    # streets: one merged, simplified line per (class, name) chain
    roads = layer("streets", "w/highway=" + ",".join(STREET_CLASS))
    roads = roads[roads.geom_type.isin(["LineString", "MultiLineString"])].copy()
    roads["cls"] = roads["highway"].map(STREET_CLASS)
    roads["name"] = roads.get("name")
    if "ref" in roads:
        fwy = roads["cls"].eq(0)
        roads.loc[fwy, "name"] = roads.loc[fwy, "ref"].fillna(roads.loc[fwy, "name"])
    roads = roads[roads.name.notna()].to_crs(M)
    roads = roads[roads.intersects(county)]
    rows = []
    for (c, nm), g in roads.groupby(["cls", "name"]):
        u = unary_union(list(g.geometry))
        if u.geom_type == "MultiLineString":
            u = linemerge(u)
        for part in (u.geoms if hasattr(u, "geoms") else [u]):
            if part.geom_type == "LineString" and part.length >= 40:
                rows.append((int(c), nm, part.simplify(4 if c >= 2 else 8)))
    st = gpd.GeoDataFrame(rows, columns=["cls", "name", "geometry"], crs=M).to_crs(4326)
    note("basemap", street_lines=len(st), by_class={str(k): int(v) for k, v in st.cls.value_counts().items()})
    with gzip.open(OUT / "map_streets.geojson.gz", "wt") as f:
        f.write(re.sub(r"(-?\d+\.\d{5})\d+", r"\1", st.to_json(drop_id=True)))
    log(f"  wrote map_streets.geojson.gz ({len(st)} lines)")

    # parks: every OSM park, nature reserve, recreation ground, playground lot, community garden and beach,
    # plus any official County park polygons that OSM lacks
    pk = layer("parks_all", "wr/leisure=park,nature_reserve,recreation_ground,garden,playground,dog_park",
               "wr/natural=beach", "wr/boundary=protected_area")
    pk = pk[pk.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    lei = pk.get("leisure", pd.Series(index=pk.index, dtype=object))
    gtype = pk.get("garden:type", pd.Series(index=pk.index, dtype=object))
    access = pk.get("access", pd.Series(index=pk.index, dtype=object))
    pk = pk[~(lei.eq("garden") & ~gtype.eq("community")) & ~access.isin(["private", "no"])]
    pk["kind"] = np.where(pk.get("natural", pd.Series(index=pk.index)).eq("beach"), "beach",
                 np.where(lei.reindex(pk.index).isin(["nature_reserve"]) | pk.get("boundary", pd.Series(index=pk.index)).eq("protected_area"), "open space",
                 np.where(lei.reindex(pk.index).eq("garden"), "community garden",
                 np.where(lei.reindex(pk.index).eq("playground"), "playground",
                 np.where(lei.reindex(pk.index).eq("dog_park"), "dog park", "park")))))
    pk = pk.to_crs(M)
    pk["geometry"] = pk.geometry.make_valid()
    pk = pk[pk.geom_type.isin(["Polygon", "MultiPolygon"]) & pk.intersects(county)]
    pk["acres"] = pk.area / 4046.86
    pk = pk[pk.acres >= 0.02]
    pk["src"] = "OpenStreetMap"
    official = None
    county_parks = "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/Countywide_Parks_and_Open_Space__(Public_-_Hosted2)/FeatureServer/0"
    for url in [county_parks] + _agol_find("Los Angeles County parks open space", ["park"])[:4]:
        try:
            lyr = url.rstrip("/") + ("/0" if not re.search(r"/\d+$", url) else "")
            g = arcgis_all(lyr, bbox=BBOX, max_rows=60000)
            if g is None or not g.geom_type.isin(["Polygon", "MultiPolygon"]).any() or len(g) < 300:
                continue
            official = g
            note("basemap", official_parks_url=lyr, official_parks=len(g), official_fields=list(g.columns)[:40])
            break
        except Exception as ex:  # noqa: BLE001
            note("basemap", official_parks_error=f"{url}: {ex}"[:200])
    if official is not None:
        o = official[official.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(M)
        o["geometry"] = o.geometry.make_valid()
        o = o[o.geom_type.isin(["Polygon", "MultiPolygon"])]
        namec = next((c for c in o.columns if re.fullmatch(r"(park_?)?name|PARK_NAME|Name|NAME|label", c, re.I)), None)
        covered = gpd.overlay(o[["geometry"]].assign(oid=range(len(o))), pk[["geometry"]], how="intersection", keep_geom_type=True)
        cov = covered.area.groupby(covered.oid).sum().reindex(range(len(o))).fillna(0).values / o.area.values
        add = o[cov < 0.5].copy()
        add = gpd.GeoDataFrame({"name": add[namec] if namec else None, "kind": "park", "src": "LA County",
                                "geometry": add.geometry}, crs=M)
        add["acres"] = add.area / 4046.86
        note("basemap", official_added=len(add))
        pk = pd.concat([pk, add[add.acres >= 0.02]], ignore_index=True)
    pk = gpd.GeoDataFrame(pk, geometry="geometry", crs=M)
    pk["geometry"] = pk.geometry.simplify(3)
    pk = pk.assign(name=pk.get("name"), acres=pk.acres.round(2))[["name", "kind", "acres", "src", "geometry"]].to_crs(4326)
    note("basemap", parks=len(pk), parks_by_kind={k: int(v) for k, v in pk.kind.value_counts().items()},
         parks_under_1ac=int((pk.acres < 1).sum()))
    pk.to_file(OUT / "map_parks_all.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    log(f"  wrote map_parks_all.geojson ({len(pk)})")

    fac = layer("facilities", "nwr/amenity=school,college,university,library,townhall,fire_station,police,post_office,hospital,clinic,community_centre,courthouse",
                "nwr/office=government")
    facilities(fac)
    facility_footprints(fac)
    # existing bikeways: off-street paths and on-street lanes (OSM), to say what a street already has
    try:
        bw = layer("bikeways", "w/highway=cycleway", "w/cycleway", "w/cycleway:left", "w/cycleway:right", "w/cycleway:both")
        bw = bw[bw.geom_type.isin(["LineString", "MultiLineString"])].copy()
        tags = pd.DataFrame({c: bw.get(c, pd.Series(index=bw.index, dtype=object)).fillna("").astype(str)
                             for c in ("highway", "cycleway", "cycleway:left", "cycleway:right", "cycleway:both")})
        allc = tags[["cycleway", "cycleway:left", "cycleway:right", "cycleway:both"]].agg(" ".join, axis=1)
        bw["cls"] = np.where(tags.highway.eq("cycleway"), "bike path (Class I)",
                    np.where(allc.str.contains("track|separate"), "protected lane (Class IV)",
                    np.where(allc.str.contains("lane|buffered"), "painted lane (Class II)",
                    np.where(allc.str.contains("shared_lane|share_busway"), "sharrows (Class III)", None))))
        bw = bw[bw.cls.notna()].to_crs(M)
        bw = bw[bw.intersects(county)]
        bw["geometry"] = bw.geometry.simplify(3)
        _write_gz(bw.assign(name=bw.get("name"))[["name", "cls", "geometry"]].to_crs(4326), "map_bikeways.geojson.gz")
        note("basemap", bikeways=len(bw), bikeways_by_class={k: int(v) for k, v in bw.cls.value_counts().items()})
    except Exception as e:  # noqa: BLE001
        note("basemap", bikeways_error=str(e)[:200])
    # surface parking lots of an acre or more (malls, stores, offices): underused-land candidates
    try:
        pl = layer("parking", "wr/amenity=parking")
        pl = pl[pl.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
        ptype = pl.get("parking", pd.Series(index=pl.index, dtype=object)).fillna("surface")
        acc = pl.get("access", pd.Series(index=pl.index, dtype=object)).fillna("")
        pl = pl[ptype.isin(["surface"])].to_crs(M)
        pl["geometry"] = pl.geometry.make_valid().simplify(2)
        pl = pl[pl.geom_type.isin(["Polygon", "MultiPolygon"]) & pl.intersects(county)]
        pl["sqft"] = (pl.area * 10.7639).round(0)
        pl = pl[pl.sqft >= 43560]
        pl.assign(name=pl.get("name"), access=acc.reindex(pl.index))[["name", "access", "sqft", "geometry"]].to_crs(4326) \
            .to_file(OUT / "map_osm_parking.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
        note("basemap", surface_lots_1ac=len(pl), surface_lot_acres=round(float(pl.sqft.sum()) / 43560))
    except Exception as e:  # noqa: BLE001
        note("basemap", parking_error=str(e)[:200])
    # what is already being built: rail lines and stations under construction (OSM)
    try:
        rc = layer("railcon", "w/railway=construction", "w/construction=subway,light_rail,rail")
        rc = rc[rc.geom_type.isin(["LineString", "MultiLineString"])]
        kind = rc.get("construction", pd.Series(index=rc.index, dtype=object)).fillna(rc.get("construction:railway", pd.Series(index=rc.index, dtype=object)))
        rc = rc[kind.isin(["subway", "light_rail", "rail"]) | rc.get("railway", pd.Series(index=rc.index)).eq("construction")]
        rc = rc[rc.to_crs(M).intersects(county)]
        save_layer(rc.assign(name=rc.get("name"), kind=kind)[["name", "kind", "geometry"]], "rail_construction", tol=10)
        sc = layer("stationcon", "nwr/construction:railway=station", "nwr/construction=station", "nwr/construction:public_transport=station",
                   "nwr/railway=construction")
        sc = sc[sc.get("name", pd.Series(index=sc.index)).notna()].copy()
        if len(sc):
            sc["geometry"] = sc.to_crs(M).geometry.representative_point().to_crs(4326)
            sc = sc[sc.to_crs(M).within(county)]
            sc = sc[sc.get("railway", pd.Series(index=sc.index)).ne("construction") | sc.geom_type.eq("Point")]
            save_layer(sc[["name", "geometry"]], "stations_construction")
        note("basemap", rail_construction_lines=len(rc), stations_construction=len(sc))
    except Exception as e:  # noqa: BLE001
        note("basemap", rail_construction_error=str(e)[:200])


# ------------------------------------------------------------------ public facilities (schools, libraries, civic buildings)
FACILITY_KINDS = [  # (kind, regex on LMS layer name / categories / OSM tags)
    ("school", r"\b(public|private|charter|elementary|middle|high|k-?12)\b.*school|^schools?$|school"),
    ("college", r"college|universit"),
    ("library", r"librar"),
    ("city hall", r"city hall|town ?hall|civic center|city government|townhall"),
    ("fire station", r"fire station|fire_station|fire dep"),
    ("police", r"police|sheriff"),
    ("post office", r"post office|post_office"),
    ("hospital", r"hospital|medical center"),
    ("clinic", r"clinic|health cent|health care|doctors"),
    ("community center", r"community cent|community_centre|recreation cent|senior|teen cent|youth cent"),
    ("museum", r"museum|arts center|theat"),
    ("courthouse", r"courthouse|superior court|\bcourts?\b(?!.*(tennis|basketball|pickleball))(?=.*(justice|law|superior|municipal))"),
]
LMS = "https://public.gis.lacounty.gov/public/rest/services/LACounty_Dynamic/LMS_Data_Public/MapServer"


NOT_PUBLIC = r"conference|convention|banquet|wedding|event cent|hotel|country club|private"


def _kind_of(text):
    t = str(text).lower()
    k = next((k for k, pat in FACILITY_KINDS if re.search(pat, t)), None)
    # conference, convention and event venues aren't public community centers
    return None if k == "community center" and re.search(NOT_PUBLIC, t) else k


def facilities(osm_layer):
    """County LMS points first; OSM fills kinds/places LMS lacks (no LMS point of that kind within 150 m)."""
    frames = []
    try:
        meta = get(LMS, params={"f": "json"}, timeout=90).json()
        layers = [(l["id"], l["name"]) for l in meta.get("layers", []) if not l.get("subLayerIds")]
        note("facilities", lms_layers=[f"{i}:{n}" for i, n in layers])
        for lid, lname in layers:
            k0 = _kind_of(lname)
            if not k0 and not re.search(r"government|public safety|health|education|municipal|civic|communit", lname, re.I):
                continue
            try:
                g = arcgis_all(f"{LMS}/{lid}", max_rows=40000)
            except Exception as e:  # noqa: BLE001
                note("facilities", **{f"lms_{lid}_error": str(e)[:120]})
                continue
            if g is None or not len(g):
                continue
            g = g[g.geometry.notna()].copy()
            g["geometry"] = g.geometry.representative_point()
            txt = lname + " " + g.get("cat1", "").astype(str) + " " + g.get("cat2", "").astype(str) + " " + g.get("cat3", "").astype(str)
            cats = (g.get("cat2", "").astype(str) + " " + g.get("cat3", "").astype(str)) if "cat2" in g else pd.Series("", index=g.index)
            g["kind"] = [_kind_of(c) or k0 or _kind_of(t) for c, t in zip(cats, txt)]
            namec = next((c for c in g.columns if c.lower() in ("name", "facname", "label")), None)
            g = g.assign(name=g[namec] if namec else None, addr=g.get("addrln1"), src="LA County LMS")
            frames.append(g[g.kind.notna()][["kind", "name", "addr", "src", "geometry"]])
            note("facilities", **{f"lms_{lid}": int(g.kind.notna().sum())})
    except Exception as e:  # noqa: BLE001
        note("facilities", lms_error=str(e)[:200])
    lms = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326) if frames else None
    o = osm_layer.copy()
    o["geometry"] = o.to_crs(M).geometry.representative_point().to_crs(4326)
    tag = (o.get("amenity", pd.Series(index=o.index, dtype=object)).fillna("").astype(str) + " " +
           o.get("office", pd.Series(index=o.index, dtype=object)).fillna("").astype(str) + " " +
           o.get("name", pd.Series(index=o.index, dtype=object)).fillna("").astype(str))
    o["kind"] = [_kind_of(t) for t in tag]
    o = o[o.kind.notna()].assign(name=o.get("name"), addr=o.get("addr:street"), src="OpenStreetMap")[["kind", "name", "addr", "src", "geometry"]]
    if lms is not None and len(lms):
        lm, om = lms.to_crs(M), o.to_crs(M)
        keep = []
        for k, grp in om.groupby("kind"):
            ref = lm[lm.kind == k]
            if not len(ref):
                keep.append(grp)
                continue
            d = gpd.sjoin_nearest(grp, ref[["geometry"]], how="left", distance_col="d").groupby(level=0).d.min()
            keep.append(grp[d.reindex(grp.index).fillna(1e9) > 150])
        o = gpd.GeoDataFrame(pd.concat(keep), crs=M).to_crs(4326) if keep else o.iloc[:0]
        out = gpd.GeoDataFrame(pd.concat([lms, o], ignore_index=True), crs=4326)
    else:
        out = gpd.GeoDataFrame(o, crs=4326)
    county = block_groups().to_crs(4326).geometry.union_all() if hasattr(gpd.GeoSeries, "union_all") else block_groups().unary_union
    out = out[out.within(county.buffer(0.003))]
    out = out.drop_duplicates(subset=["kind", "name"], keep="first") if out.name.notna().any() else out
    note("facilities", total=len(out), by_kind={k: int(v) for k, v in out.kind.value_counts().items()},
         by_source={k: int(v) for k, v in out.src.value_counts().items()})
    out.to_file(OUT / "map_facilities.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    log(f"  wrote map_facilities.geojson ({len(out)})")
    # per block group: distance to the nearest of each kind
    df = pd.DataFrame({"GEOID": bg_points().GEOID})
    for k in ["school", "library", "city hall", "fire station", "police", "post office", "hospital", "clinic", "community center"]:
        sub = out[out.kind == k]
        df[f"fac_{k.replace(' ', '_')}_m"] = nearest_m(sub, k, max_m=30000).values if len(sub) else np.nan
    save(df, "bg_facilities")


def facility_footprints(osm_layer):
    """Ground footprint of each facility: the OSM area mapped for it (school grounds, library building, city hall...)."""
    o = osm_layer[osm_layer.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    tag = (o.get("amenity", pd.Series(index=o.index, dtype=object)).fillna("").astype(str) + " " +
           o.get("office", pd.Series(index=o.index, dtype=object)).fillna("").astype(str) + " " +
           o.get("name", pd.Series(index=o.index, dtype=object)).fillna("").astype(str))
    o["kind"] = [_kind_of(t) for t in tag]
    o = o[o.kind.notna()].to_crs(M)
    o["geometry"] = o.geometry.make_valid().simplify(1.5)
    o = o[o.geom_type.isin(["Polygon", "MultiPolygon"]) & ~o.is_empty]
    o["acres"] = (o.area / 4046.86).round(2)
    o = o[o.acres >= 0.02]
    out = o.assign(name=o.get("name"))[["kind", "name", "acres", "geometry"]].to_crs(4326)
    out.to_file(OUT / "map_facility_areas.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    note("facilities", footprints=len(out), footprints_by_kind={k: int(v) for k, v in out.kind.value_counts().items()})


# ------------------------------------------------------------------ underused land (parking, golf, vacant, lightly built)
PARCEL_URL = "https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0"
UNDERUSED_QUERIES = [  # kind, where clauses tried in order (the server's SQL support varies)
    ("parking lot", ["UPPER(UseDescription) LIKE '%PARKING%'", "UseDescription LIKE '%Parking%'"]),
    ("golf course", ["UPPER(UseDescription) LIKE '%GOLF%'", "UseDescription LIKE '%Golf%'"]),
    ("vacant", ["UseCode LIKE '%V' AND Shape.STArea() >= 21780", "UseCode LIKE '%V'"]),
    ("lightly built commercial", ["UseType IN ('Commercial','Industrial') AND Roll_ImpValue < Roll_LandValue * 0.2 AND Shape.STArea() >= 43560",
                                  "UseType IN ('Commercial','Industrial') AND Roll_ImpValue < Roll_LandValue * 0.2",
                                  "UseType IN ('Commercial','Industrial') AND Roll_ImpValue < 400000"]),
]


def stage_underused():
    meta = get(PARCEL_URL, params={"f": "json"}, timeout=90).json()
    flds = [f["name"] for f in meta.get("fields", [])]
    areac = next((f for f in flds if re.search(r"shape.*area|starea", f, re.I)), None)
    want = [f for f in ("AIN", "UseCode", "UseType", "UseDescription", "SitusFullAddress", "SitusAddress", "SitusCity", "Roll_LandValue",
                        "Roll_ImpValue", "Roll_LandBaseYear", "TaxRateCity") if f in flds]
    w, s_, e, n = BBOX
    xs, ys = np.linspace(w, e, 5), np.linspace(s_, n, 5)
    tiles = [(xs[i], ys[j], xs[i + 1], ys[j + 1]) for i in range(4) for j in range(4)]
    frames = []
    for kind, wheres in UNDERUSED_QUERIES:
        got = None
        for wh in wheres:
            try:
                parts = []
                for t in tiles:
                    g = arcgis_all(PARCEL_URL, where=wh, fields=",".join(want), bbox=t, max_rows=300000)
                    if g is not None:
                        parts.append(g)
                got = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326) if parts else None
                note("underused", **{f"{kind}_where": wh, f"{kind}_rows": 0 if got is None else len(got)})
                break
            except Exception as ex:  # noqa: BLE001
                note("underused", **{f"{kind}_error_{len(wh)}": str(ex)[:160]})
        if got is None or not len(got):
            continue
        got = got.drop_duplicates("AIN")
        got["kind"] = kind
        frames.append(got)
    g = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326) if frames else None
    if g is None:
        raise RuntimeError("no underused parcels returned")
    g = g.drop_duplicates("AIN", keep="first").to_crs(M)
    g["sqft"] = g.area * 10.7639
    land = pd.to_numeric(g.get("Roll_LandValue"), errors="coerce")
    imp = pd.to_numeric(g.get("Roll_ImpValue"), errors="coerce")
    g["land_av"], g["imp_av"] = land, imp
    minsq = {"parking lot": 10000, "golf course": 43560, "vacant": 21780, "lightly built commercial": 43560}
    g = g[g.sqft >= g.kind.map(minsq)]
    g = g[~((g.kind == "lightly built commercial") & (g.imp_av > 0.2 * g.land_av))]
    addr = g.get("SitusFullAddress", g.get("SitusAddress"))
    out = gpd.GeoDataFrame({"kind": g.kind, "ain": g.AIN.astype(str), "use": g.get("UseDescription"), "addr": addr,
                            "sqft": g.sqft.round(0), "land_av": g.land_av, "imp_av": g.imp_av,
                            "base_year": pd.to_numeric(g.get("Roll_LandBaseYear"), errors="coerce"), "src": "LA County Assessor"},
                           geometry=g.geometry.simplify(1.5), crs=M).to_crs(4326)
    note("underused", sites=len(out), by_kind={k: int(v) for k, v in out.kind.value_counts().items()},
         acres_by_kind={k: round(float(v) / 43560) for k, v in out.groupby("kind").sqft.sum().items()})
    out.to_file(OUT / "map_underused.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    log(f"  wrote map_underused.geojson ({len(out)})")


# ------------------------------------------------------------------ what is already being done (round 7)
APR_CSV = ("https://publish.data.ca.gov/dataset/81b0841f-2802-403e-b48e-2ef4b751f77c/resource/"
           "fe505d9b-8c36-42ba-ba30-08bc4f34e022/download/tablea2.csv")
HE_SCAG = "https://maps.scag.ca.gov/scaggis/rest/services/LDX/HousingElementSite_poly_scag/MapServer/0"
HE_COUNTY = "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/LA_County_Housing_Element_Sites_Inventory/FeatureServer/1"


def _num(x):
    return pd.to_numeric(x, errors="coerce")


BOE_CIP = "https://maps.lacity.org/arcgis/rest/services/Mapping/NavigateLA/MapServer/10"
CCED = "https://gis.cnra.ca.gov/arcgis/rest/services/Boundaries/CCED_AccessType/MapServer/0"


def _write_gz(g, name):
    import gzip
    with gzip.open(OUT / name, "wt") as f:
        f.write(re.sub(r"(-?\d+\.\d{5})\d+", r"\1", g.to_json(drop_id=True, default=str)))
    log(f"  wrote {name} ({len(g)})")


def stage_projects():
    rows = []
    # 1. LA City affordable-housing pipeline (LAHD)
    try:
        df = socrata_rows("data.lacity.org", "mymu-zi3s", "1=1", limit=50000, max_rows=200000)
        note("projects", lahd_rows=len(df), lahd_fields=list(df.columns)[:50])
        lat = _num(df.get("latitude"))
        lon = _num(df.get("longitude"))
        units = next((c for c in df.columns if re.search(r"site_units|total_units|units", c)), None)
        for i in df.index:
            if lat[i] == lat[i] and lon[i] == lon[i]:
                rows.append({"src": "LAHD affordable housing", "kind": "affordable housing", "name": df.get("name", pd.Series(dtype=str)).get(i),
                             "addr": df.get("address", pd.Series(dtype=str)).get(i), "stage": df.get("development_stage", pd.Series(dtype=str)).get(i),
                             "detail": df.get("construction_type", pd.Series(dtype=str)).get(i), "units": _num(pd.Series([df[units][i]]))[0] if units else np.nan,
                             "year": str(df.get("in_service_date", pd.Series(dtype=str)).get(i) or df.get("date_funded", pd.Series(dtype=str)).get(i) or "")[:4],
                             "lat": lat[i], "lon": lon[i]})
    except Exception as e:  # noqa: BLE001
        note("projects", lahd_error=str(e)[:200])
    # 2. LA City new-building permits since 2024 (LADBS)
    try:
        df = socrata_rows("data.lacity.org", "pi9x-tg5x", "permit_type='Bldg-New' AND issue_date >= '2024-01-01T00:00:00'", limit=50000, max_rows=200000)
        note("projects", ladbs_new_rows=len(df), ladbs_fields=list(df.columns)[:50])
        txt = (df.get("permit_sub_type", "").astype(str) + " " + df.get("use_desc", "").astype(str) + " " + df.get("work_desc", "").astype(str)).str.upper()
        kind = np.where(txt.str.contains("ADU|ACCESSORY DWELLING"), "new ADU",
               np.where(txt.str.contains("APARTMENT|MULTI|CONDO|DWELLING UNITS|R-2|R2 "), "new apartments",
               np.where(txt.str.contains("1 OR 2 FAMILY|SINGLE FAMILY|SFD|DWELLING"), "new house", "new building")))
        for i, k in zip(df.index, kind):
            la, lo = _num(pd.Series([df.get("lat", pd.Series(dtype=str)).get(i)]))[0], _num(pd.Series([df.get("lon", pd.Series(dtype=str)).get(i)]))[0]
            if la == la and lo == lo:
                rows.append({"src": "LADBS permit", "kind": k, "name": None, "addr": df.get("primary_address", pd.Series(dtype=str)).get(i),
                             "stage": df.get("status_desc", pd.Series(dtype=str)).get(i), "detail": str(df.get("work_desc", pd.Series(dtype=str)).get(i) or "")[:140],
                             "units": np.nan, "year": str(df.get("issue_date", pd.Series(dtype=str)).get(i) or "")[:4], "lat": la, "lon": lo})
    except Exception as e:  # noqa: BLE001
        note("projects", ladbs_error=str(e)[:200])
    # 3. Statewide housing progress reports (HCD APR table A2): every LA County city's approved, permitted, completed projects
    try:
        path = cached_download(APR_CSV, "hcd_apr_tablea2.csv", 25)
        head = pd.read_csv(path, nrows=0).columns.tolist()
        note("projects", apr_columns=head[:80])
        want = [c for c in head if re.fullmatch(r"(JURIS_NAME|CNTY_NAME|YEAR|PROJECT_NAME|STREET_ADDRESS|STD_ADDRESS|APN|LATITUDE|LONGITUDE|UNIT_CAT|TENURE|"
                                               r"ENT_APPROVE_DT1|BP_ISSUE_DT1|CO_ISSUE_DT1|NO_ENTITLEMENTS|NO_BUILDING_PERMITS|CO_.*INCOME.*)", c, re.I)]
        co_cols = [c for c in want if c.upper().startswith("CO_") and "INCOME" in c.upper()]
        n = 0
        for ch in pd.read_csv(path, usecols=want, chunksize=200000, dtype=str, low_memory=False):
            cn = next((c for c in ch.columns if c.upper() == "CNTY_NAME"), None)
            ch = ch[ch[cn].astype(str).str.upper().str.contains("LOS ANGELES")] if cn else ch.iloc[:0]
            yr = _num(ch[next(c for c in ch.columns if c.upper() == "YEAR")])
            ch = ch[yr >= 2021]
            for _, r in ch.iterrows():
                la, lo = _num(pd.Series([r.get("LATITUDE")]))[0], _num(pd.Series([r.get("LONGITUDE")]))[0]
                if not (la == la and lo == lo and 33.3 < la < 35 and -119.2 < lo < -117.4):
                    continue
                ent, bp = _num(pd.Series([r.get("NO_ENTITLEMENTS")]))[0], _num(pd.Series([r.get("NO_BUILDING_PERMITS")]))[0]
                co = float(pd.to_numeric(r[co_cols], errors="coerce").fillna(0).sum()) if co_cols else np.nan
                stage = "completed" if co == co and co > 0 else "permitted" if bp == bp and bp > 0 else "approved" if ent == ent and ent > 0 else None
                if not stage:
                    continue
                units = co if stage == "completed" else bp if stage == "permitted" else ent
                rows.append({"src": "HCD housing progress report", "kind": f"housing {stage}", "name": r.get("PROJECT_NAME"),
                             "key": f"{r.get('JURIS_NAME')}|{r.get('STD_ADDRESS') or r.get('STREET_ADDRESS') or r.get('APN')}",
                             "addr": f"{r.get('STREET_ADDRESS') or ''}, {str(r.get('JURIS_NAME') or '').title()}", "stage": stage,
                             "detail": f"{r.get('UNIT_CAT') or ''} {r.get('TENURE') or ''}".strip(), "units": units, "year": r.get("YEAR"), "lat": la, "lon": lo})
                n += 1
        note("projects", apr_la_rows=n)
    except Exception as e:  # noqa: BLE001
        note("projects", apr_error=str(e)[:200])
    # 4. LA City Bureau of Engineering capital projects (points, with phase and dates)
    try:
        g = arcgis_all(BOE_CIP, max_rows=60000)
        if g is not None and len(g):
            cols = {c.lower(): c for c in g.columns}
            pick = lambda *ks: next((cols[k.lower()] for k in ks if k.lower() in cols), None)  # noqa: E731
            nm, ph, act, cost = pick("ProjectName", "Project_Name", "NAME", "PROJ_NAME"), pick("CurrentPhaseDescription", "ActivePhase"), pick("ProjectActive"), pick("ConstructionCost")
            end = pick("ConsEndDate", "EndDate")
            g = g[g.geometry.notna()]
            if act:
                g = g[~g[act].astype(str).str.upper().isin(["N", "NO", "FALSE", "0", "INACTIVE"])]
            for _, r in g.iterrows():
                pt = r.geometry.representative_point()
                yr = r.get(end) if end else None
                if isinstance(yr, (int, float)) and yr == yr and yr > 1e11:
                    yr = datetime.fromtimestamp(yr / 1000, timezone.utc).year
                rows.append({"src": "LA City Bureau of Engineering", "kind": "city capital project", "name": r.get(nm) if nm else None,
                             "addr": None, "stage": r.get(ph) if ph else None, "detail": f"construction cost ${float(r.get(cost)):,.0f}" if cost and r.get(cost) == r.get(cost) and r.get(cost) else None,
                             "units": np.nan, "year": str(yr)[:4] if yr else "", "lat": pt.y, "lon": pt.x})
            note("projects", boe_cip_rows=len(g), boe_fields=list(g.columns)[:40])
    except Exception as e:  # noqa: BLE001
        note("projects", boe_cip_error=str(e)[:200])
    if not rows:
        raise RuntimeError("no project feed answered")
    pj = gpd.GeoDataFrame(pd.DataFrame(rows), geometry=gpd.points_from_xy([r["lon"] for r in rows], [r["lat"] for r in rows]), crs=4326)
    pj = pj.drop(columns=["lat", "lon"])
    # a project appears in each year's report: keep it once, at its furthest stage (completed > permitted > approved)
    rank = pj.kind.map({"housing completed": 0, "housing permitted": 1, "housing approved": 2}).fillna(3)
    hcd = pj.src.eq("HCD housing progress report")
    keep = pj[hcd].assign(_r=rank[hcd], _y=pd.to_numeric(pj.year[hcd], errors="coerce")).sort_values(["_r", "_y"], ascending=[True, False]) \
        .drop_duplicates("key").drop(columns=["_r", "_y"])
    pj = gpd.GeoDataFrame(pd.concat([keep, pj[~hcd]], ignore_index=True), crs=4326).drop(columns=["key"], errors="ignore")
    note("projects", total=len(pj), by_kind={k: int(v) for k, v in pj.kind.value_counts().items()})
    _write_gz(pj, "map_projects.geojson.gz")
    # conservation easements (state CCED): parcels that generally can't be built on
    try:
        ce = arcgis_all(CCED, bbox=BBOX, max_rows=20000)
        if ce is not None and len(ce):
            keep = [c for c in ("sitename", "esmthldr", "pubaccess", "gis_acres") if c in ce.columns]
            ce = ce[ce.geom_type.isin(["Polygon", "MultiPolygon"])]
            ce["geometry"] = ce.to_crs(M).geometry.simplify(5).to_crs(4326)
            _write_gz(ce[keep + ["geometry"]], "map_easements.geojson.gz")
            note("projects", easements=len(ce))
    except Exception as e:  # noqa: BLE001
        note("projects", easements_error=str(e)[:200])
    # known sites from the research (golf, LAUSD, surplus land, redevelopments): Census geocoder or parcel number
    try:
        ks = pd.read_csv(RESEARCH.parent / "round7b" / "known_sites.csv", dtype=str).fillna("")
        pts = []
        for _, r in ks.iterrows():
            lat = lon = None
            if r.ain:
                try:
                    q = get(PARCEL_URL + "/query", params={"where": f"AIN='{r.ain}'", "outFields": "AIN", "returnGeometry": "true", "outSR": 4326, "f": "geojson"}, timeout=60, tries=2).json()
                    f = (q.get("features") or [None])[0]
                    if f:
                        from shapely.geometry import shape
                        c = shape(f["geometry"]).representative_point()
                        lat, lon = c.y, c.x
                except Exception:  # noqa: BLE001
                    pass
            if lat is None and r.address:
                try:
                    q = get("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
                            params={"address": r.address, "benchmark": "Public_AR_Current", "format": "json"}, timeout=60, tries=2).json()
                    m = (q.get("result", {}).get("addressMatches") or [None])[0]
                    if m:
                        lat, lon = m["coordinates"]["y"], m["coordinates"]["x"]
                except Exception:  # noqa: BLE001
                    pass
            if lat is not None:
                pts.append({**r.to_dict(), "lat": lat, "lon": lon})
        if pts:
            kd = pd.DataFrame(pts)
            gpd.GeoDataFrame(kd.drop(columns=["lat", "lon"]), geometry=gpd.points_from_xy(kd.lon, kd.lat), crs=4326) \
                .to_file(OUT / "map_known_sites.geojson", driver="GeoJSON")
        note("projects", known_sites=len(ks), known_sites_located=len(pts))
    except Exception as e:  # noqa: BLE001
        note("projects", known_sites_error=str(e)[:200])
    # 4. Housing Element site inventories: parcels each city has already identified for new homes
    frames = []
    for url, src in ((HE_SCAG, "SCAG Housing Element sites"), (HE_COUNTY, "LA County Housing Element sites")):
        try:
            g = arcgis_all(url, bbox=BBOX, max_rows=400000)
            if g is None or not len(g):
                continue
            cols = {c.lower(): c for c in g.columns}
            cty = cols.get("county")
            if cty:
                g = g[g[cty].astype(str).str.contains("Los Angeles|LOS ANGELES|037", regex=True)]
            cap = next((cols[c] for c in ("total_he_capacity", "realistic_capacity") if c in cols), None)
            jur = next((cols[c] for c in ("jurisdiction", "situscity") if c in cols), None)
            frames.append(gpd.GeoDataFrame({"src": src, "juris": g[jur] if jur else None, "capacity": _num(g[cap]) if cap else np.nan,
                                            "geometry": g.geometry}, crs=4326))
            note("projects", **{f"{src}_rows": len(g), f"{src}_fields": list(g.columns)[:40]})
        except Exception as e:  # noqa: BLE001
            note("projects", **{f"{src}_error": str(e)[:200]})
    if frames:
        he = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)
        he = he[he.geometry.notna() & he.geom_type.isin(["Polygon", "MultiPolygon"])]
        he["geometry"] = he.to_crs(M).geometry.simplify(2).to_crs(4326)
        _write_gz(he, "map_he_sites.geojson.gz")
        note("projects", he_sites=len(he), he_capacity=float(he.capacity.sum()))


# ------------------------------------------------------------------ official SB 79 transit stops and zones (SCAG)
SB79_APP = "6a2891fa768646f8a410b1e7d249d8e2"   # SCAG Regional Data Platform experience app (round-7 research, H41)
SB79_PORTALS = ["https://rdp.scag.ca.gov/portal/sharing/rest", "https://www.arcgis.com/sharing/rest"]


def _service_urls(obj, out):
    """Collect every Feature/Map service URL mentioned anywhere in an item's JSON (apps -> web maps -> layers)."""
    if isinstance(obj, dict):
        for v in obj.values():
            _service_urls(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _service_urls(v, out)
    elif isinstance(obj, str) and re.search(r"/(FeatureServer|MapServer)(/\d+)?$", obj):
        out.add(obj)


def stage_sb79():
    urls, items, seen = set(), [SB79_APP], set()
    while items and len(seen) < 25:
        it = items.pop()
        if it in seen:
            continue
        seen.add(it)
        for portal in SB79_PORTALS:
            try:
                data = get(f"{portal}/content/items/{it}/data", params={"f": "json"}, timeout=60, tries=1).json()
            except Exception:  # noqa: BLE001
                continue
            _service_urls(data, urls)
            # web maps / data sources referenced by id
            for m in re.findall(r'"itemId"\s*:\s*"([0-9a-f]{32})"', json.dumps(data)):
                items.append(m)
            break
    for u in _agol_find("SB 79 TOD stops zones tiers", ["79"])[:5]:
        urls.add(u)
    note("sb79", candidate_urls=sorted(urls)[:40], items_read=len(seen))
    frames = []
    for u in sorted(urls):
        if not re.search(r"79|tod|transit", u, re.I):
            continue
        lyrs = [u] if re.search(r"/\d+$", u) else []
        if not lyrs:
            try:
                meta = get(u, params={"f": "json"}, timeout=60, tries=1).json()
                lyrs = [f"{u}/{l['id']}" for l in meta.get("layers", [])]
            except Exception:  # noqa: BLE001
                continue
        for lu in lyrs:
            try:
                g = arcgis_all(lu, bbox=BBOX, max_rows=60000)
                if g is None or not len(g):
                    continue
                g["layer_url"] = lu
                frames.append(g)
                note("sb79", **{f"rows_{len(frames)}": f"{lu}: {len(g)} {list(g.columns)[:25]}"})
            except Exception as e:  # noqa: BLE001
                note("sb79", **{f"err_{len(frames)}": f"{lu}: {e}"[:200]})
    if not frames:
        raise RuntimeError("official SB 79 layer not reachable")
    g = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=4326)
    keep = [c for c in ("CITY", "STOP_NAME", "TRN_MODE", "TRN_LINE", "SB79_TIER", "TIER", "BUFFER", "NAME", "layer_url") if c in g.columns]
    g[keep + ["geometry"]].to_file(OUT / "map_sb79.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    note("sb79", features=len(g), geometry=g.geom_type.value_counts().to_dict())


# ------------------------------------------------------------------ research endpoint check (round 6)
RESEARCH = Path(__file__).resolve().parent.parent / "research" / "round6"


def _probe(url):
    """Schema, count and 3 real records for an ArcGIS layer or Socrata resource; status for anything else."""
    out = {"url": url}
    try:
        if "/resource/" in url and url.endswith(".json"):
            r = get(url, params={"$limit": 3}, timeout=60, tries=1)
            js = r.json() if r is not None else None
            out.update(ok=isinstance(js, list) and len(js) > 0, sample=js[:3] if isinstance(js, list) else str(js)[:300])
            return out
        if "/rest/services/" in url and re.search(r"/(MapServer|FeatureServer|ImageServer)(/\d+)?/?$", url):
            meta = get(url, params={"f": "json"}, timeout=60, tries=1)
            js = meta.json() if meta is not None else {}
            if "error" in js or not js:
                out.update(ok=False, error=str(js.get("error", "no response"))[:300])
                return out
            out.update(name=js.get("name") or js.get("mapName"), geometry=js.get("geometryType"),
                       fields=[f["name"] for f in js.get("fields", [])][:60], max_records=js.get("maxRecordCount"),
                       last_edit=(js.get("editingInfo") or {}).get("lastEditDate"),
                       layers=[f"{l['id']}:{l['name']}" for l in js.get("layers", [])][:80])
            if re.search(r"/\d+/?$", url) and "ImageServer" not in url:
                c = get(url.rstrip("/") + "/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}, timeout=90, tries=1).json()
                q = get(url.rstrip("/") + "/query", params={"where": "1=1", "outFields": "*", "returnGeometry": "false",
                                                           "resultRecordCount": 3, "f": "json"}, timeout=90, tries=1).json()
                out.update(count=c.get("count"), sample=[f["attributes"] for f in q.get("features", [])][:3])
                out["ok"] = bool(out["sample"])
            else:
                out["ok"] = True
            return out
        if "sharing/rest/content/items" in url:
            js = get(url, params={"f": "json"}, timeout=60, tries=1).json()
            out.update(ok="error" not in js, title=js.get("title"), item_url=js.get("url"), type=js.get("type"), owner=js.get("owner"))
            return out
        r = requests_head(url)
        out.update(ok=r[0] == 200, http=r[0], content_type=r[1])
    except Exception as e:  # noqa: BLE001
        out.update(ok=False, error=f"{type(e).__name__}: {e}"[:300])
    return out


def requests_head(url):
    import requests
    r = requests.get(url, headers=bd.UA, timeout=60, stream=True, allow_redirects=True)
    r.close()
    return r.status_code, r.headers.get("content-type")


def stage_research_check():
    eps = json.loads((RESEARCH / "endpoints_to_check.json").read_text())
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda e: {**e, **_probe(e["url"])}, eps))
    ok = sum(1 for r in res if r.get("ok"))
    note("research_check", checked=len(res), ok=ok)
    (OUT / "research_check.json").write_text(json.dumps({"checked_at": STATUS["generated_at"], "results": res}, indent=1, default=str))
    log(f"  {ok}/{len(res)} endpoints answered with data")


# ------------------------------------------------------------------ zoning (what can be built)
ZONING_SOURCES = [  # jurisdiction, layer URL, zone field candidates (first match wins); failures are skipped and logged
    ("Los Angeles", "https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/Zoning/FeatureServer/15", ["ZONE_CMPLT", "ZONING", "Zoning"]),
    ("Unincorporated LA County", "https://arcgis.gis.lacounty.gov/arcgis/rest/services/DRP/Open_Data/MapServer/3", ["ZONE", "ZONING", "Zone"]),
    ("Long Beach", "https://gis.longbeach.gov/arcgis/rest/services/DevelopmentServices/Zoning/MapServer/0", ["ZONE_CODE", "ZONING", "ZONE"]),
    ("Glendale", "https://gis.glendaleca.gov/arcgis/rest/services/Zoning/MapServer/0", ["ZONING", "ZONE"]),
    ("Pasadena", "https://gis.cityofpasadena.net/arcgis/rest/services/Zoning_Map/FeatureServer/0", ["ZONING", "ZONE"]),
    ("Santa Clarita", "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/City_of_Santa_Clarita_Layers/FeatureServer/2", ["NEWCODE", "ZONING_CODE", "ZONING", "ZONE"]),
    ("Lancaster", "https://gis.cityoflancasterca.gov/arcgis/rest/services/Zoning/MapServer/0", ["ZONE_CLASS", "ZONING", "ZONE"]),
    ("Palmdale", "https://gis.cityofpalmdale.org/arcgis/rest/services/Public/Zoning/MapServer/0", ["ZONE", "ZONING"]),
    ("Torrance", "https://gis.torranceca.gov/arcgis/rest/services/Public_Services/Torrance_Zoning/MapServer/0", ["ZONE", "ZONING"]),
    ("Pomona", "https://gis.ci.pomona.ca.us/arcgis/rest/services/Planning/Zoning/MapServer/0", ["ZONE_CODE", "ZONING", "ZONE"]),
    ("Inglewood", "https://gis.cityofinglewood.org/arcgis/rest/services/Planning/Inglewood_Zoning/MapServer/0", ["ZONE", "ZONING"]),
    ("Burbank", "https://gis.burbankca.gov/arcgis/rest/services/Planning/Zoning/MapServer/0", ["ZONE", "ZONING"]),
    ("Carson", "https://gis.carsonca.gov/arcgis/rest/services/Zoning/MapServer/0", ["ZONE_CODE", "ZONING", "ZONE"]),
]


def zone_category(z):
    """Broad use category from a zone code (LA City Chapter 1 / 1A, County Title 22 and common city codes)."""
    raw = str(z).upper().strip()
    if raw.startswith("[") and re.fullmatch(r"(\[[^\]]*\])+", raw):  # LA Chapter 1A: [FORM][USE-DENSITY]
        parts = re.findall(r"\[([^\]]*)\]", raw)
        raw = parts[1] if len(parts) > 1 else parts[0]
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)|^Q|^T|^D(?!X)", "", raw).strip()
    t = t.lstrip("-([ ")
    if not t or t in ("NONE", "NAN"):
        return None
    if re.match(r"^(OS|O-S|PF|PR|P-R|REC|PARK|GW|W-|W$)", t):
        return "open space / public"
    if re.match(r"^(M|MR|I|IL|IG|IH|IP|CM|BP|LM|HI|LI|UI|HJ|HR|M-)", t) and not re.match(r"^(MU|MX|MF|MD|MH)", t):
        return "industrial"
    if re.match(r"^(C|CR|CN|CG|CC|CB|CO|CS|CP|DX|MU|MX|MXD|TOD|NC|B-|CBD|SP|DT|CX)", t):
        return "commercial / mixed use"
    if re.match(r"^(RAS|R ?[2-5]|R-[2-5])", t):
        return "multifamily"
    if re.match(r"^(R ?1|R-1|RS|RE|RA|R-A|RU|RZ|RW1|R1|SF|RL|RR|E-|A-?1|A1|A2|A-2|RVL|RLD|R-7|R-10|R-20|UR1|UR2|NU)", t):
        return "single-family"
    if re.match(r"^(R ?[2-5]|R-[2-5]|RD|RW2|RAS|RM|MF|RMD|RH|MD|HD|R-M|R-3|UR[3-5]|RPD|R-?\d{4})", t):
        return "multifamily"
    if re.match(r"^(P|PB|PK)\b", t):
        return "parking"
    if re.match(r"^A", t):
        return "agricultural"
    return "other"


SCAG_LU = "https://services5.arcgis.com/vYSHcRQuTn4O8o35/arcgis/rest/services/2019_Regional_Land_Use_Information_for_Los_Angeles_County/FeatureServer"


def _scag_zoning():
    """SCAG 2019 parcel land use for LA County: each parcel's city zoning code (fills cities with no live zoning layer)."""
    from concurrent.futures import ThreadPoolExecutor
    try:
        root = get(SCAG_LU, params={"f": "json"}, timeout=60).json()
        lid = (root.get("layers") or [{"id": 0}])[0]["id"]
        url = f"{SCAG_LU}/{lid}"
        meta = get(url, params={"f": "json"}, timeout=60).json()
        flds = [f["name"] for f in meta.get("fields", [])]
        zf = next((f for f in flds if re.search(r"(city|local).*(zn|zon)|^zn_|zoning|^zn", f, re.I) and not re.search(r"scag|desc|_gp|gp_", f, re.I)), None)
        cf = next((f for f in flds if re.search(r"^city|city_name|juris|^cityname", f, re.I)), None)
        af = next((f for f in flds if re.search(r"shape__area|shape_area|acres", f, re.I)), None)
        note("zoning", scag_fields=flds[:60], scag_zone_field=zf, scag_city_field=cf)
        if not zf:
            return None
        page = min(2000, int(meta.get("maxRecordCount") or 1000))
        w, s_, e, n = BBOX
        k = 8
        xs, ys = np.linspace(w, e, k + 1), np.linspace(s_, n, k + 1)
        tiles = [(xs[i], ys[j], xs[i + 1], ys[j + 1]) for i in range(k) for j in range(k)]
        fields = [f for f in (zf, cf, af) if f]

        def fetch(t, depth=0):
            try:
                return _roll_tile(url, fields, t, True, page)
            except Exception:  # noqa: BLE001
                if depth >= 2:
                    return []
                x0, y0, x1, y1 = t
                xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
                return sum((fetch(q, depth + 1) for q in [(x0, y0, xm, ym), (xm, y0, x1, ym), (x0, ym, xm, y1), (xm, ym, x1, y1)]), [])

        rows = []
        with ThreadPoolExecutor(8) as ex:
            for r in ex.map(fetch, tiles):
                rows += r
        df = pd.DataFrame(rows)
        if df.empty or "_lat" not in df:
            return None
        df = df[df[zf].notna() & df["_lat"].notna()]
        g = points_from(df, "_lat", "_lon")
        g["zone"] = g[zf].astype(str).str.strip()
        g["juris"] = g[cf].astype(str).str.title() if cf else "SCAG"
        g["a"] = pd.to_numeric(g[af], errors="coerce").fillna(1) if af else 1.0
        g["cat"] = g.zone.map(zone_category).fillna("other")
        note("zoning", scag_parcels=len(g))
        return g[["zone", "juris", "a", "cat", "geometry"]]
    except Exception as e:  # noqa: BLE001
        note("zoning", scag_error=str(e)[:200])
        return None


def stage_zoning():
    frames, status = [], {}
    for juris, url, zf in ZONING_SOURCES:
        try:
            meta = get(url, params={"f": "json"}, timeout=60, tries=2).json()
            flds = [f["name"] for f in meta.get("fields", [])]
            zc = next((f for f in zf if f in flds), None) or next((f for f in flds if re.search(r"^zon|zone|zoning", f, re.I)), None)
            if not zc:
                status[juris] = f"no zone field in {flds[:20]}"
                continue
            g = arcgis_all(url, fields=zc, bbox=BBOX, max_rows=400000)
            if g is None or not len(g):
                status[juris] = "no features"
                continue
            g = g[g.geometry.notna() & g.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
            g = gpd.GeoDataFrame({"juris": juris, "zone": g[zc].astype(str).str.strip(), "geometry": g.geometry}, crs=4326)
            frames.append(g)
            status[juris] = f"ok: {len(g):,} polygons from {zc}"
        except Exception as e:  # noqa: BLE001
            status[juris] = f"failed: {e}"[:200]
    # official SB 79 transit stops / zones from SCAG, if published as a public layer
    sb79 = None
    for u in _agol_find("SB 79 TOD stops zones", ["79"])[:5]:
        try:
            meta = get(u, params={"f": "json"}, timeout=60).json()
            for l in meta.get("layers", []):
                g = arcgis_all(f"{u.rstrip('/')}/{l['id']}", bbox=BBOX, max_rows=50000)
                if g is not None and len(g):
                    g["layer"] = l["name"]
                    sb79 = g if sb79 is None else pd.concat([sb79, g], ignore_index=True)
            if sb79 is not None:
                note("zoning", sb79_url=u, sb79_features=len(sb79), sb79_fields=list(sb79.columns)[:30])
                break
        except Exception as e:  # noqa: BLE001
            note("zoning", sb79_error=f"{u}: {e}"[:200])
    if sb79 is not None:
        sb79 = gpd.GeoDataFrame(sb79, geometry="geometry", crs=4326)
        keep = [c for c in sb79.columns if c != "geometry" and sb79[c].dtype == object][:6]
        sb79[keep + ["layer", "geometry"]].to_file(OUT / "map_sb79.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    note("zoning", sources=status)
    if not frames:
        raise RuntimeError("no zoning layer answered: " + json.dumps(status)[:500])
    z = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)
    z["cat"] = z.zone.map(zone_category)
    scag = _scag_zoning()
    zm = z.to_crs(M)
    zm["geometry"] = zm.geometry.make_valid().simplify(2)
    zm = zm[zm.geom_type.isin(["Polygon", "MultiPolygon"]) & ~zm.is_empty]
    import gzip
    with gzip.open(OUT / "map_zoning.geojson.gz", "wt") as f:
        f.write(re.sub(r"(-?\d+\.\d{5})\d+", r"\1", zm.to_crs(4326).to_json(drop_id=True)))
    # per block group: share of zoned land by category and the most common zone codes
    bg = block_groups().to_crs(M)[["GEOID", "geometry"]]
    ov = gpd.overlay(zm[["juris", "zone", "cat", "geometry"]], bg, how="intersection", keep_geom_type=True)
    ov["a"] = ov.area
    tot = ov.groupby("GEOID").a.sum()
    shares = ov.pivot_table(index="GEOID", columns="cat", values="a", aggfunc="sum").div(tot, axis=0).round(3)
    shares.columns = ["zshare_" + re.sub(r"\W+", "_", c).strip("_") for c in shares.columns]
    top = ov.groupby(["GEOID", "zone"]).a.sum().reset_index().sort_values("a", ascending=False)
    topz = top.groupby("GEOID").apply(lambda d: "; ".join(f"{z} {a / d.a.sum():.0%}" for z, a in zip(d.zone.head(4), d.a.head(4))))
    jur = ov.groupby("GEOID").juris.agg(lambda s: s.mode().iat[0])
    out = shares.join(topz.rename("zone_top")).join(jur.rename("zone_juris")).join((tot / bg.set_index("GEOID").area).clip(0, 1).rename("zone_coverage"))
    out = out.reindex(bg.GEOID)
    if scag is not None:
        # block groups the official layers don't cover: parcel-based shares from SCAG's 2019 regional dataset
        need = out.index[out.zone_coverage.fillna(0) < 0.2]
        j = gpd.sjoin(scag.to_crs(M), bg[["GEOID", "geometry"]], predicate="within")
        j = j[j.GEOID.isin(need)]
        if len(j):
            w = j.groupby(["GEOID", "cat"]).a.sum()
            sh = (w / j.groupby("GEOID").a.sum()).unstack().round(3)
            sh.columns = ["zshare_" + re.sub(r"\W+", "_", c).strip("_") for c in sh.columns]
            tz = j.groupby(["GEOID", "zone"]).a.sum().reset_index().sort_values("a", ascending=False)
            tops = tz.groupby("GEOID").apply(lambda d: "; ".join(f"{z} {a / d.a.sum():.0%}" for z, a in zip(d.zone.head(4), d.a.head(4))))
            ju = j.groupby("GEOID").juris.agg(lambda s_: s_.mode().iat[0])
            for c in sh.columns:
                if c not in out:
                    out[c] = np.nan
            out.loc[sh.index, sh.columns] = sh
            out.loc[tops.index, "zone_top"] = tops
            out.loc[ju.index, "zone_juris"] = ju + " (SCAG 2019)"
            out.loc[sh.index, "zone_coverage"] = 1.0
            note("zoning", scag_bgs_filled=int(len(sh)))
    save(out.reset_index(), "bg_zoning")
    note("zoning", polygons=len(zm), bgs_covered=int(out.zone_coverage.gt(0.2).sum()),
         categories={k: int(v) for k, v in z.cat.value_counts().items()})


STAGES = {"geo": stage_geo, "osm": stage_osm, "transit": stage_transit, "sales": stage_sales, "crime": stage_crime,
          "requests311": stage_requests311, "crashes": stage_crashes, "trees": stage_trees,
          "parcels": stage_parcels, "assets": stage_assets,
          "tra": stage_tra, "assessed": stage_assessed, "basemap": stage_basemap,
          "research_check": stage_research_check, "zoning": stage_zoning,
          "underused": stage_underused, "projects": stage_projects, "sb79": stage_sb79}


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
