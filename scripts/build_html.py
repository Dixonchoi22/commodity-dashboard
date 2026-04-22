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
    return {
        "meta": json.loads((p / "meta.json").read_text()),
        "commodities": json.loads((p / "commodities.json").read_text()),
        "hicp": json.loads((p / "hicp.json").read_text()),
        "forecast": json.loads((p / "forecast.json").read_text()),
        "commentary": json.loads((p / "commentary.json").read_text()),
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


def commodity_row(r: dict) -> str:
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
    return f"""
<tr class="hover:bg-dark-bg transition duration-150 border-l-4 {border_tone}" data-category="{_html.escape(r['category'])}" data-name="{_html.escape(r['name'].lower())}">
  <td class="px-4 py-3 whitespace-nowrap text-sm font-semibold text-dark-muted">{_html.escape(r['category'])}</td>
  <td class="px-4 py-3 whitespace-nowrap text-sm font-semibold text-dark-text">{_html.escape(r['name'])}</td>
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
    hicp = bundle["hicp"]
    forecast = bundle["forecast"]

    # Group commodities by category
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in commodities:
        by_cat[r["category"]].append(r)

    # HICP: EU aggregate series as line chart data
    eu_series = next((s for s in hicp["series"] if s["geo"] == "European Union"), None)

    # Top risks / opportunities for Procurement Actions
    risks = sorted(commodities, key=lambda r: r.get("yoy_pct") or 0, reverse=True)[:5]
    opps = sorted(commodities, key=lambda r: r.get("yoy_pct") or 0)[:5]

    kpis_html = "\n".join(kpi_card(k) for k in meta["kpis"])
    highlights_html = "\n".join(highlight_card(h) for h in meta["highlights"])
    categories_html = "\n".join(
        category_card(cat, rows) for cat, rows in sorted(by_cat.items())
    )
    rows_html = "\n".join(commodity_row(r) for r in commodities)

    risk_items = "".join(
        f'<li class="flex items-start"><span class="mr-2 text-secondary-red font-bold leading-none mt-[-2px]">•</span><span><b>{_html.escape(r["name"])}</b> ({_html.escape(r["category"])}): YoY {fmt_pct(r.get("yoy_pct"))}, MoM {fmt_pct(r.get("mom_pct"))}.</span></li>'
        for r in risks
    )
    opp_items = "".join(
        f'<li class="flex items-start"><span class="mr-2 text-accent-green font-bold leading-none mt-[-2px]">•</span><span><b>{_html.escape(r["name"])}</b> ({_html.escape(r["category"])}): YoY {fmt_pct(r.get("yoy_pct"))}, MoM {fmt_pct(r.get("mom_pct"))}.</span></li>'
        for r in opps
    )

    # HICP: match Sep 2025's single-line "12-Month EU Food HICP Trend" style.
    # Our data is YoY % change by country (Eurostat HICP), so we plot the EU
    # aggregate only and let the subtitle/axis make the unit clear.
    eu_hicp_values = eu_series["values"] if eu_series else []
    hicp_js = json.dumps({
        "labels": hicp["months"],
        "value": eu_hicp_values,
        "unit": hicp["unit"],
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
      <a href="#forecast-section" class="px-4 py-2 text-sm font-semibold text-primary-blue hover:text-white bg-dark-bg/50 rounded-lg hover:bg-primary-blue/80 transition border border-primary-blue/30">Forward Curves</a>
      <a href="#strategy-section" class="px-4 py-2 text-sm font-semibold text-primary-blue hover:text-white bg-dark-bg/50 rounded-lg hover:bg-primary-blue/80 transition border border-primary-blue/30">Strategy</a>
    </nav>

    <section id="kpi-section" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      {kpis_html}
    </section>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div id="hicp-section" class="lg:col-span-2 card chart-visible">
        <h2 class="text-2xl font-bold text-dark-text mb-1">12-Month EU Food Index (HICP) Trend</h2>
        <p class="text-xs text-dark-muted mb-4">Source: <a href="https://ec.europa.eu/eurostat/databrowser/view/teicp010/default/table?lang=en" target="_blank" class="text-primary-blue hover:underline">Eurostat HICP Food and Beverages</a> &middot; {_html.escape(meta.get('period', ''))}</p>
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

    <section id="forecast-section" class="card mt-8">
      <h2 class="text-2xl font-bold mb-4 text-dark-text">Forward Curves (Q2 2026+)</h2>
      <p class="text-xs text-dark-muted mb-4">Source: Expana (Mintec) Q1 2026 forecast export</p>
      <div class="flex flex-wrap gap-2 mb-4" id="forecast-buttons"></div>
      <div class="h-96"><canvas id="forecastChart"></canvas></div>
    </section>

    <section id="strategy-section" class="card mt-8">
      <h2 class="text-2xl font-bold mb-4 text-dark-text flex items-center">
        <i data-lucide="shield" class="w-5 h-5 text-accent-green mr-2"></i> Procurement Actions &amp; Strategy
      </h2>
      <div class="space-y-6">
        <div>
          <h3 class="text-xl font-bold text-secondary-red flex items-center mb-2">
            <i data-lucide="triangle-alert" class="w-5 h-5 mr-2"></i> Top 5 YoY Risks
          </h3>
          <ul class="ml-2 space-y-2 text-sm text-gray-300">{risk_items}</ul>
        </div>
        <hr class="border-gray-700">
        <div>
          <h3 class="text-xl font-bold text-accent-green flex items-center mb-2">
            <i data-lucide="trending-down" class="w-5 h-5 mr-2"></i> Top 5 YoY Opportunities
          </h3>
          <ul class="ml-2 space-y-2 text-sm text-gray-300">{opp_items}</ul>
        </div>
      </div>
    </section>

    <footer class="mt-12 text-xs text-dark-muted text-center pb-6">
      Built from <code>data/{period}/*.json</code>. Generated by <code>scripts/build_html.py</code>.
    </footer>
  </div>

<script>
  // --- HICP Chart: single EU line, Sep 2025-style ---
  const hicp = {hicp_js};
  new Chart(document.getElementById('hicpChart'), {{
    type: 'line',
    data: {{
      labels: hicp.labels,
      datasets: [{{
        label: 'EU Food HICP (YoY %)',
        data: hicp.value,
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
            label: ctx => ' YoY change: ' + ctx.parsed.y.toFixed(1) + '%'
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: '#94A3B8' }}, grid: {{ color: '#334155' }} }},
        y: {{
          ticks: {{ color: '#94A3B8', callback: v => v + '%' }},
          grid: {{ color: '#334155' }},
          title: {{ display: true, text: 'YoY % change', color: '#94A3B8' }}
        }}
      }}
    }}
  }});

  // --- Forward curves ---
  const forecast = {forecast_js};
  const fcCtx = document.getElementById('forecastChart');
  let fcChart;
  function renderForecast(idx) {{
    const c = forecast.commodities[idx];
    if (fcChart) fcChart.destroy();
    fcChart = new Chart(fcCtx, {{
      type: 'line',
      data: {{
        labels: c.points.map(p => p.date),
        datasets: [{{
          label: c.description + ' (' + c.unit + ')',
          data: c.points.map(p => p.value),
          borderColor: '#60A5FA',
          backgroundColor: 'rgba(96,165,250,0.1)',
          fill: true, tension: 0.2, pointRadius: 0
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
  }}
  const btnRoot = document.getElementById('forecast-buttons');
  forecast.commodities.forEach((c, i) => {{
    const b = document.createElement('button');
    b.textContent = c.code;
    b.title = c.description;
    b.className = 'px-3 py-1 text-xs font-semibold rounded-lg border border-primary-blue/30 text-primary-blue hover:bg-primary-blue/20 transition';
    b.onclick = () => renderForecast(i);
    btnRoot.appendChild(b);
  }});
  renderForecast(0);

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

  // Category click → filter by category
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
    const col = key === 'mom' ? 2 : 3;
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
