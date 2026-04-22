"""Build a standalone HTML dashboard for a given period.

Reads data/{period}/*.json (commodities, hicp, forecast, commentary, meta)
and writes a self-contained HTML file under public/reports/.

Usage:
  python scripts/build_html.py 2026-04
"""
from __future__ import annotations

import html as _html
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(period: str) -> dict:
    p = ROOT / "data" / period
    def maybe(name: str):
        path = p / name
        return json.loads(path.read_text()) if path.exists() else None
    return {
        "meta": maybe("meta.json") or {},
        "commodities": maybe("commodities.json") or {"rows": []},
        "hicp": maybe("hicp.json") or {"months": [], "series": []},
        "forecast": maybe("forecast.json") or {"commodities": []},
        "commentary": maybe("commentary.json") or {"entries": []},
        "hicp_index": maybe("hicp_index.json"),
    }


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"


def tone_for(v: float | None) -> str:
    if v is None:
        return "neutral"
    if v > 0.5:
        return "red"
    if v < -0.5:
        return "green"
    return "neutral"


CATEGORY_ICON = {
    "Grains & Feed": "wheat",
    "Oilseeds & Vegetable Oils": "droplet",
    "Meat & Poultry": "beef",
    "Dairy & Eggs": "milk",
    "Fish & Seafood": "fish",
    "Fruit & Vegetables": "apple",
    "Juices": "soup",
    "Softs": "coffee",
    "Herbs & Spices": "leaf",
    "Nuts & Dried Fruit": "nut",
    "Textiles": "scissors",
    "Packaging": "box",
    "Unknown": "circle-help",
}


def kpi_card(kpi: dict) -> str:
    tone_ring = {
        "red": "ring-secondary-red/30",
        "green": "ring-accent-green/30",
        "blue": "ring-primary-blue/30",
        "warning": "ring-text-warning/30",
    }[kpi["tone"]]
    tone_text = {
        "red": "text-secondary-red",
        "green": "text-accent-green",
        "blue": "text-primary-blue",
        "warning": "text-text-warning",
    }[kpi["tone"]]
    return f"""
<div class="card text-center ring-2 {tone_ring} hover:shadow-xl-dark">
  <p class="text-sm font-medium text-dark-muted uppercase">{_html.escape(kpi['label'])}</p>
  <p class="text-2xl sm:text-3xl font-extrabold mt-1 {tone_text}">{_html.escape(kpi['value'])}</p>
  <p class="text-xs text-gray-400 mt-1">{_html.escape(kpi['caption'])}</p>
</div>"""


def highlight_card(h: dict) -> str:
    border = {"red": "border-secondary-red", "green": "border-accent-green", "blue": "border-primary-blue"}[h["tone"]]
    text_c = {"red": "text-secondary-red", "green": "text-accent-green", "blue": "text-primary-blue"}[h["tone"]]
    return f"""
<div class="p-3 bg-dark-bg/50 rounded-lg border-l-4 {border}">
  <p class="font-bold {text_c}">{_html.escape(h['label'])}</p>
  <p class="text-sm text-gray-300 mt-1">{_html.escape(h['body'])}</p>
</div>"""


def category_card(category: str, rows: list[dict]) -> str:
    icon = CATEGORY_ICON.get(category, "circle-help")
    risks = [r for r in rows if (r.get("yoy_pct") or 0) > 10]
    opps = [r for r in rows if (r.get("yoy_pct") or 0) < -10]
    ring = "ring-transparent"
    tag = ""
    if risks:
        top = max(risks, key=lambda r: r.get("yoy_pct") or 0)
        ring = "ring-secondary-red/50 border-secondary-red"
        tag = f'<p class="text-xs font-semibold mt-2 text-secondary-red">Risk: {_html.escape(top["name"])} <span class="font-extrabold">{fmt_pct(top["yoy_pct"])} YoY</span></p>'
    elif opps:
        top = min(opps, key=lambda r: r.get("yoy_pct") or 0)
        ring = "ring-accent-green/50 border-accent-green"
        tag = f'<p class="text-xs font-semibold mt-2 text-accent-green">Opportunity: {_html.escape(top["name"])} <span class="font-extrabold">{fmt_pct(top["yoy_pct"])} YoY</span></p>'
    else:
        tag = '<p class="text-xs text-dark-muted mt-2">Stable range</p>'

    return f"""
<div onclick="showCategory('{_html.escape(category)}')" class="card text-center transition duration-300 hover:shadow-3xl ring-2 {ring} cursor-pointer">
  <i data-lucide="{icon}" class="w-8 h-8 text-primary-blue mx-auto mb-2"></i>
  <p class="text-xl font-bold text-dark-text">{_html.escape(category)}</p>
  <p class="text-sm font-medium mt-1 text-gray-400">{len(rows)} commodities</p>
  {tag}
</div>"""


def commodity_row(r: dict, price_lookup: dict[str, str]) -> str:
    mom_tone = tone_for(r.get("mom_pct"))
    yoy_tone = tone_for(r.get("yoy_pct"))
    tone_cls = {
        "red": "bg-soft-red-bg text-secondary-red border-secondary-red/50",
        "green": "bg-soft-green-bg text-accent-green border-accent-green/50",
        "neutral": "bg-dark-bg/50 text-dark-muted border-gray-600",
    }
    border_tone = {
        "red": "border-l-secondary-red/50",
        "green": "border-l-accent-green/50",
        "neutral": "border-l-gray-700",
    }[yoy_tone]
    price = price_lookup.get(r["name"].lower(), "—")
    return f"""
<tr class="hover:bg-dark-bg transition duration-150 border-l-4 {border_tone}" data-category="{_html.escape(r['category'])}" data-name="{_html.escape(r['name'].lower())}">
  <td class="px-4 py-3 whitespace-nowrap text-sm font-semibold text-dark-muted">{_html.escape(r['category'])}</td>
  <td class="px-4 py-3 whitespace-nowrap text-sm font-semibold text-dark-text">{_html.escape(r['name'])}</td>
  <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-300">{_html.escape(price)}</td>
  <td class="px-4 py-3 whitespace-nowrap text-center text-sm">
    <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border min-w-[70px] justify-center {tone_cls[mom_tone]}">{fmt_pct(r.get('mom_pct'))}</span>
  </td>
  <td class="px-4 py-3 whitespace-nowrap text-center text-sm">
    <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border min-w-[70px] justify-center {tone_cls[yoy_tone]}">{fmt_pct(r.get('yoy_pct'))}</span>
  </td>
</tr>"""


def build(period: str) -> str:
    bundle = load(period)
    meta = bundle["meta"]
    commodities = bundle["commodities"]["rows"]
    forecast = bundle["forecast"]
    commentary = bundle["commentary"]["entries"]
    hicp_index = bundle["hicp_index"]

    # Group commodities by category
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in commodities:
        by_cat[r["category"]].append(r)

    # Price lookup (from commentary entries) keyed by lowercased commodity name
    price_lookup: dict[str, str] = {}
    for e in commentary:
        if e.get("price"):
            price_lookup[e["name"].lower()] = e["price"]

    # Auto-compute KPIs from data (matches Sep 2025's 4-card layout)
    auto_kpis: list[dict] = []
    if hicp_index:
        latest = hicp_index["series"][-1]
        first = hicp_index["series"][0]
        yoy = (latest["index"] / first["index"] - 1) * 100
        auto_kpis.append({
            "label": f"HICP Food Index ({latest['month']})",
            "value": f"{latest['index']:.2f}",
            "caption": "Eurostat EU27 · 2015 = 100 base",
            "tone": "blue",
        })
        auto_kpis.append({
            "label": "YoY Overall Inflation",
            "value": f"{yoy:+.1f}%",
            "caption": f"vs. {first['month']} (HICP Food)",
            "tone": "red" if yoy > 0 else "green",
        })
    # Highest MoM hike + biggest MoM drop from commodities
    commodities_with_mom = [c for c in commodities if c.get("mom_pct") is not None]
    if commodities_with_mom:
        top_hike = max(commodities_with_mom, key=lambda c: c["mom_pct"])
        top_drop = min(commodities_with_mom, key=lambda c: c["mom_pct"])
        auto_kpis.append({
            "label": "Highest MoM Price Hike",
            "value": f"{top_hike['name']} ({fmt_pct(top_hike['mom_pct'])})",
            "caption": "Immediate cost pressure",
            "tone": "red",
        })
        auto_kpis.append({
            "label": "Biggest MoM Drop",
            "value": f"{top_drop['name']} ({fmt_pct(top_drop['mom_pct'])})",
            "caption": "Procurement opportunity",
            "tone": "green",
        })
    # If meta.kpis exists, use those instead (lets periods override)
    kpis = meta.get("kpis") if meta.get("kpis") else auto_kpis

    # Top risks / opportunities / balanced for Procurement Actions
    risks = sorted(
        (c for c in commodities if (c.get("yoy_pct") or 0) > 0),
        key=lambda r: r.get("yoy_pct") or 0,
        reverse=True,
    )[:5]
    opps = sorted(
        (c for c in commodities if (c.get("yoy_pct") or 0) < 0),
        key=lambda r: r.get("yoy_pct") or 0,
    )[:5]
    # Balanced: small absolute changes on both timeframes — moderate risk watch
    balanced = sorted(
        (
            c for c in commodities
            if c.get("yoy_pct") is not None and c.get("mom_pct") is not None
            and abs(c["yoy_pct"]) < 3 and abs(c["mom_pct"]) < 2
        ),
        key=lambda r: abs(r.get("yoy_pct") or 0),
    )[:5]

    kpis_html = "\n".join(kpi_card(k) for k in kpis)
    highlights_html = "\n".join(highlight_card(h) for h in meta.get("highlights", []))
    categories_html = "\n".join(
        category_card(cat, rows) for cat, rows in sorted(by_cat.items())
    )
    rows_html = "\n".join(commodity_row(r, price_lookup) for r in commodities)

    def bullet(r: dict, colour: str) -> str:
        return (
            f'<li class="flex items-start"><span class="mr-2 text-{colour} font-bold leading-none mt-[-2px]">•</span>'
            f'<span><b>{_html.escape(r["name"])}</b> ({_html.escape(r["category"])}): '
            f'YoY {fmt_pct(r.get("yoy_pct"))}, MoM {fmt_pct(r.get("mom_pct"))}.</span></li>'
        )
    risk_items = "".join(bullet(r, "secondary-red") for r in risks)
    opp_items = "".join(bullet(r, "accent-green") for r in opps)
    balanced_items = "".join(bullet(r, "primary-blue") for r in balanced) or (
        '<li class="text-sm text-dark-muted">No commodities matched the balanced threshold.</li>'
    )

    # HICP chart data — prefer Eurostat index (matches Sep 2025 series type).
    # Fallback to YoY % if index not fetched.
    if hicp_index:
        hicp_js = json.dumps({
            "labels": [r["month"] for r in hicp_index["series"]],
            "values": [r["index"] for r in hicp_index["series"]],
            "unit": "Index (2015 = 100)",
            "source_url": hicp_index.get("url", ""),
            "source_label": hicp_index.get("source", ""),
            "mode": "index",
        })
    else:
        hicp = bundle["hicp"]
        eu = next((s for s in hicp["series"] if s["geo"] == "European Union"), None)
        hicp_js = json.dumps({
            "labels": hicp["months"],
            "values": eu["values"] if eu else [],
            "unit": "YoY % change",
            "source_url": "",
            "source_label": "Eurostat HICP",
            "mode": "yoy",
        })

    forecast_js = json.dumps(forecast)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_html.escape(meta['title'])} — {_html.escape(meta['period'])}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
  <script>
    tailwind.config = {{
      theme: {{ extend: {{
        fontFamily: {{ sans: ['Inter', 'sans-serif'] }},
        colors: {{
          'primary-blue': '#60A5FA',
          'secondary-red': '#F87171',
          'accent-green': '#4ADE80',
          'text-warning': '#FACC15',
          'soft-red-bg': 'rgba(248,113,113,0.15)',
          'soft-green-bg': 'rgba(74,222,128,0.15)',
          'dark-bg': '#0F172A',
          'dark-card': '#1E293B',
          'dark-text': '#F8FAFC',
          'dark-muted': '#94A3B8'
        }},
        boxShadow: {{
          '3xl': '0 35px 60px -15px rgba(0,0,0,0.5)',
          'xl-dark': '0 20px 25px -5px rgba(0,0,0,0.3), 0 8px 10px -6px rgba(0,0,0,0.3)'
        }}
      }}}}
    }};
  </script>
  <style>
    body {{ background:#0F172A; font-family:Inter,sans-serif; color:#F8FAFC; }}
    .card {{ background:#1E293B; border-radius:0.75rem; padding:1.5rem; box-shadow:0 10px 15px -3px rgba(0,0,0,0.4); transition:all .2s; }}
    .modal-overlay {{ position:fixed; inset:0; background:rgba(0,0,0,0.85); display:none; align-items:center; justify-content:center; z-index:50; backdrop-filter:blur(5px); }}
    .modal-overlay.open {{ display:flex; }}
    .modal-content {{ background:#1E293B; padding:2rem; border-radius:0.75rem; width:min(900px,92vw); max-height:90vh; overflow-y:auto; }}
  </style>
</head>
<body class="p-4 sm:p-8">
  <div class="max-w-7xl mx-auto">

    <header class="mb-5">
      <h1 class="text-4xl sm:text-5xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-primary-blue to-blue-300">
        {_html.escape(meta['title'])}
      </h1>
      <p class="text-xl text-dark-muted mt-2">{_html.escape(meta['subtitle'])}</p>
      <p class="text-xs text-dark-muted mt-2">Source: {_html.escape(meta['source'])} · Period: {_html.escape(meta['period_mom'])} (MoM) / {_html.escape(meta['period_yoy'])} (YoY)</p>
    </header>

    <nav class="mb-10 flex flex-wrap gap-3 p-4 bg-dark-card rounded-xl shadow-xl-dark justify-center">
      <a href="#kpi-section" class="px-4 py-2 text-sm font-semibold text-primary-blue hover:text-white bg-dark-bg/50 rounded-lg hover:bg-primary-blue/80 transition border border-primary-blue/30">Overview</a>
      <a href="#hicp-section" class="px-4 py-2 text-sm font-semibold text-primary-blue hover:text-white bg-dark-bg/50 rounded-lg hover:bg-primary-blue/80 transition border border-primary-blue/30">HICP Trend</a>
      <a href="#explorer-section" class="px-4 py-2 text-sm font-semibold text-primary-blue hover:text-white bg-dark-bg/50 rounded-lg hover:bg-primary-blue/80 transition border border-primary-blue/30">Commodity Explorer</a>
      <a href="#strategy-section" class="px-4 py-2 text-sm font-semibold text-primary-blue hover:text-white bg-dark-bg/50 rounded-lg hover:bg-primary-blue/80 transition border border-primary-blue/30">Strategy</a>
      <a href="#references-section" class="px-4 py-2 text-sm font-semibold text-primary-blue hover:text-white bg-dark-bg/50 rounded-lg hover:bg-primary-blue/80 transition border border-primary-blue/30">References</a>
    </nav>

    <section id="kpi-section" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      {kpis_html}
    </section>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div id="hicp-section" class="lg:col-span-2 card chart-visible">
        <h2 class="text-2xl font-bold text-dark-text mb-1">12-Month EU Food Index (HICP) Trend</h2>
        <p class="text-xs text-dark-muted mb-4">Source: <a href="https://ec.europa.eu/eurostat/databrowser/view/teicp010/default/table?lang=en" target="_blank" class="text-primary-blue hover:underline">Eurostat HICP Food &amp; Non-Alcoholic Beverages</a> · Base 2015 = 100 · {_html.escape(meta.get('period', ''))}</p>
        <div class="h-80"><canvas id="hicpChart"></canvas></div>

        <!-- Trend Analysis Summary (matches Sep 2025 layout) -->
        <div class="mt-6 pt-4 border-t border-gray-700">
          <h3 class="text-xl font-bold text-dark-text mb-2 flex items-center">
            <i data-lucide="info" class="w-5 h-5 text-primary-blue mr-2"></i>
            Trend Analysis Summary
          </h3>
          <div class="text-gray-300 leading-relaxed text-sm border-l-4 border-primary-blue pl-3 py-1">
            <p>{_html.escape(meta.get('trend_analysis', 'Trend analysis not provided for this period.'))}</p>
          </div>
        </div>
      </div>

      <div class="card">
        <h2 class="text-2xl font-bold mb-4 text-dark-text flex items-center">
          <i data-lucide="bell" class="w-5 h-5 text-text-warning mr-2"></i> Executive Summary Highlights
        </h2>
        <div class="space-y-4 text-sm">
          {highlights_html}
        </div>
      </div>
    </div>

    <section id="explorer-section" class="card mt-8">
      <h2 class="text-2xl font-bold mb-4 text-dark-text">Commodity Price Explorer</h2>
      <div class="mb-6 flex items-center gap-3">
        <i data-lucide="search" class="w-5 h-5 text-dark-muted flex-shrink-0"></i>
        <input id="search" type="text" placeholder="Search {len(commodities)} commodities (e.g. beef, wheat, hazelnuts)..." class="w-full px-4 py-2 border border-gray-600 rounded-lg bg-dark-bg text-dark-text placeholder-gray-500 focus:ring-primary-blue focus:border-primary-blue transition">
        <select id="category-filter" class="px-3 py-2 border border-gray-600 rounded-lg bg-dark-bg text-dark-text focus:ring-primary-blue">
          <option value="">All categories</option>
          {"".join(f'<option value="{_html.escape(c)}">{_html.escape(c)}</option>' for c in sorted(by_cat.keys()))}
        </select>
      </div>
      <div id="category-grid" class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-6 mb-6">
        {categories_html}
      </div>
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-700">
          <thead class="bg-dark-card border-b border-gray-700 sticky top-0">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-dark-muted uppercase tracking-wider">Category</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-dark-muted uppercase tracking-wider cursor-pointer" data-sort="name">Commodity</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-dark-muted uppercase tracking-wider">Latest Price</th>
              <th class="px-4 py-3 text-center text-xs font-medium text-dark-muted uppercase tracking-wider cursor-pointer" data-sort="mom">MoM</th>
              <th class="px-4 py-3 text-center text-xs font-medium text-dark-muted uppercase tracking-wider cursor-pointer" data-sort="yoy">YoY</th>
            </tr>
          </thead>
          <tbody id="commodity-body" class="bg-dark-card divide-y divide-gray-700">
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>

    <!-- Forward-curve modal (matches Sep 2025's click-a-row behaviour). Hidden by default. -->
    <div id="forecast-modal" class="modal-overlay" onclick="if(event.target===this)closeForecast()">
      <div class="modal-content">
        <div class="flex justify-between items-start mb-4">
          <div>
            <h3 id="forecast-title" class="text-xl font-bold text-dark-text"></h3>
            <p id="forecast-subtitle" class="text-xs text-dark-muted"></p>
          </div>
          <button onclick="closeForecast()" class="text-dark-muted hover:text-white">✕</button>
        </div>
        <div class="h-80"><canvas id="forecastChart"></canvas></div>
        <p class="text-xs text-dark-muted mt-4">Source: Expana (Mintec) Q1 2026 forward curve export.</p>
      </div>
    </div>

    <section id="strategy-section" class="card mt-8">
      <h2 class="text-2xl font-bold mb-4 text-dark-text flex items-center">
        <i data-lucide="shield" class="w-5 h-5 text-accent-green mr-2"></i> Procurement Actions &amp; Strategy
      </h2>
      <div class="space-y-6">
        <div>
          <h3 class="text-xl font-bold text-secondary-red flex items-center mb-2">
            <i data-lucide="triangle-alert" class="w-5 h-5 mr-2"></i> High Risks
          </h3>
          <ul class="ml-2 space-y-2 text-sm text-gray-300">{risk_items}</ul>
        </div>
        <hr class="border-gray-700">
        <div>
          <h3 class="text-xl font-bold text-accent-green flex items-center mb-2">
            <i data-lucide="trending-up" class="w-5 h-5 mr-2"></i> Strategic Opportunities
          </h3>
          <ul class="ml-2 space-y-2 text-sm text-gray-300">{opp_items}</ul>
        </div>
        <hr class="border-gray-700">
        <div>
          <h3 class="text-xl font-bold text-primary-blue flex items-center mb-2">
            <i data-lucide="eye" class="w-5 h-5 mr-2"></i> Balanced / Monitoring
          </h3>
          <ul class="ml-2 space-y-2 text-sm text-gray-300">{balanced_items}</ul>
        </div>
      </div>
    </section>

    <section id="references-section" class="card mt-8">
      <h2 class="text-2xl font-bold mb-4 text-dark-text flex items-center">
        <i data-lucide="book-open" class="w-5 h-5 text-primary-blue mr-2"></i> References &amp; Sources
      </h2>
      <ul class="space-y-2 text-sm text-gray-300">
        <li class="flex items-start"><span class="mr-2 text-primary-blue">•</span><span><b>Eurostat HICP</b> — <a href="https://ec.europa.eu/eurostat/databrowser/view/teicp010/default/table?lang=en" target="_blank" class="text-primary-blue hover:underline">prc_hicp_midx / teicp010</a>, CP01 Food &amp; non-alcoholic beverages, EU27, base 2015 = 100.</span></li>
        <li class="flex items-start"><span class="mr-2 text-primary-blue">•</span><span><b>Expana (Mintec)</b> — Commodity Price Change Overview Report for {_html.escape(meta.get('period', ''))}: MoM {_html.escape(meta.get('period_mom', ''))}, YoY {_html.escape(meta.get('period_yoy', ''))}.</span></li>
        <li class="flex items-start"><span class="mr-2 text-primary-blue">•</span><span><b>Expana (Mintec) forward curves</b> — Q1 2026 export covering {len(forecast['commodities'])} commodities with daily forward prices.</span></li>
        <li class="flex items-start"><span class="mr-2 text-primary-blue">•</span><span>Source files live under <code>data/{period}/raw/</code>; structured JSON under <code>data/{period}/</code>; regeneration via <code>python scripts/build_html.py {period}</code>.</span></li>
      </ul>
    </section>

    <footer class="mt-12 text-xs text-dark-muted text-center pb-6">
      Built from <code>data/{period}/*.json</code>. Generated by <code>scripts/build_html.py</code>.
    </footer>
  </div>

<script>
  // --- HICP Chart (matches Sep 2025: single EU line, index values 2015=100) ---
  const hicp = {hicp_js};
  const hicpIsIndex = hicp.mode === 'index';
  new Chart(document.getElementById('hicpChart'), {{
    type: 'line',
    data: {{
      labels: hicp.labels,
      datasets: [{{
        label: hicpIsIndex ? 'EU Food HICP Index (2015=100)' : 'EU Food HICP (YoY %)',
        data: hicp.values,
        borderColor: '#60A5FA',
        backgroundColor: 'rgba(96,165,250,0.18)',
        fill: true,
        tension: 0.3,
        borderWidth: 3,
        pointRadius: 4,
        pointBackgroundColor: '#60A5FA',
        pointBorderColor: '#0F172A',
        pointBorderWidth: 2,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: ctx => hicpIsIndex
              ? ' Index: ' + ctx.parsed.y.toFixed(2)
              : ' YoY change: ' + ctx.parsed.y.toFixed(1) + '%'
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: '#94A3B8' }}, grid: {{ color: '#334155' }} }},
        y: {{
          ticks: {{
            color: '#94A3B8',
            callback: v => hicpIsIndex ? v.toFixed(1) : v + '%'
          }},
          grid: {{ color: '#334155' }},
          title: {{
            display: true,
            text: hicpIsIndex ? 'Index (2015 = 100)' : 'YoY % change',
            color: '#94A3B8'
          }}
        }}
      }}
    }}
  }});

  // --- Forward-curve modal: opens when a commodity row is clicked (Sep 2025 behaviour) ---
  const forecast = {forecast_js};
  const forecastByName = {{}};
  forecast.commodities.forEach(c => {{
    // Build lookup keyed by lowercased commodity description (loose match)
    forecastByName[c.description.toLowerCase()] = c;
    forecastByName[c.code.toLowerCase()] = c;
  }});
  const fcCtx = document.getElementById('forecastChart');
  let fcChart;
  function renderForecastModal(c) {{
    document.getElementById('forecast-title').textContent = c.description;
    document.getElementById('forecast-subtitle').textContent =
      c.unit + ' · ' + c.points.length + ' daily points · ' + c.start + ' → ' + c.end;
    if (fcChart) fcChart.destroy();
    fcChart = new Chart(fcCtx, {{
      type: 'line',
      data: {{
        labels: c.points.map(p => p.date),
        datasets: [{{
          label: c.description + ' (' + c.unit + ')',
          data: c.points.map(p => p.value),
          borderColor: '#60A5FA',
          backgroundColor: 'rgba(96,165,250,0.15)',
          fill: true, tension: 0.2, pointRadius: 0, borderWidth: 2
        }}]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ labels: {{ color: '#94A3B8' }} }} }},
        scales: {{
          x: {{ ticks: {{ color: '#94A3B8', maxTicksLimit: 12 }}, grid: {{ color: '#334155' }} }},
          y: {{ ticks: {{ color: '#94A3B8' }}, grid: {{ color: '#334155' }} }}
        }}
      }}
    }});
    document.getElementById('forecast-modal').classList.add('open');
  }}
  function closeForecast() {{
    document.getElementById('forecast-modal').classList.remove('open');
  }}
  window.closeForecast = closeForecast;

  // Wire commodity rows: if a row's commodity name maps to a forward curve, show a glyph + click opens modal.
  document.querySelectorAll('#commodity-body tr').forEach(tr => {{
    const name = tr.dataset.name;
    // Try exact + token-based loose match against forecast descriptions
    const match = forecastByName[name]
      || Object.keys(forecastByName).find(k => k.includes(name) || name.includes(k.split(' ')[0]));
    const c = match ? (forecastByName[match] || forecastByName[match.toLowerCase()]) : null;
    if (c) {{
      tr.classList.add('cursor-pointer');
      tr.title = 'Click for forward curve forecast';
      tr.addEventListener('click', () => renderForecastModal(c));
      // Append chart glyph to Commodity cell
      const cell = tr.children[1];
      cell.insertAdjacentHTML('beforeend', ' <i data-lucide="line-chart" class="w-4 h-4 ml-1 inline text-accent-green"></i>');
    }}
  }});

  // --- Explorer filter ---
  const search = document.getElementById('search');
  const catSel = document.getElementById('category-filter');
  function applyFilter() {{
    const q = search.value.toLowerCase();
    const cat = catSel.value;
    document.querySelectorAll('#commodity-body tr').forEach(tr => {{
      const name = tr.dataset.name, c = tr.dataset.category;
      const hit = (!q || name.includes(q)) && (!cat || c === cat);
      tr.style.display = hit ? '' : 'none';
    }});
  }}
  search.addEventListener('input', applyFilter);
  catSel.addEventListener('change', applyFilter);

  // Category card click → filter the table by that category
  window.showCategory = function(cat) {{
    catSel.value = cat; applyFilter();
    document.getElementById('explorer-section').scrollIntoView({{ behavior:'smooth' }});
  }};

  // --- Sort ---
  let sortState = {{ key: null, dir: 1 }};
  document.querySelectorAll('th[data-sort]').forEach(th => {{
    th.addEventListener('click', () => {{
      const key = th.dataset.sort;
      if (sortState.key === key) sortState.dir = -sortState.dir; else {{ sortState.key = key; sortState.dir = 1; }}
      const body = document.getElementById('commodity-body');
      const rows = Array.from(body.querySelectorAll('tr'));
      rows.sort((a, b) => {{
        const av = valueFor(a, key), bv = valueFor(b, key);
        if (av === bv) return 0;
        if (av === null) return 1;
        if (bv === null) return -1;
        return av > bv ? sortState.dir : -sortState.dir;
      }});
      rows.forEach(r => body.appendChild(r));
    }});
  }});
  function valueFor(tr, key) {{
    if (key === 'name') return tr.dataset.name;
    // Columns: 0 Category, 1 Commodity, 2 Price, 3 MoM, 4 YoY
    const col = key === 'mom' ? 3 : 4;
    const txt = tr.children[col].innerText.trim().replace('%','').replace('+','');
    const n = parseFloat(txt);
    return isNaN(n) ? null : n;
  }}

  lucide.createIcons();
</script>
</body>
</html>
"""


def main() -> None:
    period = sys.argv[1] if len(sys.argv) > 1 else "2026-04"
    meta = json.loads((ROOT / "data" / period / "meta.json").read_text())
    html = build(period)
    out_path = ROOT / "public" / meta["output_html"].lstrip("/")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    print(f"Wrote {out_path.relative_to(ROOT)} ({len(html):,} chars)")


if __name__ == "__main__":
    main()
