"""EMA34_RISING_DAYS_MIN lag check (2026-09-18) -- direct follow-up to a real user
observation: fires go quiet right when Nifty turns green (filter hasn't caught up
yet) and stay elevated for several days after Nifty turns red (stale qualification
from the prior uptrend). Confirmed via the days-into-a-move / fires-per-day table
in FINDINGS.md. Nifty's own real daily streak lengths (median 1 day, 98.9% <=5
days, 0% reach 9+ in the last ~180 trading days) show the current market is
choppy enough that this lag is close to the *normal* condition, not a rare
trend-turn edge case.

Two checks, both against a shorter EMA34_RISING_DAYS_MIN (5/6/7/8 instead of the
current 9):
  1. Aggregate win/expectancy on the standard full multi-year population -- reuses
     base_filters_threshold_sweep.py's existing sweep() unchanged (already
     established, no need to re-derive).
  2. Does a shorter window actually reduce the lag, specifically in the recent
     choppy window (last ~180 trading days), not diluted by the whole multi-year
     history's mix of regime characters -- the days-into-a-move fire-count table,
     rebuilt per EMA34_RISING_DAYS_MIN value.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import TRIGGER_CLEARANCE
from base_filters_threshold_sweep import sweep


def fires_per_day_recent(tickers, recent_days=180, verbose=False):
    """Real breach count per calendar day, restricted to the last `recent_days`
    trading days present in the Nifty index cache (the choppy window in question)."""
    nifty = pd.read_csv("data_cache/_NIFTY.csv", index_col=0, parse_dates=True)
    recent_dates = set(nifty.index[-recent_days:])
    min_date = min(recent_dates)

    fire_counts = {}
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(len(df)):
            row = df.iloc[i]
            if row.Date < min_date:
                continue
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger:
                continue
            fire_counts[row.Date] = fire_counts.get(row.Date, 0) + 1
    return pd.Series(fire_counts).sort_index()


def lag_table(tickers, ema34_min, recent_days=180):
    original = signals.EMA34_RISING_DAYS_MIN
    signals.EMA34_RISING_DAYS_MIN = ema34_min
    try:
        fires = fires_per_day_recent(tickers, recent_days)
    finally:
        signals.EMA34_RISING_DAYS_MIN = original

    nifty = pd.read_csv("data_cache/_NIFTY.csv", index_col=0, parse_dates=True)
    nifty["ret_pct"] = nifty.Close.pct_change() * 100
    merged = pd.concat([fires.rename("n_fires"), nifty["ret_pct"]], axis=1).dropna()

    streak = 0
    ups = []
    for v in merged.ret_pct > 0:
        streak = streak + 1 if v else 0
        ups.append(streak)
    merged["consec_up"] = ups

    streak = 0
    downs = []
    for v in merged.ret_pct <= 0:
        streak = streak + 1 if v else 0
        downs.append(streak)
    merged["consec_down"] = downs

    up_table = merged[merged.consec_up > 0].groupby("consec_up").n_fires.mean().head(5)
    down_table = merged[merged.consec_down > 0].groupby("consec_down").n_fires.mean().head(5)
    return up_table, down_table


if __name__ == "__main__":
    print("=== 1. Aggregate win/expectancy, full multi-year population (unchanged mechanism) ===")
    sweep("EMA34_RISING_DAYS_MIN", [5, 6, 7, 8, 9, 10], 9)

    print("\n=== 2. Lag shape in the recent choppy window (last 180 trading days), by EMA34_RISING_DAYS_MIN ===")
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    for v in [5, 6, 7, 9]:
        print(f"\n-- EMA34_RISING_DAYS_MIN = {v} --", file=sys.stderr)
        up_t, down_t = lag_table(tickers, v, recent_days=180)
        print(f"EMA34_RISING_DAYS_MIN={v}:")
        print(f"  days into up-move   -> mean fires: {dict(up_t.round(2))}")
        print(f"  days into down-move -> mean fires: {dict(down_t.round(2))}")
