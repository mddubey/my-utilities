"""Most-unfiltered base criteria, both sides (user, 2026-10-06): before ADX/VWAP/2:1/ATR/full-hour-trigger/
chart-review ever existed, the FIRST mechanical spec was script 15 (2026-10-01, "proper intraday version"):
  1H 34-EMA touch (high >= EMA34 as of the last completed hour for a short setup candle) + 1H close confirmation
  back on the correct side, 1H trend (8-EMA vs 34-EMA agreeing with direction), close on the correct side of the
  (plain, non-live-blended) daily 8-EMA. No ADX, no VWAP, no 2:1 cap, no ATR/range filter, no full-hour-trigger,
  no green/red-hour skip. Liquidity floor only (tv20 >= Rs10cr). Entry = 1H close, stop = setup candle's wick,
  target = 1%, exit at the 5th candle after signal or EOD. EVERY hour is a candidate (09:15 included), not just
  10:15/11:15.
Script 15 itself was run on the POSITION-BLOCKING-BIASED engine (confirmed in 60_filter_ablation.py's own notes:
"every 3-year 1H figure derived from 15 ... overstated ~0.03-0.04%; directions need re-checking on clean data") --
that re-check was never done for this original spec either. This rebuilds it bias-free, both sides, identical
code path (is_long flag), on the 3-year 1H set (2024-01 .. now) -- the same window script 15 used."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from backtest import load
from market_regime import _compute_adx
A8 = 2 / 9
END = pd.Timestamp("2026-10-07")


def read(p):
    x = pd.read_csv(p, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[((x.Volume > 0) | (x.High != x.Low)) & (x.index < END)]


def daily_inputs(t):
    d = load(t); d = d[d.index < END]
    return d, d.Close.ewm(span=8, adjust=False).mean().shift(1), d.traded_value_sma20.shift(1)   # NOTE: no ADX here -- not part of the original spec


def walk(H, L, C, b, stop_px, tgt, is_long, j_end):
    for k in range(b + 1, min(j_end + 1, len(C))):
        if (is_long and L[k] <= stop_px) or (not is_long and H[k] >= stop_px): return stop_px, "stop"
        hit_tgt = (H[k] >= tgt) if is_long else (L[k] <= tgt)
        if hit_tgt: return tgt, "target"
        if k == j_end: return C[k], "time"
    return C[min(j_end, len(C) - 1)], "eod"


def gen(t, is_long):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try: d, d8y, tv = daily_inputs(t)
    except Exception: return []
    h = read(p)
    if len(h) < 300: return []
    O, H, L, C, V, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.Volume.values, h.index
    E34 = h.Close.ewm(span=34, adjust=False).mean().shift(1).values; E8 = h.Close.ewm(span=8, adjust=False).mean().shift(1).values
    day = T.normalize(); last = np.r_[day[1:] != day[:-1], True]
    rows = []
    for i in range(50, len(C) - 1):
        if T[i] < pd.Timestamp("2024-01-01"): continue
        dd = day[i]
        if tv.get(dd, 0) < 1e8: continue
        D8 = d8y.get(dd, np.nan)
        if np.isnan(D8) or np.isnan(E34[i]) or np.isnan(E8[i]): continue
        E = E34[i]; qh, ql, qc, qo = H[i], L[i], C[i], O[i]
        if is_long:
            core = ql <= E and qc > E
            side = E8[i] > E and qc > D8
            stop_px = ql; tgt = qc * 1.01
        else:
            core = qh >= E and qc < E
            side = E8[i] < E and qc < D8
            stop_px = qh; tgt = qc * 0.99
        if not (core and side): continue
        j_end = i + 1; steps = 0
        while j_end < len(C) and day[j_end] == dd and steps < 4: j_end += 1; steps += 1
        px, why = walk(H, L, C, i, stop_px, tgt, is_long, min(j_end, len(C) - 1))
        ret = (px - qc) / qc * 100 if is_long else (qc - px) / qc * 100
        rows.append(dict(ticker=t, date=dd, hour=T[i].strftime("%H:%M"), ret=ret, why=why, stop_pct=abs(qc - stop_px) / qc * 100))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    for side, is_long in (("SHORT", False), ("LONG", True)):
        with Pool(6) as pool:
            rows = sum(pool.starmap(gen, [(t, is_long) for t in t1], chunksize=10), [])
        x = pd.DataFrame(rows)
        x.to_csv(HERE / f"base_criteria_{side.lower()}.csv", index=False)
        days = x.date.nunique()
        x["year"] = pd.to_datetime(x.date).dt.year
        print(f"\n=== {side} (most-unfiltered base criteria, bias-free, 1H set 2024-now): n={len(x)}, {days} days, {len(x)/days:.2f}/day ===")
        print(f"mean ret%: {x.ret.mean():+.3f}  median ret%: {x.ret.median():+.3f}  win%: {(x.ret>0).mean()*100:.1f}  "
              f"target%: {(x.why=='target').mean()*100:.1f}  stop%: {(x.why=='stop').mean()*100:.1f}  "
              f"eod/time%: {(x.why.isin(['eod','time'])).mean()*100:.1f}  median stop%: {x.stop_pct.median():.2f}")
        print(x.groupby("year").ret.agg(["count", "mean"]).round(3).to_string())
        print("by hour:")
        print(x.groupby("hour").ret.agg(["count", "mean"]).round(3).to_string())
