"""Isolated research only (2026-09-13). Critic update-28's "Premium Tolerance / Fragility"
ask (their #1 priority): stop treating this as a win/loss classification problem and instead
ask which pre-breach features predict the MAGNITUDE of the edge -- how much entry premium a
trade can absorb before it flips from a win to a loss. Reuses runs/runaway_prediction_check.csv
(already has all features + day1_pnl_pct + swing_pnl_pct from the 2026-09-13 runaway-prediction
build), no new data collection needed.

Two views:
  1. Continuous correlation -- does each feature predict the SIZE of day1_pnl_pct/swing_pnl_pct,
     not just whether it's positive?
  2. Fragility classification -- of trades that ARE winners, which ones are "fragile" (would
     flip to a loss if entry slipped by a plausible real premium)? Uses the actual median
     premium found in update-27's acceptance-delay work (0.44%, streak>=3) as the slip
     assumption, not an arbitrary round number.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

SLIP_ASSUMPTION_PCT = 0.44  # median real premium paid by streak>=3 confirmation, from update-27

FEATURES = ["freshness_score", "consolidation_days", "dist_to_trigger_pct", "close_pos",
            "body_atr", "rvol_at_trigger"]


def run():
    df = pd.read_csv("runs/runaway_prediction_check.csv", parse_dates=["entry_date"])

    print("=== 1. Continuous correlation: does the feature predict MAGNITUDE, not just win/loss? ===\n")
    for feat in FEATURES:
        sub = df.dropna(subset=[feat, "day1_pnl_pct", "swing_pnl_pct"]).copy()
        if len(sub) < 20:
            print(f"{feat}: insufficient data\n")
            continue
        corr_opt = sub[feat].corr(sub.day1_pnl_pct)
        corr_swing = sub[feat].corr(sub.swing_pnl_pct)
        rank_corr_opt = sub[feat].rank().corr(sub.day1_pnl_pct.rank())
        rank_corr_swing = sub[feat].rank().corr(sub.swing_pnl_pct.rank())
        sub["q"] = pd.qcut(sub[feat].rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
        g = sub.groupby("q", observed=True).agg(
            n=(feat, "count"),
            opt_mean_pnl=("day1_pnl_pct", "mean"),
            swing_mean_pnl=("swing_pnl_pct", "mean"),
        )
        print(f"--- {feat} (n={len(sub)}) ---")
        print(f"  Pearson corr vs day1_pnl_pct: {corr_opt:+.3f}   vs swing_pnl_pct: {corr_swing:+.3f}")
        print(f"  Spearman (rank) corr vs day1_pnl_pct: {rank_corr_opt:+.3f}   vs swing_pnl_pct: {rank_corr_swing:+.3f}")
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            row = g.loc[q]
            print(f"    {q}: n={int(row.n):<4} mean OPTIONS pnl {row.opt_mean_pnl:+.2f}%   mean SWING pnl {row.swing_mean_pnl:+.2f}%")
        print()

    print(f"\n=== 2. Fragility: of OPTIONS winners, which would flip to a loss if entry slipped {SLIP_ASSUMPTION_PCT}%? ===\n")
    winners = df[df.day1_pnl_pct > 0].copy()
    winners["fragile"] = winners.day1_pnl_pct <= SLIP_ASSUMPTION_PCT
    print(f"n winners = {len(winners)}, fragile (would flip on a {SLIP_ASSUMPTION_PCT}% slip): "
          f"{winners.fragile.mean()*100:.1f}% ({winners.fragile.sum()}/{len(winners)})\n")

    for feat in FEATURES:
        sub = winners.dropna(subset=[feat]).copy()
        if len(sub) < 20:
            print(f"{feat}: insufficient data\n")
            continue
        sub["q"] = pd.qcut(sub[feat].rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
        g = sub.groupby("q", observed=True)["fragile"].agg(["mean", "count"])
        corr = sub[feat].rank().corr(sub.fragile.astype(int))
        print(f"--- {feat} vs fragility (n={len(sub)}, rank-corr={corr:+.3f}) ---")
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            print(f"    {q}: n={int(g.loc[q, 'count']):<4} fragile rate {g.loc[q, 'mean']*100:.1f}%")
        print()


if __name__ == "__main__":
    run()
