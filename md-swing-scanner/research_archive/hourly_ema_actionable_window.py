"""Isolated research only (2026-09-14). Correctness check on hourly_ema_support_recheck.py:
that script classified the hourly EMA8/34 bucket using a 3-TRADING-DAY forward window
(entry day through entry+3 days), then correlated it against day1_pnl_pct (the day+1-open
options exit). But the options position is already closed at day+1's open -- so any part
of that 3-day window occurring on day+1 or day+2 is temporally AFTER the options trade
has already resolved. That's not a live-available signal for options; it's a same-underlying-
quality correlate, not a leading indicator. (Legitimate for SWING, where the position is
still open across those days -- just not for options.)

This recomputes the hourly EMA8/34 bucket using ONLY same-entry-day hourly bars (the only
window causally available before the day+1-open exit), and re-checks whether the options
ladder (79.4% / 70.2% / 56.1%) survives on the genuinely actionable window.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

TRIGGER_CLEARANCE = 1.005


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


def classify_bucket(hourly, entry_time, window_end_time):
    window = hourly[(hourly.index > entry_time) & (hourly.index <= window_end_time)]
    if window.empty:
        return None
    touched_ema8 = (window.Low <= window.ema8).any()
    touched_ema34 = (window.Low <= window.ema34).any()
    if not touched_ema8 and not touched_ema34:
        return "never touched"
    if touched_ema34:
        broke = (window.Close < window.ema34).any()
        return "touched EMA34, broke" if broke else "touched EMA34, held"
    return "touched EMA8 only"


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
    buckets = []
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
            buckets.append(None)
            continue
        entry_ts = pd.Timestamp(r.entry_date) + pd.Timedelta(hours=9, minutes=20)
        same_day_end_ts = pd.Timestamp(r.entry_date) + pd.Timedelta(hours=15, minutes=30)
        buckets.append(classify_bucket(hourly, entry_ts, same_day_end_ts))

    df["ema_bucket_actionable"] = buckets
    df.to_csv("runs/hourly_ema_actionable_window.csv", index=False)

    sub = df.dropna(subset=["ema_bucket_actionable", "day1_pnl_pct"])
    print(f"\nn with valid bucket = {len(sub)}\n")
    print("=== OPTIONS, same-entry-day-only window (the genuinely actionable one) ===")
    order = ["never touched", "touched EMA8 only", "touched EMA34, held", "touched EMA34, broke"]
    for b in order:
        s = sub[sub.ema_bucket_actionable == b]
        if len(s) < 5:
            continue
        win = (s.day1_pnl_pct > 0).mean() * 100
        print(f"  {b:<22} n={len(s):<4} ({len(s)/len(sub)*100:.1f}%)  OPTIONS win {win:5.1f}% med {s.day1_pnl_pct.median():+.2f}%")


if __name__ == "__main__":
    run()
