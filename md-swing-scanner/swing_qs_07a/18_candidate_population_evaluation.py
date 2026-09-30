"""RQ-QS-07A-CG2 -- Frozen Candidate Population Evaluation (2026-09-30,
critic-specified).

Question changes character here, per critic's exact framing: not "what else
can we discover" but "what does this frozen machine actually surface when we
let it run?" Uses the CORRECTED frozen spec from CG1's integrity patch
(exact ECDF lookup, 0 boundary flips verified in `17_boundary_flip_audit.py`)
-- since that audit proved 0 membership flips, the already-saved `decile`
column (decile==0 / decile==9) is PROVEN equivalent to the frozen exact
lookup for classification purposes and is reused directly here rather than
redundantly recomputing composite scores for 1.66M rows a second time.

POPULATION: every eligible historical stock-day already in
`trend_state_anatomy.csv` (2022-09-02 to 2026-09-24, D1-D3 already resolved
by `01_event_matrix.py`'s own eligibility construction) -- NO date sampling,
NO new date-range logic. Route W additionally uses
`weak_state_mechanism_features.csv`, which already covers the FULL D0
population across the whole history (not a demo window). NO threshold
changes, NO candidate filtering, NO W/S combination.

LABELING DISCIPLINE (critic's explicit correction): because the frozen
constants were derived FROM this same population, every number below is
IN-SAMPLE DESCRIPTIVE characterization of what the frozen definitions
produce historically -- NOT a claim of forward predictive "hit rate."
Reported throughout as "historical candidate events had X% Cohort-A
incidence," never "hit rate" or "performance."

FOUR PRIMARY OUTPUTS (critic's exact list): (1) coverage, (2) fast-mover
enrichment, (3) temporal/regime stability (year, then quarter secondary --
per this project's own standing Rule "never pool years"), (4) candidate
overlap/independence (ticker concentration, repeated appearances). Plus one
addition, per critic: candidate PERSISTENCE (consecutive/near-consecutive
candidate runs per ticker) -- descriptive only, no dedup rule built.

THREE SECONDARY OUTPUTS (annotate, do NOT filter): liquidity, F&O
availability, circuit involvement.

GUARDRAIL: if any stratification below looks "interesting" (e.g. "W works
better in F&O"), that becomes a candidate for a NEW RQ -- this script does
not act on it, does not retune anything, does not combine W+S.
"""
import json
import numpy as np
import pandas as pd

OUT_DIR = "."

with open(f"{OUT_DIR}/frozen_candidate_spec.json") as f:
    spec = json.load(f)
DECLINE_MEDIAN = spec["decline_from_high10d_pct_median_weak_state"]
print(f"Loaded corrected frozen spec (post-17_ integrity patch): decline_median={DECLINE_MEDIAN:.3f}, "
      f"lookup_method={spec['lookup_method'][:60]}...")

print("Loading full eligible population...", flush=True)
state = pd.read_csv("trend_state_anatomy.csv", parse_dates=["date"])
mech = pd.read_csv("weak_state_mechanism_features.csv", parse_dates=["date"])[
    ["ticker", "date", "ret_1d", "decline_from_high10d_pct"]]
n_dates = state.date.nunique()
print(f"Eligible population: {len(state):,} stock-days across {n_dates:,} trading dates "
      f"({state.date.min().date()} to {state.date.max().date()})")

state["liq_decile"] = state.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop") if x.notna().sum() >= 10 else np.nan)
state["liq_tercile"] = pd.cut(state.liq_decile, [-1, 2, 6, 9], labels=["low", "mid", "high"])
state["circuit_involved"] = state.circuit_days_in_window > 0

S = state[state.decile == 9].copy()
d0 = state[state.decile == 0].merge(mech, on=["ticker", "date"], how="inner")
assert len(d0) == (state.decile == 0).sum(), "D0 merge changed row count -- investigate before trusting anything below"
W = d0[(d0.decline_from_high10d_pct <= DECLINE_MEDIAN) & (d0.ret_1d >= 0)].copy()
print(f"Route S (frozen, decile==9, proven 0-flip equivalent to exact lookup): {len(S):,} rows")
print(f"Route W (frozen, decile==0 AND decline<=median AND green): {len(W):,} rows")

baseline_cohort_a = state.cohort_a.mean() * 100
baseline_cohort_b = state.cohort_b.mean() * 100
print(f"Population baseline (context, not a comparison group): Cohort A incidence = {baseline_cohort_a:.2f}%, "
      f"Cohort B incidence = {baseline_cohort_b:.2f}%")

# ---------------------------------------------------------------------------
# PRIMARY 1 -- COVERAGE
# ---------------------------------------------------------------------------
print(f"\n{'='*110}\nPRIMARY 1 -- COVERAGE\n{'='*110}")
for label, df in [("Route W", W), ("Route S", S)]:
    print(f"  {label}: {len(df):,} candidate-events, {len(df)/len(state)*100:.3f}% of eligible stock-days, "
          f"{len(df)/n_dates:.2f} candidates/trading-day on average, "
          f"{df.date.nunique():,} distinct dates with >=1 candidate (of {n_dates:,})")

# ---------------------------------------------------------------------------
# PRIMARY 2 -- FAST-MOVER ENRICHMENT (in-sample descriptive, not a hit-rate claim)
# ---------------------------------------------------------------------------
print(f"\n{'='*110}\nPRIMARY 2 -- HISTORICAL CANDIDATE EVENTS' COHORT INCIDENCE (in-sample descriptive -- "
      f"NOT a forward hit-rate claim)\n{'='*110}")
for label, df in [("Route W", W), ("Route S", S)]:
    print(f"  {label}: Cohort A incidence = {df.cohort_a.mean()*100:.2f}% (baseline {baseline_cohort_a:.2f}%)  "
          f"Cohort B incidence = {df.cohort_b.mean()*100:.2f}% (baseline {baseline_cohort_b:.2f}%)")
    print(f"    D3 MFE distribution: P25={np.percentile(df.max_return_d3,25):.2f}  "
          f"P50={np.percentile(df.max_return_d3,50):.2f}  P75={np.percentile(df.max_return_d3,75):.2f}  "
          f"P90={np.percentile(df.max_return_d3,90):.2f}")
    print(f"    D3 close-return distribution: P25={np.percentile(df.close_ret_d3,25):.2f}  "
          f"P50={np.percentile(df.close_ret_d3,50):.2f}  P75={np.percentile(df.close_ret_d3,75):.2f}  "
          f"P90={np.percentile(df.close_ret_d3,90):.2f}")

# ---------------------------------------------------------------------------
# PRIMARY 3 -- TEMPORAL/REGIME STABILITY (per-year, never pooled; quarter secondary)
# ---------------------------------------------------------------------------
print(f"\n{'='*110}\nPRIMARY 3 -- TEMPORAL STABILITY, by year (never pooled, per this project's own standing rule)\n{'='*110}")
year_rows = []
for label, df in [("Route W", W), ("Route S", S)]:
    for y in sorted(df.year.unique()):
        sub = df[df.year == y]
        year_rows.append(dict(route=label, year=y, n=len(sub), pct_cohort_a=round(sub.cohort_a.mean()*100, 2),
                                 pct_cohort_b=round(sub.cohort_b.mean()*100, 2),
                                 median_mfe_d3=round(sub.max_return_d3.median(), 2)))
year_tbl = pd.DataFrame(year_rows)
print(year_tbl.to_string(index=False))
year_tbl.to_csv(f"{OUT_DIR}/candidate_eval_by_year.csv", index=False)

print(f"\n-- secondary view, by quarter --")
state["quarter"] = state.date.dt.to_period("Q")
W["quarter"] = W.date.dt.to_period("Q")
S["quarter"] = S.date.dt.to_period("Q")
quarter_rows = []
for label, df in [("Route W", W), ("Route S", S)]:
    for q in sorted(df.quarter.unique()):
        sub = df[df.quarter == q]
        if len(sub) < 20:
            continue
        quarter_rows.append(dict(route=label, quarter=str(q), n=len(sub),
                                    pct_cohort_a=round(sub.cohort_a.mean()*100, 2)))
quarter_tbl = pd.DataFrame(quarter_rows)
print(quarter_tbl.to_string(index=False))
quarter_tbl.to_csv(f"{OUT_DIR}/candidate_eval_by_quarter.csv", index=False)

# ---------------------------------------------------------------------------
# PRIMARY 4 -- CANDIDATE OVERLAP / INDEPENDENCE, CONCENTRATION
# ---------------------------------------------------------------------------
print(f"\n{'='*110}\nPRIMARY 4 -- OVERLAP, TICKER CONCENTRATION, REPEATED APPEARANCES\n{'='*110}")
overlap = pd.merge(W[["ticker", "date"]], S[["ticker", "date"]], on=["ticker", "date"], how="inner")
print(f"  W vs S overlap (same ticker, same date): {len(overlap)} rows -- should be 0 by construction "
      f"(opposite composite tails)")

for label, df in [("Route W", W), ("Route S", S)]:
    counts = df.ticker.value_counts()
    top10_share = counts.head(10).sum() / len(df) * 100
    top20_share = counts.head(20).sum() / len(df) * 100
    print(f"\n  {label}: {df.ticker.nunique():,} distinct tickers ever appear as a candidate, "
          f"{len(df):,} total candidate-events")
    print(f"    Top 10 tickers' share of all candidate-events: {top10_share:.2f}%")
    print(f"    Top 20 tickers' share of all candidate-events: {top20_share:.2f}%")
    print(f"    Top 5 tickers by appearance count: {counts.head(5).to_dict()}")
    appearance_buckets = pd.cut(counts, [0, 1, 2, 5, 20, 1e9], labels=["1x", "2x", "3-5x", "6-20x", "20x+"])
    print(f"    Distribution of tickers by appearance-count bucket:\n{appearance_buckets.value_counts().sort_index().to_string()}")

# ---------------------------------------------------------------------------
# CANDIDATE PERSISTENCE (critic's addition) -- consecutive/near-consecutive runs
# ---------------------------------------------------------------------------
print(f"\n{'='*110}\nCANDIDATE PERSISTENCE -- consecutive/near-consecutive candidate runs per ticker (descriptive only, "
      f"'near-consecutive' = candidate dates for the same ticker <=5 calendar days apart, accounting for weekends)\n{'='*110}")


def compute_run_lengths(df):
    run_lengths = []
    for t, g in df.sort_values("date").groupby("ticker"):
        dates = g.date.tolist()
        run = 1
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]).days <= 5:
                run += 1
            else:
                run_lengths.append(run)
                run = 1
        run_lengths.append(run)
    return pd.Series(run_lengths)


for label, df in [("Route W", W), ("Route S", S)]:
    runs = compute_run_lengths(df)
    print(f"\n  {label}: {len(runs):,} distinct candidate 'episodes' (runs) from {len(df):,} candidate-events")
    print(f"    Run-length distribution: {runs.value_counts().sort_index().head(10).to_dict()}")
    print(f"    % of episodes that are single-day (no persistence): {(runs == 1).mean()*100:.1f}%")
    print(f"    % of candidate-EVENTS (not episodes) belonging to a run of 4+ days: "
          f"{runs[runs >= 4].sum() / len(df) * 100:.1f}%")

# ---------------------------------------------------------------------------
# SECONDARY -- liquidity, F&O, circuit (annotate only, no filtering)
# ---------------------------------------------------------------------------
print(f"\n{'='*110}\nSECONDARY -- LIQUIDITY (candidate distribution vs. broad eligible population, not filtered)\n{'='*110}")
pop_liq = (state.liq_tercile.value_counts(normalize=True) * 100).round(1)
print(f"  Broad eligible population liq_tercile share: {pop_liq.to_dict()}")
for label, df in [("Route W", W), ("Route S", S)]:
    liq_share = (df.liq_tercile.value_counts(normalize=True) * 100).round(1)
    print(f"  {label} candidates' liq_tercile share: {liq_share.to_dict()}")

print(f"\n{'='*110}\nSECONDARY -- F&O AVAILABILITY (annotate only)\n{'='*110}")
for label, df in [("Route W", W), ("Route S", S)]:
    fo_pct = df.fo_eligible.mean() * 100
    fo_a_rate = df[df.fo_eligible].cohort_a.mean() * 100 if df.fo_eligible.sum() else np.nan
    nonfo_a_rate = df[~df.fo_eligible].cohort_a.mean() * 100
    print(f"  {label}: {fo_pct:.2f}% of candidates are F&O-eligible. Cohort A incidence within F&O = "
          f"{fo_a_rate:.2f}% (n={df.fo_eligible.sum():,}), within non-F&O = {nonfo_a_rate:.2f}% "
          f"(n={(~df.fo_eligible).sum():,})")

print(f"\n{'='*110}\nSECONDARY -- CIRCUIT INVOLVEMENT (annotate only)\n{'='*110}")
for label, df in [("Route W", W), ("Route S", S)]:
    circ_pct = df.circuit_involved.mean() * 100
    circ_mfe = df[df.circuit_involved].max_return_d3.median() if df.circuit_involved.sum() else np.nan
    noncirc_mfe = df[~df.circuit_involved].max_return_d3.median()
    print(f"  {label}: {circ_pct:.2f}% of candidates are circuit-involved (n={df.circuit_involved.sum():,}). "
          f"Median D3 MFE: circuit-involved={circ_mfe:.2f}, structural={noncirc_mfe:.2f}")

W.to_csv(f"{OUT_DIR}/candidate_eval_route_w.csv", index=False)
S.to_csv(f"{OUT_DIR}/candidate_eval_route_s.csv", index=False)
print("\nDONE")
