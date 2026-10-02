"""RQ-QS-07A-BT1 -- Behavioural/State-Transition Discovery (2026-10-02,
research-board item #2, critic's explicit next-in-order pick, per
swing_qs_07a/CLAUDE.md's research board). First discovery pass for this
hypothesis family: "before an exceptional 3-day move, is there a detectable
TRANSITION/regime-shift in volume or return behavior -- not merely an
elevated static LEVEL?"

WHY THIS IS NOT "ANOTHER RVOL>X TEST": RQ-QS-07A-3 already tested static
single-window volume/volatility LEVELS at T0 (vol_zscore, vol_ratio_10d,
atr_expansion, body_atr, ad_fraction, vol_declining5) and found all of them
weak-to-null (see FINDINGS.md). The board's explicit instruction is to test
a genuinely different MECHANISM: a multi-day TRANSITION/acceleration/
clustering/structural-break pattern, not a bigger single-day threshold on
the same already-tested quantities.

LITERATURE CHECKED FIRST (External Reading Guardrail), not invented from the
data: (1) short-window volume ACCELERATION (ratio of two adjacent short
windows, not a ratio to a long static baseline) is used in momentum-burst
literature as "volume building into a move"; (2) RETURN-BURST FREQUENCY
(count of outsized days in a lookback window) is distinct from average
magnitude -- captures clustering/bursty behavior, the behavioral-finance
notion that abnormal-volume days cluster before momentum continuation;
(3) CUSUM-style change-point statistics (one-sided cumulative sum of
standardized deviations from a stale baseline) are a standard, published
way to detect a sustained REGIME SHIFT as distinct from a single-day spike
(Bayesian/CUSUM change-point detection literature). These three are
pre-declared BEFORE looking at any result, per Rule #19's Parameterized
Feature corollary -- genuinely distinct mechanics, not the same feature
re-windowed.

POPULATION: the already-frozen Cohort A (102,837 events, D3 MFE >= P95) +
matched control (same-date + same-liquidity-decile, seed=42) -- IDENTICAL
construction to 03_/05_/07_/08_/28_, reused not rebuilt. Cohort B included
for the standing A/B-separate discipline.

DECISION-TIME SAFETY: all 3 features use data up to and including T0's own
close/volume only (same convention as 28_ -- T0's own bar never enters
max_return_d3/close_ret_d3, which only use T+1..T+3, so this is not
circular with the outcome; confirmed in 01_event_matrix.py's roll/shift
logic).

NO threshold chosen, no composite, no entry construct -- distribution
comparison only, same discipline as every other precursor-discovery script
in this line.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots
from signals import atr

OUT_DIR = "swing_qs_07a"
SEED = 42

print("Reconstructing Cohort A + matched controls (identical to 03_/05_/07_/08_/28_)...", flush=True)
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
work = pd.concat([a[["ticker", "date", "group", "cohort_b", "liq_decile"]],
                    controls[["ticker", "date", "group", "cohort_b", "liq_decile"]]], ignore_index=True)
print(f"Cohort A: {len(a):,}  Controls: {len(controls):,}")

print("\nComputing the 3 pre-declared behavioural-transition features (per-ticker, decision-time-safe)...", flush=True)
CUSUM_K = 0.5       # one-sided CUSUM allowance, in standardized units -- standard default
CUSUM_WINDOW = 20    # trailing days accumulated into the statistic
BASELINE_WINDOW = 60 # historical baseline window, STALE (ends 20d before T0, not overlapping the CUSUM window)
BURST_WINDOW = 10
BURST_MULT = 1.5     # a day counts as a "burst" if |return| >= 1.5x the stock's own ATR%-implied typical move

cache = {}
rows_out = []
for n, r in enumerate(work.itertuples()):
    if n % 20000 == 0:
        print(f"  {n}/{len(work)}", flush=True)
    if r.ticker not in cache:
        try:
            idf = load(r.ticker, daily_pivots)
            idf["atr14_pct"] = atr(idf, 14) / idf.Close * 100
            idf["ret1d_pct"] = idf.Close.pct_change() * 100
            idf["vol_sma3"] = idf.Volume.rolling(3).mean()
            idf["vol_sma3_lag3"] = idf.vol_sma3.shift(3)
            baseline_mean = idf.Volume.shift(BURST_WINDOW).rolling(BASELINE_WINDOW).mean()
            baseline_std = idf.Volume.shift(BURST_WINDOW).rolling(BASELINE_WINDOW).std()
            idf["vol_z_stale"] = (idf.Volume - baseline_mean) / baseline_std
            cache[r.ticker] = idf
        except FileNotFoundError:
            cache[r.ticker] = None
    idf = cache[r.ticker]
    if idf is None or r.date not in idf.index:
        continue
    pos = idf.index.get_loc(r.date)
    if pos < BASELINE_WINDOW + BURST_WINDOW:
        continue
    row = idf.iloc[pos]

    # (1) short-term volume acceleration: last 3d avg vs the 3d avg immediately before that
    vol_accel = row.vol_sma3 / row.vol_sma3_lag3 if pd.notna(row.vol_sma3) and pd.notna(row.vol_sma3_lag3) and row.vol_sma3_lag3 else np.nan

    # (2) return-burst frequency: count of |1d return| >= BURST_MULT * that day's own ATR% in trailing 10d
    window = idf.iloc[pos - BURST_WINDOW + 1: pos + 1]
    burst_days = (window.ret1d_pct.abs() >= BURST_MULT * window.atr14_pct).sum()
    valid_days = window.ret1d_pct.notna().sum()
    burst_count = burst_days if valid_days == BURST_WINDOW else np.nan

    # (3) one-sided CUSUM of standardized volume (vs a stale, non-overlapping baseline) over trailing 20d
    z_window = idf.vol_z_stale.iloc[pos - CUSUM_WINDOW + 1: pos + 1]
    if z_window.notna().sum() == CUSUM_WINDOW:
        s = 0.0
        for z in z_window.values:
            s = max(0.0, s + z - CUSUM_K)
        cusum_stat = s
    else:
        cusum_stat = np.nan

    rows_out.append(dict(ticker=r.ticker, date=r.date, group=r.group, cohort_b=r.cohort_b, liq_decile=r.liq_decile,
                            vol_accel=vol_accel, burst_count=burst_count, cusum_stat=cusum_stat))

feats = pd.DataFrame(rows_out)
feats.to_csv(f"{OUT_DIR}/behavioral_transition_features.csv", index=False)
print(f"\n{len(feats):,} rows, saved behavioral_transition_features.csv")


def pstack(s):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return f"P25={np.percentile(s,25):.3f} P50={np.percentile(s,50):.3f} P75={np.percentile(s,75):.3f} (n={len(s):,})"


print(f"\n{'='*110}\nBEHAVIOURAL-TRANSITION FEATURES -- Cohort A vs matched control\n{'='*110}")
ca, ct = feats[feats.group == "cohort_a"], feats[feats.group == "control"]
for f in ["vol_accel", "burst_count", "cusum_stat"]:
    ca_med, ct_med = ca[f].median(), ct[f].median()
    print(f"  {f:14s} cohort_a: {pstack(ca[f]):40s}  control: {pstack(ct[f]):40s}  gap={ca_med-ct_med:+.3f}")

print(f"\n{'='*110}\nCohort B context (within the same Cohort A sample, since B is a heavily-overlapping -- 73.4% --\n"
      f"population per 07A-2B; full independent B-vs-control symmetry deferred to a follow-up if A shows signal,\n"
      f"same precedent as 07A-3 -> 07A-2B)\n{'='*110}")
cb_within_a = feats[(feats.group == "cohort_a") & feats.cohort_b]
a_not_b = feats[(feats.group == "cohort_a") & ~feats.cohort_b]
for f in ["vol_accel", "burst_count", "cusum_stat"]:
    print(f"  {f:14s} A-and-B overlap: {pstack(cb_within_a[f])}   A-only: {pstack(a_not_b[f])}")

print("\nDONE")
