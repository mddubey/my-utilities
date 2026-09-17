"""Isolated research only (2026-09-14). Extends the wider-timeframe-support idea one
level down: within the "touched EMA34, broke" hourly bucket (worst-performing hourly
bucket, n=239), does an hourly SMA50 (~50 hours = ~8 trading days, genuinely wider
than hourly EMA34's ~5-6 trading days) catch support that hourly EMA34 missed?

Mirrors wider_timeframe_support_check.py exactly, one timeframe down: there we checked
whether trades that broke the HOURLY EMA34 found support at a DAILY level instead; here
we check whether they found support at a WIDER-HOURLY level (SMA50) instead, before
ever reaching a full trading day. Checked against BOTH day1 options outcome (this is
still inside the hourly/intraday frame, so options-relevant) and swing outcome, per the
standing "check both" rule.

Window: WINDOW_TRADING_DAYS=10 trading days forward from entry (~62 hourly bars),
enough room for a ~50-period hourly SMA to plausibly be tested at least once.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots

WINDOW_TRADING_DAYS = 10


def hourly_with_sma(intraday_5m):
    hourly = intraday_5m.resample("60min", origin="start_day").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna(subset=["Close"])
    hourly["ema34"] = hourly.Close.ewm(span=34, adjust=False).mean()
    hourly["sma50"] = hourly.Close.rolling(50).mean()
    return hourly


def classify_support(window, col):
    level = window[col]
    touched = window.Low <= level
    if not touched.any() or level.isna().all():
        return None
    first_touch_idx = touched.idxmax()
    after = window.loc[first_touch_idx:]
    broke = (after.Close < after[col]).sum() > 1  # allow one noisy close, not a real break
    return "held" if not broke else "broke"


def run():
    df = pd.read_csv("runs/hourly_ema_support_recheck.csv", parse_dates=["entry_date"])
    broke = df[df.ema_bucket == "touched EMA34, broke"].dropna(subset=["swing_pnl_pct", "day1_pnl_pct"]).copy()
    print(f"n (touched EMA34, broke) = {len(broke)}")

    hourly_cache = {}
    daily_cache = {}
    results = []
    for r in broke.itertuples():
        if r.ticker not in hourly_cache:
            try:
                intraday = intraday_cache.load(r.ticker)
                idx = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
                intraday = intraday.set_axis(idx)
                hourly_cache[r.ticker] = hourly_with_sma(intraday)
            except FileNotFoundError:
                hourly_cache[r.ticker] = None
        hourly = hourly_cache[r.ticker]
        if hourly is None:
            continue

        if r.ticker not in daily_cache:
            daily_cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        daily = daily_cache[r.ticker]
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        window_end_date = daily.iloc[min(i + WINDOW_TRADING_DAYS, len(daily) - 1)].Date

        entry_ts = pd.Timestamp(r.entry_date) + pd.Timedelta(hours=9, minutes=20)
        window_end_ts = pd.Timestamp(window_end_date) + pd.Timedelta(hours=15, minutes=30)
        window = hourly[(hourly.index > entry_ts) & (hourly.index <= window_end_ts)]
        if window.empty:
            continue

        state = classify_support(window, "sma50")
        results.append(dict(ticker=r.ticker, entry_date=r.entry_date, day1_pnl_pct=r.day1_pnl_pct,
                             swing_pnl_pct=r.swing_pnl_pct, hourly_sma50=state))

    out = pd.DataFrame(results)
    out.to_csv("runs/hourly_wider_support_check.csv", index=False)
    print(f"n with data = {len(out)}\n")

    def concentration(s):
        total = s.sum()
        if not total:
            return float("nan")
        return s.sort_values(ascending=False).head(10).sum() / total * 100

    print("=== hourly SMA50 (~8 trading days) support check, within 'touched EMA34, broke' bucket ===")
    for state in ["held", "broke"]:
        sub = out[out.hourly_sma50 == state]
        if len(sub) == 0:
            continue
        o_win = (sub.day1_pnl_pct > 0).mean() * 100
        s_win = (sub.swing_pnl_pct > 0).mean() * 100
        print(f"  hourly_sma50={state:<6} n={len(sub):<4} "
              f"OPTIONS win {o_win:5.1f}% med {sub.day1_pnl_pct.median():+.2f}% conc {concentration(sub.day1_pnl_pct):.1f}%   |   "
              f"SWING win {s_win:5.1f}% med {sub.swing_pnl_pct.median():+.2f}% conc {concentration(sub.swing_pnl_pct):.1f}%")
    never = out[out.hourly_sma50.isna()]
    o_win = (never.day1_pnl_pct > 0).mean() * 100
    s_win = (never.swing_pnl_pct > 0).mean() * 100
    print(f"  hourly_sma50=never n={len(never):<4} "
          f"OPTIONS win {o_win:5.1f}% med {never.day1_pnl_pct.median():+.2f}% conc {concentration(never.day1_pnl_pct):.1f}%   |   "
          f"SWING win {s_win:5.1f}% med {never.swing_pnl_pct.median():+.2f}% conc {concentration(never.swing_pnl_pct):.1f}%")


if __name__ == "__main__":
    run()
