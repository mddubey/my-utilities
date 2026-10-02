"""Re-check every real claim made today against the two things that just broke the
Nifty-regime finding: (1) does it hold consistently year by year, not just pooled,
(2) is it driven by a handful of extreme trades, not the population as a whole.

Read-only against the CSVs already produced today (pivot_and_rsi_features.csv has
everything needed: weekly_support, rsi14, the six pivot distances, r_multiple,
exit_reason, date) plus a fresh buffer-sweep re-run (with year kept) since that
wasn't saved per-trade earlier. Nothing in production touched.
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import numpy as np
import pandas as pd

from backtest import load

HERE = Path(__file__).parent
K_SWING = 3
TARGET_LOOKBACK = 252
MAX_HOLD_DAYS = 60


def year_check(df, split_col, label, true_label="A", false_label="B"):
    """meanR by year, for each side of a boolean/categorical split."""
    print(f"\n--- {label}: year-by-year ---")
    g = df.groupby([df.date.dt.year, split_col]).r_multiple.agg(["count", "mean"]).round(4)
    print(g.to_string())


def concentration_check(df, label):
    """What % of a cohort's total R comes from its top 10 / top 50 trades."""
    d = df.sort_values("r_multiple", ascending=False)
    total = d.r_multiple.sum()
    if total == 0 or len(d) < 10:
        print(f"{label}: n={len(d)}, too small or zero total R to check")
        return
    top10 = d.head(10).r_multiple.sum()
    top50 = d.head(min(50, len(d))).r_multiple.sum()
    print(f"{label:40s} n={len(d):6d}  totalR={total:8.1f}  "
          f"top10={top10/total*100:5.1f}%  top50={top50/total*100:5.1f}%")


def median_split_year_check(df, col, label):
    """For a continuous distance measure: split at the median, check year by year
    whether 'closer than median' vs 'farther than median' keeps the same direction."""
    sub = df.dropna(subset=[col, "r_multiple"]).copy()
    if len(sub) < 200:
        print(f"{label}: n={len(sub)}, too thin")
        return
    med = sub[col].median()
    sub["half"] = np.where(sub[col] <= med, "near (<=median)", "far (>median)")
    print(f"\n--- {label} (median split at {med:.2f}%) ---")
    g = sub.groupby([sub.date.dt.year, "half"]).r_multiple.agg(["count", "mean"]).round(4)
    print(g.to_string())
    concentration_check(sub[sub.half == "near (<=median)"], f"  {label}, near-median half")
    concentration_check(sub[sub.half == "far (>median)"], f"  {label}, far-median half")


def simulate_buffered(entry_idx, sh, sl, high, low, close, buffer_pct):
    entry_price = close[entry_idx]
    literal_stop = low[entry_idx]
    original_risk = entry_price - literal_stop
    if original_risk <= 0:
        return None
    stop = literal_stop * (1 - buffer_pct / 100)
    lo = max(0, entry_idx - TARGET_LOOKBACK)
    target = None
    for j in range(entry_idx - 1, lo, -1):
        if sh[j] and high[j] > entry_price:
            target = high[j]
            break
    n = len(close)
    for day in range(1, MAX_HOLD_DAYS + 1):
        i = entry_idx + day
        if i >= n:
            return (close[n - 1] - entry_price) / original_risk
        if low[i] <= stop:
            return (stop - entry_price) / original_risk
        if target is not None and high[i] >= target:
            return (target - entry_price) / original_risk
        confirm_i = i - K_SWING
        if confirm_i > entry_idx and sl[confirm_i] and low[confirm_i] > stop:
            stop = low[confirm_i]
    return (close[entry_idx + MAX_HOLD_DAYS] - entry_price) / original_risk


def find_swings(high, low, k=K_SWING):
    n = len(high)
    sh, sl = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        wh, wl = high[i - k:i + k + 1], low[i - k:i + k + 1]
        if high[i] == wh.max():
            sh[i] = True
        if low[i] == wl.min():
            sl[i] = True
    return sh, sl


def bullish_pinbar_mask(df):
    O, H, L, C = df.Open, df.High, df.Low, df.Close
    body = C - O
    return (C > O) & ((H - C) < body) & ((O - L) > body) & (C > 50)


def rerun_buffer_sweep_with_year(events, buffers=(0.0, 1.0, 2.0, 5.0)):
    print("\n=== Stop-buffer sweep, re-run WITH year kept ===")
    by_ticker = {t: g.index.tolist() for t, g in events.groupby("ticker")}
    rows = []
    for idx, (t, row_idxs) in enumerate(by_ticker.items()):
        if (idx + 1) % 400 == 0:
            print(f"  {idx + 1}/{len(by_ticker)} tickers", flush=True)
        try:
            df = load(t).reset_index()
        except FileNotFoundError:
            continue
        high, low, close = df.High.values, df.Low.values, df.Close.values
        sh, sl = find_swings(high, low)
        pinbar = bullish_pinbar_mask(df).values
        date_to_idx = {d: i for i, d in enumerate(df.Date)}
        for ridx in row_idxs:
            dt = events.at[ridx, "date"]
            i = date_to_idx.get(dt)
            if i is None or not pinbar[i] or i < TARGET_LOOKBACK or i + K_SWING >= len(df):
                continue
            for b in buffers:
                r = simulate_buffered(i, sh, sl, high, low, close, b)
                if r is not None:
                    rows.append(dict(ticker=t, date=dt, buffer=b, r_multiple=r))
    out = pd.DataFrame(rows)
    out["year"] = out.date.dt.year
    g = out.groupby(["year", "buffer"]).r_multiple.agg(["count", "mean"]).round(4)
    print(g.to_string())
    print("\nConcentration by buffer level:")
    for b in buffers:
        concentration_check(out[out.buffer == b], f"  buffer={b}%")
    return out


if __name__ == "__main__":
    events = pd.read_csv(HERE / "pivot_and_rsi_features.csv", parse_dates=["date"])
    print(f"loaded {len(events)} events with joined features\n")

    # 1. weekly-EMA support (script 01's headline finding)
    year_check(events, "weekly_support", "weekly_support (script 01)")
    concentration_check(events[events.weekly_support], "weekly_support=True")
    concentration_check(events[~events.weekly_support], "weekly_support=False")

    # 2. all six pivot distances (script 03)
    for name in ("daily", "weekly", "monthly"):
        for level in ("r1", "r2"):
            median_split_year_check(events, f"{name}_{level}_dist_pct", f"{name.upper()} {level.upper()} distance")

    # 3. RSI bands (script 03)
    print("\n--- RSI(14) bands: year-by-year ---")
    sub = events.dropna(subset=["rsi14"]).copy()
    bands = [-1, 30, 50, 70, 101]
    labels = ["<30", "30-50", "50-70", ">70"]
    sub["rsi_band"] = pd.cut(sub.rsi14, bands, labels=labels)
    g = sub.groupby([sub.date.dt.year, "rsi_band"], observed=True).r_multiple.agg(["count", "mean"]).round(4)
    print(g.to_string())
    for lab in labels:
        concentration_check(sub[sub.rsi_band == lab], f"RSI band {lab}")

    # 4. stop-buffer sweep (script 02) -- needs a fresh run, year wasn't saved originally
    rerun_buffer_sweep_with_year(events[["ticker", "date"]].drop_duplicates())
