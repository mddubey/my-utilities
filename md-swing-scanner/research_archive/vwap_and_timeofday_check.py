"""Isolated research only (2026-09-12). Two new ideas from outside research, not yet
tested: (1) VWAP alignment at the breach moment -- is price above the day's own
volume-weighted average price, a standard intraday confirmation signal (distinct from
everything tried so far); (2) time-of-day of the breach -- research says morning
breakouts (10am-12pm) are more reliable than midday/early-afternoon ones (11:30am-2pm
"chop" territory prone to fakeouts)."""
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

            up_to_breach = day_bars[day_bars.index <= breach_time]
            typical = (up_to_breach.High + up_to_breach.Low + up_to_breach.Close) / 3
            vwap = (typical * up_to_breach.Volume).sum() / up_to_breach.Volume.sum() if up_to_breach.Volume.sum() else None
            above_vwap = trigger_price > vwap if vwap else None

            confirmed_by_close = row.Close >= trigger_price
            day1_open = rows.iloc[i + 1].Open
            day1_pnl_pct = (day1_open / trigger_price - 1) * 100

            results.append(dict(ticker=t, entry_date=entry_date, breach_time=breach_time,
                               above_vwap=above_vwap, hour=breach_time.hour,
                               confirmed_by_close=confirmed_by_close, day1_pnl_pct=day1_pnl_pct))

    out = pd.DataFrame(results)
    out.to_csv("runs/vwap_and_timeofday_check.csv", index=False)
    print(f"n = {len(out)}")
    print(f"baseline: win {(out.day1_pnl_pct>0).mean()*100:.1f}%  median {out.day1_pnl_pct.median():.2f}%")
    print()

    above = out[out.above_vwap == True]
    below = out[out.above_vwap == False]
    print(f"=== VWAP alignment ===")
    print(f"ABOVE VWAP (n={len(above)}, {len(above)/len(out)*100:.1f}%): win {(above.day1_pnl_pct>0).mean()*100:.1f}%  median {above.day1_pnl_pct.median():.2f}%")
    print(f"BELOW VWAP (n={len(below)}, {len(below)/len(out)*100:.1f}%): win {(below.day1_pnl_pct>0).mean()*100:.1f}%  median {below.day1_pnl_pct.median():.2f}%")
    print()

    print(f"=== Time-of-day of breach ===")
    def bucket(h):
        if h < 10: return "09:15-10:00 (open)"
        if h < 12: return "10:00-12:00 (morning)"
        if h < 14: return "12:00-14:00 (midday)"
        return "14:00-15:30 (close)"
    out["time_bucket"] = out.hour.apply(bucket)
    g = out.groupby("time_bucket").agg(
        n=("day1_pnl_pct", "count"),
        win_rate=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        median=("day1_pnl_pct", "median"),
    )
    print(g.reindex(["09:15-10:00 (open)", "10:00-12:00 (morning)", "12:00-14:00 (midday)", "14:00-15:30 (close)"]))


if __name__ == "__main__":
    run()
