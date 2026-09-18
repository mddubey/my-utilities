"""EMA34_RISING_DAYS_MIN, real outcome check specifically in the choppy window
(2026-09-18) -- closes the exact gap flagged in FINDINGS.md/critic_update_52.md
before this goes to the critic: a shorter threshold was already checked for (1)
aggregate quality on the FULL multi-year population (flat, no cost) and (2)
fire-TIMING shape in the recent choppy window (barely changes) -- but never for
real win/expectancy specifically WITHIN the choppy window itself, which is the
actual question a promotion decision needs (Research Integrity Rule #3:
live-representative population, not just a big historical average).

Restricts the exact same base_filters_pass()+trigger-cross population used
throughout base_filters_threshold_sweep.py to only the last 180 real Nifty
trading days (the same window characterized as choppy: median 1-day streaks,
98.9% <=5 days), one EMA34_RISING_DAYS_MIN value at a time, real swing
(check_exit()) and real options (day+1-open, F&O-scoped) outcomes -- per the
standing "check both" convention.
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
from research.metrics import expectancy, win_rate, concentration_v2


def choppy_window_start(recent_days=180):
    nifty = pd.read_csv("data_cache/_NIFTY.csv", index_col=0, parse_dates=True)
    return nifty.index[-recent_days:].min()


def find_breaches_in_window(tickers, min_date, verbose=False):
    fires = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(len(df) - 1):
            row = df.iloc[i]
            if row.Date < min_date:
                continue
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger:
                continue
            if not signals.base_filters_pass(row):
                continue
            fires.append((t, i, df, trigger))
    return fires


def run_one(tickers, min_date, fo, label):
    fires = find_breaches_in_window(tickers, min_date)
    swing_pnls, day1_pnls = [], []
    for t, i, df, trigger in fires:
        swing_pnls.append(simulate_swing(df, i, trigger))
        if t in fo:
            d1 = simulate_day1(df, i, trigger)
            if d1 is not None:
                day1_pnls.append(d1)
    swing = pd.Series(swing_pnls)
    day1 = pd.Series(day1_pnls)
    flag = "" if len(swing) >= 500 and len(day1) >= 500 else "  <-- n<500, below Research Integrity Rule #4's minimum"
    print(f"  {label:<10} n={len(swing):<6} SWING win={win_rate(swing):5.1f}% exp={expectancy(swing):+.3f}% conc={concentration_v2(swing):5.1f}%   "
          f"n_opt={len(day1):<5} OPT(day1) win={win_rate(day1):5.1f}% exp={expectancy(day1):+.3f}% conc={concentration_v2(day1):5.1f}%{flag}")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    fo = _fo_tickers()
    min_date = choppy_window_start(180)
    print(f"Choppy window: {min_date.date()} onward (last 180 real Nifty trading days)\n")

    original = signals.EMA34_RISING_DAYS_MIN
    try:
        for v in [5, 6, 7, 8, 9, 10]:
            signals.EMA34_RISING_DAYS_MIN = v
            label = f"{v}" + (" (current)" if v == 9 else "")
            run_one(tickers, min_date, fo, label)
    finally:
        signals.EMA34_RISING_DAYS_MIN = original
