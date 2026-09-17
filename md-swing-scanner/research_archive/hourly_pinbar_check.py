"""Isolated research only (2026-09-14). User's specific, named hypothesis: it's not just
"touched hourly EMA8" that matters -- it's whether the touching bar is a bullish PIN BAR
(long lower wick, closes back above the EMA, bullish body) i.e. a clean rejection/hold,
vs. a plain dip that may or may not mean anything. Isolates the FIRST touch bar (same-day
actionable window only, matching hourly_ema_actionable_window.py's fix for the day+1-open
options exit) and classifies its shape, rather than just whether a touch happened at all.

Pin bar definition (on the touch bar for a given level):
  bullish       = Close > Open
  closed_above  = Close > level (rejected back above the EMA, not just touched and stayed under)
  lower_wick    = min(Open, Close) - Low
  body          = abs(Close - Open)
  wick_ratio    = lower_wick / body if body > 0 else large
  is_pin_bar    = bullish and closed_above and wick_ratio >= PIN_WICK_RATIO
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import intraday_cache
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

PIN_WICK_RATIO = 1.5


def freshness(rsi14, mom20):
    if pd.isna(rsi14) or pd.isna(mom20):
        return None
    rsi_pct = _percentile_from_breaks(rsi14, RSI_PCT_BREAKS)
    mom_pct = _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)
    return 0.5 * rsi_pct + 0.5 * mom_pct


def hourly_ema(intraday_5m):
    hourly = intraday_5m.resample("60min", origin="start_day").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna(subset=["Close"])
    hourly["ema8"] = hourly.Close.ewm(span=8, adjust=False).mean()
    hourly["ema34"] = hourly.Close.ewm(span=34, adjust=False).mean()
    return hourly


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
    is_pin = bool(bullish and closed_above and wick_ratio >= PIN_WICK_RATIO)
    return is_pin


def run():
    tod = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    feat = pd.read_csv("runs/consolidation_and_room.csv", parse_dates=["entry_date"])[
        ["ticker", "entry_date", "yday_rsi14", "yday_momentum_20d"]]
    df = tod.merge(feat, on=["ticker", "entry_date"], how="inner").dropna(subset=["yday_rsi14", "yday_momentum_20d"])
    df["freshness_score"] = df.apply(lambda r: freshness(r.yday_rsi14, r.yday_momentum_20d), axis=1)
    fresh_cut = df.freshness_score.median()
    df = df[df.freshness_score <= fresh_cut].copy()
    print(f"n (fresh-only) = {len(df)}")

    cache = {}
    pin_ema8, pin_ema34 = [], []
    for r in df.itertuples():
        if r.ticker not in cache:
            try:
                intraday = intraday_cache.load(r.ticker)
                idx5 = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
                intraday = intraday.set_axis(idx5)
                hourly = hourly_ema(intraday)
            except FileNotFoundError:
                hourly = None
            cache[r.ticker] = hourly
        hourly = cache[r.ticker]
        if hourly is None:
            pin_ema8.append(None); pin_ema34.append(None)
            continue
        entry_ts = pd.Timestamp(r.entry_date) + pd.Timedelta(hours=9, minutes=20)
        same_day_end_ts = pd.Timestamp(r.entry_date) + pd.Timedelta(hours=15, minutes=30)
        window = hourly[(hourly.index > entry_ts) & (hourly.index <= same_day_end_ts)]
        if window.empty:
            pin_ema8.append(None); pin_ema34.append(None)
            continue
        pin_ema8.append(touch_bar_shape(window, "ema8"))
        pin_ema34.append(touch_bar_shape(window, "ema34"))

    df["pin_ema8"] = pin_ema8
    df["pin_ema34"] = pin_ema34
    df.to_csv("runs/hourly_pinbar_check.csv", index=False)

    def stats(sub, label):
        win = (sub.day1_pnl_pct > 0).mean() * 100
        med = sub.day1_pnl_pct.median()
        print(f"  {label:<38} n={len(sub):<4} OPTIONS win {win:5.1f}% med {med:+.2f}%")

    print("\n=== Among trades that touched hourly EMA8 same-day: pin bar vs plain dip ===")
    touched8 = df[df.pin_ema8.notna()]
    stats(touched8[touched8.pin_ema8 == True], "pin bar at EMA8 touch")
    stats(touched8[touched8.pin_ema8 == False], "plain dip at EMA8 touch (no pin)")

    print("\n=== Among trades that touched hourly EMA34 same-day: pin bar vs plain dip ===")
    touched34 = df[df.pin_ema34.notna()]
    stats(touched34[touched34.pin_ema34 == True], "pin bar at EMA34 touch")
    stats(touched34[touched34.pin_ema34 == False], "plain dip at EMA34 touch (no pin)")

    print("\n=== Reference: never touched either level same-day ===")
    never = df[df.pin_ema8.isna() & df.pin_ema34.isna()]
    stats(never, "never touched")


if __name__ == "__main__":
    run()
