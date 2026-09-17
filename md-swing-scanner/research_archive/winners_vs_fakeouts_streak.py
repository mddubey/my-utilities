"""Isolated research only (2026-09-13). Response-23's literal proposed experiment (never
run in exactly this form): take the 50 biggest options winners and the 50 worst fakeouts
from the honest population, and measure just one thing -- how many consecutive 5-minute
closes stayed above the trigger before the streak broke (the MAX streak length reached
that day, whether or not it ever hit our streak>=3 threshold). Uses
runs/vwap_and_timeofday_check.csv (n=934, all raw-trigger entries with intraday coverage).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005


def max_streak(day_bars, trigger):
    streak, best = 0, 0
    for close in day_bars.Close:
        if close > trigger:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def run():
    pool = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    cache = {}
    results = []
    for _, r in pool.iterrows():
        if r.ticker not in cache:
            cache[r.ticker] = (backtest.load(r.ticker, daily_pivots).reset_index(),
                                intraday_cache.load(r.ticker))
        rows, intraday = cache[r.ticker]
        match = rows.index[rows.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        trigger = rows.iloc[i].high10_prior * TRIGGER_CLEARANCE
        idx = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
        day_bars = intraday.set_axis(idx)[idx.normalize() == r.entry_date]
        if day_bars.empty:
            continue
        best_streak = max_streak(day_bars, trigger)
        results.append(dict(ticker=r.ticker, entry_date=r.entry_date,
                             day1_pnl_pct=r.day1_pnl_pct, max_streak=best_streak))

    out = pd.DataFrame(results)
    out.to_csv("runs/winners_vs_fakeouts_streak.csv", index=False)
    print(f"n = {len(out)}\n")

    top50 = out.nlargest(50, "day1_pnl_pct")
    bottom50 = out.nsmallest(50, "day1_pnl_pct")

    print(f"=== 50 BIGGEST WINNERS (day1_pnl_pct range {top50.day1_pnl_pct.min():.2f}% to {top50.day1_pnl_pct.max():.2f}%) ===")
    print(f"  max streak reached: mean={top50.max_streak.mean():.1f}  median={top50.max_streak.median():.0f}  "
          f"min={top50.max_streak.min()}  max={top50.max_streak.max()}")
    print(f"  distribution: {top50.max_streak.value_counts().sort_index().to_dict()}")
    print(f"  reached streak>=3: {(top50.max_streak>=3).mean()*100:.1f}%   reached streak>=5: {(top50.max_streak>=5).mean()*100:.1f}%")

    print(f"\n=== 50 WORST FAKEOUTS (day1_pnl_pct range {bottom50.day1_pnl_pct.min():.2f}% to {bottom50.day1_pnl_pct.max():.2f}%) ===")
    print(f"  max streak reached: mean={bottom50.max_streak.mean():.1f}  median={bottom50.max_streak.median():.0f}  "
          f"min={bottom50.max_streak.min()}  max={bottom50.max_streak.max()}")
    print(f"  distribution: {bottom50.max_streak.value_counts().sort_index().to_dict()}")
    print(f"  reached streak>=3: {(bottom50.max_streak>=3).mean()*100:.1f}%   reached streak>=5: {(bottom50.max_streak>=5).mean()*100:.1f}%")

    print(f"\n=== critic's specific claim check: 'fakeouts mostly fail within 1 bar, winners survive 2-3 bars' ===")
    print(f"  winners with max_streak <= 1: {(top50.max_streak<=1).mean()*100:.1f}%")
    print(f"  fakeouts with max_streak <= 1: {(bottom50.max_streak<=1).mean()*100:.1f}%")


if __name__ == "__main__":
    run()
