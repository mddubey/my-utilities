"""Weekend threshold re-audit, Freshness leg (2026-09-18/19). Freshness isn't a hard
base_filters_pass() gate in production -- there's no threshold to sweep. The real
question, per critic: does the established Primed-Gate/Entry-Gate Freshness
relationship survive once EMA34_RISING_DAYS_MIN moves from 9 to 2, using the exact
same Fresh/Extended cutoff (freshness_score<=0.40) already validated, not a new bin.
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
from live_checkpoint import _freshness_score
from research.metrics import expectancy, win_rate

FRESH_CUTOFF = 0.40


def primed_gate(tickers, ema34_min, fo, verbose=False):
    original = signals.EMA34_RISING_DAYS_MIN
    signals.EMA34_RISING_DAYS_MIN = ema34_min
    rows = []
    try:
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
                fresh = _freshness_score(row)
                rows.append(dict(
                    fresh=(fresh is not None and fresh <= FRESH_CUTOFF),
                    swing_pnl=simulate_swing(df, i, trigger),
                    day1_pnl=simulate_day1(df, i, trigger) if t in fo else None,
                ))
    finally:
        signals.EMA34_RISING_DAYS_MIN = original
    return pd.DataFrame(rows)


def entry_gate(tickers, ema34_min, fo, verbose=False):
    original = signals.EMA34_RISING_DAYS_MIN
    signals.EMA34_RISING_DAYS_MIN = ema34_min
    rows = []
    try:
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
                fresh = _freshness_score(row)
                rows.append(dict(
                    fresh=(fresh is not None and fresh <= FRESH_CUTOFF),
                    swing_pnl=simulate_swing(df, i, trigger),
                    day1_pnl=simulate_day1(df, i, trigger) if t in fo else None,
                ))
    finally:
        signals.EMA34_RISING_DAYS_MIN = original
    return pd.DataFrame(rows)


def report(label, df):
    for fresh_flag, name in [(True, "Fresh"), (False, "Extended")]:
        d = df[df.fresh == fresh_flag]
        d1 = d.day1_pnl.dropna()
        print(f"  {label:<12} {name:<9} n={len(d):<6} SWING win={win_rate(d.swing_pnl):5.1f}% exp={expectancy(d.swing_pnl):+.3f}%   "
              f"n_opt={len(d1):<5} OPT win={win_rate(d1):5.1f}% exp={expectancy(d1):+.3f}%")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    fo = _fo_tickers()

    for ema34_min in [2, 9]:
        print(f"\n{'='*90}\nEMA34_RISING_DAYS_MIN = {ema34_min}\n{'='*90}", file=sys.stderr)
        print(f"\n=== EMA34_RISING_DAYS_MIN = {ema34_min} ===")
        pg = primed_gate(tickers, ema34_min, fo, verbose=True)
        report("Primed Gate", pg)
        eg = entry_gate(tickers, ema34_min, fo, verbose=True)
        report("Entry Gate", eg)
