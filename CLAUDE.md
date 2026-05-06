# CLAUDE.md — agent orientation

This repo produces monthly **commodity intelligence dashboards** as static
HTML under `public/reports/`. Each month is built by a small Python
pipeline that turns raw source files (PDF, xlsx, Eurostat / Destatis
exports) into JSON, then renders the JSON into a single HTML file via
`scripts/build_html.py`.

## Source of truth — read this first

**Never edit `public/reports/*.html` by hand for content changes.**
Those files are generated. Edit the source, then regenerate:

| Want to change…                              | Edit…                                            |
| -------------------------------------------- | ------------------------------------------------ |
| Trend Analysis, highlights, period dates     | `data/{slug}/meta.json`                          |
| A commodity's category / MoM / YoY           | `data/{slug}/commodities.json`                   |
| Remove a commodity (and its category card)   | delete row in `data/{slug}/commodities.json` — search count and category cards auto-update |
| Commodity commentary / paragraph             | `data/{slug}/commentary.json`                    |
| Forecast curves                              | `data/{slug}/forecast.json`                      |
| Germany sub-categories / drilldowns          | `data/{slug}/destatis.json` (built from the Destatis zip in `raw/`) |
| Headlines: KPIs, chart subtitles, table headers, column lists, drilldown layout | `scripts/build_html.py` |
| Master multi-month landing page              | `scripts/build_dashboard.py` + `data/manifest.json` |

Then regenerate:

```bash
python scripts/build_html.py {slug}        # → public/reports/{slug}.html + {slug}-germany.html
cp public/reports/{slug}.html public/reports/index.html
```

`index.html` is a duplicate of the latest period's HTML so the
GitHub Pages root URL serves the most recent report. Always `cp` after
regenerating.

## Directory map

```
data/{slug}/
  meta.json          # period metadata + trend_analysis + highlights tiles
  commodities.json   # rows: category, name, mom_pct, yoy_pct  (~110 entries)
  commentary.json    # per-commodity paragraph + price line
  forecast.json      # daily forward curves (12 commodities)
  hicp.json          # legacy HICP series
  hicp_index.json    # current HICP series (Eurostat teicp010)
  germany.json       # Eurostat headline + prc_hicp_midx subcategories (fallback)
  destatis.json      # Destatis 61111-0004 — preferred source for German data
  world_bank.json    # WB pinksheet
  raw/               # original PDFs / xlsx / Destatis zip — keep these
scripts/
  fetch_hicp.py      # Eurostat HICP → hicp_index.json
  fetch_destatis.py  # Destatis 61111-0004 zip → destatis.json
  fetch_germany.py   # Eurostat → germany.json (DE + EU27 headline + drilldowns)
  fetch_world_bank.py
  extract.py         # PDF + xlsx → commodities/commentary/forecast.json
  build_html.py      # JSON → public/reports/{slug}.html (+ {slug}-germany.html)
  build_dashboard.py # builds the multi-month master public/reports/index.html
public/reports/
  {slug}.html        # generated, one per period
  {slug}-germany.html# generated, standalone Germany page (iframed into main)
  index.html         # duplicate of latest {slug}.html
```

## Germany section data source

**All Germany data comes from Destatis Genesis Online table 61111-0004**
(base 2020 = 100), shipped as a CSV inside a zip in
`data/{slug}/raw/61111-0004_en*.zip`. `fetch_destatis.py` extracts the
zip into `data/{slug}/destatis.json`.

`build_html.py` uses Destatis CP01 for the headline KPIs / 12-month
trend chart and `_germany_drilldowns_from_destatis()` for the
drilldown panels. Each drilldown panel includes the parent COICOP
series (e.g. CP0122) as the first row + a white dashed line, alongside
its 5-digit children (CP01221, CP01222, …).

The Eurostat `germany.json` headline (teicp010) is now the **fallback**
for when no Destatis zip is provided. EU27 is not currently shown
anywhere because Destatis is German-only.

## Common edit recipes

### Remove a category / commodity from the dashboard
1. Delete the rows from `data/{slug}/commodities.json`.
2. (Optional) Delete the matching entries from `data/{slug}/commentary.json`.
3. Re-run `python scripts/build_html.py {slug}`, then `cp` to `index.html`.
   Search count, category cards, and dropdown options auto-update from the
   new commodity list — no HTML edits needed.

### Tweak Trend Analysis or highlights wording
Edit `data/{slug}/meta.json` → `trend_analysis` or `highlights[].body`,
then regenerate.

### Rename a column header / chart subtitle / KPI caption
Edit `scripts/build_html.py`. Search the literal string and change it
in one place. Regenerate.

### Add or remove a Germany drilldown parent
Edit `GERMANY_DRILLDOWN_DISPLAY` in `scripts/build_html.py` (and the
matching `DRILLDOWNS` dict in `scripts/fetch_germany.py` if Eurostat
fallback is also wanted). Regenerate.

### Change the data source for the Germany headline
The headline DE values live in `_germany_drilldowns_from_destatis`'s
caller — search `cp01 = next(... if s["coicop"] == "CP01" ...)` in
`build_html.py`. The KPI block just downstream reads from `de`. Don't
forget to update the `headline_source_label` and the chart subtitle
strings in the same block.

## Build / deploy flow

1. Edits → `data/{slug}/*.json` and/or `scripts/build_html.py`.
2. `python scripts/build_html.py {slug}` regenerates the HTML.
3. `cp public/reports/{slug}.html public/reports/index.html`.
4. Commit all four files (`scripts/build_html.py` if changed, the two
   regenerated `.html`s, and `index.html`).
5. **Push to `main`** — `.github/workflows/pages.yml` deploys
   `public/reports/` to GitHub Pages on every push to `main` that
   touches that directory. Other branches do **not** deploy.

> **Authorization**: Treat pushing to `main` as a destructive action.
> Always work on a feature branch first and ask for permission before
> merging to `main`. The user previously authorized direct pushes to
> `main` for fast iteration — defer to current session context.

## Gotchas observed in real sessions

- **`index.html` is not auto-synced.** After every `build_html.py`
  run, copy `{slug}.html` over `index.html`, otherwise the deployed
  site shows stale content.
- **Germany content is JSON-encoded inside the main HTML.**
  `<script id="cd-germany-payload" type="application/json">…</script>`
  holds an escaped HTML string. To verify changes there, parse the
  JSON first (`json.loads(payload)`) — direct grep against the main
  HTML often misses matches because of the `\"` and `·` escaping.
- **Eurostat is firewalled in some environments.** `fetch_germany.py`
  and `fetch_hicp.py` will hit 403s. Use the locally-cached JSON or
  the Destatis zip instead.
- **Don't run `build_html.py` against an unmerged feature branch's
  data without checking whether prior manual HTML edits exist** — the
  build will overwrite them. Move the manual edits into the source
  JSON / build script first.
- **`teicp010` ≠ CP01.** Eurostat's short-term `teicp010` indicator
  is *labeled* "HICP - food" but doesn't share a base year with
  Destatis CP01. They cannot be plotted on the same Y axis without
  rebasing. The current dashboard avoids this by using Destatis only
  for German values.
- **The `2025-09` snapshot is legacy.** Its `raw/overview.html` is a
  pre-built Gemini dashboard. Don't regenerate it via `build_html.py`;
  it's flagged `"legacy": true` in its `meta.json`.

## Skills

- `.claude/skills/new-month-dashboard/SKILL.md` — full procedure for
  rolling forward to the next reporting month (new PDFs, new slug,
  manifest update). Auto-invoked when the user mentions a new month
  or drops files in `input/`.
