"""RQ-QS-07A-BT1-S -- Does the BT1 behavioural-transition signal add real
separation WITHIN the already-frozen S (strong-state) population? (2026-10-02,
user-directed follow-up to BT1.)

WHY: BT1 (29_behavioral_transition_discovery.py) found that volume
acceleration/burst-clustering/CUSUM regime-shift all separate Cohort A from
control, and that this separation correlates moderately (Spearman 0.16-0.26)
with prior 3-day strength -- closer to S's territory than W's, but not a
duplicate. S never got its own standalone entry construct built (only
grafted onto QS-A, where it failed OOS -- P3-P6, closed, QS-A-compatibility-
specific). This script asks the narrower, pre-entry-construct question:
AMONG DAYS ALREADY CLASSIFIED AS S, does a higher BT1 reading mark out a
subset with a measurably better forward outcome than low-BT1 S days? If not,
there is no point building an S+BT1 entry. If yes, that's the first real
justification for attempting one.

FROZEN SPEC REUSED EXACTLY, NO RECALCULATION (same discipline as
19_forward_validation_cg3.py): `frozen_candidate_spec.json` +
`frozen_sorted_arrays.npz`, produced by `17_boundary_flip_audit.py`. S is
classified on T0's own row -- SAME historical-characterization clock CG2
(18_candidate_population_evaluation.py) already used for S's own coverage/
incidence findings. This is NOT a live-decision clock (Rule #18 applies to a
live production gate, not to characterizing an already-frozen state's own
distribution) -- flagged explicitly, not glossed over.

POPULATION: full NSE universe (`nse_equity_universe.csv`, 2,327 tickers),
same eligibility as `01_event_matrix.py` (>=252d history for the composite
inputs, T not a corp_action_day, clean T+1..T+3 forward window) -- NOT
restricted to Cohort A/B membership, since S is its own population,
independent of whether a given S day happened to also land in the top-5%-
move cohort.

OUTCOME METRICS: max_return_d3 (opportunity/MFE) and close_ret_d3
(sustained/realized-if-held-to-close) -- the SAME two metrics CG2 already
used to characterize S by itself, no new outcome definition, no stop/R yet
(none exists for a standalone S construct -- Rule #20 applies once R-based
analysis starts, not to this raw-outcome characterization step, matching
CG2's own precedent).

BT1 FEATURES: identical formulas to `29_behavioral_transition_discovery.py`
(vol_accel, burst_count, cusum_stat) -- computed ONLY for rows already
classified is_S==True, since that is the only subset this question is about
(computing BT1 for the full 1.66M-row universe would be wasted work -- is_S
is cheap/vectorized and computed for everyone first, BT1's per-row CUSUM
loop runs only on the ~10% that pass).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import json
import numpy as np
import pandas as pd
from backtest import load, daily_pivots
from signals import atr

OUT_DIR = "swing_qs_07a"
PRIMARY = ["dist_sma200_pct", "ret_20d", "dist_low252_pct", "dist_ema34_pct", "rsi14"]
CUSUM_K = 0.5
CUSUM_WINDOW = 20
BASELINE_WINDOW = 60
BURST_WINDOW = 10
BURST_MULT = 1.5

print("Loading FROZEN spec (same as CG3/19_, no recalculation)...", flush=True)
with open(f"{OUT_DIR}/frozen_candidate_spec.json") as f:
    spec = json.load(f)
P90 = spec["composite_p90_strong_state_cutoff"]
SORTED_ARRAYS = dict(np.load(f"{OUT_DIR}/frozen_sorted_arrays.npz"))
print(f"Frozen: P90(S cutoff)={P90:.3f}")


def exact_percentile_rank_vec(values, sorted_arr):
    left = np.searchsorted(sorted_arr, values, side="left")
    right = np.searchsorted(sorted_arr, values, side="right")
    return (left + right + 1) / 2.0 / len(sorted_arr) * 100.0


uni = pd.read_csv("nse_equity_universe.csv")
tickers = uni.ticker.tolist()
print(f"Universe: {len(tickers)} tickers", flush=True)

rows_out = []
for n, t in enumerate(tickers):
    if n % 200 == 0:
        print(f"{n}/{len(tickers)}  ({len(rows_out):,} S-rows so far)", flush=True)
    try:
        idf = load(t, daily_pivots)
    except FileNotFoundError:
        continue
    N = len(idf)
    if N < 252 + 4:
        continue

    close = idf.Close
    close_20ago = close.shift(20)
    dist_sma200_pct = (close / idf.sma200 - 1) * 100
    ret_20d = (close / close_20ago - 1) * 100
    dist_low252_pct = (close / idf.low_252 - 1) * 100
    dist_ema34_pct = (close / idf.ema34 - 1) * 100
    rsi14 = idf.rsi14

    valid = dist_sma200_pct.notna() & ret_20d.notna() & dist_low252_pct.notna() & dist_ema34_pct.notna() & rsi14.notna()
    valid &= (np.arange(N) >= 252) & (np.arange(N) <= N - 4) & ~idf.corp_action_day.astype(bool)
    corp1 = idf.corp_action_day.shift(-1).fillna(True).astype(bool)
    corp2 = idf.corp_action_day.shift(-2).fillna(True).astype(bool)
    corp3 = idf.corp_action_day.shift(-3).fillna(True).astype(bool)
    valid &= ~corp1 & ~corp2 & ~corp3

    vals = pd.DataFrame({"dist_sma200_pct": dist_sma200_pct, "ret_20d": ret_20d,
                           "dist_low252_pct": dist_low252_pct, "dist_ema34_pct": dist_ema34_pct, "rsi14": rsi14})
    composite = pd.Series(np.nan, index=idf.index)
    idx_valid = vals.index[valid]
    if len(idx_valid) == 0:
        continue
    rank_sum = np.zeros(len(idx_valid))
    for f in PRIMARY:
        rank_sum += exact_percentile_rank_vec(vals.loc[idx_valid, f].values, SORTED_ARRAYS[f])
    composite.loc[idx_valid] = rank_sum / len(PRIMARY)

    is_S = valid & (composite >= P90)
    if not is_S.any():
        continue

    high1, high2, high3 = idf.High.shift(-1), idf.High.shift(-2), idf.High.shift(-3)
    low1, low2, low3 = idf.Low.shift(-1), idf.Low.shift(-2), idf.Low.shift(-3)
    close1, close2, close3 = idf.Close.shift(-1), idf.Close.shift(-2), idf.Close.shift(-3)
    max_h_d3 = pd.concat([high1, high2, high3], axis=1).max(axis=1)
    max_return_d3 = (max_h_d3 / close - 1) * 100
    close_ret_d3 = (close3 / close - 1) * 100

    atr14_pct = atr(idf, 14) / idf.Close * 100
    ret1d_pct = idf.Close.pct_change() * 100
    vol_sma3 = idf.Volume.rolling(3).mean()
    vol_sma3_lag3 = vol_sma3.shift(3)
    baseline_mean = idf.Volume.shift(BURST_WINDOW).rolling(BASELINE_WINDOW).mean()
    baseline_std = idf.Volume.shift(BURST_WINDOW).rolling(BASELINE_WINDOW).std()
    vol_z_stale = (idf.Volume - baseline_mean) / baseline_std

    s_positions = np.where(is_S.values)[0]
    for pos in s_positions:
        if pos < BASELINE_WINDOW + BURST_WINDOW:
            continue
        vol_accel = vol_sma3.iloc[pos] / vol_sma3_lag3.iloc[pos] if pd.notna(vol_sma3.iloc[pos]) and pd.notna(vol_sma3_lag3.iloc[pos]) and vol_sma3_lag3.iloc[pos] else np.nan

        win = slice(pos - BURST_WINDOW + 1, pos + 1)
        ret_win, atr_win = ret1d_pct.iloc[win], atr14_pct.iloc[win]
        if ret_win.notna().sum() == BURST_WINDOW:
            burst_count = (ret_win.abs() >= BURST_MULT * atr_win).sum()
        else:
            burst_count = np.nan

        z_win = vol_z_stale.iloc[pos - CUSUM_WINDOW + 1: pos + 1]
        if z_win.notna().sum() == CUSUM_WINDOW:
            s_acc = 0.0
            for z in z_win.values:
                s_acc = max(0.0, s_acc + z - CUSUM_K)
            cusum_stat = s_acc
        else:
            cusum_stat = np.nan

        rows_out.append(dict(
            ticker=t, date=idf.index[pos], composite=composite.iloc[pos],
            max_return_d3=max_return_d3.iloc[pos], close_ret_d3=close_ret_d3.iloc[pos],
            vol_accel=vol_accel, burst_count=burst_count, cusum_stat=cusum_stat,
        ))

feats = pd.DataFrame(rows_out)
feats.to_csv(f"{OUT_DIR}/s_bt1_combo.csv", index=False)
print(f"\n{len(feats):,} S-classified rows, saved s_bt1_combo.csv")

print(f"\n{'='*110}\nBASELINE -- all S rows, regardless of BT1 reading\n{'='*110}")
print(f"  n={len(feats):,}  max_return_d3 median={feats.max_return_d3.median():.3f}%  "
      f"close_ret_d3 median={feats.close_ret_d3.median():.3f}%")

print(f"\n{'='*110}\nS split by BT1 features -- does a higher BT1 reading mark a better subset of S?\n{'='*110}")
for f, lo_label, hi_label in [("burst_count", "0", ">=1"), ("cusum_stat", "==0", ">0")]:
    d = feats.dropna(subset=[f])
    lo = d[d[f] == 0]
    hi = d[d[f] > 0]
    print(f"\n  Split on {f} ({lo_label} vs {hi_label}):")
    print(f"    LOW  (n={len(lo):,}): max_return_d3 median={lo.max_return_d3.median():.3f}%  close_ret_d3 median={lo.close_ret_d3.median():.3f}%")
    print(f"    HIGH (n={len(hi):,}): max_return_d3 median={hi.max_return_d3.median():.3f}%  close_ret_d3 median={hi.close_ret_d3.median():.3f}%")

d = feats.dropna(subset=["vol_accel"])
d["accel_q"] = pd.qcut(d.vol_accel.rank(method="first"), 4, labels=["Q1(low)", "Q2", "Q3", "Q4(high)"])
print(f"\n  Split on vol_accel quartile:")
print(d.groupby("accel_q", observed=True)[["max_return_d3", "close_ret_d3"]].median())
print(d.groupby("accel_q", observed=True).size())

print("\nDONE")
