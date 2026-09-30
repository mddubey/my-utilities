"""RQ-QS-07A-CG3-H -- Historical Holdout Validation (2026-09-30, critic-specified,
revised recommendation after the user's pushback on CG3's 5-7 week timeline).

NOT a replacement for CG3 -- runs IN PARALLEL. Critic's own framing: CG3-H
answers "could this frozen methodology have worked on a genuinely withheld
period?" (fast). CG3 answers "does it continue to work on information that
genuinely nobody had at specification-freeze time?" (slow, still
accumulating, untouched by this script).

CRITICAL: this is NOT the CG1 specification re-applied. CG1's frozen
constants (`frozen_candidate_spec.json` / `frozen_sorted_arrays.npz`) remain
untouched and are NOT used here -- that would defeat the purpose of a
holdout test (the CG1 constants were derived from the WHOLE population,
including the holdout period). This script builds an INDEPENDENT set of
constants derived EXCLUSIVELY from the training period, then applies them
to the holdout period.

TRAIN / HOLDOUT SPLIT (critic's exact cutoff, a clean quarter boundary):
  Train:   2022-09-02 -> 2026-03-31 (derive ALL reference statistics here)
  Holdout: 2026-04-01 -> 2026-09-24 (candidate generation + outcome lookup
           ONLY -- no holdout-derived statistic flows back into the
           candidate definition)

Everything that defines the candidate boundaries comes exclusively from the
training period: composite percentile distributions, P10/P90, the
decline-depth median, and the sorted-array lookup tables. Same exact-ECDF
lookup methodology as CG1's integrity patch (`17_boundary_flip_audit.py`) --
no re-adoption of the superseded 101-point interpolation.

REPORTING (critic's exact list, deliberately mirrors CG2 so it's an
apples-to-apples comparison): coverage, Cohort-A incidence (labeled
"incidence," never "hit rate"), D3 MFE distribution (median/P75/P90/P95/P99),
D3 close distribution (same), monthly/quarterly stability (not pooled),
secondary liquidity/F&O/circuit/persistence/concentration (annotate only,
never used to modify the definition), and a compact train-vs-holdout
comparison table.

RESEARCHER-CONDITIONING CAVEAT (critic's exact wording, reproduced verbatim
in FINDINGS.md): this is a genuine chronological train/test split at the
NUMERICAL level, but the research team had already inspected and analyzed
portions of the holdout period during earlier exploratory RQs conducted
before the candidate definition was frozen -- so it is an intermediate
validation of temporal generalization, not equivalent to a fully blind
prospective test. The independently-accumulating CG3 log remains the
cleanest test of forward performance.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"
PRIMARY = ["dist_sma200_pct", "ret_20d", "dist_low252_pct", "dist_ema34_pct", "rsi14"]
TRAIN_CUTOFF = pd.Timestamp("2026-03-31")

print("Loading full population (trend_state_anatomy.csv)...", flush=True)
state = pd.read_csv(f"{OUT_DIR}/trend_state_anatomy.csv", parse_dates=["date"])
print(f"Full population: {len(state):,} rows, {state.date.min().date()} to {state.date.max().date()}")

# ---------------------------------------------------------------------------
# STEP 1: decline_from_high10d_pct + ret_1d for the FULL population (not just
# the full-population's D0 subset, which is all weak_state_mechanism_features.csv
# covers -- the training-only D0 definition will select a DIFFERENT subset of
# rows, so this needs to exist for every eligible row, train and holdout alike).
# ---------------------------------------------------------------------------
CACHE_FILE = f"{OUT_DIR}/full_population_decline_ret1d.csv"
if os.path.exists(CACHE_FILE):
    print(f"\nReusing cached {CACHE_FILE}...", flush=True)
    extra = pd.read_csv(CACHE_FILE, parse_dates=["date"])
else:
    print("\nComputing decline_from_high10d_pct + ret_1d for the FULL population "
          "(per-ticker, decision-time-safe, same formula as 12_)...", flush=True)
    grouped = list(state.groupby("ticker", sort=False))
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
            if r.date not in idx:
                continue
            pos = idx.get_loc(r.date)
            close = idf.Close.iloc[pos]
            close_1ago = idf.Close.iloc[pos - 1] if pos >= 1 else np.nan
            high10 = idf.High.iloc[max(0, pos - 9):pos + 1].max() if pos >= 9 else np.nan
            rows_out.append((r.ticker, r.date,
                                (close / high10 - 1) * 100 if pd.notna(high10) and high10 else np.nan,
                                (close / close_1ago - 1) * 100 if pd.notna(close_1ago) and close_1ago else np.nan))
    extra = pd.DataFrame(rows_out, columns=["ticker", "date", "decline_from_high10d_pct", "ret_1d"])
    extra.to_csv(CACHE_FILE, index=False)
    print(f"Saved {CACHE_FILE} ({len(extra):,} rows)")

state = state.merge(extra, on=["ticker", "date"], how="inner")
assert len(state) == len(extra), "merge dropped rows unexpectedly -- investigate before trusting anything below"
print(f"After merge: {len(state):,} rows with decline_from_high10d_pct/ret_1d available")

train = state[state.date <= TRAIN_CUTOFF].copy()
holdout = state[state.date > TRAIN_CUTOFF].copy()
print(f"\nTrain: {len(train):,} rows ({train.date.min().date()} to {train.date.max().date()})")
print(f"Holdout: {len(holdout):,} rows ({holdout.date.min().date()} to {holdout.date.max().date()})")

# ---------------------------------------------------------------------------
# STEP 2: training-only reference statistics. Exact same exact-ECDF
# methodology as CG1's integrity patch -- no 101-point approximation.
# ---------------------------------------------------------------------------
print("\nDeriving TRAINING-ONLY composite score, P10/P90, decline-median...", flush=True)
SORTED_ARRAYS_TRAIN = {f: np.sort(train[f].dropna().values) for f in PRIMARY}


def exact_percentile_rank_vec(values, sorted_arr):
    left = np.searchsorted(sorted_arr, values, side="left")
    right = np.searchsorted(sorted_arr, values, side="right")
    return (left + right + 1) / 2.0 / len(sorted_arr) * 100.0


train_ranks = np.column_stack([exact_percentile_rank_vec(train[f].values, SORTED_ARRAYS_TRAIN[f]) for f in PRIMARY])
train["composite_train"] = train_ranks.mean(axis=1)
P10_TRAIN = float(np.percentile(train.composite_train, 10))
P90_TRAIN = float(np.percentile(train.composite_train, 90))
train["is_D0_train"] = train.composite_train <= P10_TRAIN
DECLINE_MEDIAN_TRAIN = float(train.loc[train.is_D0_train, "decline_from_high10d_pct"].median())
print(f"TRAINING-derived constants: P10={P10_TRAIN:.3f}  P90={P90_TRAIN:.3f}  "
      f"decline_median={DECLINE_MEDIAN_TRAIN:.3f}  (compare to CG1's full-population P10=16.728 P90=84.064 "
      f"decline=-10.433 -- expected to differ somewhat, different reference population)")

# ---------------------------------------------------------------------------
# STEP 3: apply TRAINING constants to the HOLDOUT period (no holdout-derived
# statistic flows back into the definition).
# ---------------------------------------------------------------------------
print("\nApplying training-derived constants to the holdout period...", flush=True)
holdout_ranks = np.column_stack([exact_percentile_rank_vec(holdout[f].values, SORTED_ARRAYS_TRAIN[f]) for f in PRIMARY])
holdout["composite_via_train"] = holdout_ranks.mean(axis=1)
holdout["is_W"] = ((holdout.composite_via_train <= P10_TRAIN)
                     & (holdout.decline_from_high10d_pct <= DECLINE_MEDIAN_TRAIN)
                     & (holdout.ret_1d >= 0))
holdout["is_S"] = holdout.composite_via_train >= P90_TRAIN
holdout["liq_decile"] = holdout.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop") if x.notna().sum() >= 10 else np.nan)
holdout["liq_tercile"] = pd.cut(holdout.liq_decile, [-1, 2, 6, 9], labels=["low", "mid", "high"])
holdout["circuit_involved"] = holdout.circuit_days_in_window > 0
holdout["month"] = holdout.date.dt.to_period("M")

W = holdout[holdout.is_W].copy()
S = holdout[holdout.is_S].copy()
n_holdout_dates = holdout.date.nunique()
baseline_a_holdout = holdout.cohort_a.mean() * 100
print(f"Holdout: {n_holdout_dates} trading dates, W={len(W):,} candidates, S={len(S):,} candidates, "
      f"baseline Cohort A incidence={baseline_a_holdout:.2f}%")

# ---------------------------------------------------------------------------
# PRIMARY 1 -- COVERAGE
# ---------------------------------------------------------------------------
print(f"\n{'='*115}\nPRIMARY 1 -- COVERAGE (holdout period)\n{'='*115}")
for label, df in [("W", W), ("S", S)]:
    print(f"  {label}: {len(df):,} candidate-events, {len(df)/len(holdout)*100:.3f}% of eligible holdout stock-days, "
          f"{len(df)/n_holdout_dates:.2f}/day, {df.date.nunique():,} of {n_holdout_dates} dates with >=1, "
          f"{df.ticker.nunique():,} unique tickers")

# ---------------------------------------------------------------------------
# PRIMARY 2 -- COHORT-A/B INCIDENCE + D3 MFE/CLOSE DISTRIBUTIONS
# ---------------------------------------------------------------------------
print(f"\n{'='*115}\nPRIMARY 2 -- HISTORICAL-HOLDOUT INCIDENCE (in-sample-to-training, not a hit-rate claim) "
      f"vs. CG2's original in-sample numbers\n{'='*115}")
for label, df, cg2_a, cg2_b in [("W", W, 10.23, 10.16), ("S", S, 8.47, 8.22)]:
    a_inc, b_inc = df.cohort_a.mean() * 100, df.cohort_b.mean() * 100
    print(f"  {label}: holdout Cohort A incidence={a_inc:.2f}% (CG2 in-sample was {cg2_a}%)  "
          f"Cohort B incidence={b_inc:.2f}% (CG2 in-sample was {cg2_b}%)  baseline={baseline_a_holdout:.2f}%")
    for metric in ["max_return_d3", "close_ret_d3"]:
        pct = np.percentile(df[metric], [50, 75, 90, 95, 99])
        print(f"    {metric}: P50={pct[0]:.2f} P75={pct[1]:.2f} P90={pct[2]:.2f} P95={pct[3]:.2f} P99={pct[4]:.2f}")

# ---------------------------------------------------------------------------
# PRIMARY 3 -- MONTHLY STABILITY (not pooled)
# ---------------------------------------------------------------------------
print(f"\n{'='*115}\nPRIMARY 3 -- MONTHLY STABILITY (holdout period, never pooled)\n{'='*115}")
monthly_rows = []
for label, df in [("W", W), ("S", S)]:
    for m in sorted(df.month.unique()):
        sub = df[df.month == m]
        monthly_rows.append(dict(route=label, month=str(m), n=len(sub),
                                    pct_cohort_a=round(sub.cohort_a.mean() * 100, 2),
                                    median_mfe_d3=round(sub.max_return_d3.median(), 2)))
monthly_tbl = pd.DataFrame(monthly_rows)
print(monthly_tbl.to_string(index=False))
monthly_tbl.to_csv(f"{OUT_DIR}/cg3h_by_month.csv", index=False)

# ---------------------------------------------------------------------------
# PRIMARY 4 -- OVERLAP, CONCENTRATION, EPISODES (same methodology as CG2)
# ---------------------------------------------------------------------------
print(f"\n{'='*115}\nPRIMARY 4 -- OVERLAP, CONCENTRATION, PERSISTENCE (holdout period)\n{'='*115}")
overlap = pd.merge(W[["ticker", "date"]], S[["ticker", "date"]], on=["ticker", "date"], how="inner")
print(f"  W vs S overlap: {len(overlap)} rows (should be 0 by construction)")


def compute_run_lengths(df):
    run_lengths = []
    for t, g in df.sort_values("date").groupby("ticker"):
        dates = g.date.tolist()
        run = 1
        for i in range(1, len(dates)):
            run = run + 1 if (dates[i] - dates[i - 1]).days <= 5 else (run_lengths.append(run) or 1)
        run_lengths.append(run)
    return pd.Series(run_lengths)


for label, df in [("W", W), ("S", S)]:
    counts = df.ticker.value_counts()
    runs = compute_run_lengths(df)
    print(f"\n  {label}: {df.ticker.nunique()} unique tickers, {len(df)} events, {len(runs)} episodes")
    print(f"    Top 10 tickers' share: {counts.head(10).sum()/len(df)*100:.2f}%   "
          f"% single-day episodes: {(runs==1).mean()*100:.1f}%   "
          f"% events in a 4+-day run: {runs[runs>=4].sum()/len(df)*100:.1f}%")

# ---------------------------------------------------------------------------
# SECONDARY -- liquidity, F&O, circuit (annotate only)
# ---------------------------------------------------------------------------
print(f"\n{'='*115}\nSECONDARY -- liquidity / F&O / circuit (annotate only, holdout period)\n{'='*115}")
for label, df in [("W", W), ("S", S)]:
    liq = (df.liq_tercile.value_counts(normalize=True) * 100).round(1)
    fo_pct = df.fo_eligible.mean() * 100
    circ_pct = df.circuit_involved.mean() * 100
    print(f"  {label}: liq_tercile share={liq.to_dict()}  F&O-eligible={fo_pct:.2f}%  circuit-involved={circ_pct:.2f}%")

# ---------------------------------------------------------------------------
# TRAIN-VS-HOLDOUT COMPARISON TABLE (critic's exact request)
# ---------------------------------------------------------------------------
print(f"\n{'='*115}\nTRAIN vs HOLDOUT COMPARISON\n{'='*115}")
comparison = pd.DataFrame([
    dict(metric="Baseline Cohort A incidence", training_CG2=4.68, holdout=round(baseline_a_holdout, 2)),
    dict(metric="W coverage (% of eligible)", training_CG2=1.346, holdout=round(len(W)/len(holdout)*100, 3)),
    dict(metric="W Cohort A incidence", training_CG2=10.23, holdout=round(W.cohort_a.mean()*100, 2)),
    dict(metric="S coverage (% of eligible)", training_CG2=10.000, holdout=round(len(S)/len(holdout)*100, 3)),
    dict(metric="S Cohort A incidence", training_CG2=8.47, holdout=round(S.cohort_a.mean()*100, 2)),
    dict(metric="W D3 MFE median", training_CG2=4.31, holdout=round(W.max_return_d3.median(), 2)),
    dict(metric="S D3 MFE median", training_CG2=3.75, holdout=round(S.max_return_d3.median(), 2)),
    dict(metric="W D3 close median", training_CG2=0.03, holdout=round(W.close_ret_d3.median(), 2)),
    dict(metric="S D3 close median", training_CG2=-0.25, holdout=round(S.close_ret_d3.median(), 2)),
])
print(comparison.to_string(index=False))
comparison.to_csv(f"{OUT_DIR}/cg3h_train_vs_holdout.csv", index=False)

W.to_csv(f"{OUT_DIR}/cg3h_holdout_route_w.csv", index=False)
print("\nDONE")
