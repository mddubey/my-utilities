"""RQ-QS-07A-SST1 -- Strong-State Transition Discovery (2026-10-02,
critic-specified next research-board item, pre-registered scope). S asks
"is the stock strong?" (composite trend-rank >= P90, a static detector --
CG2 already showed ~91.9% of S events occur in 4+ day runs, 85% of S
tickers appear on 20+ dates, so by the time S fires, the stock is often
already in an established state, not transitioning). This asks a
genuinely different question: "is the stock BECOMING strong, before the
static condition has saturated?"

NOT ALLOWED ON THIS PASS (critic's explicit list, carried forward as a hard
constraint): S threshold tuning, BT1 combinations, generic TA combinations,
exit optimization, liquidity rescue, BC/QS-A overlay, "best" threshold
selection. This script characterizes the state CHANGE only -- no entry
construct, no stop, no filter promotion.

LITERATURE CHECKED FIRST (External Reading Guardrail): (1) momentum
ACCELERATION (rate of change of momentum, e.g. return over the last period
minus return over the preceding period) is a published, mechanically
distinct predictor from momentum LEVEL -- "accelerating winners" earn a
higher subsequent alpha than momentum level alone (Momentum, Acceleration,
and Reversal literature) -- WITH AN EXPLICIT CAVEAT carried forward:
accelerated price increases are also linked to a HIGHER reversal
probability, not a free lunch. (2) Trend FRESHNESS/age is also published --
fresh breakouts embedded within an established uptrend outperform mature,
aged trends, whose predictive power decays as the trend ages. These
motivate the two mechanically distinct transition measures below, pre-
declared together before looking at any result (Rule #19):

  A. ACCELERATION: composite_delta_Nd = composite(T0) - composite(T-N), for
     N in {5, 10} (two windows, checked together, not picked after seeing
     results) -- the RATE OF CLIMB in the exact same composite trend-rank
     S itself is built from (dist_sma200_pct, ret_20d, dist_low252_pct,
     dist_ema34_pct, rsi14 -- frozen spec, no recalculation).
  B. FRESHNESS/AGE: among days already classified is_S, `run_age` = how
     many consecutive trading days (including T0) the composite has
     continuously sat >= P90. run_age=1 means T0 is the FIRST day of a
     fresh S entry; higher run_age = a long-established, saturated run.

PART A tests acceleration on the SAME Cohort A (102,837) + matched control
population used throughout 07A (full outcome-first discovery, not
conditioned on S) -- does the RATE OF CLIMB separate winners from ordinary
stocks, independent of whether either group is currently S?

PART B tests freshness specifically within the historical S population
(reusing the exact same frozen-spec classification as 19_/30_) -- do fresh
S entrants (low run_age) show a different forward outcome than long-
established S (high run_age)?

Outcome stays 07A's existing exceptional-3-day-mover definition
(max_return_d3/close_ret_d3) -- only the precursor characterization
changes, per the critic's framing.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import json
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"
SEED = 42
PRIMARY = ["dist_sma200_pct", "ret_20d", "dist_low252_pct", "dist_ema34_pct", "rsi14"]

print("Loading FROZEN spec (same as CG3/19_/30_, no recalculation)...", flush=True)
with open(f"{OUT_DIR}/frozen_candidate_spec.json") as f:
    spec = json.load(f)
P90 = spec["composite_p90_strong_state_cutoff"]
SORTED_ARRAYS = dict(np.load(f"{OUT_DIR}/frozen_sorted_arrays.npz"))


def exact_percentile_rank_vec(values, sorted_arr):
    left = np.searchsorted(sorted_arr, values, side="left")
    right = np.searchsorted(sorted_arr, values, side="right")
    return (left + right + 1) / 2.0 / len(sorted_arr) * 100.0


def composite_series(idf):
    """Vectorized composite trend-rank for every valid day in a ticker's history.
    Identical formula to 19_forward_validation_cg3.py / 30_s_bt1_combo.py,
    re-verified bit-for-bit against the scalar version there before being reused
    at scale -- not re-derived here."""
    N = len(idf)
    close = idf.Close
    close_20ago = close.shift(20)
    vals = pd.DataFrame({
        "dist_sma200_pct": (close / idf.sma200 - 1) * 100,
        "ret_20d": (close / close_20ago - 1) * 100,
        "dist_low252_pct": (close / idf.low_252 - 1) * 100,
        "dist_ema34_pct": (close / idf.ema34 - 1) * 100,
        "rsi14": idf.rsi14,
    })
    valid = vals.notna().all(axis=1) & (np.arange(N) >= 252)
    composite = pd.Series(np.nan, index=idf.index)
    idx_valid = vals.index[valid]
    if len(idx_valid) == 0:
        return composite
    rank_sum = np.zeros(len(idx_valid))
    for f in PRIMARY:
        rank_sum += exact_percentile_rank_vec(vals.loc[idx_valid, f].values, SORTED_ARRAYS[f])
    composite.loc[idx_valid] = rank_sum / len(PRIMARY)
    return composite


print("\n=== PART A: acceleration (composite_delta) on Cohort A vs matched control ===", flush=True)
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
work = pd.concat([a[["ticker", "date", "group"]], controls[["ticker", "date", "group"]]], ignore_index=True)
print(f"Cohort A: {len(a):,}  Controls: {len(controls):,}")

grouped = dict(tuple(work.groupby("ticker")))
rows_a = []
for n, t in enumerate(grouped):
    if n % 300 == 0:
        print(f"  {n}/{len(grouped)} tickers", flush=True)
    idf = load(t, daily_pivots)
    comp = composite_series(idf)
    comp_5ago = comp.shift(5)
    comp_10ago = comp.shift(10)
    sub = grouped[t]
    for r in sub.itertuples():
        if r.date not in idf.index:
            continue
        pos = idf.index.get_loc(r.date)
        if pos < 262:
            continue
        c0, c5, c10 = comp.iloc[pos], comp_5ago.iloc[pos], comp_10ago.iloc[pos]
        if pd.isna(c0) or pd.isna(c5) or pd.isna(c10):
            continue
        rows_a.append(dict(ticker=t, date=r.date, group=r.group, composite_t0=c0,
                             delta_5d=c0 - c5, delta_10d=c0 - c10))

feats_a = pd.DataFrame(rows_a)
feats_a.to_csv(f"{OUT_DIR}/sst1_acceleration_features.csv", index=False)
print(f"\n{len(feats_a):,} rows, saved sst1_acceleration_features.csv")


def pstack(s):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return f"P25={np.percentile(s,25):.2f} P50={np.percentile(s,50):.2f} P75={np.percentile(s,75):.2f} (n={len(s):,})"


print(f"\n{'='*110}\nACCELERATION -- Cohort A vs matched control\n{'='*110}")
ca, ct = feats_a[feats_a.group == "cohort_a"], feats_a[feats_a.group == "control"]
for f in ["delta_5d", "delta_10d"]:
    ca_med, ct_med = ca[f].median(), ct[f].median()
    print(f"  {f:10s} cohort_a: {pstack(ca[f]):36s}  control: {pstack(ct[f]):36s}  gap={ca_med-ct_med:+.2f}")

print("\n=== PART B: freshness/run_age within the historical S population ===", flush=True)
rows_b = []
uni = pd.read_csv("nse_equity_universe.csv")
tickers = uni.ticker.tolist()
print(f"Universe: {len(tickers)} tickers", flush=True)
for n, t in enumerate(tickers):
    if n % 300 == 0:
        print(f"  {n}/{len(tickers)} tickers  ({len(rows_b):,} S-rows so far)", flush=True)
    try:
        idf = load(t, daily_pivots)
    except FileNotFoundError:
        continue
    N = len(idf)
    if N < 256:
        continue
    comp = composite_series(idf)
    is_S = comp >= P90
    run_id = (is_S != is_S.shift()).cumsum()
    run_age = is_S.groupby(run_id).cumcount() + 1
    run_age = run_age.where(is_S, 0)

    close = idf.Close
    high1, high2, high3 = idf.High.shift(-1), idf.High.shift(-2), idf.High.shift(-3)
    close3 = idf.Close.shift(-3)
    max_h_d3 = pd.concat([high1, high2, high3], axis=1).max(axis=1)
    max_return_d3 = (max_h_d3 / close - 1) * 100
    close_ret_d3 = (close3 / close - 1) * 100
    valid_future = (np.arange(N) <= N - 4) & ~idf.corp_action_day.astype(bool)

    s_positions = np.where(is_S.values & valid_future)[0]
    for pos in s_positions:
        rows_b.append(dict(ticker=t, date=idf.index[pos], run_age=int(run_age.iloc[pos]),
                             max_return_d3=max_return_d3.iloc[pos], close_ret_d3=close_ret_d3.iloc[pos]))

feats_b = pd.DataFrame(rows_b)
feats_b.to_csv(f"{OUT_DIR}/sst1_freshness_features.csv", index=False)
print(f"\n{len(feats_b):,} S-classified rows, saved sst1_freshness_features.csv")

print(f"\n{'='*110}\nFRESHNESS -- forward outcome by run_age bucket (within S)\n{'='*110}")
b = feats_b.copy()
b["age_bucket"] = pd.cut(b.run_age, bins=[0, 1, 3, 7, 1000], labels=["1 (fresh)", "2-3", "4-7", "8+ (established)"])
summary = b.groupby("age_bucket", observed=True).agg(
    n=("run_age", "size"),
    max_return_d3_med=("max_return_d3", "median"),
    close_ret_d3_med=("close_ret_d3", "median"),
)
print(summary.to_string())

print("\nDONE")
