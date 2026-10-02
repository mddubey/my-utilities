"""Encode the user's three nuances (2026-10-01), specs fixed before running. Base set: 18's 'held' trades (5m,
Jun-Sep 2026); (A) and (C) also on 15's 1H-close set (2024-26).
(A) TODAY'S NIFTY BIAS: Nifty's last COMPLETED 1H close vs Nifty's classic daily pivots (prior day H/L/C).
    short: 'below S1' / 'S1..PP' / 'above PP'; long mirrored with R1. Known at entry (coarse: 1H Nifty only).
(B) LIMIT AT THE EMA: after 18's trigger bar, a limit at the 1H EMA34 (short: sell limit; long: buy limit), valid until
    the forming hour ends. Fills on the first later 5m bar that reaches it; if that bar also reaches the stop -> stopped.
    Stop = 18's stop (wick), target = fill -/+1%, out at 5h after fill or the day's last 5m close. No fill = no trade.
    Compared on the SAME triggers: market entry (18 as-is), limit fills, and the triggers the limit never filled.
(C) DAILY 8-EMA OVERHEAD (short; long mirrored): day extreme so far vs dEMA8 -> 'tagged' (reached it) / 'near' (within
    0.5% short of it, BPCL today) / 'far'; and dEMA8 beyond the stop by <=0.3% vs more (a daily retest stops you out)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent
M5 = HERE.parent / "intraday_cache"


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


# Nifty pivots + last completed 1H close
ND = pd.read_csv(HERE.parent / "data_cache" / "_NIFTY.csv", parse_dates=["Date"]).set_index("Date").sort_index()
pp = (ND.High + ND.Low + ND.Close) / 3
NP = pd.DataFrame({"PP": pp, "R1": 2 * pp - ND.Low, "S1": 2 * pp - ND.High}).shift(1)
NH = read(HERE / "index_1h" / "_NIFTY_1h.csv"); NH["end"] = NH.index + pd.Timedelta("60min")


def nifty_state(decide_ts, date, s):
    z = NH[(NH.end <= decide_ts) & (NH.index.normalize() == date)]
    if z.empty or date not in NP.index: return "na"
    c, p = z.Close.iloc[-1], NP.loc[date]
    if s == -1: return "below S1" if c < p.S1 else ("S1..PP" if c < p.PP else "above PP")
    return "above R1" if c > p.R1 else ("PP..R1" if c > p.PP else "below PP")


def d8_feats(t, date, s, stop, ext):
    d = load(t); d8 = d.Close.ewm(span=8, adjust=False).mean().shift(1).get(date, np.nan)
    if np.isnan(d8): return "na", "na"
    gap_ext = (d8 - ext) / d8 * 100 * (1 if s == -1 else -1)        # >0: extreme short of d8
    tag = "tagged" if gap_ext <= 0 else ("near" if gap_ext <= 0.5 else "far")
    beyond = (d8 - stop) / stop * 100 * (1 if s == -1 else -1)      # d8 beyond the stop by this %
    room = "d8 inside stop" if beyond <= 0 else ("d8 <=0.3% past stop" if beyond <= 0.3 else "d8 >0.3% past stop")
    return tag, room


def limit_sim(g, s, E, stop, trig_k, hour_end):
    """returns (filled, ret, exit)"""
    H, L, C, T = g.High.values, g.Low.values, g.Close.values, g.index
    for k in range(trig_k + 1, len(C)):
        if T[k] >= hour_end: return False, np.nan, "nofill"
        if (H[k] >= E) if s == -1 else (L[k] <= E):
            if (H[k] >= stop) if s == -1 else (L[k] <= stop): return True, (E - stop) / E * 100 * (-s) * -1 if False else -abs(stop - E) / E * 100, "stop_fillbar"
            tgt, end = E * (1 + s * 0.01), T[k] + pd.Timedelta("5h")
            for j in range(k + 1, len(C)):
                if (H[j] >= stop) if s == -1 else (L[j] <= stop): return True, -abs(stop - E) / E * 100, "stop"
                if (L[j] <= tgt) if s == -1 else (H[j] >= tgt): return True, 1.0, "target"
                if T[j] >= end: return True, (C[j] - E) / E * 100 * s, "time5h"
            return True, (C[-1] - E) / E * 100 * s, "eod"
    return False, np.nan, "nofill"


def run(args):
    t, rows = args
    x = read(M5 / f"{t}.csv")
    out = []
    for r in rows.itertuples():
        s = 1 if r.side == "long" else -1
        g = x[x.index.normalize() == r.date]
        hs = pd.Timestamp(f"{r.date:%Y-%m-%d} {r.hour}"); et = pd.Timestamp(f"{r.date:%Y-%m-%d} {r.entry_time}")
        if et not in g.index: continue
        k = g.index.get_loc(et)
        E = r.entry - s * r.entry * r.entry_past_ema_pct / 100
        stop = r.entry - s * r.stop_rs
        ext = g.High.iloc[:k + 1].max() if s == -1 else g.Low.iloc[:k + 1].min()
        filled, lret, lexit = limit_sim(g, s, E, stop, k, hs + pd.Timedelta("60min"))
        tag, room = d8_feats(t, r.date, s, stop, ext)
        out.append(dict(key=r.key, nifty=nifty_state(et + pd.Timedelta("5min"), r.date, s), d8_tag=tag, d8_room=room,
                        lim_filled=filled, lim_ret=lret, lim_exit=lexit, lim_stop_pct=abs(stop - E) / E * 100 if filled else np.nan))
    return out


def line(x, l, col="ret", per=None):
    if len(x) < 100: print(f"| {l} | {len(x)} | too few | | | |"); return
    y = x.groupby(per(x))[col].mean() if per else None
    print(f"| {l} | {len(x)} | {(x[col]>0).mean()*100:.0f} | {x[col].mean():+.3f} | {x[col].median():+.3f} | "
          + (" / ".join(f"{k}:{v:+.2f}" for k, v in y.items()) if per is not None else "") + " |")


if __name__ == "__main__":
    from multiprocessing import Pool
    P = pd.read_csv(HERE / "pin_rejection_held_results.csv", parse_dates=["date"]); P = P[P.variant == "held"].reset_index(drop=True)
    P["key"] = P.index
    with Pool(6) as p: F = sum(p.map(run, list(P.groupby("ticker"))), [])
    P = P.merge(pd.DataFrame(F), on="key", how="inner"); P.to_csv(HERE / "nuances_5m.csv", index=False)
    mon = lambda x: x.date.dt.month
    hdr = "| group | n | win% | mean% | med% | by month |\n|---|---|---|---|---|---|"
    print(f"5m held trades with features: {len(P)}\n\n(A) TODAY'S NIFTY vs its daily pivots, at entry\n{hdr}"); line(P, "BASELINE", per=mon)
    for side in ("short", "long"):
        for v in sorted(P[P.side == side].nifty.unique()):
            if v != "na": line(P[(P.side == side) & (P.nifty == v)], f"{side}: Nifty {v}", per=mon)
    print(f"\n(B) LIMIT AT THE 1H EMA34 after the trigger (same triggers)\n{hdr}")
    line(P, "market entry at trigger (18 as-is)", per=mon)
    f = P[P.lim_filled]; line(f, f"limit FILLED ({len(f)/len(P)*100:.0f}% of triggers): limit result", col="lim_ret", per=mon)
    line(f, "  same trades, market-entry result", per=mon)
    line(P[~P.lim_filled], "limit NEVER filled: what market entry made on them", per=mon)
    print(f"  limit stop median {f.lim_stop_pct.median():.2f}% vs market-entry stop median {P.stop_pct.median():.2f}% | limit exits {f.lim_exit.value_counts(normalize=True).round(2).to_dict()}")
    print(f"\n(C) DAILY 8-EMA OVERHEAD\n{hdr}")
    for v in ("tagged", "near", "far"): line(P[P.d8_tag == v], f"day extreme vs dEMA8: {v}", per=mon)
    for v in ("d8 inside stop", "d8 <=0.3% past stop", "d8 >0.3% past stop"): line(P[P.d8_room == v], v, per=mon)
