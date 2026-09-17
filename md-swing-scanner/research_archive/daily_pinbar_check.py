"""Isolated research only (2026-09-14). Daily-timeframe version of hourly_pinbar_check.py:
same "is the touch bar bullish / a clean pin-bar rejection" question, but on daily EMA8 and
EMA34, over the same 20-trading-day forward window used elsewhere (full_pop_daily_cascade,
wider_timeframe_support_check). Checked against BOTH day1 options outcome and real swing
outcome, per the standing rule -- expectation (per every other daily-vs-hourly result this
session) is that this will be swing-relevant, not options-relevant, since these touches can
occur well after the day+1-open options exit has already resolved.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

MAX_WINDOW_DAYS = 20
LEVELS = ["ema8", "ema34"]


def touch_bar_shape(window, level_col):
    touched = window.Low <= window[level_col]
    if not touched.any():
        return None
    bar = window.loc[touched.idxmax()]
    body = abs(bar.Close - bar.Open)
    lower_wick = min(bar.Open, bar.Close) - bar.Low
    bullish = bar.Close > bar.Open
    closed_above = bar.Close > bar[level_col]
    wick_ratio = lower_wick / body if body > 0 else float("inf")
    return dict(bullish=bool(bullish), closed_above=bool(closed_above), wick_ratio=wick_ratio)


def run():
    df = pd.read_csv("runs/hourly_ema_support_recheck.csv", parse_dates=["entry_date"])
    df = df.dropna(subset=["swing_pnl_pct"]).copy()
    print(f"n = {len(df)}")

    cache = {}
    rows = []
    for r in df.itertuples():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        daily = cache[r.ticker]
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        window = daily.iloc[i + 1: i + 1 + MAX_WINDOW_DAYS]
        if window.empty:
            continue
        row = dict(ticker=r.ticker, entry_date=r.entry_date,
                   day1_pnl_pct=r.day1_pnl_pct, swing_pnl_pct=r.swing_pnl_pct)
        for col in LEVELS:
            shape = touch_bar_shape(window, col)
            if shape is None:
                row[f"{col}_touched"] = False
            else:
                row[f"{col}_touched"] = True
                row[f"{col}_bullish"] = shape["bullish"]
                row[f"{col}_closed_above"] = shape["closed_above"]
                row[f"{col}_wick_ratio"] = shape["wick_ratio"]
        rows.append(row)

    out = pd.DataFrame(rows)
    out.to_csv("runs/daily_pinbar_check.csv", index=False)
    print(f"n with data = {len(out)}\n")

    def stats(s, label):
        if len(s) == 0:
            return
        o_win = (s.day1_pnl_pct > 0).mean() * 100
        s_win = (s.swing_pnl_pct > 0).mean() * 100
        print(f"  {label:<42} n={len(s):<4} OPTIONS win {o_win:5.1f}% med {s.day1_pnl_pct.median():+.2f}%   |   "
              f"SWING win {s_win:5.1f}% med {s.swing_pnl_pct.median():+.2f}%")

    for col in LEVELS:
        print(f"=== daily {col}: bullish vs bearish close at first touch ===")
        touched = out[out[f"{col}_touched"] == True]
        never = out[out[f"{col}_touched"] == False]
        stats(touched[touched[f"{col}_bullish"] == True], f"bullish close at {col} touch")
        stats(touched[touched[f"{col}_bullish"] == False], f"bearish close at {col} touch")
        for thresh in [1.5, 2.0]:
            s = touched[(touched[f"{col}_bullish"] == True) & (touched[f"{col}_closed_above"] == True) &
                        (touched[f"{col}_wick_ratio"] >= thresh)]
            stats(s, f"full pin bar, wick_ratio>={thresh}")
        stats(never, f"never touched {col}")
        print()


if __name__ == "__main__":
    run()
