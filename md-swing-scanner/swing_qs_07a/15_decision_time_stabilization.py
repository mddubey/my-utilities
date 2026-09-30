"""RQ-QS-07A-6U -- Decision-Time Stabilization Test (2026-09-30, critic-specified).

The first genuinely "can we use it" RQ in this line, after five "is this
pattern real" RQs (07A-5, 07A-5R, 07A-6, 07A-6R, 07A-6T). Primary question
(critic's exact wording): "Within frozen D0, can eventual fast movers be
distinguished from ordinary D0 names using only information available at the
candidate decision time?"

Frozen, no new cohort definitions: D0_A (eventual D3-MFE fast movers),
D0_ordinary (ALL remaining D0 events, not filtered), D2_A as secondary
reference only (not used below -- this pass is about D0_A vs D0_ordinary
information content, D2_A adds nothing to that specific question).

TWO DISTINCT NOTIONS OF "T INFORMATION" (critic's explicit framing, both
tested separately, never conflated):
  Level 1 -- T CLOSE: T's full realized day (close, range, volume) -- tells
    us whether the phenomenon is observable AT ALL, but may be too late for
    QS-A's actual intraday-breach entry architecture.
  Level 2 -- PRE-CLOSE / EARLY-SESSION: only information available before or
    at an early point in T's own session -- the real actionability question.
    Severely data-constrained: real 5-min intraday cache only covers
    2026-06-10 to 2026-09-23 (~3.5 months, 500 tickers) -- a tiny fraction of
    D0's 5-year population (2255 of 166,831 D0 events fall in this window
    with a cached ticker, 42 of which are Cohort A). Part B below is
    EXPLICITLY an exploratory side-check on that tiny slice, never a
    population-wide finding -- same disclosed-limitation convention already
    used for the hourly-pivot check in 06_pivot_distance_features.py.

PART A -- T-CLOSE FEASIBILITY CEILING (full 166,831-row D0 population, no
intraday needed): uses ONLY already-existing variables from 06/06R/06T
(`decline_from_high10d_pct`, `ret_3d`, `dist_low10d_pct`, `ret_1d`,
`close_loc_pct`, `lower_wick_pct`) -- no new TA indicators. Per critic's
explicit instruction, this is NOT another round of univariate median gaps
(already done in 07A-6) -- it tests JOINT separation via natural,
NON-ARBITRARY splits (no fitted/optimized threshold): each continuous
variable is split at D0's OWN median (a population-intrinsic reference
point, same "empirical, not chosen" logic as using D2 as a reference decile
rather than an arbitrary one), and `ret_1d` is split at its natural
zero-crossing (green vs. red day -- zero is not a fitted number). This
directly instantiates critic's own example: "sharp deterioration + no
further deterioration at T" (deep decline AND ret_1d>=0) vs. "sharp
deterioration + still deteriorating at T" (deep decline AND ret_1d<0).

PART B -- EARLIEST-AVAILABLE-INFORMATION SIDE-CHECK (small sample, honestly
disclosed): for the 2255 D0 events with real intraday coverage, compares the
FIRST HOUR of trading (09:15-10:15 IST) against the full day's close -- does
the eventual T-close direction already show up an hour into the session?
Chosen because no QS-A-specific "breach" rule exists yet for this pathway
(critic's own architecture-decision is still parked) -- the first hour is a
non-arbitrary, natural anchor (a fixed calendar convention, not a fitted
cutoff), not a stand-in for an actual entry rule.

No new features anywhere. No threshold optimization. No composite score. No
strategy simulation. No candidate-generation freeze -- per critic's explicit
guardrail, that only happens after establishing (1) whether stabilization is
visible at T-close, (2) whether it's visible before/at an actual entry
decision, (3) how much information is lost moving earlier.
"""
import pandas as pd
import numpy as np
import glob
import os

OUT_DIR = "."

print("PART A -- loading full D0 population (T-close feasibility ceiling)...", flush=True)
state = pd.read_csv("trend_state_anatomy.csv", parse_dates=["date"])
mech = pd.read_csv("weak_state_mechanism_features.csv", parse_dates=["date"])[
    ["ticker", "date", "ret_1d", "ret_3d", "dist_low10d_pct", "decline_from_high10d_pct",
     "close_loc_pct", "lower_wick_pct"]]
d0 = state[state.decile == 0].merge(mech, on=["ticker", "date"], how="inner")
assert len(d0) == (state.decile == 0).sum()
print(f"D0 population: {len(d0):,}  Cohort A: {d0.cohort_a.sum():,} ({d0.cohort_a.mean()*100:.2f}%)")


def joint_table(df, split_col, split_label):
    med = df[split_col].median()
    deep = df[split_col] < med  # more negative = deeper decline / more negative return
    green = df.ret_1d >= 0
    rows = []
    for deep_val, deep_name in [(True, f"below-median ({split_label}, deeper/more-negative)"),
                                   (False, f"above-median ({split_label}, shallower)")]:
        for green_val, green_name in [(True, "T green (ret_1d>=0)"), (False, "T red (ret_1d<0)")]:
            cell = df[(deep == deep_val) & (green == green_val)]
            rows.append(dict(split_var=split_label, dimension1=deep_name, dimension2=green_name,
                                n=len(cell), pct_cohort_a=round(cell.cohort_a.mean() * 100, 2),
                                pct_cohort_b=round(cell.cohort_b.mean() * 100, 2)))
    # marginals for comparison -- does the joint cell beat either single dimension alone?
    rows.append(dict(split_var=split_label, dimension1="MARGINAL: below-median only", dimension2="(any T direction)",
                        n=deep.sum(), pct_cohort_a=round(df[deep].cohort_a.mean() * 100, 2),
                        pct_cohort_b=round(df[deep].cohort_b.mean() * 100, 2)))
    rows.append(dict(split_var=split_label, dimension1="(any decline depth)", dimension2="MARGINAL: T green only",
                        n=green.sum(), pct_cohort_a=round(df[green].cohort_a.mean() * 100, 2),
                        pct_cohort_b=round(df[green].cohort_b.mean() * 100, 2)))
    return pd.DataFrame(rows)


print(f"\n{'='*120}\nPART A -- JOINT SEPARATION at T-close (natural splits: population median, ret_1d sign -- no fitted threshold)\n{'='*120}")
t1 = joint_table(d0, "decline_from_high10d_pct", "decline_from_high10d_pct")
t2 = joint_table(d0, "ret_3d", "ret_3d")
joint_all = pd.concat([t1, t2], ignore_index=True)
print(joint_all.to_string(index=False))
joint_all.to_csv(f"{OUT_DIR}/decision_time_joint_separation.csv", index=False)

print(f"\n{'='*120}\nPART B -- EARLIEST-AVAILABLE-INFORMATION SIDE-CHECK (SMALL SAMPLE, exploratory only -- "
      f"real intraday cache covers only 2026-06-10 to 2026-09-23, ~3.5 months of D0's 5-year population)\n{'='*120}")

intraday_tickers = set(os.path.basename(f)[:-4] for f in glob.glob("../intraday_cache/*.csv"))
WINDOW_START, WINDOW_END = pd.Timestamp("2026-06-10"), pd.Timestamp("2026-09-23")
window = d0[(d0.date >= WINDOW_START) & (d0.date <= WINDOW_END) & (d0.ticker.isin(intraday_tickers))].copy()
print(f"D0 events falling inside the real intraday window with a cached ticker: {len(window):,} of {len(d0):,} "
      f"({len(window)/len(d0)*100:.2f}%) -- Cohort A: {window.cohort_a.sum()} -- "
      f"TOO SMALL for a population-wide finding, reported as an exploratory side-check only.")

print("Extracting first-hour (09:15-10:15 IST = 03:45-04:45 UTC) return for each event...", flush=True)
cache = {}
first_hour_rets = []
for r in window.itertuples():
    if r.ticker not in cache:
        idf = pd.read_csv(f"../intraday_cache/{r.ticker}.csv", parse_dates=["Datetime"])
        idf["date_ist"] = (idf.Datetime + pd.Timedelta(hours=5, minutes=30)).dt.date
        cache[r.ticker] = idf
    idf = cache[r.ticker]
    day_bars = idf[idf.date_ist == r.date.date()]
    if day_bars.empty:
        first_hour_rets.append(np.nan)
        continue
    prior_close = r.close / (1 + r.ret_1d / 100) if pd.notna(r.ret_1d) else np.nan
    first_hour_bars = day_bars[day_bars.Datetime <= day_bars.Datetime.min() + pd.Timedelta(hours=1)]
    if first_hour_bars.empty or pd.isna(prior_close) or prior_close == 0:
        first_hour_rets.append(np.nan)
        continue
    first_hour_close = first_hour_bars.iloc[-1].Close
    first_hour_rets.append((first_hour_close / prior_close - 1) * 100)

window["first_hour_ret"] = first_hour_rets
valid = window.dropna(subset=["first_hour_ret", "ret_1d"])
print(f"Valid first-hour extractions: {len(valid):,} of {len(window):,}")

for cohort_col, cohort_label in [("cohort_a", "Cohort A"), ("cohort_b", "Cohort B")]:
    fast = valid[valid[cohort_col]]
    ordinary = valid[~valid[cohort_col]]
    print(f"\n-- {cohort_label} (n={len(fast)}) vs ordinary (n={len(ordinary)}), intraday-window subset only --")
    for label, sub in [(f"{cohort_label} fast movers", fast), ("ordinary (same window)", ordinary)]:
        if len(sub) == 0:
            print(f"  {label}: n=0")
            continue
        sign_agree = ((sub.first_hour_ret >= 0) == (sub.ret_1d >= 0)).mean() * 100
        print(f"  {label}: n={len(sub)}  median first_hour_ret={sub.first_hour_ret.median():+.2f}%  "
              f"median full_day ret_1d={sub.ret_1d.median():+.2f}%  "
              f"sign-agreement (first-hour vs full-day)={sign_agree:.1f}%")
    if len(fast) >= 10:
        fh_green = valid[valid.first_hour_ret >= 0]
        fh_red = valid[valid.first_hour_ret < 0]
        print(f"  Within this window: %{cohort_label} when first-hour green: "
              f"{fh_green[cohort_col].mean()*100:.2f}% (n={len(fh_green)})   "
              f"%{cohort_label} when first-hour red: {fh_red[cohort_col].mean()*100:.2f}% (n={len(fh_red)})")
    else:
        print(f"  n={len(fast)} too small (<10) for a first-hour-green/red split -- not reported, low-n/indeterminate.")

window.to_csv(f"{OUT_DIR}/decision_time_intraday_sidecheck.csv", index=False)

print("\nDONE")
