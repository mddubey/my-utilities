"""Isolated research only (2026-09-12). The proper version of bullish_vs_bearish_volume_check.py
-- uses the standard Chaikin Money Flow construction instead of a crude Close-vs-Open bar
split: each 5-min bar's Money Flow Multiplier = ((Close-Low)-(High-Close))/(High-Low) (in
[-1,+1], zero-range bars treated as 0 -- no directional info), weighted by that bar's Volume,
summed from market open to the breach moment, then CMF = sum(money flow volume) / sum(volume).
Positive = net real buying pressure behind the volume; negative = net selling pressure even
though the stock is touching/crossing the trigger -- the actual OIL-type warning sign.
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
            up_to_breach = day_bars[day_bars.index <= breach_time].copy()
            if up_to_breach.empty or up_to_breach.Volume.sum() == 0:
                continue

            rng = up_to_breach.High - up_to_breach.Low
            mult = ((up_to_breach.Close - up_to_breach.Low) - (up_to_breach.High - up_to_breach.Close)) / rng
            mult = mult.where(rng > 0, 0.0)
            mfv = mult * up_to_breach.Volume
            cmf = mfv.sum() / up_to_breach.Volume.sum()

            confirmed_by_close = row.Close >= trigger_price
            day1_open = rows.iloc[i + 1].Open
            day1_pnl_pct = (day1_open / trigger_price - 1) * 100

            results.append(dict(ticker=t, entry_date=entry_date, cmf=cmf,
                               confirmed_by_close=confirmed_by_close, day1_pnl_pct=day1_pnl_pct))

    out = pd.DataFrame(results)
    out.to_csv("runs/cmf_check.csv", index=False)
    print(f"n = {len(out)}")
    print(f"baseline: win {(out.day1_pnl_pct>0).mean()*100:.1f}%  median {out.day1_pnl_pct.median():.2f}%")
    print()
    out["q"] = pd.qcut(out.cmf.rank(method="first"), 4, labels=["Q1(most selling)", "Q2", "Q3", "Q4(most buying)"])
    g = out.groupby("q", observed=True).agg(
        n=("day1_pnl_pct", "count"),
        hold_rate=("confirmed_by_close", lambda s: s.mean() * 100),
        win_rate=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        median=("day1_pnl_pct", "median"),
    )
    print("=== quartile breakdown ===")
    print(g)
    print()
    print("=== concentration check, sweeping the threshold ===")
    for pct in [0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 0.90]:
        cut = out.cmf.quantile(1 - pct)
        top = out[out.cmf >= cut]
        total = top.day1_pnl_pct.sum()
        top10 = top.day1_pnl_pct.sort_values(ascending=False).head(10).sum()
        conc = top10 / total * 100 if total else float("nan")
        win = (top.day1_pnl_pct > 0).mean() * 100
        med = top.day1_pnl_pct.median()
        print(f"  top {int(pct*100)}% CMF (n={len(top)}): win {win:.1f}%  median {med:.2f}%  concentration {conc:.1f}%")


if __name__ == "__main__":
    run()
