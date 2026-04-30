"""Build the master dashboard wiring across period reports.

Drops the previous iframe-based shell entirely (which kept hitting browser
compositor / sibling-load bugs that produced "duplicated header" stacks
across both file:// and http(s) hosts).

New approach — no iframes, no srcdoc, no Blob URLs:

  * Each period HTML (e.g. public/reports/2026-04.html) gets a small
    sticky "period switcher" banner injected at the top of <body>. The
    banner is just <a href> links to the sibling period files plus a
    "Now viewing" label. Clicking a link is a normal full-page navigation,
    so the browser starts from a clean canvas every time — no ghost
    renders, no nested iframes.

  * public/reports/index.html becomes a tiny landing page that auto-
    redirects (meta refresh + JS) to the latest period file. Anyone who
    bookmarked /reports/index.html still ends up on the right report.

The injection is idempotent: an existing
<div data-cd-switcher> at the top of <body> is replaced on each rebuild,
so re-running build_html.py followed by build_dashboard.py is safe.

Usage:
  python scripts/build_dashboard.py
"""
from __future__ import annotations

import datetime as _dt
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


def switcher_html(reports: list[dict], active_slug: str, default_slug: str) -> str:
    """Render the sticky period-switcher banner that goes at the top of every
    period HTML. Links navigate the whole window — no iframe involved."""
    pills = []
    for r in reports:
        slug = r["slug"]
        href = Path(r["html"]).name  # sibling file, e.g. "2026-04.html"
        is_active = slug == active_slug
        is_latest = slug == default_slug
        meta = load_meta(slug)
        legacy = bool(meta.get("legacy"))
        active_cls = " cd-pill-active" if is_active else ""
        hint = "LATEST" if is_latest else ("LEGACY" if legacy else "")
        hint_html = (
            f'<span class="cd-pill-hint">{_html.escape(hint)}</span>' if hint else ""
        )
        pills.append(
            f'<a class="cd-pill{active_cls}" href="{_html.escape(href)}" '
            f'aria-current="{"page" if is_active else "false"}">'
            f'<span class="cd-pill-month">{_html.escape(month_label(slug))}</span>'
            f"{hint_html}"
            f"</a>"
        )

    pills_html = "".join(pills)

    return f"""
<div {SWITCHER_MARKER} class="cd-switcher">
  <style>
    .cd-switcher {{
      position: sticky; top: 0; z-index: 9999;
      background: rgba(15,23,42,0.96);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border-bottom: 1px solid rgba(96,165,250,0.25);
      box-shadow: 0 4px 14px rgba(0,0,0,0.4);
      padding: 0.5rem 1rem;
      font-family: Inter, system-ui, sans-serif;
    }}
    .cd-switcher-inner {{
      max-width: 80rem; margin: 0 auto;
      display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
    }}
    .cd-switcher-label {{
      font-size: 0.625rem; font-weight: 700; letter-spacing: 0.1em;
      text-transform: uppercase; color: #60A5FA;
      background: rgba(96,165,250,0.18);
      padding: 0.2rem 0.5rem; border-radius: 0.25rem;
      display: inline-flex; align-items: center; gap: 0.375rem;
    }}
    .cd-switcher-label::before {{
      content: ""; width: 6px; height: 6px; border-radius: 50%;
      background: #4ADE80;
      box-shadow: 0 0 0 3px rgba(74,222,128,0.25);
    }}
    .cd-switcher-pills {{ display: flex; gap: 0.4rem; flex-wrap: wrap; }}
    .cd-pill {{
      display: inline-flex; flex-direction: column; align-items: center;
      min-width: 110px; padding: 0.35rem 0.75rem;
      border-radius: 0.4rem; border: 1px solid rgba(96,165,250,0.3);
      background: rgba(15,23,42,0.5); color: #60A5FA;
      font-size: 0.8rem; font-weight: 600; text-decoration: none;
      transition: background .15s, transform .15s;
    }}
    .cd-pill:hover {{ background: rgba(96,165,250,0.2); }}
    .cd-pill-active {{
      background: #60A5FA; color: #0F172A; border-color: #60A5FA;
      box-shadow: 0 4px 12px rgba(96,165,250,0.4);
    }}
    .cd-pill-month {{ font-size: 0.85rem; letter-spacing: -0.01em; }}
    .cd-pill-hint {{
      font-size: 0.55rem; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase; opacity: 0.85; margin-top: 1px;
    }}
  </style>
  <div class="cd-switcher-inner">
    <span class="cd-switcher-label">Commodity Dashboard</span>
    <div class="cd-switcher-pills">{pills_html}</div>
  </div>
</div><!--/cd-switcher-->
"""


def inject_switcher(period_html: str, banner: str) -> str:
    """Insert (or replace) the switcher banner immediately after <body...>.

    Idempotent: if a previous switcher (marked with SWITCHER_MARKER) already
    exists, it gets stripped first so we don't accumulate copies on re-run.
    """
    # Strip any existing switcher block from a previous run. We bracket the
    # injected block with a <!--/cd-switcher--> end marker so the regex
    # can match the full block regardless of how many nested <div>s it
    # contains.
    period_html = re.sub(
        r"\s*<div [^>]*" + re.escape(SWITCHER_MARKER) + r".*?<!--/cd-switcher-->\s*",
        "",
        period_html,
        count=1,
        flags=re.DOTALL,
    )

    # Insert right after the opening <body ...> tag.
    def _insert(match: re.Match) -> str:
        return match.group(0) + "\n" + banner + "\n"

    new_html, n = re.subn(r"<body[^>]*>", _insert, period_html, count=1)
    if n == 0:
        # No <body> tag found — fall back to prepending.
        return banner + period_html
    return new_html


def build_index(reports: list[dict], default_slug: str) -> str:
    """Tiny landing page that redirects to the latest period."""
    default_href = Path(
        next(r["html"] for r in reports if r["slug"] == default_slug)
    ).name
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
  <meta http-equiv="refresh" content="0; url={_html.escape(default_href)}">
  <title>Commodity Dashboard</title>
  <link rel="canonical" href="{_html.escape(default_href)}">
  <style>
    body {{
      margin: 0; height: 100vh;
      display: flex; align-items: center; justify-content: center;
      background: #0F172A; color: #94A3B8;
      font-family: Inter, system-ui, sans-serif;
    }}
    a {{ color: #60A5FA; }}
  </style>
</head>
<body>
  <p>Loading latest report&hellip; <a href="{_html.escape(default_href)}">Click here if not redirected.</a></p>
  <script>window.location.replace({json.dumps(default_href)});</script>
</body>
</html>
"""


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    reports = sorted(manifest["reports"], key=lambda r: r["slug"], reverse=True)
    default_slug = reports[0]["slug"]

    # Inject the sticky switcher banner into every period HTML so each
    # report carries its own period switcher — no iframe orchestration.
    for r in reports:
        slug = r["slug"]
        html_path = REPORTS_DIR / Path(r["html"]).name
        if not html_path.exists():
            print(f"  skip {slug} (file missing: {html_path})")
            continue
        original = html_path.read_text(encoding="utf-8")
        banner = switcher_html(reports, active_slug=slug, default_slug=default_slug)
        updated = inject_switcher(original, banner)
        html_path.write_text(updated, encoding="utf-8")
        print(f"  patched {html_path.relative_to(ROOT)}")

    # Landing page: just redirect to the latest period.
    INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    INDEX_OUT.write_text(build_index(reports, default_slug))
    print(f"Wrote {INDEX_OUT.relative_to(ROOT)} (redirect → {Path(reports[0]['html']).name})")


if __name__ == "__main__":
    main()
