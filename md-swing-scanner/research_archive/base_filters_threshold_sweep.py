"""Isolated research only (2026-09-17). Three core base_filters_pass() thresholds --
RSI_MIN, EMA34_RISING_DAYS_MIN, MOMENTUM_20D_MIN -- have NEVER been swept since the
project's first commit (2026-08-30), unlike RSI_MAX (properly re-swept, RQ-34,
2026-09-13) or VOL_ZSCORE_MIN/vcp.LAST_LEG_TOLERANCE (swept once, 2026-08-30/31).

Deliberately NOT freshness-conditioned: freshness_score is itself
0.5*percentile(RSI14) + 0.5*percentile(mom20) -- the same two quantities RSI_MIN/
MOMENTUM_20D_MIN gate on. Conditioning a re-sweep of those thresholds on freshness
would be circular. Instead: reuse the exact "real live-equivalent population"
mechanism from live_equivalent_population.py (base_filters_pass + intraday High-cross
via daily OHLC, full multi-year, no intraday_cache dependency) -- the same population
choice RQ-34 already used properly for RSI_MAX.

One threshold swept at a time, the other two held at their current production value.
Reports REAL swing (backtest.check_exit(), current mechanism) and REAL options
(day+1-open, F&O-scoped subset) -- both, per the project's standing "check both"
convention.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from research.metrics import win_rate, expectancy, concentration_v2

TRIGGER_CLEARANCE = 1.005

daily_cache = {}


def load_daily(t):
    if t not in daily_cache:
        daily_cache[t] = backtest.load(t, daily_pivots).reset_index()
    return daily_cache[t]


def find_breaches(tickers):
    """Exact mechanism from live_equivalent_population.py: base_filters_pass() (reads
    whatever signals.RSI_MIN/EMA34_RISING_DAYS_MIN/MOMENTUM_20D_MIN are set to at call
    time) AND the day's real intraday High crosses the trigger."""
    fires = []
    for t in tickers:
        df = load_daily(t)
        for i in range(len(df) - 1):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger_price:
                continue
            if not signals.base_filters_pass(row):
                continue
            fires.append((t, i, row.Date, trigger_price))
    return fires


def simulate_swing(t, i, trigger_price):
    """Real production stock-side exit -- structural_low-1xATR + SMA21-2% trail +
    MAX_HOLD_DAYS=15, exactly as wired into backtest.py right now."""
    df = load_daily(t)
    row = df.iloc[i]
    lo = max(0, i - backtest.STRUCTURAL_LOOKBACK_BC)
    structural_low = df.iloc[lo:i].Low.min() if i > lo else trigger_price * 0.9
    state = dict(entry_price=trigger_price, peak_close=trigger_price, peak_high=row.High,
                 structural_low=structural_low, target=None, days_held=0, atr_entry=row.atr14)
    for j in range(i + 1, len(df)):
        r2 = df.iloc[j]
        if r2.corp_action_day:
            return (state["peak_close"] / trigger_price - 1) * 100
        reason, state = backtest.check_exit("breakout_cont", state, r2)
        if reason is not None:
            return (r2.Close / trigger_price - 1) * 100
    return (df.iloc[-1].Close / trigger_price - 1) * 100


def simulate_day1(t, i, trigger_price):
    df = load_daily(t)
    if i + 1 >= len(df):
        return None
    day1_open = df.iloc[i + 1].Open
    return (day1_open / trigger_price - 1) * 100


def run_one(tickers, fo_tickers, label):
    fires = find_breaches(tickers)
    swing_pnls, day1_pnls = [], []
    for t, i, date, trigger_price in fires:
        swing_pnls.append(simulate_swing(t, i, trigger_price))
        if t in fo_tickers:
            d1 = simulate_day1(t, i, trigger_price)
            if d1 is not None:
                day1_pnls.append(d1)
    swing = pd.Series(swing_pnls)
    day1 = pd.Series(day1_pnls)
    print(f"  {label:<10} n={len(swing):<6} SWING win={win_rate(swing):5.1f}% exp={expectancy(swing):+.3f}% conc={concentration_v2(swing):5.1f}%   "
          f"n_opt={len(day1):<5} OPT(day1) win={win_rate(day1):5.1f}% exp={expectancy(day1):+.3f}% conc={concentration_v2(day1):5.1f}%")


def sweep(param_name, values, current_value):
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    fo_tickers = set(pd.read_csv("fo_universe.csv", header=None)[0])
    print(f"\n{'='*100}\nSweeping {param_name} (current production value = {current_value}), others held fixed\n{'='*100}")
    original = getattr(signals, param_name)
    try:
        for v in values:
            setattr(signals, param_name, v)
            label = f"{v}" + (" (current)" if v == current_value else "")
            run_one(tickers, fo_tickers, label)
    finally:
        setattr(signals, param_name, original)


if __name__ == "__main__":
    sweep("RSI_MIN", [55, 60, 65, 70, 75, 80, 85], 55)
    sweep("MOMENTUM_20D_MIN", [1.05, 1.10, 1.15, 1.20, 1.25, 1.30], 1.05)
