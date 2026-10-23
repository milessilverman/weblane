"""Rank neighborhood improvements by property value created per dollar spent.

Prototype: reads the evidence library (data/interventions.csv), regional cost
factors and neighborhood inputs, then prints a ranked list per neighborhood.

    python3 model/roi.py [neighborhoods.json] [--optimistic]

Defaults are conservative: the low end of each published effect, and a
distance decay so homes at the edge of a radius gain less than homes next door.
"""
import csv
import json
import math
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
DISCOUNT_RATE = 0.05
HORIZON_YRS = 10
ACRE_SQFT = 43560
CANOPY_TARGET_PCT = 40
# Area-weighted mean of an effect that falls linearly to zero at the radius.
DISTANCE_DECAY = 1 / 3

# Size of one "standard project" for each intervention, in its cost unit.
PROJECT_UNITS = {
    "street_tree": 100,
    "vacant_lot_greening": 20,
    "abandoned_house_fix": 20,
    "blight_demolition": 10,
    "community_garden": 1,
    "pocket_park": 1,
    "green_schoolyard": 1,
    "rail_trail": 1,
    "street_lighting": 50,
    "sidewalk_walkability": 10,
    "brownfield_cleanup": 1,
    "noise_barrier": 1,
    "bid_corridor": 1,
    "power_undergrounding": 1,
}
LINEAR_UNITS = {"rail_trail", "noise_barrier", "power_undergrounding"}
POCKET_PARK_ACRES = 0.25
GARDEN_ACRES = 0.1


def load_interventions():
    with open(DATA / "interventions.csv", newline="") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def load_cost_factors():
    with open(DATA / "regional_cost_factors.csv", newline="") as f:
        return {row["metro"]: float(row["cost_factor"]) for row in csv.DictReader(f)}


def applicability(iid, n):
    """0-1 scale: how much of the published effect this neighborhood can expect."""
    canopy_gap = max(0.0, (CANOPY_TARGET_PCT - n["canopy_pct"]) / CANOPY_TARGET_PCT)
    # Voicu & Been's garden effect is concentrated in the poorest neighborhoods.
    low_income = 1.0 if n["income_ratio_to_metro"] <= 0.6 else max(0.25, 1 - (n["income_ratio_to_metro"] - 0.6) * 1.5)
    vacancy = min(1.0, n["vacancy_rate"] / 0.15) if n["vacancy_rate"] >= 0.05 else 0.0
    rules = {
        "street_tree": canopy_gap * (0.7 + 0.3 * n["heat_index"]),
        "vacant_lot_greening": vacancy,
        "abandoned_house_fix": vacancy * n["crime_index"],
        "blight_demolition": vacancy,
        "community_garden": n["park_gap_share"] * min(1.0, n["vacancy_rate"] / 0.05) * low_income,
        "pocket_park": n["park_gap_share"],
        "green_schoolyard": n["schoolyard_asphalt_share"] * (0.5 * n["park_gap_share"] + 0.5 * n["heat_index"]),
        "rail_trail": 1.0 if n["has_unused_corridor"] else 0.0,
        "street_lighting": n["crime_index"],
        "sidewalk_walkability": max(0.0, (70 - n["walk_score"]) / 70),
        "brownfield_cleanup": 1.0 if n["has_brownfield"] else 0.0,
        "noise_barrier": 1.0 if n["freeway_adjacent"] else 0.0,
        "bid_corridor": 1.0 if n["struggling_main_street"] else 0.0,
        "power_undergrounding": 1.0,
    }
    return rules.get(iid, 0.0)


def homes_affected(iid, row, units, n):
    radius = float(row["radius_ft"])
    if iid in LINEAR_UNITS:
        area_acres = 2 * radius * 5280 * units / ACRE_SQFT
    else:
        circle_acres = math.pi * radius**2 / ACRE_SQFT
        overlap = 1.0 if units == 1 else 0.5  # nearby projects share neighbors
        area_acres = circle_acres * units * overlap
    if iid == "noise_barrier":
        area_acres *= 0.5  # only the side facing the freeway benefits
    return min(n["homes"], area_acres * n["homes_per_acre"])


def pv_annuity(amount, years=HORIZON_YRS, r=DISCOUNT_RATE):
    return amount * (1 - (1 + r) ** -years) / r


def ramp_discount(years_to_effect, r=DISCOUNT_RATE):
    """Buyers capitalize future benefits; value a linear ramp to full effect."""
    if years_to_effect <= 0:
        return 1.0
    yrs = int(math.ceil(years_to_effect))
    return sum((t / yrs) * (1 + r) ** -t for t in range(1, yrs + 1)) / yrs + (1 + r) ** -yrs * 0.5 + 0.5 * (1 - 1 / yrs)


def evaluate(n, interventions, cost_factors, optimistic=False):
    factor = cost_factors.get(n["metro"], 1.0)
    results = []
    for iid, units in PROJECT_UNITS.items():
        row = interventions[iid]
        fit = applicability(iid, n)
        if fit <= 0:
            continue
        low, high = float(row["uplift_pct_low"]), float(row["uplift_pct_high"])
        uplift = ((low + high) / 2 if optimistic else low) / 100
        value = n["median_home_value"]
        if iid == "street_tree":
            # Portland: ~3% to the fronting home (shared by ~2 trees) + ~0.6% to ~2 neighbors.
            gain = units * value * (0.03 * 0.5 + 2 * 0.006)
            homes = units * 2
        else:
            homes = homes_affected(iid, row, units, n)
            gain = homes * value * uplift * DISTANCE_DECAY
        gain *= fit * min(1.0, ramp_discount(float(row["time_to_full_effect_yrs"])))

        unit_cost = (float(row["unit_cost_low_usd"]) + float(row["unit_cost_high_usd"])) / 2
        capex = unit_cost * units * factor
        if iid == "pocket_park":
            capex += POCKET_PARK_ACRES * n["land_value_per_acre"]
        if iid == "community_garden":
            capex += GARDEN_ACRES * n["land_value_per_acre"]
        cost = capex + pv_annuity(float(row["annual_maint_usd"]) * units * factor)

        results.append({
            "id": iid,
            "intervention": row["intervention"],
            "project": f"{units} {row['unit']}{'s' if units > 1 else ''}",
            "homes_affected": round(homes),
            "cost_usd": round(cost),
            "value_created_usd": round(gain),
            "value_per_dollar": round(gain / cost, 2),
            "evidence": row["evidence_strength"],
        })
    return sorted(results, key=lambda r: r["value_per_dollar"], reverse=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    optimistic = "--optimistic" in sys.argv
    path = Path(args[0]) if args else DATA / "example_neighborhoods.json"
    neighborhoods = json.loads(path.read_text())["neighborhoods"]
    interventions = load_interventions()
    cost_factors = load_cost_factors()
    for n in neighborhoods:
        print(f"\n== {n['name']} ({n['metro']}, median ${n['median_home_value']:,}) ==")
        print(f"{'Intervention':48} {'Project':16} {'Cost':>12} {'Value created':>14} {'$/$':>6}  Evidence")
        for r in evaluate(n, interventions, cost_factors, optimistic):
            print(f"{r['intervention'][:48]:48} {r['project'][:16]:16} {r['cost_usd']:>12,} "
                  f"{r['value_created_usd']:>14,} {r['value_per_dollar']:>6}  {r['evidence']}")


if __name__ == "__main__":
    main()
