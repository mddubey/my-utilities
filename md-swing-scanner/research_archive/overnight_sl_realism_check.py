"""Isolated research only (2026-09-12) -- does the REAL production stop (peak_close -
3xATR / structural_low, i.e. current_stop_level() in backtest.py, completely unmodified)
actually get touched intraday between a real trigger-cross entry and the very next
session's open -- the ONLY window relevant to the "exit at day+1 open, don't chase the
intraday high" plan? Conservative assumption per direct user request: if the stop is
touched at any point in that window, treat it as a real, filled stop-out -- no benefit of
the doubt for "it might have recovered."

Uses REAL 5-min intraday bars (intraday_cache/, 2026-06-10 onward) for the entry-cross
moment and the overnight-to-open path, not daily bars -- this project already found once
(FINDINGS.md, 2026-09-05 intraday-target study) that a daily-bar approximation is blind to
same-day chop and dangerously overstates how safe a tight stop is. Same caution applied
here to the overnight-hold question instead.
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import pandas as pd

import intraday_cache
from backtest import load, detect_entry, current_stop_level
from pivots import daily_pivots

CACHE_DIR = Path("intraday_cache")


def run():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    cache_tickers = {p.stem for p in CACHE_DIR.glob("*.csv")}

    results = []
    for ticker in tickers:
        if ticker not in cache_tickers:
            continue
        try:
            df = load(ticker, daily_pivots)
        except FileNotFoundError:
            continue
        try:
            intraday = intraday_cache.load(ticker)
        except FileNotFoundError:
            continue
        if intraday.empty:
            continue
        intraday = intraday.copy()
        intraday.index = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
        cache_min, cache_max = intraday.index.min().normalize(), intraday.index.max().normalize()

        rows = df.reset_index()
        for i in range(len(rows) - 1):
            row = rows.iloc[i]
            if row.corp_action_day:
                continue
            entry_date = row.Date
            if entry_date < cache_min or entry_date > cache_max:
                continue
            # regime gate ignored, same precedent as FINDINGS.md's 2026-09-05 intraday
            # study -- irrelevant to whether the STOP MECHANICS get tested honestly, and
            # the gate has been shut for this entire 3-month cache window regardless
            candidate = detect_entry(ticker, rows, i, require_regime=False)
            if candidate is None:
                continue
            pattern, structural_low = candidate

            day0 = intraday[intraday.index.normalize() == entry_date]
            if day0.empty:
                continue
            trigger_price = row.high10_prior * 1.005
            crossed = day0[day0.High >= trigger_price]
            if crossed.empty:
                continue  # daily-Close-based fire, but intraday High never actually cleared it -- skip
            entry_bar_time = crossed.index[0]
            entry_price = trigger_price

            state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=entry_price,
                         structural_low=structural_low, target=None)
            stop_price = current_stop_level(pattern, state, row)

            next_date = rows.iloc[i + 1].Date
            path = intraday[(intraday.index > entry_bar_time) & (intraday.index.normalize() <= next_date)]

            touched_at = None
            day1_open = None
            for t, bar in path.iterrows():
                bar_date = t.normalize()
                if bar_date == entry_date:
                    if bar.Low <= stop_price:
                        touched_at = t
                        break
                elif bar_date == next_date:
                    day1_open = bar.Open
                    if bar.Low <= stop_price:
                        touched_at = t
                    break
                else:
                    break

            if touched_at is not None:
                exit_reason, exit_price = "sl_touched_before_open", stop_price
            elif day1_open is not None:
                exit_reason, exit_price = "day1_open", day1_open
            else:
                continue  # no day+1 intraday data available (edge of cache window) -- skip, not a real result either way

            results.append(dict(
                ticker=ticker, entry_date=entry_date, pattern=pattern,
                entry_price=entry_price, stop_price=stop_price,
                exit_reason=exit_reason, exit_price=exit_price,
                pnl_pct=(exit_price / entry_price - 1) * 100,
            ))

    out = pd.DataFrame(results)
    out.to_csv("runs/overnight_sl_realism.csv", index=False)
    print(f"n = {len(out)}")
    if out.empty:
        return
    print(out.exit_reason.value_counts())
    print()
    print(out.groupby("exit_reason").pnl_pct.agg(["count", "mean", "median"]))
    print()
    print(f"overall win rate: {(out.pnl_pct > 0).mean() * 100:.1f}%")
    print(f"overall median: {out.pnl_pct.median():.2f}%")
    print(f"overall mean: {out.pnl_pct.mean():.2f}%")


if __name__ == "__main__":
    run()
