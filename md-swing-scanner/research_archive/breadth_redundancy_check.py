"""Isolated research only (2026-09-14). Reconsideration-shortlist item 6 (critic_update_35):
market breadth (breadth.breadth_pct -- % of Nifty500 above their own 200-SMA) was already
adopted as a real, monotonic RANKING signal (never a gate, deliberate choice) on the raw,
unfiltered population. Different question from items 3-5: breadth was never rejected, the
open question is whether it still adds independent lift ON TOP of freshness+cutoff, or has
become redundant with them -- same overlap risk already found once this project (consolidation_days
vs streak-confirmation: real on the raw population, redundant once streak-confirmation applied).

Two checks:
1. Correlation between breadth_pct and freshness_score at entry -- if these are highly
   correlated, breadth may just be a proxy for the same thing freshness already captures.
2. Within the freshness<=0.40-conditioned population, does breadth still show a real
   gradient (win rate/median climbing with breadth quartile), or is it flat/redundant now?

Run across the standard 3-population bracket (feedback_population_choice_for_backtests.md).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import breadth


def concentration(s):
    total = s.sum()
    if not total:
        return float("nan")
    return s.sort_values(ascending=False).head(10).sum() / total * 100


def stats(pnl, label):
    if len(pnl) < 5:
        print(f"    {label:<20} n={len(pnl):<5} (too thin)")
        return
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    wr = len(wins) / len(pnl) * 100
    exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
    print(f"    {label:<20} n={len(pnl):<5} win={wr:5.1f}%  med={pnl.median():+.2f}%  exp={exp:+.3f}%  conc={concentration(pnl):.1f}%")


POPS = {
    "BIG (full-history, n=5213)": pd.read_csv("runs/pop_fresh40_big.csv", parse_dates=["entry_date"]),
    "SMALL (cache-window, n=365)": pd.read_csv("runs/pop_fresh40_small.csv", parse_dates=["entry_date", "breach_time"]),
    "SMALL+1PM cutoff (n=298)": pd.read_csv("runs/pop_fresh40_cutoff.csv", parse_dates=["entry_date", "breach_time"]),
}
for name, df in POPS.items():
    if "opt_pnl_pct" not in df.columns and "day1_pnl_pct" in df.columns:
        df["opt_pnl_pct"] = df["day1_pnl_pct"]

for pop_name, df in POPS.items():
    df = df.copy()
    df["breadth_pct"] = df.entry_date.apply(breadth.breadth_pct)
    df = df.dropna(subset=["breadth_pct"])
    print(f"\n{'=' * 100}\n{pop_name}  (n with breadth = {len(df)})\n{'=' * 100}")

    corr = df.breadth_pct.corr(df.freshness_score)
    print(f"  correlation(breadth_pct, freshness_score) = {corr:+.3f}")

    print("\n  quartile split (breadth_pct):")
    df["q"] = pd.qcut(df.breadth_pct, 4, labels=["Q1 (low)", "Q2", "Q3", "Q4 (high)"], duplicates="drop")
    for q in df.q.cat.categories:
        sub = df[df.q == q]
        o_win = (sub.opt_pnl_pct > 0).mean() * 100
        s_win = (sub.swing_pnl_pct > 0).mean() * 100
        print(f"    {q:<10} n={len(sub):<5} breadth range [{sub.breadth_pct.min():.1f},{sub.breadth_pct.max():.1f}]  "
              f"OPTIONS win {o_win:5.1f}% med {sub.opt_pnl_pct.median():+.2f}%   |   SWING win {s_win:5.1f}% med {sub.swing_pnl_pct.median():+.2f}%")

    print("\n  threshold cuts (>=X%):")
    for thresh in [50, 60, 65, 70, 75, 80]:
        sub = df[df.breadth_pct >= thresh]
        if len(sub) < 20:
            continue
        o_win = (sub.opt_pnl_pct > 0).mean() * 100
        s_win = (sub.swing_pnl_pct > 0).mean() * 100
        print(f"    >={thresh}%    n={len(sub):<5} ({len(sub)/len(df)*100:.1f}%)  OPTIONS win {o_win:5.1f}% med {sub.opt_pnl_pct.median():+.2f}%   |   SWING win {s_win:5.1f}% med {sub.swing_pnl_pct.median():+.2f}%")
