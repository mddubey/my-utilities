"""Isolated research only (2026-09-13). The HONEST version of the acceptance-delay test --
entry price is the close of the bar where the streak requirement is FIRST satisfied (real
execution: you fire your order the moment acceptance confirms, you don't wait to see if the
streak gets longer), not the original trigger-touch price. Retry allowed across the day
(same as before): if an early attempt fails, keep scanning for a later crossing.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005


def first_acceptance(day_bars, trigger, threshold):
    """Returns the close price of the bar where `threshold` consecutive closes above
    trigger is FIRST reached (retrying after a broken streak), or None if never reached."""
    streak = 0
    for close in day_bars.Close:
        if close > trigger:
            streak += 1
            if streak >= threshold:
                return close
        else:
            streak = 0
    return None


def run():
    pool = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    cache = {}

    for threshold in [3, 5]:
        results = []
        for _, r in pool.iterrows():
            if r.ticker not in cache:
                cache[r.ticker] = (backtest.load(r.ticker, daily_pivots).reset_index(),
                                   intraday_cache.load(r.ticker))
            ticker_df, intraday = cache[r.ticker]
            row = ticker_df[ticker_df.Date == r.entry_date]
            if row.empty:
                continue
            i = row.index[0]
            trigger = row.iloc[0].high10_prior * TRIGGER_CLEARANCE
            idx_local = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None) if intraday.index.tz is not None else intraday.index
            day_bars = intraday.set_axis(idx_local)[idx_local.normalize() == r.entry_date]
            if day_bars.empty:
                continue
            entry_price = first_acceptance(day_bars, trigger, threshold)
            if entry_price is None:
                continue
            day1_open = ticker_df.iloc[i + 1].Open
            pnl = (day1_open / entry_price - 1) * 100
            results.append(dict(ticker=r.ticker, entry_date=r.entry_date,
                               trigger_price=trigger, real_entry_price=entry_price,
                               premium_paid_pct=(entry_price/trigger-1)*100, day1_pnl_pct=pnl))

        out = pd.DataFrame(results)
        out.to_csv(f"runs/acceptance_real_entry_streak{threshold}.csv", index=False)
        print(f"\n=== streak >= {threshold}, REAL entry price at confirmation, n={len(out)} ===")
        print(f"win {(out.day1_pnl_pct>0).mean()*100:.1f}%  median {out.day1_pnl_pct.median():.2f}%")
        print(f"median premium already paid by the time you'd fire (vs original trigger): {out.premium_paid_pct.median():.2f}%")


if __name__ == "__main__":
    run()
