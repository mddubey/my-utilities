"""RQ-QS-03C -- Define B, don't optimize B (2026-09-29, critic-approved, strictly
bounded). Five candidate definitions of "the second breakout," each decision-time-safe.
Compare ONLY: number of candidates, median days after A, pullback duration, distance
from the original breakout level. NO returns, NO expectancy, NO exit design.

All five share the same walk: starting from A's entry+1, find the first day price
closes below A's entry_price (pullback begins), then track the pullback's own low and
the recovery attempt afterward. Each definition is a different, decision-time-safe
trigger condition checked day-by-day during/after that recovery -- never using
information from after the day being evaluated.

Definitions:
  D1 Close above pullback high    -- Close > the running max CLOSE since the
                                      pullback's own low (a closing-basis reclaim of
                                      the recovery attempt's own local high).
  D2 High above pullback high (IOC) -- same concept, but High > running max HIGH
                                      since the low (intraday touch, no close needed).
  D3 Close above breakout level after retest -- first Close > A's original
                                      entry_price, once a genuine pullback below it
                                      has occurred first.
  D4 First higher high after EMA21 touch -- once the pullback's Low touches at or
                                      below ema21, the first subsequent day whose
                                      High exceeds the running max High since that
                                      touch.
  D5 Current mechanical QS trigger (control) -- the same v0.1-gate-passing fresh
                                      trigger used in RQ-QS-03A, for direct comparison.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

from backtest import load
from pivots import daily_pivots
import primed_engine as pe
from qs_dashboard import _base_duration, GAP_BAD_THRESHOLD_PCT

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SEARCH_WINDOW_DAYS = 10  # same window RQ-QS-03A used, for direct comparability
MIN_HISTORY = 61


def passes_v01_gate(base_duration, gap_to_trigger_pct):
    return not (base_duration == 0 and gap_to_trigger_pct is not None and gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT)


def gate_check(rows, high_prior_series, i):
    hp = high_prior_series.iloc[i]
    if pd.isna(hp):
        return None
    entry_price = hp * pe.TRIGGER_CLEARANCE
    if rows.iloc[i].High < entry_price:
        return None
    base_dur = _base_duration(rows, high_prior_series, i)
    row_prev = rows.iloc[i - 1]
    gap_to_trigger_pct = (entry_price / row_prev.Close - 1) * 100 if row_prev.Close else None
    if not passes_v01_gate(base_dur, gap_to_trigger_pct):
        return None
    return entry_price


def find_a_positions(ticker, lookback):
    """Same single-position walk as every other script tonight -- identifies A."""
    try:
        rows = load(ticker, daily_pivots).reset_index()
    except FileNotFoundError:
        return [], None
    n_rows = len(rows)
    high_prior_series = rows.High.shift(1).rolling(lookback).max()
    a_list = []
    in_position = False
    entry_i = None
    for i in range(n_rows):
        row = rows.iloc[i]
        if row.corp_action_day:
            in_position = False
            continue
        if in_position:
            days_held = i - entry_i
            if row.Low <= a_stop_price or days_held >= 15:
                in_position = False
        if i < MIN_HISTORY:
            continue
        ep = gate_check(rows, high_prior_series, i)
        if ep is None or in_position:
            continue
        in_position = True
        entry_i = i
        a_entry_price = ep
        a_stop_price = rows.iloc[i - 1].Low
        a_list.append(dict(entry_i=i, entry_price=ep, entry_definition=lookback))
    return a_list, rows


def find_five_b_definitions(rows, a):
    """For one A, walk forward SEARCH_WINDOW_DAYS and evaluate all 5 definitions
    independently, day by day, decision-time-safe (only using info known as of that
    day's close/high, never later)."""
    ia = a["entry_i"]
    a_entry_price = a["entry_price"]
    n_rows = len(rows)
    end = min(ia + 1 + SEARCH_WINDOW_DAYS, n_rows)

    results = {d: None for d in ["D1", "D2", "D3", "D4"]}  # value = (day_offset, price) or None
    pulled_back = False
    pullback_low = None
    recovery_high_close = None
    recovery_high_high = None
    ema21_touched = False
    high_since_ema21_touch = None

    for k in range(ia + 1, end):
        if rows.iloc[k].corp_action_day:
            break
        row = rows.iloc[k]
        day_offset = k - ia

        if not pulled_back and row.Close < a_entry_price:
            pulled_back = True
            pullback_low = row.Low
            recovery_high_close = row.Close
            recovery_high_high = row.High
        elif pulled_back:
            pullback_low = min(pullback_low, row.Low)

        if pulled_back:
            # D1: close above the running recovery high (close-basis)
            if results["D1"] is None and row.Close > recovery_high_close:
                results["D1"] = (day_offset, row.Close)
            # D2: high above the running recovery high (intraday/IOC-basis)
            if results["D2"] is None and row.High > recovery_high_high:
                results["D2"] = (day_offset, row.High)
            recovery_high_close = max(recovery_high_close, row.Close)
            recovery_high_high = max(recovery_high_high, row.High)

            # D3: first close back above A's original level after a genuine dip below it
            if results["D3"] is None and row.Close > a_entry_price:
                results["D3"] = (day_offset, row.Close)

            # D4: touches EMA21, then first subsequent higher-high
            ema21 = row.get("ema21")
            if not ema21_touched and pd.notna(ema21) and row.Low <= ema21:
                ema21_touched = True
                high_since_ema21_touch = row.High
            elif ema21_touched and results["D4"] is None:
                if row.High > high_since_ema21_touch:
                    results["D4"] = (day_offset, row.High)
                high_since_ema21_touch = max(high_since_ema21_touch, row.High)

    return results


def run(tickers, lookbacks=(10, 20, 40)):
    rows_out = []
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
        for lb in lookbacks:
            a_list, rows = find_a_positions(t, lb)
            if rows is None:
                continue
            for a in a_list:
                b5 = find_five_b_definitions(rows, a)
                # D5: control -- reuse the same mechanical gate-passing search
                high_prior_series = rows.High.shift(1).rolling(lb).max()
                d5 = None
                for k in range(a["entry_i"] + 1, min(a["entry_i"] + 1 + SEARCH_WINDOW_DAYS, len(rows))):
                    if rows.iloc[k].corp_action_day:
                        break
                    ep = gate_check(rows, high_prior_series, k)
                    if ep is not None:
                        d5 = (k - a["entry_i"], ep)
                        break
                rows_out.append(dict(
                    ticker=t, entry_definition=lb, a_entry_i=a["entry_i"],
                    a_entry_price=a["entry_price"],
                    d1_days=b5["D1"][0] if b5["D1"] else None, d1_price=b5["D1"][1] if b5["D1"] else None,
                    d2_days=b5["D2"][0] if b5["D2"] else None, d2_price=b5["D2"][1] if b5["D2"] else None,
                    d3_days=b5["D3"][0] if b5["D3"] else None, d3_price=b5["D3"][1] if b5["D3"] else None,
                    d4_days=b5["D4"][0] if b5["D4"] else None, d4_price=b5["D4"][1] if b5["D4"] else None,
                    d5_days=d5[0] if d5 else None, d5_price=d5[1] if d5 else None,
                ))
    return pd.DataFrame(rows_out)


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    df = run(tickers)
    df.to_csv(f"{OUT_DIR}/rq03c_five_b_definitions.csv", index=False)

    n_a = len(df)
    print(f"\n=== RQ-QS-03C: Define B, don't optimize B (n A's = {n_a}) ===\n")
    print(f"{'Definition':<45}{'n candidates':>14}{'% of A':>9}{'median days after A':>21}{'median dist from level %':>26}")
    labels = {
        "d1": "D1 Close above pullback high",
        "d2": "D2 High above pullback high (IOC)",
        "d3": "D3 Close above breakout level after retest",
        "d4": "D4 First higher high after EMA21 touch",
        "d5": "D5 Current mechanical QS trigger (control)",
    }
    for prefix, label in labels.items():
        days_col, price_col = f"{prefix}_days", f"{prefix}_price"
        valid = df[df[days_col].notna()]
        n_cand = len(valid)
        dist_pct = (valid[price_col] / valid.a_entry_price - 1) * 100
        print(f"{label:<45}{n_cand:>14}{n_cand/n_a*100:>8.1f}%{valid[days_col].median():>21.1f}{dist_pct.median():>25.2f}%")
