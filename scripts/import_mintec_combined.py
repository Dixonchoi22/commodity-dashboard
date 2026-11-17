"""Turn a Mintec "Combined Commodity Data" workbook into data/{slug}/forecast.json.

Layout of the workbook (sheet "Combined Data"): Period | Commodity | Code | Value | Unit,
one row per dated observation of a forward curve. Output matches what extract.py writes
(``{"source":…, "commodities":[{code,label,description,unit,start,end,points[]}]}``) so
build_app_data.py / build_html.py read it unchanged.

    py scripts/import_mintec_combined.py 2026-10 data/2026-10/raw/forecast-mintec-combined.xlsx --carry RSOR,J114 --from 2026-04
"""
import json
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent


def carry_over(commodities: list, codes: list, from_slug: str) -> None:
    """Keep an older Mintec curve for a code the new workbook no longer contains.
    Only points from the new file's first date onwards are kept, and the description says
    which month the curve was made, so the chart footer never passes it off as current."""
    src = json.loads((ROOT / "data" / from_slug / "forecast.json").read_text(encoding="utf-8"))
    first = min(c["start"] for c in commodities)
    have = {c["code"] for c in commodities}
    for c in src["commodities"]:
        if c["code"] in codes and c["code"] not in have:
            pts = [p for p in c["points"] if p["date"] >= first]
            made = c["points"][0]["date"][:7]
            if not pts:
                continue
            c = dict(c, points=pts, start=pts[0]["date"], end=pts[-1]["date"],
                     description=f"{c['description']} (older Mintec curve, made {made}; not in the latest file)",
                     carried_from=from_slug)
            commodities.append(c)
            print(f"carried over {c['code']} from {from_slug}: {len(pts)} points to {c['end']}")


def main(slug: str, xlsx: str, carry: list | None = None, from_slug: str | None = None) -> None:
    ws = openpyxl.load_workbook(xlsx, data_only=True)["Combined Data"]
    series: dict = {}
    for period, name, code, value, unit in ws.iter_rows(min_row=2, max_col=5, values_only=True):
        if period is None or value is None or not code:
            continue
        s = series.setdefault(code, {"description": name, "unit": unit or "", "pts": {}})
        s["pts"][period.date().isoformat()] = value
    commodities = []
    for code, s in series.items():
        pts = [{"date": d, "value": v} for d, v in sorted(s["pts"].items())]
        commodities.append({
            "sheet": "Combined Data", "code": code,
            "label": f"{s['description']} [{code}]", "description": s["description"],
            "unit": s["unit"], "start": pts[0]["date"], "end": pts[-1]["date"], "points": pts,
        })
    if carry and from_slug:
        carry_over(commodities, carry, from_slug)
    out = {"source": "Expana (Mintec) forward curves", "commodities": commodities}
    path = ROOT / "data" / slug / "forecast.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"{path}: {len(commodities)} commodities, {sum(len(c['points']) for c in commodities)} points")


if __name__ == "__main__":
    # optional: --carry RSOR,J114 --from 2026-04
    a = sys.argv
    carry = a[a.index("--carry") + 1].split(",") if "--carry" in a else None
    frm = a[a.index("--from") + 1] if "--from" in a else None
    main(a[1], a[2], carry, frm)
