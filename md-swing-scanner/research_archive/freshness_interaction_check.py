"""Isolated research only (2026-09-13). Critic update-28 ask #2/#3: Freshness x Distance and
Freshness x Consolidation interactions -- does combining freshness with either of these two
(individually flat-on-streak-confirmed-population) features recover something an additive
model would miss? Reuses runs/runaway_prediction_check.csv, no new data collection.

Reports win rate AND mean pnl, options AND swing, per the two standing rules established this
session (report both exit regimes; don't just report a proxy label when the real outcome is
available).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd


def two_way(df, feat_a, feat_b, label_a, label_b):
    sub = df.dropna(subset=[feat_a, feat_b, "day1_pnl_pct", "swing_pnl_pct"]).copy()
    sub[f"{feat_a}_q"] = pd.qcut(sub[feat_a].rank(method="first"), 2, labels=[f"{label_a}(low)", f"{label_a}(high)"])
    sub[f"{feat_b}_q"] = pd.qcut(sub[feat_b].rank(method="first"), 2, labels=[f"{label_b}(low)", f"{label_b}(high)"])
    g = sub.groupby([f"{feat_a}_q", f"{feat_b}_q"], observed=True).agg(
        n=("day1_pnl_pct", "count"),
        opt_win=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        opt_mean=("day1_pnl_pct", "mean"),
        swing_win=("swing_pnl_pct", lambda s: (s > 0).mean() * 100),
        swing_mean=("swing_pnl_pct", "mean"),
    )
    print(f"=== {feat_a} x {feat_b} (n={len(sub)}) ===")
    for idx, row in g.iterrows():
        print(f"  {idx[0]:<22} {idx[1]:<22} n={int(row.n):<4} "
              f"OPTIONS win {row.opt_win:5.1f}% mean {row.opt_mean:+.2f}%   |   "
              f"SWING win {row.swing_win:5.1f}% mean {row.swing_mean:+.2f}%")
    print()


def run():
    df = pd.read_csv("runs/runaway_prediction_check.csv", parse_dates=["entry_date"])

    two_way(df, "freshness_score", "dist_to_trigger_pct", "Fresh", "Distance")
    two_way(df, "freshness_score", "consolidation_days", "Fresh", "Consol")

    # additive-model check: does the interaction cell beat what you'd predict from each
    # margin alone (i.e. is there a real cross-term, or is it just two additive effects)?
    print("=== Additive-model check: Fresh+Distance ===")
    sub = df.dropna(subset=["freshness_score", "dist_to_trigger_pct", "day1_pnl_pct"]).copy()
    overall = sub.day1_pnl_pct.mean()
    sub["fresh_q"] = pd.qcut(sub.freshness_score.rank(method="first"), 2, labels=["Fresh", "Extended"])
    sub["dist_q"] = pd.qcut(sub.dist_to_trigger_pct.rank(method="first"), 2, labels=["Near", "Far"])
    marg_fresh = sub.groupby("fresh_q", observed=True).day1_pnl_pct.mean()
    marg_dist = sub.groupby("dist_q", observed=True).day1_pnl_pct.mean()
    cell = sub.groupby(["fresh_q", "dist_q"], observed=True).day1_pnl_pct.mean()
    for f in ["Fresh", "Extended"]:
        for d in ["Near", "Far"]:
            predicted_additive = overall + (marg_fresh[f] - overall) + (marg_dist[d] - overall)
            actual = cell[(f, d)]
            print(f"  {f}/{d}: actual mean {actual:+.2f}%   additive-predicted {predicted_additive:+.2f}%   "
                  f"cross-term {actual - predicted_additive:+.2f}pp")
    print()

    print("=== Additive-model check: Fresh+Consolidation ===")
    sub2 = df.dropna(subset=["freshness_score", "consolidation_days", "day1_pnl_pct"]).copy()
    overall2 = sub2.day1_pnl_pct.mean()
    sub2["fresh_q"] = pd.qcut(sub2.freshness_score.rank(method="first"), 2, labels=["Fresh", "Extended"])
    sub2["cons_q"] = pd.qcut(sub2.consolidation_days.rank(method="first"), 2, labels=["Low", "High"])
    marg_fresh2 = sub2.groupby("fresh_q", observed=True).day1_pnl_pct.mean()
    marg_cons = sub2.groupby("cons_q", observed=True).day1_pnl_pct.mean()
    cell2 = sub2.groupby(["fresh_q", "cons_q"], observed=True).day1_pnl_pct.mean()
    for f in ["Fresh", "Extended"]:
        for c in ["Low", "High"]:
            predicted_additive = overall2 + (marg_fresh2[f] - overall2) + (marg_cons[c] - overall2)
            actual = cell2[(f, c)]
            print(f"  {f}/{c}: actual mean {actual:+.2f}%   additive-predicted {predicted_additive:+.2f}%   "
                  f"cross-term {actual - predicted_additive:+.2f}pp")
    print()


if __name__ == "__main__":
    run()
