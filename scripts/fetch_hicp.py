"""Fetch HICP Food Index data from Eurostat REST API and store as JSON
under data/{period}/hicp_index.json.

Pulls the 12 most recent months of EU27 HICP for Food & Non-Alcoholic
Beverages (COICOP = CP01), base 2015=100. Use this alongside the YoY %
xlsx so chart + KPI can show absolute index levels (same series type
as Sep 2025's legacy dashboard).

Usage:
  python scripts/fetch_hicp.py 2026-04
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "prc_hicp_midx?format=JSON&lang=EN&geo=EU27_2020&coicop=CP01&unit=I15"
    "&sinceTimePeriod=2024-01"
)


def fetch() -> list[dict]:
    with urllib.request.urlopen(EUROSTAT_URL, timeout=20) as r:
        data = json.load(r)
    time_cat = data["dimension"]["time"]["category"]
    index_by_month = time_cat["index"]
    values = data["value"]
    out = []
    for month, idx in sorted(index_by_month.items(), key=lambda kv: kv[0]):
        v = values.get(str(idx))
        if v is not None:
            out.append({"month": month, "index": float(v)})
    return out


def trailing_twelve(series: list[dict]) -> list[dict]:
    return series[-12:]


def pretty_month(ym: str) -> str:
    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    y, m = ym.split("-")
    return f"{months[int(m) - 1]} {y}"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/fetch_hicp.py <period-slug>")
    period = sys.argv[1]
    out_path = ROOT / "data" / period / "hicp_index.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    series = fetch()
    last_12 = [{"month": pretty_month(r["month"]), "index": r["index"]} for r in trailing_twelve(series)]

    first_idx = last_12[0]["index"]
    last_idx = last_12[-1]["index"]
    yoy = (last_idx / first_idx - 1) * 100

    payload = {
        "source": "Eurostat — prc_hicp_midx (CP01 Food & non-alcoholic beverages, EU27, base 2015=100)",
        "url": "https://ec.europa.eu/eurostat/databrowser/view/teicp010/default/table?lang=en",
        "unit": "Index (2015 = 100)",
        "series": last_12,
        "latest_month": last_12[-1]["month"],
        "latest_index": last_idx,
        "yoy_pct_last_12": round(yoy, 2),
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_path.relative_to(ROOT)}")
    print(f"  latest: {last_12[-1]['month']} = {last_idx}")
    print(f"  range : {last_12[0]['month']} ({first_idx}) -> {last_12[-1]['month']} ({last_idx})")


if __name__ == "__main__":
    main()
