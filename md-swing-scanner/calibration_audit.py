"""Probability Calibration Audit (2026-09-08) — the critic's final pre-freeze
research task: verify that live_checkpoint.py's FIRE_RATE_BY_DISTANCE table (the
fire_pct shown on every watching candidate) is genuinely calibrated, not just an
in-sample fit to the same data it's applied to.

The original table (FINDINGS.md, 2026-09-06) was built and immediately used on
the SAME 62-day pooled dataset — the only robustness check done was splitting by
CHECKPOINT TIME (09:20 vs 09:40), never by TIME PERIOD. That leaves two real
gaps: (1) in-sample fit, no genuine held-out check; (2) thin buckets (n=25-150
for the tightest distance bands) with no confidence interval shown alongside the
displayed percentage.

This script rebuilds the same (distance, fired) dataset from scratch (the
original generation script wasn't saved anywhere), splits it by DATE into two
halves, builds a calibration table on the FIRST half only, then checks whether
the SECOND half's observed fire rates land near what the first half predicted
per bucket — the actual reliability-curve construction, not just a shape check.

"Fires" is defined exactly as live_checkpoint.py's own tier-1/2 classification
does it: the day's real (fully-realized) High reaching trigger_low
(high10_prior * 1.003) at some point during the session — checkpoint-
independent by construction, since it's a single per-(ticker, day) ground truth
checked against multiple checkpoints' distances.
"""
import sys
from datetime import time as dtime
from pathlib import Path

import pandas as pd

from backtest import load
from pivots import daily_pivots
from daily_scan import _passes_primed_checks
from live_checkpoint import TRIGGER_CLEARANCE_LOW

INTRADAY_CACHE_DIR = Path(__file__).parent / "intraday_cache"
CHECKPOINTS = ["09:20", "09:25", "09:30", "09:35", "09:40", "09:45"]
DISTANCE_BUCKETS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0, float("inf")]


def _bucket(dist_pct):
    for upper in DISTANCE_BUCKETS:
        if dist_pct <= upper:
            return upper
    return DISTANCE_BUCKETS[-1]


def _load_intraday(ticker):
    """Returns (df, naive_day_index) -- df's own index stays tz-aware Asia/Kolkata
    (needed for .time comparisons against a cutoff), naive_day_index is the
    matching tz-naive calendar-day Series used to match against daily_df's
    tz-naive Date column."""
    path = INTRADAY_CACHE_DIR / f"{ticker}.csv"
    if not path.exists():
        return None, None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if df.empty:
        return None, None
    df.index = df.index.tz_convert("Asia/Kolkata")
    naive_day = df.index.tz_localize(None).normalize()
    return df, naive_day


def build_dataset(tickers, verbose=False):
    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 50 == 0:
            print(f"  {n}/{len(tickers)} tickers processed, {len(rows)} obs so far", file=sys.stderr)
        try:
            daily_df = load(t, daily_pivots)
        except FileNotFoundError:
            continue
        intraday_df, naive_day = _load_intraday(t)
        if intraday_df is None:
            continue
        intraday_dates = set(naive_day.unique())
        if not intraday_dates:
            continue

        daily_rows = daily_df.reset_index()
        dates = daily_rows.Date
        i_start = int(dates.searchsorted(min(intraday_dates)))
        i_end = int(dates.searchsorted(max(intraday_dates), side="right"))

        for i in range(max(i_start, 11), i_end):
            row = daily_rows.iloc[i]
            date_norm = pd.Timestamp(row.Date).normalize()
            if date_norm not in intraday_dates:
                continue
            if pd.isna(row.high10_prior):
                continue

            prior_rows = daily_rows.iloc[:i]
            if len(prior_rows) < 11:
                continue
            prior_row = prior_rows.iloc[-1]
            if not _passes_primed_checks(t, prior_rows, prior_row):
                continue

            trigger_low = row.high10_prior * (1 + TRIGGER_CLEARANCE_LOW)
            # "fired" = touched trigger_low at any point during the day (the ORIGINAL
            # ground truth -- kept for reference/comparison only). "held" = actually
            # CLOSED above trigger_low by end of day -- the real question a trader
            # cares about (did this become a genuine trade, not a wick that reversed).
            # Checked directly (2026-09-08): of 602 real "fired" cases, only 43.4%
            # were also "held" -- the majority just breezed through and reversed, and
            # that hold-rate is roughly CONSTANT (~40-50%) regardless of how far away
            # the candidate started, i.e. touching and holding are near-independent
            # events. "held" is the ground truth actually used for the live table now.
            fired = bool(row.High >= trigger_low)
            held = bool(row.Close >= trigger_low)

            day_bars = intraday_df[naive_day == date_norm]
            if day_bars.empty:
                continue

            for cp in CHECKPOINTS:
                h, m = map(int, cp.split(":"))
                window = day_bars[day_bars.index.time <= dtime(h, m)]
                if window.empty:
                    continue
                bar_close = window.Close.iloc[-1]
                bar_high = window.High.max()
                if bar_high >= trigger_low:
                    continue  # already fired by this checkpoint -- not a "watching" observation
                dist_pct = (trigger_low / bar_close - 1) * 100
                if dist_pct < 0:
                    continue
                rows.append(dict(ticker=t, date=row.Date, checkpoint=cp,
                                  dist_pct=dist_pct, fired=fired, held=held))
    return pd.DataFrame(rows)


def calibration_table(df, col="held"):
    df = df.copy()
    df["bucket"] = df.dist_pct.apply(_bucket)
    return df.groupby("bucket").agg(n=(col, "size"), fire_rate=(col, "mean")).reset_index()


def main():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print(f"Building calibration dataset from {len(tickers)} tickers...", file=sys.stderr)
    df = build_dataset(tickers, verbose=True)
    print(f"\nTotal observations: {len(df)}", file=sys.stderr)
    if df.empty:
        print("No observations built -- check intraday_cache/data_cache coverage.")
        return

    dates = sorted(df.date.unique())
    mid = dates[len(dates) // 2]
    first_half = df[df.date <= mid]
    second_half = df[df.date > mid]
    print(f"Split at {pd.Timestamp(mid).date()}: first half {len(first_half)} obs "
          f"({pd.Timestamp(first_half.date.min()).date()}-{pd.Timestamp(first_half.date.max()).date()}), "
          f"second half {len(second_half)} obs "
          f"({pd.Timestamp(second_half.date.min()).date()}-{pd.Timestamp(second_half.date.max()).date()})")

    train_table = calibration_table(first_half)
    test_table = calibration_table(second_half)

    merged = train_table.merge(test_table, on="bucket", suffixes=("_train", "_test"), how="outer")
    merged = merged.sort_values("bucket")
    print("\nbucket | train_n | train_rate | test_n | test_rate |    gap")
    for _, r in merged.iterrows():
        train_n = r.n_train if pd.notna(r.n_train) else 0
        test_n = r.n_test if pd.notna(r.n_test) else 0
        train_rate = r.fire_rate_train * 100 if pd.notna(r.fire_rate_train) else None
        test_rate = r.fire_rate_test * 100 if pd.notna(r.fire_rate_test) else None
        gap_str = f"{(test_rate - train_rate):+5.1f}pp" if train_rate is not None and test_rate is not None else "   n/a"
        train_str = f"{train_rate:5.1f}%" if train_rate is not None else "  n/a"
        test_str = f"{test_rate:5.1f}%" if test_rate is not None else "  n/a"
        print(f"{r.bucket:>6} | {train_n:>7.0f} | {train_str:>9} | {test_n:>6.0f} | {test_str:>8} | {gap_str:>7}")

    df.to_csv("calibration_audit_raw.csv", index=False)
    print("\nRaw dataset saved to calibration_audit_raw.csv")


if __name__ == "__main__":
    main()
