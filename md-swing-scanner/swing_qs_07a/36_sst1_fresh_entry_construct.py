"""RQ-QS-07A-SST1-E1 -- First entry construct for the Strong-State Transition
discovery (2026-10-02). Freshness (run_age=1) survived the W-overlap audit
(SST1-R1) -- this is the first real trade built on it, per the critic's
decision tree ("freshness survives -> build the first actual entry
construct around the transition").

STOP-LOSS, discussed and declared BEFORE this script was written (Risk Unit
Integrity, Rule #20): 1.5x ATR14 at entry. Literature-grounded (breakout/
momentum stop-placement convention, distinct from W's bottom-reversal
literature -- this is a trend-initiation setup, not a reversal setup).
CHOSEN OVER "T0's own low" after a mandatory risk-geometry check: T0's own
low has a near-zero-risk failure mode in 3.2% of cases (the same category
of bug that corrupted W's first entry construct, E1) and a much wider,
less consistent spread (1.3%-9.6% vs ATR's 4.6%-9.0% at P10-P90). 1.5x ATR
cannot be near-zero by construction and was explicitly preferred for that
reason.

ENTRY: T0's own Close, the same validated ~3pm proxy used throughout the
BT1/SST chain (median gap to real 3pm price -0.03%, n=1,795 real intraday
days) -- lets the full multi-year fresh (run_age=1) population be used,
and captures the overnight gap rather than missing it via a T+1-open entry.

HORIZON: 3 trading days, unchanged -- matches the whole 07A outcome unit.

TARGET: swept at {2x, 3x, 4x} the SAME 1.5x-ATR risk unit (consistent R-
multiple accounting, same convention as 32_s_bt1_rr_simulation.py) --
informed by, not picked blind from, the real reachability check already
run on this exact population (+10% reached 16.9% of the time, +15% reached
8.1% of the time, for run_age=1 specifically -- genuinely more opportunity
than plain S's 13.8%/6.2%).

PATH WALK: identical mechanics to script 32 -- real day-by-day High/Low
over T+1..T+3, stop checked before target if both trigger the same day
(conservative convention), exit at T+3 close if neither triggers.

POPULATION: run_age==1 only (fresh entrants, n=26,536) -- the population
that survived SST1-R1's overlap audit. Compared against plain S (all
run_age, the already-known-too-thin baseline from BT1-S-RR) for direct
contrast.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"
STOP_MULT = 1.5
TARGET_MULTS = [2.0, 3.0, 4.0]  # multiples of the 1.5x-ATR risk unit

print("Loading fresh (run_age=1) population...", flush=True)
feats_b = pd.read_csv(f"{OUT_DIR}/sst1_freshness_features.csv", parse_dates=["date"])
fresh = feats_b[feats_b.run_age == 1][["ticker", "date"]].copy()
print(f"n={len(fresh):,}")

print("\nSimulating the real day-by-day path (T+1..T+3), stop=1.5x ATR14...", flush=True)
grouped = dict(tuple(fresh.groupby("ticker")))
rows_out = []
for n, t in enumerate(grouped):
    if n % 300 == 0:
        print(f"  {n}/{len(grouped)} tickers", flush=True)
    idf = load(t, daily_pivots)
    close, high, low, atr14 = idf.Close, idf.High, idf.Low, idf.atr14
    sub = grouped[t]
    for r in sub.itertuples():
        if r.date not in idf.index:
            continue
        pos = idf.index.get_loc(r.date)
        if pos + 3 >= len(idf) or pd.isna(atr14.iloc[pos]) or atr14.iloc[pos] <= 0:
            continue
        entry = close.iloc[pos]
        risk = STOP_MULT * atr14.iloc[pos]
        stop_level = entry - risk
        result = {}
        for tm in TARGET_MULTS:
            target_level = entry + tm * risk
            outcome, day_hit = None, None
            for d in [1, 2, 3]:
                lo, hi = low.iloc[pos + d], high.iloc[pos + d]
                if lo <= stop_level:
                    outcome, day_hit = "stop", d
                    break
                if hi >= target_level:
                    outcome, day_hit = "target", d
                    break
            if outcome is None:
                outcome, day_hit = "neither", 3
                r_mult = (close.iloc[pos + 3] - entry) / risk
            elif outcome == "stop":
                r_mult = -1.0
            else:
                r_mult = tm
            result[f"outcome_{tm:g}x"] = outcome
            result[f"r_{tm:g}x"] = r_mult
        rows_out.append(dict(ticker=t, date=r.date, **result))

sim = pd.DataFrame(rows_out)
sim.to_csv(f"{OUT_DIR}/sst1_fresh_entry_simulation.csv", index=False)
print(f"\n{len(sim):,} rows simulated, saved sst1_fresh_entry_simulation.csv")

for tm in TARGET_MULTS:
    oc, rm = sim[f"outcome_{tm:g}x"], sim[f"r_{tm:g}x"]
    target_rate, stop_rate, neither_rate = (oc == "target").mean() * 100, (oc == "stop").mean() * 100, (oc == "neither").mean() * 100
    win_rate = (rm > 0).mean() * 100
    print(f"Target={tm:g}x risk: hit target {target_rate:5.1f}%  hit stop {stop_rate:5.1f}%  neither {neither_rate:5.1f}%  "
          f"| win%={win_rate:5.1f}%  mean R={rm.mean():+.3f}  median R={rm.median():+.3f}")

print("\nDONE")
