"""Freeze the published Forecast-tab projections so they can later be scored against actuals.

Appends one snapshot to data/food_forecast_archive.json whenever the forecast was made on a data
month that is not archived yet (the weekly refresh therefore adds a snapshot only when new data
arrived). Existing snapshots are never rewritten - that is the point: no hindsight.
"""
from __future__ import annotations
import datetime as dt, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "food_forecast.json"
ARCH = ROOT / "data" / "food_forecast_archive.json"


def main() -> None:
    f = json.loads(SRC.read_text(encoding="utf-8"))
    arch = json.loads(ARCH.read_text(encoding="utf-8")) if ARCH.exists() else {"snapshots": []}
    have = {(s["last"]) for s in arch["snapshots"]}
    # one snapshot per origin month: the series' own `last` (UK/EU can differ by a month)
    by_last: dict[str, dict] = {}
    for k, e in f["series"].items():
        by_last.setdefault(e["last"], {})[k] = {"yoy": e["yoy"], "lo": e["lo"], "hi": e["hi"], "model": e["model"]}
    added = 0
    for last, ser in sorted(by_last.items()):
        if last in have:
            continue
        arch["snapshots"].append({"made": dt.date.today().isoformat(), "last": last, "series": ser})
        added += 1
    ARCH.write_text(json.dumps(arch, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"archive: +{added} snapshot(s), {len(arch['snapshots'])} total")


if __name__ == "__main__":
    main()
