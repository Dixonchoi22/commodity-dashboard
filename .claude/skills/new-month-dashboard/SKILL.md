---
name: new-month-dashboard
description: Produce the next month's commodity intelligence dashboard. Use this when the user mentions a new monthly report, drops new PDF/xlsx sources into the repo (especially in input/), or says things like "new month", "next month", "May 2026 dashboard", "regenerate", or "monthly update".
---

# New Monthly Commodity Dashboard

End-to-end workflow for producing a fresh `public/reports/YYYY-MM.html`
and updating the master `index.html` from new raw source files. Follow
these steps when a new month's data arrives.

## Required inputs

The user provides (per month):

1. **Overview PDF** — Expana "Commodity Price Change Overview Report"
   for the target month. (~1 MB, multi-page.)
2. **Forecast xlsx** — Mintec forward curves export covering the next
   quarter+.
3. **HICP xlsx** — *optional*. If missing, `fetch_hicp.py` will pull
   the latest published index values straight from Eurostat.

Files typically arrive in one of two places:

- `input/` drop folder at repo root — preferred, the user uploads here
- `data/YYYY-MM/raw/` already in place — skip the file-move step

## Procedure

### 1 · Determine the period slug

Ask the user which reporting month if unclear. Convert to `YYYY-MM`:

| Reporting month | Slug       |
| --------------- | ---------- |
| April 2026      | `2026-04`  |
| May 2026        | `2026-05`  |
| September 2025  | `2025-09`  |

The "reporting month" is the cover date of the Expana PDF (e.g., a
report titled "...Report April 2026" has slug `2026-04` even though
its MoM window is March 2026 vs February 2026).

### 2 · Move raw files into `data/{slug}/raw/`

```bash
PERIOD=2026-05   # replace
mkdir -p data/$PERIOD/raw
git mv "input/<overview>.pdf"  "data/$PERIOD/raw/overview.pdf"
git mv "input/<forecast>.xlsx" "data/$PERIOD/raw/forecast.xlsx"
# optional, only if user supplied one:
git mv "input/<hicp>.xlsx"     "data/$PERIOD/raw/hicp.xlsx"
```

The three canonical filenames inside `raw/` must be
`overview.pdf`, `forecast.xlsx`, and (optional) `hicp.xlsx`.
Anything else is ignored by the scripts.

### 3 · Draft `data/{slug}/meta.json`

Copy `.claude/skills/new-month-dashboard/meta-template.json` to
`data/$PERIOD/meta.json` and fill in:

- `slug`, `period`, `subtitle`
- `period_mom` and `period_yoy` — **the window the PDF covers**
  (usually month M-1 vs M-2 for MoM and month M-1 vs M-1 of prior
  year for YoY, where M = reporting month)
- `trend_analysis` — 2–3 sentences; *leave placeholder text if the
  user hasn't provided commentary yet, they can edit later*
- `highlights` — 3 tiles (red / green / blue). Pick the most
  striking risk, opportunity, and secondary theme from the PDF's
  executive summary

`kpis` is **omitted on purpose** — they are auto-computed by
`build_html.py` from `hicp_index.json` + `commodities.json`.

### 4 · Run the data pipeline

```bash
python scripts/fetch_hicp.py $PERIOD    # Eurostat → data/$PERIOD/hicp_index.json
python scripts/extract.py    $PERIOD    # PDF + xlsx → data/$PERIOD/*.json
python scripts/build_html.py $PERIOD    # JSON → public/reports/$PERIOD.html
```

After `extract.py`, check its printout:

- `commodities`: should be ~112. If drastically different, the PDF
  layout may have shifted — inspect `pdftotext -layout
  data/$PERIOD/raw/overview.pdf` and tweak `scripts/extract.py`.
- `hicp`: 12 series × 12 months (or close).
- `forecast`: 12 commodities, thousands of daily points.

Then spot-check the commodity JSON for unknown categories:

```bash
python3 -c "import json, collections; rows=json.load(open('data/$PERIOD/commodities.json'))['rows']; print(collections.Counter(r['category'] for r in rows))"
```

Any `Unknown` count > 0 means a new commodity name appeared this
month. Add it to `data/_canonical_categories.json` (lowercase name →
category), then re-run `extract.py` and `build_html.py`.

### 5 · Register in the manifest

Edit `data/manifest.json`, adding a new entry at the **top** of the
`reports` array (master dashboard sorts descending):

```json
{
  "slug": "2026-05",
  "title": "Commodity Intelligence: EU Outlook",
  "period": "May 2026",
  "region": "European Union",
  "html": "/reports/2026-05.html",
  "meta": "/data/2026-05/meta.json"
}
```

### 6 · Rebuild the master dashboard

```bash
python scripts/build_dashboard.py
```

This re-inlines every registered period into `public/reports/index.html`
via iframe `srcdoc`, so opening it offline still works. The new period
will appear as the left-most button and becomes the default view.

### 7 · Verify in a browser

Open `public/reports/index.html`:

- ✅ New month's button shows "LATEST"
- ✅ "Now viewing" banner lists the correct MoM / YoY windows
- ✅ 4 KPI cards populated (Index level, YoY %, Top hike, Top drop)
- ✅ HICP chart shows 12 months ending on Eurostat's latest month
- ✅ Commodity table has all ~112 rows, each categorised
- ✅ Clicking a commodity with a forward curve opens the modal

### 8 · Commit & push

Use a descriptive commit summarising the period and any parser
tweaks. Default to the user's current branch; ask before pushing to
`main`.

```bash
git add data/$PERIOD public/reports/$PERIOD.html \
        public/reports/index.html data/manifest.json \
        data/_canonical_categories.json
git commit -m "Add $PERIOD dashboard"
git push
```

## Common gotchas

- **HICP not yet published** — Eurostat publishes HICP with ~20-day
  lag. If the target month isn't live yet, `fetch_hicp.py` returns
  the most recent 12 months available; the chart title still reads
  "12-Month EU Food Index (HICP) Trend".
- **PDF layout drift** — If Expana changes the PDF template, the
  two-column summary parser (`extract_summary` in `extract.py`) may
  mis-segment rows. Fix by re-testing against the new layout and
  updating the column MID threshold if needed.
- **New commodity not in canonical map** — always add to
  `data/_canonical_categories.json`, not to ad-hoc logic in
  `extract.py`.
- **Sep 2025 is the legacy snapshot** — its raw HTML under
  `data/2025-09/raw/` is a pre-built Gemini dashboard we do *not*
  regenerate via `build_html.py`. Leave it alone; it's flagged
  `"legacy": true` in its `meta.json`.
