"""EMAPB v1.1 -- literal state-machine implementation of the critic-specified specification
(2026-10-11). Builds Track A (structural labels: advance -> pullback -> candidate base ->
confirmed base -> breakout) and records Track B (descriptive only: breakout-day EOD close to
next-trading-day EOD close return) -- Track B is NEVER used to decide Track A eligibility.

Implementation-detail choices made where the spec was still ambiguous, documented inline at each
point (per critic's explicit instruction) -- search "IMPLEMENTATION CHOICE" for all of them.

Usage: python3 swing_qs_emapb/34_emapb_v1_statemachine.py [--tickers T1,T2,...] [--limit N]
"""
import sys, os, argparse
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
SWING_K = 2                 # IMPLEMENTATION CHOICE: symmetric confirmation lag, matches the
                             # project's existing K_SWING=2 convention used elsewhere (primed_engine.py)
ATR_WINDOW = 20
ADVANCE_MIN_ATR_MULT = 2.0
ADVANCE_MIN_SEPARATION_DAYS = 3
RETRACEMENT_DISQUALIFY = 2.0 / 3.0
BASE_WINDOW = 5
BASE_STABILIZE_TAIL = 2      # neither of the final 2 bars makes a new low
BASE_MAX_RANGE_ATR_MULT = 3.0
PRICE_FLOOR = 50.0
TURNOVER_FLOOR_CR = 1.0
LIQ_LOOKBACK_DAYS = 20


def load_daily(path):
    d = pd.read_csv(path)
    required = {"Date", "Open", "High", "Low", "Close", "Volume"}
    if d.empty or len(d) < 60 or not required.issubset(d.columns):
        return None
    d["Date"] = pd.to_datetime(d.Date)
    d = d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
    d["prev_close"] = d.Close.shift(1)
    # True Range: standard definition, includes gap vs prior close
    d["tr"] = pd.concat([
        d.High - d.Low,
        (d.High - d.prev_close).abs(),
        (d.Low - d.prev_close).abs(),
    ], axis=1).max(axis=1)
    # IMPLEMENTATION CHOICE: ATR(20) "at the swing-low/window-start date" = rolling mean of TR
    # over the 20 sessions ENDING AT AND INCLUDING that date (not excluding it) -- the spec says
    # "ATR measured at the swing-low date" without specifying inclusive/exclusive; since this is a
    # retrospective structural measurement (not a live same-day decision gate), including the date
    # itself in its own trailing window is the natural reading and is still fully decision-time-safe
    # (no future information).
    d["atr20"] = d.tr.rolling(ATR_WINDOW).mean()
    d["turnover"] = d.Close * d.Volume
    return d


def confirmed_swings(d):
    """IMPLEMENTATION CHOICE: strict inequality (Low/High must be strictly beyond all 4
    neighbors, not <=/>=) -- avoids ambiguous ties being double-counted as both a swing low and
    part of a flat range."""
    n = len(d)
    is_swing_low = np.zeros(n, dtype=bool)
    is_swing_high = np.zeros(n, dtype=bool)
    for i in range(SWING_K, n - SWING_K):
        window_low = d.Low.iloc[i - SWING_K:i + SWING_K + 1].values
        if d.Low.iloc[i] == window_low.min() and (window_low == d.Low.iloc[i]).sum() == 1:
            is_swing_low[i] = True
        window_high = d.High.iloc[i - SWING_K:i + SWING_K + 1].values
        if d.High.iloc[i] == window_high.max() and (window_high == d.High.iloc[i]).sum() == 1:
            is_swing_high[i] = True
    return is_swing_low, is_swing_high


def run_ticker(ticker, d):
    """Forward scan, one state machine per ticker. Returns a list of episode-outcome dicts."""
    n = len(d)
    is_swing_low, is_swing_high = confirmed_swings(d)
    episodes = []

    state = "SEARCHING_ADVANCE"
    last_swing_low_i = None
    swing_low_i = swing_high_i = None
    peak_price = peak_i = swing_low_price = atr_at_swing_low = None
    search_start = None
    box_high = box_low = box_start = box_end = None

    i = SWING_K
    while i < n - SWING_K:
        # confirmation becomes knowable once bar i exists (i = original_swing_index + SWING_K)
        confirmed_i = i - SWING_K
        if is_swing_low[confirmed_i]:
            last_swing_low_i = confirmed_i
        if is_swing_high[confirmed_i] and state == "SEARCHING_ADVANCE" and last_swing_low_i is not None \
                and last_swing_low_i < confirmed_i:
            sl_i, sh_i = last_swing_low_i, confirmed_i
            rise = d.High.iloc[sh_i] - d.Low.iloc[sl_i]
            atr_sl = d.atr20.iloc[sl_i]
            sep_days = sh_i - sl_i
            if pd.notna(atr_sl) and atr_sl > 0 and rise >= ADVANCE_MIN_ATR_MULT * atr_sl \
                    and sep_days >= ADVANCE_MIN_SEPARATION_DAYS:
                swing_low_i, swing_high_i = sl_i, sh_i
                swing_low_price = d.Low.iloc[sl_i]
                peak_price, peak_i = d.High.iloc[sh_i], sh_i
                atr_at_swing_low = atr_sl
                search_start = sh_i + 1
                state = "PULLBACK_SEARCHING_BASE"
            else:
                episodes.append(dict(ticker=ticker, outcome="advance_non_qualifying",
                                      swing_low_date=d.Date.iloc[sl_i], swing_high_date=d.Date.iloc[sh_i],
                                      rise=rise, atr_at_swing_low=atr_sl, separation_days=sep_days))

        if state in ("PULLBACK_SEARCHING_BASE", "CONFIRMED_BASE_WAITING_BREAKOUT") and i > peak_i:
            # (a) extension check -- only while still searching for a candidate base, per spec
            if state == "PULLBACK_SEARCHING_BASE" and d.High.iloc[i] > peak_price:
                peak_price, peak_i = d.High.iloc[i], i
                search_start = i + 1

            # (b) advance-level invalidation, checked every bar regardless of sub-state
            running_low = d.Low.iloc[peak_i:i + 1].min()
            retracement = (peak_price - running_low) / (peak_price - swing_low_price)
            close_breach = d.Close.iloc[i] < swing_low_price
            if retracement >= RETRACEMENT_DISQUALIFY or close_breach:
                episodes.append(dict(ticker=ticker, outcome="advance_invalidated",
                                      swing_low_date=d.Date.iloc[swing_low_i], peak_date=d.Date.iloc[peak_i],
                                      invalidation_date=d.Date.iloc[i], retracement=retracement,
                                      close_breach=bool(close_breach),
                                      had_confirmed_base=(state == "CONFIRMED_BASE_WAITING_BREAKOUT")))
                state = "SEARCHING_ADVANCE"
                i += 1
                continue

            if state == "PULLBACK_SEARCHING_BASE":
                if i >= search_start + BASE_WINDOW - 1:
                    w0, w1 = search_start, search_start + BASE_WINDOW  # [w0, w1)
                    window = d.iloc[w0:w1]
                    min_low = window.Low.min()
                    min_low_pos = window.Low.values.argmin()  # 0..4
                    # condition 3: lowest Low in first 3 bars (positions 0,1,2); neither of final
                    # 2 bars (positions 3,4) makes a Low at or below that minimum
                    tail = window.Low.iloc[-BASE_STABILIZE_TAIL:]
                    stabilized = (min_low_pos <= 2) and (tail > min_low).all()
                    atr_at_start = d.atr20.iloc[w0]
                    rng = window.High.max() - window.Low.min()
                    width_ok = pd.notna(atr_at_start) and atr_at_start > 0 and rng <= BASE_MAX_RANGE_ATR_MULT * atr_at_start
                    if stabilized and width_ok:
                        box_high, box_low = window.High.max(), window.Low.min()
                        box_start, box_end = w0, w1 - 1
                        state = "CONFIRMED_BASE_WAITING_BREAKOUT"
                    else:
                        search_start += 1

            elif state == "CONFIRMED_BASE_WAITING_BREAKOUT" and i >= box_end + 1:
                if d.Close.iloc[i] < box_low:
                    episodes.append(dict(ticker=ticker, outcome="base_invalidated",
                                          swing_low_date=d.Date.iloc[swing_low_i], peak_date=d.Date.iloc[peak_i],
                                          box_start_date=d.Date.iloc[box_start], box_end_date=d.Date.iloc[box_end],
                                          box_high=box_high, box_low=box_low,
                                          invalidation_date=d.Date.iloc[i]))
                    state = "PULLBACK_SEARCHING_BASE"
                    search_start = i + 1
                elif d.Close.iloc[i] > box_high:
                    d0_close = d.Close.iloc[i]
                    d1_ret = ((d.Close.iloc[i + 1] / d0_close - 1) * 100) if i + 1 < n else np.nan
                    episodes.append(dict(ticker=ticker, outcome="breakout",
                                          swing_low_date=d.Date.iloc[swing_low_i], peak_date=d.Date.iloc[peak_i],
                                          box_start_date=d.Date.iloc[box_start], box_end_date=d.Date.iloc[box_end],
                                          box_high=box_high, box_low=box_low,
                                          breakout_date=d.Date.iloc[i], breakout_close=d0_close,
                                          track_b_d1_ret=d1_ret))
                    state = "SEARCHING_ADVANCE"
        i += 1

    return episodes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if args.tickers:
        files = [f"data/daily/{t}.csv" for t in args.tickers.split(",")]
    else:
        files = sorted(glob.glob("data/daily/*.csv"))
        if args.limit:
            files = files[:args.limit]

    all_rows = []
    for n, f in enumerate(files):
        ticker = os.path.basename(f).replace(".csv", "")
        d = load_daily(f)
        if d is None:
            continue
        rows = run_ticker(ticker, d)
        all_rows.extend(rows)
        if (n + 1) % 200 == 0:
            print(f"  ...{n+1}/{len(files)} tickers")

    df = pd.DataFrame(all_rows)
    df.to_csv(f"{HERE}/rq_emapb_v1_episodes.csv", index=False)
    print(f"\nTotal episode records: {len(df):,}\n")
    print(df.outcome.value_counts())

    breakouts = df[df.outcome == "breakout"].copy()
    print(f"\n=== Breakouts: n={len(breakouts):,} ===")
    print(f"Track B (breakout-day EOD -> D+1 EOD), descriptive only:")
    print(breakouts.track_b_d1_ret.describe(percentiles=[.1, .25, .5, .75, .9]).round(2))
    print(f"% positive: {(breakouts.track_b_d1_ret > 0).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
