"""Isolated research only (2026-09-12/13). Critic response-22's proposed validation,
with retry allowed (direct user instruction after the PAYTM Sept 11 case showed a real
winner whose FIRST trigger-touch failed acceptance but who broke out again later the same
day): for the 50 biggest option winners and 50 worst fakeouts in the honest population,
measure the LONGEST run of consecutive 5-minute CLOSES above the trigger anywhere in the
day (not just from the first touch) -- does a stock get to retry after an early failed
attempt, and if so, how much acceptance does the eventual real move actually show?
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
    # reuse the already-built intraday-window population (has day1_pnl_pct, ticker, entry_date)
    pool = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    winners = pool.nlargest(50, "day1_pnl_pct")
    fakeouts = pool.nsmallest(50, "day1_pnl_pct")

    def annotate(df, label):
        results = []
        for _, r in df.iterrows():
            ticker_df = backtest.load(r.ticker, daily_pivots).reset_index()
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
        print(f"\n=== {label} (n={len(out)}) ===")
        print(out.best_streak.value_counts().sort_index())
        print(f"median best_streak: {out.best_streak.median()}")
        print(f"% with best_streak >= 2: {(out.best_streak >= 2).mean()*100:.1f}%")
        print(f"% with best_streak >= 3: {(out.best_streak >= 3).mean()*100:.1f}%")
        print(f"% with best_streak == 0 or 1 (never got real acceptance): {(out.best_streak <= 1).mean()*100:.1f}%")
        return out

    w = annotate(winners, "50 BIGGEST WINNERS")
    f = annotate(fakeouts, "50 WORST FAKEOUTS")
    w.to_csv("runs/acceptance_delay_winners.csv", index=False)
    f.to_csv("runs/acceptance_delay_fakeouts.csv", index=False)


if __name__ == "__main__":
    run()
