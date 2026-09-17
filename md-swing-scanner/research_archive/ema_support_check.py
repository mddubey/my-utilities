"""Isolated research only (2026-09-12). Refined multi-timeframe check per direct feedback:
not "is price above the 1H EMA8" (trivially always true for a fresh breakout, already
found) but "did price actually TEST the EMA8 as support and hold, at any point that day up
to the breach moment" -- a genuine support-and-bounce signature, vs a stock that just
floats above without ever being challenged. Touch tolerance matches the earlier manual
PAYTM/LAURUSLABS check (Low within 0.3% of EMA8, Close still above it).
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots
from signals import base_filters_pass

CACHE_DIR = Path("intraday_cache")
TRIGGER_CLEARANCE = 1.005
TOUCH_TOLERANCE = 0.003  # 0.3%, same as the earlier manual check


def hourly_ema8(ticker_intraday):
    h = ticker_intraday.resample("1h", origin=ticker_intraday.index[0]).agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    h["ema8"] = h["Close"].ewm(span=8, adjust=False).mean()
    return h


def run():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    cache_tickers = {p.stem for p in CACHE_DIR.glob("*.csv")}

    results = []
    for t in tickers:
        if t not in cache_tickers:
            continue
        try:
            df = backtest.load(t, daily_pivots)
        except FileNotFoundError:
            continue
        try:
            intraday = intraday_cache.load(t)
        except FileNotFoundError:
            continue
        if intraday.empty:
            continue
        intraday = intraday.copy()
        intraday.index = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
        cache_min, cache_max = intraday.index.min().normalize(), intraday.index.max().normalize()

        h = hourly_ema8(intraday)

        rows = df.reset_index()
        for i in range(len(rows) - 1):
            row = rows.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            entry_date = row.Date
            if entry_date < cache_min or entry_date > cache_max:
                continue
            if not base_filters_pass(row):
                continue
            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger_price:
                continue

            day_bars = intraday[intraday.index.normalize() == entry_date]
            if day_bars.empty:
                continue
            crossed = day_bars[day_bars.High >= trigger_price]
            if crossed.empty:
                continue
            breach_time = crossed.index[0]

            # today's own 1H bars, up to and including the hour of the breach
            today_h = h[(h.index.normalize() == entry_date) & (h.index <= breach_time)]
            if today_h.empty or len(h[h.index < today_h.index[0]]) < 8:
                continue  # not enough prior 1H history for a stable EMA8

            tested_and_held = False
            for _, bar in today_h.iterrows():
                if bar.ema8 <= 0:
                    continue
                touched = bar.Low <= bar.ema8 * (1 + TOUCH_TOLERANCE)
                held = bar.Close > bar.ema8
                if touched and held:
                    tested_and_held = True
                    break

            confirmed_by_close = row.Close >= trigger_price
            day1_open = rows.iloc[i + 1].Open
            day1_pnl_pct = (day1_open / trigger_price - 1) * 100

            results.append(dict(ticker=t, entry_date=entry_date, tested_and_held=tested_and_held,
                               confirmed_by_close=confirmed_by_close, day1_pnl_pct=day1_pnl_pct))

    out = pd.DataFrame(results)
    out.to_csv("runs/ema_support_check.csv", index=False)
    print(f"n = {len(out)}")
    print(f"baseline: win {(out.day1_pnl_pct>0).mean()*100:.1f}%  median {out.day1_pnl_pct.median():.2f}%")
    print()
    tested = out[out.tested_and_held]
    untested = out[~out.tested_and_held]
    print(f"TESTED 1H EMA8 and held (n={len(tested)}, {len(tested)/len(out)*100:.1f}%): "
          f"hold {tested.confirmed_by_close.mean()*100:.1f}%  win {(tested.day1_pnl_pct>0).mean()*100:.1f}%  median {tested.day1_pnl_pct.median():.2f}%")
    print(f"NEVER tested (just floated, n={len(untested)}, {len(untested)/len(out)*100:.1f}%): "
          f"hold {untested.confirmed_by_close.mean()*100:.1f}%  win {(untested.day1_pnl_pct>0).mean()*100:.1f}%  median {untested.day1_pnl_pct.median():.2f}%")


if __name__ == "__main__":
    run()
