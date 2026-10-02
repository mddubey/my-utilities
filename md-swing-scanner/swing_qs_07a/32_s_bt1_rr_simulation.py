"""RQ-QS-07A-BT1-S-RR -- Real path-based stop/target simulation for S (and
S+BT1), 3-day window (2026-10-02, user-directed). Fixes the close-based
proxy problem from BT1-S: this walks the ACTUAL day-by-day High/Low over
T+1..T+3, not just the day-3 close, to see whether price touches a target
BEFORE a stop -- the real question the user wants answered.

DESIGN, per user's explicit direction this session:
  - HORIZON: strictly 3 trading days (T+1, T+2, T+3) -- matches the entire
    07A line's existing outcome definition (max_return_d3/close_ret_d3,
    Cohort A/B, S/W). Do NOT silently extend -- that would be a new,
    non-comparable risk/outcome unit (Rule #20's spirit). A longer-horizon
    sweep is a SEPARATE, later, explicitly-labeled variant, not this script.
  - ENTRY PRICE: T0's own Close, used as a validated proxy for "around
    3pm" (checked against real intraday data first: median gap between
    the ~3pm price and the close is only -0.03%, average absolute diff
    0.455%, n=1,795 real intraday days -- small relative to the stop/target
    sizes used here). This lets the full multi-year S population be used,
    instead of being restricted to the ~4-month real-intraday-cache window.
    Rationale: entering before the close (not at T+1's open) captures the
    real, sizeable overnight gap already measured for S days (median
    +0.434%, 27% gap >1%, n=2,000) -- this was the user's explicit reason
    for rejecting a T+1-open entry.
  - STOP: 1.0x the stock's own ATR14 (in price terms) AT ENTRY (T0's own
    atr14 column, already a validated production indicator -- reused
    directly, not re-derived). Scales per stock instead of one flat %.
  - TARGET: SWEPT across {2x, 3x, 4x} ATR14 -- a pre-declared sweep (Rule
    #19), not a single guess, to see the real win-rate/payoff trade-off as
    the target widens.
  - PATH WALK: for day_offset in [1,2,3], check today's Low against the
    stop and today's High against the target. If BOTH trigger the same
    day, the stop is assumed to win (standard conservative backtest
    convention -- can't know the real intraday sequence from daily bars).
    First trigger found (in day order) ends the trade. If neither triggers
    across all 3 days, exit at T+3's close.
  - R DEFINITION: stop hit -> R = -1.0 (exits exactly at the stop level,
    by construction). Target hit -> R = +target_mult (exits exactly at the
    target level, by construction). Neither -> R = (close_d3 - entry) /
    (1.0 x ATR14), i.e. still measured in units of the SAME risk (1x ATR)
    regardless of outcome bucket.

POPULATION: plain S (166,646 rows) reported first as the baseline, then
split by BT1 (burst_count>=1, cusum_stat>0) to see whether the volume-
building signal actually changes the real win rate once measured this way
-- not just under the close-based proxy that already showed a mixed
result.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"
STOP_MULT = 1.0
TARGET_MULTS = [2.0, 3.0, 4.0]

print("Loading S+BT1 population...", flush=True)
s = pd.read_csv(f"{OUT_DIR}/s_bt1_combo.csv", parse_dates=["date"])
print(f"n={len(s):,}")

print("\nSimulating the real day-by-day path (T+1..T+3) for each row, stop=1.0x ATR14...", flush=True)
grouped = dict(tuple(s.groupby("ticker")))
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
                stop_hit = lo <= stop_level
                target_hit = hi >= target_level
                if stop_hit:
                    outcome, day_hit = "stop", d
                    break
                if target_hit:
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
            result[f"day_{tm:g}x"] = day_hit
            result[f"r_{tm:g}x"] = r_mult
        rows_out.append(dict(ticker=t, date=r.date, burst_count=r.burst_count, cusum_stat=r.cusum_stat,
                               vol_accel=r.vol_accel, **result))

sim = pd.DataFrame(rows_out)
sim.to_csv(f"{OUT_DIR}/s_bt1_rr_simulation.csv", index=False)
print(f"\n{len(sim):,} rows simulated, saved s_bt1_rr_simulation.csv")


def report(df, label):
    print(f"\n--- {label} (n={len(df):,}) ---")
    for tm in TARGET_MULTS:
        oc = df[f"outcome_{tm:g}x"]
        rm = df[f"r_{tm:g}x"]
        target_rate = (oc == "target").mean() * 100
        stop_rate = (oc == "stop").mean() * 100
        neither_rate = (oc == "neither").mean() * 100
        win_rate = (rm > 0).mean() * 100
        meaningful_win = (rm >= 0.25).mean() * 100
        mean_r = rm.mean()
        median_r = rm.median()
        print(f"  Target={tm:g}x ATR: hit target {target_rate:5.1f}%  hit stop {stop_rate:5.1f}%  neither {neither_rate:5.1f}%  "
              f"| win%(R>0)={win_rate:5.1f}%  meaningful-win%(R>=.25)={meaningful_win:5.1f}%  mean R={mean_r:+.3f}  median R={median_r:+.3f}")


print(f"\n{'='*120}\nBASELINE -- all S, regardless of BT1\n{'='*120}")
report(sim, "All S")

print(f"\n{'='*120}\nSplit by BT1\n{'='*120}")
report(sim[sim.burst_count == 0], "burst_count = 0")
report(sim[sim.burst_count >= 1], "burst_count >= 1")
report(sim[sim.cusum_stat == 0], "cusum_stat = 0")
report(sim[sim.cusum_stat > 0], "cusum_stat > 0")

print("\nDONE")
