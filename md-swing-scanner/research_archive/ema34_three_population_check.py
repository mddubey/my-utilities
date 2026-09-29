"""EMA34_RISING_DAYS_MIN, the exact RQ-51 three-population promotion check
(2026-09-18) -- direct user request to see this new lead evaluated against the
same standard this project already uses for every promotion decision
(Research Integrity Rule #3): Primed Gate (full history), Entry Gate (full
history), and the real intraday+13:00-cutoff population (the only one that's
actually live-representative). RQ-51 rejected RSI_MIN/MOMENTUM_20D_MIN on
exactly this test -- both looked great on the first two, and vanished on the
third. This is the same test, run on EMA34_RISING_DAYS_MIN instead.

Primed Gate: base_filters_threshold_sweep.py's established mechanism
(base_filters_pass() + intraday High-cross via daily OHLC, full multi-year).
Entry Gate: backtest.detect_entry(require_regime=False), breakout_cont only,
same convention as min_traded_value_ablation.py.
Real intraday+13:00 cutoff: real 5-min intraday_cache (the ~69-day window),
base_filters_pass() + intraday High crossing the trigger at or before 13:00 IST.
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from datetime import time as dtime

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import _load_intraday, simulate_swing, simulate_day1, TRIGGER_CLEARANCE
from daily_scan import _fo_tickers
from research.metrics import expectancy, win_rate, concentration_v2

CUTOFF = dtime(13, 0)


def primed_gate(tickers, fo, verbose=False):
    swing_pnls, day1_pnls = [], []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  primed {n}/{len(tickers)}", file=sys.stderr)
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
            swing_pnls.append(simulate_swing(df, i, trigger))
            if t in fo:
                d1 = simulate_day1(df, i, trigger)
                if d1 is not None:
                    day1_pnls.append(d1)
    return pd.Series(swing_pnls), pd.Series(day1_pnls)


def entry_gate(tickers, fo, verbose=False):
    swing_pnls, day1_pnls = [], []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  entry {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(len(df) - 1):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            candidate = backtest.detect_entry(t, df, i, require_regime=False)
            if candidate is None or candidate[0] != "breakout_cont":
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            swing_pnls.append(simulate_swing(df, i, trigger))
            if t in fo:
                d1 = simulate_day1(df, i, trigger)
                if d1 is not None:
                    day1_pnls.append(d1)
    return pd.Series(swing_pnls), pd.Series(day1_pnls)


def real_intraday_cutoff(tickers, fo, verbose=False):
    swing_pnls, day1_pnls = [], []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  intraday {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        intraday_df, naive_day = _load_intraday(t)
        if intraday_df is None:
            continue
        intraday_dates = set(naive_day.unique())
        for i in range(len(df) - 1):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            date_norm = pd.Timestamp(row.Date).normalize()
            if date_norm not in intraday_dates:
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            day_bars = intraday_df[naive_day == date_norm]
            before_cutoff = day_bars[day_bars.index.time <= CUTOFF]
            if before_cutoff.empty or before_cutoff.High.max() < trigger:
                continue
            swing_pnls.append(simulate_swing(df, i, trigger))
            if t in fo:
                d1 = simulate_day1(df, i, trigger)
                if d1 is not None:
                    day1_pnls.append(d1)
    return pd.Series(swing_pnls), pd.Series(day1_pnls)


def report(label, swing, day1):
    print(f"  {label:<10} n={len(swing):<6} SWING win={win_rate(swing):5.1f}% exp={expectancy(swing):+.3f}% conc={concentration_v2(swing):5.1f}%   "
          f"n_opt={len(day1):<5} OPT(day1) win={win_rate(day1):5.1f}% exp={expectancy(day1):+.3f}% conc={concentration_v2(day1):5.1f}%")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    fo = _fo_tickers()
    original = signals.EMA34_RISING_DAYS_MIN

    values = [3, 5, 9]  # peak, midpoint, current -- keep this run fast; extend if needed
    try:
        for v in values:
            signals.EMA34_RISING_DAYS_MIN = v
            label = f"{v}" + (" (current)" if v == 9 else "")
            print(f"\n=== EMA34_RISING_DAYS_MIN = {label} ===")
            print("Primed Gate (full history):")
            report(label, *primed_gate(tickers, fo, verbose=True))
            print("Entry Gate (full history, require_regime=False):")
            report(label, *entry_gate(tickers, fo, verbose=True))
            print("Real intraday+13:00-cutoff (real 5-min cache, ~69 days):")
            report(label, *real_intraday_cutoff(tickers, fo, verbose=True))
    finally:
        signals.EMA34_RISING_DAYS_MIN = original
