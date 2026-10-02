"""Forming-pin entry, with a REAL rejection (user's framing, 2026-10-01). Spec fixed before running.
Same as 16 (1H EMA34/EMA8 of last completed hour, daily-8 not wrong side, forming hour from 10:15 to 14:15,
hour opened on the trend side of the EMA, 5m touch of the EMA, liquid days, 5m data Jun 10 - Sep 30 2026), but:
  REJECTION HELD: entry at the close of a 5m bar b inside the same hour where
    - b ends at least 15 min after the touch bar ends (b >= touch + 3 bars),
    - the hour's low (long) was not broken in the last 3 bars (pin low has held 15 min),
    - close is back across the EMA (long: > EMA) but less than 1% past it (not already gone 1%).
  PIN SHAPE (second variant): also, forming hour so far (open = hour open, close = 5m close, H/L so far):
    lower wick >= 2 x body and close in the top third of the hour's range (short: mirror).
Stop = hour's extreme so far (the pin's wick). Target +1%. Out at 5h after entry or day's last 5m close.
Stop first if a 5m bar hits both. One position per ticker; each variant simulated separately. Gross of costs.
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"
HOLD_BARS = 3


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
        hstart = hl.index[np.searchsorted(hl.index.values, T.values, side="right") - 1]
        lo_day, hi_day = np.minimum.accumulate(L), np.maximum.accumulate(H)
        free = {"held": 0, "pin": 0}
        for hs in hl.index:
            hm = hs.hour * 60 + hs.minute
            if hm < 10 * 60 + 15 or hm >= 15 * 60: continue
            idx = np.where(hstart == hs)[0]
            if len(idx) == 0: continue
            E, e8, ho = hl.loc[hs, ["e34", "e8", "hopen"]]
            if np.isnan(E): continue
            if e8 > E and ho > E: s = 1
            elif e8 < E and ho < E: s = -1
            else: continue
            touch = next((k for k in idx if (L[k] <= E if s == 1 else H[k] >= E)), None)
            if touch is None: continue
            for var in ("held", "pin"):
                if idx[0] < free[var]: continue
                b = None
                for k in idx:
                    if k < touch + HOLD_BARS: continue
                    seg = slice(idx[0], k + 1)
                    lo, hi = L[seg].min(), H[seg].max()
                    ext = lo if s == 1 else hi
                    recent = L[k - HOLD_BARS + 1:k + 1].min() if s == 1 else H[k - HOLD_BARS + 1:k + 1].max()
                    if (recent - ext) * s <= 0 and recent != ext: continue          # pin extreme broken recently
                    if s == 1 and L[k - HOLD_BARS + 1:k + 1].min() <= lo: continue   # strict: no new/equal low in last 15m
                    if s == -1 and H[k - HOLD_BARS + 1:k + 1].max() >= hi: continue
                    past = (C[k] - E) * s / E * 100
                    if not (0 < past < 1): continue
                    if var == "pin":
                        body = abs(C[k] - ho)
                        if s == 1:
                            wick, pos = min(ho, C[k]) - lo, (C[k] - lo) / (hi - lo) if hi > lo else 0
                        else:
                            wick, pos = hi - max(ho, C[k]), (hi - C[k]) / (hi - lo) if hi > lo else 0
                        if not (wick >= 2 * body and pos >= 2 / 3): continue
                    b = k; break
                if b is None: continue
                entry = C[b]
                stop = L[idx[0]:b + 1].min() if s == 1 else H[idx[0]:b + 1].max()
                risk = (entry - stop) * s
                if risk <= 0: continue
                if (entry - D8) * s < 0: continue                                  # daily-8 wrong side
                dstate = "touch" if ((s == 1 and lo_day[b] <= D8 * 1.005) or (s == -1 and hi_day[b] >= D8 * 0.995)) else "untested"
                tgt, end = entry * (1 + s * 0.01), T[b] + pd.Timedelta("5h")
                px, why, k = None, None, b
                for k in range(b + 1, len(C)):
                    if (L[k] <= stop) if s == 1 else (H[k] >= stop): px, why = stop, "stop"; break
                    if (H[k] >= tgt) if s == 1 else (L[k] <= tgt): px, why = tgt, "target"; break
                    if T[k] >= end: px, why = C[k], "time5h"; break
                if px is None: px, why, k = C[-1], "eod", len(C) - 1
                ret = (px - entry) / entry * 100 * s
                rows.append(dict(variant=var, ticker=t, date=day, hour=hs.strftime("%H:%M"), touch_time=T[touch].strftime("%H:%M"),
                                 entry_time=T[b].strftime("%H:%M"), side="long" if s == 1 else "short", dstate=dstate,
                                 entry=entry, stop_rs=risk, stop_pct=risk / entry * 100,
                                 entry_past_ema_pct=(entry - E) * s / entry * 100, exit=why, ret=ret,
                                 R=ret / (risk / entry * 100), minutes=(T[k] - T[b]).seconds // 60))
                free[var] = k + 1
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv"))
    out = []
    with Pool(6) as pool:
        for n, r in enumerate(pool.imap_unordered(run, tick, chunksize=8), 1):
            out += r
            if n % 500 == 0: print(f"  {n}/{len(tick)}", flush=True)
    R = pd.DataFrame(out); R.to_csv(HERE / "pin_rejection_held_results.csv", index=False)
    print(R.groupby("variant").size().to_dict(), R.date.min(), R.date.max())
