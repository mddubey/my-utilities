"""Isolated research only (2026-09-14). User asked for a broader search of "better
support areas" -- extends the daily EMA34/SMA50 cascade check (which already showed a
clean, strong swing-discriminating pattern) to every other daily MA available in the
production dataframe: ema8, ema21, ema34, sma50, sma150, sma200. Same methodology as
wider_timeframe_support_check.py / full_pop_daily_cascade: walk forward from entry
through a 20-trading-day cap (or real swing exit), classify held/broke/never_touched,
on the FULL fresh-only population (n=467). SWING-side only (options already shown to
need the same-day-only window, tested separately in hourly_ema_actionable_window.py --
daily-level touches happen on timescales that, like the old 3-day hourly window, occur
after the options trade has already resolved, so they're not options-legitimate).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
MAX_WINDOW_DAYS = 20
LEVELS = ["ema8", "ema21", "ema34", "sma50", "sma150", "sma200"]


def run():
    df = pd.read_csv("runs/hourly_ema_support_recheck.csv", parse_dates=["entry_date"])
    df = df.dropna(subset=["swing_pnl_pct"]).copy()
    print(f"n = {len(df)}")

    cache = {}
    results = []
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

        row = dict(ticker=r.ticker, entry_date=r.entry_date, swing_pnl_pct=r.swing_pnl_pct)
        for col in LEVELS:
            if col not in window.columns or window[col].isna().all():
                row[col] = None
                continue
            touched = window.Low <= window[col]
            if not touched.any():
                row[col] = "never_touched"
                continue
            first_touch_idx = touched.idxmax()
            after = window.loc[first_touch_idx:]
            broke = (after.Close < after[col]).sum() > 1
            row[col] = "broke" if broke else "held"
        results.append(row)

    out = pd.DataFrame(results)
    out.to_csv("runs/daily_level_search.csv", index=False)
    print(f"n with data = {len(out)}\n")

    def concentration(s):
        total = s.sum()
        if not total:
            return float("nan")
        return s.sort_values(ascending=False).head(10).sum() / total * 100

    print("=== SWING discrimination by daily level (spread = never_touched win% - broke win%) ===")
    summary = []
    for col in LEVELS:
        rows = []
        for state in ["never_touched", "held", "broke"]:
            sub = out[out[col] == state]
            if len(sub) < 5:
                continue
            win = (sub.swing_pnl_pct > 0).mean() * 100
            med = sub.swing_pnl_pct.median()
            conc = concentration(sub.swing_pnl_pct)
            rows.append((state, len(sub), win, med, conc))
        if len(rows) < 2:
            continue
        nt = next((r for r in rows if r[0] == "never_touched"), None)
        bk = next((r for r in rows if r[0] == "broke"), None)
        spread = (nt[2] - bk[2]) if (nt and bk) else float("nan")
        summary.append((col, spread, rows))

    summary.sort(key=lambda x: -x[1] if x[1] == x[1] else 0)
    for col, spread, rows in summary:
        print(f"\n  {col}  (win-rate spread = {spread:+.1f}pp)")
        for state, n, win, med, conc in rows:
            print(f"    {state:<14} n={n:<4} win {win:5.1f}%  med {med:+.2f}%  conc {conc:.1f}%")


if __name__ == "__main__":
    run()
