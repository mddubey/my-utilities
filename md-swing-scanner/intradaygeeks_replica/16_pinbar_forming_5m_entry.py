"""Enter WHILE the 1H pin is forming, instead of waiting for the 1H close. Spec fixed before running (2026-10-01):
Level  : 1H EMA34 as of the last COMPLETED 1H bar (constant while the current hour forms). Trend: 1H EMA8 > EMA34 (long).
Daily  : daily 8-EMA as of yesterday's close; avoid if entry price on the wrong side; touch = day low so far at/through
         dEMA8 (+0.5% band), else untested.
Setup  : forming 1H candle starts at 10:15 or later (never the 09:15 candle), opened above the EMA (long), and a 5m bar
         inside it trades down to the EMA.
Entry  : close of the first 5m bar (at/after the touch, inside the same hour) that closes back above the EMA.
Stop   : the forming hour's low so far (the pin's wick). Target +1%. Out at 5 hours after entry or 15:25 close.
         Walked on 5m bars, stop first if a 5m bar hits both. Shorts mirrored. One position per ticker.
Days   : liquid (prior-day tv20 >= Rs 10 cr), >=70 5m bars, no corp action, 5m/daily close within 2%.
Data   : 5m intraday_cache (Jun 10 - Sep 30 2026 only); 1H EMAs from h1_cache. Gross of costs.
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def run(t):
    if not (H1 / f"{t}.csv").exists() or not (M5 / f"{t}.csv").exists(): return []
    try: d = load(t)
    except FileNotFoundError: return []
    h1, m5 = read(H1 / f"{t}.csv"), read(M5 / f"{t}.csv")
    if len(h1) < 200 or m5.empty: return []
    lev = pd.DataFrame({"e34": h1.Close.ewm(span=34, adjust=False).mean().shift(1),
                        "e8": h1.Close.ewm(span=8, adjust=False).mean().shift(1), "hopen": h1.Open}, index=h1.index)
    de8 = d.Close.ewm(span=8, adjust=False).mean().shift(1)
    tv = d.traded_value_sma20.shift(1)
    rows = []
    for day, g in m5.groupby(m5.index.normalize()):
        if len(g) < 70 or day not in d.index or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        if abs(g.Close.iloc[-1] / d.Close.loc[day] - 1) > 0.02: continue
        D8 = de8.loc[day]
        hl = lev[(lev.index >= day) & (lev.index < day + pd.Timedelta("1D"))]
        if hl.empty or np.isnan(D8): continue
        O, H, L, C = (g[k].values for k in ("Open", "High", "Low", "Close"))
        T = g.index
        hstart = hl.index[np.searchsorted(hl.index.values, T.values, side="right") - 1]   # 1H bucket of each 5m bar
        lo_day, hi_day = np.minimum.accumulate(L), np.maximum.accumulate(H)
        free_from = 0
        for hs in hl.index:
            if hs.hour * 60 + hs.minute < 10 * 60 + 15: continue
            idx = np.where(hstart == hs)[0]
            if len(idx) == 0 or idx[0] < free_from: continue
            E, e8, ho = hl.loc[hs, ["e34", "e8", "hopen"]]
            if np.isnan(E): continue
            if e8 > E and ho > E: s = 1
            elif e8 < E and ho < E: s = -1
            else: continue
            touch = next((k for k in idx if (L[k] <= E if s == 1 else H[k] >= E)), None)
            if touch is None: continue
            b = next((k for k in idx if k >= touch and (C[k] - E) * s > 0), None)
            if b is None: continue
            entry = C[b]
            stop = L[idx[0]:b + 1].min() if s == 1 else H[idx[0]:b + 1].max()
            risk = (entry - stop) * s
            if risk <= 0: continue
            if (entry - D8) * s < 0: dstate = "wrong"
            elif (s == 1 and lo_day[b] <= D8 * 1.005) or (s == -1 and hi_day[b] >= D8 * 0.995): dstate = "touch"
            else: dstate = "untested"
            tgt, end = entry * (1 + s * 0.01), T[b] + pd.Timedelta("5h")
            px, why, k = None, None, b
            for k in range(b + 1, len(C)):
                if (L[k] <= stop) if s == 1 else (H[k] >= stop): px, why = stop, "stop"; break
                if (H[k] >= tgt) if s == 1 else (L[k] <= tgt): px, why = tgt, "target"; break
                if T[k] >= end: px, why = C[k], "time5h"; break
            if px is None: px, why, k = C[-1], "eod", len(C) - 1
            ret = (px - entry) / entry * 100 * s
            rows.append(dict(ticker=t, date=day, hour=hs.strftime("%H:%M"), entry_time=T[b].strftime("%H:%M"),
                             side="long" if s == 1 else "short", dstate=dstate, entry=entry, stop_rs=risk,
                             stop_pct=risk / entry * 100, entry_past_ema_pct=(entry - E) * s / entry * 100,
                             wick_past_ema_pct=(E - stop) * s / entry * 100, exit=why, ret=ret, R=ret / (risk / entry * 100),
                             minutes=(T[k] - T[b]).seconds // 60))
            free_from = k + 1
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv"))
    out = []
    with Pool(6) as pool:
        for n, r in enumerate(pool.imap_unordered(run, tick, chunksize=8), 1):
            out += r
            if n % 500 == 0: print(f"  {n}/{len(tick)}", flush=True)
    R = pd.DataFrame(out); R.to_csv(HERE / "pinbar_forming_5m_results.csv", index=False)
    print("trades", len(R), R.date.min(), R.date.max())
