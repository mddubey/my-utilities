"""Isolated research only (2026-09-14). Re-check of the 2026-09-02 hourly EMA8/34
support/pin-bar test -- "does a next-few-day pullback that touches (or closes below)
the hourly EMA8/34 mean anything." Original verdict was genuinely inconclusive, not
rejected: every bucket was too thin (n<105, wild concentration) on the ~2.5-month
intraday_cache window available then. The cache now spans 93 days (June 10-Sept 11),
a real if modest increase. Also, per the standing rule established this session,
conditions on Freshness first rather than testing the raw population.

Bucket definitions match the original daily-EMA test exactly, just on hourly bars:
never touched EMA8 or EMA34 in the 3 trading days after entry / touched EMA8 only
(shallow) / touched EMA34, closed back above it (held) / touched EMA34, closed below
it (broke) -- checked on the hourly Close series, not 5-min, matching the "hourly"
framing of the original test.
"""
import time
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

TRIGGER_CLEARANCE = 1.005
WINDOW_TRADING_DAYS = 3


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
    swing_pnl, buckets = [], []
    t0 = time.time()
    for idx, r in enumerate(df.itertuples(), 1):
        if idx % 100 == 0:
            print(f"  {idx}/{len(df)}  ({time.time()-t0:.0f}s)", flush=True)
        if r.ticker not in cache:
            daily = backtest.load(r.ticker, daily_pivots).reset_index()
            try:
                intraday = intraday_cache.load(r.ticker)
                idx5 = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
                intraday = intraday.set_axis(idx5)
                hourly = hourly_ema(intraday)
            except FileNotFoundError:
                hourly = None
            cache[r.ticker] = (daily, hourly)
        daily, hourly = cache[r.ticker]

        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0 or match[0] + 1 >= len(daily):
            swing_pnl.append(None); buckets.append(None)
            continue
        i = match[0]
        trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE

        state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, structural_low=0.0, target=None)
        exit_price = None
        for j in range(i + 1, len(daily)):
            row = daily.iloc[j]
            if row.corp_action_day:
                exit_price = state["peak_close"]; break
            exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=True)
            if exit_reason is not None:
                exit_price = row.Close; break
        if exit_price is None:
            exit_price = daily.iloc[-1].Close
        swing_pnl.append((exit_price / trigger - 1) * 100)

        if hourly is None:
            buckets.append(None)
            continue
        entry_ts = pd.Timestamp(r.entry_date) + pd.Timedelta(hours=9, minutes=20)
        window_end_date = daily.iloc[min(i + WINDOW_TRADING_DAYS, len(daily) - 1)].Date
        window_end_ts = pd.Timestamp(window_end_date) + pd.Timedelta(hours=15, minutes=30)
        buckets.append(classify_bucket(hourly, entry_ts, window_end_ts))

    df["swing_pnl_pct"] = swing_pnl
    df["ema_bucket"] = buckets
    df.to_csv("runs/hourly_ema_support_recheck.csv", index=False)

    sub = df.dropna(subset=["ema_bucket", "swing_pnl_pct"])
    print(f"\nn with valid bucket = {len(sub)}\n")
    g = sub.groupby("ema_bucket").agg(
        n=("day1_pnl_pct", "count"),
        pct_of_total=("day1_pnl_pct", lambda s: len(s) / len(sub) * 100),
        opt_win=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        opt_med=("day1_pnl_pct", "median"),
        swing_win=("swing_pnl_pct", lambda s: (s > 0).mean() * 100),
        swing_med=("swing_pnl_pct", "median"),
    )
    order = ["never touched", "touched EMA8 only", "touched EMA34, held", "touched EMA34, broke"]
    for b in order:
        if b in g.index:
            row = g.loc[b]
            print(f"  {b:<22} n={int(row.n):<4} ({row.pct_of_total:.1f}%)  OPTIONS win {row.opt_win:5.1f}% med {row.opt_med:+.2f}%   |   "
                  f"SWING win {row.swing_win:5.1f}% med {row.swing_med:+.2f}%")

    def concentration(s):
        total = s.sum()
        if not total:
            return float("nan")
        return s.sort_values(ascending=False).head(10).sum() / total * 100
    print("\n=== concentration check per bucket (options metric) ===")
    for b in order:
        if b in sub.ema_bucket.values:
            s = sub[sub.ema_bucket == b].day1_pnl_pct
            print(f"  {b}: n={len(s)}  concentration={concentration(s):.1f}%")


if __name__ == "__main__":
    run()
