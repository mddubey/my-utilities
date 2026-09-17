"""Isolated research only (2026-09-12). Multi-timeframe alignment check from the false-
breakout research: does the breach agree with the higher-timeframe (1-hour) trend, or is
it fighting it? For each real breach, find the most recently COMPLETED 1-hour bar strictly
before the breach moment, compute that ticker's 1H EMA8 as of that bar (same construction
already manually checked for PAYTM/LAURUSLABS/etc. earlier), and check whether price at the
breach moment is above or below it. Fully knowable at the moment of breach -- the EMA8 only
uses bars that have already closed.
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

            prior_h = h[h.index < breach_time]
            if len(prior_h) < 8:
                continue  # not enough 1H history yet for a stable EMA8
            ema8_now = prior_h.ema8.iloc[-1]
            above_1h_ema = trigger_price > ema8_now
            dist_from_1h_ema_pct = (trigger_price / ema8_now - 1) * 100

            confirmed_by_close = row.Close >= trigger_price
            day1_open = rows.iloc[i + 1].Open
            day1_pnl_pct = (day1_open / trigger_price - 1) * 100

            results.append(dict(ticker=t, entry_date=entry_date, above_1h_ema=above_1h_ema,
                               dist_from_1h_ema_pct=dist_from_1h_ema_pct,
                               confirmed_by_close=confirmed_by_close, day1_pnl_pct=day1_pnl_pct))

    out = pd.DataFrame(results)
    out.to_csv("runs/multi_timeframe_check.csv", index=False)
    print(f"n = {len(out)}")
    print(f"baseline: win {(out.day1_pnl_pct>0).mean()*100:.1f}%  median {out.day1_pnl_pct.median():.2f}%")
    print()
    above = out[out.above_1h_ema]
    below = out[~out.above_1h_ema]
    print(f"ABOVE 1H EMA8 (n={len(above)}, {len(above)/len(out)*100:.1f}%): "
          f"hold {above.confirmed_by_close.mean()*100:.1f}%  win {(above.day1_pnl_pct>0).mean()*100:.1f}%  median {above.day1_pnl_pct.median():.2f}%")
    print(f"BELOW 1H EMA8 (n={len(below)}, {len(below)/len(out)*100:.1f}%): "
          f"hold {below.confirmed_by_close.mean()*100:.1f}%  win {(below.day1_pnl_pct>0).mean()*100:.1f}%  median {below.day1_pnl_pct.median():.2f}%")
    print()
    print("=== distance-from-1H-EMA8 quartile (higher = further above, more room) ===")
    q = out.copy()
    q["q"] = pd.qcut(q.dist_from_1h_ema_pct.rank(method="first"), 4, labels=["Q1(below/near)", "Q2", "Q3", "Q4(furthest above)"])
    g = q.groupby("q", observed=True).agg(
        n=("day1_pnl_pct", "count"),
        win_rate=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        median=("day1_pnl_pct", "median"),
    )
    print(g)


if __name__ == "__main__":
    run()
