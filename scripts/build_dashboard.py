"""Build a master dashboard HTML that wraps all period reports with a top
period switcher bar. Reads data/manifest.json and embeds each report as an
iframe so each period's HTML remains self-contained and standalone.

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


def build() -> str:
    manifest = json.loads(MANIFEST.read_text())
    reports = sorted(manifest["reports"], key=lambda r: r["slug"], reverse=True)
    default = reports[0]["slug"]

    buttons = "\n".join(
        f"""
        <button data-slug="{_html.escape(r['slug'])}" data-src="{_html.escape(r['html'].lstrip('/'))}"
                class="period-btn px-4 py-2 text-sm font-semibold rounded-lg border transition whitespace-nowrap"
                onclick="selectPeriod('{_html.escape(r['slug'])}')">
          {_html.escape(month_label(r['slug']))}
        </button>"""
        for r in reports
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Commodity Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0F172A;
      --card: #1E293B;
      --text: #F8FAFC;
      --muted: #94A3B8;
      --primary: #60A5FA;
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
      padding: 1rem 1.5rem;
      border-bottom: 1px solid #334155;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      flex-shrink: 0;
    }}
    .header-inner {{
      max-width: 80rem;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: center;
      justify-content: space-between;
    }}
    h1 {{
      font-size: 1.125rem;
      font-weight: 800;
      margin: 0;
      background: linear-gradient(to right, var(--primary), #93c5fd);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
      letter-spacing: -0.025em;
    }}
    .subtitle {{ color: var(--muted); font-size: 0.75rem; margin-top: 2px; }}
    .period-bar {{
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }}
    .period-btn {{
      background: rgba(15,23,42,0.5);
      color: var(--primary);
      border-color: var(--border);
      cursor: pointer;
      font-family: inherit;
    }}
    .period-btn:hover {{ background: rgba(96,165,250,0.2); }}
    .period-btn.active {{
      background: var(--primary);
      color: #0F172A;
      border-color: var(--primary);
    }}
    main {{
      flex: 1;
      min-height: 0;
      display: flex;
    }}
    iframe {{
      flex: 1;
      width: 100%;
      height: 100%;
      border: 0;
      background: var(--bg);
    }}
    .loading {{
      position: absolute;
      top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      color: var(--muted);
      font-size: 0.875rem;
    }}
  </style>
</head>
<body>

  <header>
    <div class="header-inner">
      <div>
        <h1>Commodity Dashboard</h1>
        <p class="subtitle">Monthly commodity intelligence · {len(reports)} report(s)</p>
      </div>
      <div class="period-bar">
        {buttons}
      </div>
    </div>
  </header>

  <main>
    <iframe id="report-frame" title="Report" src=""></iframe>
  </main>

  <script>
    const defaultSlug = {json.dumps(default)};
    function selectPeriod(slug) {{
      const btn = document.querySelector('.period-btn[data-slug="' + slug + '"]');
      if (!btn) return;
      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('report-frame').src = btn.dataset.src;
      history.replaceState(null, '', '?period=' + slug);
    }}
    // Initial period: from ?period= query, else most recent
    const params = new URLSearchParams(window.location.search);
    const initial = params.get('period') || defaultSlug;
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
