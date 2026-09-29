"""Weekend threshold re-audit (2026-09-18/19), critic-approved plan: EMA34=2 has
passed every falsification test run this session (RQ-52A/55/56/57) -- stop treating
it as the hypothesis under test. The real open question now: with EMA34=2 as the
new baseline, are RSI_MIN/MOMENTUM_20D_MIN/liquidity floor still calibrated for the
population they filter, or were they implicitly compensating for EMA34>=9's
narrower population?

One-at-a-time re-sweep (explicitly NOT a joint/multidimensional optimization, per
critic's own caution about not knowing whether a joint optimum is signal or a
historically lucky combination). For each threshold: old value, swept region, real
swing+options outcomes (fixing EMA34_RISING_DAYS_MIN=2 this time, not 9), AND the
critical new metric the critic asked for -- % of the RQ-56 "Delta" population (the
4,618 trades unique to EMA34=2) retained at each threshold value. If a threshold
disproportionately kills Delta trades as it tightens, that's the "old filter was
secretly compensating for EMA34>=9" interaction the critic is hoping to surface.
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

EMA34_BASELINE = 2


def load_delta_keys():
    """(ticker, date) keys of the RQ-56 Delta population -- trades unique to EMA34=2,
    already built and saved by ema34_delta_population_audit.py."""
    df = pd.read_csv("ema34_delta_population.csv", parse_dates=["date"])
    delta = df[df.group == "Delta"]
    return set(zip(delta.ticker, delta.date.dt.strftime("%Y-%m-%d")))


def find_breaches(tickers):
    fires = []
    for t in tickers:
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(len(df) - 1):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger:
                continue
            if not signals.base_filters_pass(row):
                continue
            fires.append((t, i, row.Date, trigger, df))
    return fires


def sweep(param_name, values, current_value, delta_keys, fo):
    original_ema34 = signals.EMA34_RISING_DAYS_MIN
    original_param = getattr(signals, param_name)
    signals.EMA34_RISING_DAYS_MIN = EMA34_BASELINE
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print(f"\n{'='*100}\nRe-sweeping {param_name} with EMA34_RISING_DAYS_MIN={EMA34_BASELINE} fixed "
          f"(production value = {current_value})\n{'='*100}")
    try:
        for v in values:
            setattr(signals, param_name, v)
            fires = find_breaches(tickers)
            n_delta_total = len(delta_keys)
            n_delta_retained = sum(1 for t, i, date, trigger, df in fires
                                    if (t, date.strftime("%Y-%m-%d")) in delta_keys)
            swing_pnls, day1_pnls = [], []
            for t, i, date, trigger, df in fires:
                swing_pnls.append(simulate_swing(df, i, trigger))
                if t in fo:
                    d1 = simulate_day1(df, i, trigger)
                    if d1 is not None:
                        day1_pnls.append(d1)
            swing = pd.Series(swing_pnls)
            day1 = pd.Series(day1_pnls)
            label = f"{v}" + (" (current)" if v == current_value else "")
            retention_pct = n_delta_retained / n_delta_total * 100 if n_delta_total else float("nan")
            print(f"  {label:<10} n={len(swing):<6} SWING win={win_rate(swing):5.1f}% exp={expectancy(swing):+.3f}% conc={concentration_v2(swing):5.1f}%   "
                  f"n_opt={len(day1):<5} OPT win={win_rate(day1):5.1f}% exp={expectancy(day1):+.3f}% conc={concentration_v2(day1):5.1f}%   "
                  f"Delta retained={retention_pct:5.1f}% ({n_delta_retained}/{n_delta_total})")
    finally:
        signals.EMA34_RISING_DAYS_MIN = original_ema34
        setattr(signals, param_name, original_param)


if __name__ == "__main__":
    fo = _fo_tickers()
    delta_keys = load_delta_keys()
    print(f"Delta population (EMA34=2-unique trades) to track retention against: n={len(delta_keys)}")

    sweep("RSI_MIN", [40, 45, 50, 55, 60, 65, 70, 75, 80], 55, delta_keys, fo)
    sweep("MOMENTUM_20D_MIN", [1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30], 1.05, delta_keys, fo)
