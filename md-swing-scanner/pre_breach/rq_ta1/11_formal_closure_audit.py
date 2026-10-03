"""RQ-TA1 Formal Closure Audit (critic's exact spec) -- one pre-registered batch, no
feature/snapshot/threshold additions during the run.

A. The 4 remaining dashboard-observable candidate-state features (gap_pct,
   first_dir_up, range_so_far_atr, dist_to_trigger_atr) across the 7 pre-declared
   snapshots (09_candidate_state_snapshots.py's own population) = 28 combinations.
   Family-wise test: shuffle the (ticker,date)->r5 outcome mapping ONCE per permutation
   (not per row -- a candidate appears in multiple snapshot rows before it touches, so
   shuffling at the candidate-day level preserves that structure, exactly the critic's
   "preserve the snapshot structure" instruction), recompute all 28 Spearman rhos under
   that shuffle, take the max |rho| across the family. Repeat 5,000 times for the null.
   Compare the REAL max |rho| across the 28 real combinations against that null.

B. G.1 (S1-break timing vs the touch, 03_s1_timing.py's output) -- formal permutation
   test on the one-way group separation (before/after/never; same_bar dropped, n=2),
   using eta-squared (variance explained) as the test statistic, permuted 5,000 times.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

RNG = np.random.default_rng(42)
N_PERM = 5000
FEATURES = ["gap_pct", "first_dir_up", "range_so_far_atr", "dist_to_trigger_atr"]
SNAPSHOTS = ["09:20", "09:30", "09:45", "10:00", "10:30", "11:00", "12:00"]


def part_a():
    print("=" * 70)
    print("A. Family-wise test: 4 features x 7 snapshots = 28 combinations")
    print("=" * 70)
    R = pd.read_csv(Path(__file__).resolve().parent / "candidate_state_snapshots.csv")
    R["key"] = R.ticker + "|" + R.date.astype(str)
    uniq = R.drop_duplicates("key")[["key", "r5"]].dropna()
    keys = uniq.key.values
    real_r5 = dict(zip(uniq.key, uniq.r5))

    def all_rhos(r5_map):
        out = {}
        r5_col = R.key.map(r5_map)
        for feat in FEATURES:
            for snap in SNAPSHOTS:
                sub_mask = (R.snapshot == snap)
                f = R.loc[sub_mask, feat].replace([np.inf, -np.inf], np.nan)
                o = r5_col[sub_mask]
                valid = f.notna() & o.notna()
                if valid.sum() < 30:
                    out[(feat, snap)] = (np.nan, int(valid.sum()))
                    continue
                rho, _ = spearmanr(f[valid].astype(float), o[valid].astype(float))
                out[(feat, snap)] = (rho, int(valid.sum()))
        return out

    real = all_rhos(real_r5)
    print("\nReal observed rho per feature x snapshot:")
    for feat in FEATURES:
        print(f"  {feat}:")
        for snap in SNAPSHOTS:
            rho, n = real[(feat, snap)]
            print(f"    {snap}: n={n}, rho={rho if np.isnan(rho) else round(rho, 4)}")

    real_abs = [abs(v[0]) for v in real.values() if not np.isnan(v[0])]
    real_max = max(real_abs)
    real_max_combo = [k for k, v in real.items() if not np.isnan(v[0]) and abs(v[0]) == real_max][0]
    print(f"\nREAL max |rho| across all {len(real_abs)} valid combinations: {real_max:.4f} (at {real_max_combo})")

    print(f"\nBuilding null distribution ({N_PERM} permutations, shuffling at the candidate-day level)...")
    null_max = np.empty(N_PERM)
    for i in range(N_PERM):
        shuffled_vals = RNG.permutation(uniq.r5.values)
        shuffled_map = dict(zip(keys, shuffled_vals))
        rhos = all_rhos(shuffled_map)
        abs_rhos = [abs(v[0]) for v in rhos.values() if not np.isnan(v[0])]
        null_max[i] = max(abs_rhos)
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{N_PERM}", flush=True)

    pct = (null_max < real_max).mean() * 100
    print(f"\nFAMILY-WISE RESULT: real max |rho| = {real_max:.4f}, "
          f"null distribution percentile = {pct:.1f}")
    print("VERDICT:", "SOMETHING SURVIVES (real max exceeds 95% of the random-family maxima)"
          if pct >= 95 else "NULL -- entire remaining candidate-state family indistinguishable from chance")


def part_b():
    print("\n" + "=" * 70)
    print("B. G.1 formal permutation test (eta-squared, before/after/never)")
    print("=" * 70)
    R = pd.read_csv(Path(__file__).resolve().parent / "s1_timing.csv")
    R = R[R.s1_order.isin(["before", "after", "never"])].dropna(subset=["r5"])
    print(f"n={len(R)}  groups: {R.s1_order.value_counts().to_dict()}")

    def eta_sq(labels, values):
        grand_mean = values.mean()
        ss_total = ((values - grand_mean) ** 2).sum()
        ss_between = sum(len(values[labels == g]) * (values[labels == g].mean() - grand_mean) ** 2
                          for g in np.unique(labels))
        return ss_between / ss_total if ss_total > 0 else 0.0

    labels = R.s1_order.values
    values = R.r5.values
    real_eta = eta_sq(labels, values)
    print(f"Real eta-squared (variance explained by before/after/never): {real_eta:.4f}")

    null_eta = np.empty(N_PERM)
    for i in range(N_PERM):
        null_eta[i] = eta_sq(RNG.permutation(labels), values)
    pct = (null_eta < real_eta).mean() * 100
    print(f"Null-distribution percentile: {pct:.1f}")
    print("VERDICT:", "SURVIVES (real separation exceeds 95% of random relabelings)"
          if pct >= 95 else "NULL -- not distinguishable from random grouping at this sample size")


if __name__ == "__main__":
    part_a()
    part_b()
