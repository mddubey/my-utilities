"""Drop-one ablation of the checklist filters under the CURRENT rules (user, 2026-10-03). Spec fixed before running.
Setup core (always): rejection candle at the 1H EMA34 -- high >= EMA34 (as of the last completed hour), close back below
it within 0.5%; 2:1 rule (stop = candle high <= 0.5%); liquid (prior-day tv20 >= Rs 10cr); shorts.
Filters ablated one at a time (all others kept): F1 1H EMA8 < EMA34 | F2 red candle | F3 close below daily 8-EMA |
F4 day's high so far >= live daily 8-EMA | F5 daily ADX(yday) <= 25 | F6 close below session VWAP.
Sets: (a) 30-min trigger on 5m bars, alarms 10:45/11:15/11:45/12:15, Jun 10 - Sep 30 2026, outcome walked on 5m;
      (b) 1H trigger, setup candles 10:15/11:15 (alarms 11:15/12:15), 2024-01 .. 2026-09, outcome walked on 1H bars
          (VWAP from 1H typical price -- approximation). Target -1%, out at 5h (a) / 5 candles (b) or EOD, stop first.
KEEP a filter only if removing it lowers the all-setups mean in BOTH sets; otherwise it is not earning its place."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent; M5 = HERE.parent / "intraday_cache"; A8 = 2 / 9
END = pd.Timestamp("2026-10-01")


def read(p):
    x = pd.read_csv(p, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[((x.Volume > 0) | (x.High != x.Low)) & (x.index < END)]


def hour_key(idx):
    d = idx.normalize(); return d + pd.Timedelta("9h15min") + ((idx - d - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")


def daily_inputs(t):
    d = load(t); d = d[d.index < END]
    return d, d.Close.ewm(span=8, adjust=False).mean().shift(1), _compute_adx(d)[0].shift(1), d.traded_value_sma20.shift(1)


def gen_a(t):
    p = M5 / f"{t}.csv"
    if not p.exists(): return []
    try: d, d8y, adx, tv = daily_inputs(t)
    except Exception: return []
    m = read(p)
    if len(m) < 1500: return []
    hc = m.Close.groupby(hour_key(m.index)).last()
    e34 = hc.ewm(span=34, adjust=False).mean().shift(1); e8 = hc.ewm(span=8, adjust=False).mean().shift(1)
    rows = []
    for day, g in m.groupby(m.index.normalize()):
        if day < pd.Timestamp("2026-06-10") or len(g) < 70 or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        D8, AD = d8y.get(day, np.nan), adx.get(day, np.nan)
        if np.isnan(D8): continue
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1); hi_day = np.maximum.accumulate(H)
        base = day + pd.Timedelta("9h15min"); k30 = (T - base) // pd.Timedelta("30min")
        for q in (2, 3, 4, 5):
            qi = np.where(k30 == q)[0]
            if len(qi) < 6: continue
            hs = base + ((q * 30) // 60) * pd.Timedelta("60min")
            E, E8 = e34.get(hs, np.nan), e8.get(hs, np.nan)
            if np.isnan(E): continue
            b = qi[-1]; qo, qh, qc = O[qi[0]], H[qi].max(), C[b]
            if not (qh >= E and qc < E and (E - qc) / E * 100 <= 0.5 and (qh - qc) / qc * 100 <= 0.5): continue
            tgt, end = qc * 0.99, T[b] + pd.Timedelta("5h"); px = C[-1]
            for k in range(b + 1, len(C)):
                if H[k] >= qh: px = qh; break
                if L[k] <= tgt: px = tgt; break
                if T[k] >= end: px = C[k]; break
            rows.append(dict(set="a", ticker=t, date=day, ret=(qc - px) / qc * 100, F1=E8 < E, F2=qc < qo, F3=qc < D8,
                             F4=hi_day[b] >= A8 * qc + (1 - A8) * D8, F5=(AD <= 25) if not np.isnan(AD) else False, F6=qc < vw[b]))
    return rows


def gen_b(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try: d, d8y, adx, tv = daily_inputs(t)
    except Exception: return []
    h = read(p)
    if len(h) < 300: return []
    O, H, L, C, V, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.Volume.values, h.index
    E34 = h.Close.ewm(span=34, adjust=False).mean().shift(1).values; E8 = h.Close.ewm(span=8, adjust=False).mean().shift(1).values
    day = T.normalize(); last = np.r_[day[1:] != day[:-1], True]
    tp = (h.High + h.Low + h.Close) / 3
    vw = ((tp * h.Volume).groupby(day).cumsum() / h.Volume.groupby(day).cumsum().replace(0, np.nan)).values
    hi_day = h.High.groupby(day).cummax().values
    rows = []
    for i in range(200, len(C) - 1):
        if T[i] < pd.Timestamp("2024-01-01") or T[i].strftime("%H:%M") not in ("10:15", "11:15"): continue
        dd = day[i]
        if tv.get(dd, 0) < 1e8 or bool(d.corp_action_day.get(dd, False)): continue
        D8, AD = d8y.get(dd, np.nan), adx.get(dd, np.nan)
        if np.isnan(D8) or np.isnan(E34[i]): continue
        E = E34[i]; qh, qc = H[i], C[i]
        if not (qh >= E and qc < E and (E - qc) / E * 100 <= 0.5 and (qh - qc) / qc * 100 <= 0.5): continue
        tgt = qc * 0.99; px = None
        for j in range(i + 1, len(C)):
            if day[j] != dd: px = C[j - 1]; break
            if H[j] >= qh: px = qh; break
            if L[j] <= tgt: px = tgt; break
            if j - i >= 5 or last[j]: px = C[j]; break
        if px is None: continue
        rows.append(dict(set="b", ticker=t, date=dd, ret=(qc - px) / qc * 100, F1=E8[i] < E, F2=qc < O[i], F3=qc < D8,
                         F4=hi_day[i] >= A8 * qc + (1 - A8) * D8, F5=(AD <= 25) if not np.isnan(AD) else False, F6=qc < vw[i]))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    pd.concat([A, B]).to_csv(HERE / "filter_ablation.csv", index=False)
    F = ["F1", "F2", "F3", "F4", "F5", "F6"]
    name = {"F1": "1H trend (EMA8 < EMA34)", "F2": "red candle", "F3": "below daily 8-EMA", "F4": "wick pierced live daily 8-EMA",
            "F5": "daily ADX <= 25", "F6": "below VWAP"}
    nda, ndb = A.date.nunique(), B.date.nunique()
    def stat(D, m, nd, per):
        x = D[m]; y = x.groupby(per(x)).ret.mean()
        return x.ret.mean(), len(x) / nd, " / ".join(f"{v:+.2f}" for v in y)
    allA, allB = A[F].all(axis=1), B[F].all(axis=1)
    pa, pb = lambda x: x.date.dt.month, lambda x: x.date.dt.year
    ba, bb = stat(A, allA, nda, pa), stat(B, allB, ndb, pb)
    print(f"| version | 30m: setups/day | 30m: mean % | 30m by month | 1H: setups/day | 1H: mean % | 1H by year | verdict |\n|---|---|---|---|---|---|---|---|")
    print(f"| ALL filters (current) | {ba[1]:.1f} | {ba[0]:+.3f} | {ba[2]} | {bb[1]:.2f} | {bb[0]:+.3f} | {bb[2]} | |")
    for f in F:
        others = [g for g in F if g != f]
        ra, rb = stat(A, A[others].all(axis=1), nda, pa), stat(B, B[others].all(axis=1), ndb, pb)
        keep = ra[0] < ba[0] and rb[0] < bb[0]
        print(f"| without {name[f]} | {ra[1]:.1f} | {ra[0]:+.3f} | {ra[2]} | {rb[1]:.2f} | {rb[0]:+.3f} | {rb[2]} | {'KEEP (removing it hurts both)' if keep else 'not earning its place'} |")
    ra, rb = stat(A, np.ones(len(A), bool), nda, pa), stat(B, np.ones(len(B), bool), ndb, pb)
    print(f"| NO filters (core + 2:1 only) | {ra[1]:.1f} | {ra[0]:+.3f} | {ra[2]} | {rb[1]:.2f} | {rb[0]:+.3f} | {rb[2]} | |")
