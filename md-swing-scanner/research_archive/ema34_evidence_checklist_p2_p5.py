"""RQ-52A Evidence Checklist, P2/P3/P4/P5 (2026-09-18) -- the remaining items
after P1 (Delta Population Audit, done separately). Reuses
ema34_delta_population.csv (already built) for P2/P3, and Nifty's own streak
state (build_streak_state(), already built for the lag investigation) for P5.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

from research.metrics import expectancy, win_rate
from ema34_lag_outcome_check import build_streak_state


def p2_fragility_margin_size(df):
    print("=== P2: Fragility Margin size (not just discrete labels) ===")
    for name in ["Common", "Delta"]:
        d = df[(df.group == name) & (df.day1_pnl > 0)]
        print(f"  {name} winners (n={len(d)}): mean margin={d.day1_pnl.mean():+.3f}%  median={d.day1_pnl.median():+.3f}%  "
          f"p10={d.day1_pnl.quantile(0.10):+.3f}%  p25={d.day1_pnl.quantile(0.25):+.3f}%")


def p3_freshness_matrix(df):
    print("\n=== P3: Freshness overlap matrix ===")
    print(f"{'group':<8} {'fresh?':<10} {'n':>6}  {'SWING win/exp':>20}  {'OPT win/exp':>20}")
    for group in ["Common", "Delta"]:
        for fresh_flag, label in [(True, "Fresh"), (False, "Not Fresh")]:
            d = df[(df.group == group) & (df.fresh == fresh_flag)]
            d1 = d.day1_pnl.dropna()
            print(f"{group:<8} {label:<10} {len(d):>6}  {win_rate(d.swing_pnl):5.1f}% / {expectancy(d.swing_pnl):+.3f}%      "
                  f"{win_rate(d1):5.1f}% / {expectancy(d1):+.3f}%  (n_opt={len(d1)})")


def p4_candidate_distribution(df, recent_days=90):
    print(f"\n=== P4: Daily candidate-count distribution, last {recent_days} real trading days ===")
    max_date = df.date.max()
    recent_dates = sorted(df.date.unique())[-recent_days:]
    recent = df[df.date.isin(recent_dates)]

    common_per_day = recent[recent.group == "Common"].groupby("date").size().reindex(recent_dates, fill_value=0)
    all_per_day = recent.groupby("date").size().reindex(recent_dates, fill_value=0)

    for label, s in [("EMA34=9 (Common only)", common_per_day), ("EMA34=2 (Common+Delta)", all_per_day)]:
        print(f"  {label:<24} avg={s.mean():5.2f}  P95={s.quantile(0.95):5.1f}  max={s.max():>3}  days>15={  (s>15).sum()}/{len(s)}")


def p5_transition_latency(df, streak_state):
    print("\n=== P5: Transition latency (real trading days from a Nifty recovery start to the first fire, any ticker) ===")
    common_by_date = df[df.group == "Common"].groupby("date").size()
    all_by_date = df.groupby("date").size()  # EMA34=2, i.e. Common+Delta

    # Use the REAL full trading calendar (every real trading day, not just fire-days --
    # df only contains rows where a fire already happened, so restricting the search
    # to df's own dates trivially gives ~0 latency).
    nifty = pd.read_csv("data_cache/_NIFTY.csv", index_col=0, parse_dates=True)
    all_dates = list(nifty.index)
    date_to_idx = {d.normalize(): i for i, d in enumerate(all_dates)}

    recovery_starts = [d for d in all_dates if streak_state.get(d) == ("up", 1)]

    def latency_after(recovery_date, series):
        start_idx = date_to_idx.get(recovery_date.normalize())
        if start_idx is None:
            return None
        for d in all_dates[start_idx:]:
            if series.get(pd.Timestamp(d.date()), 0) > 0:
                return all_dates.index(d) - start_idx  # trading days, not calendar days
        return None

    lat9 = [latency_after(d, common_by_date) for d in recovery_starts]
    lat2 = [latency_after(d, all_by_date) for d in recovery_starts]
    lat9 = pd.Series([x for x in lat9 if x is not None])
    lat2 = pd.Series([x for x in lat2 if x is not None])

    print(f"  n recovery-start events: {len(recovery_starts)}")
    print(f"  EMA34=9 latency: median={lat9.median():.1f} trading days  mean={lat9.mean():.2f}  p75={lat9.quantile(0.75):.1f}")
    print(f"  EMA34=2 latency: median={lat2.median():.1f} trading days  mean={lat2.mean():.2f}  p75={lat2.quantile(0.75):.1f}")


if __name__ == "__main__":
    df = pd.read_csv("ema34_delta_population.csv", parse_dates=["date"])
    p2_fragility_margin_size(df)
    p3_freshness_matrix(df)
    p4_candidate_distribution(df)
    streak_state = build_streak_state()
    p5_transition_latency(df, streak_state)
