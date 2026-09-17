"""Isolated research only (2026-09-14). Tests the user's specific combo hypothesis:
- OPTIONS/intraday: hourly EMA34 = entry confirmation (already validated), daily EMA8
  (prior close) = overall trend support/context.
- SWING: daily EMA34 = entry confirmation (already validated), weekly EMA8 (last
  completed week) = overall trend support/context.

Note up front (from web research): the standard multi-timeframe EMA convention is
either (a) same period checked across timeframes for alignment, or (b) faster EMA =
entry trigger, slower EMA (21/34) = trend anchor, on the SAME timeframe -- nobody
swaps which period sits on which timeframe the way this hypothesis does. Testing
anyway since it's a clean, cheap check and the user's own hourly result (EMA8-touch
best, EMA34-break worst) already matches the "8=shallow/fine, 34=structural" reading
on a single timeframe; this asks whether ALSO requiring the next-timeframe-up's 8 EMA
to be supportive adds anything.

No-lookahead convention: ema8/ema34/sma50 columns in backtest.load()'s daily frame are
computed off THAT day's own close (contemporaneous) -- so "support level at entry" uses
the PRIOR day's value (or prior completed week's value for the weekly leg), matching
this project's yday_* convention elsewhere.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005


def weekly_ema8_asof(daily, entry_date):
    """Last COMPLETED week's EMA8 (Close, span=8) strictly before entry_date's week."""
    hist = daily[daily.Date < entry_date]
    if len(hist) < 8 * 5:  # need a handful of completed weeks
        return None
    weekly = hist.set_index("Date").Close.resample("W-FRI").last().dropna()
    if len(weekly) < 8:
        return None
    # drop the most recent weekly bar if it's the (possibly partial) current week
    weekly_ema8 = weekly.ewm(span=8, adjust=False).mean()
    return weekly_ema8.iloc[-1]


def run():
    df = pd.read_csv("runs/hourly_ema_support_recheck.csv", parse_dates=["entry_date"])
    cascade = pd.read_csv("runs/full_pop_daily_cascade.csv", parse_dates=["entry_date"])[
        ["ticker", "entry_date", "daily_ema34"]]
    df = df.merge(cascade, on=["ticker", "entry_date"], how="inner").dropna(subset=["ema_bucket", "swing_pnl_pct"])
    print(f"n = {len(df)}")

    cache = {}
    daily_ema8_support, weekly_ema8_support = [], []
    for r in df.itertuples():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        daily = cache[r.ticker]
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0 or match[0] == 0:
            daily_ema8_support.append(None); weekly_ema8_support.append(None)
            continue
        i = match[0]
        trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
        prior_ema8 = daily.iloc[i - 1].ema8
        daily_ema8_support.append("above" if trigger > prior_ema8 else "below")

        w_ema8 = weekly_ema8_asof(daily, r.entry_date)
        weekly_ema8_support.append(None if w_ema8 is None else ("above" if trigger > w_ema8 else "below"))

    df["daily_ema8_support"] = daily_ema8_support
    df["weekly_ema8_support"] = weekly_ema8_support
    df.to_csv("runs/ema_combo_check.csv", index=False)

    def stats(sub, label, col):
        o_win = (sub.day1_pnl_pct > 0).mean() * 100
        o_med = sub.day1_pnl_pct.median()
        s_win = (sub.swing_pnl_pct > 0).mean() * 100
        s_med = sub.swing_pnl_pct.median()
        print(f"  {label:<48} n={len(sub):<4} OPTIONS win {o_win:5.1f}% med {o_med:+.2f}%   |   SWING win {s_win:5.1f}% med {s_med:+.2f}%")

    print("\n=== OPTIONS combo: hourly EMA34 bucket x daily EMA8 support (prior close) ===")
    for bucket in ["touched EMA8 only", "touched EMA34, held", "touched EMA34, broke"]:
        for support in ["above", "below"]:
            sub = df[(df.ema_bucket == bucket) & (df.daily_ema8_support == support)]
            if len(sub) >= 5:
                stats(sub, f"{bucket} + daily_ema8={support}", None)

    print("\n=== SWING combo: daily EMA34 bucket x weekly EMA8 support (last completed week) ===")
    for bucket in ["never_touched", "held", "broke"]:
        for support in ["above", "below"]:
            sub = df[(df.daily_ema34 == bucket) & (df.weekly_ema8_support == support)]
            if len(sub) >= 5:
                stats(sub, f"daily_ema34={bucket} + weekly_ema8={support}", None)


if __name__ == "__main__":
    run()
