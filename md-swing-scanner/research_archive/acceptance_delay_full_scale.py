"""Isolated research only (2026-09-13). Full-scale version of acceptance_delay_check.py --
the 50/50 extremes test was decisive (0% of the biggest winners missed even at a 3-bar
threshold, 72% of worst fakeouts filtered), now checking the complete honest population
(base_filters_pass + intraday breach, full universe, intraday-cache window) to get the
real win-rate/median lift and a proper concentration check before wiring anything in.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005


def max_consecutive_closes_above(day_bars, trigger):
    best = 0
    current = 0
    for close in day_bars.Close:
        if close > trigger:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def run():
    pool = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    cache = {}
    results = []
    for _, r in pool.iterrows():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        ticker_df = cache[r.ticker]
        row = ticker_df[ticker_df.Date == r.entry_date]
        if row.empty:
            continue
        trigger = row.iloc[0].high10_prior * TRIGGER_CLEARANCE
        intraday = intraday_cache.load(r.ticker)
        intraday.index = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
        day_bars = intraday[intraday.index.normalize() == r.entry_date]
        if day_bars.empty:
            continue
        best_streak = max_consecutive_closes_above(day_bars, trigger)
        results.append(dict(ticker=r.ticker, entry_date=r.entry_date,
                           day1_pnl_pct=r.day1_pnl_pct, best_streak=best_streak))

    out = pd.DataFrame(results)
    out.to_csv("runs/acceptance_delay_full_scale.csv", index=False)

    print(f"n = {len(out)}")
    print(f"baseline: win {(out.day1_pnl_pct>0).mean()*100:.1f}%  median {out.day1_pnl_pct.median():.2f}%")
    print()
    for thresh in [1, 2, 3, 4, 5]:
        sub = out[out.best_streak >= thresh]
        rejected = out[out.best_streak < thresh]
        total = sub.day1_pnl_pct.sum()
        top10 = sub.day1_pnl_pct.sort_values(ascending=False).head(10).sum()
        conc = top10/total*100 if total else float("nan")
        print(f"--- streak >= {thresh} (n={len(sub)}, {len(sub)/len(out)*100:.1f}% kept) ---")
        print(f"  win {(sub.day1_pnl_pct>0).mean()*100:.1f}%  median {sub.day1_pnl_pct.median():.2f}%  concentration {conc:.1f}%")
        print(f"  rejected (n={len(rejected)}): win {(rejected.day1_pnl_pct>0).mean()*100:.1f}%  median {rejected.day1_pnl_pct.median():.2f}%")
        print()


if __name__ == "__main__":
    run()
