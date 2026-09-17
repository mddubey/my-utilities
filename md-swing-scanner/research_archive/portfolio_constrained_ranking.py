"""Isolated research only (2026-09-13). Portfolio-constrained ranking (critic response-21,
one of the original 5 research tracks, never done for the freshness/streak filters
specifically -- only ever done for the older 3-day-stall rule, FINDINGS.md 2026-09-07).
Does freshness's per-trade quality lift survive when capital only allows a handful of
concurrent positions? Chronological greedy admission: walk all n=934 raw-trigger signals
(vwap_and_timeofday_check.csv) in entry-date order, admit a new signal only if fewer than
MAX_CONCURRENT positions are already open (tracked via each trade's real check_exit() exit
date), preferring the freshest candidate when multiple fire on the same day. Compared
against a no-ranking control (chronological/first-come admission, same cap) to isolate
whether the RANKING specifically matters, not just the cap itself.
"""
import warnings
warnings.filterwarnings("ignore")

import heapq

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

TRIGGER_CLEARANCE = 1.005
MAX_CONCURRENT = 5


def simulate_swing(rows, entry_i, entry_price):
    state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=entry_price,
                 structural_low=0.0, target=None)
    for j in range(entry_i + 1, len(rows)):
        row = rows.iloc[j]
        if row.corp_action_day:
            return dict(exit_i=j, exit_price=state["peak_close"], open_at_end=False)
        exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=True)
        if exit_reason is not None:
            return dict(exit_i=j, exit_price=row.Close, open_at_end=False)
    last_i = len(rows) - 1
    return dict(exit_i=last_i, exit_price=rows.iloc[last_i].Close, open_at_end=True)


def freshness(rsi14, mom20):
    if pd.isna(rsi14) or pd.isna(mom20):
        return None
    rsi_pct = _percentile_from_breaks(rsi14, RSI_PCT_BREAKS)
    mom_pct = _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)
    return 0.5 * rsi_pct + 0.5 * mom_pct


def build_population():
    pool = pd.read_csv("runs/consolidation_and_room.csv", parse_dates=["entry_date"])
    pool = pool.dropna(subset=["yday_rsi14", "yday_momentum_20d", "day1_pnl_pct"]).copy()
    pool["freshness_score"] = pool.apply(lambda r: freshness(r.yday_rsi14, r.yday_momentum_20d), axis=1)

    cache = {}
    exit_dates, pnl_pcts, open_flags = [], [], []
    for _, r in pool.iterrows():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        rows = cache[r.ticker]
        match = rows.index[rows.Date == r.entry_date]
        if len(match) == 0 or match[0] + 1 >= len(rows):
            exit_dates.append(None); pnl_pcts.append(None); open_flags.append(None)
            continue
        i = match[0]
        trigger = rows.iloc[i].high10_prior * TRIGGER_CLEARANCE
        out = simulate_swing(rows, i, trigger)
        exit_dates.append(rows.iloc[out["exit_i"]].Date)
        pnl_pcts.append((out["exit_price"] / trigger - 1) * 100)
        open_flags.append(out["open_at_end"])

    pool["exit_date"] = exit_dates
    pool["swing_pnl_pct"] = pnl_pcts
    pool["swing_open"] = open_flags
    pool = pool.dropna(subset=["exit_date"]).copy()
    # sort by ticker alphabetically as the neutral base order -- deliberately NOT by
    # freshness, so the "no ranking" control below is a genuinely different admission
    # order from the "ranked" one, not the same order relabeled.
    pool = pool.sort_values(["entry_date", "ticker"]).reset_index(drop=True)
    return pool


def greedy_admit(pool, max_concurrent, use_ranking):
    """Walk chronologically; within same entry_date, process freshest-first if use_ranking,
    else in ticker-alphabetical order (the neutral base order pool is already sorted in,
    uncorrelated with freshness). Admit if fewer than max_concurrent positions are open
    (tracked via a min-heap of exit dates)."""
    if use_ranking:
        order = pool.sort_values(["entry_date", "freshness_score"], kind="stable").index
    else:
        order = pool.index  # already ticker-alphabetical within each entry_date
    open_heap = []  # min-heap of exit_date for currently open positions
    admitted_idx = []
    for idx in order:
        row = pool.loc[idx]
        while open_heap and open_heap[0] <= row.entry_date:
            heapq.heappop(open_heap)
        if len(open_heap) < max_concurrent:
            heapq.heappush(open_heap, row.exit_date)
            admitted_idx.append(idx)
    return pool.loc[admitted_idx]


def run():
    print("Building population (swing-simulated exit dates for all n~14k signals)...")
    pool = build_population()
    print(f"n = {len(pool)}\n")

    print(f"=== BASELINE: no cap, take everything ===")
    win = (pool.swing_pnl_pct > 0).mean() * 100
    print(f"  n={len(pool)}  win {win:.1f}%  median {pool.swing_pnl_pct.median():+.2f}%  mean {pool.swing_pnl_pct.mean():+.2f}%\n")

    print(f"=== Capital-constrained, max {MAX_CONCURRENT} concurrent positions ===")
    ranked = greedy_admit(pool, MAX_CONCURRENT, use_ranking=True)
    unranked = greedy_admit(pool, MAX_CONCURRENT, use_ranking=False)

    for label, sub in [("freshness-ranked admission", ranked), ("chronological (no ranking) admission", unranked)]:
        win = (sub.swing_pnl_pct > 0).mean() * 100
        med = sub.swing_pnl_pct.median()
        mean = sub.swing_pnl_pct.mean()
        print(f"  {label}: n={len(sub)} ({len(sub)/len(pool)*100:.1f}% of pool admitted)  "
              f"win {win:.1f}%  median {med:+.2f}%  mean {mean:+.2f}%")

    print(f"\n=== Cumulative R, {MAX_CONCURRENT}-slot cap (assuming ~1R risk per trade, R = pnl_pct at a nominal 1% stock-risk unit not computed here -- using raw pnl_pct sum as a proxy) ===")
    print(f"  freshness-ranked total pnl sum: {ranked.swing_pnl_pct.sum():+.1f}%")
    print(f"  chronological total pnl sum: {unranked.swing_pnl_pct.sum():+.1f}%")


if __name__ == "__main__":
    run()
