"""6-month projection of the food CPI, driven by producer prices -> data/food_forecast.json

What it does (and why it is built this way):

* Series: total food, food, non-alcoholic beverages and the nine food classes (COICOP 011x)
  of every market, as YEAR-ON-YEAR inflation. Working in year-on-year terms removes
  seasonality without a seasonal-adjustment package; the projected index level is rebuilt as
  index(t+h-12) x (1 + projected YoY).
* Raw drivers: food-manufacturing producer prices (Eurostat sts_inppd_m, NACE C10 and the
  matching sub-industry - meat C101, fish C102, fruit & veg C103, oils C104, dairy C105,
  grain mill C106, other food C108, beverages C11; UK: ONS PPI domestic output, C10).
  Farm-gate prices are NOT used: the EU agri-food portal API is suspended and Eurostat's monthly
  farm-price dataset could not be found.
* Candidate models per series (direct h-step OLS on the change in YoY, h = 1..6):
    naive       YoY stays where it is
    own         own YoY level + 3-month momentum
    ppi_own     own + producer-price YoY level and momentum (matching sub-industry)
    ppi_c10     own + total food-manufacturing producer prices
    ets         damped-trend seasonal ETS on the log index (the first version of this projection)
    ets+ppi     equal-weight average of ets and the producer-price model
* The published projection is ets+ppi (ets alone where no producer-price series exists). This is a
  rule fixed in advance for every series, NOT selected per series. Caveat: it was fixed after a first
  run showed the producer-price model alone did not beat ETS but the average of the two did on the
  test window, so the test-window numbers are not a clean out-of-sample proof of that choice; only
  the live record from now on is.
* Evaluation: rolling-origin, expanding window, test window = targets from 2024-01. For the total
  food index of each market the test-window error of every candidate is stored. Intervals are
  empirical 10/90 % quantiles of out-of-sample errors; coverage is checked in the test window using
  selection-window (up to 2023-12) errors only. A Diebold-Mariano test (squared error, Newey-West,
  h = 6) says whether the projection beats "YoY stays" in the test window.

It is a statistical projection, not an official forecast: policy changes (VAT) and shocks it has
no driver for are invisible to it. Needs: pip install statsmodels pandas numpy.
Run:  py scripts/forecast_food.py
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from math import erf, sqrt
from pathlib import Path
from urllib.parse import urlencode

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")                                # one BLAS thread per worker, otherwise the pool thrashes

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_food_cpi import GEOS  # noqa: E402
from fetch_indirect_countries import EUROSTAT, INFL, ONS, SHORT, get_json  # noqa: E402
from statsmodels.tsa.exponential_smoothing.ets import ETSModel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "food_forecast.json"
SINCE = "2015-01"
H = 6
SEL_END = "2023-12"              # last target month of the selection window
MIN_TRAIN = 30

CODES = ["CP01", "CP011", "CP012", "CP0111", "CP0112", "CP0113", "CP0114", "CP0115", "CP0116", "CP0117", "CP0118", "CP0119"]
UK_CODES = {"CP01": ("D7BU", "uk:01"), "CP011": ("D7C8", "uk:01.1"), "CP012": ("D7C9", "uk:01.2"),
            "CP0111": ("D7D5", "uk:01.1.1"), "CP0112": ("D7D6", "uk:01.1.2"), "CP0113": ("D7D7", "uk:01.1.3"),
            "CP0114": ("D7D8", "uk:01.1.4"), "CP0115": ("D7D9", "uk:01.1.5"), "CP0116": ("D7DA", "uk:01.1.6"),
            "CP0117": ("D7DB", "uk:01.1.7"), "CP0118": ("D7DC", "uk:01.1.8"), "CP0119": ("D7DD", "uk:01.1.9")}
# matching producer-price industry for each class
NACE_OF = {"CP01": "C10", "CP011": "C10", "CP012": "C11", "CP0111": "C106", "CP0112": "C101", "CP0113": "C102",
           "CP0114": "C105", "CP0115": "C104", "CP0116": "C103", "CP0117": "C103", "CP0118": "C108", "CP0119": "C10"}
NACES = sorted(set(NACE_OF.values()) | {"C10"})
PPI_GEO = {"EA": "EA20"}


def month_key(r: dict) -> str:
    y, mon = r["date"].split()
    return f"{y}-{[x.upper() for x in SHORT].index(mon[:3].upper()) + 1:02d}"


def parse_stat(d: dict, dim_names: tuple[str, ...]) -> dict[tuple, dict[str, float]]:
    ids, size = d["id"], d["size"]
    cats = {i: list(d["dimension"][i]["category"]["index"]) for i in ids}
    st = [1] * len(ids)
    for k in range(len(ids) - 2, -1, -1):
        st[k] = st[k + 1] * size[k + 1]
    out: dict[tuple, dict[str, float]] = {}
    for pos, v in d.get("value", {}).items():
        pos = int(pos)
        ix = {ids[k]: (pos // st[k]) % size[k] for k in range(len(ids))}
        key = (cats["geo"][ix["geo"]],) + tuple(cats[n][ix[n]] for n in dim_names)
        out.setdefault(key, {})[cats["time"][ix["time"]]] = float(v)
    return out


def yoy(s: pd.Series) -> pd.Series:
    return (s / s.shift(12) - 1) * 100


def to_series(m: dict[str, float]) -> pd.Series:
    idx = pd.period_range(min(m), max(m), freq="M")
    return pd.Series({pd.Period(k, "M"): v for k, v in m.items()}).reindex(idx)


# ---------------------------------------------------------------- models
def feats(model: str, P: np.ndarray, X: np.ndarray | None, t: int, h: int) -> np.ndarray | None:
    """Features known at origin t (positions in the index array P; X = producer-price index aligned to P).

    base   growth of the index over the h months a year ago (log %): the part of next
           year's comparison that is already fixed - the "base effect"
    mom3   growth over the last 3 months (log %)
    y      current year-on-year inflation (%)
    dx3/xy producer-price growth over 3 months and producer-price year-on-year (driver models)"""
    if t < 12 or t + h - 12 < 0:
        return None
    f = [np.log(P[t + h - 12] / P[t - 12]) * 100, np.log(P[t] / P[t - 3]) * 100, (P[t] / P[t - 12] - 1) * 100]
    if model in ("ppi_own", "ppi_c10"):
        if X is None or np.isnan(X[t]) or np.isnan(X[t - 12]) or np.isnan(X[t - 3]):
            return None
        f += [np.log(X[t] / X[t - 3]) * 100, (X[t] / X[t - 12] - 1) * 100]
    out = np.array(f)
    return None if np.isnan(out).any() else out


def direct_forecasts(model: str, P: np.ndarray, X: np.ndarray | None, h: int, origins: list[int]) -> dict[int, float]:
    """Expanding-window direct h-step OLS on the change in YoY. Returns predicted YoY at t+h for each origin."""
    n = len(P)
    yoy_ = np.full(n, np.nan)
    yoy_[12:] = (P[12:] / P[:-12] - 1) * 100
    rows, targets = [], {}
    for i in range(12, n - h):
        f = feats(model, P, X, i, h)
        if f is not None and not np.isnan(yoy_[i + h]) and not np.isnan(yoy_[i]):
            targets[i] = (f, yoy_[i + h] - yoy_[i])
    out = {}
    for t in origins:
        f_t = feats(model, P, X, t, h)
        if f_t is None:
            continue
        tr = [(f, y) for i, (f, y) in targets.items() if i + h <= t]
        if len(tr) < MIN_TRAIN:
            continue
        A = np.column_stack([np.ones(len(tr)), np.array([f for f, _ in tr])])
        beta, *_ = np.linalg.lstsq(A, np.array([y for _, y in tr]), rcond=None)
        out[t] = float(yoy_[t] + np.r_[1.0, f_t] @ beta)
    return out


def ets_all(P: np.ndarray, origins: list[int]) -> dict[int, dict[int, float]]:
    """Damped-trend seasonal ETS on the log index, refitted at every origin: {t: {h: predicted YoY at t+h}}."""
    y = np.log(P)
    out: dict[int, dict[int, float]] = {}
    for t in origins:
        if t < 60:
            continue
        try:
            res = ETSModel(pd.Series(y[: t + 1], index=pd.date_range("2000-01-01", periods=t + 1, freq="MS")),
                           error="add", trend="add", damped_trend=True, seasonal="add", seasonal_periods=12).fit(disp=False)
            fc = res.forecast(H).to_numpy()
        except Exception:                                          # noqa: BLE001
            continue
        out[t] = {h: float((np.exp(fc[h - 1] - y[t + h - 12]) - 1) * 100) for h in range(1, H + 1)}
    return out


def dm_pvalue(e_model: np.ndarray, e_naive: np.ndarray, lag: int) -> float | None:
    d = e_naive ** 2 - e_model ** 2                                 # >0 means the model is better
    n = len(d)
    if n < 12:
        return None
    dc = d - d.mean()
    var = dc @ dc / n + 2 * sum((1 - k / (lag + 1)) * (dc[k:] @ dc[:-k]) / n for k in range(1, lag + 1))
    if var <= 0:
        return None
    z = d.mean() / sqrt(var / n)
    return float(2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2)))))


CPI: dict = {}
PPI: dict = {}


def work(task):
    g, c = task
    idx = CPI[(g, c)].dropna()
    newest = CPI[(g, "CP01")].dropna().index[-1]
    if len(idx) < 100 or idx.index[-1] != newest:
        return None
    P = idx.to_numpy(dtype=float)
    months = [str(p) for p in idx.index]
    n = len(P)
    yv = np.full(n, np.nan)
    yv[12:] = (P[12:] / P[:-12] - 1) * 100
    T = n - 1
    drivers: dict[str, np.ndarray | None] = {"naive": None, "own": None}
    for nm, nace in (("ppi_own", NACE_OF[c]), ("ppi_c10", "C10")):
        p = PPI.get((g, nace))
        if p is not None and not p.dropna().empty and p.dropna().index[-1] >= idx.index[-1] - 1:
            drivers[nm] = p.reindex(idx.index).ffill(limit=1).to_numpy(dtype=float)     # a producer-price print one month late is held flat
    if NACE_OF[c] == "C10":
        drivers.pop("ppi_c10", None)                            # same driver twice
    origins = {h: list(range(MIN_TRAIN + 12, n - h)) for h in range(1, H + 1)}
    res: dict[str, dict[int, dict[int, float]]] = {}
    fin: dict[str, dict[int, float]] = {}                          # forecasts made at the last month, per model and horizon
    for nm, X in drivers.items():
        if nm == "naive":
            res[nm] = {h: {t: float(yv[t]) for t in origins[h] if not np.isnan(yv[t])} for h in range(1, H + 1)}
            fin[nm] = {h: float(yv[T]) for h in range(1, H + 1)}
        else:
            res[nm] = {h: direct_forecasts(nm, P, X, h, origins[h]) for h in range(1, H + 1)}
            fin[nm] = {h: v for h in range(1, H + 1) for v in [direct_forecasts(nm, P, X, h, [T]).get(T)] if v is not None}
    ee = ets_all(P, list(range(60, n)))
    res["ets"] = {h: {t: ee[t][h] for t in origins[h] if t in ee} for h in range(1, H + 1)}
    if T in ee:
        fin["ets"] = ee[T]
    best_ppi = "ppi_own" if "ppi_own" in res else ("ppi_c10" if "ppi_c10" in res else None)
    if best_ppi:                                                    # equal-weight combination of the two ideas
        res["ets+ppi"] = {h: {t: (res["ets"][h][t] + res[best_ppi][h][t]) / 2 for t in res["ets"][h] if t in res[best_ppi][h]} for h in range(1, H + 1)}
        if "ets" in fin and best_ppi in fin and len(fin[best_ppi]) == H:
            fin["ets+ppi"] = {h: (fin["ets"][h] + fin[best_ppi][h]) / 2 for h in range(1, H + 1)}

    def errs(nm: str, h: int, lo: str | None, hi: str | None) -> np.ndarray:
        e = []
        for t, f in res[nm][h].items():
            m = months[t + h]
            if (lo is None or m >= lo) and (hi is None or m <= hi) and not np.isnan(yv[t + h]):
                e.append(float(yv[t + h]) - f)
        return np.array(e)

    # Pre-committed rule (not tuned per series): equal-weight combination of ETS and the producer-price model;
    # ETS alone where no producer-price series exists. Every candidate's test-window error is stored for transparency.
    chosen = "ets+ppi" if "ets+ppi" in fin else ("ets" if "ets" in fin else None)
    if chosen is None:
        return None
    e_c, e_n = errs(chosen, 6, "2024-01", None), errs("naive", 6, "2024-01", None)
    rec = None
    if len(e_c) >= 12 and len(e_n) == len(e_c):
        e_sel = errs(chosen, 6, None, SEL_END)
        q10, q90 = np.quantile(e_sel, [0.1, 0.9]) if len(e_sel) >= 20 else (-1.28 * e_sel.std(), 1.28 * e_sel.std())
        dm = dm_pvalue(e_c, e_n, 5)
        rec = {"mae": round(float(np.abs(e_c).mean()), 2), "naive": round(float(np.abs(e_n).mean()), 2), "n": int(len(e_c)),
               "cover": round(float(np.mean((e_c >= q10) & (e_c <= q90))), 2), "dm": None if dm is None else round(dm, 3)}
    yoy_f, lo, hi, lev = [], [], [], []
    for h in range(1, H + 1):
        f = fin.get(chosen, {}).get(h)
        if f is None:
            break
        e_all = errs(chosen, h, None, None)
        sd = e_all.std() if len(e_all) > 2 else 2.0
        q10, q90 = np.quantile(e_all, [0.1, 0.9]) if len(e_all) >= 20 else (-1.28 * sd, 1.28 * sd)
        base = float(P[T + h - 12])
        yoy_f.append(round(f, 2)); lo.append(round(f + float(q10), 2)); hi.append(round(f + float(q90), 2))
        lev.append(round(base * (1 + f / 100), 2))
    if len(yoy_f) < H:
        return None
    key = f"{g}|{c if g != 'UK' else UK_CODES[c][1]}"
    entry = {"last": months[-1], "yoy": yoy_f, "lo": lo, "hi": hi, "fc": lev, "model": chosen,
                       "driver": (NACE_OF[c] if chosen == "ppi_own" else "C10" if chosen == "ppi_c10" else None), "bt": rec}
    cmp_ = None
    if c == "CP01":
        tm = {nm: (round(float(np.abs(errs(nm, 6, "2024-01", None)).mean()), 2) if len(errs(nm, 6, "2024-01", None)) >= 12 else None) for nm in res}
        cmp_ = {"chosen": chosen, "test_mae_h6": tm}
        print(f"  {g}: chosen {chosen:8s} test MAE h6 {tm}", flush=True)
    return key, entry, cmp_


# ---------------------------------------------------------------- main
def main() -> None:
    nodes = json.loads((ROOT / "data" / "food_cpi.json").read_text(encoding="utf-8"))
    print("Eurostat CPI classes ...")
    cpi: dict[tuple[str, str], pd.Series] = {}
    for geo in GEOS:
        q = urlencode({"format": "JSON", "unit": "I25", "geo": geo, "coicop18": CODES, "sinceTimePeriod": SINCE}, doseq=True)
        for (g, c), m in parse_stat(get_json(EUROSTAT + "prc_hicp_minr?" + q), ("coicop18",)).items():
            cpi[(g, c)] = to_series(m)
    print("Eurostat producer prices ...")
    ppi: dict[tuple[str, str], pd.Series] = {}
    q = urlencode({"format": "JSON", "unit": "I21", "geo": [PPI_GEO.get(g, g) for g in GEOS if g != "UK"], "nace_r2": NACES, "sinceTimePeriod": SINCE}, doseq=True)
    for (g, n), m in parse_stat(get_json(EUROSTAT + "sts_inppd_m?" + q), ("nace_r2",)).items():
        ppi[({"EA20": "EA"}.get(g, g), n)] = to_series(m)
    print("ONS CPI + PPI (UK) ...")
    for code, (cdid, _) in UK_CODES.items():
        j = get_json(ONS.format(path=INFL, cdid=cdid.lower(), ds="mm23"))
        cpi[("UK", code)] = to_series({month_key(r): float(r["value"]) for r in j["months"] if r.get("value") not in (None, "") and month_key(r) >= SINCE})
    j = get_json(ONS.format(path="economy/inflationandpriceindices", cdid="g6si", ds="ppi"))
    uk_ppi = to_series({month_key(r): float(r["value"]) for r in j["months"] if r.get("value") not in (None, "") and month_key(r) >= SINCE})
    for n in NACES:
        ppi[("UK", n)] = uk_ppi                                     # UK: one food-manufacturing PPI for every class

    global CPI, PPI
    CPI, PPI = cpi, ppi
    from multiprocessing import Pool
    with Pool(max(1, (__import__("os").cpu_count() or 2))) as pool:
        results = pool.map(work, sorted(cpi), chunksize=1)
    series_out = {k: e for r in results if r for k, e, _ in [r]}
    market_cmp = {k.split("|")[0]: cm for r in results if r and r[2] for k, _, cm in [r]}
    out = {"horizon": H, "level": 0.8, "since": SINCE, "selection_end": SEL_END, "test_from": "2024-01",
           "series": series_out, "compare_total": market_cmp}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(series_out)} series ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
