"""Build the deployed dashboard: the SPA landing page + in-report switcher.

Three things happen:

1. **In-report switcher shell** — injected right after ``<body>`` of every
   period HTML under ``public/reports/``. It shows the "Commodity Dashboard"
   header, an "All quarters" link back to the landing, a row of quarter
   buttons (sibling ``<a href>`` links, normal full-page navigation — no
   iframes), and a "Now viewing" banner. With one quarter the row collapses.

2. **SPA data** — ``build_app_data.main()`` regenerates
   ``public/reports/app-data.js`` (every quarter's JSON plus the translations
   from ``data/i18n.json``).

3. **Landing page** — ``public/reports/index.html`` is written as a mirror of
   ``app.html``, the category-first SPA. That is the page the GitHub Pages
   root URL serves.

Reports are keyed by a ``YYYY-MM`` slug (the cover month of the Expana PDF)
and map to a fiscal quarter — see ``quarter_of``.

Usage:
  python scripts/build_dashboard.py
"""
from __future__ import annotations

import hashlib
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
    """Return (fiscal_year, fiscal_quarter) for a YYYY-MM slug. The fiscal year
    starts in April: Apr-Jun = Q1, Jul-Sep = Q2, Oct-Dec = Q3, Jan-Mar = Q4 (of
    the fiscal year that began the previous April). Falls back to (0, 0)."""
    try:
        y, m = int(slug.split("-")[0]), int(slug.split("-")[1])
        fq = ((m - 4) % 12) // 3 + 1
        fy = y if m >= 4 else y - 1
        return fy, fq
    except Exception:
        return 0, 0


def quarter_label(slug: str) -> str:
    """'2026-04' -> 'Q1 2026', '2026-07' -> 'Q2 2026'. Falls back to raw slug."""
    y, q = quarter_of(slug)
    if not y:
        return slug
    return f"Q{q} {y}"


def load_meta(slug: str) -> dict:
    path = ROOT / "data" / slug / "meta.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


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
    #     Not guarded: app-data.js carries the translations, so a failure here
    #     would otherwise ship a landing page stuck on stale data.
    import build_app_data
    build_app_data.main()

    # 3 · The redesigned SPA is the site landing: index.html mirrors app.html
    #     (GitHub Pages serves public/reports/ as the site root).
    app_path = REPORTS_DIR / "app.html"
    if not app_path.exists():
        raise SystemExit(f"missing {app_path} — the SPA source is the landing page")
    html = app_path.read_text(encoding="utf-8")

    # Cache-bust the data blob. index.html and app-data.js are separate
    # requests, so a browser can pair a fresh page with a cached blob — the
    # page then renders with the previous quarter's data and silently drops
    # anything new (a section whose `has…` flag is only in the new blob just
    # never appears). Stamping the src with a content hash makes the URL change
    # whenever the data does, and stay put when it doesn't.
    data_path = REPORTS_DIR / "app-data.js"
    if data_path.exists():
        digest = hashlib.sha256(data_path.read_bytes()).hexdigest()[:10]
        html, n = re.subn(r'(<script src="\./app-data\.js)(\?v=[0-9a-f]+)?(")',
                          rf'\1?v={digest}\3', html)
        if n != 1:
            raise SystemExit("could not stamp app-data.js in app.html — "
                             "the <script src=\"./app-data.js\"> tag moved")
        print(f"  stamped app-data.js?v={digest}")

    INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    INDEX_OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {INDEX_OUT.relative_to(ROOT)} (mirror of app.html — the landing page)")


if __name__ == "__main__":
    main()
