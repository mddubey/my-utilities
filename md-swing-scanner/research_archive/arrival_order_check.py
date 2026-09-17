"""Isolated research only (2026-09-12). Real-time-honest version of the portfolio ranking
test: does taking the FIRST N candidates to breach each day (the realistic, first-come
strategy, since you don't know what's still coming later in the session) perform as well
as the retrospective "best N by freshness, sorted after the fact" version already tested?
Uses real intraday breach timestamps (5-min bars, intraday-cache window only) to get a
genuine chronological arrival order per day, not just the daily entry_date.
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
MAX_POSITIONS = 5


def run():
    fo_tickers = set(pd.read_csv("fo_universe.csv", header=None)[0])
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    cache_tickers = {p.stem for p in CACHE_DIR.glob("*.csv")}

    results = []
    for t in tickers:
        if t not in cache_tickers or t not in fo_tickers:
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
        for i in range(1, len(rows) - 1):
            row = rows.iloc[i]
            yday = rows.iloc[i - 1]
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

            if pd.isna(yday.rsi14) or pd.isna(yday.close_20ago) or not yday.close_20ago:
                continue
            momentum_20d = (yday.Close / yday.close_20ago - 1) * 100

            day1_open = rows.iloc[i + 1].Open
            day1_pnl_pct = (day1_open / trigger_price - 1) * 100

            results.append(dict(ticker=t, entry_date=entry_date, breach_time=breach_time,
                               yday_rsi14=yday.rsi14, yday_momentum_20d=momentum_20d,
                               day1_pnl_pct=day1_pnl_pct))

    out = pd.DataFrame(results)
    out["rsi_pct"] = out.yday_rsi14.rank(pct=True)
    out["mom_pct"] = out.yday_momentum_20d.rank(pct=True)
    out["freshness"] = 0.5 * out.rsi_pct + 0.5 * out.mom_pct
    out.to_csv("runs/arrival_order_check.csv", index=False)

    print(f"n = {len(out)} real intraday-timed breaches")

    first_picks, best_picks, correlations = [], [], []
    for day, group in out.groupby("entry_date"):
        n = len(group)
        if n < 2:
            continue
        by_time = group.sort_values("breach_time")
        by_fresh = group.sort_values("freshness")
        first_picks.append(by_time.iloc[:min(n, MAX_POSITIONS)])
        best_picks.append(by_fresh.iloc[:min(n, MAX_POSITIONS)])
        # correlation between arrival order and freshness rank, for days with enough spread
        if n >= 3:
            by_time = by_time.reset_index(drop=True)
            by_time["arrival_rank"] = by_time.index + 1
            fresh_rank = by_time.freshness.rank()
            correlations.append(by_time.arrival_rank.corr(fresh_rank, method="spearman"))

    first_df = pd.concat(first_picks)
    best_df = pd.concat(best_picks)

    print(f"\ndays with >=2 real breaches: {len(first_picks)}")
    print(f"avg Spearman correlation (arrival order vs freshness rank), n={len(correlations)}: "
          f"{pd.Series(correlations).mean():.3f}  (0 = no relationship, 1 = best always arrives first)")

    print(f"\n--- FIRST-ARRIVAL strategy (take earliest breaches, up to 5/day) ---")
    print(f"  n={len(first_df)}  win {(first_df.day1_pnl_pct>0).mean()*100:.1f}%  median {first_df.day1_pnl_pct.median():.2f}%")

    print(f"\n--- RETROSPECTIVE BEST-BY-FRESHNESS (the unrealistic, look-ahead version) ---")
    print(f"  n={len(best_df)}  win {(best_df.day1_pnl_pct>0).mean()*100:.1f}%  median {best_df.day1_pnl_pct.median():.2f}%")


if __name__ == "__main__":
    run()
