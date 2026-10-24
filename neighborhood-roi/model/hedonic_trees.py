"""Local calibration: what is a street tree in front of a home worth on the Westside?

Hedonic regression on LA County Assessor recorded sales (single-family):
  log(price) ~ log(sq ft) + beds + baths + age + age² + sale quarter + block fixed effects
               + tree_in_front
Sample: homes with a city-inventoried planting site within 20 m of the parcel center's
nearest street side (tree or vacant site), so "treated" = planted site and
"control" = surveyed empty site on otherwise similar streets.

    python3 model/hedonic_trees.py la_westside
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent.parent
M = 3310


def main(region="la_westside"):
    src = ROOT / "data" / "derived" / f"focus_{region}"
    s = gpd.read_file(src / "sales.geojson")
    cols = {c.lower(): c for c in s.columns}
    s = s.rename(columns={cols[k]: k for k in cols})
    s["price"] = pd.to_numeric(s.saleprice, errors="coerce")
    s["sqft"] = pd.to_numeric(s["size"], errors="coerce")
    s["beds"] = pd.to_numeric(s.bedrooms, errors="coerce")
    s["baths"] = pd.to_numeric(s.bathrooms, errors="coerce")
    yb = pd.to_numeric(s.get("effective_yearbuilt", s.yearbuilt), errors="coerce").where(lambda x: x > 1850, pd.to_numeric(s.yearbuilt, errors="coerce"))
    d = s.saledate
    s["date"] = pd.to_datetime(d, unit="ms", errors="coerce") if np.issubdtype(pd.Series(d).dtype, np.number) else pd.to_datetime(d, errors="coerce")
    s["age"] = s.date.dt.year - yb
    s["q"] = s.date.dt.to_period("Q").astype(str)
    sf = s.usecode.astype(str).str.startswith("01") if "usecode" in s else True
    s = s[sf & s.price.between(200_000, 20_000_000) & s.sqft.between(500, 10_000) & s.age.between(0, 130) & s.date.notna()]
    s = s[s.date >= s.date.max() - pd.Timedelta(days=365 * 6)]
    print(f"{len(s):,} single-family sales {s.date.min():%Y-%m} to {s.date.max():%Y-%m}")

    trees = gpd.read_file(src / "street_trees.geojson").to_crs(M)
    sites = gpd.read_file(src / "vacant_street_sites.geojson").to_crs(M) if (src / "vacant_street_sites.geojson").exists() else gpd.read_file(src / "vacant_planting_sites.geojson").to_crs(M)
    blocks = gpd.read_file(ROOT / "web" / "focus_data" / region / "blocks_scored.geojson").to_crs(M)
    sm = s.to_crs(M)
    sm = gpd.sjoin(sm, blocks[["block_id", "name", "geometry"]], predicate="within").drop(columns="index_right")
    allpts = pd.concat([trees.assign(kind="tree")[["kind", "geometry"]], sites.assign(kind="empty")[["kind", "geometry"]]], ignore_index=True)
    allpts = gpd.GeoDataFrame(allpts, geometry="geometry", crs=M)
    near = gpd.sjoin_nearest(sm[["geometry"]], allpts, max_distance=25, distance_col="dist", how="left")
    near = near[~near.index.duplicated()]
    sm["front"] = near.kind
    sm["trees_50m"] = gpd.sjoin(trees, sm[["geometry"]].assign(geometry=sm.buffer(50)), predicate="within").groupby("index_right").size().reindex(sm.index).fillna(0)
    df = sm[sm.front.notna()].copy()
    df["tree_in_front"] = (df.front == "tree").astype(int)
    df["lp"], df["lsq"] = np.log(df.price), np.log(df.sqft)
    df = df.dropna(subset=["lp", "lsq", "beds", "baths", "age"])
    print(f"{len(df):,} sales with an inventoried site in front ({df.tree_in_front.mean()*100:.0f}% planted)")
    base = "lp ~ lsq + beds + baths + age + I(age**2) + C(q) + C(block_id)"
    out = {"sales": int(len(df)), "share_planted": round(float(df.tree_in_front.mean()), 3),
           "period": f"{df.date.min():%Y-%m} to {df.date.max():%Y-%m}"}
    for name, f in (("tree_in_front", base + " + tree_in_front"), ("trees_within_50m", base + " + trees_50m")):
        m = smf.ols(f, data=df).fit(cov_type="cluster", cov_kwds={"groups": df.block_id})
        term = name if name in m.params else "trees_50m"
        b, se = m.params[term], m.bse[term]
        out[name] = {"pct": round(float(np.expm1(b) * 100), 2), "ci95_pct": [round(float(np.expm1(b - 1.96 * se) * 100), 2), round(float(np.expm1(b + 1.96 * se) * 100), 2)],
                     "p": round(float(m.pvalues[term]), 4), "r2": round(float(m.rsquared), 3)}
        print(name, out[name])
    (ROOT / "data" / f"calibration_trees_{region}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*(sys.argv[1:] or []))
