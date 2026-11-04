"""Price series for the other markets on the indirect-inflation screen
-> data/indirect_countries.json

Same six cost topics as the German area (electricity, gas, fuel, cardboard boxes,
PPE & plastic, logistics), but from the public APIs - no key or token needed:

  Eurostat dissemination API   IE DK SE NO NL IT
      prc_hicp_minr   consumer prices (HICP, 2025 = 100): electricity, gas, diesel, petrol
      sts_inppd_m     producer prices, domestic market (2021 = 100): paper / corrugated
                      board, plastics, refined petroleum, electricity & gas supply
      sts_sepp_q      services producer prices (quarterly): warehousing & transport support
      lc_lci_r2_q     hourly labour cost index (quarterly): accommodation & food, whole economy
      nrg_pc_205/203  electricity and gas prices for non-household (business) users, half-yearly
  ECB data API                 DKK / GBP / NOK / SEK per euro, monthly average
  ONS time-series API          UK
      MM23 (CPI), PPI (producer prices), SPPI (services producer prices)  - 2015 = 100
      EMP (average weekly earnings: accommodation & food services, whole economy)

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
ONS = "https://www.ons.gov.uk/{path}/timeseries/{cdid}/{ds}/data"
ECB = "https://data-api.ecb.europa.eu/service/data/EXR/M.{ccy}.EUR.SP00.A?format=jsondata&startPeriod=2024-01"
INFL = "economy/inflationandpriceindices"
EARN = "employmentandlabourmarket/peopleinwork/earningsandworkinghours"
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
    """'2026-09' -> 'Sep 2026'; '2026-Q2' -> 'Jun 2026' (quarter-end); '2026-S1' -> 'Jun 2026' (half-year end)."""
    if "-S" in period:
        y, h = period.split("-S")
        return f"{SHORT[int(h) * 6 - 1]} {y}"
    if "-Q" in period:
        y, q = period.split("-Q")
        return f"{SHORT[int(q) * 3 - 1]} {y}"
    y, m = period.split("-")
    return f"{SHORT[int(m) - 1]} {y}"


def eurostat(dataset: str, params: dict, dims: tuple[str, ...] | None = None) -> dict[tuple, dict[str, float]]:
    """Return {(geo, *dim_values): {period: value}} from a JSON-stat response."""
    q = urllib.parse.urlencode({"format": "JSON", **params}, doseq=True)
    d = get_json(EUROSTAT + dataset + "?" + q)
    ids, size = d["id"], d["size"]
    cats = {i: list(d["dimension"][i]["category"]["index"]) for i in ids}
    strides = [1] * len(ids)
    for k in range(len(ids) - 2, -1, -1):
        strides[k] = strides[k + 1] * size[k + 1]
    if dims is None:
        dims = (next(i for i in ("coicop18", "nace_r2") if i in ids),)
    out: dict[tuple, dict[str, float]] = {}
    for pos, v in d.get("value", {}).items():
        pos = int(pos)
        idx = [(pos // strides[k]) % size[k] for k in range(len(ids))]
        geo = cats["geo"][idx[ids.index("geo")]]
        dim = tuple(cats[k][idx[ids.index(k)]] for k in dims)
        per = cats["time"][idx[ids.index("time")]]
        out.setdefault((geo, *dim), {})[per] = float(v)
    return out


def ecb_fx(ccy: str) -> tuple[list[str], list[float]]:
    d = get_json(ECB.format(ccy=ccy))
    obs = next(iter(d["dataSets"][0]["series"].values()))["observations"]
    times = [v["id"] for v in d["structure"]["dimensions"]["observation"][0]["values"]]
    per = [label(times[int(i)]) for i in sorted(obs, key=int)]
    val = [float(obs[i][0]) for i in sorted(obs, key=int)]
    return per, val


def ons(cdid: str, dataset: str, freq: str, path: str = INFL) -> tuple[list[str], list[float]]:
    d = get_json(ONS.format(path=path, cdid=cdid.lower(), ds=dataset.lower()))
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
    countries: dict[str, list[dict]] = {c: [] for c in ["DE"] + ORDER}

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

    # ---------------- labour cost, business energy, FX ----------------
    ALL = ["DE"] + EU_COUNTRIES
    print("Eurostat: labour cost index ...")
    lci = eurostat("lc_lci_r2_q", {"unit": "I20", "geo": ALL, "lcstruct": "D1_D4_MD5", "s_adj": ["SCA", "NSA"],
                                   "nace_r2": ["I", "G-N", "B-S"], "sinceTimePeriod": "2024-Q1"}, dims=("nace_r2", "s_adj"))
    for g in ALL:
        for key, topic, codes, lab in (("lab_acc", "labour", ["I", "G-N"], "Hourly labour cost — accommodation & food services"),
                                       ("lab_all", "labour", ["B-S"], "Hourly labour cost — whole business economy")):
            for code in codes:
                hit = next(((code, a) for a in ("SCA", "NSA") if lci.get((g, code, a))), None)
                if hit:
                    s_ = lci[(g, *hit)]
                    ps = sorted(s_)
                    name = lab if code != "G-N" else "Hourly labour cost — trade, transport, accommodation & services"
                    add(g, key, topic, name + ("" if hit[1] == "SCA" else " (not seasonally adjusted)"), "lci", "q",
                        "lc_lci_r2_q", code, "2020 = 100", [label(p) for p in ps], [s_[p] for p in ps])
                    break

    print("Eurostat: business energy prices ...")
    el = eurostat("nrg_pc_205", {"geo": ALL, "nrg_cons": "MWH500-1999", "tax": "X_VAT", "currency": "EUR",
                                 "sinceTimePeriod": "2024-S1"}, dims=())
    gas = eurostat("nrg_pc_203", {"geo": ALL, "nrg_cons": "GJ1000-9999", "tax": "X_VAT", "currency": "EUR",
                                  "unit": "KWH", "sinceTimePeriod": "2024-S1"}, dims=())
    for g in ALL:
        for key, topic, data, lab, tb, code in (
                ("el_bus", "electricity", el, "Electricity — business users, 500–1,999 MWh/yr, excl. VAT", "nrg_pc_205", "MWH500-1999"),
                ("gas_bus", "gas", gas, "Natural gas — business users, 1,000–9,999 GJ/yr, excl. VAT", "nrg_pc_203", "GJ1000-9999")):
            s_ = data.get((g,))
            if s_:
                ps = sorted(s_)
                add(g, key, topic, lab, "bus", "s", tb, code, "EUR/kWh", [label(p) for p in ps], [s_[p] for p in ps])

    print("ECB: exchange rates ...")
    for g, ccy in (("UK", "GBP"), ("DK", "DKK"), ("SE", "SEK"), ("NO", "NOK")):
        try:
            per, val = ecb_fx(ccy)
        except Exception as e:                       # noqa: BLE001
            print(f"  ! ECB {ccy}: {e}")
            continue
        add(g, "fx", "fx", f"{ccy} per 1 EUR — monthly average", "fx", "m", "ECB EXR", f"EUR/{ccy}", f"{ccy} per EUR", per, val)

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
    UK += [("lab_acc", "labour", "Average weekly earnings — accommodation & food services (total pay)", "lci", "m", "K5B6", "EMP"),
           ("lab_all", "labour", "Average weekly earnings — whole economy (total pay)", "lci", "m", "KA5Q", "EMP")]
    for key, topic, lab, basis, freq, cdid, ds in UK:
        try:
            per, val = ons(cdid, ds, freq, EARN if ds == "EMP" else INFL)
        except Exception as e:                       # noqa: BLE001
            print(f"  ! ONS {cdid}: {e}")
            continue
        add("UK", key, topic, lab, basis, freq, f"ONS {ds}", cdid, "2015 = 100", per, val)

    payload = {"source": "Eurostat dissemination API (IE DK SE NO NL IT) and ONS time-series API (UK)",
               "countries": [{"code": c, "series": countries[c]} for c in ["DE"] + ORDER]}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    for c in ["DE"] + ORDER:
        print(f"  {c}: {len(countries[c])} series ->", ", ".join(f"{s['key']}({len(s['values'])})" for s in countries[c]))


if __name__ == "__main__":
    main()
