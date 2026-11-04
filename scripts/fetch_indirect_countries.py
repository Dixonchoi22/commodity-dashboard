"""Price series for the other markets on the indirect-inflation screen
-> data/indirect_countries.json

Same six cost topics as the German area (electricity, gas, fuel, cardboard boxes,
PPE & plastic, logistics), but from the public APIs - no key or token needed:

  Eurostat dissemination API   IE DK SE NO NL IT
      prc_hicp_minr   consumer prices (HICP, 2025 = 100): electricity, gas, diesel, petrol
      sts_inppd_m     producer prices, domestic market (2021 = 100): paper / corrugated
                      board, plastics, refined petroleum, electricity & gas supply
      sts_sepp_q      services producer prices (quarterly): warehousing & transport support
  ONS time-series API          UK
      MM23 (CPI), PPI (producer prices), SPPI (services producer prices)  - 2015 = 100

Eurostat does not publish every NACE class for every country. Where the narrow
class is missing the next wider one is used and the label says so; where nothing
exists the series is simply left out. Run:  py scripts/fetch_indirect_countries.py
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "indirect_countries.json"
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
ONS = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/{cdid}/{ds}/data"
UA = {"User-Agent": "commodity-dashboard/1.0"}
SINCE = "2024-01"
SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
EU_COUNTRIES = ["IE", "DK", "SE", "NO", "NL", "IT"]
ORDER = ["UK", "IE", "DK", "SE", "NO", "NL", "IT"]


def get_json(url: str, retries: int = 3) -> dict:
    last = None
    for _ in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.load(r)
        except Exception as e:                      # noqa: BLE001 - retry any transient failure
            last = e
    raise RuntimeError(f"GET failed: {url[:120]} ({last})")


def label(period: str) -> str:
    """'2026-09' -> 'Sep 2026'; '2026-Q2' -> 'Jun 2026' (quarter-end month)."""
    if "-Q" in period:
        y, q = period.split("-Q")
        return f"{SHORT[int(q) * 3 - 1]} {y}"
    y, m = period.split("-")
    return f"{SHORT[int(m) - 1]} {y}"


def eurostat(dataset: str, params: dict) -> dict[tuple, dict[str, float]]:
    """Return {(geo, dim_value): {period: value}} from a JSON-stat response."""
    q = urllib.parse.urlencode({"format": "JSON", **params}, doseq=True)
    d = get_json(EUROSTAT + dataset + "?" + q)
    ids, size = d["id"], d["size"]
    cats = {i: list(d["dimension"][i]["category"]["index"]) for i in ids}
    strides = [1] * len(ids)
    for k in range(len(ids) - 2, -1, -1):
        strides[k] = strides[k + 1] * size[k + 1]
    key_dim = next(i for i in ("coicop18", "nace_r2") if i in ids)
    out: dict[tuple, dict[str, float]] = {}
    for pos, v in d.get("value", {}).items():
        pos = int(pos)
        idx = [(pos // strides[k]) % size[k] for k in range(len(ids))]
        geo = cats["geo"][idx[ids.index("geo")]]
        dim = cats[key_dim][idx[ids.index(key_dim)]]
        per = cats["time"][idx[ids.index("time")]]
        out.setdefault((geo, dim), {})[per] = float(v)
    return out


def ons(cdid: str, dataset: str, freq: str) -> tuple[list[str], list[float]]:
    d = get_json(ONS.format(cdid=cdid.lower(), ds=dataset.lower()))
    rows = d["months"] if freq == "m" else d["quarters"]
    per, val = [], []
    for r in rows:
        try:
            v = float(r["value"])
        except (KeyError, ValueError):
            continue
        parts = r["date"].split()                    # '2026 SEP' or '2026 Q2'
        if freq == "m":
            m = [s.upper() for s in SHORT].index(parts[1][:3].upper()) + 1
            p = f"{parts[0]}-{m:02d}"
        else:
            p = f"{parts[0]}-{parts[1]}"
        if p[:4] >= SINCE[:4]:
            per.append(label(p)); val.append(v)
    return per, val


def main() -> None:
    countries: dict[str, list[dict]] = {c: [] for c in ORDER}

    def add(country, key, topic, lab, basis, freq, table, code, unit, per, val):
        if per and val:
            countries[country].append({"key": key, "topic": topic, "label": lab, "basis": basis,
                "freq": freq, "table": table, "code": code, "unit": unit, "periods": per, "values": val})

    # ---------------- Eurostat ----------------
    print("Eurostat: HICP ...")
    hicp = eurostat("prc_hicp_minr", {"unit": "I25", "geo": EU_COUNTRIES, "sinceTimePeriod": SINCE,
                                      "coicop18": ["CP0451", "CP0452", "CP07221", "CP07222"]})
    HICP = [("el_cpi", "electricity", "Electricity — consumer price (HICP)", "CP0451"),
            ("gas_cpi", "gas", "Gas — consumer price (HICP)", "CP0452"),
            ("petrol_cpi", "fuel", "Petrol at the pump — consumer price (HICP)", "CP07222"),
            ("diesel_cpi", "fuel", "Diesel at the pump — consumer price (HICP)", "CP07221")]
    for g in EU_COUNTRIES:
        for key, topic, lab, code in HICP:
            s = hicp.get((g, code))
            if s:
                ps = sorted(s)
                add(g, key, topic, lab, "cpi", "m", "prc_hicp_minr", code, "2025 = 100", [label(p) for p in ps], [s[p] for p in ps])

    print("Eurostat: producer prices ...")
    want = ["C1721", "C172", "C17", "C222", "C22", "C192", "D351", "D352", "D35"]
    ppi = eurostat("sts_inppd_m", {"unit": "I21", "geo": EU_COUNTRIES, "sinceTimePeriod": SINCE, "nace_r2": want})
    NACE_NAME = {"C1721": "Corrugated board & paper containers", "C172": "Articles of paper & paperboard",
                 "C17": "Paper & paper products", "C222": "Plastic products", "C22": "Rubber & plastic products",
                 "C192": "Refined petroleum products", "D351": "Electricity supply", "D352": "Gas supply",
                 "D35": "Electricity, gas, steam & air-conditioning supply"}
    PRIORITY = [("box", "cardboard", ["C1721", "C172", "C17"]), ("plastic", "ppe_plastic", ["C222", "C22"]),
                ("fuel_ppi", "fuel", ["C192"]), ("el_ppi", "electricity", ["D351", "D35"]), ("gas_ppi", "gas", ["D352", "D35"])]
    for g in EU_COUNTRIES:
        used: set[str] = set()                       # D35 can stand in for both electricity and gas: show it once
        for key, topic, codes in PRIORITY:
            for code in codes:
                s = ppi.get((g, code))
                if s and code in used:
                    break
                if s:
                    used.add(code)
                    ps = sorted(s)
                    add(g, key + "_ppi" if not key.endswith("_ppi") else key, topic, NACE_NAME[code] + " — producer price",
                        "ppi", "m", "sts_inppd_m", code, "2021 = 100", [label(p) for p in ps], [s[p] for p in ps])
                    break

    print("Eurostat: services producer prices ...")
    sppi = eurostat("sts_sepp_q", {"unit": "I21", "geo": EU_COUNTRIES, "sinceTimePeriod": "2024-Q1",
                                   "nace_r2": ["H494", "H52"], "indic_bt": "PRC_PRR"})
    for g in EU_COUNTRIES:
        for code, lab, key in (("H494", "Road freight transport & removals", "road_freight"),
                               ("H52", "Warehousing & transport support services", "warehousing")):
            s = sppi.get((g, code))
            if s:
                ps = sorted(s)
                add(g, key, "logistics", lab + " — producer price", "ppi", "q", "sts_sepp_q", code, "2021 = 100",
                    [label(p) for p in ps], [s[p] for p in ps])

    # ---------------- ONS (UK) ----------------
    print("ONS: UK ...")
    UK = [("el_cpi", "electricity", "Electricity — consumer price (CPI)", "cpi", "m", "D7DT", "MM23"),
          ("gas_cpi", "gas", "Gas — consumer price (CPI)", "cpi", "m", "D7DU", "MM23"),
          ("fuel_cpi", "fuel", "Fuels & lubricants for vehicles — consumer price (CPI)", "cpi", "m", "D7EC", "MM23"),
          ("fuel_ppi", "fuel", "Refined petroleum products — producer price", "ppi", "m", "G323", "PPI"),
          ("box_ppi", "cardboard", "Corrugated board & paper containers — producer price", "ppi", "m", "EVVQ", "PPI"),
          ("plastic_ppi", "ppe_plastic", "Plastic products — producer price", "ppi", "m", "G32D", "PPI"),
          ("road_freight", "logistics", "Road freight transport & removals — producer price", "ppi", "q", "HQDV", "SPPI"),
          ("warehousing", "logistics", "Warehousing & storage — producer price", "ppi", "q", "HQRC", "SPPI")]
    for key, topic, lab, basis, freq, cdid, ds in UK:
        try:
            per, val = ons(cdid, ds, freq)
        except Exception as e:                       # noqa: BLE001
            print(f"  ! ONS {cdid}: {e}")
            continue
        add("UK", key, topic, lab, basis, freq, f"ONS {ds}", cdid, "2015 = 100", per, val)

    payload = {"source": "Eurostat dissemination API (IE DK SE NO NL IT) and ONS time-series API (UK)",
               "countries": [{"code": c, "series": countries[c]} for c in ORDER]}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    for c in ORDER:
        print(f"  {c}: {len(countries[c])} series ->", ", ".join(f"{s['key']}({len(s['values'])})" for s in countries[c]))


if __name__ == "__main__":
    main()
