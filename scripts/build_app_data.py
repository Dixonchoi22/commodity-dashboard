"""Build the data blob for the redesigned single-page app (app.html).

Reads every quarter registered in data/manifest.json and emits
public/reports/app-data.js as `window.CD_APP = {...}` — a single object the
static SPA renders client-side (menu + quarter report + Germany deep-dive).

Everything the UI needs is precomputed here (category colours, category net
YoY, movers inputs, Germany food-group indices, forecast curves), so the
client stays a thin renderer.

Labels are the exception: anything the user reads is emitted as a
translation *key* plus parameters, never as a finished English sentence, so
the SPA can render it in any of the languages in data/i18n.json. Raw values
that need locale formatting (numbers, percentages, "Jun 2026" months) are
emitted unformatted and shaped client-side.

Usage:
  py scripts/build_app_data.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
I18N = ROOT / "data" / "i18n.json"
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


# ------------------------------------------------------------------ i18n
# data/i18n.json is authored key-first (all languages of one string side by
# side, so gaps are obvious). The client wants it language-first, so pivot
# here and report anything that would silently fall back to English.
def build_i18n() -> dict:
    cat = json.loads(I18N.read_text(encoding="utf-8"))
    langs = cat["languages"]
    codes = [l["code"] for l in langs]
    missing: list[str] = []

    def pivot(section: str, self_is_en: bool = False) -> dict:
        """section -> {lang: {key: text}}. With self_is_en the entry key is
        itself the English text (categories, phrases)."""
        out = {c: {} for c in codes}
        for key, vals in cat.get(section, {}).items():
            en = key if self_is_en else vals.get("en", key)
            for c in codes:
                text = vals.get(c) or (en if c == "en" else None)
                if text is None:
                    missing.append(f"{section}.{key} [{c}]")
                    text = en
                out[c][key] = text
        return out

    pivoted = {
        "strings": pivot("strings"),
        "categories": pivot("categories", self_is_en=True),
        "coicop": pivot("coicop"),
        "phrases": pivot("phrases", self_is_en=True),
        "commodities": pivot("commodities", self_is_en=True),
    }
    if missing:
        print(f"  ! {len(missing)} untranslated entries fall back to English:")
        for m in missing[:10]:
            print(f"      {m}")
        if len(missing) > 10:
            print(f"      … and {len(missing) - 10} more")
    return {
        "languages": [{"code": l["code"], "name": l["name"], "locale": l["locale"]}
                      for l in langs],
        "default": "en",
        **pivoted,
    }


def load_overrides(slug: str, codes: list[str]) -> dict:
    """Optional per-quarter translations of analyst-written text, one file per
    language at data/{slug}/i18n/{lang}.json:

        {"trend_analysis": "…",
         "highlights": [{"label": "…", "body": "…"}],
         "commentary": {"Butter EU": "…"},
         "indirect": {"summary": "…",
                      "pillars": {"energy": "…"},
                      "actions": [{"label": "…", "body": "…"}]}}

    Anything absent falls back to the English source text — including
    individually, so a file may translate two pillars and leave the rest."""
    out = {}
    for code in codes:
        if code == "en":
            continue
        p = ROOT / "data" / slug / "i18n" / f"{code}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        entry = {}
        if d.get("trend_analysis"):
            entry["trend"] = d["trend_analysis"]
        if d.get("highlights"):
            entry["highlights"] = d["highlights"]
        if d.get("commentary"):
            entry["notes"] = d["commentary"]
        if d.get("indirect"):
            entry["indirect"] = d["indirect"]
        if entry:
            out[code] = entry
    return out


def quarter_parts(slug: str) -> tuple[int, int]:
    # Fiscal year starts in April: Apr-Jun = Q1, Jul-Sep = Q2, Oct-Dec = Q3,
    # Jan-Mar = Q4 (of the fiscal year that began the previous April).
    y, m = int(slug.split("-")[0]), int(slug.split("-")[1])
    fq = ((m - 4) % 12) // 3 + 1
    fy = y if m >= 4 else y - 1
    return fq, fy


def quarter_label(slug: str) -> str:
    fq, fy = quarter_parts(slug)
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

    base = destatis.get("base_year", "2020 = 100")
    kpis = [
        {"k": "menu.deIndex", "type": "num", "num": head["latest"],
         "sub": "de.kpiIndexSub", "subp": {"month": head["month"]}, "tone": "neutral"},
        {"k": "common.yoyLong", "type": "pct", "pct": head["yoy"],
         "sub": "de.kpiYoySub", "tone": _tone(head["yoy"])},
        {"k": "common.momLong", "type": "pct", "pct": head["mom"],
         "sub": "de.kpiMomSub", "tone": _tone(head["mom"])},
        {"k": "de.kpiGroups", "type": "count", "num": len(groups),
         "sub": "de.kpiGroupsSub", "tone": "neutral"},
    ]
    return {
        "meta": {"latestMonth": head["month"], "base": base},
        "head": head,
        "kpis": kpis,
        "trend": {"labels": [p["month"] for p in trend],
                  "values": [p["index"] for p in trend],
                  "base": base},
        "groups": groups,
    }


def _tone(v):
    if not isinstance(v, (int, float)):
        return "neutral"
    return "up" if v >= 0 else "down"


# ------------------------------------------------------------------ indirect
def build_indirect(ind: dict | None) -> dict | None:
    """Indirect inflation — energy, freight, labour and packaging inputs.

    Optional per quarter: without data/{slug}/indirect.json the SPA simply has
    no indirect section. Each pillar gets a basket average (mean YoY / first-
    percentage across its drivers) so the rail, the KPIs and the report-level
    teaser can all rank pillars without the client recomputing anything."""
    if not ind:
        return None
    pillars = []
    for p in ind.get("pillars", []):
        drivers = p.get("drivers", [])
        pillars.append({
            "key": p["key"],
            "color": p.get("color", FALLBACK_COLOR),
            "count": len(drivers),
            "netYoY": mean([d.get("yoy") for d in drivers]),
            "netMoM": mean([d.get("mom") for d in drivers]),
            "commentary": p.get("commentary", ""),
            "crosslink": p.get("crosslink", ""),
            "policy": p.get("policy", []),
            "drivers": [{
                "name": d.get("name", ""),
                "region": d.get("region", ""),
                "code": d.get("code", ""),
                "price": d.get("price", ""),
                "mom": num(d.get("mom")),
                "yoy": num(d.get("yoy")),
                "basis": d.get("basis", "mom"),
                "asOf": d.get("asOf", ""),
                "source": d.get("source", ""),
                "note": d.get("note", ""),
                # which report and page the figure was read from
                "ref": d.get("ref"),
            } for d in drivers],
        })

    all_yoy = [d["yoy"] for p in pillars for d in p["drivers"]]
    net = mean(all_yoy)
    summary = ind.get("summary", {})
    gap = summary.get("gap", {})
    gap_pp = None
    if isinstance(gap.get("labour_pct"), (int, float)) and isinstance(gap.get("cpi_pct"), (int, float)):
        gap_pp = round(gap["labour_pct"] - gap["cpi_pct"], 1)

    def basket(key):
        p = [x for x in pillars if x["key"] == key]
        return p[0] if p else {"netYoY": None, "count": 0}

    energy, freight, labour = basket("energy"), basket("freight"), basket("labour")
    kpis = [
        {"k": "ind.kpi.energy", "type": "pct", "pct": energy["netYoY"],
         "sub": "ind.kpi.basketSub", "subp": {"n": energy["count"]},
         "tone": _tone(energy["netYoY"])},
        {"k": "ind.kpi.freight", "type": "pct", "pct": freight["netYoY"],
         "sub": "ind.kpi.basketSub", "subp": {"n": freight["count"]},
         "tone": _tone(freight["netYoY"])},
        {"k": "ind.kpi.labour", "type": "pct", "pct": labour["netYoY"],
         "sub": "ind.kpi.basketSub", "subp": {"n": labour["count"]},
         "tone": _tone(labour["netYoY"])},
        {"k": "ind.kpi.gap", "type": "pp", "num": gap_pp,
         "sub": "ind.kpi.gapSub", "tone": _tone(gap_pp)},
    ]
    return {
        "meta": {"asOf": ind.get("as_of", ""), "sources": ind.get("sources", [])},
        "net": net,
        "kpis": kpis,
        "summary": summary,
        "pillars": pillars,
        "actions": ind.get("actions", []),
    }


# ------------------------------------------------------------------ per report
def build_report(slug: str, lang_codes: list[str]) -> dict:
    meta = load(slug, "meta.json") or {}
    commodities = (load(slug, "commodities.json") or {}).get("rows", [])
    hicp = load(slug, "hicp_index.json") or {}
    commentary = (load(slug, "commentary.json") or {}).get("entries", [])
    destatis = load(slug, "destatis.json")
    indirect = load(slug, "indirect.json")
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
    base = hicp.get("base_year", "2025 = 100")
    kpis = [
        {"k": "kpi.hicpIndex", "kp": {"month": latest_month},
         "type": "num", "num": num(hicp.get("latest_index")),
         "sub": "kpi.hicpIndex.sub", "subp": {"base": base}, "tone": "neutral"},
        {"k": "kpi.yoyFood", "type": "pct", "pct": hicp.get("yoy_pct_last_12"),
         "sub": "kpi.yoyFood.sub", "tone": _tone(hicp.get("yoy_pct_last_12"))},
        {"k": "kpi.topHike", "type": "namePct",
         "name": top_hike["name"] if top_hike else None,
         "pct": top_hike["mom"] if top_hike else None,
         "sub": "kpi.topHike.sub", "tone": "up"},
        {"k": "kpi.topDrop", "type": "namePct",
         "name": top_drop["name"] if top_drop else None,
         "pct": top_drop["mom"] if top_drop else None,
         "sub": "kpi.topDrop.sub", "tone": "down"},
    ]

    fq, fy = quarter_parts(slug)
    y, m = slug.split("-")
    series = hicp.get("series", [])
    return {
        "meta": {
            "slug": slug, "q": quarter_label(slug), "qn": fq, "fy": fy,
            "title": meta.get("title", ""),
            "period": meta.get("period", month_label(slug)),
            "periodY": int(y), "periodM": int(m), "region": meta.get("region", ""),
            "periodMom": meta.get("period_mom", ""), "periodYoy": meta.get("period_yoy", ""),
            "source": meta.get("source", ""),
        },
        "hicp": {
            "labels": [s["month"] for s in series],
            "values": [s["index"] for s in series],
            "base": base,
            "yoyPct": hicp.get("yoy_pct_last_12"),
        },
        "kpis": kpis,
        "tr": load_overrides(slug, lang_codes),
        "highlights": meta.get("highlights", []),
        "trend": meta.get("trend_analysis", ""),
        "categories": categories,
        "rows": rows,
        "germany": build_germany(destatis),
        "indirect": build_indirect(indirect),
    }


def build_menu_card(slug: str, report: dict, is_latest: bool) -> dict:
    rows = report["rows"]
    risks = sum(1 for r in rows if (r["yoy"] or 0) >= 25)
    opps = sum(1 for r in rows if (r["yoy"] or 0) <= -25)
    g = report.get("germany") or {}
    ghead = g.get("head") or {}
    ind = report.get("indirect") or {}
    return {
        "slug": slug,
        "q": report["meta"]["q"],
        "qn": report["meta"]["qn"],
        "fy": report["meta"]["fy"],
        "title": report["meta"]["title"],
        "period": report["meta"]["period"],
        "periodY": report["meta"]["periodY"],
        "periodM": report["meta"]["periodM"],
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
        "hasIndirect": bool(ind),
        "iNet": ind.get("net"),
        "iAsOf": (ind.get("meta") or {}).get("asOf"),
        "iPillars": [{"key": p["key"], "color": p["color"], "netYoY": p["netYoY"]}
                     for p in ind.get("pillars", [])],
        "highlights": report["highlights"][:3],
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reports_meta = sorted(manifest["reports"], key=lambda r: r["slug"], reverse=True)
    default_slug = reports_meta[0]["slug"] if reports_meta else None

    i18n = build_i18n()
    lang_codes = [l["code"] for l in i18n["languages"]]

    reports = {}
    menu = []
    for rm in reports_meta:
        slug = rm["slug"]
        rep = build_report(slug, lang_codes)
        reports[slug] = rep
        menu.append(build_menu_card(slug, rep, is_latest=(slug == default_slug)))

    # Indirect-inflation prose is analyst-written, so it lives in the optional
    # per-quarter override files rather than the catalogue. Report what is still
    # falling back to English — the screen shows a note when it does, but the
    # build is the only place anyone learns which pieces are missing.
    gaps = []
    for slug, rep in reports.items():
        ind = rep.get("indirect")
        if not ind:
            continue
        wanted = (["summary"]
                  + [f"pillars.{p['key']}" for p in ind["pillars"]]
                  + (["actions"] if ind.get("actions") else []))
        for code in lang_codes:
            if code == "en":
                continue
            ov = (rep["tr"].get(code) or {}).get("indirect") or {}
            missing = []
            for key in wanted:
                if key.startswith("pillars."):
                    if not (ov.get("pillars") or {}).get(key.split(".", 1)[1]):
                        missing.append(key)
                elif key == "actions":
                    if len(ov.get("actions") or []) != len(ind["actions"]):
                        missing.append(key)
                elif not ov.get(key):
                    missing.append(key)
            if missing:
                gaps.append(f"{slug} [{code}]: {', '.join(missing)}")
    if gaps:
        print(f"  ! indirect-inflation prose still in English for "
              f"{len(gaps)} quarter/language pair(s):")
        for g in gaps[:10]:
            print(f"      {g}")
        if len(gaps) > 10:
            print(f"      … and {len(gaps) - 10} more")

    # A new quarter can introduce a commodity the catalogue has never seen.
    # It still renders (falling back to its English name), but say so — that
    # is the only way anyone finds out a name needs translating.
    known = i18n["commodities"]["en"]
    unknown = sorted({row["name"] for rep in reports.values() for row in rep["rows"]}
                     - set(known))
    if unknown:
        print(f"  ! {len(unknown)} commodity name(s) missing from "
              f"data/i18n.json 'commodities' — shown in English:")
        for n in unknown:
            print(f"      {n}")

    payload = {
        "defaultSlug": default_slug,
        "menu": menu,
        "reports": reports,
        "categoryColors": CATEGORY_COLORS,
        "i18n": i18n,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = "window.CD_APP = " + json.dumps(payload, ensure_ascii=False) + ";\n"
    OUT.write_text(js, encoding="utf-8")
    fc = sum(1 for r in reports.values() for row in r["rows"] if row["forecast"])
    print(f"Wrote {OUT.relative_to(ROOT)} — {len(menu)} quarter(s), "
          f"{sum(len(r['rows']) for r in reports.values())} rows, {fc} forecast matches, "
          f"{len(lang_codes)} languages ({', '.join(lang_codes)})")


if __name__ == "__main__":
    main()
