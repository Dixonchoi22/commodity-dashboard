"""Germany price series for the indirect-inflation screen -> data/indirect_de.json

Six cost topics, each with the Destatis series behind it:

  electricity   PPI electricity to commercial plants (61241-0006) + CPI households
  gas           PPI natural gas to industry / trade (61241-0006) + CPI natural gas
  fuel          PPI motor gasoline + gas oil (61241-0006) + CPI petrol / diesel
  cardboard     PPI corrugated-board boxes, folding cartons (61241-0006)
  ppe_plastic   PPI safety gloves & headgear (PPE), plastic goods, plastic packaging
  logistics     services PPI, quarterly (61311-0006): road freight, refrigerated
                road freight, warehousing, freight forwarding

CPI series come from the Destatis 61111-0004 pull already in data/{latest}/destatis.json.
PPI series are downloaded from the Genesis API (needs GENESIS_TOKEN); without
--api only the CPI series are rebuilt and the PPI ones already in the file are kept.

Usage:
  GENESIS_TOKEN=... py scripts/fetch_indirect_de.py --api
  py scripts/fetch_indirect_de.py            # CPI series only
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "indirect_de.json"
API = "https://genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
START_YEAR = 2024          # two full years so every 2025+ month has a year-on-year
SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# key, topic, label, source ("cpi" | table code), code, freq
SERIES = [
    ("el_ppi", "electricity", "Electricity — commercial & industrial plants", "61241-0006", "GP19-351113", "m"),
    ("el_cpi", "electricity", "Electricity — households", "cpi", "CP0451", "m"),
    ("gas_ind", "gas", "Natural gas — industry", "61241-0006", "GP19-352223", "m"),
    ("gas_trade", "gas", "Natural gas — trade & commerce", "61241-0006", "GP19-352222", "m"),
    ("gas_cpi", "gas", "Natural gas — households", "cpi", "CP04521", "m"),
    ("petrol_ppi", "fuel", "Motor gasoline — producer price", "61241-0006", "GP19-192021", "m"),
    ("diesel_ppi", "fuel", "Gas oil (diesel) — producer price", "61241-0006", "GP19-192026", "m"),
    ("petrol_cpi", "fuel", "Petrol at the pump", "cpi", "CP07222", "m"),
    ("diesel_cpi", "fuel", "Diesel at the pump", "cpi", "CP07221", "m"),
    ("box_corr", "cardboard", "Boxes & cartons of corrugated board", "61241-0006", "GP19-172113", "m"),
    ("box_fold", "cardboard", "Folding cartons (paper / board)", "61241-0006", "GP19-172114", "m"),
    ("ppe", "ppe_plastic", "Safety gloves & safety headgear (PPE)", "61241-0006", "GP19-329911", "m"),
    ("plastic_goods", "ppe_plastic", "Other plastic goods", "61241-0006", "GP19-2229", "m"),
    ("plastic_pack", "ppe_plastic", "Plastic packaging", "61241-0006", "GP19-2222", "m"),
    ("road_freight", "logistics", "Road freight transport", "61311-0006", "CPA08-4941", "q"),
    ("cold_freight", "logistics", "Road freight — refrigerated vehicles", "61311-0006", "CPA08-494111", "q"),
    ("warehousing", "logistics", "Warehousing", "61311-0006", "CPA08-5210", "q"),
    ("forwarding", "logistics", "Freight forwarding", "61311-0006", "CPA08-52291", "q"),
]
TOPICS = ["electricity", "gas", "fuel", "cardboard", "ppe_plastic", "logistics"]


def fnum(s: str):
    s = (s or "").strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def download(table: str, token: str) -> list[dict]:
    body = urllib.parse.urlencode({
        "name": table, "area": "all", "format": "ffcsv", "language": "en",
        "compress": "false", "job": "false", "startyear": str(START_YEAR),
    }).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "username": token, "password": "", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"Genesis API HTTP {e.code} for {table}")
    if not raw.startswith(b"PK"):
        sys.exit(f"Genesis API did not return a zip for {table}: {raw[:200]!r}")
    z = zipfile.ZipFile(io.BytesIO(raw))
    text = z.read(z.namelist()[0]).decode("utf-8-sig")
    return list(csv.DictReader(text.splitlines(), delimiter=";"))


def extract(rows: list[dict], codes: dict[str, str], freq: str) -> dict[str, dict]:
    """codes: {code: key}. Returns {key: {"unit": str, "points": {(year, n): value}}}."""
    out: dict[str, dict] = {}
    for r in rows:
        key = codes.get((r.get("3_variable_attribute_code") or "").strip())
        if not key:
            continue
        per = (r.get("1_variable_attribute_code") or "").strip()
        digits = "".join(ch for ch in per if ch.isdigit())
        if not digits or not r.get("time", "").strip().isdigit():
            continue
        v = fnum(r.get("value", ""))
        if v is None:
            continue
        n = int(digits)
        if (freq == "m" and not 1 <= n <= 12) or (freq == "q" and not 1 <= n <= 4):
            continue
        slot = out.setdefault(key, {"unit": (r.get("value_unit") or "").strip(), "points": {}})
        slot["points"][(int(r["time"]), n)] = v
    return out


def label(year: int, n: int, freq: str) -> str:
    m = n if freq == "m" else n * 3          # quarter -> its last month
    return f"{SHORT[m - 1]} {year}"


def load_cpi() -> dict[str, dict]:
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    for rep in manifest["reports"]:
        p = ROOT / "data" / rep["slug"] / "destatis.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            return {s["coicop"]: s for s in d["series"]}
    return {}


def main() -> None:
    use_api = "--api" in sys.argv[1:]
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"series": []}
    prev_by_key = {s["key"]: s for s in prev.get("series", [])}
    cpi = load_cpi()
    fetched: dict[str, dict] = {}
    if use_api:
        token = os.environ.get("GENESIS_TOKEN", "").strip()
        if not token:
            sys.exit("GENESIS_TOKEN is not set.")
        for table, freq in (("61241-0006", "m"), ("61311-0006", "q")):
            codes = {c: k for k, _t, _l, tb, c, f in SERIES if tb == table}
            print(f"Downloading {table} ...")
            fetched.update(extract(download(table, token), codes, freq))

    series = []
    for key, topic, lab, src, code, freq in SERIES:
        base = {"key": key, "topic": topic, "label": lab, "freq": freq,
                "basis": "cpi" if src == "cpi" else "ppi", "table": "61111-0004" if src == "cpi" else src, "code": code}
        if src == "cpi":
            s = cpi.get(code)
            if not s or not s.get("history"):
                print(f"  ! CPI {code} missing from destatis.json"); continue
            base.update(unit="2020 = 100", periods=[p["month"] for p in s["history"]],
                        values=[p["index"] for p in s["history"]])
        elif key in fetched and fetched[key]["points"]:
            pts = sorted(fetched[key]["points"].items())
            unit = fetched[key]["unit"].replace("=", " = ") or "2021 = 100"
            base.update(unit=unit, periods=[label(y, n, freq) for (y, n), _ in pts], values=[v for _, v in pts])
        elif key in prev_by_key:
            base.update({k: prev_by_key[key][k] for k in ("unit", "periods", "values")})
        else:
            print(f"  ! no data for {key} ({code})"); continue
        series.append(base)

    payload = {"source": "Destatis Genesis Online - producer, services and consumer price indices",
               "topics": TOPICS, "series": series}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(series)} series")
    for s in series:
        print(f"  {s['key']:<14} {s['basis']}  {len(s['values']):>3} pts  latest {s['periods'][-1]} = {s['values'][-1]}")


if __name__ == "__main__":
    main()
