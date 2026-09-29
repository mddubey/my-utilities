"""20 QS-A vs 20 QS-B (D3) replay, per critic's exact spec (2026-09-29). D3 = close
above A's original breakout level after a genuine retest. Same A, same risk unit
(S1b), same decision-time-safe constraints -- no EMA21/volume/quality filter added.
Trajectory/behavior only -- NOT an expectancy comparison.

Sample: 20 A events with a genuine D3 second-breakout, drawn via the SAME
deterministic stratified method as the original 100-trade replay MVP (25/25/25/25
scaled to 5/5/5/5 early/mid/late/random), fixed seed, before looking at any
trajectory. A<->B relationship preserved (both IDs + elapsed days recorded). D5
(mechanical control) retained as reference metadata only, not a third replay arm.

B's entry mechanics: D3 is a CLOSE-based signal (close above A's original level) --
per this project's own standing convention (decide at a close, execute at the next
open), B's actual entry is modeled as the OPEN of the trading day immediately after
the D3 signal day, with a fresh S1b stop (prior day's Low as of B's own entry day).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

from backtest import load
from pivots import daily_pivots
from qs_trajectory_replay import replay as replay_trajectory

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SEED = 42

df = pd.read_csv(f"{OUT_DIR}/rq03c_five_b_definitions.csv", parse_dates=["a_entry_date"])
cache_files = set(f[:-4] for f in os.listdir("intraday_cache") if f.endswith(".csv"))
pool = df[df.d3_days.notna() & df.a_entry_date.between("2026-06-10", "2026-09-05")
          & df.ticker.isin(cache_files)].copy()
pool = pool.drop_duplicates(subset=["ticker", "entry_definition", "a_entry_i"]).reset_index(drop=True)
print(f"Eligible pool: {len(pool)}")

d_min, d_max = pool.a_entry_date.min(), pool.a_entry_date.max()
span = (d_max - d_min) / 3
early_cut, mid_cut = d_min + span, d_min + 2 * span
early_pool = pool[pool.a_entry_date < early_cut]
mid_pool = pool[(pool.a_entry_date >= early_cut) & (pool.a_entry_date < mid_cut)]
late_pool = pool[pool.a_entry_date >= mid_cut]

rng = np.random.RandomState(SEED)
def draw(sub_pool, n, exclude_idx):
    avail = sub_pool[~sub_pool.index.isin(exclude_idx)]
    return avail.sample(n=min(n, len(avail)), random_state=rng)

picked = pd.DataFrame()
early_s = draw(early_pool, 5, picked.index).assign(stratum="early"); picked = pd.concat([picked, early_s])
mid_s = draw(mid_pool, 5, picked.index).assign(stratum="mid"); picked = pd.concat([picked, mid_s])
late_s = draw(late_pool, 5, picked.index).assign(stratum="late"); picked = pd.concat([picked, late_s])
random_s = draw(pool, 5, picked.index).assign(stratum="random"); picked = pd.concat([picked, random_s])
sample = picked.reset_index(drop=True)
sample["pair_id"] = sample.index
print(f"Sample: n={len(sample)}")
sample.to_csv(f"{OUT_DIR}/replay20_sample.csv", index=False)

# --- for each pair, find B's actual entry (next trading day's open after the D3 signal) ---
cache = {}
pairs = []
for tr in sample.itertuples():
    t = tr.ticker
    if t not in cache:
        cache[t] = load(t, daily_pivots).reset_index()
    rows = cache[t]
    d3_signal_i = int(tr.a_entry_i + tr.d3_days)  # the day D3's close condition fires
    b_entry_i = d3_signal_i + 1  # execute at the NEXT open, per standing convention
    if b_entry_i >= len(rows):
        continue
    b_row = rows.iloc[b_entry_i]
    b_entry_price = b_row.Open
    b_stop_price = rows.iloc[b_entry_i - 1].Low  # S1b, fresh as of B's own entry day
    if b_entry_price <= b_stop_price:
        continue
    a_stop_price = rows.iloc[int(tr.a_entry_i) - 1].Low
    pairs.append(dict(
        pair_id=tr.pair_id, stratum=tr.stratum,
        ticker=t, a_entry_date=str(tr.a_entry_date.date()), a_entry_price=tr.a_entry_price,
        a_stop_price=a_stop_price,
        b_entry_date=str(b_row.Date.date()), b_entry_price=b_entry_price, b_stop_price=b_stop_price,
        d3_days_after_a=tr.d3_days, d5_days_after_a=tr.d5_days,
    ))

pairs_df = pd.DataFrame(pairs)
pairs_df.to_csv(f"{OUT_DIR}/replay20_pairs.csv", index=False)
print(f"\nPairs with valid B entry: {len(pairs_df)}")
print(pairs_df[["ticker", "a_entry_date", "b_entry_date", "d3_days_after_a"]].to_string(index=False))

# --- replay both A and B for each pair, reusing the validated replay() function ---
print("\n\n" + "=" * 100 + "\nREPLAYING A (original QS-A entry)\n" + "=" * 100)
for tr in pairs_df.itertuples():
    replay_trajectory(tr.ticker, tr.a_entry_date, entry_price=tr.a_entry_price, stop_price=tr.a_stop_price)

print("\n\n" + "=" * 100 + "\nREPLAYING B (D3 -- close above breakout level after retest, entered at next open)\n" + "=" * 100)
for tr in pairs_df.itertuples():
    replay_trajectory(tr.ticker, tr.b_entry_date, entry_price=tr.b_entry_price, stop_price=tr.b_stop_price)
