"""Daily bullish pinbar, alone vs. combined with weekly-8-EMA support, real exit.

Isolated, read-only research script -- imports backtest.load() for data only, never
writes to any production file, never imports daily_scan.py/live_checkpoint.py/
signals.py's production filters. Per the user's explicit instruction: keep the exit
EXACTLY as literally stated in the source material (SOURCE_TRANSCRIPT.md File 2),
tune later, not now.

Entry: daily bullish pinbar (exact chartink formula, minus the market-cap floor --
this project's price cache has no market-cap data, so that one filter is dropped and
flagged, not faked). Entry price = that day's own Close (per the user's clarified
entry-clock: acted on same-day, at the close, not next-day's open).

Stop: the pinbar's own Low -- literal.
Target: nearest prior confirmed swing high above entry ("common high") -- plain
  textbook swing definition (K bars on each side), not any project-specific logic.
Trail: stop moves up to each newly CONFIRMED swing low as the trade runs -- the
  standard price-action meaning of "trail your stop."
Weekly support: the most recently COMPLETED week's 8-EMA value falls inside that
  day's own [Low, Close] range -- the most literal reading of "taking support at
  that level," no invented % threshold.

Comparison unit: pinbar alone vs. pinbar + weekly-support, same exit held fixed
across both arms.
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import numpy as np
import pandas as pd

from backtest import load

K_SWING = 3            # plain textbook swing high/low definition, K bars each side
TARGET_LOOKBACK = 252  # how far back to search for the nearest prior swing high
MAX_HOLD_DAYS = 60     # practical cap so trades close out -- not in the source notes,
                        # flagged as a necessary addition, not part of the literal rule


def find_swings(high, low, k=K_SWING):
    """Returns (is_swing_high, is_swing_low) boolean arrays -- confirmed only once
    k bars exist on both sides, i.e. decision-time-safe (no lookahead when walking
    forward day by day)."""
    n = len(high)
    sh = np.zeros(n, dtype=bool)
    sl = np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        window_h = high[i - k:i + k + 1]
        window_l = low[i - k:i + k + 1]
        if high[i] == window_h.max():
            sh[i] = True
        if low[i] == window_l.min():
            sl[i] = True
    return sh, sl


def bullish_pinbar_mask(df):
    """Exact chartink formula (Bullish Pinbar day chart), market-cap floor dropped
    (no market-cap data in this project's cache)."""
    O, H, L, C = df.Open, df.High, df.Low, df.Close
    body = C - O
    return (
        (C > O) &
        ((H - C) < body) &
        ((O - L) > body) &
        (C > 50)
    )


def weekly_ema8_asof(df):
    """Most recently COMPLETED week's 8-EMA, forward-filled onto daily dates --
    same verified as-of convention as EMA_TIMEFRAME_ALIGNMENT.md's own check."""
    s = df.set_index("Date")["Close"]
    wk = s.resample("W-FRI").last().dropna()
    wk_ema8 = wk.ewm(span=8, adjust=False).mean()
    asof = wk_ema8.shift(1).reindex(s.index, method="ffill")
    return asof.values


def simulate_one(df, entry_idx, sh, sl, high, low, close):
    """Walk forward from entry_idx+1, trailing the stop to each newly confirmed
    swing low, exit on stop hit or target hit or MAX_HOLD_DAYS. Returns
    (exit_reason, r_multiple, days_held)."""
    entry_price = close[entry_idx]
    stop = low[entry_idx]
    risk = entry_price - stop
    if risk <= 0:
        return None

    # target = nearest prior CONFIRMED swing high above entry, searched backward
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
            return ("data_end", (close[n - 1] - entry_price) / risk, day - 1)
        if low[i] <= stop:
            return ("stop", (stop - entry_price) / risk, day)
        if target is not None and high[i] >= target:
            return ("target", (target - entry_price) / risk, day)
        # trail: once a new swing low CONFIRMS (needs K_SWING bars after it), raise the stop
        confirm_i = i - K_SWING
        if confirm_i > entry_idx and sl[confirm_i] and low[confirm_i] > stop:
            stop = low[confirm_i]
    return ("max_hold", (close[entry_idx + MAX_HOLD_DAYS] - entry_price) / risk, MAX_HOLD_DAYS)


def run(tickers):
    rows = []
    for idx, t in enumerate(tickers):
        if (idx + 1) % 200 == 0:
            print(f"  {idx + 1}/{len(tickers)} tickers processed, {len(rows)} events so far", flush=True)
        try:
            df = load(t).reset_index()
        except FileNotFoundError:
            continue
        if len(df) < TARGET_LOOKBACK + K_SWING + 5:
            continue
        high, low, close = df.High.values, df.Low.values, df.Close.values
        sh, sl = find_swings(high, low)
        pinbar = bullish_pinbar_mask(df).values
        wk_asof = weekly_ema8_asof(df)

        for i in np.where(pinbar)[0]:
            if i < TARGET_LOOKBACK or i + K_SWING >= len(df):
                continue  # need real history behind it and room for swing confirmation
            wk_val = wk_asof[i]
            weekly_support = (not np.isnan(wk_val)) and (low[i] <= wk_val <= close[i])
            result = simulate_one(df, i, sh, sl, high, low, close)
            if result is None:
                continue
            reason, r, days = result
            rows.append(dict(ticker=t, date=df.Date.iloc[i], weekly_support=weekly_support,
                              exit_reason=reason, r_multiple=r, days_held=days))
    return pd.DataFrame(rows)


def summarize(df, label):
    n = len(df)
    if n == 0:
        print(f"{label}: n=0")
        return
    win = (df.r_multiple > 0).mean() * 100
    meaningful = (df.r_multiple >= 0.25).mean() * 100
    full = (df.r_multiple >= 1.0).mean() * 100
    mean_r = df.r_multiple.mean()
    median_r = df.r_multiple.median()
    avg_win = df.loc[df.r_multiple > 0, "r_multiple"].mean()
    avg_loss = df.loc[df.r_multiple < 0, "r_multiple"].mean()
    payoff = avg_win / abs(avg_loss) if avg_loss else float("nan")
    print(f"{label}: n={n}  win%={win:.1f}  >=0.25R%={meaningful:.1f}  >=1R%={full:.1f}  "
          f"meanR={mean_r:.3f}  medianR={median_r:.3f}  payoff={payoff:.2f}  "
          f"avg_days={df.days_held.mean():.1f}")
    print("  exit reasons:", df.exit_reason.value_counts().to_dict())


if __name__ == "__main__":
    universe = pd.read_csv(str(Path(__file__).parent.parent / "nse_equity_universe.csv"))["ticker"].tolist()
    print(f"universe: {len(universe)} tickers (nse_equity_universe.csv)")
    print("NOTE: chartink's market-cap>500 floor is DROPPED -- no market-cap data in this "
          "project's price cache. Everything else is the literal formula.\n")

    results = run(universe)
    results.to_csv(Path(__file__).parent / "pinbar_weekly_support_results.csv", index=False)
    print(f"\ntotal pinbar events: {len(results)}\n")

    summarize(results, "ALL (pinbar alone, no weekly-support requirement)")
    print()
    summarize(results[results.weekly_support], "pinbar + weekly-8-ema support")
    print()
    summarize(results[~results.weekly_support], "pinbar, NO weekly support (for contrast)")
