"""Extract the Destatis CPI annual baselines from the index-tracker workbook
(sheet "CPI Catalogue") into data/{period}/cpi_baselines.json.

Kept: CPI code, English label, the category column (the workbook's parent
group, e.g. "Meat", "Vegetables"), the 2023 / 2024 / 2025 annual averages and the
2026 year-to-date average. Procurement (GMC) mappings, contract thresholds and
everything else in the workbook are deliberately NOT read - the dashboard is a
public site, and the category is shown as a plain grouping label.

The workbook itself is not committed to the repo.

Usage:
  py scripts/extract_cpi_baselines.py 2026-10 path/to/tracker.xlsx
Needs openpyxl (pip install openpyxl).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parent_of(code: str, known: set[str]) -> str | None:
    """Nearest ancestor present in the catalogue: CP0111101100 -> CP01111 -> CP0111 -> CP011."""
    digits = code[2:]
    cand = []
    if len(digits) > 5:
        cand.append(digits[:5])
    for n in range(min(len(digits), 5) - 1, 2, -1):
        cand.append(digits[:n])
    for c in cand:
        if "CP" + c in known and "CP" + c != code:
            return "CP" + c
    return None


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("usage: python scripts/extract_cpi_baselines.py <period-slug> <tracker.xlsx>")
    import openpyxl
    period, xlsx = sys.argv[1], Path(sys.argv[2])
    ws = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)["CPI Catalogue"]
    rows = list(ws.iter_rows(values_only=True))
    hdr_i = next(i for i, r in enumerate(rows) if r and r[2] == "CPI Index Code")
    hdr = rows[hdr_i]
    years = [int(m.group(1)) for c in hdr if c and (m := re.match(r"(\d{4}) Baseline", str(c)))]
    ytd_note = str(rows[1][0] or "")
    out = []
    for r in rows[hdr_i + 1:]:
        if not r or not r[2]:
            continue
        m = re.match(r"CC13-?(\d+)$", str(r[2]).strip())
        if not m:
            continue
        vals = r[5:5 + len(years)]
        ytd = r[5 + len(years)]
        if not isinstance(ytd, (int, float)) or any(not isinstance(v, (int, float)) for v in vals):
            continue
        pm = re.match(r"CC13-?(\d+)$", str(r[0]).strip())
        cat_name = str(r[1]).strip()
        cat_name = {"Oliveoil": "Olive oil"}.get(cat_name, cat_name)
        out.append({"coicop": "CP" + m.group(1), "label": str(r[3]).strip(),
                    "cat": ("CP" + pm.group(1)) if pm else None, "catName": cat_name,
                    "base": [round(float(v), 3) for v in vals], "ytd": round(float(ytd), 3)})
    cats, seen = [], set()
    for x in out:                                  # catalogue order = display order
        if x["cat"] and x["cat"] not in seen:
            seen.add(x["cat"]); cats.append({"code": x["cat"], "name": x["catName"]})
        x.pop("catName")
    known = {x["coicop"] for x in out}
    for x in out:
        x["parent"] = parent_of(x["coicop"], known)
        x["depth"] = len(x["coicop"]) - 2 if len(x["coicop"]) <= 7 else 6
    MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
              "september", "october", "november", "december"]
    mm = re.search(r"January\W+(" + "|".join(MONTHS) + r")", ytd_note, re.I)
    ytd_n = MONTHS.index(mm.group(1).lower()) + 1 if mm else 6 if "H1" in ytd_note else 0
    ytd_year = int(re.search(r"(20\d\d)", ytd_note).group(1)) if re.search(r"(20\d\d)", ytd_note) else 2026
    payload = {
        "source": "Destatis Genesis Online - CPI (2020 = 100), annual averages",
        "years": years, "ytd": {"year": ytd_year, "months": ytd_n}, "categories": cats, "series": out,
    }
    dest = ROOT / "data" / period / "cpi_baselines.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {dest.relative_to(ROOT)}: {len(out)} series, baselines {years}, YTD = first {ytd_n} months of {ytd_year}")


if __name__ == "__main__":
    main()
