"""Isolated research only (2026-09-12). "Signal 1" at scale: does the close position of
the BREACH CANDLE ITSELF (the single 5-min bar where price first crosses the trigger) --
(Close-Low)/(High-Low) of that one bar -- predict day+1 outcome? Fully knowable the moment
that bar closes, no lookahead. Real, illustrative cases already checked individually: OIL
(9% close position, textbook fakeout) vs PAYTM/GRANULES (91%/95%, strong) vs LAURUSLABS
(85%, strong breach candle that still faded later in the session for unrelated reasons).
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
            bar = crossed.iloc[0]
            rng = bar.High - bar.Low
            if rng <= 0:
                continue
            close_pos = (bar.Close - bar.Low) / rng * 100

            confirmed_by_close = row.Close >= trigger_price
            day1_open = rows.iloc[i + 1].Open
            day1_pnl_pct = (day1_open / trigger_price - 1) * 100

            results.append(dict(ticker=t, entry_date=entry_date, close_pos=close_pos,
                               confirmed_by_close=confirmed_by_close, day1_pnl_pct=day1_pnl_pct))

    out = pd.DataFrame(results)
    out.to_csv("runs/breach_candle_quality.csv", index=False)
    print(f"n = {len(out)}")
    print(f"baseline: win {(out.day1_pnl_pct>0).mean()*100:.1f}%  median {out.day1_pnl_pct.median():.2f}%")
    print()
    out["q"] = pd.qcut(out.close_pos.rank(method="first"), 4, labels=["Q1(weak/wick)", "Q2", "Q3", "Q4(strong)"])
    g = out.groupby("q", observed=True).agg(
        n=("day1_pnl_pct", "count"),
        hold_rate=("confirmed_by_close", lambda s: s.mean() * 100),
        win_rate=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        median=("day1_pnl_pct", "median"),
    )
    print("=== quartile breakdown ===")
    print(g)
    print()
    print("=== concentration sweep ===")
    for pct in [0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 0.90]:
        cut = out.close_pos.quantile(1 - pct)
        top = out[out.close_pos >= cut]
        total = top.day1_pnl_pct.sum()
        top10 = top.day1_pnl_pct.sort_values(ascending=False).head(10).sum()
        conc = top10 / total * 100 if total else float("nan")
        win = (top.day1_pnl_pct > 0).mean() * 100
        med = top.day1_pnl_pct.median()
        print(f"  top {int(pct*100)}% close_pos (n={len(top)}): win {win:.1f}%  median {med:.2f}%  concentration {conc:.1f}%")


if __name__ == "__main__":
    run()
