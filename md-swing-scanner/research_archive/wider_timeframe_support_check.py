"""Isolated research only (2026-09-14). User hypothesis: within the "broke hourly
EMA34" bucket (worst-performing, 46.0% swing win rate), do the trades that STILL win
on the real swing metric find support at a WIDER timeframe instead (daily EMA8, daily
EMA34, or SMA50), rather than the hourly level? Multi-timeframe framing: hourly EMA34
spans ~5-6 trading days (short-week reference); daily EMA34 spans ~7 weeks
(short-month reference) -- if a trade's real structure lives on a wider timeframe,
breaking the hourly level wouldn't mean much, and the actual support test happens
later at a daily level instead.

Walks forward from entry through the real swing exit (or a 20-trading-day cap,
whichever comes first) checking whether daily Low touches ema8/ema34/sma50, and
whether it holds (closes back above) or breaks (closes below) -- correlated against
the real swing win/loss outcome already computed for this bucket.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
MAX_WINDOW_DAYS = 20


def run():
    df = pd.read_csv("runs/hourly_ema_support_recheck.csv", parse_dates=["entry_date"])
    broke = df[df.ema_bucket == "touched EMA34, broke"].dropna(subset=["swing_pnl_pct"]).copy()
    print(f"n = {len(broke)}")

    cache = {}
    results = []
    for r in broke.itertuples():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        rows = cache[r.ticker]
        match = rows.index[rows.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        window = rows.iloc[i + 1: i + 1 + MAX_WINDOW_DAYS]
        if window.empty:
            continue

        found = {"daily_ema8": None, "daily_ema34": None, "daily_sma50": None}
        for level_name, col in [("daily_ema8", "ema8"), ("daily_ema34", "ema34"), ("daily_sma50", "sma50")]:
            level_series = window[col]
            touched = window.Low <= level_series
            if not touched.any():
                continue
            first_touch_idx = touched.idxmax()
            # held = closed back above that level within 2 days of the touch, and never
            # closed meaningfully below it again in the rest of the window
            after = window.loc[first_touch_idx:]
            broke_close = (after.Close < after[col]).sum() > 1  # allow one noisy close, not a real break
            found[level_name] = "held" if not broke_close else "broke"

        any_support = any(v == "held" for v in found.values())
        results.append(dict(ticker=r.ticker, entry_date=r.entry_date, swing_pnl_pct=r.swing_pnl_pct,
                             swing_win=r.swing_pnl_pct > 0, **found, any_wider_support_held=any_support))

    out = pd.DataFrame(results)
    out.to_csv("runs/wider_timeframe_support_check.csv", index=False)
    print(f"n with data = {len(out)}\n")

    print("=== Did finding support at ANY wider daily level correlate with swing win? ===")
    for label, sub in [("found wider support (held)", out[out.any_wider_support_held]),
                        ("no wider support found", out[~out.any_wider_support_held])]:
        win = sub.swing_win.mean() * 100
        med = sub.swing_pnl_pct.median()
        print(f"  {label}: n={len(sub)}  swing win={win:.1f}%  median={med:+.2f}%")

    print("\n=== Breakdown by specific level ===")
    for col in ["daily_ema8", "daily_ema34", "daily_sma50"]:
        for state in ["held", "broke"]:
            sub = out[out[col] == state]
            if len(sub) < 5:
                continue
            win = sub.swing_win.mean() * 100
            med = sub.swing_pnl_pct.median()
            print(f"  {col}={state}: n={len(sub)}  swing win={win:.1f}%  median={med:+.2f}%")
        never = out[out[col].isna()]
        print(f"  {col}=never touched: n={len(never)}  swing win={never.swing_win.mean()*100:.1f}%  median={never.swing_pnl_pct.median():+.2f}%")


if __name__ == "__main__":
    run()
