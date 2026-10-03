"""Running the scan EARLY: judge the 30-min candle after only 20 or 25 minutes (user is in office). Spec fixed 2026-10-03.
Same rules as 43 (1H EMA34 level of the candle's hour, 1H EMA8 < EMA34, live daily 8-EMA wick + below it, daily ADX <= 25,
below VWAP, liquid, red candle, high >= EMA, close < EMA within 0.5%, 2:1 rule: stop = candle high <= 0.5%), but the
'candle' is its first n 5m bars: n = 4 (20 min), 5 (25 min), 6 (full 30 min). Entry at the close of bar n, stop = high
so far, target -1%, out 5h/EOD. Alarms 10:45/11:15/11:45/12:15. 5m data Jun 10 - Sep 30 2026. Also: of the early (n=5)
setups, how many still qualify at the full candle, and how the ones that don't qualify did."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"; A8 = 2 / 9


def read(p):
    x = pd.read_csv(p, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def run(t):
    if not (H1 / f"{t}.csv").exists() or not (M5 / f"{t}.csv").exists(): return []
    try: d = load(t)
    except Exception: return []
    d = d[d.index < pd.Timestamp("2026-10-01")]
    h1, m5 = read(H1 / f"{t}.csv"), read(M5 / f"{t}.csv")
    h1 = h1[h1.index < "2026-10-01"]
    if len(h1) < 200 or m5.empty: return []
    e34h = h1.Close.ewm(span=34, adjust=False).mean().shift(1); e8h = h1.Close.ewm(span=8, adjust=False).mean().shift(1)
    d8y = d.Close.ewm(span=8, adjust=False).mean().shift(1); adx = _compute_adx(d)[0].shift(1); tv = d.traded_value_sma20.shift(1)
    rows = []
    for day, g in m5.groupby(m5.index.normalize()):
        if day >= pd.Timestamp("2026-10-01") or len(g) < 70 or day not in d.index or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        if abs(g.Close.iloc[-1] / d.Close.loc[day] - 1) > 0.02: continue
        D8, AD = d8y.get(day, np.nan), adx.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25: continue
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1); hi_day = np.maximum.accumulate(H)
        base = day + pd.Timedelta("9h15min"); k30 = (T - base) // pd.Timedelta("30min")
        for q in (2, 3, 4, 5):                                   # candles ending 10:45, 11:15, 11:45, 12:15
            qi = np.where(k30 == q)[0]
            if len(qi) < 6: continue
            cs = base + q * pd.Timedelta("30min"); hs = base + ((cs - base) // pd.Timedelta("60min")) * pd.Timedelta("60min")
            E, E8 = e34h.get(hs, np.nan), e8h.get(hs, np.nan)
            if np.isnan(E) or not E8 < E: continue
            res = {}
            for n in (4, 5, 6):
                bi = qi[:n]; b = bi[-1]; qo, qh, qc = O[bi[0]], H[bi].max(), C[b]
                ok = (qc < qo and qh >= E and qc < E and (E - qc) / E * 100 <= 0.5 and qc < D8
                      and hi_day[b] >= A8 * qc + (1 - A8) * D8 and qc < vw[b] and (qh - qc) / qc * 100 <= 0.5)
                if not ok: res[n] = None; continue
                tgt, end = qc * 0.99, T[b] + pd.Timedelta("5h"); px = C[-1]
                for k in range(b + 1, len(C)):
                    if H[k] >= qh: px = qh; break
                    if L[k] <= tgt: px = tgt; break
                    if T[k] >= end: px = C[k]; break
                res[n] = (qc - px) / qc * 100
            for n in (4, 5, 6):
                if res[n] is not None:
                    rows.append(dict(ticker=t, date=day, q=q, n=n, ret=res[n], full_ok=res[6] is not None))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=8), []))
    R.to_csv(HERE / "partial_candle.csv", index=False)
    print("| judged the candle after | setups | mean % | win% | Jun / Jul / Aug / Sep | still a setup at the full 30 min |\n|---|---|---|---|---|---|")
    for n, lab in ((4, "20 min (e.g. run 11:10 for 11:15)"), (5, "25 min (e.g. run 11:12 for 11:15)"), (6, "full 30 min (current)")):
        x = R[R.n == n]; m = x.groupby(pd.to_datetime(x.date).dt.month).ret.mean()
        print(f"| {lab} | {len(x)} | {x.ret.mean():+.3f} | {(x.ret>0).mean()*100:.0f} | " + " / ".join(f"{v:+.2f}" for v in m) + f" | {x.full_ok.mean()*100:.0f}% |")
    x = R[R.n == 5]
    print(f"\n25-min early setups that STILL qualify at 30 min: n {x.full_ok.sum()}, mean {x[x.full_ok].ret.mean():+.3f}% | "
          f"that DON'T (candle changed in the last 5 min): n {(~x.full_ok).sum()}, mean {x[~x.full_ok].ret.mean():+.3f}%")
