"""Isolated research only (2026-09-12). The real OIL-style test: yesterday's live fix
(_moving_away_on_volume in live_checkpoint.py) established that raw volume magnitude means
nothing without knowing which DIRECTION the price was moving while that volume traded --
OIL showed "STRONG volume" while actually breaking down, not building toward a breakout.
That fix only applies to PRE-breach ("watching") candidates via velocity_pct (a 10-min
snapshot delta). This builds the POST-breach equivalent: using real 5-min intraday bars,
split the volume accumulated from market open up to the breach moment into volume that
traded on UP-ticking bars (Close>Open, genuine buying pressure) vs DOWN-ticking bars
(Close<Open, selling/reversal volume) -- i.e. is the volume actually bullish or is a real
chunk of it contaminated by an earlier decline within the same session that happened to
resolve into a breach anyway.
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
            if up_to_breach.empty or up_to_breach.Volume.sum() == 0:
                continue

            up_bars = up_to_breach[up_to_breach.Close > up_to_breach.Open]
            bullish_vol_frac = up_bars.Volume.sum() / up_to_breach.Volume.sum() * 100

            confirmed_by_close = row.Close >= trigger_price
            day1_open = rows.iloc[i + 1].Open
            day1_pnl_pct = (day1_open / trigger_price - 1) * 100

            results.append(dict(ticker=t, entry_date=entry_date, bullish_vol_frac=bullish_vol_frac,
                               confirmed_by_close=confirmed_by_close, day1_pnl_pct=day1_pnl_pct))

    out = pd.DataFrame(results)
    out.to_csv("runs/bullish_vs_bearish_volume.csv", index=False)
    print(f"n = {len(out)}")
    print(f"baseline: win {(out.day1_pnl_pct>0).mean()*100:.1f}%  median {out.day1_pnl_pct.median():.2f}%")
    print()
    out["q"] = pd.qcut(out.bullish_vol_frac.rank(method="first"), 4, labels=["Q1(most bearish)", "Q2", "Q3", "Q4(most bullish)"])
    print("=== hold rate & day+1 by bullish-volume-fraction quartile ===")
    g = out.groupby("q", observed=True).agg(
        n=("day1_pnl_pct", "count"),
        hold_rate=("confirmed_by_close", lambda s: s.mean() * 100),
        win_rate=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        median=("day1_pnl_pct", "median"),
    )
    print(g)


if __name__ == "__main__":
    run()
