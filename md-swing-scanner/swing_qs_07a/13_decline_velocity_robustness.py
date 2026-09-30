"""RQ-QS-07A-6R -- Decline-Velocity Robustness (2026-09-30, critic-specified).

07A-6 found exactly ONE mechanism family clears the pre-registered CANDIDATE
threshold within D0: recent decline velocity (`ret_3d`, `decline_from_high10d_pct`,
correlated 0.62, collapsed into one mechanism concept but NOT one feature --
critic's explicit instruction: "the robustness run should... preserve BOTH
existing variables and show their individual behavior," because they aren't
identical -- `decline_from_high10d_pct` captures DEPTH of recent decline,
`ret_3d` captures RECENT ACCELERATION, and 07A-6R's job is to find out which
one (or both) actually survives, not to retest a merged composite.

Per critic's explicit scope for this pass:
  - Carry forward ONLY decline velocity (`ret_3d`, `decline_from_high10d_pct`).
  - Volume participation is explicitly EXCLUDED from this robustness test --
    it sits below the pre-registered CANDIDATE threshold in 07A-6 (both
    cohorts), and testing it now "would turn a weak supporting observation
    into a second research branch without sufficient evidence." It remains
    an observed secondary annotation in 07A-6's own writeup, not retested here.
  - Family 3 (volatility-transition) already closed as null in 07A-6, not
    retested.
  - Same four ONE-DIMENSIONAL stratifications as 07A-5R (critic: "you don't
    need a gigantic nested matrix"): year, liquidity tercile, F&O, circuit
    involvement -- no crossing/nesting between them.
  - Same effect-size definition and pre-declared bands as 07A-6 (median gap /
    ordinary-D0-population IQR within that stratum; |z|>=0.30 CANDIDATE,
    0.10-0.30 weak, <0.10 null) -- no re-estimation, no new thresholds.
  - Cohort A and B reported separately throughout (standing convention).

SAMPLE-SIZE DISCLOSURE RULE (critic's explicit new requirement for this pass):
if a stratum's Cohort A (or B) count is too small for a stable effect
estimate, report it as "low-n / indeterminate", NOT as "null" -- a thin
cell reading null is a different, weaker statement than a well-populated
cell reading null, and conflating them would misrepresent the evidence.
Threshold: n<30 (same floor this whole project already uses for "too thin,
skipped" cells in 07_/07A-5R -- not a new number invented for this script).
No threshold-lowering, no pooling adjacent years/strata to rescue a thin
cell.

FROZEN: D0 definition (decile==0 of 10_'s composite), Cohort A/B definitions,
D0-ordinary reference population -- nothing redefined, nothing re-thresholded.

No new features. No composite. No threshold search. No strategy test.

DECISION RULE AFTERWARD (critic's exact framing):
  - If BOTH ret_3d and decline_from_high10d_pct are robust across strata:
    "recent deterioration/deceleration into a weak state" is a robust
    precursor characteristic -- mechanism branch continues to post-decline
    transition anatomy (T -> D1 -> D2 -> D3), NOT another feature search.
  - If only ONE survives: rename the mechanism accordingly (depth of decline
    vs. short-term acceleration) rather than keeping "velocity" as a label
    out of attachment to the original hypothesis.
  - If BOTH collapse: 07A-6 was a real pooled observation but not a robust
    mechanism -- D0's existence remains valid (07A-5R already established
    that independently), only its internal mechanism stays unresolved.
"""
import pandas as pd
import numpy as np

OUT_DIR = "."
FEATURES = ["ret_3d", "decline_from_high10d_pct"]
MIN_N = 30

print("Loading D0 population (state metadata from 10_, decline-velocity features from 12_)...", flush=True)
state = pd.read_csv("trend_state_anatomy.csv", parse_dates=["date"])
d0_state = state[state.decile == 0][["ticker", "date", "cohort_a", "cohort_b", "year",
                                        "fo_eligible", "circuit_days_in_window", "traded_value_sma20"]]
mech = pd.read_csv("weak_state_mechanism_features.csv", parse_dates=["date"])[["ticker", "date"] + FEATURES]

d0 = d0_state.merge(mech, on=["ticker", "date"], how="inner")
assert len(d0) == len(d0_state), f"merge changed row count: {len(d0_state)} -> {len(d0)}"
print(f"D0 population: {len(d0):,}  Cohort A: {d0.cohort_a.sum():,}  Cohort B: {d0.cohort_b.sum():,}")

d0["liq_decile"] = d0.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop") if x.notna().sum() >= 10 else np.nan)
d0["liq_tercile"] = pd.cut(d0.liq_decile, [-1, 2, 6, 9], labels=["low", "mid", "high"])
d0["circuit_involved"] = d0.circuit_days_in_window > 0


def effect(fast_series, ordinary_series):
    fa, oa = fast_series.dropna(), ordinary_series.dropna()
    if len(fa) < MIN_N:
        return fa.median() if len(fa) else np.nan, oa.median() if len(oa) else np.nan, np.nan, np.nan, "low-n/indeterminate"
    fm, om = fa.median(), oa.median()
    iqr = np.percentile(oa, 75) - np.percentile(oa, 25) if len(oa) >= MIN_N else np.nan
    z = (fm - om) / iqr if iqr else np.nan
    if pd.isna(z):
        status = "low-n/indeterminate"
    elif abs(z) >= 0.30:
        status = "CANDIDATE"
    elif abs(z) >= 0.10:
        status = "weak"
    else:
        status = "null"
    return fm, om, fm - om, z, status


def run_stratified(dimension, values):
    rows = []
    for v in values:
        sub = d0[d0[dimension] == v]
        for cohort_col, cohort_label in [("cohort_a", "CohortA"), ("cohort_b", "CohortB")]:
            fast = sub[sub[cohort_col]]
            ordinary = sub[~sub[cohort_col]]
            for f in FEATURES:
                fm, om, gap, z, status = effect(fast[f], ordinary[f])
                rows.append(dict(dimension=dimension, value=str(v), cohort=cohort_label, feature=f,
                                    n_fast=len(fast[f].dropna()), n_ordinary=len(ordinary[f].dropna()),
                                    fast_median=round(fm, 3) if pd.notna(fm) else np.nan,
                                    ordinary_median=round(om, 3) if pd.notna(om) else np.nan,
                                    gap=round(gap, 3) if pd.notna(gap) else np.nan,
                                    z_iqr=round(z, 3) if pd.notna(z) else np.nan, status=status))
    return rows


all_rows = []
all_rows += run_stratified("year", [2022, 2023, 2024, 2025, 2026])
all_rows += run_stratified("liq_tercile", ["low", "mid", "high"])
all_rows += run_stratified("fo_eligible", [True, False])
all_rows += run_stratified("circuit_involved", [False, True])

result = pd.DataFrame(all_rows)
result.to_csv(f"{OUT_DIR}/decline_velocity_robustness.csv", index=False)

print(f"\n{'='*130}\nRQ-QS-07A-6R -- decline-velocity robustness matrix "
      f"(effect size = median gap / ordinary-D0 IQR within stratum; n<{MIN_N} -> low-n/indeterminate)\n{'='*130}")
for dimension in ["year", "liq_tercile", "fo_eligible", "circuit_involved"]:
    print(f"\n-- {dimension} --")
    print(result[result.dimension == dimension].drop(columns="dimension").to_string(index=False))

print(f"\n{'='*130}\nSUMMARY -- how many strata does each feature clear CANDIDATE in? (out of {len(set(zip(result.dimension, result.value)))} strata x 2 cohorts)\n{'='*130}")
for f in FEATURES:
    sub = result[result.feature == f]
    counts = sub.status.value_counts()
    print(f"  {f}: {counts.to_dict()}")

print("\nDONE")
