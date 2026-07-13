# Design Brief — Commodity Dashboard (Procurement PMO, Europe)

A brief for redesigning the UI/UX, plus a ready-to-paste **prompt for a
Claude design session** (claude.ai artifact / design tool). Scroll to
[§ Prompt to paste](#prompt-to-paste) for the copy-paste block.

---

## 1. Who it's for & the job to be done

**Primary user: a category procurement manager** (Dairy, Meat & Poultry,
Oilseeds, Packaging, Fish, Grains, Softs…). They open this quarterly and
ask, in order:

1. **"What happened to *my* category this quarter?"** — is it up or down,
   MoM and YoY?
2. **"Where's the pain and where's the opportunity?"** — which commodities
   spiked (renegotiate / hedge) and which are in deep deflation (lock in
   long-term contracts)?
3. **"What do I tell my stakeholders?"** — one or two defensible headlines
   with the numbers attached.

Design implication: the product must be **category-first**. Today it opens
on a quarter, then shows *all* categories at once. The redesign should let
a manager land on — or immediately filter to — their own category and get
the three answers above in ~10 seconds.

## 2. Surfaces

1. **Landing menu** (`index.html`) — pick a quarter. Card per quarter with
   quarter badge, period, region, top risk/opportunity chips.
2. **Quarter report** (`{slug}.html`) — KPI row, HICP trend chart,
   commodity table (~112 rows across ~12 categories), per-commodity
   forecast modal, Germany drilldown page.

Both are **static HTML** (Tailwind CDN + Chart.js), dark theme, generated
by Python. No build step, no framework — keep it that way.

## 3. What's good today (keep)

- Clear dark palette; blue primary, red/green polarity already in use.
- Quarter switcher + "All quarters" navigation.
- Auto-computed KPIs and category cards from the data.

## 4. What to improve (the design problems)

- **No category-first entry.** A Dairy manager must scan the whole table.
  Add category navigation: a category rail / chips that filter the table
  and drive a per-category summary (MoM/YoY, top hike, top drop, verdict).
- **Table does the work a summary should.** 112 rows is a reference, not an
  answer. Lead with **per-category stat tiles** and a **ranked movers**
  view; make the full table a secondary "detail" tab.
- **Polarity is under-encoded.** MoM/YoY are inherently diverging
  (cheaper ↔ dearer). Use a **diverging encoding** (one cool pole for
  price falls = opportunity, one warm pole for rises = risk, neutral gray
  at 0) consistently across tiles, bars, and table cells.
- **No annotations.** The biggest stories (e.g. "Onion EU +130.8% MoM,
  supply snap-back") should be **called out on the charts** with a short
  labelled marker, not left for the reader to find.
- **Menu is thin with one card.** Give each quarter card a compact
  "at a glance" (HICP level + YoY arrow, count of risks/opportunities).

## 5. Visual system (rules the redesign must follow)

These come from the data-viz method — treat them as non-negotiable:

- **One axis per chart. Never dual-axis.** Two measures of different scale
  → two charts or index to a common base. (`teicp010` and Destatis CP01 do
  **not** share a base year — never co-plot them on one Y axis.)
- **Categorical color = fixed order, never cycled.** Assign the ~12
  category hues once in a fixed order; a filter that hides categories must
  **not** repaint the survivors. A 9th+ hue folds into "Other," never a
  generated color.
- **Diverging for MoM/YoY:** two hues + a neutral gray midpoint at 0%.
  Cool = price down (opportunity), warm = price up (risk). Never a rainbow.
- **Status colors are reserved** (good / warning / serious / critical) and
  ship with an icon + label — never color alone, never reused as a series.
- **Text wears text tokens** (primary/secondary/muted ink), never the
  series color. A colored mark sits *beside* the label to carry identity.
- **Marks:** thin (2px lines, ≥8px markers), rounded 4px data-ends on the
  baseline, 2px surface gap between adjacent fills, recessive grid/axes.
- **Legend present for ≥2 series; single series names itself in the title.
  Direct-label selectively** — never a number on every point.
- **Accessibility:** color is never the only signal (arrows/±/icons +
  labels); a **table view** always exists; **dark mode is designed**, not
  auto-flipped — steps re-picked against the dark surface; texture/pattern
  available for colorblind & print.
- **Hover by default:** crosshair+tooltip on line/area, per-mark tooltip on
  bars/cells. Filters sit in one row above the charts.

## 6. Annotation requirements (explicitly requested)

- **On-chart callouts** for the 2–3 headline movers per quarter: a small
  anchored marker + one line ("Tomato EU +48% MoM — Spanish shortage").
  Source these from `meta.json → highlights` and the top movers.
- **Per-category verdict chip**: Risk / Watch / Opportunity, with the
  reason ("Butter EU −51% YoY → lock long-term").
- **Method note** near any HICP chart clarifying base year (2025 = 100) and
  that German data is Destatis (2020 = 100) — the two aren't comparable.
- Keep annotations **short, factual, and numeric**; they explain the mark,
  they don't decorate it.

## 7. Constraints

- Static HTML only (Tailwind CDN + Chart.js), dark theme, no framework.
- Content is generated from JSON by `scripts/build_html.py` /
  `scripts/build_dashboard.py` — the redesign must be expressible as an
  HTML/CSS template those scripts emit. Deliver **annotated static mockups
  + the HTML/CSS**, not a React app.
- Data shape is fixed: `commodities.json` (category, name, mom_pct,
  yoy_pct), `meta.json` (highlights, trend), `hicp_index.json`,
  `destatis.json`.

---

## Prompt to paste

> Copy everything below into a fresh Claude design session (attach a
> screenshot of the current dashboard if you can).

```
You are designing the UI for a quarterly "Commodity Dashboard" used by
CATEGORY PROCUREMENT MANAGERS at a European food & catering business
(Procurement PMO — Europe / Strategic Procurement & Logistics).

AUDIENCE & JOB: Each user owns one category (Dairy, Meat & Poultry,
Oilseeds & Vegetable Oils, Packaging, Fish & Seafood, Grains & Feed,
Softs, Fruit & Veg, etc.). Opening the dashboard they need, in ~10
seconds: (1) did MY category rise or fall this quarter, MoM and YoY?
(2) which commodities are risks (big price rises → renegotiate/hedge) vs
opportunities (deep deflation → lock long-term contracts)? (3) one or two
defensible headlines with numbers to brief stakeholders.

DELIVERABLES:
1. An annotated redesign of two screens — (a) a landing menu to pick a
   reporting quarter, and (b) the quarter report — as static mockups with
   callouts explaining each design decision.
2. The corresponding HTML + CSS (Tailwind via CDN is fine; charts via
   Chart.js). NO React / framework — it must render as a plain static file.

MAKE IT CATEGORY-FIRST: add a category rail/chips that filter the report
and drive a per-category summary card (MoM %, YoY %, top hike, top drop,
and a Risk/Watch/Opportunity verdict with a one-line reason). Lead with
per-category stat tiles and a ranked "top movers" view; demote the full
~112-row commodity table to a secondary "detail" tab.

VISUAL SYSTEM (follow strictly):
- Dark theme. Surfaces ~ #0F172A background, #1E293B cards, text #F8FAFC /
  muted #94A3B8, primary blue #60A5FA.
- One Y axis per chart — never dual-axis. If two measures differ in scale,
  use two charts or index to a common base. (Note: EU HICP is base
  2025=100 and German Destatis is base 2020=100 — never co-plot them.)
- Encode MoM/YoY as DIVERGING: a cool hue for price falls (opportunity), a
  warm hue for price rises (risk), neutral gray at 0%. Use it consistently
  in stat tiles, movers bars, and table cells.
- Category colors: a fixed hue order assigned once, never cycled or
  repainted when filtered; a 9th+ category folds into "Other".
- Reserve status colors (good/warning/serious/critical) for verdicts, with
  an icon + label, never color alone. Never reuse them as chart series.
- Labels/values/legends wear neutral text ink, never the series color.
- Thin marks (2px lines, ≥8px points), rounded 4px bar ends on the
  baseline, recessive grid/axes, legend for ≥2 series, selective direct
  labels (not every point).
- Every chart has hover (crosshair+tooltip / per-mark tooltip); filters in
  one row above the charts; a table view always available; colorblind-safe
  (verify adjacent hues are distinguishable; add arrows/±/patterns).

ANNOTATIONS (important): put short, numeric on-chart callouts on the 2–3
headline movers per quarter (e.g. "Onion EU +130.8% MoM — supply
snap-back"); add a per-category verdict chip with its reason ("Butter EU
−51% YoY → lock long-term"); add a method note wherever HICP appears
(base 2025=100; German data is Destatis 2020=100 and not directly
comparable). Annotations must explain the mark, not decorate it.

TONE: institutional, calm, data-dense but scannable — a procurement
analyst's tool, not a marketing page. Deliver light explanatory captions
so a manager who isn't a data analyst can still read every chart.
```
