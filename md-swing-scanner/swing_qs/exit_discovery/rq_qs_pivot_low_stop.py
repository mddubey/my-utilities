"""Does the stop matter -- S1b (prior day's Low) vs the actual most-recent CONFIRMED
pivot/swing low (2026-09-28 next session), per direct user question: S1b was always a
placeholder to have something to work with, never a validated final choice. Reuses
primed_engine.py's own K_SWING=2 confirmation convention (a low is confirmed once 2
bars on both sides close higher) -- not invented fresh, this is the project's existing
swing-point definition.

Same entry population/gate as everywhere else tonight (raw N-day-high breakout,
frozen v0.1 base_duration/gap_to_trigger conditional, single position per ticker) --
ONLY the stop changes. Everything else held identical for a clean A/B.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

from backtest import load
from pivots import daily_pivots
import primed_engine as pe
from qs_dashboard import _base_duration, GAP_BAD_THRESHOLD_PCT, MAX_TRACK_DAYS, STOP_R

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LOOKBACKS = (10, 20, 40)
MIN_HISTORY = 61
K_SWING = pe.K_SWING  # =2, reused not reinvented


def passes_v01_gate(base_duration, gap_to_trigger_pct):
    return not (base_duration == 0 and gap_to_trigger_pct is not None and gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT)


def most_recent_confirmed_swing_low(rows, i, max_lookback=120):
    """Most recent K=2-confirmed swing low strictly before entry index i. A bar at j is
    confirmed once bars j-K..j+K are all known and Low[j] is the min of that window --
    the earliest such j usable at entry is j <= i-1-K_SWING (so j+K_SWING < i, fully
    confirmed by yesterday). Returns None if none found within max_lookback."""
    lows = rows.Low.values
    j_max = i - 1 - K_SWING
    for j in range(j_max, max(j_max - max_lookback, K_SWING - 1), -1):
        window = lows[j - K_SWING:j + K_SWING + 1]
        if len(window) == 2 * K_SWING + 1 and lows[j] == window.min():
            return lows[j]
    return None


def walk_ticker(ticker, lookback, stop_mode):
    try:
        rows = load(ticker, daily_pivots).reset_index()
    except FileNotFoundError:
        return []
    n_rows = len(rows)
    high_prior_series = rows.High.shift(1).rolling(lookback).max()
    trades = []
    in_position = False
    cur = None

    for i in range(n_rows):
        row = rows.iloc[i]
        if row.corp_action_day:
            in_position, cur = False, None
            continue
        if in_position:
            days_held = i - cur["entry_i"]
            high_r = (row.High / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            low_r = (row.Low / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            close_r = (row.Close / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            stopped = low_r <= STOP_R
            capped = days_held >= MAX_TRACK_DAYS
            if stopped or capped:
                cur["exit_r"] = STOP_R if stopped else close_r
                cur["exit_reason"] = "stop" if stopped else "max_days"
                cur["days_held"] = days_held
                trades.append(cur)
                in_position, cur = False, None

        if i < MIN_HISTORY:
            continue
        hp = high_prior_series.iloc[i]
        if pd.isna(hp):
            continue
        entry_price = hp * pe.TRIGGER_CLEARANCE
        if row.High < entry_price:
            continue
        base_dur = _base_duration(rows, high_prior_series, i)
        row_t1 = rows.iloc[i - 1]
        gap_to_trigger_pct = (entry_price / row_t1.Close - 1) * 100 if row_t1.Close else None
        if in_position or not passes_v01_gate(base_dur, gap_to_trigger_pct):
            continue

        if stop_mode == "s1b":
            initial_stop_price = row_t1.Low
        elif stop_mode == "pivot_low":
            initial_stop_price = most_recent_confirmed_swing_low(rows, i)
            if initial_stop_price is None:
                continue  # no confirmed swing low found -- skip, don't guess
        else:
            raise ValueError(stop_mode)

        initial_risk_pct = (entry_price - initial_stop_price) / entry_price * 100
        if initial_risk_pct <= 0:
            continue
        in_position = True
        cur = dict(ticker=ticker, entry_definition=lookback, entry_i=i,
                    entry_date=str(row.Date.date()), entry_price=entry_price,
                    initial_stop_price=initial_stop_price, initial_risk_pct=initial_risk_pct)
    return trades


def run(tickers, stop_mode):
    all_trades = []
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"  [{stop_mode}] {n}/{len(tickers)}", flush=True)
        for lb in LOOKBACKS:
            all_trades.extend(walk_ticker(t, lb, stop_mode))
    return pd.DataFrame(all_trades)


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

    for stop_mode in ("s1b", "pivot_low"):
        print(f"Running stop_mode={stop_mode}")
        df = run(tickers, stop_mode)
        df.to_csv(f"{OUT_DIR}/pivot_low_{stop_mode}_trades.csv", index=False)
        risk_med = df.initial_risk_pct.median()
        print(f"  n={len(df)}  mean_r={df.exit_r.mean():.4f}  median_r={df.exit_r.median():.4f}  "
              f"win%={(df.exit_r>0).mean()*100:.1f}  stopped%={(df.exit_reason=='stop').mean()*100:.1f}  "
              f"median_initial_risk_pct={risk_med:.2f}%\n")
