"""RQ-QS-07A-5 -- Trend-State -> Fast-Mover Anatomy (2026-09-29, critic-specified).

NOT another predictor search. NOT a threshold optimization. Question (critic's
exact framing): "What does the trend-strength state actually represent
immediately before the fast move?" -- the SHAPE of the relationship between
prior trend strength and subsequent fast-mover outcome, not a "does it
predict" binary (already answered, real but liquidity-concentrated, in
07A-3/07A-3R).

Critic's exact asks, all implemented here:
  1. At what degree of prior trend strength does fast-mover probability/
     opportunity begin to separate? -- descriptive bins, PRE-DECLARED (deciles
     of a composite score) before looking at any outcome.
  2. Continuous or concentrated in a tail?
  3. Survives across 07R's own regime labels (stable 2023-24 vs choppy
     2025-26)? -- so we can tell "trend state has predictive structure" from
     "trend state only looked predictive because 2022-24 happened to be a
     friendlier environment."
  4. Correlates with MFE, sustained close, or both? -- Cohort A and Cohort B
     reported SEPARATELY per bin, not unioned (07A-2B found 73.4% overlap;
     this checks whether the remaining ~27% is meaningful).
  5. Differs between structural pathway and circuit/wake-up pathway? --
     circuit_days_in_window==0 vs >0, same convention as 07A-3R's own
     circuit-involvement stratification.

Composite trend-strength score (MY design choice, not critic-specified --
documented for critic's review): 07A-3R found the 5 primary trend/momentum
variables (dist_sma200_pct, ret_20d, dist_low252_pct, dist_ema34_pct, rsi14)
are largely one latent dimension (Spearman 0.5-0.8 pairwise, both cohort_a and
control). All 5 share the same "higher = stronger trend" sign convention,
verified against 05_precursor_discovery.py's exact formulas -- no sign flips
needed. Composite = mean of each variable's percentile rank (0-100), computed
ONCE across this script's full population (not per-date). Used ONLY as the
single binning axis this whole RQ is about -- never tested as an additional
feature alongside its own components (would violate Rule #7).

POPULATION: unlike 05_/07_/08_ (Cohort A + matched controls, 205,674 rows),
this uses the FULL neutral event_matrix.csv population (2,056,725 stock-days)
-- deliberately: a dose-response/shape question needs the full distribution,
not a matched-pair subsample. Cohort A/B membership (fixed whole-period P95
thresholds, same as every other 07A script) and MFE/close_ret_d3 magnitude
already exist in event_matrix.csv.

REGIME LABEL (operational, derived directly from 07R's own finding, not a new
claim): year in {2023,2024} -> "stable", year in {2025,2026} -> "choppy",
year in {2021,2022} -> "early" (kept separate, de-emphasized -- 07R's
breadth-stability characterization was specifically about 2023-24 vs 2025-26).

No threshold chosen on the composite itself (bins are for description only).
No model. No filter promoted.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"

print("Loading full neutral event matrix...", flush=True)
em = pd.read_csv(f"{OUT_DIR}/event_matrix.csv", parse_dates=["date"])
P95_MFE = np.percentile(em.max_return_d3, 95)
P95_CLOSE = np.percentile(em.close_ret_d3, 95)
em["cohort_a"] = em.max_return_d3 >= P95_MFE
em["cohort_b"] = em.close_ret_d3 >= P95_CLOSE
em["year"] = em.date.dt.year
em["regime"] = np.select([em.year.isin([2023, 2024]), em.year.isin([2025, 2026])],
                           ["stable(23-24)", "choppy(25-26)"], default="early(21-22)")
em["circuit_pathway"] = np.where(em.circuit_days_in_window > 0, "circuit/wake-up", "structural")
print(f"Population: {len(em):,}  cohort_a={em.cohort_a.sum():,}  cohort_b={em.cohort_b.sum():,}  "
      f"overlap={((em.cohort_a) & (em.cohort_b)).sum():,}")

print("Computing 5 trend/momentum features per stock-day (per-ticker, decision-time-safe, "
      "same formulas as 05_precursor_discovery.py)...", flush=True)
grouped = list(em.groupby("ticker", sort=False))
rows_out = []
for n, (t, sub) in enumerate(grouped):
    if n % 300 == 0:
        print(f"  {n}/{len(grouped)}", flush=True)
    try:
        idf = load(t, daily_pivots)
    except FileNotFoundError:
        continue
    idx = idf.index
    for r in sub.itertuples():
        if r.date not in idf.index:
            continue
        row = idf.loc[r.date]
        close = row.Close
        pos = idx.get_loc(r.date)
        close_20ago = idf.Close.iloc[pos - 20] if pos >= 20 else np.nan
        rows_out.append((
            r.Index,
            (close / row.ema34 - 1) * 100 if pd.notna(row.ema34) else np.nan,
            (close / row.sma200 - 1) * 100 if pd.notna(row.sma200) else np.nan,
            (close / row.low_252 - 1) * 100 if pd.notna(row.low_252) and row.low_252 else np.nan,
            (close / close_20ago - 1) * 100 if pd.notna(close_20ago) and close_20ago else np.nan,
            row.rsi14,
        ))

feat_df = pd.DataFrame(rows_out, columns=["idx", "dist_ema34_pct", "dist_sma200_pct",
                                            "dist_low252_pct", "ret_20d", "rsi14"]).set_index("idx")
em = em.join(feat_df)
PRIMARY = ["dist_sma200_pct", "ret_20d", "dist_low252_pct", "dist_ema34_pct", "rsi14"]
fully_populated = em[PRIMARY].notna().all(axis=1)
print(f"Rows with all 5 features populated: {fully_populated.sum():,} of {len(em):,}")

print("Building composite trend-strength score (mean of percentile ranks)...", flush=True)
work = em[fully_populated].copy()
for f in PRIMARY:
    work[f"{f}_rank"] = work[f].rank(pct=True) * 100
work["trend_strength_composite"] = work[[f"{f}_rank" for f in PRIMARY]].mean(axis=1)
work["decile"] = pd.qcut(work.trend_strength_composite, 10, labels=False, duplicates="drop")

work.to_csv(f"{OUT_DIR}/trend_state_anatomy.csv", index=False)
print(f"saved trend_state_anatomy.csv ({len(work):,} rows)")


def summarize(df, label):
    print(f"\n{'='*100}\n{label}\n{'='*100}")
    g = df.groupby("decile").agg(
        n=("ticker", "size"),
        composite_mean=("trend_strength_composite", "mean"),
        pct_cohort_a=("cohort_a", lambda x: x.mean() * 100),
        pct_cohort_b=("cohort_b", lambda x: x.mean() * 100),
        pct_a_only=("ticker", lambda x: (df.loc[x.index, "cohort_a"] & ~df.loc[x.index, "cohort_b"]).mean() * 100),
        pct_b_only=("ticker", lambda x: (~df.loc[x.index, "cohort_a"] & df.loc[x.index, "cohort_b"]).mean() * 100),
        pct_overlap=("ticker", lambda x: (df.loc[x.index, "cohort_a"] & df.loc[x.index, "cohort_b"]).mean() * 100),
        median_mfe=("max_return_d3", "median"), p90_mfe=("max_return_d3", lambda x: np.percentile(x, 90)),
        median_close=("close_ret_d3", "median"), p90_close=("close_ret_d3", lambda x: np.percentile(x, 90)),
    )
    print(g.round(2).to_string())
    return g


overall = summarize(work, "OVERALL -- trend-strength decile vs Cohort A / Cohort B rate & magnitude "
                            "(0=weakest trend state, 9=strongest)")
overall.round(4).to_csv(f"{OUT_DIR}/trend_state_anatomy_overall_by_decile.csv")

for regime in ["stable(23-24)", "choppy(25-26)", "early(21-22)"]:
    sub = work[work.regime == regime]
    if len(sub) < 5000:
        print(f"\n{regime}: too thin ({len(sub):,}), skipped")
        continue
    summarize(sub, f"BY REGIME -- {regime} (n={len(sub):,})")

for pathway in ["structural", "circuit/wake-up"]:
    sub = work[work.circuit_pathway == pathway]
    summarize(sub, f"BY PATHWAY -- {pathway} (n={len(sub):,})")

print(f"\n{'='*100}\nSHAPE CHECK -- decile-over-decile rate change (is separation gradual or a tail effect?)\n{'='*100}")
d = overall.reset_index()
d["pct_a_delta"] = d.pct_cohort_a.diff()
d["pct_b_delta"] = d.pct_cohort_b.diff()
print(d[["decile", "pct_cohort_a", "pct_a_delta", "pct_cohort_b", "pct_b_delta"]].round(2).to_string(index=False))

print("\nDONE")
