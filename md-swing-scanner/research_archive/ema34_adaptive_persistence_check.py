"""RQ-52A: Adaptive Persistence (2026-09-18), critic-proposed direct follow-up to
the EMA34_RISING_DAYS_MIN lag finding (FINDINGS.md, "the live pipeline has never
applied the Nifty regime gate..."). Instead of one global EMA34_RISING_DAYS_MIN,
test whether the RIGHT value differs by market regime bucket:
  - "recovery": the first few days of a new Nifty up-move (where the lag finding
    showed fires are suppressed and the rare early fires were the BEST quality)
  - "established": a mature, longer-running Nifty up-move
  - "downtrend": any day Nifty is in a down-move (where stale qualification was
    shown to degrade real outcomes, options flipping to a loss by day 3-5)

Critic's hypothesis: recovery wants a short window (2-4), established/downtrend
should keep the current longer window (7-9) or be stricter. Tests this directly
rather than asserting it -- reuses the exact real-outcome mechanism (simulate_swing/
simulate_day1, base_filters_pass + trigger-cross, full multi-year population) and
the same Nifty streak-state tagging already built for the lag investigation.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import TRIGGER_CLEARANCE, simulate_swing, simulate_day1
from daily_scan import _fo_tickers
from ema34_lag_outcome_check import build_streak_state
from research.metrics import expectancy, win_rate


def regime_bucket(direction, streak_len):
    if direction == "down":
        return "downtrend"
    if streak_len <= 4:
        return "recovery"
    return "established"


def gather(tickers, streak_state, fo, verbose=False):
    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(len(df) - 1):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger:
                continue
            state = streak_state.get(pd.Timestamp(row.Date))
            if state is None:
                continue
            direction, streak_len = state
            rows.append(dict(
                ticker=t, date=row.Date, bucket=regime_bucket(direction, streak_len),
                swing_pnl=simulate_swing(df, i, trigger),
                day1_pnl=simulate_day1(df, i, trigger) if t in fo else None,
            ))
    return pd.DataFrame(rows)


def report(bucket_name, df):
    d1 = df.day1_pnl.dropna()
    print(f"    {bucket_name:<12} n={len(df):<6} SWING win={win_rate(df.swing_pnl):5.1f}% exp={expectancy(df.swing_pnl):+.3f}%   "
          f"n_opt={len(d1):<5} OPT win={win_rate(d1):5.1f}% exp={expectancy(d1):+.3f}%")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    fo = _fo_tickers()
    streak_state = build_streak_state()
    original = signals.EMA34_RISING_DAYS_MIN

    values = [2, 3, 5, 7, 9]
    try:
        for v in values:
            signals.EMA34_RISING_DAYS_MIN = v
            print(f"\n=== EMA34_RISING_DAYS_MIN = {v}{' (current)' if v == 9 else ''} ===", file=sys.stderr)
            df = gather(tickers, streak_state, fo, verbose=True)
            print(f"\nEMA34_RISING_DAYS_MIN = {v}{' (current)' if v == 9 else ''}:")
            for b in ["recovery", "established", "downtrend"]:
                report(b, df[df.bucket == b])
    finally:
        signals.EMA34_RISING_DAYS_MIN = original
