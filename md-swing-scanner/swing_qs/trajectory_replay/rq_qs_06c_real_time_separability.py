"""RQ-QS-06C -- Real-Time Archetype Separability Audit (2026-09-29, critic-specified).

Question (critic's exact framing): "At the moment a QS-A trade has demonstrated
meaningful favorable excursion, is there already enough information in its
trajectory to distinguish future burst/exhaustion from future persistent
continuation?" NOT "what should we exit at" -- no intervention, no threshold
optimization, no exit rule anywhere in this script.

METHODOLOGICAL DISCIPLINE, per critic's explicit instruction: outcome labels (the
06B archetypes) are FUTURE TRUTH, used only to evaluate separability after the fact.
Predictors are information CENSORED at each observation landmark -- computed using
ONLY days up to and including the landmark day, never anything from after it.

LABEL-LEAKAGE AUDIT (done explicitly, before building anything, not assumed):
burst_then_exhaustion is defined by (reaches >=1.5R at some point) AND (eventual
exit R <= 50% of the eventual 15D peak). persistent_continuation is defined by
(gaps between consecutively-touched levels <=3 days) AND (eventual exit R >=50% of
its own 15D peak). BOTH definitions use the FINAL/eventual exit R and the FINAL/
eventual 15D peak -- neither definition is a function of the close on the specific
day a landmark is first touched. The predictors below (peak_retention_at_landmark,
is_new_closing_high_at_landmark, days_to_landmark, trailing persistence) are all
computed strictly from days <= the landmark day and do not reference exit_r or
max_r_15d at all. No predictor here is mathematically part of either archetype's
own definition -- confirmed by inspection of rq_qs_06b's archetype-assignment code
before writing this script, not asserted without checking.

Reuses `walk_full()` from `rq_qs_06b_favorable_state_trajectory.py` VERBATIM
(imported, not reimplemented) for the day-by-day walk. Joins the already-computed
archetype labels from `rq_qs_06b_state_trajectory.csv` -- not re-derived.

Landmarks: first +0.5R, +0.75R, +1.0R, +1.5R, +2.0R (not proposed exit thresholds --
observation points only, matching 06B's own R_LEVELS minus 0.25R, which critic's
message doesn't list as a landmark).

Predictors at each landmark (deliberately small, per critic's explicit preference):
  days_to_landmark        -- how many days it took to first reach this level
  close_r_at_landmark     -- today's close-R
  peak_retention          -- close_r_at_landmark / running_mfe_at_landmark (how much
                              of the excursion is still being held right now)
  is_new_closing_high     -- is today's close the highest CLOSE of the trade so far
                              (decision-time-safe: compares only to PRIOR days)
  trailing_persist_3d     -- of the up-to-3 days ending at the landmark (inclusive),
                              how many closed at/above half the running peak AS OF
                              THAT DAY -- a short, already-decision-time-safe
                              "is this holding up" measure, not a future giveback
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib.util import spec_from_file_location, module_from_spec
_spec = spec_from_file_location("rq_qs_06b", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rq_qs_06b_favorable_state_trajectory.py"))
rq_qs_06b = module_from_spec(_spec)
_spec.loader.exec_module(rq_qs_06b)
walk_full = rq_qs_06b.walk_full

from backtest import load
from pivots import daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LANDMARKS = [0.5, 0.75, 1.0, 1.5, 2.0]
PRIMARY = ["burst_then_exhaustion", "persistent_continuation"]


def landmark_predictors(days, level):
    """days: full day-by-day list from walk_full(). Returns None if this level is
    never reached, else the predictor dict computed using ONLY days <= landmark."""
    hit = next((d for d in days if d["mfe_so_far"] >= level), None)
    if hit is None:
        return None
    d0 = hit["day"]
    censored = [d for d in days if d["day"] <= d0]  # strictly <=landmark, decision-time-safe
    close0 = hit["close_r"]
    mfe0 = hit["mfe_so_far"]
    prior_closes = [d["close_r"] for d in censored if d["day"] < d0]
    is_new_closing_high = bool(not prior_closes or close0 > max(prior_closes))
    trailing = [d for d in censored if d["day"] > d0 - 3]  # up to 3 days ending at landmark, inclusive
    trailing_persist = sum(1 for d in trailing if d["close_r"] >= d["mfe_so_far"] / 2 if d["mfe_so_far"] > 0)
    return dict(
        days_to_landmark=d0,
        close_r_at_landmark=close0,
        peak_retention=(close0 / mfe0) if mfe0 else None,
        is_new_closing_high=is_new_closing_high,
        trailing_persist_3d=trailing_persist,
        trailing_persist_3d_n=len(trailing),
    )


if __name__ == "__main__":
    # Rule #22: (ticker, entry_date) is NOT a unique key -- the same ticker/date can
    # legitimately trigger under more than one lookback (10D/20D/40D) simultaneously
    # (confirmed: 46,613 rows but only 30,374 unique (ticker,entry_date) pairs, up to
    # 3x duplication). A merge on (ticker, entry_date) alone produces a cross-product
    # within each duplicated group -- caught this BEFORE trusting a first run that
    # silently inflated 46,613 -> 89,097 rows (more than either input, the exact
    # mathematically-impossible-for-an-inner-join signal Rule #22 names explicitly).
    # entry_definition is required as a join key to disambiguate.
    labels = pd.read_csv("swing_qs/trajectory_replay/rq_qs_06b_state_trajectory.csv")[
        ["ticker", "entry_date", "entry_definition", "archetype", "eventual_exit_r", "eventual_max_r_15d"]]
    env = pd.read_csv("swing_qs/trajectory_replay/rq_qs_06_envelope.csv")
    src = env.merge(labels, on=["ticker", "entry_date", "entry_definition"], how="inner")
    assert len(src) == len(env), f"join still not 1:1: {len(src)} vs {len(env)}"
    src["entry_date"] = pd.to_datetime(src.entry_date)
    print(f"{len(src)} trades with archetype labels")

    cache = {}
    recs = []
    for n, r in enumerate(src.itertuples()):
        if n % 5000 == 0:
            print(f"{n}/{len(src)}", flush=True)
        rows = cache.setdefault(r.ticker, load(r.ticker, daily_pivots).reset_index())
        m = rows.index[rows.Date == r.entry_date]
        if len(m) == 0:
            continue
        entry_i = m[0]
        days, exit_reason, exit_day = walk_full(rows, entry_i, r.entry_price, r.initial_risk_pct)
        if not days:
            continue
        for level in LANDMARKS:
            pred = landmark_predictors(days, level)
            if pred is None:
                continue
            rec = dict(ticker=r.ticker, entry_date=r.entry_date.date(), level=level,
                        archetype=r.archetype, eventual_exit_r=r.eventual_exit_r,
                        eventual_max_r_15d=r.eventual_max_r_15d)
            rec.update(pred)
            recs.append(rec)

    df = pd.DataFrame(recs)
    df.to_csv(f"{OUT_DIR}/rq_qs_06c_separability.csv", index=False)
    print(f"\n{len(df)} landmark-observations across {df[['ticker','entry_date']].drop_duplicates().shape[0]} trades\n")

    prim = df[df.archetype.isin(PRIMARY)]
    print(f"Primary comparison population (burst_then_exhaustion vs persistent_continuation): n={len(prim)} observations\n")

    def pstack(s, fmt="{:.2f}"):
        s = pd.Series(s).dropna()
        if len(s) == 0:
            return "n=0"
        return f"P25={fmt.format(np.percentile(s,25))} P50={fmt.format(np.percentile(s,50))} P75={fmt.format(np.percentile(s,75))} (n={len(s)})"

    print("=" * 100)
    print("SEPARABILITY TIMELINE -- at each landmark, burst_then_exhaustion vs persistent_continuation")
    print("=" * 100)
    for level in LANDMARKS:
        sub = prim[prim.level == level]
        b = sub[sub.archetype == "burst_then_exhaustion"]
        p = sub[sub.archetype == "persistent_continuation"]
        print(f"\n--- Landmark: first +{level}R  (burst n={len(b)}, persistent n={len(p)}) ---")
        print(f"  days_to_landmark        burst: {pstack(b.days_to_landmark, '{:.0f}')}   persistent: {pstack(p.days_to_landmark, '{:.0f}')}")
        print(f"  peak_retention (%)      burst: {pstack(b.peak_retention*100)}   persistent: {pstack(p.peak_retention*100)}")
        print(f"  is_new_closing_high     burst: {b.is_new_closing_high.mean()*100:.1f}%   persistent: {p.is_new_closing_high.mean()*100:.1f}%")
        print(f"  trailing_persist_3d     burst: {pstack(b.trailing_persist_3d, '{:.1f}')}   persistent: {pstack(p.trailing_persist_3d, '{:.1f}')}")
        # simple separation check: does the median differ by more than the IQR overlap
        bm, pm = b.peak_retention.median(), p.peak_retention.median()
        b_iqr = (b.peak_retention.quantile(.25), b.peak_retention.quantile(.75))
        p_iqr = (p.peak_retention.quantile(.25), p.peak_retention.quantile(.75))
        overlap = not (b_iqr[1] < p_iqr[0] or p_iqr[1] < b_iqr[0])
        print(f"  peak_retention median gap: {abs(bm-pm)*100:.1f}pp   IQRs overlap: {overlap}")

    print("\n" + "=" * 100)
    print("For context only (not the primary comparison): all 5 archetypes' peak_retention at first +1.0R")
    print("=" * 100)
    sub1 = df[df.level == 1.0]
    for arch, grp in sub1.groupby("archetype"):
        print(f"  {arch:24s} n={len(grp):6d}  peak_retention median={grp.peak_retention.median()*100:.1f}%")
