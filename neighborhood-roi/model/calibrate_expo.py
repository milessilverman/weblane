"""Local calibration: did the Expo Line Phase 2 (opened May 2016) lift nearby home prices?

Difference-in-differences on FHFA tract price indexes:
  treated  = tracts whose center is within 800 m of a Phase 2 station
  control  = tracts 1.5-3 km from any Expo station (same Westside market)
  effect   = (post growth - pre growth) treated minus the same for control

    python3 model/calibrate_expo.py
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data" / "derived"
PHASE2 = ["Palms", "Westwood/Rancho Park", "Expo/Sepulveda", "Expo/Bundy", "26th Street/Bergamot", "17th Street/SMC",
          "Downtown Santa Monica"]
ALL_EXPO = PHASE2 + ["Culver City", "La Cienega/Jefferson", "Expo/La Brea", "Farmdale"]


def main():
    st = gpd.read_file(D / "focus_la_westside" / "osm_stations.geojson")
    st = st[st.geom_type == "Point"]
    st["nm"] = st["name"].fillna("")
    p2 = st[st.nm.isin(PHASE2)].drop_duplicates("nm")
    allx = st[st.nm.isin(ALL_EXPO)].drop_duplicates("nm")
    print("phase 2 stations found:", sorted(p2.nm))
    # FHFA tract indexes use 2010 tract IDs; use 2010 shapes when the pipeline has them
    m = pd.read_csv(D / "stage_fhfa.csv", dtype={"GEOID": str}, usecols=["GEOID", "hpi_series"])
    shapes = D / "tracts_2010.geojson" if (D / "tracts_2010.geojson").exists() else D / "tracts.geojson"
    print("tract shapes:", shapes.name)
    tr = gpd.read_file(shapes).merge(m, on="GEOID")
    tr = tr.to_crs(3310)
    c = tr.geometry.representative_point()
    d2 = c.apply(lambda p: p2.to_crs(3310).distance(p).min())
    dall = c.apply(lambda p: allx.to_crs(3310).distance(p).min())
    tr["group"] = np.where(d2 <= 1000, "treated", np.where((dall >= 1500) & (dall <= 3000), "control", None))
    tr = tr[tr.group.notna()]

    def growth(s, a, b):
        s = json.loads(s)
        va, vb = s.get(str(a)), s.get(str(b))
        return np.nan if not va or not vb else np.log(vb / va)

    tr["pre"] = tr.hpi_series.apply(lambda s: growth(s, 2010, 2015))     # construction years, before opening
    tr["post"] = tr.hpi_series.apply(lambda s: growth(s, 2015, 2019))    # opening May 2016 to pre-COVID
    tr = tr.dropna(subset=["pre", "post"])
    g = tr.groupby("group")[["pre", "post"]].agg(["mean", "count"])
    print(g)
    did = (tr[tr.group == "treated"].post.mean() - tr[tr.group == "treated"].pre.mean() * 4 / 5) - \
          (tr[tr.group == "control"].post.mean() - tr[tr.group == "control"].pre.mean() * 4 / 5)
    simple = tr[tr.group == "treated"].post.mean() - tr[tr.group == "control"].post.mean()
    # bootstrap CI on the simple post-period difference
    rng = np.random.default_rng(0)
    t, c_ = tr[tr.group == "treated"].post.values, tr[tr.group == "control"].post.values
    boots = [rng.choice(t, len(t)).mean() - rng.choice(c_, len(c_)).mean() for _ in range(2000)]
    lo, hi = np.percentile(boots, [5, 95])
    out = {"treated_tracts": int((tr.group == "treated").sum()), "control_tracts": int((tr.group == "control").sum()),
           "post_2015_2019_log_growth_gap": round(float(simple), 4), "gap_pct": round(float(np.expm1(simple) * 100), 1),
           "gap_90ci_pct": [round(float(np.expm1(lo) * 100), 1), round(float(np.expm1(hi) * 100), 1)],
           "trend_adjusted_did_pct": round(float(np.expm1(did) * 100), 1), "stations": sorted(p2.nm)}
    print(json.dumps(out, indent=1))
    (ROOT / "data" / "calibration_expo.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
