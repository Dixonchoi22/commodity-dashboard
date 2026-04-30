"""Build the master dashboard wiring across period reports.

This script does two things:

  1. INJECTS the master shell (Commodity Dashboard header + period
     switcher + "Now viewing" banner) into each generated period HTML
     under public/reports/. The shell's period buttons are sibling-file
     <a href> links — works perfectly on HTTP / GitHub Pages where the
     other period file is reachable.

  2. BUILDS public/reports/index.html as an all-in-one bundle: master
     shell + a separate <iframe srcdoc> per period. srcdoc is set in
     the static HTML once and NEVER swapped — JS only toggles CSS
     display: none/block to switch periods. This avoids the iframe
     compositor "duplicated header" ghost bug we saw earlier when
     srcdoc was swapped on the same iframe.

The all-in-one index.html lets the user download a SINGLE file and
still switch periods locally without needing the sibling files.

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


def shell_styles() -> str:
    """The master-shell CSS shared by both the standalone period files
    (where buttons are <a href>) and the all-in-one index.html (where
    buttons are <button onclick>). Same look in both."""
    return """
    .cd-shell {
      font-family: Inter, system-ui, sans-serif;
      color: #F8FAFC;
    }
    .cd-shell * { box-sizing: border-box; }
    .cd-shell-header {
      background: #1E293B;
      border-bottom: 1px solid #334155;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .cd-header-inner {
      max-width: 80rem; margin: 0 auto;
      padding: 1rem 1.5rem;
      display: flex; flex-wrap: wrap;
      gap: 1rem 2rem;
      align-items: center; justify-content: space-between;
    }
    .cd-title-block h1 {
      font-size: 1.125rem; font-weight: 800; margin: 0;
      background: linear-gradient(to right, #60A5FA, #93c5fd);
      -webkit-background-clip: text; background-clip: text; color: transparent;
      letter-spacing: -0.025em;
    }
    .cd-title-block .cd-subtitle {
      color: #94A3B8; font-size: 0.75rem; margin: 2px 0 0;
    }
    .cd-period-bar { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .cd-shell .period-btn {
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
    }
    .cd-shell .period-btn:hover { background: rgba(96,165,250,0.2); }
    .cd-shell .period-btn.active {
      background: #60A5FA; color: #0F172A; border-color: #60A5FA;
      box-shadow: 0 4px 14px rgba(96,165,250,0.45);
      transform: translateY(-1px);
    }
    .cd-shell .period-btn-month { font-size: 0.95rem; letter-spacing: -0.01em; }
    .cd-shell .period-btn-hint {
      font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.08em;
      opacity: 0.75; margin-top: 2px; min-height: 0.75rem;
    }
    .cd-shell .period-btn.active .period-btn-hint { opacity: 1; }
    .cd-viewing-banner {
      background: linear-gradient(to right, rgba(96,165,250,0.12), rgba(96,165,250,0.02));
      border-bottom: 1px solid rgba(96,165,250,0.25);
      padding: 0.75rem 1.5rem;
    }
    .cd-viewing-inner {
      max-width: 80rem; margin: 0 auto;
      display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
    }
    .cd-viewing-tag {
      display: inline-flex; align-items: center; gap: 0.375rem;
      font-size: 0.625rem; font-weight: 700; letter-spacing: 0.1em;
      text-transform: uppercase; color: #60A5FA;
      background: rgba(96,165,250,0.18);
      padding: 0.25rem 0.5rem; border-radius: 0.25rem;
    }
    .cd-viewing-tag::before {
      content: ""; width: 6px; height: 6px; border-radius: 50%;
      background: #4ADE80; box-shadow: 0 0 0 3px rgba(74,222,128,0.25);
    }
    .cd-viewing-title { font-size: 1rem; font-weight: 700; color: #F8FAFC; }
    .cd-viewing-period {
      font-size: 1.5rem; font-weight: 800; color: #60A5FA; letter-spacing: -0.02em;
    }
    .cd-viewing-meta { font-size: 0.75rem; color: #94A3B8; }
    .cd-viewing-legacy {
      display: inline-flex; align-items: center; gap: 0.375rem;
      background: rgba(250,204,21,0.15); color: #FACC15;
      border: 1px solid rgba(250,204,21,0.4);
      padding: 0.2rem 0.5rem; border-radius: 0.25rem;
      font-size: 0.625rem; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    """


def shell_html_inject(reports: list[dict], active_slug: str, default_slug: str) -> str:
    """Master shell with <a href> sibling-file buttons. Used inside each
    standalone period HTML file."""
    active_meta = load_meta(active_slug)
    n = len(reports)

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
    legacy_html = '<span class="cd-viewing-legacy">Legacy snapshot</span>' if legacy else ""

    return f"""
<div {SWITCHER_MARKER} class="cd-shell" style="margin: -1rem -1rem 1.5rem">
  <style>{shell_styles()}
    @media (min-width: 640px) {{
      [{SWITCHER_MARKER}].cd-shell {{ margin: -2rem -2rem 2rem !important; }}
    }}
  </style>
  <div class="cd-shell-header">
    <div class="cd-header-inner">
      <div class="cd-title-block">
        <h1>Commodity Dashboard</h1>
        <p class="cd-subtitle">Monthly intelligence · {n} report(s) available</p>
      </div>
      <div class="cd-period-bar" role="tablist" aria-label="Select report period">
        {"".join(btns)}
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


def build_all_in_one(reports: list[dict], originals: dict[str, str], default_slug: str) -> str:
    """Render index.html with the master shell and one <iframe srcdoc>
    per period. srcdoc is baked into the static HTML — JS only toggles
    CSS display, never touches srcdoc — so the swap-induced duplicate-
    header ghost bug cannot trigger."""
    # Per-period button data for the shell (rendered as <button onclick>
    # since clicking calls the in-page selectPeriod() instead of nav-ing).
    btns = []
    for r in reports:
        slug = r["slug"]
        is_active = slug == default_slug
        is_latest = slug == default_slug
        active_cls = " active" if is_active else ""
        hint = "latest" if is_latest else ""
        btns.append(
            f'<button type="button" class="period-btn{active_cls}" '
            f'data-slug="{_html.escape(slug)}" '
            f'onclick="cdSelectPeriod(\'{_html.escape(slug)}\')" '
            f'aria-selected="{"true" if is_active else "false"}">'
            f'<span class="period-btn-month">{_html.escape(month_label(slug))}</span>'
            f'<span class="period-btn-hint">{_html.escape(hint)}</span>'
            f"</button>"
        )

    # Per-period metadata for the "Now viewing" banner — the JS swaps the
    # banner text on click without re-rendering the whole shell.
    banner_data = {}
    for r in reports:
        slug = r["slug"]
        meta = load_meta(slug)
        banner_data[slug] = {
            "title": meta.get("title", ""),
            "period": meta.get("period", month_label(slug)),
            "region": meta.get("region", ""),
            "mom": meta.get("period_mom", ""),
            "yoy": meta.get("period_yoy", ""),
            "legacy": bool(meta.get("legacy")),
        }
    banner_json = json.dumps(banner_data).replace("</", "<\\/")

    # One <iframe srcdoc> per period. Set in static HTML, never swapped.
    iframes_html = []
    for r in reports:
        slug = r["slug"]
        original = originals.get(slug, "")
        # Escape so the period HTML survives as a srcdoc attribute value.
        escaped = _html.escape(original, quote=True)
        is_default = slug == default_slug
        display = "block" if is_default else "none"
        iframes_html.append(
            f'<iframe data-period-frame="{_html.escape(slug)}" '
            f'class="cd-period-frame" '
            f'style="display: {display}" '
            f'srcdoc="{escaped}"></iframe>'
        )

    n = len(reports)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="cache-control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="pragma" content="no-cache">
  <meta http-equiv="expires" content="0">
  <title>Commodity Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0; padding: 0; height: 100%;
      background: #0F172A; color: #F8FAFC;
      font-family: Inter, system-ui, sans-serif;
    }}
    body {{ display: flex; flex-direction: column; }}
    main {{ flex: 1; min-height: 0; display: flex; }}
    .cd-period-frame {{
      flex: 1; width: 100%; height: 100%;
      border: 0; background: #0F172A;
    }}
    {shell_styles()}
  </style>
</head>
<body>
  <div {SWITCHER_MARKER} class="cd-shell">
    <div class="cd-shell-header">
      <div class="cd-header-inner">
        <div class="cd-title-block">
          <h1>Commodity Dashboard</h1>
          <p class="cd-subtitle">Monthly intelligence · {n} report(s) available</p>
        </div>
        <div class="cd-period-bar" role="tablist" aria-label="Select report period">
          {"".join(btns)}
        </div>
      </div>
    </div>
    <div class="cd-viewing-banner">
      <div class="cd-viewing-inner">
        <span class="cd-viewing-tag">Now viewing</span>
        <span class="cd-viewing-title" id="cd-v-title"></span>
        <span class="cd-viewing-period" id="cd-v-period"></span>
        <span class="cd-viewing-meta" id="cd-v-meta"></span>
        <span class="cd-viewing-legacy" id="cd-v-legacy" style="display:none">Legacy snapshot</span>
      </div>
    </div>
  </div>

  <main>
    {chr(10).join(iframes_html)}
  </main>

  <script>
    const CD_BANNER = {banner_json};
    const CD_DEFAULT = {json.dumps(default_slug)};

    function cdSelectPeriod(slug) {{
      const data = CD_BANNER[slug];
      if (!data) return;

      // Toggle button states.
      document.querySelectorAll('.cd-shell .period-btn').forEach(b => {{
        const on = b.dataset.slug === slug;
        b.classList.toggle('active', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      }});

      // Update viewing banner text in place — never touch the shell DOM
      // structure, never recreate the iframes.
      document.getElementById('cd-v-title').textContent = data.title;
      document.getElementById('cd-v-period').textContent = data.period;
      let meta = '';
      if (data.region) meta += data.region;
      if (data.mom) meta += (meta ? ' · ' : '') + 'MoM: ' + data.mom;
      if (data.yoy) meta += (meta ? ' · ' : '') + 'YoY: ' + data.yoy;
      document.getElementById('cd-v-meta').textContent = meta;
      document.getElementById('cd-v-legacy').style.display = data.legacy ? '' : 'none';

      // Toggle iframe visibility — srcdoc stays untouched on every iframe.
      document.querySelectorAll('iframe[data-period-frame]').forEach(f => {{
        f.style.display = f.dataset.periodFrame === slug ? 'block' : 'none';
      }});

      document.title = 'Commodity Dashboard — ' + data.period;
      history.replaceState(null, '', '?period=' + slug);
    }}

    const params = new URLSearchParams(window.location.search);
    const initial = params.get('period') && CD_BANNER[params.get('period')]
      ? params.get('period') : CD_DEFAULT;

    // Defensive: if anything (browser quirk, cached state, extension) ends
    // up rendering the master shell more than once at the top level, drop
    // every copy past the first so the user only sees one bar.
    function cdDedupShells() {{
      const shells = document.body.querySelectorAll(':scope > [{SWITCHER_MARKER}]');
      for (let i = 1; i < shells.length; i++) shells[i].remove();
    }}
    cdDedupShells();
    cdSelectPeriod(initial);
  </script>
</body>
</html>
"""


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    reports = sorted(manifest["reports"], key=lambda r: r["slug"], reverse=True)
    default_slug = reports[0]["slug"]

    # Step 1: Read each period file, strip any existing shell, capture the
    # bare content for use as iframe srcdoc, then write the period file
    # back with a fresh shell injection (for standalone sibling navigation).
    originals: dict[str, str] = {}
    for r in reports:
        slug = r["slug"]
        html_path = REPORTS_DIR / Path(r["html"]).name
        if not html_path.exists():
            print(f"  skip {slug} (file missing: {html_path})")
            continue
        raw = html_path.read_text(encoding="utf-8")
        stripped = strip_shell(raw)
        originals[slug] = stripped

        banner = shell_html_inject(reports, active_slug=slug, default_slug=default_slug)
        updated = inject_shell(stripped, banner)
        html_path.write_text(updated, encoding="utf-8")
        print(f"  patched {html_path.relative_to(ROOT)}")

    # Step 2: Build all-in-one index.html bundling both periods inline.
    INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    INDEX_OUT.write_text(build_all_in_one(reports, originals, default_slug))
    print(
        f"Wrote {INDEX_OUT.relative_to(ROOT)} "
        f"(all-in-one bundle of {len(originals)} period(s))"
    )


if __name__ == "__main__":
    main()
