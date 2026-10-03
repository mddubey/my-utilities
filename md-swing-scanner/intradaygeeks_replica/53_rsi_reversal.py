"""His 'Reversal strategy' scanner (CHARTINK_QUERIES.md s.4) as an intraday trade. Spec fixed 2026-10-02 before running.
SHORT ('Bearish area'): yesterday's daily RSI14 > 80, yesterday's close >= day-before's low (yesterday hadn't already
broken), and TODAY price breaks below yesterday's low. LONG mirror: RSI14 < 20, yesterday's close <= day-before's high,
today breaks above yesterday's high. Trade = first 1H candle starting 10:15 or 11:15 that CLOSES beyond yesterday's
level; entry at its close, stop = that candle's high (short) / low (long), target 1%, out after 5 candles / day's last.
Variant (robustness, sample size): RSI thresholds 70/30. Liquid (prior-day tv20 >= Rs 10cr). 2024-01 .. 2026-09."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from signals import rsi
HERE = Path(__file__).resolve().parent


def run(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try: d = load(t)
    except Exception: return []
    d = d[d.index < pd.Timestamp("2026-10-01")]
    if len(d) < 60: return []
    r = rsi(d.Close, 14)
    f = pd.DataFrame({"rsi_y": r.shift(1), "lo_y": d.Low.shift(1), "hi_y": d.High.shift(1), "cl_y": d.Close.shift(1),
                      "lo_y2": d.Low.shift(2), "hi_y2": d.High.shift(2), "tv": d.traded_value_sma20.shift(1)})
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[((h.Volume > 0) | (h.High != h.Low)) & (h.index >= "2024-01-01") & (h.index < "2026-10-01")]
    rows = []
    for day, g in h.groupby(h.index.normalize()):
        if day not in f.index: continue
        x = f.loc[day]
        if np.isnan(x.rsi_y) or x.tv < 1e8: continue
        H, L, C, T = g.High.values, g.Low.values, g.Close.values, g.index
        for lab, hi_t, lo_t in (("80/20", 80, 20), ("70/30", 70, 30)):
            for s in (-1, 1):
                if s == -1 and not (x.rsi_y > hi_t and x.cl_y >= x.lo_y2): continue
                if s == 1 and not (x.rsi_y < lo_t and x.cl_y <= x.hi_y2): continue
                lvl = x.lo_y if s == -1 else x.hi_y
                k = next((k for k in range(len(C)) if T[k].strftime("%H:%M") in ("10:15", "11:15") and (C[k] - lvl) * s > 0), None)
                if k is None: continue
                entry = C[k]; stop = H[k] if s == -1 else L[k]; risk = (stop - entry) * -s
                if risk <= 0: continue
                tgt = entry * (1 + s * 0.01); px = C[-1]
                for j in range(k + 1, len(C)):
                    if (H[j] >= stop) if s == -1 else (L[j] <= stop): px = stop; break
                    if (L[j] <= tgt) if s == -1 else (H[j] >= tgt): px = tgt; break
                    if j - k >= 5: px = C[j]; break
                rows.append(dict(ticker=t, date=day, hour=T[k].strftime("%H:%M"), rsi=lab, side="short" if s == -1 else "long", stop_pct=risk / entry * 100,
                                 ret=(px - entry) / entry * 100 * s))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=10), []))
    R.to_csv(HERE / "rsi_reversal.csv", index=False)
    nd = 675
    def cell(x): return f"{x.ret.mean():+.3f} (n {len(x)})" if len(x) >= 30 else f"n {len(x)}"
    for rr in (False, True):
        D = R[R.stop_pct <= 0.5] if rr else R
        print(f"\n### RSI reversal {'WITH 2:1 RULE' if rr else '(all stops)'}\n| RSI | side | 2024 | 2025 | 2026 | all | per day | median stop | win% | net @0.06 | net @0.10 |\n|---|---|---|---|---|---|---|---|---|---|---|")
        for lab in ("80/20", "70/30"):
            for sd in ("short", "long"):
                x = D[(D.rsi == lab) & (D.side == sd)]
                if len(x) < 10: print(f"| {lab} | {sd} | n {len(x)} | | | | | | | | |"); continue
                print(f"| {lab} | {sd} | " + " | ".join(cell(x[x.date.dt.year == y]) for y in (2024, 2025, 2026)) +
                      f" | {cell(x)} | {len(x)/nd:.2f} | {x.stop_pct.median():.2f}% | {(x.ret>0).mean()*100:.0f} | {x.ret.mean()-0.06:+.3f} | {x.ret.mean()-0.10:+.3f} |")
