"""RQ-EMAPB-05 -- Hourly-NATIVE breach + pullback (granularity-consistent, 2026-10-04).

User's rule, confirmed this session: whatever timeframe DEFINES the breach, that whole bar is
excluded from pullback-eligibility -- you can't slice inside it with a finer timeframe and call
part of it "after." RQ-EMAPB-04 was correctly granularity-consistent at the DAILY level (A
defined on daily bars, pullback measured only from day A+1). This script builds a SEPARATE,
consistently-hourly population: A is defined and detected on 1H bars from the start (same
10-bar-lookback / 1.5x-volume convention as the daily population -- same parameters, no new
tuning, just applied at 1H resolution, matching backtest.py's own 10-bar structural lookback
convention), so subsequent 1H bars -- even later the same calendar day -- are legitimately
eligible as pullback, since the breach itself is already a single, complete 1H bar.

Literature context (read before building, per standing discipline): price action is
scale-invariant/fractal across timeframes, but lower-timeframe breakouts empirically have HIGHER
failure rates and SMALLER follow-through relative to volatility than daily ones (~50% failure /
1.8-2.5x ATR at 1H vs ~40-45% / 3.0-4.5x ATR daily). This script exists to measure that trade-off
in our own data, not assume it.

Purely descriptive: no filter, no promotion, no strategy test.

Usage: python3 swing_qs_emapb/09_hourly_native_episode.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
LOOKBACK = 10          # bars -- same convention as the daily A definition / backtest.py, not tuned
VOL_RATIO_MIN = 1.5    # same threshold as the daily A definition, not tuned
WINDOW_BARS = 300      # ~48 trading days of 1H bars, calendar-comparable to RQ-EMAPB-04's 50d window


def load_60m(ticker):
    f = INTRADAY_60M_DIR / f"{ticker}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f, index_col=0)
    if d.empty:
        return None
    d.index = pd.to_datetime(d.index, utc=True).tz_convert("Asia/Kolkata")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d.dropna(subset=["Close", "High", "Low", "Volume"])
    d = d[d.Volume > 0]
    if len(d) < LOOKBACK + WINDOW_BARS:
        return None
    return d.reset_index(drop=True)


def find_a_bars(d):
    """Hourly-native breach: High[i] > max(High[i-LOOKBACK:i]) and Volume[i] >= 1.5x mean(Volume[i-LOOKBACK:i]).
    Same lookback/threshold as the daily A definition, applied at 1H resolution. First-of-cluster
    only (skip i if i-1 also qualified) to avoid trivially double-counting one extended breakout --
    but cluster_length is recorded (diagnostic only, per critic's instruction, not a filter)."""
    prior_high = d.High.rolling(LOOKBACK).max().shift(1)
    prior_vol_avg = d.Volume.rolling(LOOKBACK).mean().shift(1)
    qualifies = (d.High > prior_high) & (d.Volume >= VOL_RATIO_MIN * prior_vol_avg)
    qualifies = qualifies.fillna(False).values
    out = []
    i = 0
    n = len(qualifies)
    while i < n:
        if qualifies[i] and (i == 0 or not qualifies[i - 1]):
            j = i
            while j < n and qualifies[j]:
                j += 1
            out.append((i, j - i))  # (a_index, cluster_length)
        i += 1
    return out


def reconstruct(d, ia):
    """Expanded per critic's instruction: audit whether the running-high-walk ("local peak" =
    first point extension pauses) mis-segments the episode, by comparing it against the TRUE
    max High of the full window. Continuation definition itself is UNCHANGED -- this only adds
    diagnostic fields on top of it. No day-boundary special-casing (hourly-native A)."""
    end = min(ia + 1 + WINDOW_BARS, len(d))
    if end - ia < 5:
        return None

    a_price = d.Close.iloc[ia]
    a_high = d.High.iloc[ia]

    # --- window true max (independent of the walk) ---
    window_slice = d.High.iloc[ia:end]
    window_max_high = window_slice.max()
    window_max_i = int(window_slice.values.argmax()) + ia

    # --- local running-high walk (same algorithm as RQ-EMAPB-04, unchanged) ---
    local_high = a_high
    local_peak_i = ia
    for k in range(ia + 1, end):
        if d.High.iloc[k] > local_high:
            local_high = d.High.iloc[k]
            local_peak_i = k
        else:
            break
    else:
        return dict(a_price=a_price, a_high=a_high, local_peak_i=local_peak_i,
                    local_peak_high=local_high, a_to_local_peak_bars=local_peak_i - ia,
                    window_max_high=window_max_high, window_max_i=window_max_i,
                    max_after_first_failure=None, peak_hit_window_end=True,
                    bars_to_continuation=None, pullback_depth_pct=None, window_truncated=True)

    pullback_start_i = local_peak_i + 1
    window_min_low = d.Low.iloc[pullback_start_i:end].min() if pullback_start_i < end else np.nan
    pullback_depth_pct = (window_min_low / local_high - 1) * 100 if pd.notna(window_min_low) else None

    # does the window's TRUE max occur strictly after the local-pause point? (mis-segmentation check)
    max_after_first_failure = bool(window_max_i > local_peak_i)

    continuation_i = None
    for k in range(pullback_start_i, end):
        if d.High.iloc[k] > local_high:
            continuation_i = k
            break

    return dict(
        a_price=a_price, a_high=a_high,
        local_peak_i=local_peak_i, local_peak_high=local_high,
        a_to_local_peak_bars=local_peak_i - ia,
        window_max_high=window_max_high, window_max_i=window_max_i,
        max_after_first_failure=max_after_first_failure,
        peak_hit_window_end=False,
        bars_to_continuation=(continuation_i - local_peak_i) if continuation_i is not None else None,
        pullback_depth_pct=pullback_depth_pct,
        window_truncated=(continuation_i is None),
    )


def bucket_bars(bars):
    """Buckets in 1H bars, ~6.25 bars/trading day on NSE."""
    if bars is None or pd.isna(bars):
        return "never (within 300-bar window)"
    if bars <= 2:
        return "1-2 bars (same session, ~1-2h)"
    if bars <= 6:
        return "3-6 bars (rest of day / next AM)"
    if bars <= 13:
        return "7-13 bars (~1-2 trading days)"
    if bars <= 39:
        return "14-39 bars (~2-6 trading days)"
    return ">39 bars (~6+ trading days)"


def main():
    tickers = sorted(f.stem for f in INTRADAY_60M_DIR.glob("*.csv"))
    print(f"Scanning {len(tickers)} tickers for hourly-native A's "
          f"(High > prior {LOOKBACK}-bar high, Volume >= {VOL_RATIO_MIN}x prior {LOOKBACK}-bar avg)...")

    rows = []
    n_bars_total = 0
    n_a_total = 0
    for n, ticker in enumerate(tickers):
        d = load_60m(ticker)
        if d is None:
            continue
        n_bars_total += len(d)
        a_clusters = find_a_bars(d)
        n_a_total += len(a_clusters)
        for ia, cluster_length in a_clusters:
            res = reconstruct(d, ia)
            if res is None:
                continue
            res.update(ticker=ticker, a_i=ia, cluster_length=cluster_length)
            rows.append(res)
        if (n + 1) % 500 == 0:
            print(f"  ...{n+1}/{len(tickers)} tickers, {len(rows):,} episodes so far")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb05_hourly_native_episodes.csv", index=False)
    print(f"\nTotal 1H bars scanned: {n_bars_total:,}")
    print(f"Hourly-native A's found (first-of-cluster): {n_a_total:,}  "
          f"(trigger rate: {n_a_total/n_bars_total*100:.3f}% of all bars)")
    print(f"Episodes with valid window: {len(df):,}\n")

    # --- Cluster length diagnostic (critic's addition #1) ---
    print("--- Cluster length diagnostic (NOT a filter) ---")
    print(f"cluster_length==1 (isolated bar): {(df.cluster_length==1).mean()*100:.1f}%")
    print(f"cluster_length 2-3: {df.cluster_length.between(2,3).mean()*100:.1f}%")
    print(f"cluster_length 4+: {(df.cluster_length>=4).mean()*100:.1f}%  "
          f"(median={df.cluster_length.median():.0f}, max={df.cluster_length.max():.0f})")

    # --- Hand-check a handful of concrete episodes (Rule #22) ---
    print("\n--- Hand-check: 5 concrete episodes ---")
    sample = df.sample(min(5, len(df)), random_state=2026)
    for r in sample.itertuples():
        print(f"{r.ticker:12} a_i={r.a_i} cluster_len={r.cluster_length}  "
              f"a_to_local_peak_bars={r.a_to_local_peak_bars}  "
              f"max_after_first_failure={getattr(r, 'max_after_first_failure', None)}  "
              f"bars_to_continuation={getattr(r, 'bars_to_continuation', None)}  "
              f"pullback_depth={getattr(r, 'pullback_depth_pct', None)}")

    print("\n--- Distribution: A -> local peak (bars) ---")
    n = len(df)
    print(f"same bar (0 extra bars, A is immediately its own local peak): "
          f"{(df.a_to_local_peak_bars==0).sum():,} ({(df.a_to_local_peak_bars==0).mean()*100:.1f}%)")
    print(f"1-5 extra bars (~same day): {df.a_to_local_peak_bars.between(1,5).sum():,} "
          f"({df.a_to_local_peak_bars.between(1,5).sum()/n*100:.1f}%)")
    print(f"6-13 extra bars (~1-2 days): {df.a_to_local_peak_bars.between(6,13).sum():,} "
          f"({df.a_to_local_peak_bars.between(6,13).sum()/n*100:.1f}%)")
    print(f"14+ extra bars (2+ days): {(df.a_to_local_peak_bars>=14).sum():,} "
          f"({(df.a_to_local_peak_bars>=14).sum()/n*100:.1f}%)")
    print(f"never found a pullback within {WINDOW_BARS}-bar window (still extending): "
          f"{df.peak_hit_window_end.sum():,} ({df.peak_hit_window_end.mean()*100:.1f}%)")

    # --- Mis-segmentation check (critic's addition #2) ---
    scoped = df[~df.peak_hit_window_end].copy()
    print(f"\n--- Mis-segmentation check: does the TRUE window max come AFTER the local-pause peak? ---")
    print(f"n = {len(scoped):,}")
    print(f"max_after_first_failure = True (local peak undercounted a bigger later move): "
          f"{scoped.max_after_first_failure.mean()*100:.1f}%")
    print(f"max_after_first_failure = False (local peak WAS the true window max): "
          f"{(~scoped.max_after_first_failure).mean()*100:.1f}%")

    print("\n--- Distribution: local peak -> continuation (bars) -- the key diagnostic ---")
    print(f"n = {len(scoped):,}")
    scoped["bucket"] = scoped.bars_to_continuation.apply(bucket_bars)
    order = ["1-2 bars (same session, ~1-2h)", "3-6 bars (rest of day / next AM)",
              "7-13 bars (~1-2 trading days)", "14-39 bars (~2-6 trading days)",
              ">39 bars (~6+ trading days)", "never (within 300-bar window)"]
    counts = scoped["bucket"].value_counts().reindex(order, fill_value=0)
    for b, c in counts.items():
        print(f"  {b:34}: {c:6,}  ({c/len(scoped)*100:5.1f}%)")

    print("\n--- Pullback depth (observational only) ---")
    pds = scoped.pullback_depth_pct.dropna()
    print(f"median={pds.median():.2f}%  p25={pds.quantile(.25):.2f}%  p75={pds.quantile(.75):.2f}%")

    print(f"\nWritten: {HERE}/rq_emapb05_hourly_native_episodes.csv")


if __name__ == "__main__":
    main()
