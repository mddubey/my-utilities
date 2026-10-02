"""How much confirmation is enough? Confirmation candle length L = 5 / 15 / 30 / 60 min (built from 5m, aligned to the
hour start). Spec fixed 2026-10-02 before running. 5m data Jun 10 - Sep 30 2026. Level = 1H EMA34 as of the last
completed hour (fixed while the hour forms); 1H EMA8 < EMA34. Forming hours 10:15 and 11:15. First L-candle in the hour
that is red, high >= EMA, close < EMA and within 0.5% of it -> short at its close, stop = its high, target -1%, out at
5h or the day's last 5m close (stop first). At entry: day's high so far >= live daily 8-EMA, daily ADX(yday) <= 25,
close < session VWAP, liquid. One trade per ticker per hour. Reported with and without the 2:1 rule (stop <= 0.5%)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"
A8 = 2 / 9; LENS = (5, 15, 30, 60)


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def run(t):
    if not (H1 / f"{t}.csv").exists() or not (M5 / f"{t}.csv").exists(): return []
    try: d = load(t)
    except Exception: return []
    d = d[d.index < pd.Timestamp("2026-10-01")]
    h1, m5 = read(H1 / f"{t}.csv"), read(M5 / f"{t}.csv")
    if len(h1) < 200 or m5.empty: return []
    lev = pd.DataFrame({"e34": h1.Close.ewm(span=34, adjust=False).mean().shift(1),
                        "e8": h1.Close.ewm(span=8, adjust=False).mean().shift(1)}, index=h1.index)
    d8y = d.Close.ewm(span=8, adjust=False).mean().shift(1); adx = _compute_adx(d)[0].shift(1); tv = d.traded_value_sma20.shift(1)
    rows = []
    for day, g in m5.groupby(m5.index.normalize()):
        if len(g) < 70 or day not in d.index or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        if abs(g.Close.iloc[-1] / d.Close.loc[day] - 1) > 0.02: continue
        D8, AD = d8y.get(day, np.nan), adx.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25: continue
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1); hi_day = np.maximum.accumulate(H)
        for hstr in ("10:15", "11:15"):
            hs = pd.Timestamp(f"{day:%Y-%m-%d} {hstr}")
            if hs not in lev.index: continue
            E, e8 = lev.loc[hs, ["e34", "e8"]]
            if np.isnan(E) or not e8 < E: continue
            idx = np.where((T >= hs) & (T < hs + pd.Timedelta("60min")))[0]
            if len(idx) < 12: continue
            for Ln in LENS:
                n = Ln // 5
                for q0 in range(0, 12, n):
                    qi = idx[q0:q0 + n]
                    qo, qh, qc = O[qi[0]], H[qi].max(), C[qi[-1]]
                    if not (qc < qo and qh >= E and qc < E and (E - qc) / E * 100 <= 0.5): continue
                    b = qi[-1]; entry, stop = qc, qh
                    live = A8 * entry + (1 - A8) * D8
                    if entry >= D8 or hi_day[b] < live or entry >= vw[b]: break
                    tgt, end = entry * 0.99, T[b] + pd.Timedelta("5h"); px, why = C[-1], "eod"
                    for k in range(b + 1, len(C)):
                        if H[k] >= stop: px, why = stop, "stop"; break
                        if L[k] <= tgt: px, why = tgt, "target"; break
                        if T[k] >= end: px, why = C[k], "time"; break
                    rows.append(dict(L=Ln, ticker=t, date=day, hour=hstr, entry_time=f"{T[b] + pd.Timedelta('5min'):%H:%M}",
                                     stop_pct=(stop - entry) / entry * 100, below_ema=(E - entry) / E * 100, exit=why,
                                     ret=(entry - px) / entry * 100))
                    break
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=8), []))
    R.to_csv(HERE / "confirmation_length_5m.csv", index=False)
    nd = R.date.nunique()
    def line(x, lab):
        e = x.exit.value_counts(normalize=True); m = x.groupby(pd.to_datetime(x.date).dt.month).ret.mean()
        print(f"| {lab} | {len(x)} | {len(x)/nd:.1f} | {x.stop_pct.median():.2f}% | {x.below_ema.median():.2f}% | {e.get('target',0)*100:.0f}% / {e.get('stop',0)*100:.0f}% | "
              f"{(x.ret>0).mean()*100:.0f} | {x.ret.mean():+.3f} | {x.ret.mean()/x.stop_pct.mean():.2f} | " + " / ".join(f"{v:+.2f}" for v in m) + " |")
    H = "| confirmation candle | trades | per day | median stop | entry below EMA | target / stopped | win% | mean % | per 1% of stop | Jun / Jul / Aug / Sep |\n|---|---|---|---|---|---|---|---|---|---|"
    print(f"days {nd}\n\nALL (0.5% cap)\n" + H)
    for Ln in LENS: line(R[R.L == Ln], f"{Ln} min")
    print("\nWITH 2:1 RULE (stop <= 0.5%)\n" + H)
    for Ln in LENS: line(R[(R.L == Ln) & (R.stop_pct <= 0.5)], f"{Ln} min")
