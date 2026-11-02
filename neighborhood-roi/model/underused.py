"""Underused land (parking lots, golf courses, vacant parcels, lightly built commercial lots) and neighborhood profit.

For each site: assessed land value (Assessor roll, a Prop 13 base that is often far below market), an estimated
market land value (from the block group's home values, the same method the model uses for park land), what its
zoning allows, whether it sits near existing or under-construction rail (SB 79 / AB 2097), a rough count of homes it
could hold, and a rough development margin. Then, for each named neighborhood, the total value City Pretty's paying
projects would add net of their cost plus the positive development margins of its underused sites.

Every assumption below is a stated screening input, to be replaced by round-7 research (land sales, construction
costs, rents). Reads data/derived/county_la + web/county_data; writes web/county_data/underused.json.
"""
import json
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC, MOD = ROOT / "data" / "derived" / "county_la", ROOT / "web" / "county_data"
M = 3310

# homes per acre each broad zone allows (typical base zoning; SB 9 doubles single-family lots)
DENSITY = {"single-family": 8, "multifamily": 40, "commercial / mixed use": 60, "parking": 40, "other": 20,
           "industrial": 0, "open space / public": 0, "agricultural": 1}
SB79 = [(402, 100), (805, 60)]          # assumed homes/acre within ¼ and ½ mile of rail (SB 79 tiers vary by station)
# ---- round-7 research inputs (research/round7/partI_profit_inputs.csv); escalation and soft-cost shares are assumptions
HARD_COST_PSF_2023 = (268 + 295 + 334 + 312) / 4   # I16-I19: LA case-study direct construction cost, 2023 basis
ESCALATE_2023_2026 = 1.04 ** 3                      # assumption: 4%/yr construction inflation
SOFT_AND_FINANCE = 0.30                             # assumption: design, permits, financing, developer fee on top of hard cost
FEES_PER_UNIT = 25_000                              # assumption: impact/school/utility fees (LA fee matrix not recovered, I34-I37)
UNIT_SQFT = {"apartment": 850, "house": 1_500}
RENT_2026Q3 = {"studio": 1707, "1br": 2102, "2br": 2680}   # I20-I22: LA average rents, all stock
NEW_RENT_PREMIUM = 1.15                             # assumption: new buildings rent above the all-stock average
OPEX_SHARE = 0.35                                   # assumption: operating costs + vacancy as a share of rent
CAP_RATE = 0.059                                    # I23: LA multifamily cap rate, 2026-Q3
NEW_UNIT_SHARE = 0.6                                # for-sale houses: new house worth ~60% of the area's typical home ...
UNIT_PRICE_RANGE = (350_000, 1_200_000)  # ... within this range
ACTIVE_USE = r"manufactur|mineral|motion picture|nurser|greenhouse|oil|petroleum|refin|quarr|landfill|utilit|cemeter|warehous|lumber|rail"
GOLF_HOUSING_SHARE = 0.10              # golf courses: only the edge (10%) considered for housing, rest kept as open space
ASSUMPTIONS = {
    "density_homes_per_acre": DENSITY, "sb79_homes_per_acre_by_distance_m": SB79,
    "hard_cost_psf_2023 (round 7, I16-I19 avg)": HARD_COST_PSF_2023, "escalation_2023_2026": round(ESCALATE_2023_2026, 3),
    "soft_and_finance_share": SOFT_AND_FINANCE, "fees_per_unit": FEES_PER_UNIT, "unit_sqft": UNIT_SQFT,
    "rents_2026q3 (round 7, I20-I22)": RENT_2026Q3, "new_rent_premium": NEW_RENT_PREMIUM, "opex_share": OPEX_SHARE,
    "cap_rate (round 7, I23)": CAP_RATE, "house_value_share_of_typical_home": NEW_UNIT_SHARE, "house_value_range": UNIT_PRICE_RANGE, "golf_course_share_for_housing": GOLF_HOUSING_SHARE,
    "market_land": "block-group land value per sq ft: 60% of typical home value over its share of land (or the "
                   "Assessor's vacant-land roll value if higher), clipped to $15-$600/sq ft"}


RENT_MED = None


def unit_economics(b, houses):
    """Value and cost of one new home. Apartments: local rent (county average x the area's rent level) -> net income
    / cap rate. Houses: share of the area's typical home value. Cost: escalated LA hard cost + soft costs + fees."""
    if houses:
        price = float(np.clip(float(b.home_value) * NEW_UNIT_SHARE, *UNIT_PRICE_RANGE)) if b.home_value == b.home_value else np.nan
        sqft = UNIT_SQFT["house"]
    else:
        local = float(np.clip((b.median_gross_rent / RENT_MED) if b.median_gross_rent == b.median_gross_rent else 1.0, 0.7, 2.0))
        rent = (RENT_2026Q3["1br"] + RENT_2026Q3["2br"]) / 2 * NEW_RENT_PREMIUM * local
        price = rent * 12 * (1 - OPEX_SHARE) / CAP_RATE
        sqft = UNIT_SQFT["apartment"]
    cost = HARD_COST_PSF_2023 * ESCALATE_2023_2026 * sqft * (1 + SOFT_AND_FINANCE) + FEES_PER_UNIT
    return price, cost


def land_psf(r):
    units_per_acre = max(r.homes / max(r.aland_m2 / 4046.86, 0.1), 0.5) * 1.35
    est = 0.6 * r.home_value * units_per_acre / 43560 if r.home_value == r.home_value else np.nan
    roll = r.vacant_land_psf_median if "vacant_land_psf_median" in r and r.vacant_land_psf_median == r.vacant_land_psf_median else np.nan
    if roll == roll:
        est = max(est, roll) if est == est else roll
    return float(np.clip(est, 15, 600)) if est == est else np.nan


def load_sites():
    parts = []
    p = SRC / "map_underused.geojson"
    if p.exists():
        g = gpd.read_file(p)
        g["name"] = None
        parts.append(g)
    q = SRC / "map_osm_parking.geojson"
    if q.exists():
        o = gpd.read_file(q)
        o = o.assign(kind="parking lot", ain=None, use="Surface parking (mapped in OpenStreetMap)", addr=None,
                     land_av=np.nan, imp_av=np.nan, base_year=np.nan, src="OpenStreetMap")
        # skip OSM lots already covered by an Assessor parking parcel
        if parts:
            a = parts[0][parts[0].kind == "parking lot"].to_crs(M)
            om = o.to_crs(M)
            if len(a):
                inter = gpd.overlay(om[["geometry"]].assign(i=range(len(om))), a[["geometry"]], how="intersection", keep_geom_type=True)
                cov = inter.area.groupby(inter.i).sum().reindex(range(len(om))).fillna(0).values / om.area.values
                o = o[cov < 0.5]
        parts.append(o)
    if not parts:
        return None
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326)
    gm = g.to_crs(M)
    g["acres"] = gm.area / 4046.86
    # stacked parcels (condo / hotel-condo units) share one footprint: merge them and add up their roll values
    c = gm.geometry.centroid
    g["fp"] = (c.x / 5).round().astype("Int64").astype(str) + "_" + (c.y / 5).round().astype("Int64").astype(str) + "_" + g.acres.round(2).astype(str)
    agg = g.groupby("fp").agg(land_av=("land_av", lambda x: x.sum(min_count=1)), imp_av=("imp_av", lambda x: x.sum(min_count=1)), n_ain=("kind", "size"))
    g = g.drop_duplicates("fp").drop(columns=["land_av", "imp_av"]).join(agg, on="fp")
    # "lightly built" must hold for the whole footprint, and big buildings are never underused
    lb = g.kind.eq("lightly built commercial")
    g = g[~(lb & ((g.imp_av > 0.2 * g.land_av) | (g.imp_av >= 2_000_000)))]
    return g[g.acres >= 0.25]


def main():
    global RENT_MED
    d = pd.read_csv(MOD / "bg_scored.csv", dtype={"GEOID": str})
    RENT_MED = float(d.median_gross_rent.median())
    g = load_sites()
    out_sites, bg_sum = [], {}
    if g is not None and len(g):
        bg = gpd.read_file(SRC / "map_block_groups.geojson")[["GEOID", "geometry"]].to_crs(M)
        gm = g.to_crs(M)
        pts = gpd.GeoDataFrame(g.drop(columns="geometry"), geometry=gm.geometry.representative_point(), crs=M)
        pts = gpd.sjoin(pts, bg, predicate="within", how="left").drop(columns="index_right")
        pts = pts[~pts.index.duplicated()]
        # zone at the site: official zoning polygons where loaded, else the block group's dominant category
        zp = SRC / "map_zoning.geojson.gz"
        if zp.exists():
            z = gpd.read_file(f"/vsigzip/{zp}")[["zone", "cat", "geometry"]].to_crs(M)
            zj = gpd.sjoin(pts[["geometry"]], z, predicate="within", how="left")
            zj = zj[~zj.index.duplicated()]
            pts["zone"], pts["zcat"] = zj.zone, zj.cat
        else:
            pts["zone"], pts["zcat"] = None, None
        dd = d.set_index("GEOID")
        zcols = [c for c in d.columns if c.startswith("zshare_")]
        dom = d.set_index("GEOID")[zcols].fillna(-1).idxmax(axis=1).str.replace("zshare_", "").str.replace("_", " ") if zcols else pd.Series(dtype=str)
        dom = dom.replace({"commercial mixed use": "commercial / mixed use", "open space public": "open space / public", "single family": "single-family"})
        pts["zcat"] = pts.zcat.fillna(pts.GEOID.map(dom))
        # rail: existing stations plus stations under construction
        st = []
        for f, tag in (("map_stations.geojson", "open"), ("map_stations_construction.geojson", "coming")):
            if (SRC / f).exists():
                s = gpd.read_file(SRC / f)
                s["status"] = tag
                st.append(s[["name", "status", "geometry"]])
        if st:
            st = gpd.GeoDataFrame(pd.concat(st, ignore_index=True), crs=4326).to_crs(M)
            sj = gpd.sjoin_nearest(pts[["geometry"]], st, how="left", distance_col="rail_m")
            sj = sj[~sj.index.duplicated()]
            pts["rail_m"], pts["station"], pts["st_status"] = sj.rail_m, sj["name"], sj["status"]
        else:
            pts["rail_m"], pts["station"], pts["st_status"] = np.nan, None, None
        # sites a city's Housing Element already lists for new homes (SCAG consolidated + County inventories)
        pts["he_cap"] = np.nan
        if (SRC / "map_he_sites.geojson.gz").exists():
            he = gpd.read_file(f"/vsigzip/{SRC / 'map_he_sites.geojson.gz'}").to_crs(M)
            hj = gpd.sjoin(gpd.GeoDataFrame(geometry=gm.geometry, crs=M), he[["capacity", "geometry"]], predicate="intersects", how="left")
            pts["he_cap"] = hj.groupby(level=0).capacity.sum(min_count=1).reindex(pts.index)
            pts.loc[hj.groupby(level=0).index_right.count().reindex(pts.index).fillna(0).eq(0), "he_cap"] = np.nan
            pts["he_any"] = hj.groupby(level=0).index_right.count().reindex(pts.index).fillna(0) > 0
        else:
            pts["he_any"] = False
        lpsf = {gid: land_psf(r) for gid, r in dd.iterrows()}
        for i, r in pts.iterrows():
            gid = r.GEOID
            if not isinstance(gid, str) or gid not in dd.index:
                continue
            b = dd.loc[gid]
            ac = float(r.acres)
            cat0 = r.zcat if isinstance(r.zcat, str) else "other"
            # active uses that only look "lightly built" on the roll, and airport land, are not underused
            use = str(r.use) if isinstance(r.use, str) else ""
            zone = str(r.zone) if isinstance(r.zone, str) else ""
            if re.match(r"^\(?(LAX|AIRPORT|ARPT)", zone, re.I) or re.search(r"airport", use, re.I):
                continue
            if r.kind == "lightly built commercial" and (ac > 40 or re.search(ACTIVE_USE, use, re.I)):
                continue
            # vacant land counts only inside built-up areas, at an infill scale, and not on open-space/farm zoning
            if r.kind == "vacant" and (not (b.density >= 0.0015) or not (0.5 <= ac <= 25) or cat0 in ("open space / public", "agricultural")):
                continue
            sqft = ac * 43560
            psf = lpsf.get(gid, np.nan)
            lav = float(r.land_av) if r.land_av == r.land_av and r.land_av >= 10_000 else np.nan  # tiny values are common-area parcels
            mkt = sqft * psf if psf == psf else np.nan
            if lav == lav:
                mkt = max(mkt, lav) if mkt == mkt else lav  # market land is never below the Prop 13 assessed value
            cat = r.zcat if isinstance(r.zcat, str) else "other"
            dens = DENSITY.get(cat, 20)
            rail = r.rail_m if r.rail_m == r.rail_m else 1e9
            sb79 = next((v for dist, v in SB79 if rail <= dist), None) if cat in ("single-family", "multifamily", "commercial / mixed use", "parking", "other") else None
            if sb79:
                dens = max(dens, sb79)
            usable = ac * (GOLF_HOUSING_SHARE if r.kind == "golf course" else 1.0)
            homes = int(round(usable * dens))
            houses = cat == "single-family" and not sb79
            price, cost = unit_economics(b, houses)
            land_used = mkt * (GOLF_HOUSING_SHARE if r.kind == "golf course" else 1.0) if mkt == mkt else 0
            margin = homes * (price - cost) - land_used if homes and price == price else np.nan
            if r.kind == "golf course":
                idea = (f"Keep as open space and open it to the public; a {GOLF_HOUSING_SHARE:.0%} edge (~{usable:.0f} acres) could hold ~{homes:,} homes"
                        if homes else "Keep as open space; add public trails and access")
            elif cat == "industrial":
                idea = "Jobs: small-industrial or maker space; housing would need a rezoning"
            elif cat == "open space / public":
                idea = "Public land: park, school field or community facility"
            elif sb79:
                idea = f"Apartments near rail (~{homes:,} homes; SB 79 and AB 2097 apply within ½ mile of {r.station or 'the station'})"
            elif r.kind == "parking lot":
                idea = f"Housing over or in place of the lot (~{homes:,} homes); a pocket park or plaza on part of it"
            elif r.kind == "vacant":
                idea = f"Infill housing (~{homes:,} homes) or a pocket park / community garden if the neighborhood lacks parks"
            else:
                idea = f"Mixed use: shops below, ~{homes:,} homes above"
            site = {"k": r.kind, "nm": r["name"] if isinstance(r.get("name"), str) else None,
                    "ad": r.addr if isinstance(r.addr, str) else None, "use": r.use if isinstance(r.use, str) else None,
                    "ac": round(ac, 2), "lav": None if lav != lav else round(lav),
                    "by": None if r.base_year != r.base_year else int(r.base_year),
                    "mkt": None if mkt != mkt else round(mkt), "z": r.zone if isinstance(r.zone, str) else None, "zc": cat,
                    "rail": None if rail >= 1e9 else round(rail), "st": r.station if isinstance(r.station, str) else None,
                    "sts": r.st_status if isinstance(r.st_status, str) else None, "homes": homes,
                    "margin": None if margin != margin else round(margin), "idea": idea, "gid": gid, "i": int(i),
                    "he": (round(float(r.he_cap)) if r.he_cap == r.he_cap else 0) if bool(r.get("he_any", False)) else None}
            out_sites.append(site)
            s_ = bg_sum.setdefault(gid, {"n": 0, "ac": 0.0, "homes": 0, "margin": 0.0, "mkt": 0.0})
            s_["n"] += 1
            s_["ac"] += ac
            s_["homes"] += homes
            s_["margin"] += max(margin, 0) if margin == margin else 0
            s_["mkt"] += mkt if mkt == mkt else 0
        geo = g.loc[[s["i"] for s in out_sites]].copy()
        geo["sid"] = range(len(geo))
        for k, s in enumerate(out_sites):
            s["i"] = k
        geo[["sid", "kind", "geometry"]].to_file(MOD / "underused_sites.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    # ---- neighborhood profit: paying projects (net of cost) + positive development margins on underused land
    d = d.copy()
    d["hk"] = d.hood.fillna(d.city) + "|" + d.city
    d["net_proj"] = (d.pkg_value.fillna(0) - d.pkg_cost.fillna(0)).clip(lower=0)
    d["land_margin"] = d.GEOID.map(lambda x: bg_sum.get(x, {}).get("margin", 0))
    d["homes_value"] = d.homes.fillna(0) * d.home_value.fillna(0)
    rail_soon = set()
    if (SRC / "map_stations_construction.geojson").exists():
        sc = gpd.read_file(SRC / "map_stations_construction.geojson").to_crs(M)
        bgp = gpd.read_file(SRC / "map_block_groups.geojson")[["GEOID", "geometry"]].to_crs(M)
        bgp["geometry"] = bgp.geometry.representative_point()
        if len(sc):
            j = gpd.sjoin_nearest(bgp, sc[["name", "geometry"]], how="left", distance_col="dist")
            rail_soon = {(gid, nm) for gid, nm, dd_ in zip(j.GEOID, j["name"], j.dist) if dd_ <= 1200}
    soon = {}
    for gid, nm in rail_soon:
        soon.setdefault(gid, nm)
    # work already under way: housing approved / permitted / completed since 2021, affordable pipeline, new-building permits
    way = {}
    if (SRC / "map_projects.geojson.gz").exists():
        pj = gpd.read_file(f"/vsigzip/{SRC / 'map_projects.geojson.gz'}").to_crs(M)
        bgp2 = gpd.read_file(SRC / "map_block_groups.geojson")[["GEOID", "geometry"]].to_crs(M)
        pj = gpd.sjoin(pj, bgp2, predicate="within", how="inner")
        for gid, grp_ in pj.groupby("GEOID"):
            w = way.setdefault(gid, {})
            for k, sub in grp_.groupby("kind"):
                w[k] = [int(len(sub)), int(pd.to_numeric(sub.units, errors="coerce").fillna(0).sum())]
    prof = {}
    d = d.copy()
    for hk, grp in d.groupby("hk"):
        hv = float(grp.homes_value.sum())
        if hv <= 0:
            continue
        a, l_ = float(grp.net_proj.sum()), float(grp.land_margin.sum())
        st_names = sorted({soon[g_] for g_ in grp.GEOID if g_ in soon})
        uw = {}
        for g_ in grp.GEOID:
            for k, (n_, u_) in way.get(g_, {}).items():
                c_ = uw.setdefault(k, [0, 0])
                c_[0] += n_
                c_[1] += u_
        prof[hk] = {"proj": round(a), "land": round(l_), "total": round(a + l_), "pct": round((a + l_) / hv, 4),
                    "per_home": round((a + l_) / max(float(grp.homes.sum()), 1)), "homes": int(grp.homes.sum()),
                    "sites": int(sum(bg_sum.get(g_, {}).get("n", 0) for g_ in grp.GEOID)),
                    "site_homes": int(sum(bg_sum.get(g_, {}).get("homes", 0) for g_ in grp.GEOID)), "soon": st_names, "way": uw}
    bgp_ = {gid: round(float((r.net_proj + r.land_margin) / r.homes_value), 4) for gid, r in d.set_index("GEOID").iterrows()
            if r.homes_value > 0}
    (MOD / "underused.json").write_text(json.dumps({"sites": out_sites, "bg": bg_sum, "profit": prof, "bg_pct": bgp_,
                                                     "soon": soon, "way": way, "assumptions": ASSUMPTIONS}, separators=(",", ":"), default=float))
    ks = pd.Series([s["k"] for s in out_sites]).value_counts().to_dict() if out_sites else {}
    print(f"{len(out_sites):,} underused sites {ks}; {sum(s['homes'] for s in out_sites):,} homes possible; "
          f"{len(prof):,} neighborhoods ranked; {len(soon):,} block groups within 1.2 km of a station under construction")
    top = sorted(prof.items(), key=lambda kv: -kv[1]["total"])[:12]
    for k, v in top:
        print(f"  {k:45s} ${v['total'] / 1e6:8.1f}M  {v['pct']:.1%}  sites {v['sites']}")


if __name__ == "__main__":
    main()
