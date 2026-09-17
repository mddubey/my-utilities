"""Isolated research only (2026-09-14). Update 39 (critic priority list): the exact
RVOL-retirement portfolio-ranking methodology (rvol_portfolio_ranking_test.py), applied to
market breadth instead of RVOL. Same retirement rule: if Freshness+Breadth does not
outperform Freshness-only (and Freshness+Distance+Breadth doesn't beat Freshness+Distance),
breadth stays display-only, never promoted to the ranking formula.

Unlike RVOL, breadth doesn't need real intraday bars -- it's a daily, market-wide number
-- so this runs on the full 2021-2026 population (runs/consolidation_and_room.csv, n=14225),
not the small intraday-cache-limited pool RVOL was stuck with. Per the standing
population-choice discipline, bigger population preferred whenever the test doesn't
actually require intraday data.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import breadth
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

CAPS = [2, 3]


def freshness(rsi14, mom20):
    if pd.isna(rsi14) or pd.isna(mom20):
        return None
    rsi_pct = _percentile_from_breaks(rsi14, RSI_PCT_BREAKS)
    mom_pct = _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)
    return 0.5 * rsi_pct + 0.5 * mom_pct


def run():
    df = pd.read_csv("runs/consolidation_and_room.csv", parse_dates=["entry_date"])
    df["freshness_score"] = df.apply(lambda r: freshness(r.yday_rsi14, r.yday_momentum_20d), axis=1)
    df["breadth_pct"] = df.entry_date.apply(breadth.breadth_pct)

    print(f"n = {len(df)}   with freshness = {df.freshness_score.notna().sum()}   "
          f"with breadth = {df.breadth_pct.notna().sum()}   with distance = {df.dist_to_trigger_pct.notna().sum()}\n")

    day_counts = df.groupby("entry_date").size()
    print(f"days with >1 candidate: {(day_counts > 1).sum()} / {len(day_counts)}")

    complete = df.dropna(subset=["freshness_score", "breadth_pct", "dist_to_trigger_pct", "day1_pnl_pct"]).copy()
    print(f"n with ALL fields present = {len(complete)}")
    multi_days = complete.groupby("entry_date").filter(lambda g: len(g) > 1)
    print(f"on days with >1 simultaneous candidate: {len(multi_days)} trades across "
          f"{multi_days.entry_date.nunique()} days\n")

    def rank_asc(s):  # lower raw value = better
        return s.rank(ascending=True, pct=True)

    def rank_desc(s):  # higher raw value = better
        return s.rank(ascending=False, pct=True)

    strategies = {
        "Freshness only": lambda g: rank_asc(g.freshness_score),
        "Freshness + Breadth": lambda g: (rank_asc(g.freshness_score) + rank_desc(g.breadth_pct)) / 2,
        "Freshness + Distance": lambda g: (rank_asc(g.freshness_score) + rank_desc(g.dist_to_trigger_pct)) / 2,
        "Freshness + Distance + Breadth": lambda g: (rank_asc(g.freshness_score) + rank_desc(g.dist_to_trigger_pct) + rank_desc(g.breadth_pct)) / 3,
    }

    for cap in CAPS:
        print(f"=== Capital cap = {cap} positions/day ===")
        for name, score_fn in strategies.items():
            selected = []
            for date, g in complete.groupby("entry_date"):
                if len(g) <= cap:
                    selected.append(g)
                    continue
                score = score_fn(g)
                top = g.loc[score.nsmallest(cap).index]
                selected.append(top)
            picked = pd.concat(selected)
            win = (picked.day1_pnl_pct > 0).mean() * 100
            med = picked.day1_pnl_pct.median()
            mean = picked.day1_pnl_pct.mean()
            print(f"  {name:<32} n={len(picked):<6} win {win:5.1f}%  median {med:+.2f}%  mean {mean:+.2f}%")
        print()


if __name__ == "__main__":
    run()
