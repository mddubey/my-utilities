"""RQ-QS-07A-CG3 -- Forward/Out-of-Sample Candidate Validation (2026-09-30,
critic-specified). The line crosses from "can we discover another
precursor?" to "when we freeze what we discovered and let it run forward,
does it actually surface the phenomenon?"

STRICT REQUIREMENT (critic's exact instruction, the whole point of this RQ):
the specification is frozen at the CG1 integrity-patched version. NO
recalculation, NO re-estimation, NO new percentile boundaries, NO adding
recent data to the reference population. Reuses `frozen_candidate_spec.json`
+ `frozen_sorted_arrays.npz` exactly as produced by `17_boundary_flip_audit.py`
-- imports nothing from 16_'s own (superseded) functions.

THE CLEAN OOS BOUNDARY (critic's exact framing): "the first trading date
after the CG1 freeze that was not used to establish the frozen constants."
The frozen reference population spans through 2026-09-24 -- so OOS starts
2026-09-25. Checked directly (not assumed) before building anything: the
real price cache currently has exactly THREE trading dates strictly after
2026-09-24 -- 2026-09-25, 2026-09-28, 2026-09-29. For NONE of these does a
full D1-D3 window resolve yet (2026-09-25's D3 needs the trading day after
2026-09-29, not yet cached; today is 2026-09-30, mid-session, not yet
fetched). This is disclosed honestly, not hidden -- per critic's own
framing, CG3 is meant to be an ACCUMULATING log that grows as more genuinely
unseen trading days pass, not a single complete answer today. This script is
designed to be RE-RUN as fresh data arrives (via fetch_prices.py), each time
adding newly-resolved outcomes without ever touching the frozen constants.

S PERSISTENCE LABELING (critic's explicit addition, descriptive only, never
used to filter): for every S candidate, label S_new (first S qualification
after being outside S) vs S_persistent (qualified on the previous eligible
day too). Same for W, though critic notes it will likely matter less given
W's already-established transient character (CG2: 52.7% single-day
episodes). The "previous eligible day" for the FIRST OOS date (2026-09-25)
is 2026-09-24 -- looked up from the ALREADY-COMPUTED historical `decile`
column in `trend_state_anatomy.csv` (a historical fact, not a recalculation
of the frozen constants).

UNIQUE-EPISODE COUNTING (critic's explicit requirement): report candidate-
events, unique ticker-date events, AND unique ticker-episodes separately --
S's extreme persistence (CG2: 91.9% of events in a 4+-day run) means
candidate-event counts are NOT independent-opportunity counts.

NOT built here, per critic's explicit prohibition list: W vs S winner
selection, new/persistent FILTERING, liquidity/F&O/circuit/sector filtering,
ranking, scoring, options conversion, entry/exit simulation, threshold
optimization.
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

print("Loading FROZEN spec (CG1 integrity-patched version -- no recalculation)...", flush=True)
with open(f"{OUT_DIR}/frozen_candidate_spec.json") as f:
    spec = json.load(f)
P10, P90 = spec["composite_p10_weak_state_cutoff"], spec["composite_p90_strong_state_cutoff"]
DECLINE_MEDIAN = spec["decline_from_high10d_pct_median_weak_state"]
SORTED_ARRAYS = dict(np.load(f"{OUT_DIR}/frozen_sorted_arrays.npz"))
print(f"Frozen: P10={P10:.3f}  P90={P90:.3f}  decline_median={DECLINE_MEDIAN:.3f}  "
      f"(reference population unchanged: {spec['reference_population_dates']})")


def exact_percentile_rank(value, sorted_arr):
    left = np.searchsorted(sorted_arr, value, side="left")
    right = np.searchsorted(sorted_arr, value, side="right")
    return (left + right + 1) / 2.0 / len(sorted_arr) * 100.0


def compute_composite(vals):
    ranks = [exact_percentile_rank(vals[f], SORTED_ARRAYS[f]) for f in PRIMARY]
    return float(np.mean(ranks))


print("\nDetermining the OOS window (checked directly against the real cache, not assumed)...", flush=True)
FREEZE_CUTOFF = pd.Timestamp(spec["reference_population_dates"][1])  # 2026-09-24
ref_ticker = pd.read_csv("data_cache/RELIANCE.csv", index_col="Date", parse_dates=True)
oos_dates = sorted(d for d in ref_ticker.index if d > FREEZE_CUTOFF)
print(f"OOS trading dates available right now (strictly after the {FREEZE_CUTOFF.date()} freeze): "
      f"{[d.date() for d in oos_dates]}")

print("\nLoading yesterday's (last in-sample day's) decile classification for new/persistent labeling...", flush=True)
last_insample = pd.read_csv(f"{OUT_DIR}/trend_state_anatomy.csv", parse_dates=["date"])
last_insample = last_insample[last_insample.date == FREEZE_CUTOFF][["ticker", "decile"]]
prev_day_S = set(last_insample[last_insample.decile == 9].ticker)
# For symmetry with S's definition ("remained S from the previous eligible day" = full S definition, not just
# a precursor gate), W's previous-day reference must also be the FULL 3-gate W definition on 2026-09-24, not
# just D0 membership -- weak_state_mechanism_features.csv covers the whole 5-year D0 population including this
# date, so the full historical W definition can be looked up directly rather than approximated.
mech_hist = pd.read_csv(f"{OUT_DIR}/weak_state_mechanism_features.csv", parse_dates=["date"])[
    ["ticker", "date", "ret_1d", "decline_from_high10d_pct"]]
prev_day_full = last_insample[last_insample.decile == 0].merge(
    mech_hist[mech_hist.date == FREEZE_CUTOFF][["ticker", "ret_1d", "decline_from_high10d_pct"]], on="ticker", how="inner")
prev_day_W = set(prev_day_full[(prev_day_full.decline_from_high10d_pct <= DECLINE_MEDIAN)
                                  & (prev_day_full.ret_1d >= 0)].ticker)
print(f"On the freeze date itself ({FREEZE_CUTOFF.date()}): {len(prev_day_S)} tickers were S-candidates, "
      f"{len(prev_day_W)} were full W-candidates (all 3 gates, not just the D0 precursor)")

universe = pd.read_csv("nse_equity_universe.csv").ticker.tolist()
print(f"\nComputing frozen candidate classification for all {len(universe)} universe tickers, "
      f"across {len(oos_dates)} OOS dates...", flush=True)

rows = []
for n, t in enumerate(universe):
    if n % 300 == 0:
        print(f"  {n}/{len(universe)}", flush=True)
    try:
        idf = load(t, daily_pivots)
    except FileNotFoundError:
        continue
    idx = idf.index
    for d in oos_dates:
        if d not in idx:
            continue
        row = idf.loc[d]
        pos = idx.get_loc(d)
        if pos < 252:
            continue  # can't compute dist_low252_pct etc -- same eligibility floor as the whole research line
        close = row.Close
        close_1ago = idf.Close.iloc[pos - 1]
        close_20ago = idf.Close.iloc[pos - 20] if pos >= 20 else np.nan
        high10 = idf.High.iloc[max(0, pos - 9):pos + 1].max() if pos >= 9 else np.nan
        vals = dict(
            dist_sma200_pct=(close / row.sma200 - 1) * 100 if pd.notna(row.sma200) else np.nan,
            ret_20d=(close / close_20ago - 1) * 100 if pd.notna(close_20ago) and close_20ago else np.nan,
            dist_low252_pct=(close / row.low_252 - 1) * 100 if pd.notna(row.low_252) and row.low_252 else np.nan,
            dist_ema34_pct=(close / row.ema34 - 1) * 100 if pd.notna(row.ema34) else np.nan,
            rsi14=row.rsi14,
        )
        if any(pd.isna(v) for v in vals.values()):
            continue
        composite = compute_composite(vals)
        decline_from_high10d_pct = (close / high10 - 1) * 100 if pd.notna(high10) and high10 else np.nan
        # matches 12_weak_state_mechanism.py's exact formula: (close / high10 - 1) * 100 -- distance
        # BELOW the 10-day high (a bug in an earlier draft of this script used the 10-day LOW instead,
        # which is always positive and could never satisfy the frozen negative threshold -- caught via
        # Rule #22 when is_W came back at exactly 0 across all 3 OOS dates, confirmed and fixed here).
        ret_1d = (close / close_1ago - 1) * 100 if pd.notna(close_1ago) and close_1ago else np.nan
        is_D0 = composite <= P10
        is_S = composite >= P90
        is_W = is_D0 and pd.notna(decline_from_high10d_pct) and decline_from_high10d_pct <= DECLINE_MEDIAN and ret_1d >= 0

        # forward outcome lookup -- ONLY for whatever is actually resolved in the cache right now
        outcome = {}
        for k, label in [(1, "d1"), (2, "d2"), (3, "d3")]:
            if pos + k < len(idx):
                fut_close = idf.Close.iloc[pos + k]
                fut_high = idf.High.iloc[pos + 1:pos + k + 1].max()
                fut_low = idf.Low.iloc[pos + 1:pos + k + 1].min()
                outcome[f"max_return_{label}"] = (fut_high / close - 1) * 100
                outcome[f"adverse_{label}"] = (fut_low / close - 1) * 100
                outcome[f"close_ret_{label}"] = (fut_close / close - 1) * 100
            else:
                outcome[f"max_return_{label}"] = np.nan
                outcome[f"adverse_{label}"] = np.nan
                outcome[f"close_ret_{label}"] = np.nan

        if is_S or is_W:
            rows.append(dict(ticker=t, date=d, composite=composite, decline_from_high10d_pct=decline_from_high10d_pct,
                                ret_1d=ret_1d, is_W=is_W, is_S=is_S, **outcome))

candidates = pd.DataFrame(rows)
candidates.to_csv(f"{OUT_DIR}/cg3_forward_candidates.csv", index=False)
print(f"\nSaved cg3_forward_candidates.csv ({len(candidates)} rows)")

# ---------------------------------------------------------------------------
# NEW vs PERSISTENT labeling (descriptive only, never used to filter)
# ---------------------------------------------------------------------------
print("\nLabeling S_new/S_persistent and W_new/W_persistent (previous ELIGIBLE day, not previous calendar day)...",
      flush=True)
candidates = candidates.sort_values(["ticker", "date"])
day_index = {d: i for i, d in enumerate(oos_dates)}


def label_persistence(sub_df, is_col, prev_day_seed_set):
    labels = []
    for r in sub_df.itertuples():
        di = day_index[r.date]
        if di == 0:
            was_member = r.ticker in prev_day_seed_set
        else:
            prev_date = oos_dates[di - 1]
            prev_rows = candidates[(candidates.ticker == r.ticker) & (candidates.date == prev_date)]
            was_member = bool(len(prev_rows)) and prev_rows.iloc[0][is_col]
        labels.append("persistent" if was_member else "new")
    return labels


s_candidates = candidates[candidates.is_S].copy()
w_candidates = candidates[candidates.is_W].copy()
if len(s_candidates):
    s_candidates["persistence"] = label_persistence(s_candidates, "is_S", prev_day_S)
if len(w_candidates):
    w_candidates["persistence"] = label_persistence(w_candidates, "is_W", prev_day_W)

# ---------------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------------
print(f"\n{'='*115}\nCG3 -- FORWARD CANDIDATE GENERATION on genuinely OOS dates (frozen spec, no recalculation)\n{'='*115}")
for d in oos_dates:
    w_day = w_candidates[w_candidates.date == d] if len(w_candidates) else pd.DataFrame()
    s_day = s_candidates[s_candidates.date == d] if len(s_candidates) else pd.DataFrame()
    d3_resolved = w_day.max_return_d3.notna().any() or s_day.max_return_d3.notna().any() if (len(w_day) or len(s_day)) else False
    print(f"\n{d.date()} (D3 resolved: {d3_resolved}):")
    print(f"  W candidates: {len(w_day)}  ({(w_day.persistence=='new').sum() if len(w_day) else 0} new, "
          f"{(w_day.persistence=='persistent').sum() if len(w_day) else 0} persistent)")
    print(f"  S candidates: {len(s_day)}  ({(s_day.persistence=='new').sum() if len(s_day) else 0} new, "
          f"{(s_day.persistence=='persistent').sum() if len(s_day) else 0} persistent)")
    for label, df in [("W", w_day), ("S", s_day)]:
        for k in ["d1", "d2", "d3"]:
            col = f"max_return_{k}"
            resolved = df[col].notna()
            if resolved.any():
                print(f"    {label} {k.upper()} MFE (resolved n={resolved.sum()}): "
                      f"median={df.loc[resolved, col].median():+.2f}  P90={np.percentile(df.loc[resolved, col],90):+.2f}")
            else:
                print(f"    {label} {k.upper()}: PENDING (not yet resolved in the cache)")

print(f"\n{'='*115}\nCOVERAGE -- events vs. unique ticker-dates vs. unique ticker-episodes (S persistence means these differ a lot)\n{'='*115}")
for label, df in [("W", w_candidates), ("S", s_candidates)]:
    if not len(df):
        print(f"  {label}: no candidates in this OOS window")
        continue
    n_events = len(df)
    n_unique_ticker_dates = df[["ticker", "date"]].drop_duplicates().shape[0]  # == n_events, by construction (1 row/ticker/date)
    n_unique_tickers = df.ticker.nunique()
    n_new_episodes = (df.persistence == "new").sum()  # a "new" qualification starts an episode
    print(f"  {label}: {n_events} candidate-events, {n_unique_ticker_dates} unique ticker-date events "
          f"(identical here -- one row per ticker per date by construction), {n_unique_tickers} unique tickers, "
          f"{n_new_episodes} new episode-starts (vs. {n_events - n_new_episodes} persistent continuations) -- "
          f"do NOT read {n_events} as {n_events} independent opportunities.")

print("\nNOTE: this is a THREE-DAY snapshot of an experiment designed to accumulate. Re-run this script "
      "after fetch_prices.py brings in fresh trading days -- every additional day both extends the OOS "
      "candidate window AND resolves more D1-D3 outcomes for the dates already generated above. The frozen "
      "spec (P10/P90/decline_median/sorted arrays) must never be touched as this accumulates.")

print("\nDONE")
