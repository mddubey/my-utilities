"""Isolated research only (2026-09-15+). Freshness x Stop Distance interaction -- the last
item on the critic's post-cap priority list before it got queued behind the stop
architecture (now settled and frozen, see FINDINGS.md). Same additive-model-check
methodology as the earlier Freshness x Distance-to-trigger / Freshness x Consolidation
interactions (freshness_interaction_check.py, critic update-28): does combining freshness
with the trade's own initial-stop width recover something an additive model would miss,
or are the two effects just independent and additive?

"Stop distance" here = the real production initial-risk % at entry for Breakout
Continuation: (trigger - (structural_low - STRUCTURAL_STOP_ATR_BUFFER*atr_entry)) /
trigger * 100 -- the exact formula now wired into backtest.py's current_stop_level()
pre-engagement branch, not a re-derived approximation.

Population: runs/rsi_max_sweep_80.csv, the full unfiltered daily-bar-only Breakout
Continuation population (n=14,225, pattern=="breakout_cont" only, matching every other
test in the SMA21/Family-C/stop thread) -- freshness_score already computed per trade.
Deliberately NOT pre-filtered to freshness<=0.40 here, since freshness is one of the two
axes under study; filtering it first would collapse the very variable being tested.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def compute_stop_dist_pct(daily, i):
    row = daily.iloc[i]
    trigger = row.high10_prior * TRIGGER_CLEARANCE
    lo = max(0, i - backtest.STRUCTURAL_LOOKBACK_BC)
    structural_low = daily.iloc[lo:i].Low.min() if i > lo else trigger * 0.9
    atr_entry = row.atr14
    if not atr_entry or pd.isna(atr_entry):
        return None
    base_stop = structural_low - backtest.STRUCTURAL_STOP_ATR_BUFFER * atr_entry
    return (trigger - base_stop) / trigger * 100


def two_way(df):
    sub = df.dropna(subset=["freshness_score", "stop_dist_pct", "opt_pnl_pct", "swing_pnl_pct"]).copy()
    sub["fresh_q"] = pd.qcut(sub.freshness_score.rank(method="first"), 2, labels=["Fresh", "Extended"])
    sub["dist_q"] = pd.qcut(sub.stop_dist_pct.rank(method="first"), 2, labels=["Near(tight stop)", "Far(wide stop)"])
    g = sub.groupby(["fresh_q", "dist_q"], observed=True).agg(
        n=("opt_pnl_pct", "count"),
        opt_win=("opt_pnl_pct", lambda s: (s > 0).mean() * 100),
        opt_mean=("opt_pnl_pct", "mean"),
        swing_win=("swing_pnl_pct", lambda s: (s > 0).mean() * 100),
        swing_mean=("swing_pnl_pct", "mean"),
    )
    print(f"=== Freshness x Stop Distance (n={len(sub)}) ===")
    for idx, row in g.iterrows():
        print(f"  {idx[0]:<10} {idx[1]:<18} n={int(row.n):<5} "
              f"OPTIONS win {row.opt_win:5.1f}% mean {row.opt_mean:+.2f}%   |   "
              f"SWING win {row.swing_win:5.1f}% mean {row.swing_mean:+.2f}%")
    print()
    return sub


def additive_check(sub, outcome_col, label):
    overall = sub[outcome_col].mean()
    marg_fresh = sub.groupby("fresh_q", observed=True)[outcome_col].mean()
    marg_dist = sub.groupby("dist_q", observed=True)[outcome_col].mean()
    cell = sub.groupby(["fresh_q", "dist_q"], observed=True)[outcome_col].mean()
    print(f"=== Additive-model check: Fresh+StopDistance ({label}) ===")
    for f in ["Fresh", "Extended"]:
        for d in ["Near(tight stop)", "Far(wide stop)"]:
            predicted_additive = overall + (marg_fresh[f] - overall) + (marg_dist[d] - overall)
            actual = cell[(f, d)]
            print(f"  {f}/{d}: actual mean {actual:+.2f}%   additive-predicted {predicted_additive:+.2f}%   "
                  f"cross-term {actual - predicted_additive:+.2f}pp")
    print()


def quartile_check(sub, outcome_col, label):
    """Finer 4x4 grid, quartiles both axes -- a coarser 2x2 read can mask a real
    non-monotonic interaction; check before concluding "purely additive" from halves alone."""
    q = sub.copy()
    q["fresh_q4"] = pd.qcut(q.freshness_score.rank(method="first"), 4, labels=["Q1(freshest)", "Q2", "Q3", "Q4(most ext.)"])
    q["dist_q4"] = pd.qcut(q.stop_dist_pct.rank(method="first"), 4, labels=["D1(tightest)", "D2", "D3", "D4(widest)"])
    g = q.groupby(["fresh_q4", "dist_q4"], observed=True)[outcome_col].agg(["count", "mean"])
    print(f"=== Quartile grid: Fresh x StopDistance on {label} (mean pnl%, n in parens) ===")
    pivot_mean = g["mean"].unstack()
    pivot_n = g["count"].unstack()
    for fq in pivot_mean.index:
        row_str = "  ".join(f"{pivot_mean.loc[fq, dq]:+6.2f}%(n={int(pivot_n.loc[fq, dq])})" for dq in pivot_mean.columns)
        print(f"  {fq:<15} {row_str}")
    print()


def run():
    df = pd.read_csv("runs/rsi_max_sweep_80.csv", parse_dates=["entry_date"])
    print(f"n (full unfiltered BC population) = {len(df)}")

    stop_dists = []
    for idx, r in enumerate(df.itertuples(), 1):
        if idx % 2000 == 0:
            print(f"  {idx}/{len(df)}", flush=True)
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            stop_dists.append(None)
            continue
        stop_dists.append(compute_stop_dist_pct(daily, match[0]))
    df["stop_dist_pct"] = stop_dists

    print(f"n with computable stop distance = {df.stop_dist_pct.notna().sum()}\n")

    sub = two_way(df)
    additive_check(sub, "opt_pnl_pct", "options")
    additive_check(sub, "swing_pnl_pct", "swing")
    quartile_check(sub, "opt_pnl_pct", "options")
    quartile_check(sub, "swing_pnl_pct", "swing")

    df.to_csv("runs/freshness_stop_distance_check.csv", index=False)


if __name__ == "__main__":
    run()
