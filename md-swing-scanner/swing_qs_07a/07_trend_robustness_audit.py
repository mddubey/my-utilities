"""RQ-QS-07A-3R -- Trend/Momentum Robustness Audit (2026-09-29, critic-specified).

Question: is the trend/momentum precursor found in 05_ real, stable, and useful
across market-quality/regime strata -- or is it an artifact of a specific
liquidity/F&O/circuit/year slice? NOT a search for more features. NOT picking a
"winning" feature. Frozen population (full Cohort A + matched controls, no
F&O/circuit/NIFTY filter) -- these dimensions are recorded as STRATIFICATION
only, exactly as they've been throughout this line.

PRIMARY VARIABLES (critic's exact pre-declared 5, representing the different
aspects of what 05_ found -- NOT re-selected after seeing which "wins"):
  dist_sma200_pct, ret_20d, dist_low252_pct, dist_ema34_pct, rsi14

STRATIFICATION, in critic's priority order:
  A. Liquidity decile (highest priority -- literature: Indian momentum/reversal
     behavior differs sharply by liquidity; matching was already done same-
     date/same-decile, so this comparison is naturally apples-to-apples)
  B. F&O vs non-F&O (does the relationship hold in the population that matters
     for the eventual options product -- not yet a filter, a check)
  C. Circuit-involved vs zero-circuit (confounder/distortion check: does the
     gap survive in clean, non-circuit-locked names)
  D. NIFTY-500 vs non-NIFTY-500 (lowest priority; membership is itself an
     imperfect historical construct in this project's v1 universe -- metadata,
     not a canonical boundary)
  E. Year (2022-2026, part of the SAME audit per critic, not a separate RQ)

For every stratum, report: n (cohort / control), and each primary variable's
median gap (cohort - control) -- direction and magnitude, not a ranking.

FEATURE CORRELATION DIAGNOSTIC (critic's explicit ask): are these 5 variables
one latent "trend strength" dimension expressed multiple ways, or genuinely
independent signals? Computed separately within cohort_a and within control
populations (Spearman, robust to the very different scales of a % distance vs
an RSI value).

No new TA features. No threshold chosen. No model.
"""
import os
import numpy as np
import pandas as pd

os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
OUT_DIR = "swing_qs_07a"
SEED = 42
PRIMARY = ["dist_sma200_pct", "ret_20d", "dist_low252_pct", "dist_ema34_pct", "rsi14"]

print("Reconstructing Cohort A + matched controls with full stratification metadata "
      "(identical to 03_/05_/06_)...", flush=True)
df = pd.read_csv(f"{OUT_DIR}/event_matrix.csv", parse_dates=["date"])
P95_MFE = np.percentile(df.max_return_d3, 95)
df["cohort_a"] = df.max_return_d3 >= P95_MFE
df["cohort_b"] = df.close_ret_d3 >= np.percentile(df.close_ret_d3, 95)
df["liq_decile"] = df.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop"))

rng = np.random.RandomState(SEED)
noncohort = df[~df.cohort_a & ~df.cohort_b]
pool_by_key = noncohort.groupby(["date", "liq_decile"]).apply(lambda g: g.index.tolist(), include_groups=False)

def draw_control(row):
    pool = pool_by_key.get((row["date"], row["liq_decile"]))
    return pool[rng.randint(len(pool))] if pool else None

a = df[df.cohort_a].copy()
control_idx = a.apply(draw_control, axis=1)
a = a[control_idx.notna()].copy()
controls = df.loc[control_idx.dropna().astype(int)].copy()
a["group"], controls["group"] = "cohort_a", "control"
meta_cols = ["ticker", "date", "group", "nifty500_member", "fo_eligible", "circuit_days_in_window", "liq_decile"]
work = pd.concat([a[meta_cols], controls[meta_cols]], ignore_index=True)
work["year"] = work.date.dt.year
work["circuit_involved"] = work.circuit_days_in_window > 0
print(f"Cohort A: {len(a):,}  Controls: {len(controls):,}")

feats = pd.read_csv(f"{OUT_DIR}/precursor_features.csv", parse_dates=["date"])[["ticker", "date", "group"] + PRIMARY]
work = work.merge(feats, on=["ticker", "date", "group"], how="left")
print(f"Merged features: {work[PRIMARY].notna().all(axis=1).sum():,} of {len(work):,} rows fully populated")


def audit(strat_col, label, order=None):
    print(f"\n{'='*100}\nStratified by {label}\n{'='*100}")
    values = order if order is not None else sorted(work[strat_col].dropna().unique())
    for v in values:
        ca = work[(work.group == "cohort_a") & (work[strat_col] == v)]
        ct = work[(work.group == "control") & (work[strat_col] == v)]
        if len(ca) < 30 or len(ct) < 30:
            print(f"  {v}: n_cohort={len(ca)} n_control={len(ct)}  (too thin, <30, skipped)")
            continue
        gaps = "  ".join(f"{f}={ca[f].median()-ct[f].median():+.2f}" for f in PRIMARY)
        print(f"  {v}: n_cohort={len(ca):,} n_control={len(ct):,}  {gaps}")


audit("liq_decile", "A. Liquidity decile (0=least liquid, 9=most liquid)")
audit("fo_eligible", "B. F&O eligibility", order=[True, False])
audit("circuit_involved", "C. Circuit involvement (any circuit day in the D1-D3 window)", order=[False, True])
audit("nifty500_member", "D. NIFTY 500 membership", order=[True, False])
audit("year", "E. Year")

print(f"\n{'='*100}\nFEATURE-FEATURE CORRELATION DIAGNOSTIC (Spearman)\n{'='*100}")
print("\n-- Within Cohort A --")
print(work[work.group == "cohort_a"][PRIMARY].corr(method="spearman").round(2).to_string())
print("\n-- Within Control --")
print(work[work.group == "control"][PRIMARY].corr(method="spearman").round(2).to_string())

work.to_csv(f"{OUT_DIR}/trend_robustness_audit.csv", index=False)
print(f"\nsaved trend_robustness_audit.csv ({len(work):,} rows)")
