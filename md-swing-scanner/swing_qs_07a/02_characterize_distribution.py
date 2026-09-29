"""RQ-QS-07A-1, characterization pass (2026-09-29). Reads event_matrix.csv (built by
01_event_matrix.py) and reports the natural distribution -- no threshold chosen, no
"fast mover" defined, purely descriptive, per critic's exact instruction: "then we
decide what a 'fast mover' cohort should mean" only AFTER seeing this.
"""
import os
import numpy as np
import pandas as pd

os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
OUT_DIR = "swing_qs_07a"

df = pd.read_csv(f"{OUT_DIR}/event_matrix.csv", parse_dates=["date"])
print(f"n={len(df):,} eligible stock-days, {df.ticker.nunique():,} tickers, "
      f"{df.date.min().date()} to {df.date.max().date()}\n")


def pstack(s, fmt="{:.2f}"):
    s = pd.Series(s).dropna()
    return "  ".join(f"P{p}={fmt.format(np.percentile(s, p))}" for p in [10, 25, 50, 75, 90, 95, 99]) + f"  (n={len(s):,})"


print("=" * 100 + "\nFORWARD MAX RETURN (MFE, High-based) DISTRIBUTIONS\n" + "=" * 100)
for h in ["d1", "d2", "d3"]:
    print(f"  max_return_{h}: {pstack(df[f'max_return_{h}'])}")

print("\n" + "=" * 100 + "\nFORWARD ADVERSE (MAE, Low-based) DISTRIBUTIONS\n" + "=" * 100)
for h in ["d1", "d2", "d3"]:
    print(f"  adverse_{h}:    {pstack(df[f'adverse_{h}'])}")

print("\n" + "=" * 100 + "\nCLOSE-TO-CLOSE (SUSTAINED) RETURN DISTRIBUTIONS\n" + "=" * 100)
for h in ["d1", "d2", "d3"]:
    print(f"  close_ret_{h}:  {pstack(df[f'close_ret_{h}'])}")

print("\n" + "=" * 100 + "\nJOINT MFE/MAE VIEW -- median MFE conditional on MAE tercile, and vice versa (D3)\n" + "=" * 100)
df["mae_tercile"] = pd.qcut(df.adverse_d3, 3, labels=["worst_third", "mid_third", "best_third"])
print(df.groupby("mae_tercile", observed=True).max_return_d3.median())
df["mfe_tercile"] = pd.qcut(df.max_return_d3, 3, labels=["worst_third", "mid_third", "best_third"])
print(df.groupby("mfe_tercile", observed=True).adverse_d3.median())

print("\n" + "=" * 100 + "\nDAY OF MAX (time-to-peak within the D1-D3 window)\n" + "=" * 100)
print(df.day_of_max.value_counts(normalize=True).sort_index().mul(100).round(1))

print("\n" + "=" * 100 + "\nPATH SHAPE (pre-declared categories)\n" + "=" * 100)
print(df.path_shape.value_counts())
print(df.path_shape.value_counts(normalize=True).mul(100).round(1))
print("\n  D3 outcomes by path_shape (median max_return_d3 / median close_ret_d3 / median adverse_d3):")
print(df.groupby("path_shape")[["max_return_d3", "close_ret_d3", "adverse_d3"]].median())

print("\n" + "=" * 100 + "\nYEAR-BY-YEAR (Rule #16 -- never pool years)\n" + "=" * 100)
df["year"] = df.date.dt.year
yr = df.groupby("year").agg(n=("ticker", "size"),
                              max_return_d3_med=("max_return_d3", "median"),
                              close_ret_d3_med=("close_ret_d3", "median"),
                              adverse_d3_med=("adverse_d3", "median"))
print(yr.round(2))

print("\n" + "=" * 100 + "\nMETADATA SPLIT -- NIFTY 500 / F&O membership (current, v1 caveat -- see CLAUDE.md)\n" + "=" * 100)
for col in ["nifty500_member", "fo_eligible"]:
    print(f"\n  by {col}:")
    print(df.groupby(col)[["max_return_d3", "close_ret_d3", "adverse_d3"]].median())
    print(f"  n: {df[col].value_counts().to_dict()}")

print("\n" + "=" * 100 + "\nTHE 'UNUSUALLY LARGE MOVE' TAIL -- natural percentile anchors, no threshold chosen yet\n" + "=" * 100)
for p in [90, 95, 99, 99.5]:
    v = np.percentile(df.max_return_d3, p)
    n_above = (df.max_return_d3 >= v).sum()
    print(f"  P{p} of max_return_d3 = {v:.2f}%  ({n_above:,} stock-days at/above this)")
