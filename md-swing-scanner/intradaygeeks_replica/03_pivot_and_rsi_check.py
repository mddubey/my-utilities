"""Stress-test three things, one at a time, against the existing daily-pinbar event
list (46,083 events from 01_daily_pinbar_weekly_support.py):

1. Daily pivot R1/R2 distance (the plain prior-day pivot)
2. Weekly pivot R1/R2 distance (this is what TradingView's "Auto" shows on a 1H chart --
   real, documented: https://www.tradingview.com/support/solutions/43000521824-)
3. Monthly pivot R1/R2 distance (this is what "Auto" shows on a DAILY chart -- same
   source; user suspects this is "too much," testing it anyway rather than assuming)
4. RSI(14) on the pinbar's own entry day -- reusing signals.py's real rsi() function,
   read-only, not re-derived.

Each is reported SEPARATELY (one dimension at a time, not combined), per the user's own
explicit instruction. Read-only against backtest.load() and signals.rsi(), nothing
written to production. Prior, worth keeping in mind: the main project's own past R1/R2
proximity research found it "real telemetry, not predictable enough pre-entry to act on"
-- a fair expectation here too, not a reason to skip testing.
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import numpy as np
import pandas as pd

from backtest import load
from signals import rsi as rsi_fn

HERE = Path(__file__).parent


def pivots_asof(daily_close_series, high, low, close, freq):
    """R1/R2 for a given resampling frequency, as-of the most recently COMPLETED
    period -- decision-time-safe, forward-filled onto daily dates. freq=None means
    plain daily pivots (prior day's own H/L/C, no resampling)."""
    if freq is None:
        H, L, C = high.shift(1), low.shift(1), close.shift(1)
        PP = (H + L + C) / 3
        return 2 * PP - L, PP + (H - L)  # R1, R2

    df = pd.DataFrame({"High": high, "Low": low, "Close": close})
    period = df.resample(freq).agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    PP = (period.High + period.Low + period.Close) / 3
    R1 = (2 * PP - period.Low).shift(1)
    R2 = (PP + (period.High - period.Low)).shift(1)
    R1_asof = R1.reindex(daily_close_series.index, method="ffill")
    R2_asof = R2.reindex(daily_close_series.index, method="ffill")
    return R1_asof, R2_asof


def build_features(events, universe_tickers):
    events = events.copy()
    events["date"] = pd.to_datetime(events["date"])
    by_ticker = {t: g.index.tolist() for t, g in events.groupby("ticker")}

    out = {c: np.nan for c in [
        "entry_close", "rsi14",
        "daily_r1_dist_pct", "daily_r2_dist_pct",
        "weekly_r1_dist_pct", "weekly_r2_dist_pct",
        "monthly_r1_dist_pct", "monthly_r2_dist_pct",
    ]}
    for c in out:
        events[c] = np.nan

    n_tickers = len(by_ticker)
    for idx, (t, row_idxs) in enumerate(by_ticker.items()):
        if (idx + 1) % 300 == 0:
            print(f"  {idx + 1}/{n_tickers} tickers", flush=True)
        try:
            df = load(t).reset_index()
        except FileNotFoundError:
            continue
        df = df.set_index("Date")
        close_s = df["Close"]
        r14 = rsi_fn(close_s, 14)

        d_r1, d_r2 = pivots_asof(close_s, df.High, df.Low, df.Close, None)
        w_r1, w_r2 = pivots_asof(close_s, df.High, df.Low, df.Close, "W-FRI")
        m_r1, m_r2 = pivots_asof(close_s, df.High, df.Low, df.Close, "ME")

        for ridx in row_idxs:
            dt = events.at[ridx, "date"]
            if dt not in df.index:
                continue
            c = df.at[dt, "Close"]
            events.at[ridx, "entry_close"] = c
            events.at[ridx, "rsi14"] = r14.get(dt, np.nan)
            for name, (r1s, r2s) in [("daily", (d_r1, d_r2)), ("weekly", (w_r1, w_r2)),
                                      ("monthly", (m_r1, m_r2))]:
                r1v, r2v = r1s.get(dt, np.nan), r2s.get(dt, np.nan)
                if pd.notna(r1v) and r1v > c:
                    events.at[ridx, f"{name}_r1_dist_pct"] = (r1v / c - 1) * 100
                if pd.notna(r2v) and r2v > c:
                    events.at[ridx, f"{name}_r2_dist_pct"] = (r2v / c - 1) * 100
    return events


def quintile_report(df, col, label):
    sub = df.dropna(subset=[col, "r_multiple"])
    if len(sub) < 50:
        print(f"{label}: n={len(sub)}, too thin to bucket")
        return
    sub = sub.copy()
    sub["bucket"] = pd.qcut(sub[col], 5, duplicates="drop")
    g = sub.groupby("bucket", observed=True).agg(
        n=("r_multiple", "size"),
        win_pct=("r_multiple", lambda x: (x > 0).mean() * 100),
        mean_r=("r_multiple", "mean"),
        median_dist=(col, "median"),
    )
    print(f"\n{label} (n={len(sub)} with this level above entry, out of {len(df)} total):")
    print(g.round(3).to_string())


def rsi_band_report(df):
    sub = df.dropna(subset=["rsi14", "r_multiple"]).copy()
    bands = [-1, 30, 50, 70, 101]
    labels = ["<30 (oversold)", "30-50", "50-70", ">70 (overbought)"]
    sub["band"] = pd.cut(sub.rsi14, bands, labels=labels)
    g = sub.groupby("band", observed=True).agg(
        n=("r_multiple", "size"),
        win_pct=("r_multiple", lambda x: (x > 0).mean() * 100),
        mean_r=("r_multiple", "mean"),
    )
    print(f"\nRSI(14) on entry day (n={len(sub)}):")
    print(g.round(3).to_string())


if __name__ == "__main__":
    events = pd.read_csv(HERE / "pinbar_weekly_support_results.csv")
    print(f"loaded {len(events)} events\n")

    events = build_features(events, None)
    events.to_csv(HERE / "pivot_and_rsi_features.csv", index=False)

    for name in ("daily", "weekly", "monthly"):
        quintile_report(events, f"{name}_r1_dist_pct", f"{name.upper()} R1 distance")
        quintile_report(events, f"{name}_r2_dist_pct", f"{name.upper()} R2 distance")

    rsi_band_report(events)
