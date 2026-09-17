"""Isolated research only (2026-09-13). Critic update-28 ask #4 (Freshness x Velocity
interaction) and #5 (incremental/combined model, Freshness -> Distance -> Velocity ->
Consolidation). `velocity_pct` exists live in live_checkpoint.py (closing speed toward the
trigger over a 10-min lookback, dist_prior_pct - dist_pct) but isn't in any historical
research population yet -- backfilled here for the n=690 streak-confirmed set using the
same definition: at the bar 5 min before the actual breach bar ("current"), and the bar
10 minutes before THAT ("prior"), both still below the trigger, velocity = how much closer
price got to the trigger in that 10-minute window.
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
VELOCITY_LOOKBACK_MIN = 10


def backfill_velocity(df):
    cache = {}
    velocity_list = []
    for _, r in df.iterrows():
        ticker, entry_date = r.ticker, r.entry_date
        if ticker not in cache:
            daily = backtest.load(ticker, daily_pivots).reset_index()
            try:
                intraday = intraday_cache.load(ticker)
            except FileNotFoundError:
                intraday = None
            by_day = {}
            if intraday is not None and not intraday.empty:
                idx = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
                intraday = intraday.set_axis(idx)
                by_day = {d: g for d, g in intraday.groupby(intraday.index.normalize())}
            cache[ticker] = (daily, by_day)
        daily, by_day = cache[ticker]

        match = daily.index[daily.Date == entry_date]
        if len(match) == 0:
            velocity_list.append(None); continue
        row = daily.iloc[match[0]]
        trigger = row.high10_prior * TRIGGER_CLEARANCE
        day = pd.Timestamp(entry_date).normalize()
        day_bars = by_day.get(day)
        if day_bars is None or day_bars.empty:
            velocity_list.append(None); continue
        crossed = day_bars[day_bars.High >= trigger]
        if crossed.empty:
            velocity_list.append(None); continue
        breach_time = crossed.index[0]

        pre = day_bars[day_bars.index < breach_time]
        if len(pre) < 3:
            velocity_list.append(None); continue
        cur_time = breach_time - pd.Timedelta(minutes=5)
        prior_time = breach_time - pd.Timedelta(minutes=5 + VELOCITY_LOOKBACK_MIN)
        cur_bars = pre[pre.index <= cur_time]
        prior_bars = pre[pre.index <= prior_time]
        if cur_bars.empty or prior_bars.empty:
            velocity_list.append(None); continue
        cur_close = cur_bars.iloc[-1].Close
        prior_close = prior_bars.iloc[-1].Close
        if not cur_close or not prior_close:
            velocity_list.append(None); continue
        dist_cur = (trigger / cur_close - 1) * 100
        dist_prior = (trigger / prior_close - 1) * 100
        velocity_list.append(dist_prior - dist_cur)  # positive = closing fast

    df = df.copy()
    df["velocity_pct"] = velocity_list
    return df


def ols_r2(X_cols, y):
    X = np.column_stack([np.ones(len(y))] + [c for c in X_cols])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    ss_res = ((y - pred) ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    return 1 - ss_res / ss_tot


def run():
    df = pd.read_csv("runs/runaway_prediction_check.csv", parse_dates=["entry_date"])
    df = backfill_velocity(df)
    df.to_csv("runs/velocity_and_incremental_check.csv", index=False)
    print(f"velocity_pct computed for {df.velocity_pct.notna().sum()}/{len(df)}\n")

    sub = df.dropna(subset=["velocity_pct", "day1_pnl_pct", "swing_pnl_pct"]).copy()
    corr_opt = sub.velocity_pct.corr(sub.day1_pnl_pct)
    corr_swing = sub.velocity_pct.corr(sub.swing_pnl_pct)
    rank_win = sub.velocity_pct.rank().corr((sub.day1_pnl_pct > 0).astype(int))
    print(f"=== velocity_pct alone (n={len(sub)}) ===")
    print(f"Pearson corr vs day1_pnl_pct: {corr_opt:+.3f}   vs swing_pnl_pct: {corr_swing:+.3f}")
    print(f"rank-corr vs options win: {rank_win:+.3f}")
    sub["q"] = pd.qcut(sub.velocity_pct.rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
    g = sub.groupby("q", observed=True).agg(
        n=("velocity_pct", "count"),
        opt_win=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        opt_mean=("day1_pnl_pct", "mean"),
        swing_win=("swing_pnl_pct", lambda s: (s > 0).mean() * 100),
        swing_mean=("swing_pnl_pct", "mean"),
    )
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        row = g.loc[q]
        print(f"  {q}: n={int(row.n):<4} OPTIONS win {row.opt_win:5.1f}% mean {row.opt_mean:+.2f}%   |   "
              f"SWING win {row.swing_win:5.1f}% mean {row.swing_mean:+.2f}%")
    print()

    print("=== Freshness x Velocity ===")
    sub2 = df.dropna(subset=["freshness_score", "velocity_pct", "day1_pnl_pct", "swing_pnl_pct"]).copy()
    sub2["fresh_q"] = pd.qcut(sub2.freshness_score.rank(method="first"), 2, labels=["Fresh", "Extended"])
    sub2["vel_q"] = pd.qcut(sub2.velocity_pct.rank(method="first"), 2, labels=["Slow", "Fast"])
    g2 = sub2.groupby(["fresh_q", "vel_q"], observed=True).agg(
        n=("day1_pnl_pct", "count"),
        opt_win=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        opt_mean=("day1_pnl_pct", "mean"),
        swing_win=("swing_pnl_pct", lambda s: (s > 0).mean() * 100),
        swing_mean=("swing_pnl_pct", "mean"),
    )
    for idx, row in g2.iterrows():
        print(f"  {idx[0]:<10} {idx[1]:<6} n={int(row.n):<4} OPTIONS win {row.opt_win:5.1f}% mean {row.opt_mean:+.2f}%   |   "
              f"SWING win {row.swing_win:5.1f}% mean {row.swing_mean:+.2f}%")
    print()

    print("=== Incremental / combined model: Freshness -> Distance -> Velocity -> Consolidation ===")
    inc = df.dropna(subset=["freshness_score", "dist_to_trigger_pct", "velocity_pct",
                             "consolidation_days", "day1_pnl_pct", "swing_pnl_pct"]).copy()
    print(f"n = {len(inc)} (matched population across all 4 features)\n")
    y_opt = inc.day1_pnl_pct.values
    y_swing = inc.swing_pnl_pct.values
    feats_ranked = {
        "freshness_score": -inc.freshness_score.rank().values,  # flip sign: lower score = better
        "dist_to_trigger_pct": inc.dist_to_trigger_pct.rank().values,
        "velocity_pct": inc.velocity_pct.rank().values,
        "consolidation_days": inc.consolidation_days.rank().values,
    }
    order = ["freshness_score", "dist_to_trigger_pct", "velocity_pct", "consolidation_days"]
    cols = []
    for name in order:
        cols.append(feats_ranked[name])
        r2_opt = ols_r2(cols, y_opt)
        r2_swing = ols_r2(cols, y_swing)
        print(f"  + {name:<20} cumulative R^2 vs OPTIONS pnl: {r2_opt:.4f}   vs SWING pnl: {r2_swing:.4f}")


if __name__ == "__main__":
    run()
