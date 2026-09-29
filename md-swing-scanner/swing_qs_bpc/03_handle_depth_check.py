"""Third and final prioritized hypothesis from critic's list: handle depth <= 50% of
the prior base/cup depth (O'Neil cup-and-handle rule). Descriptive only -- reports
the distribution and the %-meeting-the-convention, does not filter or gate anything.

Prior base depth = the range (High-Low as % of High) over the SAME lookback window
used to compute A's own trigger (the N days whose rolling high A broke out above) --
reuses A's own entry_definition, not a new/arbitrary window.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

from backtest import load
from pivots import daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

pb = pd.read_csv(f"{OUT_DIR}/rq03a_pullback_verified.csv", parse_dates=["a_entry_date", "b_entry_date"])
pb = pb[pb.genuine_pullback].copy()
audit = pd.read_csv(f"{OUT_DIR}/rq03b_quality_pullback_audit.csv", parse_dates=["a_entry_date", "b_entry_date"])
pb = pb.merge(audit[["ticker", "entry_definition", "a_entry_date", "b_entry_date", "pullback_depth_pct"]],
              on=["ticker", "entry_definition", "a_entry_date", "b_entry_date"], how="inner")
print(f"n={len(pb)}")

cache = {}
prior_base_depth = []
for n, tr in enumerate(pb.itertuples()):
    if n % 3000 == 0:
        print(f"{n}/{len(pb)}", flush=True)
    t = tr.ticker
    if t not in cache:
        try:
            cache[t] = load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            cache[t] = None
    rows = cache[t]
    if rows is None:
        prior_base_depth.append(None)
        continue
    ia = int(tr.a_entry_i)
    lookback = int(tr.entry_definition)
    base_window = rows.iloc[max(0, ia - lookback):ia]  # the same N days A's own trigger used
    if len(base_window) == 0:
        prior_base_depth.append(None)
        continue
    base_high = base_window.High.max()
    base_low = base_window.Low.min()
    depth_pct = (base_high - base_low) / base_high * 100 if base_high else None
    prior_base_depth.append(depth_pct)

pb["prior_base_depth_pct"] = prior_base_depth
pb["handle_depth_ratio"] = pb.pullback_depth_pct.abs() / pb.prior_base_depth_pct
pb.to_csv(f"{OUT_DIR}/rq03b_handle_depth.csv", index=False)

valid = pb.dropna(subset=["handle_depth_ratio"])
print(f"\n=== Handle depth ratio (pullback depth / prior base depth), n={len(valid)} ===")
print(valid.handle_depth_ratio.describe(percentiles=[.1, .25, .5, .75, .9]).round(3))
print(f"\n% of events where pullback depth <= 50% of the prior base depth (O'Neil's convention): "
      f"{(valid.handle_depth_ratio <= 0.5).mean()*100:.1f}%")
print(f"median prior_base_depth_pct: {valid.prior_base_depth_pct.median():.2f}%")
print(f"median pullback depth (abs %): {valid.pullback_depth_pct.abs().median():.2f}%")
