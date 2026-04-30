"""Build a master dashboard HTML that wraps all period reports with a top
period switcher bar. Reads data/manifest.json and each period's meta.json
so the current period (and its MoM / YoY comparison windows) are always
clearly labeled.

Each report HTML stays self-contained — the master shell just orchestrates
them via an iframe.

Usage:
  python scripts/build_dashboard.py
"""
from __future__ import annotations

import html as _html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
OUT = ROOT / "public" / "reports" / "index.html"


def month_label(slug: str) -> str:
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    try:
        y, m = slug.split("-")
        return f"{months[int(m) - 1]} {y}"
    except Exception:
        return slug


def load_meta(slug: str) -> dict:
    path = ROOT / "data" / slug / "meta.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def build() -> str:
    manifest = json.loads(MANIFEST.read_text())
    reports = sorted(manifest["reports"], key=lambda r: r["slug"], reverse=True)
    default = reports[0]["slug"]

    # Bundle period info for the client-side switcher. We inline the full HTML
    # of each report into an iframe via srcdoc so that opening index.html via
    # file:// still works — browsers block cross-file iframe src but allow
    # srcdoc because it's not a separate resource load.
    periods_js = {}
    for r in reports:
        meta = load_meta(r["slug"])
        html_path = ROOT / "public" / r["html"].lstrip("/")
        srcdoc = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        periods_js[r["slug"]] = {
            "label": month_label(r["slug"]),
            "title": meta.get("title", r.get("title", "")),
            "period": meta.get("period", month_label(r["slug"])),
            "period_mom": meta.get("period_mom", ""),
            "period_yoy": meta.get("period_yoy", ""),
            "region": meta.get("region", r.get("region", "")),
            "srcdoc": srcdoc,
            "legacy": bool(meta.get("legacy")),
        }

    buttons = "\n".join(
        f"""
        <button data-slug="{_html.escape(r['slug'])}"
                class="period-btn"
                onclick="selectPeriod('{_html.escape(r['slug'])}')">
          <span class="period-btn-month">{_html.escape(month_label(r['slug']))}</span>
          <span class="period-btn-hint">{"latest" if r["slug"] == default else ""}</span>
        </button>"""
        for r in reports
    )

    # Escape "</" in the JSON blob so the browser's HTML parser doesn't
    # mistake an inlined </script> (e.g. inside a legacy report's srcdoc)
    # for the end of our outer <script> tag. "<\/" is legal inside JSON
    # strings and JS unescapes it back to "</".
    periods_json = json.dumps(periods_js).replace("</", "<\\/")

    import datetime as _dt
    build_ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <!-- build: {build_ts} -->
  <meta http-equiv="cache-control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="pragma" content="no-cache">
  <meta http-equiv="expires" content="0">
  <title>Commodity Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0F172A;
      --card: #1E293B;
      --card-2: #273449;
      --text: #F8FAFC;
      --muted: #94A3B8;
      --primary: #60A5FA;
      --accent: #4ADE80;
      --warn: #FACC15;
      --border: rgba(96,165,250,0.3);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0; padding: 0; height: 100%;
      background: var(--bg); color: var(--text);
      font-family: Inter, system-ui, sans-serif;
    }}
    body {{ display: flex; flex-direction: column; }}

    header {{
      background: var(--card);
      border-bottom: 1px solid #334155;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      flex-shrink: 0;
    }}
    .header-inner {{
      max-width: 80rem;
      margin: 0 auto;
      padding: 1rem 1.5rem;
      display: flex;
      flex-wrap: wrap;
      gap: 1rem 2rem;
      align-items: center;
      justify-content: space-between;
    }}
    .title-block h1 {{
      font-size: 1.125rem;
      font-weight: 800;
      margin: 0;
      background: linear-gradient(to right, var(--primary), #93c5fd);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
      letter-spacing: -0.025em;
    }}
    .title-block .subtitle {{ color: var(--muted); font-size: 0.75rem; margin-top: 2px; }}

    /* Period switcher */
    .period-bar {{ display: flex; gap: 0.5rem; flex-wrap: wrap; }}
    .period-btn {{
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      min-width: 130px;
      padding: 0.5rem 1rem;
      border-radius: 0.5rem;
      border: 1px solid var(--border);
      background: rgba(15,23,42,0.5);
      color: var(--primary);
      font-family: inherit;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .period-btn:hover {{ background: rgba(96,165,250,0.2); }}
    .period-btn.active {{
      background: var(--primary);
      color: #0F172A;
      border-color: var(--primary);
      box-shadow: 0 4px 14px rgba(96,165,250,0.45);
      transform: translateY(-1px);
    }}
    .period-btn-month {{ font-size: 0.95rem; letter-spacing: -0.01em; }}
    .period-btn-hint {{
      font-size: 0.625rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      opacity: 0.75;
      margin-top: 2px;
      min-height: 0.75rem;
    }}
    .period-btn.active .period-btn-hint {{ opacity: 1; }}

    /* Currently-viewing banner: keeps the active period impossible to miss */
    .viewing-banner {{
      background: linear-gradient(to right, rgba(96,165,250,0.12), rgba(96,165,250,0.02));
      border-top: 1px solid rgba(96,165,250,0.25);
      border-bottom: 1px solid rgba(96,165,250,0.25);
      padding: 0.75rem 1.5rem;
      flex-shrink: 0;
    }}
    .viewing-inner {{
      max-width: 80rem;
      margin: 0 auto;
      display: flex;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }}
    .viewing-tag {{
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      font-size: 0.625rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--primary);
      background: rgba(96,165,250,0.18);
      padding: 0.25rem 0.5rem;
      border-radius: 0.25rem;
    }}
    .viewing-tag::before {{
      content: '';
      width: 6px; height: 6px; border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 0 3px rgba(74,222,128,0.25);
    }}
    .viewing-title {{ font-size: 1rem; font-weight: 700; color: var(--text); }}
    .viewing-period {{
      font-size: 1.5rem; font-weight: 800; color: var(--primary);
      letter-spacing: -0.02em;
    }}
    .viewing-meta {{ font-size: 0.75rem; color: var(--muted); }}
    .viewing-meta b {{ color: var(--text); font-weight: 600; }}
    .viewing-legacy {{
      display: inline-flex; align-items: center; gap: 0.375rem;
      background: rgba(250,204,21,0.15);
      color: var(--warn);
      border: 1px solid rgba(250,204,21,0.4);
      padding: 0.2rem 0.5rem;
      border-radius: 0.25rem;
      font-size: 0.625rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    main {{ flex: 1; min-height: 0; display: flex; }}
    iframe {{ flex: 1; width: 100%; height: 100%; border: 0; background: var(--bg); }}
  </style>
</head>
<body>

  <header>
    <div class="header-inner">
      <div class="title-block">
        <h1>Commodity Dashboard</h1>
        <p class="subtitle">Monthly intelligence · {len(reports)} report(s) available</p>
      </div>
      <div class="period-bar" role="tablist" aria-label="Select report period">
        {buttons}
      </div>
    </div>
  </header>

  <!-- Currently viewing banner: big, obvious, tells the reader exactly which period is on screen -->
  <div class="viewing-banner">
    <div class="viewing-inner">
      <span class="viewing-tag">Now viewing</span>
      <span class="viewing-title" id="v-title"></span>
      <span class="viewing-period" id="v-period"></span>
      <span class="viewing-meta" id="v-meta"></span>
      <span class="viewing-legacy" id="v-legacy" style="display:none">Legacy snapshot</span>
    </div>
  </div>

  <main>
    <iframe id="report-frame" title="Report" src=""></iframe>
  </main>

  <script>
    const PERIODS = {periods_json};
    const DEFAULT = {json.dumps(default)};

    function selectPeriod(slug) {{
      const p = PERIODS[slug];
      if (!p) return;

      // Button state
      document.querySelectorAll('.period-btn').forEach(b => {{
        b.classList.toggle('active', b.dataset.slug === slug);
        b.setAttribute('aria-selected', b.dataset.slug === slug ? 'true' : 'false');
      }});

      // Banner
      document.getElementById('v-title').textContent = p.title || 'Report';
      document.getElementById('v-period').textContent = p.period;
      let meta = '';
      if (p.region) meta += p.region;
      if (p.period_mom) meta += (meta ? ' · ' : '') + 'MoM: ' + p.period_mom;
      if (p.period_yoy) meta += (meta ? ' · ' : '') + 'YoY: ' + p.period_yoy;
      document.getElementById('v-meta').innerHTML = meta;
      document.getElementById('v-legacy').style.display = p.legacy ? '' : 'none';

      // Report frame & URL — srcdoc lets the nested HTML load under file://
      const frame = document.getElementById('report-frame');
      frame.srcdoc = p.srcdoc;
      document.title = 'Commodity Dashboard — ' + p.period;
      history.replaceState(null, '', '?period=' + slug);
    }}

    const params = new URLSearchParams(window.location.search);
    const initial = params.get('period') && PERIODS[params.get('period')]
      ? params.get('period')
      : DEFAULT;
    selectPeriod(initial);
  </script>

</body>
</html>
"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build())
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
