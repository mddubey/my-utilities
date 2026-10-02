"""How often does the literal stop (pinbar's own low) get hit, and what happens right
after -- does price keep falling (stop was correct), or does it dip a little further
and then recover (stop was too tight, needed a buffer/"gap" below the low)?

Reuses the exact same pinbar/swing/weekly-support logic as 01_daily_pinbar_weekly_support.py
(duplicated directly, not imported, since this project's own files start with a digit and
can't be `import`ed normally -- kept self-contained rather than using importlib gymnastics).
Read-only against backtest.load(), nothing written to production.
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import numpy as np
import pandas as pd

from backtest import load

K_SWING = 3
TARGET_LOOKBACK = 252
MAX_HOLD_DAYS = 60
BUFFERS_PCT = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]  # extra room below the literal low, in %


def find_swings(high, low, k=K_SWING):
    n = len(high)
    sh = np.zeros(n, dtype=bool)
    sl = np.zeros(n, dtype=bool)
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


def weekly_ema8_asof(df):
    s = df.set_index("Date")["Close"]
    wk = s.resample("W-FRI").last().dropna()
    wk_ema8 = wk.ewm(span=8, adjust=False).mean()
    return wk_ema8.shift(1).reindex(s.index, method="ffill").values


def simulate_buffered(entry_idx, sh, sl, high, low, close, buffer_pct):
    """Same walk-forward as 01's simulate_one, but the stop starts `buffer_pct`% below
    the literal pinbar low. 1R is ALWAYS measured against the ORIGINAL (0% buffer) risk
    unit -- per this project's own Risk Unit Integrity rule, changing the stop creates a
    different risk unit, so R-multiples across buffer levels are only comparable if both
    use the same original risk-in-rupees as the denominator, not a re-normalized one."""
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
            return ("data_end", (close[n - 1] - entry_price) / original_risk, day - 1)
        if low[i] <= stop:
            return ("stop", (stop - entry_price) / original_risk, day)
        if target is not None and high[i] >= target:
            return ("target", (target - entry_price) / original_risk, day)
        confirm_i = i - K_SWING
        if confirm_i > entry_idx and sl[confirm_i] and low[confirm_i] > stop:
            stop = low[confirm_i]
    return ("max_hold", (close[entry_idx + MAX_HOLD_DAYS] - entry_price) / original_risk, MAX_HOLD_DAYS)


def find_real_undershoot(df, entry_idx, literal_low_stop_day):
    """For a trade that got stopped at the LITERAL low (0% buffer): starting from the
    day it was stopped, how much FURTHER below the literal low did price actually dip
    (real max adverse excursion) before either closing back above the original entry
    price, or the MAX_HOLD_DAYS window runs out? Expressed as % below the literal low --
    directly answers 'how much gap would have been needed to not get stopped here.'"""
    close, low = df.Close.values, df.Low.values
    entry_price = close[entry_idx]
    literal_low = low[entry_idx]
    n = len(close)
    worst_low = low[literal_low_stop_day] if literal_low_stop_day < n else literal_low
    recovered = False
    for day in range(literal_low_stop_day - entry_idx, MAX_HOLD_DAYS + 1):
        i = entry_idx + day
        if i >= n:
            break
        worst_low = min(worst_low, low[i])
        if close[i] >= entry_price:
            recovered = True
            break
    undershoot_pct = (literal_low - worst_low) / literal_low * 100
    return undershoot_pct, recovered


def run(tickers):
    stop_rows = []
    buffer_rows = {b: [] for b in BUFFERS_PCT}

    for idx, t in enumerate(tickers):
        if (idx + 1) % 300 == 0:
            print(f"  {idx + 1}/{len(tickers)} tickers processed", flush=True)
        try:
            df = load(t).reset_index()
        except FileNotFoundError:
            continue
        if len(df) < TARGET_LOOKBACK + K_SWING + 5:
            continue
        high, low, close = df.High.values, df.Low.values, df.Close.values
        sh, sl = find_swings(high, low)
        pinbar = bullish_pinbar_mask(df).values

        for i in np.where(pinbar)[0]:
            if i < TARGET_LOOKBACK or i + K_SWING >= len(df):
                continue

            for b in BUFFERS_PCT:
                result = simulate_buffered(i, sh, sl, high, low, close, b)
                if result is None:
                    continue
                reason, r, days = result
                buffer_rows[b].append(dict(ticker=t, date=df.Date.iloc[i],
                                            exit_reason=reason, r_multiple=r))

            # literal (0% buffer) stop -- find where it actually got stopped, then trace
            # what happens after
            r0 = simulate_buffered(i, sh, sl, high, low, close, 0.0)
            if r0 is None or r0[0] != "stop":
                continue
            entry_price = close[i]
            literal_stop = low[i]
            stop_day_idx = None
            n = len(close)
            cur_stop = literal_stop
            for day in range(1, MAX_HOLD_DAYS + 1):
                j = i + day
                if j >= n:
                    break
                if low[j] <= cur_stop:
                    stop_day_idx = j
                    break
                confirm_i = j - K_SWING
                if confirm_i > i and sl[confirm_i] and low[confirm_i] > cur_stop:
                    cur_stop = low[confirm_i]
            if stop_day_idx is None or cur_stop != literal_stop:
                continue  # only look at trades stopped at the ORIGINAL literal low,
                          # not ones where the trail had already moved the stop up
            undershoot_pct, recovered = find_real_undershoot(df, i, stop_day_idx)
            stop_rows.append(dict(ticker=t, date=df.Date.iloc[i],
                                   undershoot_pct=undershoot_pct, recovered=recovered))

    return pd.DataFrame(stop_rows), {b: pd.DataFrame(v) for b, v in buffer_rows.items()}


def summarize_buffer(df, label):
    n = len(df)
    if n == 0:
        print(f"{label}: n=0")
        return
    win = (df.r_multiple > 0).mean() * 100
    mean_r = df.r_multiple.mean()
    total_r = df.r_multiple.sum()
    payoff = df.loc[df.r_multiple > 0, "r_multiple"].mean() / abs(df.loc[df.r_multiple < 0, "r_multiple"].mean())
    stops = (df.exit_reason == "stop").mean() * 100
    print(f"{label:20s} n={n:6d}  stop%%={stops:5.1f}  win%%={win:5.1f}  "
          f"meanR(orig risk)={mean_r:+.4f}  totalR={total_r:+9.1f}  payoff={payoff:.2f}")


if __name__ == "__main__":
    universe = pd.read_csv(str(Path(__file__).parent.parent / "nse_equity_universe.csv"))["ticker"].tolist()
    print(f"universe: {len(universe)} tickers\n")

    stop_gap_df, buffer_dfs = run(universe)
    stop_gap_df.to_csv(Path(__file__).parent / "stop_gap_undershoot.csv", index=False)

    print(f"\n=== Literal-stop (0%% buffer) trades that DID get stopped: n={len(stop_gap_df)} ===\n")
    print("Real undershoot below the literal low, before either recovering to entry or",
          f"the {MAX_HOLD_DAYS}-day window ending (this is 'how much gap was actually needed'):")
    print(stop_gap_df.undershoot_pct.describe(percentiles=[.1, .25, .5, .75, .9]).to_string())
    print()
    print(f"Of the stopped trades, %% that recovered back to entry price at some point after: "
          f"{stop_gap_df.recovered.mean()*100:.1f}%%")

    print("\n=== Buffer sweep: does giving the stop extra room below the literal low help, ===")
    print("=== measured in the ORIGINAL (0%% buffer) risk unit, not a re-normalized one ===\n")
    for b in BUFFERS_PCT:
        summarize_buffer(buffer_dfs[b], f"buffer={b}%%")
