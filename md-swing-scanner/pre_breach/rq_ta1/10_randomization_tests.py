"""RQ-TA1 -- formal randomization tests, same discipline that actually closed RVOL@Trigger
(main FINDINGS.md: looked real twice via bugs, failed a 5,000-iteration label-shuffle test
once honestly computed) and promoted h8_cushion_atr (same test, passed at 99.7th
percentile). Both candidates from this thread need the same bar before being trusted.

Test statistic: Spearman rank-correlation between the feature and r5 (continuous,
matches this project's own convention -- e.g. body_atr's rank-corr 0.223). Null
distribution: shuffle r5 (keeping the feature fixed) 5,000 times, recompute the
correlation each time, report the percentile of the REAL observed correlation within
that null.

1. cum_vol_ratio -- per snapshot, on the existing 1,475-row/5-min-window population
   (09_candidate_state_snapshots.py's own output). Can't do better than this population;
   constrained by 5-min data availability.
2. dist_open_atr -- on the FULL 26,265-trade, 6-year population (panel.csv has this
   field for every touched & non-gap-through row, no 5-min data needed), with a
   year-by-year breakdown (the real Rule #19 check this feature never got before).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
PB = ROOT / "pre_breach"
sys.path.insert(0, str(ROOT))

RNG = np.random.default_rng(42)
N_PERM = 5000


def perm_test(feature, outcome):
    valid = feature.notna() & outcome.notna()
    f, o = feature[valid].values, outcome[valid].values
    n = len(f)
    if n < 30:
        return dict(n=n, rho=np.nan, percentile=np.nan)
    rho_obs, _ = spearmanr(f, o)
    null = np.empty(N_PERM)
    for i in range(N_PERM):
        null[i], _ = spearmanr(f, RNG.permutation(o))
    pct = (null < rho_obs).mean() * 100
    return dict(n=n, rho=round(rho_obs, 4), percentile=round(pct, 1))


def test_cum_vol_ratio():
    print("=" * 70)
    print("1. cum_vol_ratio -- per snapshot, 5,000-shuffle randomization test")
    print("=" * 70)
    R = pd.read_csv(Path(__file__).resolve().parent / "candidate_state_snapshots.csv")
    for snap in ["09:20", "09:30", "09:45", "10:00", "10:30", "11:00", "12:00"]:
        sub = R[R.snapshot == snap]
        result = perm_test(sub.cum_vol_ratio, sub.r5)
        flag = "REAL (>=95th or <=5th)" if (result["percentile"] is not np.nan and
               (result["percentile"] >= 95 or result["percentile"] <= 5)) else "not distinguishable from noise"
        print(f"  {snap}: n={result['n']}, rho={result['rho']}, null-percentile={result['percentile']} -- {flag}")


def test_dist_open_atr():
    print("\n" + "=" * 70)
    print("2. dist_open_atr -- FULL 26,265-trade population, year-by-year + pooled")
    print("=" * 70)
    panel = pd.read_csv(PB / "panel.csv", parse_dates=["date"])
    panel = panel[(panel.touched) & (~panel.gap_through)]
    outcomes = pd.read_pickle(PB / "rq_pb2" / "pivot_feats.pkl")[
        ["ticker", "date", "cls", "r5"]
    ].drop_duplicates(["ticker", "date"])
    X = panel.merge(outcomes, on=["ticker", "date"], how="inner")
    X["year"] = X.date.dt.year

    print(f"\nPooled (n={len(X)}):")
    result = perm_test(X.dist_open_atr, X.r5)
    flag = "REAL" if (result["percentile"] >= 95 or result["percentile"] <= 5) else "not distinguishable from noise"
    print(f"  rho={result['rho']}, null-percentile={result['percentile']} -- {flag}")

    print("\nBy year (does it survive year-by-year, Rule #19/#16):")
    for yr, g in X.groupby("year"):
        result = perm_test(g.dist_open_atr, g.r5)
        if np.isnan(result["rho"]):
            print(f"  {yr}: n={result['n']}, too few")
            continue
        flag = "REAL" if (result["percentile"] >= 95 or result["percentile"] <= 5) else "noise"
        print(f"  {yr}: n={result['n']}, rho={result['rho']}, percentile={result['percentile']} -- {flag}")

    # tercile table for interpretability alongside the formal test
    print("\nTercile table, pooled, for interpretability:")
    b = pd.qcut(X.dist_open_atr.rank(method="first"), 3, labels=["T1 (close to trigger at open)", "T2", "T3 (far from trigger at open)"])

    def st(g):
        return pd.Series({"n": len(g), "BLAST%": (g.cls == "BLAST").mean() * 100,
                           "FAIL%": (g.cls == "FAIL").mean() * 100, "r5_mean": g.r5.mean()})
    print(X.groupby(b, observed=True).apply(st, include_groups=False).round(3))


if __name__ == "__main__":
    test_cum_vol_ratio()
    test_dist_open_atr()
