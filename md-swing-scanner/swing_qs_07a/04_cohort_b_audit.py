"""RQ-QS-07A-2B -- Cohort B Tradeability Symmetry Audit (2026-09-29, critic-specified).

Small, deliberate scope, per critic: "No feature search yet... No thresholds
changed. No filtering of the cohort. No predictor search." Same fields as
Cohort A's audit (07A-2), for symmetry -- does B also retain its extreme
behavior inside the zero-circuit, F&O-eligible subset, or does A and B differ
in a way the 73.4% overlap obscures?
"""
import os
import numpy as np
import pandas as pd

os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
OUT_DIR = "swing_qs_07a"

b = pd.read_csv(f"{OUT_DIR}/cohort_b_events.csv", parse_dates=["date"])
print(f"Cohort B: n={len(b):,}\n")

print("By circuit involvement:")
print((b.circuit_days_in_window.value_counts(normalize=True).sort_index() * 100).round(1))
print("\nBy F&O eligibility:")
print((b.fo_eligible.value_counts(normalize=True) * 100).round(1))
print("\nBy NIFTY 500 membership:")
print((b.nifty500_member.value_counts(normalize=True) * 100).round(1))

# liq_decile is already a column on cohort_b_events.csv (computed once in 03_ and
# saved) -- reuse it directly, don't recompute
print("\nLiquidity decile distribution:")
print((b.liq_decile.value_counts(normalize=True).sort_index() * 100).round(1))

clean_b = b[(b.circuit_days_in_window == 0) & b.fo_eligible]
print(f"\nClean subset (0 circuit days AND F&O-eligible): {len(clean_b):,} ({len(clean_b)/len(b)*100:.1f}% of Cohort B)")
OUTCOME_COLS = ["max_return_d1", "max_return_d2", "max_return_d3", "adverse_d1", "adverse_d2", "adverse_d3",
                "close_ret_d1", "close_ret_d2", "close_ret_d3"]
print("\nFull Cohort B outcomes (median):")
print(b[OUTCOME_COLS].median().round(2).to_string())
print("\nClean subset outcomes (median):")
print(clean_b[OUTCOME_COLS].median().round(2).to_string())

b["year"] = b.date.dt.year
clean_b_ = clean_b.assign(year=clean_b.date.dt.year)
print("\nYear-by-year clean-subset coverage:")
print(pd.concat([
    clean_b_.groupby("year").size().rename("clean_n"),
    b.groupby("year").size().rename("cohort_b_n"),
], axis=1).assign(pct=lambda x: (x.clean_n / x.cohort_b_n * 100).round(1)))

# Rule #22: one deterministic hand-check pick from the clean subset
pick = clean_b.sort_values(["ticker", "date"]).iloc[len(clean_b) // 2]
print(f"\nDeterministic clean-subset pick for hand-verification: {pick.ticker} {pick.date.date()}  "
      f"close={pick.close:.2f}  max_return_d3={pick.max_return_d3:.2f}%  close_ret_d3={pick.close_ret_d3:.2f}%  "
      f"day_of_max={pick.day_of_max}")
