"""Build the master dashboard: a quarter-picker landing menu + in-report switcher.

Two things get produced:

1. **In-report switcher shell** — injected right after ``<body>`` of every
   period HTML under ``public/reports/``. It shows the "Commodity Dashboard"
   header, an "All quarters" link back to the menu, a row of quarter buttons
   (sibling ``<a href>`` links, normal full-page navigation — no iframes),
   and a "Now viewing" banner. With only one quarter the button row collapses.

2. **Landing menu** — ``public/reports/index.html`` is a standalone page that
   lists every registered quarter as a card (quarter badge, title, region,
   trend snippet, highlight chips, "Open full report"). This is the page the
   GitHub Pages root URL lands on, so users pick a quarter first.

Reports are keyed by a ``YYYY-MM`` slug (the cover month of the Expana PDF).
The month maps to a calendar quarter: Jan–Mar → Q1, Apr–Jun → Q2,
Jul–Sep → Q3, Oct–Dec → Q4.

Usage:
  python scripts/build_dashboard.py
"""
from __future__ import annotations

import html as _html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
REPORTS_DIR = ROOT / "public" / "reports"
INDEX_OUT = REPORTS_DIR / "index.html"

SWITCHER_MARKER = "data-cd-switcher"

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def month_label(slug: str) -> str:
    try:
        y, m = slug.split("-")
        return f"{_MONTHS[int(m) - 1]} {y}"
    except Exception:
        return slug


def quarter_of(slug: str) -> tuple[int, int]:
    """Return (year, quarter) for a YYYY-MM slug. Falls back to (0, 0)."""
    try:
        y, m = slug.split("-")
        return int(y), (int(m) - 1) // 3 + 1
    except Exception:
        return 0, 0


def quarter_label(slug: str) -> str:
    """'2026-04' -> 'Q2 2026'. Falls back to the raw slug."""
    y, q = quarter_of(slug)
    if not y:
        return slug
    return f"Q{q} {y}"


def load_meta(slug: str) -> dict:
    path = ROOT / "data" / slug / "meta.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _load_json(slug: str, name: str):
    path = ROOT / "data" / slug / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def glance_stats(slug: str) -> dict:
    """Compact 'at a glance' numbers for a quarter card: EU Food HICP level
    + YoY, and how many commodities are big risks (YoY >= +25%) vs
    opportunities (YoY <= -25%)."""
    hicp = _load_json(slug, "hicp_index.json") or {}
    commodities = _load_json(slug, "commodities.json") or {}
    rows = commodities.get("rows", []) if isinstance(commodities, dict) else []

    def _num(v):
        return v if isinstance(v, (int, float)) else None

    risks = sum(1 for r in rows if (_num(r.get("yoy_pct")) or 0) >= 25)
    opps = sum(1 for r in rows if (_num(r.get("yoy_pct")) or 0) <= -25)
    return {
        "hicp_level": hicp.get("latest_index"),
        "hicp_month": hicp.get("latest_month"),
        "hicp_yoy": hicp.get("yoy_pct_last_12"),
        "risks": risks,
        "opps": opps,
        "n": len(rows),
    }


# --------------------------------------------------------------------------- #
# In-report switcher shell
# --------------------------------------------------------------------------- #
def shell_html(reports: list[dict], active_slug: str, default_slug: str) -> str:
    """Master shell (header + quarter switcher + viewing banner) for one
    active period. Sibling-file <a href> buttons — full-page navigation."""
    active_meta = load_meta(active_slug)
    n = len(reports)

    if n > 1:
        btns = []
        for r in reports:
            slug = r["slug"]
            href = Path(r["html"]).name
            is_active = slug == active_slug
            is_latest = slug == default_slug
            active_cls = " active" if is_active else ""
            hint = "latest" if is_latest else ""
            btns.append(
                f'<a class="period-btn{active_cls}" href="{_html.escape(href)}" '
                f'data-slug="{_html.escape(slug)}" '
                f'aria-current="{"page" if is_active else "false"}">'
                f'<span class="period-btn-month">{_html.escape(quarter_label(slug))}</span>'
                f'<span class="period-btn-hint">{_html.escape(hint)}</span>'
                f"</a>"
            )
        period_bar_html = (
            f'<div class="cd-period-bar" role="tablist" '
            f'aria-label="Select report quarter">{"".join(btns)}</div>'
        )
    else:
        period_bar_html = ""

    title = active_meta.get("title", "")
    period = active_meta.get("period", month_label(active_slug))
    region = active_meta.get("region", "")
    mom = active_meta.get("period_mom", "")
    yoy = active_meta.get("period_yoy", "")
    legacy = bool(active_meta.get("legacy"))
    meta_bits = []
    if region: meta_bits.append(_html.escape(region))
    if mom:    meta_bits.append("MoM: " + _html.escape(mom))
    if yoy:    meta_bits.append("YoY: " + _html.escape(yoy))
    meta_str = " · ".join(meta_bits)
    legacy_html = (
        '<span class="cd-viewing-legacy">Legacy snapshot</span>' if legacy else ""
    )
    subtitle = (
        f"Quarterly intelligence · {n} report(s) available" if n > 1
        else "Quarterly intelligence"
    )
    quarter_badge = quarter_label(active_slug)

    return f"""
<div {SWITCHER_MARKER} class="cd-shell" style="margin: -1rem -1rem 1.5rem">
  <style>
    .cd-shell {{
      font-family: Inter, system-ui, sans-serif;
      color: #F8FAFC;
    }}
    @media (min-width: 640px) {{
      [{SWITCHER_MARKER}].cd-shell {{ margin: -2rem -2rem 2rem !important; }}
    }}
    .cd-shell * {{ box-sizing: border-box; }}
    .cd-shell-header {{
      background: #1E293B;
      border-bottom: 1px solid #334155;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }}
    .cd-header-inner {{
      max-width: 80rem; margin: 0 auto;
      padding: 1rem 1.5rem;
      display: flex; flex-wrap: wrap;
      gap: 1rem 2rem;
      align-items: center; justify-content: space-between;
    }}
    .cd-title-block {{ display: flex; align-items: center; gap: 1rem; }}
    .cd-home-link {{
      display: inline-flex; align-items: center; gap: 0.35rem;
      font-size: 0.75rem; font-weight: 600; text-decoration: none;
      color: #60A5FA; border: 1px solid rgba(96,165,250,0.3);
      background: rgba(15,23,42,0.5); padding: 0.4rem 0.7rem;
      border-radius: 0.5rem; transition: all 0.15s; white-space: nowrap;
    }}
    .cd-home-link:hover {{ background: rgba(96,165,250,0.2); }}
    .cd-title-block h1 {{
      font-size: 1.125rem; font-weight: 800; margin: 0;
      background: linear-gradient(to right, #60A5FA, #93c5fd);
      -webkit-background-clip: text; background-clip: text; color: transparent;
      letter-spacing: -0.025em;
    }}
    .cd-title-block .cd-subtitle {{
      color: #94A3B8; font-size: 0.75rem; margin: 2px 0 0;
    }}
    .cd-period-bar {{ display: flex; gap: 0.5rem; flex-wrap: wrap; }}
    .cd-shell .period-btn {{
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      min-width: 120px;
      padding: 0.5rem 1rem;
      border-radius: 0.5rem;
      border: 1px solid rgba(96,165,250,0.3);
      background: rgba(15,23,42,0.5);
      color: #60A5FA;
      font-family: inherit; font-size: 0.875rem; font-weight: 600;
      cursor: pointer; text-decoration: none;
      transition: all 0.15s;
    }}
    .cd-shell .period-btn:hover {{ background: rgba(96,165,250,0.2); }}
    .cd-shell .period-btn.active {{
      background: #60A5FA; color: #0F172A; border-color: #60A5FA;
      box-shadow: 0 4px 14px rgba(96,165,250,0.45);
      transform: translateY(-1px);
    }}
    .cd-shell .period-btn-month {{ font-size: 0.95rem; letter-spacing: -0.01em; }}
    .cd-shell .period-btn-hint {{
      font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.08em;
      opacity: 0.75; margin-top: 2px; min-height: 0.75rem;
    }}
    .cd-shell .period-btn.active .period-btn-hint {{ opacity: 1; }}
    .cd-viewing-banner {{
      background: linear-gradient(to right, rgba(96,165,250,0.12), rgba(96,165,250,0.02));
      border-bottom: 1px solid rgba(96,165,250,0.25);
      padding: 0.75rem 1.5rem;
    }}
    .cd-viewing-inner {{
      max-width: 80rem; margin: 0 auto;
      display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
    }}
    .cd-viewing-tag {{
      display: inline-flex; align-items: center; gap: 0.375rem;
      font-size: 0.625rem; font-weight: 700; letter-spacing: 0.1em;
      text-transform: uppercase; color: #60A5FA;
      background: rgba(96,165,250,0.18);
      padding: 0.25rem 0.5rem; border-radius: 0.25rem;
    }}
    .cd-viewing-tag::before {{
      content: ""; width: 6px; height: 6px; border-radius: 50%;
      background: #4ADE80; box-shadow: 0 0 0 3px rgba(74,222,128,0.25);
    }}
    .cd-viewing-quarter {{
      font-size: 0.625rem; font-weight: 700; letter-spacing: 0.1em;
      text-transform: uppercase; color: #0F172A; background: #60A5FA;
      padding: 0.25rem 0.5rem; border-radius: 0.25rem;
    }}
    .cd-viewing-title {{ font-size: 1rem; font-weight: 700; color: #F8FAFC; }}
    .cd-viewing-period {{
      font-size: 1.5rem; font-weight: 800; color: #60A5FA; letter-spacing: -0.02em;
    }}
    .cd-viewing-meta {{ font-size: 0.75rem; color: #94A3B8; }}
    .cd-viewing-legacy {{
      display: inline-flex; align-items: center; gap: 0.375rem;
      background: rgba(250,204,21,0.15); color: #FACC15;
      border: 1px solid rgba(250,204,21,0.4);
      padding: 0.2rem 0.5rem; border-radius: 0.25rem;
      font-size: 0.625rem; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
  </style>
  <div class="cd-shell-header">
    <div class="cd-header-inner">
      <div class="cd-title-block">
        <a class="cd-home-link" href="index.html" title="Back to all quarters">&larr; All quarters</a>
        <div>
          <h1>Procurement PMO - Europe</h1>
          <p class="cd-subtitle">Strategic Procurement &amp; Logistics &middot; {subtitle}</p>
        </div>
      </div>
      {period_bar_html}
    </div>
  </div>
  <div class="cd-viewing-banner">
    <div class="cd-viewing-inner">
      <span class="cd-viewing-tag">Now viewing</span>
      <span class="cd-viewing-quarter">{_html.escape(quarter_badge)}</span>
      <span class="cd-viewing-title">{_html.escape(title)}</span>
      <span class="cd-viewing-period">{_html.escape(period)}</span>
      <span class="cd-viewing-meta">{meta_str}</span>
      {legacy_html}
    </div>
  </div>
</div><!--/cd-switcher-->
"""


def strip_shell(period_html: str) -> str:
    """Remove any previously injected shell block from the period HTML."""
    return re.sub(
        r"\s*<div [^>]*" + re.escape(SWITCHER_MARKER) + r".*?<!--/cd-switcher-->\s*",
        "",
        period_html,
        count=1,
        flags=re.DOTALL,
    )


def inject_shell(period_html: str, banner: str) -> str:
    """Insert the shell immediately after <body...>. Pre-strips any
    existing block so the operation is idempotent."""
    period_html = strip_shell(period_html)

    def _insert(match: re.Match) -> str:
        return match.group(0) + "\n" + banner + "\n"

    new_html, n = re.subn(r"<body[^>]*>", _insert, period_html, count=1)
    if n == 0:
        return banner + period_html
    return new_html


# --------------------------------------------------------------------------- #
# Landing menu (index.html)
# --------------------------------------------------------------------------- #
_HL_TONES = {
    "red":   ("#F87171", "rgba(248,113,113,0.15)"),
    "green": ("#4ADE80", "rgba(74,222,128,0.15)"),
    "blue":  ("#60A5FA", "rgba(96,165,250,0.15)"),
}


def _card_html(r: dict, is_latest: bool) -> str:
    slug = r["slug"]
    href = Path(r["html"]).name
    meta = load_meta(slug)
    title = meta.get("title", r.get("title", "Commodity Intelligence"))
    period = meta.get("period", r.get("period", month_label(slug)))
    region = meta.get("region", r.get("region", ""))
    qlabel = quarter_label(slug)
    legacy = bool(meta.get("legacy"))
    trend = (meta.get("trend_analysis") or "").strip()
    if len(trend) > 240:
        trend = trend[:237].rstrip() + "…"

    latest_ribbon = '<span class="card-latest">Latest</span>' if is_latest else ""
    legacy_ribbon = '<span class="card-legacy">Legacy</span>' if legacy else ""

    chips = []
    for h in meta.get("highlights", [])[:3]:
        colour, bg = _HL_TONES.get(h.get("tone", "blue"), _HL_TONES["blue"])
        label = _html.escape(h.get("label", ""))
        chips.append(
            f'<span class="chip" style="color:{colour};background:{bg};'
            f'border-color:{colour}55">{label}</span>'
        )
    chips_html = f'<div class="card-chips">{"".join(chips)}</div>' if chips else ""

    trend_html = f'<p class="card-trend">{_html.escape(trend)}</p>' if trend else ""
    region_html = (
        f'<span class="card-region">{_html.escape(region)}</span>' if region else ""
    )

    # --- "At a glance" strip: HICP level + YoY (diverging: up=risk warm,
    # down=opportunity cool) and a risk/opportunity commodity count. ---
    g = glance_stats(slug)
    glance_html = ""
    if not legacy and (g["hicp_level"] is not None or g["n"]):
        items = []
        if g["hicp_level"] is not None:
            yoy = g["hicp_yoy"]
            if isinstance(yoy, (int, float)):
                up = yoy >= 0
                arrow = "▲" if up else "▼"
                cls = "up" if up else "down"
                yoy_html = f'<em class="g-delta {cls}">{arrow} {yoy:+.1f}% YoY</em>'
            else:
                yoy_html = ""
            items.append(
                f'<div class="g-item"><span class="g-k">EU Food HICP</span>'
                f'<span class="g-v">{g["hicp_level"]:.1f} {yoy_html}</span></div>'
            )
        if g["n"]:
            items.append(
                f'<div class="g-item"><span class="g-k">Risks / Opportunities '
                f'<span class="g-hint">(YoY &plusmn;25%)</span></span>'
                f'<span class="g-v"><em class="g-delta up">&#9650; {g["risks"]} risk</em>'
                f'<span class="g-sep">&middot;</span>'
                f'<em class="g-delta down">&#9660; {g["opps"]} opp</em></span></div>'
            )
        glance_html = f'<div class="card-glance">{"".join(items)}</div>'

    return f"""
      <a class="card" href="{_html.escape(href)}">
        <div class="card-top">
          <span class="card-quarter">{_html.escape(qlabel)}</span>
          {latest_ribbon}{legacy_ribbon}
        </div>
        <h2 class="card-title">{_html.escape(title)}</h2>
        <div class="card-sub">
          <span class="card-period">{_html.escape(period)}</span>
          {region_html}
        </div>
        {glance_html}
        {trend_html}
        {chips_html}
        <span class="card-cta">Open full report &rarr;</span>
      </a>"""


def build_index(reports: list[dict], default_slug: str) -> str:
    """Standalone quarter-picker landing page."""
    # Group cards by year (descending), quarters descending within a year.
    by_year: dict[int, list[dict]] = {}
    for r in reports:
        y, _ = quarter_of(r["slug"])
        by_year.setdefault(y, []).append(r)

    sections = []
    for year in sorted(by_year, reverse=True):
        cards = "".join(
            _card_html(r, is_latest=(r["slug"] == default_slug))
            for r in by_year[year]
        )
        heading = str(year) if year else "Other"
        sections.append(
            f'<section class="year-block">'
            f'<h2 class="year-heading">{_html.escape(heading)}</h2>'
            f'<div class="card-grid">{cards}</div>'
            f"</section>"
        )
    sections_html = "\n".join(sections)
    count = len(reports)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Commodity Dashboard — Quarterly Reports</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0F172A; --card: #1E293B; --border: #334155;
      --text: #F8FAFC; --muted: #94A3B8; --blue: #60A5FA;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; background: var(--bg); color: var(--text);
      font-family: Inter, system-ui, sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    .wrap {{ max-width: 80rem; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
    header.page-head {{ margin-bottom: 2.5rem; }}
    .page-head h1 {{
      font-size: clamp(2rem, 5vw, 3rem); font-weight: 800; margin: 0;
      letter-spacing: -0.03em;
      background: linear-gradient(to right, var(--blue), #93c5fd);
      -webkit-background-clip: text; background-clip: text; color: transparent;
    }}
    .page-head p {{ color: var(--muted); font-size: 1.05rem; margin: 0.6rem 0 0; }}
    .page-head .count {{
      display: inline-block; margin-top: 1rem;
      font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase; color: var(--blue);
      background: rgba(96,165,250,0.15); border: 1px solid rgba(96,165,250,0.3);
      padding: 0.3rem 0.7rem; border-radius: 0.4rem;
    }}
    .year-block {{ margin-bottom: 2.5rem; }}
    .year-heading {{
      font-size: 0.8rem; font-weight: 700; letter-spacing: 0.15em;
      text-transform: uppercase; color: var(--muted);
      margin: 0 0 1rem; padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
    }}
    .card-grid {{
      display: grid; gap: 1.25rem;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    }}
    .card {{
      display: flex; flex-direction: column; gap: 0.75rem;
      background: var(--card); border: 1px solid var(--border);
      border-radius: 1rem; padding: 1.5rem; text-decoration: none;
      color: inherit; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3);
      transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
    }}
    .card:hover {{
      transform: translateY(-3px); border-color: rgba(96,165,250,0.6);
      box-shadow: 0 24px 34px -8px rgba(0,0,0,0.45);
    }}
    .card-top {{ display: flex; align-items: center; gap: 0.5rem; }}
    .card-quarter {{
      font-size: 0.9rem; font-weight: 800; letter-spacing: 0.02em;
      color: #0F172A; background: var(--blue);
      padding: 0.25rem 0.6rem; border-radius: 0.4rem;
    }}
    .card-latest {{
      font-size: 0.6rem; font-weight: 700; letter-spacing: 0.1em;
      text-transform: uppercase; color: #4ADE80;
      background: rgba(74,222,128,0.15); border: 1px solid rgba(74,222,128,0.4);
      padding: 0.2rem 0.45rem; border-radius: 0.3rem;
    }}
    .card-legacy {{
      font-size: 0.6rem; font-weight: 700; letter-spacing: 0.1em;
      text-transform: uppercase; color: #FACC15;
      background: rgba(250,204,21,0.15); border: 1px solid rgba(250,204,21,0.4);
      padding: 0.2rem 0.45rem; border-radius: 0.3rem;
    }}
    .card-title {{ font-size: 1.15rem; font-weight: 700; margin: 0; }}
    .card-sub {{ display: flex; flex-wrap: wrap; gap: 0.5rem 0.9rem; align-items: baseline; }}
    .card-period {{ font-size: 0.95rem; font-weight: 700; color: var(--blue); }}
    .card-region {{ font-size: 0.8rem; color: var(--muted); }}
    .card-glance {{
      display: flex; flex-wrap: wrap; gap: 0.5rem;
      padding: 0.7rem 0.85rem; border-radius: 0.6rem;
      background: rgba(15,23,42,0.55); border: 1px solid var(--border);
    }}
    .g-item {{ display: flex; flex-direction: column; gap: 0.15rem; flex: 1 1 45%; min-width: 130px; }}
    .g-k {{
      font-size: 0.6rem; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase; color: var(--muted);
    }}
    .g-hint {{ font-weight: 600; letter-spacing: 0.02em; opacity: 0.7; }}
    .g-v {{ font-size: 1.05rem; font-weight: 800; color: var(--text); display: flex; align-items: baseline; gap: 0.4rem; flex-wrap: wrap; }}
    .g-delta {{ font-size: 0.8rem; font-weight: 700; font-style: normal; }}
    .g-delta.up {{ color: #F87171; }}     /* price up = risk (warm) */
    .g-delta.down {{ color: #4ADE80; }}   /* price down = opportunity (cool) */
    .g-sep {{ color: var(--muted); font-weight: 400; }}
    .card-trend {{
      font-size: 0.85rem; line-height: 1.5; color: #CBD5E1; margin: 0;
    }}
    .card-chips {{ display: flex; flex-wrap: wrap; gap: 0.4rem; }}
    .chip {{
      font-size: 0.7rem; font-weight: 600; padding: 0.2rem 0.5rem;
      border-radius: 0.3rem; border: 1px solid transparent;
    }}
    .card-cta {{
      margin-top: auto; padding-top: 0.4rem;
      font-size: 0.85rem; font-weight: 700; color: var(--blue);
    }}
    footer.page-foot {{
      margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border);
      font-size: 0.75rem; color: var(--muted);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="page-head">
      <h1>Procurement PMO - Europe</h1>
      <p>Strategic Procurement &amp; Logistics &middot; Commodity Dashboard</p>
      <span class="count">{count} quarter(s) available</span>
    </header>
    {sections_html}
    <footer class="page-foot">
      Pick a quarter above to open its full report. Data source: Expana
      (Mintec) Commodity Price Change Overview Report, Eurostat &amp; Destatis.
    </footer>
  </div>
</body>
</html>
"""


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reports = sorted(manifest["reports"], key=lambda r: r["slug"], reverse=True)
    if not reports:
        print("No reports in manifest — nothing to build.")
        return
    default_slug = reports[0]["slug"]

    # 1 · Inject the switcher shell into every period report.
    for r in reports:
        slug = r["slug"]
        html_path = REPORTS_DIR / Path(r["html"]).name
        if not html_path.exists():
            print(f"  skip {slug} (file missing: {html_path})")
            continue
        banner = shell_html(reports, active_slug=slug, default_slug=default_slug)

        original = html_path.read_text(encoding="utf-8")
        html_path.write_text(inject_shell(original, banner), encoding="utf-8")
        print(f"  patched {html_path.relative_to(ROOT)}")

        germany_path = REPORTS_DIR / f"{slug}-germany.html"
        if germany_path.exists():
            g_original = germany_path.read_text(encoding="utf-8")
            germany_path.write_text(inject_shell(g_original, banner), encoding="utf-8")
            print(f"  patched {germany_path.relative_to(ROOT)}")

    # 2 · Regenerate the redesigned SPA's data blob (app.html reads it).
    try:
        import build_app_data
        build_app_data.main()
    except Exception as exc:  # pragma: no cover - keep menu build resilient
        print(f"  (skipped app-data build: {exc})")

    # 3 · The redesigned SPA is the site landing: index.html mirrors app.html
    #     (GitHub Pages serves public/reports/ as the site root).
    INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    app_path = REPORTS_DIR / "app.html"
    if app_path.exists():
        INDEX_OUT.write_text(app_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Wrote {INDEX_OUT.relative_to(ROOT)} (mirror of app.html — redesigned landing)")
    else:
        INDEX_OUT.write_text(build_index(reports, default_slug), encoding="utf-8")
        print(f"Wrote {INDEX_OUT.relative_to(ROOT)} (quarter-picker menu fallback)")

    # Classic card menu retained for reference (not the landing).
    (REPORTS_DIR / "menu-classic.html").write_text(
        build_index(reports, default_slug), encoding="utf-8")
    print("Wrote public/reports/menu-classic.html (legacy card menu)")


if __name__ == "__main__":
    main()
