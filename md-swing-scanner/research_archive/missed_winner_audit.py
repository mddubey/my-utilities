"""Isolated research only (2026-09-13). Missed Winner Audit (critic response-21, one of the
original 5 research tracks, never done): our filters are validated on AVERAGE quality lift,
but how many genuinely big winners do they throw away as false negatives? Two filters
audited on the same n=934 raw-trigger population (vwap_and_timeofday_check.csv):
freshness (fresh half vs extended half) and streak-acceptance (accepted vs rejected same
day). "Big winner" = top quartile of the WHOLE population's day1_pnl_pct (a fixed, absolute
bar, not relative to whichever subset we're looking at).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
STREAK_THRESHOLD = 3


def first_acceptance_reached(day_bars, trigger, threshold):
    streak = 0
    for close in day_bars.Close:
        if close > trigger:
            streak += 1
            if streak >= threshold:
                return True
        else:
            streak = 0
    return False


def run():
    df = pd.read_csv("runs/runaway_prediction_check.csv", parse_dates=["entry_date"])
    # runaway_prediction_check.csv is already streak-filtered (n=690) -- need the FULL
    # unfiltered pool with freshness score for a fair "what would we have missed" audit.
    pool = pd.read_csv("runs/consolidation_and_room.csv", parse_dates=["entry_date"])
    pool = pool.dropna(subset=["yday_rsi14", "yday_momentum_20d", "day1_pnl_pct"]).copy()

    from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

    def freshness(rsi14, mom20):
        rsi_pct = _percentile_from_breaks(rsi14, RSI_PCT_BREAKS)
        mom_pct = _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)
        return 0.5 * rsi_pct + 0.5 * mom_pct

    pool["freshness_score"] = pool.apply(lambda r: freshness(r.yday_rsi14, r.yday_momentum_20d), axis=1)

    big_winner_cut = pool.day1_pnl_pct.quantile(0.75)
    print(f"n = {len(pool)}   big-winner threshold (top quartile of whole pool): {big_winner_cut:.2f}%\n")

    print("=== FRESHNESS FILTER: fresh half (kept) vs extended half (rejected) ===")
    median_fresh = pool.freshness_score.median()
    kept = pool[pool.freshness_score <= median_fresh]
    rejected = pool[pool.freshness_score > median_fresh]
    for label, sub in [("kept (fresh half)", kept), ("rejected (extended half)", rejected)]:
        big = sub[sub.day1_pnl_pct >= big_winner_cut]
        print(f"  {label}: n={len(sub)}  win {(sub.day1_pnl_pct>0).mean()*100:.1f}%  "
              f"big winners inside: {len(big)} ({len(big)/len(sub)*100:.1f}% of this subset)  "
              f"total pnl of those big winners: {big.day1_pnl_pct.sum():+.1f}%")
    total_big = (pool.day1_pnl_pct >= big_winner_cut).sum()
    missed_big = (rejected.day1_pnl_pct >= big_winner_cut).sum()
    print(f"  => of {total_big} total big winners in the whole pool, freshness-filtering would have "
          f"missed {missed_big} ({missed_big/total_big*100:.1f}%)")
    print(f"  => but rejected group's total pnl (all trades, not just big winners): {rejected.day1_pnl_pct.sum():+.1f}%  "
          f"vs kept group's: {kept.day1_pnl_pct.sum():+.1f}%")

    print("\n=== STREAK FILTER: accepted (kept) vs rejected same-day, only trades w/ intraday data ===")
    cache = {}
    accepted_flags = []
    daily_cache = {}
    for _, r in pool.iterrows():
        if r.ticker not in cache:
            try:
                intraday = intraday_cache.load(r.ticker)
            except FileNotFoundError:
                intraday = None
            cache[r.ticker] = intraday
        intraday = cache[r.ticker]
        if intraday is None or intraday.empty:
            accepted_flags.append(None)
            continue
        if r.ticker not in daily_cache:
            daily_cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        daily = daily_cache[r.ticker]
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            accepted_flags.append(None)
            continue
        row = daily.iloc[match[0]]
        trigger = row.high10_prior * TRIGGER_CLEARANCE
        idx = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
        day_bars = intraday.set_axis(idx)[idx.normalize() == r.entry_date]
        if day_bars.empty:
            accepted_flags.append(None)
            continue
        accepted_flags.append(first_acceptance_reached(day_bars, trigger, STREAK_THRESHOLD))

    pool["accepted"] = accepted_flags
    sub_pool = pool.dropna(subset=["accepted"]).copy()
    sub_pool["accepted"] = sub_pool["accepted"].astype(bool)
    big_winner_cut2 = sub_pool.day1_pnl_pct.quantile(0.75)
    kept2 = sub_pool[sub_pool.accepted]
    rejected2 = sub_pool[~sub_pool.accepted]
    print(f"n (w/ intraday) = {len(sub_pool)}   big-winner threshold: {big_winner_cut2:.2f}%")
    for label, sub in [("accepted (kept)", kept2), ("rejected (never accepted)", rejected2)]:
        big = sub[sub.day1_pnl_pct >= big_winner_cut2]
        print(f"  {label}: n={len(sub)}  win {(sub.day1_pnl_pct>0).mean()*100:.1f}%  "
              f"big winners inside: {len(big)} ({len(big)/len(sub)*100:.1f}% of this subset)  "
              f"total pnl of those big winners: {big.day1_pnl_pct.sum():+.1f}%")
    total_big2 = (sub_pool.day1_pnl_pct >= big_winner_cut2).sum()
    missed_big2 = (rejected2.day1_pnl_pct >= big_winner_cut2).sum()
    print(f"  => of {total_big2} total big winners, streak-filtering would have missed "
          f"{missed_big2} ({missed_big2/total_big2*100:.1f}%)")
    print(f"  => rejected group's total pnl: {rejected2.day1_pnl_pct.sum():+.1f}%  vs accepted group's: {kept2.day1_pnl_pct.sum():+.1f}%")


if __name__ == "__main__":
    run()
