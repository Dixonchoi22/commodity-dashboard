"""Food consumer-price indices for many markets -> data/food_cpi.json

Everything food related (COICOP division 01 "Food and non-alcoholic beverages", down to
the most detailed level a source publishes) from public APIs, no key needed:

  Eurostat dissemination API   prc_hicp_minr (HICP, ECOICOP v2, 2025 = 100)
      EU27, euro area, and DE IT NL IE DK SE NO  - 101 food codes each
  ONS time-series API          UK CPI (dataset MM23, 2015 = 100) - 63 food series

The UK is no longer in Eurostat HICP, so it keeps ONS' own (older COICOP) tree.
Germany's national CPI detail (Destatis 61111-0004) stays in data/{slug}/destatis.json
and is merged into the same screen by build_app_data.py.

Run:  py scripts/fetch_food_cpi.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_indirect_countries import EUROSTAT, INFL, ONS, SHORT, get_json  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "food_cpi.json"
SINCE = "2024-01"
GEOS = ["EU27_2020", "EA", "DE", "IT", "NL", "IE", "DK", "SE", "NO"]

# ONS CPI index series for COICOP 01 (MM23). CDID, dotted COICOP code, label.
UK = [
    ("D7BU", "01", "Food and non-alcoholic beverages"), ("D7C8", "01.1", "Food"), ("D7C9", "01.2", "Non-alcoholic beverages"),
    ("D7D5", "01.1.1", "Bread & cereals"), ("D7D6", "01.1.2", "Meat"), ("D7D7", "01.1.3", "Fish"),
    ("D7D8", "01.1.4", "Milk, cheese & eggs"), ("D7D9", "01.1.5", "Oils & fats"), ("D7DA", "01.1.6", "Fruit"),
    ("D7DB", "01.1.7", "Vegetables incl. potatoes"), ("D7DC", "01.1.8", "Sugar, jam, honey, chocolate & confectionery"),
    ("D7DD", "01.1.9", "Food products n.e.c."), ("D7DE", "01.2.1", "Coffee, tea, cocoa"), ("D7DF", "01.2.2", "Mineral waters, soft drinks & juices"),
    ("L78H", "01.1.1.1", "Rice"), ("L78I", "01.1.1.2", "Flours and other cereals"), ("L78J", "01.1.1.3", "Bread"),
    ("L78K", "01.1.1.4", "Other bakery products"), ("L78M", "01.1.1.5", "Pizza and quiche"), ("L78N", "01.1.1.6", "Pasta products and couscous"),
    ("L78O", "01.1.1.7", "Breakfast cereals and other cereal products"),
    ("L78Q", "01.1.2.1", "Beef and veal"), ("L78R", "01.1.2.2", "Pork"), ("L78S", "01.1.2.3", "Lamb and goat"),
    ("L78U", "01.1.2.4", "Poultry"), ("L78V", "01.1.2.6", "Edible offal"), ("L78W", "01.1.2.7", "Dried, salted or smoked meat"),
    ("L78X", "01.1.2.8", "Other meat preparations"),
    ("L78Y", "01.1.3.1", "Fresh or chilled fish"), ("L78Z", "01.1.3.4", "Frozen seafood"),
    ("L792", "01.1.3.6", "Other preserved or processed fish & seafood"),
    ("L793", "01.1.4.1", "Whole milk"), ("L794", "01.1.4.2", "Low fat milk"), ("L796", "01.1.4.4", "Yoghurt"),
    ("L797", "01.1.4.5", "Cheese and curd"), ("L798", "01.1.4.6", "Other milk products"), ("L79A", "01.1.4.7", "Eggs"),
    ("L79C", "01.1.5.1", "Butter"), ("L79D", "01.1.5.2", "Margarine and other vegetable fats"), ("L79E", "01.1.5.3", "Olive oil"),
    ("L79G", "01.1.6.1", "Fresh or chilled fruit"), ("L79I", "01.1.6.3", "Dried fruit and nuts"),
    ("L79K", "01.1.6.4", "Preserved fruit and fruit-based products"),
    ("L79M", "01.1.7.1", "Fresh or chilled vegetables (excl. potatoes)"), ("L79N", "01.1.7.2", "Frozen vegetables"),
    ("L79O", "01.1.7.3", "Dried, preserved or processed vegetables"), ("L79Q", "01.1.7.4", "Potatoes"), ("L79R", "01.1.7.5", "Crisps"),
    ("L79S", "01.1.7.6", "Other tubers and tuber products"),
    ("L79U", "01.1.8.1", "Sugar"), ("L79W", "01.1.8.2", "Jams, marmalades and honey"), ("L79X", "01.1.8.3", "Chocolate"),
    ("L79Y", "01.1.8.4", "Confectionery products"), ("L7A2", "01.1.8.5", "Edible ices and ice cream"),
    ("L7A3", "01.1.9.1", "Sauces, condiments, salt, spices and herbs"), ("L7A4", "01.1.9.4", "Ready-made meals"),
    ("L7A5", "01.1.9.9", "Other food products n.e.c."),
    ("L7A6", "01.2.1.1", "Coffee"), ("L7A8", "01.2.1.2", "Tea"), ("L7AA", "01.2.1.3", "Cocoa and powdered chocolate"),
    ("L7AC", "01.2.2.1", "Mineral or spring waters"), ("L7AE", "01.2.2.2", "Soft drinks"), ("L7AF", "01.2.2.3", "Fruit and vegetable juices"),
]


def parent_of(code: str, codes: set[str]) -> str | None:
    """Longest other code that is a strict prefix of `code` (works for both CP.. and dotted codes)."""
    best = None
    for c in codes:
        if c != code and code.startswith(c) and (best is None or len(c) > len(best)):
            best = c
    return best


def months_from(first: str, last: str) -> list[str]:
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def main() -> None:
    # ---------------- Eurostat ----------------
    print("Eurostat HICP, all COICOP 01 codes ...")
    d = get_json(EUROSTAT + "prc_hicp_minr?format=JSON&unit=I25&geo=IE&sinceTimePeriod=2026-09&lang=en")
    labels = {k: v for k, v in d["dimension"]["coicop18"]["category"]["label"].items() if k.startswith("CP01")}
    labels = {k: v.replace(" (ND)", "").replace(" (S)", "") for k, v in labels.items()}
    codes = sorted(labels)
    tr: dict[str, dict[str, str]] = {}                # German / French names straight from Eurostat
    for lg in ("de", "fr"):
        dd = get_json(EUROSTAT + f"prc_hicp_minr?format=JSON&unit=I25&geo=IE&sinceTimePeriod=2026-09&lang={lg}")
        for k, v in dd["dimension"]["coicop18"]["category"]["label"].items():
            if k in labels:
                tr.setdefault(k, {})[lg] = v.replace(" (ND)", "").replace(" (S)", "")
    from urllib.parse import urlencode
    q = urlencode({"format": "JSON", "unit": "I25", "geo": GEOS, "coicop18": codes, "sinceTimePeriod": SINCE}, doseq=True)
    d = get_json(EUROSTAT + "prc_hicp_minr?" + q)
    ids, size = d["id"], d["size"]
    cats = {i: list(d["dimension"][i]["category"]["index"]) for i in ids}
    strides = [1] * len(ids)
    for k in range(len(ids) - 2, -1, -1):
        strides[k] = strides[k + 1] * size[k + 1]
    series: dict[str, dict[str, dict[str, float]]] = {}
    for pos, v in d.get("value", {}).items():
        pos = int(pos)
        idx = {ids[k]: (pos // strides[k]) % size[k] for k in range(len(ids))}
        g = cats["geo"][idx["geo"]]
        c = cats["coicop18"][idx["coicop18"]]
        t = cats["time"][idx["time"]]
        series.setdefault(g, {}).setdefault(c, {})[t] = float(v)

    # ---------------- ONS ----------------
    print("ONS CPI food series ...")
    uk: dict[str, dict[str, float]] = {}
    for cdid, code, lab in UK:
        try:
            j = get_json(ONS.format(path=INFL, cdid=cdid.lower(), ds="mm23"))
        except Exception as e:                       # noqa: BLE001
            print("  skip", cdid, e)
            continue
        s: dict[str, float] = {}
        for r in j["months"]:
            try:
                val = float(r["value"])
            except (KeyError, ValueError):
                continue
            y, mon = r["date"].split()
            p = f"{y}-{[x.upper() for x in SHORT].index(mon[:3].upper()) + 1:02d}"
            if p >= SINCE:
                s[p] = val
        if s:
            uk["uk:" + code] = s

    # ---------------- assemble ----------------
    all_months = sorted({t for g in series.values() for c in g.values() for t in c} |
                        {t for s in uk.values() for t in s})
    months = months_from(all_months[0], all_months[-1])

    nodes: dict[str, dict] = {}
    for c in codes:
        nodes[c] = {"label": labels[c], "parent": parent_of(c, set(codes))}
        if c in tr:
            nodes[c]["tr"] = tr[c]
    ukcodes = {"uk:" + code for _, code, _ in UK}
    for _, code, lab in UK:
        k = "uk:" + code
        p = parent_of(k, ukcodes)
        nodes[k] = {"label": lab, "parent": p}

    def row(s: dict[str, float]) -> list:
        return [s.get(m) for m in months]

    countries = {}
    for g in GEOS:
        if g in series:
            countries[g] = {"source": "Eurostat HICP", "base": "2025 = 100",
                            "series": {c: row(s) for c, s in sorted(series[g].items())}}
    countries["UK"] = {"source": "ONS CPI", "base": "2015 = 100", "series": {c: row(s) for c, s in sorted(uk.items())}}

    out = {"months": months, "nodes": nodes, "countries": countries}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = sum(len(c["series"]) for c in countries.values())
    print(f"wrote {OUT.relative_to(ROOT)}: {len(countries)} markets, {n} series, {months[0]}..{months[-1]}, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
