"""Fetch Germany-specific food market data from Eurostat for a given period.

Two Eurostat datasets are mixed because they cover different ground:
  - teicp010 (HICP - food, short-term indicator, base 2025=100): updated
    monthly with ~20-day lag, so the April 2026 report has March 2026
    figures here.
  - prc_hicp_midx (HICP monthly indices by COICOP, base 2015=100):
    re-published with longer lag (typically Dec n-1 by mid-Feb n) but is
    the only source for fine-grained sub-categories (CP0111 bread, CP0112
    meat, CP0114 dairy, etc.).

Categories covered by sub-category breakdown (prc_hicp_midx):
  CP01    Food and non-alcoholic beverages   (overall)
  CP011   Food                                (food only, no beverages)
  CP0111  Bread and cereals
  CP0112  Meat
  CP0113  Fish and seafood
  CP0114  Milk, cheese and eggs
  CP0115  Oils and fats
  CP0116  Fruit
  CP0117  Vegetables
  CP0118  Sugar, jam, honey, chocolate and confectionery
  CP0119  Food products n.e.c.
  CP012   Non-alcoholic beverages

Output: data/{period}/germany.json

Usage:
  python scripts/fetch_germany.py 2026-04
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRC_HICP = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "prc_hicp_midx?format=JSON&lang=EN"
    "&geo={geo}&coicop={coicop}&unit=I15&sinceTimePeriod=2024-09"
)
TEICP010 = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "teicp010?format=JSON&lang=EN&geo={geo}&unit=I25&sinceTimePeriod=2024-12"
)

CATEGORIES = [
    ("CP01",   "Food & non-alcoholic beverages", "shopping-bag"),
    ("CP011",  "Food",                            "utensils"),
    ("CP0111", "Bread & cereals",                 "wheat"),
    ("CP0112", "Meat",                            "beef"),
    ("CP0113", "Fish & seafood",                  "fish"),
    ("CP0114", "Milk, cheese & eggs",             "milk"),
    ("CP0115", "Oils & fats",                     "droplet"),
    ("CP0116", "Fruit",                           "apple"),
    ("CP0117", "Vegetables",                      "leaf"),
    ("CP0118", "Sugar & confectionery",           "candy"),
    ("CP0119", "Other food products",             "package"),
    ("CP012",  "Non-alcoholic beverages",         "cup-soda"),
]

# Drill-downs — 5-digit COICOP. Each entry maps a parent category to a list
# of (code, label, colour) tuples. Add new groups here to surface deeper
# breakdowns in the dashboard.
PALETTE = [
    "#F87171", "#FB923C", "#FACC15", "#34D399", "#60A5FA",
    "#A78BFA", "#F472B6", "#22D3EE", "#FB7185", "#84CC16",
]

DRILLDOWNS = {
    "CP0111": (
        "Bread & cereals",
        [
            ("CP01111", "Rice"),
            ("CP01112", "Flours & cereals"),
            ("CP01113", "Bread"),
            ("CP01114", "Other bakery products"),
            ("CP01115", "Pizza & quiche"),
            ("CP01116", "Pasta & couscous"),
            ("CP01117", "Breakfast cereals"),
            ("CP01118", "Other cereal products"),
        ],
    ),
    "CP0112": (
        "Meat",
        [
            ("CP01121", "Beef & veal"),
            ("CP01122", "Pork"),
            ("CP01123", "Lamb, mutton & goat"),
            ("CP01124", "Poultry"),
            ("CP01125", "Other meats & offal"),
            ("CP01126", "Delicatessen & prep"),
        ],
    ),
    "CP0113": (
        "Fish & seafood",
        [
            ("CP01131", "Fresh / chilled fish"),
            ("CP01132", "Frozen fish"),
            ("CP01133", "Fresh / chilled seafood"),
            ("CP01134", "Frozen seafood"),
            ("CP01135", "Dried / smoked / salted"),
            ("CP01136", "Other preserved fish"),
        ],
    ),
    "CP0114": (
        "Milk, cheese & eggs",
        [
            ("CP01141", "Whole milk"),
            ("CP01142", "Low-fat milk"),
            ("CP01143", "Preserved milk"),
            ("CP01144", "Yoghurt"),
            ("CP01145", "Cheese & curd"),
            ("CP01146", "Other milk products"),
            ("CP01147", "Eggs"),
        ],
    ),
    "CP0115": (
        "Oils & fats",
        [
            ("CP01151", "Butter"),
            ("CP01152", "Margarine & vegetable fats"),
            ("CP01153", "Olive oil"),
            ("CP01154", "Other edible oils"),
            ("CP01155", "Other animal fats"),
        ],
    ),
    "CP0116": (
        "Fruit",
        [
            ("CP01161", "Fresh / chilled fruit"),
            ("CP01162", "Frozen fruit"),
            ("CP01163", "Dried fruit & nuts"),
            ("CP01164", "Preserved fruit"),
        ],
    ),
    "CP0117": (
        "Vegetables",
        [
            ("CP01171", "Fresh / chilled veg"),
            ("CP01172", "Frozen veg"),
            ("CP01173", "Dried & preserved veg"),
            ("CP01174", "Potatoes"),
            ("CP01175", "Crisps & potato products"),
        ],
    ),
    "CP0118": (
        "Sugar & confectionery",
        [
            ("CP01181", "Sugar"),
            ("CP01182", "Jams, marmalades & honey"),
            ("CP01183", "Confectionery & chocolate"),
            ("CP01184", "Edible ices & ice cream"),
            ("CP01185", "Other confectionery"),
        ],
    ),
    "CP0121": (
        "Coffee, tea & cocoa",
        [
            ("CP01211", "Coffee"),
            ("CP01212", "Tea"),
            ("CP01213", "Cocoa & powdered chocolate"),
        ],
    ),
    "CP0122": (
        "Waters, soft drinks & juices",
        [
            ("CP01221", "Mineral / spring waters"),
            ("CP01222", "Soft drinks"),
            ("CP01223", "Fruit & vegetable juices"),
        ],
    ),
}


def colour_for(idx: int) -> str:
    return PALETTE[idx % len(PALETTE)]


def fetch(url: str) -> tuple[list[dict], str]:
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    time_cat = data["dimension"]["time"]["category"]
    index_by_month = time_cat["index"]
    values = data["value"]
    out = []
    for month, idx in sorted(index_by_month.items(), key=lambda kv: kv[0]):
        v = values.get(str(idx))
        if v is not None:
            out.append({"month": month, "index": float(v)})
    return out, data.get("updated", "")


def pretty_month(ym: str) -> str:
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    y, m = ym.split("-")
    return f"{months[int(m) - 1]} {y}"


def trailing(series, n=12):
    return series[-n:]


def yoy_pct(series):
    if len(series) < 2: return None
    return (series[-1]["index"] / series[0]["index"] - 1) * 100


def mom_pct(series):
    if len(series) < 2: return None
    return (series[-1]["index"] / series[-2]["index"] - 1) * 100


def fetch_food_top(geo: str) -> dict:
    """Top-level Food index from teicp010 (freshest data, base 2025=100)."""
    series_full, updated = fetch(TEICP010.format(geo=geo))
    s = trailing(series_full, 12)
    return {
        "geo": geo,
        "series": [{"month": pretty_month(r["month"]), "index": r["index"]} for r in s],
        "latest": {"month": pretty_month(s[-1]["month"]), "index": s[-1]["index"]},
        "yoy_pct": round(yoy_pct(s), 2) if yoy_pct(s) is not None else None,
        "mom_pct": round(mom_pct(s), 2) if mom_pct(s) is not None else None,
        "base": "2025 = 100",
        "dataset": "teicp010",
        "updated": updated,
    }


def fetch_subcategory(geo: str, coicop: str) -> dict | None:
    """Sub-category index from prc_hicp_midx (base 2015=100, lags more)."""
    try:
        series_full, updated = fetch(PRC_HICP.format(geo=geo, coicop=coicop))
    except Exception as exc:
        return {"error": str(exc)}
    if not series_full:
        return None
    s = trailing(series_full, 12)
    return {
        "series": [{"month": pretty_month(r["month"]), "index": r["index"]} for r in s],
        "latest": {"month": pretty_month(s[-1]["month"]), "index": s[-1]["index"]},
        "yoy_pct": round(yoy_pct(s), 2) if yoy_pct(s) is not None else None,
        "mom_pct": round(mom_pct(s), 2) if mom_pct(s) is not None else None,
        "base": "2015 = 100",
        "dataset": "prc_hicp_midx",
        "updated": updated,
    }


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/fetch_germany.py <period-slug>")
    period = sys.argv[1]
    out_path = ROOT / "data" / period / "germany.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Fetching headline Germany + EU Food index from teicp010 (latest data)...")
    de_top = fetch_food_top("DE")
    eu_top = fetch_food_top("EU27_2020")
    print(f"  Germany latest: {de_top['latest']['month']} = {de_top['latest']['index']} (YoY {de_top['yoy_pct']:+}%)")
    print(f"  EU27   latest: {eu_top['latest']['month']} = {eu_top['latest']['index']} (YoY {eu_top['yoy_pct']:+}%)")

    print("\nFetching Germany sub-categories from prc_hicp_midx (longer lag)...")
    sub = []
    for coicop, label, icon in CATEGORIES:
        item = fetch_subcategory("DE", coicop)
        if not item or "error" in (item or {}):
            print(f"  ! {coicop} {label}: skipped")
            continue
        item["coicop"] = coicop
        item["label"] = label
        item["icon"] = icon
        sub.append(item)
        print(f"  ✓ {coicop:<7} {label:<32} latest {item['latest']['month']} = {item['latest']['index']:<7}  YoY {item['yoy_pct']:+}%")

    print("\nFetching deeper drill-downs...")
    drilldowns = {}
    for parent_code, (parent_label, items) in DRILLDOWNS.items():
        print(f"  -- {parent_code} {parent_label} --")
        children = []
        for idx, (code, label) in enumerate(items):
            entry = fetch_subcategory("DE", code)
            if not entry or "error" in (entry or {}):
                print(f"    ! {code} {label}: skipped")
                continue
            entry["coicop"] = code
            entry["label"] = label
            entry["colour"] = colour_for(idx)
            children.append(entry)
            print(f"    ✓ {code:<8} {label:<28} {entry['latest']['index']:<7} YoY {entry['yoy_pct']:+}%")
        if children:
            drilldowns[parent_code] = {
                "parent_code": parent_code,
                "parent_label": parent_label,
                "items": children,
            }

    payload = {
        "source": "Eurostat (teicp010 short-term indicator + prc_hicp_midx by COICOP)",
        "geo_label": "Germany (DE)",
        "headline": {
            "germany": de_top,
            "eu27": eu_top,
        },
        "subcategories": sub,
        "drilldowns": drilldowns,
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
