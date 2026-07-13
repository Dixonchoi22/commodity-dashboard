---
name: new-quarter-dashboard
description: Produce the next quarter's commodity intelligence dashboard. Use this when the user mentions a new quarterly report, drops new PDF/xlsx sources into the repo (especially in input/), or says things like "new quarter", "next quarter", "Q3 2026 dashboard", "July 2026 report", "regenerate", or "quarterly update".
---

# New Quarterly Commodity Dashboard

End-to-end workflow for producing a fresh `public/reports/YYYY-MM.html`
and updating the master quarter-picker `index.html` from new raw source
files. Follow these steps when a new quarter's data arrives.

Reports are updated **quarterly**. The slug is still the `YYYY-MM` cover
month of the Expana PDF; the month maps to a calendar quarter for display:

| Reporting month | Quarter | Slug      |
| --------------- | ------- | --------- |
| April 2026      | Q2 2026 | `2026-04` |
| July 2026       | Q3 2026 | `2026-07` |
| October 2026    | Q4 2026 | `2026-10` |
| January 2027    | Q1 2027 | `2027-01` |

## Environment (Windows)

This repo's pipeline was authored on Linux; on the user's Windows machine:

- Run Python with the **`py`** launcher (`python` is not on PATH — it hits
  the Microsoft Store alias).
- Set **`$env:PYTHONUTF8 = "1"`** before every run. Several scripts print
  `·`, `✓`, `→` etc. and write UTF-8 HTML; without UTF-8 mode Windows'
  cp1252 default raises `UnicodeEncodeError`.
- **`pdftotext`** (Poppler) is required by `extract.py`. Install once with
  `winget install --id oschwartz10612.Poppler`, then either restart the
  shell or prepend its `...\poppler-*\Library\bin` to `$env:PATH` for the
  session.

## Required inputs

The user provides (per quarter):

1. **Overview PDF** — Expana "Commodity Price Change Overview Report" for
   the cover month. (~1 MB, multi-page.) → `raw/overview.pdf`
2. **Germany zip** — Destatis Genesis table `61111-0004_en*.zip`. → keep
   its original name in `raw/`.
3. **Forecast xlsx** — Mintec forward curves. → `raw/forecast.xlsx`.
   *Forward curves span more than one quarter, so it is acceptable to
   carry over the previous quarter's `forecast.xlsx` for one more quarter
   if a fresh export isn't available — note the carry-over in
   `meta.json` → `trend_analysis` and refresh when the new file lands.*
4. **HICP xlsx** — *optional*. If missing, `fetch_hicp.py` pulls the
   latest published index values from Eurostat.

Files typically arrive in `input/` (drop folder) or the user points at
their Downloads path; copy them into `data/YYYY-MM/raw/` under the
canonical names above.

## Procedure

### 1 · Determine the period slug

Cover date of the Expana PDF → `YYYY-MM` (see the quarter table above).

### 2 · Stage raw files into `data/{slug}/raw/`

Canonical names: `overview.pdf`, `forecast.xlsx`, `61111-0004_en*.zip`,
and optionally `hicp.xlsx`. Anything else is ignored by the scripts.

### 3 · Draft `data/{slug}/meta.json`

Copy `.claude/skills/new-quarter-dashboard/meta-template.json` to
`data/$PERIOD/meta.json` and fill in:

- `slug`, `period`, `subtitle`
- `period_mom` / `period_yoy` — **the window the PDF states** (grep the
  PDF for the header line, e.g. "Price changes for June 2026 vs May 2026
  MOM and June 2025 YOY").
- `trend_analysis` — 2–3 sentences; cite the latest HICP index level and
  YoY, plus the biggest category swings. Note any forecast carry-over.
- `highlights` — 3 tiles (red / green / blue). Derive from the biggest
  MoM/YoY movers in `commodities.json` (see step 4 spot-check).

`kpis` is **omitted on purpose** — auto-computed by `build_html.py`.

### 4 · Run the data pipeline

```powershell
$env:PYTHONUTF8 = "1"
$env:PATH = "<poppler>\Library\bin;$env:PATH"   # for pdftotext
py scripts/fetch_hicp.py     $PERIOD   # Eurostat HICP -> hicp_index.json
py scripts/fetch_destatis.py $PERIOD   # Germany zip  -> destatis.json
py scripts/fetch_germany.py  $PERIOD   # Eurostat     -> germany.json  (see note)
py scripts/extract.py        $PERIOD   # PDF + xlsx   -> commodities/commentary/forecast.json
py scripts/build_html.py     $PERIOD   # JSON         -> public/reports/$PERIOD.html (+ -germany.html)
```

> **`germany.json` is required to render the Germany section.**
> `build_html.py` gates the whole Germany page on `germany.json`
> (Eurostat headline). The Destatis zip alone only fills the
> sub-category drilldowns. Always run `fetch_germany.py` too; if Eurostat
> is firewalled, copy the previous quarter's `germany.json` as a fallback
> (the DE headline is overridden by Destatis CP01 anyway).

After `extract.py`, spot-check for unknown categories:

```powershell
py -c "import json,collections; r=json.load(open('data/$PERIOD/commodities.json'))['rows']; print(collections.Counter(x['category'] for x in r))"
```

Any `Unknown` > 0 means a new commodity name appeared. Add it to
`data/_canonical_categories.json` (lowercase name → category), then re-run
`extract.py` and `build_html.py`.

### 5 · Register in the manifest

Edit `data/manifest.json`, adding the new entry at the **top** of
`reports` (the menu sorts descending):

```json
{
  "slug": "2026-07",
  "title": "Commodity Intelligence: EU Outlook",
  "period": "July 2026",
  "region": "European Union",
  "html": "/reports/2026-07.html",
  "meta": "/data/2026-07/meta.json"
}
```

### 6 · Rebuild the master menu

```powershell
py scripts/build_dashboard.py
```

This (a) injects the quarter-switcher shell into every period report and
(b) regenerates `public/reports/index.html` as the standalone
**quarter-picker landing menu** (one card per quarter, newest flagged
"Latest"). The new quarter appears as the first card.

### 7 · Verify in a browser

Open `public/reports/index.html`:

- ✅ New quarter card shows "Latest" with the right Q badge (e.g. Q3 2026)
- ✅ Clicking a card opens that quarter's full report
- ✅ In-report header has "← All quarters" + a quarter switcher
- ✅ "Now viewing" banner lists the correct MoM / YoY windows
- ✅ 4 KPI cards populated (Index level, YoY %, Top hike, Top drop)
- ✅ Commodity table has all ~112 rows, each categorised
- ✅ Germany page opens and shows Destatis drilldowns

### 8 · Commit & push

`public/reports/**` on `main` auto-deploys to GitHub Pages. Treat pushing
to `main` as a deploy — confirm with the user first (they have authorised
direct pushes for fast iteration; defer to current session context).

```powershell
git add data/$PERIOD public/reports/$PERIOD.html `
        public/reports/$PERIOD-germany.html public/reports/index.html `
        data/manifest.json data/_canonical_categories.json
git commit -m "Add $PERIOD (QX YYYY) dashboard"
git push origin main
```

## Common gotchas

- **`UnicodeEncodeError` on Windows** — you forgot `$env:PYTHONUTF8="1"`.
- **`pdftotext` FileNotFoundError** — Poppler not on PATH (see Environment).
- **No Germany section** — `germany.json` missing; run `fetch_germany.py`.
- **HICP not yet published** — Eurostat lags ~20 days; `fetch_hicp.py`
  returns the most recent 12 months available.
- **PDF layout drift** — if Expana changes the template, the two-column
  summary parser (`extract_summary` in `extract.py`) may mis-segment rows.
- **New commodity not in canonical map** — always add to
  `data/_canonical_categories.json`, not ad-hoc logic in `extract.py`.
- **Stale forecast** — if forecast curves were carried over, refresh
  `raw/forecast.xlsx` and re-run `extract.py` + `build_html.py` once the
  new Mintec export arrives.
