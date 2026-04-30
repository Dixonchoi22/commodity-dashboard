"""Parse the Destatis Genesis Online table 61111-0004 export ZIP and
write it as JSON for the dashboard.

Destatis publishes German Verbraucherpreisindex (CPI) ~5–7 days after
month end — much fresher than Eurostat's prc_hicp_midx (which lags
3-4 months for full COICOP detail). The data we want is in:

    Table 61111-0004
    "Consumer price index: Germany, months, individual consumption by
     purpose (COICOP 2-5-digit hierarchy)"

The Destatis Genesis Online API requires a free account, so this
script reads the manually-exported ZIP/CSV that the user drops into
data/{period}/raw/ (filename pattern: 61111-0004*.zip or .csv).

Index base: 2020 = 100 (different from Eurostat's 2015 = 100 — keep
this in mind when comparing levels).

Output: data/{period}/destatis.json

Usage:
  python scripts/fetch_destatis.py 2026-04
"""
from __future__ import annotations

import csv
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_NUM = {n: i + 1 for i, n in enumerate(MONTH_NAMES)}


def find_source(raw_dir: Path) -> Path | None:
    """Find a 61111-0004 export under raw/ — accept either a zip or csv."""
    for p in sorted(raw_dir.glob("61111-0004*.zip")):
        return p
    for p in sorted(raw_dir.glob("61111-0004*.csv")):
        return p
    return None


def read_csv_text(path: Path) -> str:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            csv_member = next((n for n in z.namelist() if n.endswith(".csv")), None)
            if not csv_member:
                raise RuntimeError(f"no CSV inside {path.name}")
            return z.read(csv_member).decode("utf-8-sig")
    return path.read_text(encoding="utf-8-sig")


def parse_header(rows: list[list[str]]) -> tuple[int, list[str]]:
    """Find the data-start row and return (data_start_index, month_columns).

    Destatis CSVs have several preamble rows before the data; the year row
    has '2025'/'2026' tokens, and the next row has month names. Each month
    occupies two columns (value + 'e' estimate flag).
    """
    year_row_idx = month_row_idx = None
    for i, row in enumerate(rows):
        if any(c.strip().isdigit() and 2000 <= int(c.strip()) <= 2100 for c in row):
            year_row_idx = i
            month_row_idx = i + 1
            break
    if year_row_idx is None:
        raise RuntimeError("could not find year header row")

    year_row = rows[year_row_idx]
    month_row = rows[month_row_idx]
    months: list[str] = []
    current_year = None
    for col_idx, cell in enumerate(month_row):
        # Pick up the year for this column from the year row (sparse).
        yr_token = year_row[col_idx].strip() if col_idx < len(year_row) else ""
        if yr_token.isdigit() and 2000 <= int(yr_token) <= 2100:
            current_year = int(yr_token)
        name = cell.strip()
        if name in MONTH_NUM and current_year:
            months.append(f"{current_year:04d}-{MONTH_NUM[name]:02d}")
        else:
            months.append("")
    return month_row_idx + 1, months


def parse_destatis(text: str) -> dict:
    rows = [r for r in csv.reader(text.splitlines(), delimiter=";")]
    data_start, month_cols = parse_header(rows)
    series: list[dict] = []

    for row in rows[data_start:]:
        if len(row) < 3 or not row[0].strip():
            continue
        code_raw = row[0].strip()              # e.g. CC13-01121
        label = row[1].strip()
        # Normalise: drop the "CC13-" prefix → "01121"; convert to Eurostat
        # form "CP01121" so we can join against existing canonical codes.
        m = re.match(r"CC13-?(\d+)", code_raw)
        if not m:
            continue
        digits = m.group(1)
        coicop = "CP" + digits

        # Build a {YYYY-MM: index_value} map from the row
        values: list[tuple[str, float]] = []
        for col_idx, month_str in enumerate(month_cols):
            if not month_str:
                continue
            cell = row[col_idx].strip() if col_idx < len(row) else ""
            if not cell or cell == "...":
                continue
            try:
                v = float(cell.replace(",", "."))
            except ValueError:
                continue
            values.append((month_str, v))
        if not values:
            continue
        values.sort(key=lambda kv: kv[0])

        # Trailing 12 months
        last_12 = values[-12:]
        first_idx = last_12[0][1]
        last_idx = last_12[-1][1]
        prev_idx = values[-2][1] if len(values) >= 2 else last_idx
        yoy = (last_idx / first_idx - 1) * 100 if first_idx else None
        mom = (last_idx / prev_idx - 1) * 100 if prev_idx else None

        # COICOP digits → "depth" (number of digits after CP). 2 = top-level
        # parent (e.g., 01 = Food & beverages), 3 = food (011), 4 = parent
        # category like meat (0112), 5 = sub-type like beef (01121).
        depth = len(digits)

        series.append({
            "coicop": coicop,
            "label": label,
            "depth": depth,
            "series": [
                {"month": pretty_month(m), "index": v} for m, v in last_12
            ],
            "latest": {"month": pretty_month(last_12[-1][0]), "index": last_idx},
            "yoy_pct": round(yoy, 2) if yoy is not None else None,
            "mom_pct": round(mom, 2) if mom is not None else None,
        })

    return {
        "source": "Destatis Genesis Online — table 61111-0004",
        "url": "https://www-genesis.destatis.de/datenbank/online/statistic/61111/table/61111-0004",
        "geo_label": "Germany (DE) — national CPI",
        "base_year": "2020 = 100",
        "series": series,
    }


def pretty_month(ym: str) -> str:
    y, m = ym.split("-")
    short = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    return f"{short[int(m) - 1]} {y}"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/fetch_destatis.py <period-slug>")
    period = sys.argv[1]
    raw_dir = ROOT / "data" / period / "raw"
    source = find_source(raw_dir)
    if not source:
        print("=" * 70)
        print(f"No Destatis export found under {raw_dir.relative_to(ROOT)}/")
        print()
        print("Drop a 61111-0004*.zip (or .csv) export there. Get one from:")
        print("  https://www-genesis.destatis.de/datenbank/online/statistic/61111/table/61111-0004")
        print("  → top-right export → CSV → download the zip → place under raw/.")
        print("=" * 70)
        sys.exit(2)

    print(f"Reading {source.relative_to(ROOT)}")
    text = read_csv_text(source)
    payload = parse_destatis(text)

    out_path = ROOT / "data" / period / "destatis.json"
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_path.relative_to(ROOT)}")
    print(f"  series          : {len(payload['series'])}")
    if payload["series"]:
        latest = payload["series"][0]["latest"]["month"]
        print(f"  latest month    : {latest}")
        print(f"  base year       : {payload['base_year']}")
        # Show top-level Food + a few interesting sub-categories
        print("  spot check:")
        for code in ("CP01", "CP011", "CP0112", "CP01121", "CP01122", "CP0114", "CP01147"):
            s = next((x for x in payload["series"] if x["coicop"] == code), None)
            if s:
                print(f"    {code:<8} {s['label'][:32]:<32}  latest {s['latest']['month']} = {s['latest']['index']:6.2f}  YoY {s['yoy_pct']:+.2f}%")


if __name__ == "__main__":
    main()
