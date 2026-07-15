"""Build the data blob for the redesigned single-page app (app.html).

Reads every quarter registered in data/manifest.json and emits
public/reports/app-data.js as `window.CD_APP = {...}` — a single object the
static SPA renders client-side (menu + quarter report + Germany deep-dive).

Everything the UI needs is precomputed here (category colours, category net
YoY, KPIs, movers inputs, Germany food-group indices, forecast curves), so
the client stays a thin renderer.

Usage:
  py scripts/build_app_data.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
OUT = ROOT / "public" / "reports" / "app-data.js"

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

# Fixed categorical colour order (assigned once, never cycled). Dark-theme
# hues chosen to stay distinguishable side by side.
CATEGORY_COLORS = {
    "Meat & Poultry": "#F87171",
    "Dairy & Eggs": "#FBBF24",
    "Grains & Feed": "#A3E635",
    "Oilseeds & Vegetable Oils": "#34D399",
    "Fish & Seafood": "#22D3EE",
    "Fruit & Vegetables": "#60A5FA",
    "Packaging": "#A78BFA",
    "Softs": "#F472B6",
    "Nuts & Dried Fruit": "#FB923C",
    "Herbs & Spices": "#2DD4BF",
    "Juices": "#C084FC",
    "Textiles": "#E879F9",
}
FALLBACK_COLOR = "#94A3B8"


def cat_color(name: str) -> str:
    return CATEGORY_COLORS.get(name, FALLBACK_COLOR)


def quarter_label(slug: str) -> str:
    # Fiscal year starts in April: Apr-Jun = Q1, Jul-Sep = Q2, Oct-Dec = Q3,
    # Jan-Mar = Q4 (of the fiscal year that began the previous April).
    y, m = int(slug.split("-")[0]), int(slug.split("-")[1])
    fq = ((m - 4) % 12) // 3 + 1
    fy = y if m >= 4 else y - 1
    return f"Q{fq} {fy}"


def month_label(slug: str) -> str:
    y, m = slug.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def load(slug: str, name: str):
    p = ROOT / "data" / slug / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def num(v):
    return v if isinstance(v, (int, float)) else None


def mean(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 1) if vals else None


# ------------------------------------------------------------------ forecast
# Curated forecast code -> exact commodity name (mirrors build_html.py's
# FORECAST_CODE_TO_SUMMARY_NAME). Loose token matching produced wrong curves
# (e.g. Cocoa Bean ICE New York -> London curve, Rapeseed Oil Canada ->
# Rotterdam curve), so we map by the Mintec code, not by name similarity.
# Extend this when new codes appear in forecast.xlsx.
FORECAST_CODE_TO_NAME = {
    "COCL": "Cocoa Bean ICE London",
    "COFN": "Arabica Coffee ICE New York",
    "WHT2": "Wheat Euronext",
    "CRNP": "Maize Euronext",
    "RSOR": "Rapeseed Oil EU",
    "SG11": "Sugar ICE #11 New York",
    "BUTH": "Butter EU",
    "MDC2": "Beef EU",
    "BY18": "Chicken EU",
    "BW19": "Pork EU",
    "J114": "Gouda EU",
    "ED24": "Milk EU",
    "UI62": "Cod Norway",
    "UG01": "Salmon Norway",
}


def build_forecast_by_name(forecast: dict) -> dict:
    """Map lowercased commodity name -> downsampled forward curve, using the
    curated code map (no fuzzy matching)."""
    out = {}
    for c in (forecast or {}).get("commodities", []):
        target = FORECAST_CODE_TO_NAME.get(c.get("code"))
        if not target:
            continue
        pts = c.get("points", [])
        step = max(1, len(pts) // 50)  # ~50 points keeps the payload small
        out[target.lower()] = {
            "desc": c.get("description") or c.get("label") or target,
            "unit": c.get("unit", ""),
            "points": [{"d": p["date"], "v": p["value"]} for p in pts[::step]],
        }
    return out


# ------------------------------------------------------------------ germany
def _head_of(s: dict) -> dict:
    """Read the precomputed latest/yoy/mom fields off a Destatis series."""
    latest = s.get("latest") or {}
    return {"latest": latest.get("index"), "month": latest.get("month"),
            "yoy": s.get("yoy_pct"), "mom": s.get("mom_pct")}


def build_germany(destatis: dict) -> dict | None:
    if not destatis:
        return None
    by_coicop = {s["coicop"]: s for s in destatis.get("series", [])}
    cp01 = by_coicop.get("CP01")
    if not cp01:
        return None
    head = _head_of(cp01)
    trend = cp01["series"][-12:]

    # Food groups = 5-digit COICOP under food (CP011x) & beverages (CP012x).
    groups = []
    for coicop, s in by_coicop.items():
        if re.fullmatch(r"CP01[12]\d", coicop):
            st = _head_of(s)
            groups.append({
                "coicop": coicop,
                "label": s.get("label", coicop),
                "index": st["latest"],
                "yoy": st["yoy"],
                "mom": st["mom"],
            })
    groups.sort(key=lambda g: (g["index"] is None, -(g["index"] or 0)))

    kpis = [
        {"label": "DE Food Index", "value": f'{head["latest"]:.1f}' if head["latest"] else "—",
         "sub": f'Destatis CP01 · latest {head["month"] or "—"}', "tone": "neutral"},
        {"label": "YoY", "value": _pct(head["yoy"]), "sub": "vs a year ago", "tone": _tone(head["yoy"])},
        {"label": "MoM", "value": _pct(head["mom"]), "sub": "vs previous month", "tone": _tone(head["mom"])},
        {"label": "Food groups", "value": str(len(groups)), "sub": "COICOP 5-digit tracked", "tone": "neutral"},
    ]
    return {
        "meta": {"title": "Germany — Food Market Detail", "period": None,
                 "latestMonth": head["month"], "baseLabel": destatis.get("base_year", "2020 = 100")},
        "head": head,
        "kpis": kpis,
        "trend": {"labels": [p["month"] for p in trend],
                  "values": [p["index"] for p in trend],
                  "baseLabel": f'Index, {destatis.get("base_year", "2020 = 100")}'},
        "groups": groups,
    }


def _pct(v):
    return f"{v:+.1f}%" if isinstance(v, (int, float)) else "—"


def _tone(v):
    if not isinstance(v, (int, float)):
        return "neutral"
    return "up" if v >= 0 else "down"


# ------------------------------------------------------------------ per report
def build_report(slug: str) -> dict:
    meta = load(slug, "meta.json") or {}
    commodities = (load(slug, "commodities.json") or {}).get("rows", [])
    hicp = load(slug, "hicp_index.json") or {}
    commentary = (load(slug, "commentary.json") or {}).get("entries", [])
    destatis = load(slug, "destatis.json")
    forecast = load(slug, "forecast.json")
    fmap = build_forecast_by_name(forecast)

    # commentary lookup by canonical name (fall back to raw name)
    cmap = {}
    for e in commentary:
        for key in (e.get("canonical_name"), e.get("name")):
            if key and key not in cmap:
                cmap[key] = e

    rows = []
    for r in commodities:
        name = r.get("name", "")
        c = cmap.get(name)
        fc = fmap.get(name.lower())
        # Display name without the trailing "*" lag marker (kept in the raw
        # data, but hidden in the UI on request).
        display = re.sub(r"\s*\*+\s*$", "", name)
        rows.append({
            "category": r.get("category", "Other"),
            "name": display,
            "mom": num(r.get("mom_pct")),
            "yoy": num(r.get("yoy_pct")),
            "price": (c or {}).get("price", ""),
            "note": (c or {}).get("paragraph", ""),
            "forecast": fc,
        })

    # categories with net (avg) YoY
    cats = {}
    for r in rows:
        cats.setdefault(r["category"], []).append(r)
    categories = [{
        "name": name,
        "color": cat_color(name),
        "count": len(items),
        "netYoY": mean([i["yoy"] for i in items]),
        "netMoM": mean([i["mom"] for i in items]),
    } for name, items in cats.items()]
    categories.sort(key=lambda c: c["name"])

    # KPIs
    with_mom = [r for r in rows if r["mom"] is not None]
    top_hike = max(with_mom, key=lambda r: r["mom"], default=None)
    top_drop = min(with_mom, key=lambda r: r["mom"], default=None)
    latest_month = hicp.get("latest_month", "")
    kpis = [
        {"label": f"HICP Food Index ({latest_month})",
         "value": f'{hicp.get("latest_index", "—")}',
         "sub": f'Eurostat EU27 · {hicp.get("base_year", "2025 = 100")} base', "tone": "neutral"},
        {"label": "YoY Food Inflation", "value": _pct(hicp.get("yoy_pct_last_12")),
         "sub": "HICP food, last 12 months", "tone": _tone(hicp.get("yoy_pct_last_12"))},
        {"label": "Highest MoM Hike",
         "value": f'{top_hike["name"]} ({_pct(top_hike["mom"])})' if top_hike else "—",
         "sub": "Immediate cost pressure", "tone": "up"},
        {"label": "Biggest MoM Drop",
         "value": f'{top_drop["name"]} ({_pct(top_drop["mom"])})' if top_drop else "—",
         "sub": "Procurement opportunity", "tone": "down"},
    ]

    series = hicp.get("series", [])
    return {
        "meta": {
            "slug": slug, "q": quarter_label(slug), "title": meta.get("title", ""),
            "period": meta.get("period", month_label(slug)), "region": meta.get("region", ""),
            "periodMom": meta.get("period_mom", ""), "periodYoy": meta.get("period_yoy", ""),
            "source": meta.get("source", ""),
        },
        "hicp": {
            "labels": [s["month"] for s in series],
            "values": [s["index"] for s in series],
            "baseLabel": f'Index, {hicp.get("base_year", "2025 = 100")}',
            "yoyPct": hicp.get("yoy_pct_last_12"),
        },
        "kpis": kpis,
        "highlights": meta.get("highlights", []),
        "trend": meta.get("trend_analysis", ""),
        "categories": categories,
        "rows": rows,
        "germany": build_germany(destatis),
    }


def build_menu_card(slug: str, report: dict, is_latest: bool) -> dict:
    rows = report["rows"]
    risks = sum(1 for r in rows if (r["yoy"] or 0) >= 25)
    opps = sum(1 for r in rows if (r["yoy"] or 0) <= -25)
    g = report.get("germany") or {}
    ghead = g.get("head") or {}
    return {
        "slug": slug,
        "q": report["meta"]["q"],
        "title": report["meta"]["title"],
        "period": report["meta"]["period"],
        "region": report["meta"]["region"],
        "latest": is_latest,
        "hicpLevel": report["hicp"]["values"][-1] if report["hicp"]["values"] else None,
        "hicpYoY": report["hicp"].get("yoyPct"),
        "riskN": risks,
        "oppN": opps,
        "categories": [{"name": c["name"], "color": c["color"], "netYoY": c["netYoY"]}
                       for c in report["categories"]],
        "hasGermany": bool(g),
        "gIndex": ghead.get("latest"),
        "gYoY": ghead.get("yoy"),
        "gLatest": ghead.get("month"),
        "highlights": report["highlights"][:3],
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reports_meta = sorted(manifest["reports"], key=lambda r: r["slug"], reverse=True)
    default_slug = reports_meta[0]["slug"] if reports_meta else None

    reports = {}
    menu = []
    for rm in reports_meta:
        slug = rm["slug"]
        rep = build_report(slug)
        reports[slug] = rep
        menu.append(build_menu_card(slug, rep, is_latest=(slug == default_slug)))

    payload = {
        "brand": {
            "eyebrow": "Procurement PMO · Europe",
            "title": "Commodity Dashboard",
            "subtitle": "Quarterly cost intelligence for food & catering procurement",
        },
        "defaultSlug": default_slug,
        "menu": menu,
        "reports": reports,
        "categoryColors": CATEGORY_COLORS,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = "window.CD_APP = " + json.dumps(payload, ensure_ascii=False) + ";\n"
    OUT.write_text(js, encoding="utf-8")
    fc = sum(1 for r in reports.values() for row in r["rows"] if row["forecast"])
    print(f"Wrote {OUT.relative_to(ROOT)} — {len(menu)} quarter(s), "
          f"{sum(len(r['rows']) for r in reports.values())} rows, {fc} forecast matches")


if __name__ == "__main__":
    main()
