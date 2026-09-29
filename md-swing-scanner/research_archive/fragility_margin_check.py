"""Isolated research only (2026-09-17). Critic's "Fragility Margin" proposal, prompted by
direct user concern: swing can tolerate a pullback (structural stop, SMA21 trail, 15-day
cap all give it room), but options are far more sensitive to the exact same pullback
(leverage + theta decay), and the user wants to know in advance which breakouts are the
"boots through" kind vs the "pulls back and needs room" kind, specifically from an
options-survivability angle.

Fragility Margin = (Day+1 Exit Price - Trigger Price) / Trigger Price -- already exactly
what day1_pnl_pct represents in this project's convention (entry price = trigger price),
so no new simulation needed, just the slippage-scenario labeling the critic asked for
instead of a raw quartile split. Reuses runs/runaway_prediction_check.csv (n=690, real
intraday-confirmed set, already has freshness_score/body_atr/consolidation_days/
dist_to_trigger_pct/close_pos/rvol_at_trigger from the earlier 2026-09-13 fragility work) --
no new data collection.

Labels (winners only): Robust = survives all 4 tested slippage levels (margin > 0.8%);
Medium = survives some (0.4% < margin <= 0.8%); Fragile = would flip to a loss on the
smallest tested slip (0% < margin <= 0.4%, matching the real 0.44% median premium found
in the acceptance-delay work).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

SLIP_LEVELS = [0.2, 0.4, 0.6, 0.8]  # %, matching the critic's exact proposal

FEATURES = ["freshness_score", "consolidation_days", "dist_to_trigger_pct", "close_pos",
            "body_atr", "rvol_at_trigger"]


def label_fragility(margin_pct):
    if margin_pct <= 0:
        return "already_loss"
    if margin_pct <= 0.4:
        return "Fragile"
    if margin_pct <= 0.8:
        return "Medium"
    return "Robust"


def run():
    df = pd.read_csv("runs/runaway_prediction_check.csv", parse_dates=["entry_date"])
    df["fragility_margin_pct"] = df.day1_pnl_pct  # already margin-over-trigger, per project convention
    df["fragility_label"] = df.fragility_margin_pct.apply(label_fragility)

    winners = df[df.fragility_margin_pct > 0].copy()
    print(f"n winners = {len(winners)} of {len(df)} total\n")
    print("=== Fragility label distribution (winners only) ===")
    counts = winners.fragility_label.value_counts()
    for label in ["Fragile", "Medium", "Robust"]:
        n = counts.get(label, 0)
        print(f"  {label:<8} n={n:<4} ({n/len(winners)*100:.1f}%)")
    print()

    print("=== slippage survival: what fraction of winners survive each tested slip level? ===")
    for slip in SLIP_LEVELS:
        survives = (winners.fragility_margin_pct > slip).mean() * 100
        print(f"  survives {slip}% adverse slip: {survives:.1f}%")
    print()

    print("=== which pre-entry features predict Fragile vs Robust? (winners only) ===\n")
    labeled = winners[winners.fragility_label.isin(["Fragile", "Robust"])].copy()
    labeled["is_fragile"] = (labeled.fragility_label == "Fragile").astype(int)
    for feat in FEATURES:
        sub = labeled.dropna(subset=[feat]).copy()
        if len(sub) < 20:
            print(f"{feat}: insufficient data\n")
            continue
        corr = sub[feat].rank().corr(sub.is_fragile.rank())
        sub["q"] = pd.qcut(sub[feat].rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
        g = sub.groupby("q", observed=True)["is_fragile"].agg(["mean", "count"])
        print(f"--- {feat} (n={len(sub)}, rank-corr={corr:+.3f}) ---")
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            print(f"    {q}: n={int(g.loc[q, 'count']):<4} fragile rate {g.loc[q, 'mean']*100:.1f}%")
        print()

    print("=== does Fragility Margin ALSO predict real swing outcome? (checking both, per standing convention) ===")
    swing_corr = winners.fragility_margin_pct.corr(winners.swing_pnl_pct)
    print(f"  Pearson(fragility_margin_pct, swing_pnl_pct) among winners = {swing_corr:+.3f}")


if __name__ == "__main__":
    run()
