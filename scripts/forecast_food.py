"""Statistical 6-month projection of the food CPI series -> data/food_forecast.json

For the total food index and every product group (COICOP class level) of each market:
the full monthly history since 2015 is fetched (Eurostat prc_hicp_minr; ONS MM23 for
the UK), an exponential-smoothing (ETS) model is fitted to the log index - the best of
four variants (with / without damped trend, with / without 12-month seasonality) by AICc -
and the next six months are projected with an 80 % prediction interval.

This is a mechanical extrapolation of the past, NOT an official forecast: it cannot see
shocks (energy, tax changes). To say how far to trust it, the script back-tests the total
food index of every market (rolling origins over the last 30 months, 6 months ahead,
year-on-year error) against a naive "inflation stays where it is" baseline and stores that
error in `backtest`. The back-test only covers the total, not the individual groups.

Germany: the Germany screen uses the Destatis national CPI (a different, shorter series).
Its projection uses the Eurostat HICP series for Germany, rebased to the Destatis last value
in the client.

Needs: pip install statsmodels numpy.   Run:  py scripts/forecast_food.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_food_cpi import UK, GEOS  # noqa: E402
from fetch_indirect_countries import EUROSTAT, INFL, ONS, SHORT, get_json  # noqa: E402
from statsmodels.tsa.exponential_smoothing.ets import ETSModel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "food_forecast.json"
SINCE = "2015-01"
H = 6
CFGS = [(None, False, None), ("add", True, None), (None, False, "add"), ("add", True, "add")]


def fit_best(y: np.ndarray):
    best = None
    for tr, damped, se in CFGS:
        try:
            res = ETSModel(y, error="add", trend=tr, damped_trend=damped, seasonal=se,
                           seasonal_periods=12 if se else None).fit(disp=False)
        except Exception:                                   # noqa: BLE001 - skip variants that do not converge
            continue
        if best is None or res.aicc < best.aicc:
            best = res
    return best


def project(vals: list[float]):
    y = pd.Series(np.log(np.array(vals, dtype=float)), index=pd.date_range("2000-01-01", periods=len(vals), freq="MS"))
    res = fit_best(y)
    if res is None:
        return None
    sf = res.get_prediction(start=len(y), end=len(y) + H - 1).summary_frame(alpha=0.2)
    f = lambda col: [round(float(np.exp(v)), 2) for v in sf[col]]    # noqa: E731
    return {"fc": f("mean"), "lo": f("pi_lower"), "hi": f("pi_upper")}


def backtest(vals: list[float]):
    y = np.log(np.array(vals, dtype=float))
    em, nv = [], []
    for o in range(len(y) - H - 30, len(y) - H):
        res = fit_best(y[: o + 1])
        if res is None:
            continue
        tgt = o + H
        fc = float(res.forecast(H)[-1])
        actual = (np.exp(y[tgt] - y[tgt - 12]) - 1) * 100
        em.append(abs((np.exp(fc - y[tgt - 12]) - 1) * 100 - actual))
        nv.append(abs((np.exp(y[o] - y[o - 12]) - 1) * 100 - actual))
    return {"ets": round(float(np.mean(em)), 2), "naive": round(float(np.mean(nv)), 2), "n": len(em)}


def main() -> None:
    nodes = json.loads((ROOT / "data" / "food_cpi.json").read_text(encoding="utf-8"))["nodes"]
    codes = sorted(c for c in nodes if c.startswith("CP") and len(c) <= 6)
    print(f"Eurostat history since {SINCE}: {len(codes)} codes x {len(GEOS)} markets ...")
    q = urlencode({"format": "JSON", "unit": "I25", "geo": GEOS, "coicop18": codes, "sinceTimePeriod": SINCE}, doseq=True)
    d = get_json(EUROSTAT + "prc_hicp_minr?" + q)
    ids, size = d["id"], d["size"]
    cats = {i: list(d["dimension"][i]["category"]["index"]) for i in ids}
    st = [1] * len(ids)
    for k in range(len(ids) - 2, -1, -1):
        st[k] = st[k + 1] * size[k + 1]
    hist: dict[tuple[str, str], dict[str, float]] = {}
    for pos, v in d.get("value", {}).items():
        pos = int(pos)
        ix = {ids[k]: (pos // st[k]) % size[k] for k in range(len(ids))}
        hist.setdefault((cats["geo"][ix["geo"]], cats["coicop18"][ix["coicop18"]]), {})[cats["time"][ix["time"]]] = float(v)

    print("ONS history (UK) ...")
    for cdid, code, _ in UK:
        if code.count(".") > 2:
            continue
        j = get_json(ONS.format(path=INFL, cdid=cdid.lower(), ds="mm23"))
        s: dict[str, float] = {}
        for r in j["months"]:
            try:
                val = float(r["value"])
            except (KeyError, ValueError):
                continue
            y, mon = r["date"].split()
            p = f"{y}-{[x.upper() for x in SHORT].index(mon[:3].upper()) + 1:02d}"
            if p >= SINCE:
                s[p] = val
        if s:
            hist[("UK", "uk:" + code)] = s

    series: dict[str, dict] = {}
    for (g, c), s in sorted(hist.items()):
        ps = sorted(s)
        if len(ps) < 60 or ps[-1] != max(p for (gg, _), ss in hist.items() if gg == g for p in ss):
            continue                                          # need 5+ years and an up-to-date series
        out = project([s[p] for p in ps])
        if out:
            series[f"{g}|{c}"] = {"last": ps[-1], **out}
    print(f"projected {len(series)} series")

    bt = {}
    for (g, c), s in sorted(hist.items()):
        if c not in ("CP01", "uk:01"):
            continue
        ps = sorted(s)
        if len(ps) >= 80:
            bt[g] = backtest([s[p] for p in ps])
            print(f"  back-test {g}: ETS {bt[g]['ets']} pp vs naive {bt[g]['naive']} pp (6-month-ahead YoY error)")
    out = {"horizon": H, "level": 0.8, "since": SINCE, "series": series, "backtest": bt}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
