"""Fetch World Bank Pink Sheet food-related indices (base 2010 = 100).

The World Bank publishes monthly commodity price indices ~5th of every
month with a 1-month lag — fresher than Eurostat's prc_hicp_midx
(which lags ~3-4 months for sub-categories). This complements the
EU/Germany HICP data with global commodity benchmarks that food buyers
care about: Agriculture, Beverages, Food, Oils & Meals, Grains and
"Other Food".

Output: data/{period}/world_bank.json

Usage:
  python scripts/fetch_world_bank.py 2026-04
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent

# World Bank "Commodity Markets Outlook" historical monthly XLSX. The doc-id
# in the URL changes when the WB rebrands the file; if this returns 404,
# scrape https://www.worldbank.org/en/research/commodity-markets to find
# the new "CMO-Historical-Data-Monthly.xlsx" link and update WB_URL.
WB_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
    "related/CMO-Historical-Data-Monthly.xlsx"
)

# Column index in the "Monthly Indices" sheet (0-based) for each series we
# want. Header rows are 5-8 (nested) — verified once and hard-coded here.
SERIES = [
    {"key": "agriculture", "col": 4,  "label": "Agriculture",          "colour": "#84CC16"},
    {"key": "food",        "col": 6,  "label": "Food",                  "colour": "#60A5FA"},
    {"key": "oils_meals",  "col": 7,  "label": "Oils & Meals",          "colour": "#FACC15"},
    {"key": "grains",      "col": 8,  "label": "Grains",                "colour": "#FB923C"},
    {"key": "other_food",  "col": 9,  "label": "Other Food",            "colour": "#A78BFA"},
    {"key": "beverages",   "col": 5,  "label": "Beverages (incl. coffee/cocoa)", "colour": "#F472B6"},
]


def parse_month(token: str) -> str | None:
    """Convert '2026M03' to '2026-03'."""
    if not isinstance(token, str) or "M" not in token:
        return None
    y, m = token.split("M")
    return f"{int(y):04d}-{int(m):02d}"


def pretty_month(ym: str) -> str:
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    y, m = ym.split("-")
    return f"{months[int(m) - 1]} {y}"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/fetch_world_bank.py <period-slug>")
    period = sys.argv[1]
    out_dir = ROOT / "data" / period
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = out_dir / "world_bank_pinksheet.xlsx"

    print(f"Downloading World Bank Pink Sheet ...")
    with urllib.request.urlopen(WB_URL, timeout=60) as r:
        xlsx_path.write_bytes(r.read())

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb["Monthly Indices"]
    rows = list(ws.iter_rows(values_only=True))

    # Read updated stamp from row 3
    updated_label = rows[3][0] if len(rows) > 3 else ""

    # Pull last 13 months for each series (we only show 12 but need 13 for MoM)
    monthly: dict[str, list] = {s["key"]: [] for s in SERIES}
    for r in rows:
        if not r or not r[0]:
            continue
        month = parse_month(str(r[0]))
        if not month:
            continue
        for s in SERIES:
            v = r[s["col"]] if s["col"] < len(r) else None
            if v is None:
                continue
            monthly[s["key"]].append({"month": month, "index": float(v)})

    series_payload = []
    for s in SERIES:
        ms = monthly[s["key"]][-13:]
        if not ms:
            continue
        last_12 = ms[-12:]
        first = last_12[0]["index"]
        last = last_12[-1]["index"]
        prev = ms[-2]["index"] if len(ms) >= 2 else last
        series_payload.append({
            "key": s["key"],
            "label": s["label"],
            "colour": s["colour"],
            "series": [{"month": pretty_month(r["month"]), "index": r["index"]} for r in last_12],
            "latest": {
                "month": pretty_month(last_12[-1]["month"]),
                "index": last,
            },
            "yoy_pct": round((last / first - 1) * 100, 2),
            "mom_pct": round((last / prev - 1) * 100, 2),
        })

    payload = {
        "source": "World Bank Pink Sheet (Commodity Markets) — Monthly Indices",
        "url": "https://www.worldbank.org/en/research/commodity-markets",
        "base_year": "2010 = 100",
        "updated": updated_label,
        "series": series_payload,
    }
    out_path = out_dir / "world_bank.json"
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_path.relative_to(ROOT)}")
    print(f"  source: {updated_label}")
    for s in series_payload:
        print(f"    {s['label']:<32} latest {s['latest']['month']} = {s['latest']['index']:6.2f}  YoY {s['yoy_pct']:+.2f}%")


if __name__ == "__main__":
    main()
