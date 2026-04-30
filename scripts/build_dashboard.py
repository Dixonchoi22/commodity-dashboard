"""Build the master dashboard wiring across period reports.

Drops the previous iframe-based shell entirely (which kept hitting browser
compositor / sibling-load bugs that produced "duplicated header" stacks).

New approach — no iframe, no srcdoc, no Blob URL:

  * Each period HTML (e.g. public/reports/2026-04.html) gets the FULL
    master shell injected at the top of <body>: the "Commodity Dashboard"
    header with the period switcher buttons, plus the "Now viewing"
    banner with title / period / MoM / YoY metadata. Period buttons are
    plain <a href> links to sibling period files — clicking is a normal
    full-page navigation, so the browser starts from a clean canvas every
    time. Cannot duplicate.
  * public/reports/index.html is a tiny landing page that auto-redirects
    (meta refresh + JS) to the latest period file.

The injection is idempotent: bracketed by a <!--/cd-switcher--> end
marker, so re-running build_html.py followed by build_dashboard.py is
safe — the previous block is replaced in place.

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


def shell_html(reports: list[dict], active_slug: str, default_slug: str) -> str:
    """Render the full master shell (header + viewing banner) for the given
    active period. Replaces what used to be an iframe-wrapping page."""
    active_meta = load_meta(active_slug)
    n = len(reports)

    # Period switcher buttons (anchors, not <button>s — full-page nav).
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
            f'<span class="period-btn-month">{_html.escape(month_label(slug))}</span>'
            f'<span class="period-btn-hint">{_html.escape(hint)}</span>'
            f"</a>"
        )
    buttons_html = "".join(btns)

    # Viewing-banner content for the active period.
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

    return f"""
<div {SWITCHER_MARKER} class="cd-shell">
  <style>
    .cd-shell {{
      font-family: Inter, system-ui, sans-serif;
      color: #F8FAFC;
      margin: -1rem -1rem 1.5rem;
    }}
    @media (min-width: 640px) {{
      .cd-shell {{ margin: -2rem -2rem 2rem; }}
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
      min-width: 130px;
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
    .cd-shell .period-btn-month {{
      font-size: 0.95rem; letter-spacing: -0.01em;
    }}
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
        <h1>Commodity Dashboard</h1>
        <p class="cd-subtitle">Monthly intelligence · {n} report(s) available</p>
      </div>
      <div class="cd-period-bar" role="tablist" aria-label="Select report period">
        {buttons_html}
      </div>
    </div>
  </div>
  <div class="cd-viewing-banner">
    <div class="cd-viewing-inner">
      <span class="cd-viewing-tag">Now viewing</span>
      <span class="cd-viewing-title">{_html.escape(title)}</span>
      <span class="cd-viewing-period">{_html.escape(period)}</span>
      <span class="cd-viewing-meta">{meta_str}</span>
      {legacy_html}
    </div>
  </div>
</div><!--/cd-switcher-->
"""


def inject_shell(period_html: str, banner: str) -> str:
    """Insert (or replace) the master shell immediately after <body...>.

    Idempotent: if a previous shell (bracketed by SWITCHER_MARKER and the
    <!--/cd-switcher--> end marker) already exists, it gets stripped first
    so we don't accumulate copies on re-run.
    """
    period_html = re.sub(
        r"\s*<div [^>]*" + re.escape(SWITCHER_MARKER) + r".*?<!--/cd-switcher-->\s*",
        "",
        period_html,
        count=1,
        flags=re.DOTALL,
    )

    def _insert(match: re.Match) -> str:
        return match.group(0) + "\n" + banner + "\n"

    new_html, n = re.subn(r"<body[^>]*>", _insert, period_html, count=1)
    if n == 0:
        return banner + period_html
    return new_html


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    reports = sorted(manifest["reports"], key=lambda r: r["slug"], reverse=True)
    default_slug = reports[0]["slug"]

    for r in reports:
        slug = r["slug"]
        html_path = REPORTS_DIR / Path(r["html"]).name
        if not html_path.exists():
            print(f"  skip {slug} (file missing: {html_path})")
            continue
        original = html_path.read_text(encoding="utf-8")
        banner = shell_html(reports, active_slug=slug, default_slug=default_slug)
        updated = inject_shell(original, banner)
        html_path.write_text(updated, encoding="utf-8")
        print(f"  patched {html_path.relative_to(ROOT)}")

    # index.html mirrors the latest period file so /reports/ lands directly
    # on the full dashboard (master shell + April 2026 content) instead of
    # a redirect page. The shell's period buttons still point to the
    # canonical sibling files (2026-04.html, 2025-09.html), so clicking
    # them navigates away from index.html cleanly.
    INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    latest_path = REPORTS_DIR / Path(
        next(r["html"] for r in reports if r["slug"] == default_slug)
    ).name
    INDEX_OUT.write_text(latest_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Wrote {INDEX_OUT.relative_to(ROOT)} (mirror of {latest_path.name})")


if __name__ == "__main__":
    main()
