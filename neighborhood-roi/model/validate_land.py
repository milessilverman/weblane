"""Check the underused-land screen against the round-10 test set (research/round10/known_sites_r10.csv).

Positives (redeveloped since 2016) should not be shown as underused; negatives (reported still underused) should be.
Uses the geocoded test sites in data/derived/county_la/map_known_sites.geojson (projects stage) and the model output
web/county_data/underused.json + underused_sites.geojson. Writes research/round10/validation_results.csv.
"""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC, MOD = ROOT / "data" / "derived" / "county_la", ROOT / "web" / "county_data"
M = 3310


def main():
    test = pd.read_csv(ROOT / "research" / "round10" / "known_sites_r10.csv", dtype=str).fillna("")
    ks = gpd.read_file(SRC / "map_known_sites.geojson")
    ks = ks[ks.research_id.isin(test.research_id)].to_crs(M)
    u = json.loads((MOD / "underused.json").read_text())["sites"]
    geo = gpd.read_file(MOD / "underused_sites.geojson").to_crs(M)
    rows = []
    for _, t in test.iterrows():
        exp = "not underused" if t.kind == "redevelopment" else "underused"
        hit = ks[ks.research_id == t.research_id]
        if not len(hit):
            rows.append({**t[["research_id", "name", "address"]].to_dict(), "expected": exp, "located": False, "map_shows": "", "ok": "", "detail": "address not geocoded"})
            continue
        pt = hit.geometry.iloc[0]
        near = geo[geo.distance(pt) <= 60]
        if not len(near):
            shows, detail = "not listed", ""
        else:
            s = u[int(near.assign(d=near.distance(pt)).sort_values("d").iloc[0].sid)]
            shows = "listed as underused" if not s.get("bs") else f"marked {s['bs']}"
            detail = f"{s['k']}, {s['ac']} ac: {s['idea'][:140]}"
        ok = (shows != "listed as underused") if exp == "not underused" else (shows == "listed as underused")
        rows.append({**t[["research_id", "name", "address"]].to_dict(), "expected": exp, "located": True, "map_shows": shows, "ok": ok, "detail": detail})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "research" / "round10" / "validation_results.csv", index=False)
    loc = df[df.located == True]  # noqa: E712
    for exp in ("not underused", "underused"):
        x = loc[loc.expected == exp]
        print(f"{exp:>14}: {int(x.ok.sum())} of {len(x)} located test sites right ({len(df[df.expected == exp])} in the set)")
    print(df[df.located == True][["research_id", "name", "expected", "map_shows"]].to_string())  # noqa: E712


if __name__ == "__main__":
    main()
