# Input drop folder

Put next month's raw files here. Accepted:

- `overview.pdf`  — Expana Commodity Price Change Overview Report
- `forecast.xlsx` — Mintec forward curves export
- `hicp.xlsx`     — (optional) HICP data; if omitted, Eurostat API is used

Any filename works — the skill will rename them when they are moved
into `data/{period}/raw/`. After the new dashboard is built, this
folder should end up empty again.

To produce the dashboard, invoke the `new-month-dashboard` skill or
tell Claude "new month dashboard" / "regenerate for <Month Year>".
