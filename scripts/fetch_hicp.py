"""Fetch HICP Food Index data from Eurostat REST API and store as JSON
under data/{period}/hicp_index.json.

Pulls the 12 most recent months of EU27 HICP food index from the
"teicp010 — HICP food" short-term indicator dataset (base 2025=100).
This dataset is published with a ~20-day lag, so the April 2026 report
already has March 2026 data — versus prc_hicp_midx (2015=100 base)
which only carries through Dec 2025.

Usage:
  python scripts/fetch_hicp.py 2026-04
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# teicp010 = HICP - food short-term indicator (2025 = 100). Latest publication.
EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "teicp010?format=JSON&lang=EN&geo=EU27_2020&unit=I25"
    "&sinceTimePeriod=2024-12"
)
# Older series with longer history (2015=100 base) used as a fallback.
FALLBACK_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "prc_hicp_midx?format=JSON&lang=EN&geo=EU27_2020&coicop=CP01&unit=I15"
    "&sinceTimePeriod=2024-01"
)


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


def trailing_twelve(series: list[dict]) -> list[dict]:
    return series[-12:]


def pretty_month(ym: str) -> str:
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    y, m = ym.split("-")
    return f"{months[int(m) - 1]} {y}"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/fetch_hicp.py <period-slug>")
    period = sys.argv[1]
    out_path = ROOT / "data" / period / "hicp_index.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Prefer teicp010 (has the freshest months); fall back to prc_hicp_midx
    # if it ever returns nothing.
    try:
        series, updated = fetch(EUROSTAT_URL)
        base = "2025 = 100"
        source_dataset = "teicp010 (HICP - Food, Short-Term Indicator)"
        source_url = "https://ec.europa.eu/eurostat/databrowser/view/teicp010/default/table?lang=en"
    except Exception:
        series, updated = [], ""
    if not series:
        series, updated = fetch(FALLBACK_URL)
        base = "2015 = 100"
        source_dataset = "prc_hicp_midx (HICP Monthly Index, CP01)"
        source_url = "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx/default/table?lang=en"

    last_12 = [{"month": pretty_month(r["month"]), "index": r["index"]} for r in trailing_twelve(series)]
    first_idx = last_12[0]["index"]
    last_idx = last_12[-1]["index"]
    yoy = (last_idx / first_idx - 1) * 100

    payload = {
        "source": f"Eurostat — {source_dataset}, base {base}",
        "source_dataset": source_dataset,
        "url": source_url,
        "unit": f"Index ({base})",
        "base_year": base,
        "updated": updated,
        "series": last_12,
        "latest_month": last_12[-1]["month"],
        "latest_index": last_idx,
        "yoy_pct_last_12": round(yoy, 2),
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_path.relative_to(ROOT)}")
    print(f"  dataset: {source_dataset} (updated {updated})")
    print(f"  latest : {last_12[-1]['month']} = {last_idx}  (base {base})")
    print(f"  range  : {last_12[0]['month']} -> {last_12[-1]['month']}")


if __name__ == "__main__":
    main()
