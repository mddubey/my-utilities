"""RQ-QS-03B -- Quality Pullback Audit (2026-09-29, critic-approved, exactly this
scope). NOT a backtest, NOT a gate, NOT an exit rule. Output distributions only, no
thresholds, no pass/fail, no expectancy -- exactly like the earlier anatomy audits
(Stage A's pre-breakout 1H audit, the trajectory replay's decomposition).

Five fields only, on the properly-verified pullback population (RQ-QS-03A,
gap>=2 days AND confirmed pullback below A's entry price):
  1. Pullback depth from breakout (lowest point vs A's entry, in % and R)
  2. Pullback duration (already have this -- b_days_after_a)
  3. Lowest point relative to the breakout level specifically (same underlying
     number as #1, reported in R terms -- did it stay above the stop, or actually
     breach toward/through it)
  4. EMA20-equivalent distance at the pullback's low (reusing the project's existing
     `ema21` production column -- no ema20 column exists, ema21 is the established
     near-equivalent already used elsewhere in this project, not a new indicator)
  5. B's OWN breakout-day volume vs its own 10-day average (`vol_avg10_prior`,
     existing production column, T-1-safe) -- never checked before; everything
     checked so far was A's volume or the pullback's own volume, never B's.
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
print(f"n={len(pb)}")

cache = {}
rows_out = []
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
        continue
    ia = int(tr.a_entry_i)
    ib = int(ia + tr.b_days_after_a)
    between = rows.iloc[ia + 1:ib]
    if len(between) == 0:
        continue

    low_idx_pos = between.Low.values.argmin()
    low_row = between.iloc[low_idx_pos]
    lowest_low = low_row.Low

    depth_pct = (lowest_low / tr.a_entry_price - 1) * 100  # negative = below A's entry
    depth_r = depth_pct / tr.a_initial_risk_pct  # in R terms, using A's own risk unit

    ema21_at_low = low_row.get("ema21")
    ema21_dist_pct = ((lowest_low / ema21_at_low - 1) * 100) if pd.notna(ema21_at_low) and ema21_at_low else None

    b_row = rows.iloc[int(tr.b_entry_i)]
    b_vol_avg10_prior = b_row.get("vol_avg10_prior")
    b_vol_ratio = (b_row.Volume / b_vol_avg10_prior) if pd.notna(b_vol_avg10_prior) and b_vol_avg10_prior else None

    rows_out.append(dict(
        ticker=t, entry_definition=tr.entry_definition,
        a_entry_date=tr.a_entry_date, b_entry_date=tr.b_entry_date,
        pullback_depth_pct=depth_pct, pullback_depth_r=depth_r,
        pullback_duration_days=tr.b_days_after_a,
        ema21_dist_pct_at_low=ema21_dist_pct,
        b_volume_ratio_vs_10d_avg=b_vol_ratio,
    ))

audit = pd.DataFrame(rows_out)
audit.to_csv(f"{OUT_DIR}/rq03b_quality_pullback_audit.csv", index=False)

print(f"\n=== RQ-QS-03B: Quality Pullback Audit -- distributions only, n={len(audit)} ===\n")

print("1. Pullback depth from breakout (% below A's entry price):")
print(audit.pullback_depth_pct.describe(percentiles=[.1, .25, .5, .75, .9]).round(2))

print("\n1b. Pullback depth in R terms (using A's own risk unit):")
print(audit.pullback_depth_r.describe(percentiles=[.1, .25, .5, .75, .9]).round(3))
print(f"   % of pullbacks that went to or beyond -1R (i.e. would have hit A's own stop level): "
      f"{(audit.pullback_depth_r <= -1.0).mean()*100:.1f}%")

print("\n2. Pullback duration (days):")
print(audit.pullback_duration_days.describe(percentiles=[.1, .25, .5, .75, .9]).round(1))

print("\n3. Lowest point relative to breakout level -- same as #1, R-based already above.")

print("\n4. EMA21 distance at the pullback's low (%):")
valid_ema = audit.ema21_dist_pct_at_low.dropna()
print(valid_ema.describe(percentiles=[.1, .25, .5, .75, .9]).round(2))
print(f"   % of pullback lows within +/-2% of EMA21 (landed near it): {(valid_ema.abs() <= 2).mean()*100:.1f}%")
print(f"   % of pullback lows BELOW EMA21 (undershot it): {(valid_ema < 0).mean()*100:.1f}%")

print("\n5. B's own breakout-day volume vs its 10-day average:")
valid_vol = audit.b_volume_ratio_vs_10d_avg.dropna()
print(valid_vol.describe(percentiles=[.1, .25, .5, .75, .9]).round(2))
print(f"   % of B's with volume >= 1.4x their own 10-day average (matches VCP/cup-handle's "
      f"'40%+ above average' breakout convention -- reported, not filtered): "
      f"{(valid_vol >= 1.4).mean()*100:.1f}%")
