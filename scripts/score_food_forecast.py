"""Score the frozen forecasts (data/food_forecast_archive.json) against what actually happened.

Actual YoY comes from data/food_cpi.json. Naive benchmark = "inflation stays where it was at the
forecast origin". Writes data/food_forecast_live.json: per series and horizon, number of scored
forecasts, mean absolute error of the model and of naive, plus a pooled summary.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = 6


def add_m(iso: str, k: int) -> str:
    y, m = map(int, iso.split("-")); m += k - 1
    return f"{y + m // 12}-{m % 12 + 1:02d}"


def main() -> None:
    cpi = json.loads((ROOT / "data" / "food_cpi.json").read_text(encoding="utf-8"))
    arch = json.loads((ROOT / "data" / "food_forecast_archive.json").read_text(encoding="utf-8"))
    pos = {m: i for i, m in enumerate(cpi["months"])}

    def yoy(cc: str, code: str, m: str):
        s = cpi["countries"].get(cc, {}).get("series", {}).get(code)
        if not s or m not in pos or add_m(m, -12) not in pos:
            return None
        a, b = s[pos[m]], s[pos[add_m(m, -12)]]
        return None if a is None or b is None or b == 0 else (a / b - 1) * 100

    acc: dict[str, list[list[tuple[float, float]]]] = {}
    for snap in arch["snapshots"]:
        for key, e in snap["series"].items():
            cc, code = key.split("|")
            base = yoy(cc, code, snap["last"])
            if base is None:
                continue
            for h in range(1, H + 1):
                act = yoy(cc, code, add_m(snap["last"], h))
                if act is None:
                    continue
                acc.setdefault(key, [[] for _ in range(H)])[h - 1].append((abs(e["yoy"][h - 1] - act), abs(base - act)))
    series, pool = {}, [[0, 0.0, 0.0] for _ in range(H)]
    for key, hs in acc.items():
        series[key] = {"n": [len(x) for x in hs],
                       "mae": [round(sum(a for a, _ in x) / len(x), 2) if x else None for x in hs],
                       "naive": [round(sum(b for _, b in x) / len(x), 2) if x else None for x in hs]}
        for i, x in enumerate(hs):
            pool[i][0] += len(x); pool[i][1] += sum(a for a, _ in x); pool[i][2] += sum(b for _, b in x)
    out = {"snapshots": [{"made": s["made"], "last": s["last"], "n": len(s["series"])} for s in arch["snapshots"]],
           "series": series,
           "pooled": {"n": [p[0] for p in pool],
                      "mae": [round(p[1] / p[0], 2) if p[0] else None for p in pool],
                      "naive": [round(p[2] / p[0], 2) if p[0] else None for p in pool]}}
    (ROOT / "data" / "food_forecast_live.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"live record: {len(arch['snapshots'])} snapshot(s), scored forecasts per horizon {out['pooled']['n']}")


if __name__ == "__main__":
    main()
