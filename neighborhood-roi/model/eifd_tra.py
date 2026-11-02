"""EIFD calculator inputs: Assessor roll values and Auditor-Controller tax shares by block group.

Reads data/derived/county_la/:
  bg_assessed.csv     net taxable value per block group (pipeline stage `assessed`)
  bg_tra_av.csv.gz    net taxable value per block group and tax-rate area (TRA)
  raw/af*.gz          Auditor-Controller AB8 apportionment factor files (pipeline stage `tra`)
  raw/boe_tra_districts.csv.gz   BOE list of districts levying in each TRA

Writes web/county_data/eifd.json:
  {"meta": {...}, "tra": {tra: [city, county, other, school]}, "bg": {GEOID: {av, avr, avc, np, ry, sh, t}}}
Shares are fractions of the 1% general levy. "school" includes K-12, community colleges, county
education offices and ERAF, none of which can take part in an EIFD.
"""
import gzip
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "derived" / "county_la"
RAW = SRC / "raw"
OUT = ROOT / "web" / "county_data"

AF49_LINE = re.compile(r"^\s+(?:(\d{5})\s+)?(\d{3})\.(\d{2})\s+(.*?)\s+(\d?\.\d+)\s*$")


def tra_key(x):
    s = re.sub(r"\D", "", str(x).split(".")[0])
    return str(int(s)) if s else None


def classify(acct, sub, name):
    """Agency class from the Auditor-Controller account number.
    001.05 = County General Fund; 1xx.01 / 2xx.01 = a city's general levy (labels may name old RDA project
    areas or an existing EIFD); 400 and up = ERAF, county school services, school and college districts;
    everything else (other County funds, fire, flood, library, lighting, water, sanitation, city lighting/parking
    districts) = other districts."""
    a = int(acct)
    if (acct, sub) == ("001", "05"):
        return "county"
    if 100 <= a < 300 and sub == "01":
        return "city"
    if a >= 400:
        return "school"
    return "other"


def parse_factors():
    """Auditor-Controller AF49 'Modified ATI ratio' report: each agency's share of the annual tax increment
    in every TRA (the ratios an EIFD's Auditor allocation uses). Returns (rows, meta, city name and existing EIFD by TRA)."""
    path = next(RAW.glob("af49__*.gz"))
    rows, tra, fy, prepared = [], None, None, None
    with gzip.open(path, "rt", encoding="latin-1") as f:
        for line in f:
            if fy is None and "MODIFIED ATI" in line:
                fy = (re.search(r"FY\s*(\d{4}-\d{2})", line) or [None, None])[1]
            if prepared is None:
                m = re.search(r"(\d{2}/\d{2}/\d{4})\s*$", line)
                prepared = m.group(1) if m else None
            m = AF49_LINE.match(line)
            if not m:
                continue
            if m.group(1):
                tra = m.group(1)
            rows.append((tra_key(tra), m.group(2), m.group(3), m.group(4).strip(), float(m.group(5))))
    df = pd.DataFrame(rows, columns=["tra", "acct", "sub", "agency", "share"])
    df["cls"] = [classify(a, s_, n) for a, s_, n in zip(df.acct, df["sub"], df.agency)]
    cityname = df[df.cls == "city"].groupby("tra").agency.first()
    eifd = df[df.agency.str.contains(r"EIFD", case=False)].groupby("tra").agency.first()
    meta = {"source": "LA County Auditor-Controller, AF49 Modified ATI Ratio Report", "factor_year": f"FY {fy}" if fy else None,
            "prepared": prepared, "url": "https://auditor.lacounty.gov/property-tax-report-central/", "rows": len(df),
            "tras": int(df.tra.nunique())}
    return df, meta, cityname, eifd


EIFD_NAMES = [(r"W\.? ?CARSON", "West Carson EIFD (County)"), (r"PALMDALE", "Palmdale EIFD"), (r"LA VERNE", "La Verne EIFD"),
              (r"CARSON", "Carson EIFD"), (r"COVINA", "Covina EIFD"), (r"LAKEWOOD", "Lakewood EIFD"), (r"NORWALK", "Norwalk EIFD")]


def eifd_name(label):
    return next((nm for pat, nm in EIFD_NAMES if re.search(pat, label, re.I)), label.title())


def build():
    fac, meta, cityname, eifd_tra = parse_factors()
    piv = fac.pivot_table(index="tra", columns="cls", values="share", aggfunc="sum").reindex(columns=["city", "county", "other", "school"]).fillna(0)
    tot = piv.sum(axis=1)
    meta["tras_zero_total"] = int((tot <= 0).sum())
    piv = piv[tot > 0].div(tot[tot > 0], axis=0)
    meta["tras_with_factors"] = int(len(piv))
    av = pd.read_csv(SRC / "bg_assessed.csv", dtype={"GEOID": str})
    by = pd.read_csv(SRC / "bg_tra_av.csv.gz", dtype={"GEOID": str, "tra": str})
    by["k"] = by.tra.map(tra_key)
    by = by.join(piv, on="k")
    matched = by.city.notna()
    meta["roll_value_matched_share"] = round(float(by.net[matched].sum() / by.net.sum()), 4)
    meta["roll_year"] = int(av.roll_year.dropna().mode().iat[0]) if av.roll_year.notna().any() else None
    meta["county_net_av"] = float(av.av_net.sum())
    bg = {}
    for gid, g in by.groupby("GEOID"):
        m = g[g.city.notna() & (g.net > 0)]
        sh = (m[["city", "county", "other", "school"]].mul(m.net, axis=0).sum() / m.net.sum()).round(4).tolist() if len(m) else None
        top = g.sort_values("net", ascending=False).head(5)
        ex = sorted({eifd_name(eifd_tra[k]) for k in g.k if k in eifd_tra.index})
        bg[gid] = {"sh": sh, "t": [[t, round(float(v))] for t, v in zip(top.tra, top.net)]}
        if ex:
            bg[gid]["x"] = ex
    for r in av.itertuples():
        e = bg.setdefault(r.GEOID, {})
        e.update({"av": round(r.av_net), "avr": round(r.av_net_res), "avc": round(r.av_net_com), "np": int(r.av_parcels),
                  "ry": meta["roll_year"]})
    OUT.mkdir(parents=True, exist_ok=True)
    tra = {k: [round(float(x), 5) for x in v] for k, v in piv.iterrows()}
    (OUT / "eifd.json").write_text(json.dumps({"meta": meta, "tra": tra, "bg": bg}, separators=(",", ":")))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    build()
