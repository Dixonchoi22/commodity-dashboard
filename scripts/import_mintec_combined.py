"""Turn a Mintec "Combined Commodity Data" workbook into data/{slug}/forecast.json.

Layout of the workbook (sheet "Combined Data"): Period | Commodity | Code | Value | Unit,
one row per dated observation of a forward curve. Output matches what extract.py writes
(``{"source":…, "commodities":[{code,label,description,unit,start,end,points[]}]}``) so
build_app_data.py / build_html.py read it unchanged.

    py scripts/import_mintec_combined.py 2026-10 data/2026-10/raw/forecast-mintec-combined.xlsx
"""
import json
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent


def main(slug: str, xlsx: str) -> None:
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
    out = {"source": "Expana (Mintec) forward curves", "commodities": commodities}
    path = ROOT / "data" / slug / "forecast.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"{path}: {len(commodities)} commodities, {sum(len(c['points']) for c in commodities)} points")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
