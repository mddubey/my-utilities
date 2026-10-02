"""RQ-QS-07A-SST1-R1 -- Freshness mechanism/overlap audit (2026-10-02,
critic-specified, exact next action after SST1's clean discovery pass).

QUESTION (critic's exact framing): is "freshly entering the strong state"
(run_age=1) a genuinely new precursor, or is it mostly a disguised version
of the already-discovered weak-state/recovery phenomenon (W)? A stock going
weak -> recovering -> strong would be classified "freshly strong" today,
but we already know recovering-from-weakness can produce a large move --
that would mean SST1's freshness result is a rediscovery, not new
information.

NOT ALLOWED (critic's explicit list, carried forward): no threshold tuning,
no new composite, no entry rule, no stop, no liquidity rescue. This script
answers ONE question -- does freshness survive once the W-overlap is
accounted for -- not "which combination has the highest return."

METHOD: for every run_age=1 ("fresh") and run_age>=8 ("established") event
from `sst1_freshness_features.csv`, check whether the ticker was classified
W (`is_W`, the exact frozen spec formula from 19_/30_ -- composite<=P10 AND
decline_from_high10d_pct<=DECLINE_MEDIAN AND ret_1d>=0) at ANY point in the
20 trading days strictly BEFORE the event day (a 10-day window checked
alongside as a robustness cross-check, not a tuned choice). Report: (1) the
overlap rate for fresh vs. established, (2) the forward outcome
(max_return_d3/close_ret_d3) split by overlap/non-overlap within fresh,
compared against established as the baseline, (3) the basic acceleration
relationship (delta_5d/10d, already computed in `sst1_acceleration_
features.csv`) by overlap/non-overlap, descriptively only -- NOT a
combination to optimize, and (4) a year-level sanity check on the key
split if it shows a meaningful pattern.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import json
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"
PRIMARY = ["dist_sma200_pct", "ret_20d", "dist_low252_pct", "dist_ema34_pct", "rsi14"]
LOOKBACK_WINDOWS = [20, 10]

print("Loading FROZEN spec (same as CG3/19_/30_/34_, no recalculation)...", flush=True)
with open(f"{OUT_DIR}/frozen_candidate_spec.json") as f:
    spec = json.load(f)
P10 = spec["composite_p10_weak_state_cutoff"]
P90 = spec["composite_p90_strong_state_cutoff"]
DECLINE_MEDIAN = spec["decline_from_high10d_pct_median_weak_state"]
SORTED_ARRAYS = dict(np.load(f"{OUT_DIR}/frozen_sorted_arrays.npz"))


def exact_percentile_rank_vec(values, sorted_arr):
    left = np.searchsorted(sorted_arr, values, side="left")
    right = np.searchsorted(sorted_arr, values, side="right")
    return (left + right + 1) / 2.0 / len(sorted_arr) * 100.0


def composite_series(idf):
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


print("Loading SST1 freshness population (fresh=run_age==1, established=run_age>=8)...", flush=True)
feats_b = pd.read_csv(f"{OUT_DIR}/sst1_freshness_features.csv", parse_dates=["date"])
target = feats_b[(feats_b.run_age == 1) | (feats_b.run_age >= 8)].copy()
target["bucket"] = np.where(target.run_age == 1, "fresh", "established")
print(f"fresh: {(target.bucket=='fresh').sum():,}  established: {(target.bucket=='established').sum():,}")

grouped = dict(tuple(target.groupby("ticker")))
rows_out = []
for n, t in enumerate(grouped):
    if n % 300 == 0:
        print(f"  {n}/{len(grouped)} tickers", flush=True)
    idf = load(t, daily_pivots)
    comp = composite_series(idf)
    is_D0 = comp <= P10
    high10 = idf.High.rolling(10).max()
    decline_from_high10d_pct = (idf.Close / high10 - 1) * 100
    ret_1d = idf.Close.pct_change() * 100
    is_W = is_D0 & (decline_from_high10d_pct <= DECLINE_MEDIAN) & (ret_1d >= 0)

    sub = grouped[t]
    for r in sub.itertuples():
        if r.date not in idf.index:
            continue
        pos = idf.index.get_loc(r.date)
        result = dict(ticker=t, date=r.date, bucket=r.bucket, run_age=r.run_age,
                       max_return_d3=r.max_return_d3, close_ret_d3=r.close_ret_d3)
        for win in LOOKBACK_WINDOWS:
            lo = max(0, pos - win)
            window_is_W = is_W.iloc[lo:pos]  # strictly BEFORE the event day
            result[f"overlap_w_{win}d"] = bool(window_is_W.any()) if len(window_is_W) > 0 else False
        rows_out.append(result)

out = pd.DataFrame(rows_out)
out.to_csv(f"{OUT_DIR}/sst1_freshness_overlap.csv", index=False)
print(f"\n{len(out):,} rows, saved sst1_freshness_overlap.csv")

print(f"\n{'='*110}\n(1) OVERLAP RATE -- was this ticker W at any point in the lookback window?\n{'='*110}")
for win in LOOKBACK_WINDOWS:
    col = f"overlap_w_{win}d"
    print(f"  {win}d lookback:  fresh overlap rate = {out[out.bucket=='fresh'][col].mean()*100:.1f}%   "
          f"established overlap rate = {out[out.bucket=='established'][col].mean()*100:.1f}%")

print(f"\n{'='*110}\n(2) FORWARD OUTCOME -- fresh split by overlap, vs established baseline (20d lookback)\n{'='*110}")
fresh = out[out.bucket == "fresh"]
established = out[out.bucket == "established"]
fresh_overlap = fresh[fresh.overlap_w_20d]
fresh_nonoverlap = fresh[~fresh.overlap_w_20d]
for label, grp in [("established (baseline)", established), ("fresh - OVERLAP w/ W", fresh_overlap),
                     ("fresh - NO overlap w/ W", fresh_nonoverlap)]:
    print(f"  {label:26s} n={len(grp):6,}  max_return_d3 median={grp.max_return_d3.median():+.3f}%  "
          f"close_ret_d3 median={grp.close_ret_d3.median():+.3f}%")

print(f"\n{'='*110}\n(3) Acceleration relationship (descriptive only, from sst1_acceleration_features.csv)\n{'='*110}")
accel = pd.read_csv(f"{OUT_DIR}/sst1_acceleration_features.csv", parse_dates=["date"])
merged = out.merge(accel[["ticker", "date", "delta_5d", "delta_10d"]], on=["ticker", "date"], how="left")
for label, grp in [("fresh - OVERLAP w/ W", merged[(merged.bucket=="fresh") & merged.overlap_w_20d]),
                     ("fresh - NO overlap w/ W", merged[(merged.bucket=="fresh") & ~merged.overlap_w_20d]),
                     ("established", merged[merged.bucket=="established"])]:
    d5 = grp.delta_5d.dropna()
    print(f"  {label:26s} n(matched)={len(d5):6,}  delta_5d median={d5.median():+.2f}" if len(d5) else f"  {label}: n=0")

print(f"\n{'='*110}\n(4) Year-level check, fresh split by overlap (20d lookback)\n{'='*110}")
fresh = fresh.copy()
fresh["year"] = fresh.date.dt.year
for y in sorted(fresh.year.unique()):
    sub = fresh[fresh.year == y]
    ov, non = sub[sub.overlap_w_20d], sub[~sub.overlap_w_20d]
    if len(ov) < 100 or len(non) < 100:
        continue
    print(f"  {y}: OVERLAP n={len(ov):5,} med={ov.max_return_d3.median():+.2f}%   "
          f"NO-OVERLAP n={len(non):5,} med={non.max_return_d3.median():+.2f}%")

print("\nDONE")
