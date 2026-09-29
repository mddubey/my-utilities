"""RQ-QS-03 -- Breakout Pullback Continuation (2026-09-28 next session, critic-approved,
strictly bounded). Does the FIRST QS breakout's pullback/digestion produce a SECOND,
independently-gate-passing breakout on the same ticker within 10 trading days -- and if
so, does that second breakout behave like the short continuation QS actually wants?

Scope, exactly per critic's spec -- nothing else:
  Allowed: existing QS v0.1 breakout events, existing daily OHLCV, existing S1b stop.
  Not allowed: new indicators, new stop rules, parameter sweeps, exit optimization.
Four measurements only:
  1. How many first breakouts (A) generate a second gate-passing setup (B) on the
     SAME ticker within 10 trading days of A's entry?
  2. Of those, how many B's independently pass the v0.1 gate? (By construction, all of
     them -- B is only counted if it already passes. Reported for completeness.)
  3. D5/D10 trajectory comparison: A vs B.
  4. Days to 1R / 2R: A vs B.

Guardrails: pullback/second-setup detection uses only information known at that time
(no hindsight -- B's own trigger/gate check is the same T-1-safe formula used
everywhere else). S1b stop unchanged. If B is rare (<5-10% of A's), stop immediately
per critic's explicit instruction -- do not keep building past that point.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

from backtest import load
from pivots import daily_pivots
import primed_engine as pe
from qs_dashboard import _base_duration, GAP_BAD_THRESHOLD_PCT, MAX_TRACK_DAYS

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LOOKBACKS = (10, 20, 40)
MIN_HISTORY = 61
SECOND_SETUP_WINDOW_DAYS = 10


def passes_v01_gate(base_duration, gap_to_trigger_pct):
    return not (base_duration == 0 and gap_to_trigger_pct is not None and gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT)


def gate_check(rows, high_prior_series, i):
    """Returns (entry_price, initial_stop_price, initial_risk_pct) if a gate-passing
    trigger fires at row i, else None. Same T-1-safe formula used everywhere tonight."""
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
    initial_stop_price = row_prev.Low
    initial_risk_pct = (entry_price - initial_stop_price) / entry_price * 100
    if initial_risk_pct <= 0:
        return None
    return entry_price, initial_stop_price, initial_risk_pct


def trajectory_stats(rows, entry_i, entry_price, initial_risk_pct):
    """D5/D10 close_r, days to first 1R/2R -- through MAX_TRACK_DAYS, no exit
    simulation, pure observation per the replay MVP's own convention."""
    d5 = d10 = None
    day_1r = day_2r = None
    for k in range(1, MAX_TRACK_DAYS + 1):
        j = entry_i + k
        if j >= len(rows) or rows.iloc[j].corp_action_day:
            break
        row_k = rows.iloc[j]
        high_r = (row_k.High / entry_price - 1) * 100 / initial_risk_pct
        close_r = (row_k.Close / entry_price - 1) * 100 / initial_risk_pct
        if k == 5:
            d5 = close_r
        if k == 10:
            d10 = close_r
        if day_1r is None and high_r >= 1.0:
            day_1r = k
        if day_2r is None and high_r >= 2.0:
            day_2r = k
    return d5, d10, day_1r, day_2r


def walk_ticker(ticker, lookback):
    """Single-position walk to identify A (first breakouts, matching every other
    population tonight) -- then, independently, search for B (second gate-passing
    setup on the SAME ticker within SECOND_SETUP_WINDOW_DAYS of A's entry). A's own
    occupancy is resolved DAY BY DAY as the outer loop advances (same pattern as
    rq_qs_01/02's walk_ticker) -- not pre-resolved in one shot, which would silently
    let a new A open immediately after the previous one instead of respecting real
    multi-day occupancy."""
    try:
        rows = load(ticker, daily_pivots).reset_index()
    except FileNotFoundError:
        return []
    n_rows = len(rows)
    high_prior_series = rows.High.shift(1).rolling(lookback).max()
    results = []
    in_position = False
    cur = None  # dict: entry_i, entry_price, initial_risk_pct

    for i in range(n_rows):
        row = rows.iloc[i]
        if row.corp_action_day:
            in_position, cur = False, None
            continue

        if in_position:
            days_held = i - cur["entry_i"]
            low_r = (row.Low / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            if low_r <= -1.0 or days_held >= MAX_TRACK_DAYS:
                in_position, cur = False, None
            # fall through -- still check today for a fresh trigger below, whether A
            # just resolved this same day or is still open

        if i < MIN_HISTORY:
            continue
        gate = gate_check(rows, high_prior_series, i)
        if gate is None:
            continue
        if in_position:
            continue  # A still genuinely open -- can't start a new A here
        entry_price, initial_stop_price, initial_risk_pct = gate
        in_position = True
        cur = dict(entry_i=i, entry_price=entry_price, initial_risk_pct=initial_risk_pct)

        # search for B within the window -- a read-only forward peek for THIS specific
        # research question, not a change to A's own day-by-day occupancy state above
        b_found = None
        for j in range(i + 1, min(i + 1 + SECOND_SETUP_WINDOW_DAYS, n_rows)):
            if rows.iloc[j].corp_action_day:
                break
            gate_b = gate_check(rows, high_prior_series, j)
            if gate_b is not None:
                b_found = (j, *gate_b)
                break
        a_d5, a_d10, a_day1r, a_day2r = trajectory_stats(rows, i, entry_price, initial_risk_pct)
        rec = dict(ticker=ticker, entry_definition=lookback, a_entry_i=i,
                   a_entry_date=str(row.Date.date()), a_entry_price=entry_price,
                   a_initial_risk_pct=initial_risk_pct, a_d5_close_r=a_d5, a_d10_close_r=a_d10,
                   a_day_1r=a_day1r, a_day_2r=a_day2r, has_b=b_found is not None)
        if b_found is not None:
            bi, b_entry_price, b_stop, b_risk_pct = b_found
            b_d5, b_d10, b_day1r, b_day2r = trajectory_stats(rows, bi, b_entry_price, b_risk_pct)
            rec.update(b_entry_i=bi, b_entry_date=str(rows.iloc[bi].Date.date()),
                       b_days_after_a=bi - i, b_entry_price=b_entry_price,
                       b_initial_risk_pct=b_risk_pct, b_d5_close_r=b_d5, b_d10_close_r=b_d10,
                       b_day_1r=b_day1r, b_day_2r=b_day2r)
        results.append(rec)
    return results


def run(tickers):
    all_results = []
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
        for lb in LOOKBACKS:
            all_results.extend(walk_ticker(t, lb))
    return pd.DataFrame(all_results)


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    df = run(tickers)
    df.to_csv(f"{OUT_DIR}/rq03a_a_b_pairs.csv", index=False)

    n_a = len(df)
    n_b = df.has_b.sum()
    pct_b = n_b / n_a * 100
    print(f"\n=== 1. Frequency ===")
    print(f"Total A (first breakouts): {n_a}")
    print(f"A's with a B (second gate-passing setup within {SECOND_SETUP_WINDOW_DAYS} days): {n_b} ({pct_b:.1f}%)")

    if pct_b < 5:
        print(f"\n*** STOP CONDITION MET: {pct_b:.1f}% < 5% -- per critic's explicit guardrail, "
              f"second breakouts are too rare. Stopping here, not building further. ***")
    else:
        b_df = df[df.has_b]
        print(f"\n=== 2. All B's independently pass v0.1 gate (by construction): {len(b_df)}/{len(b_df)} (100%) ===")

        print(f"\n=== 3. D5/D10 trajectory: A vs B (n={len(b_df)}) ===")
        print(f"A: median D5={b_df.a_d5_close_r.median():.3f}R  median D10={b_df.a_d10_close_r.median():.3f}R")
        print(f"B: median D5={b_df.b_d5_close_r.median():.3f}R  median D10={b_df.b_d10_close_r.median():.3f}R")

        print(f"\n=== 4. Days to 1R / 2R: A vs B ===")
        print(f"A: %reach 1R={b_df.a_day_1r.notna().mean()*100:.1f}%  median day={b_df.a_day_1r.median()}  "
              f"| %reach 2R={b_df.a_day_2r.notna().mean()*100:.1f}%  median day={b_df.a_day_2r.median()}")
        print(f"B: %reach 1R={b_df.b_day_1r.notna().mean()*100:.1f}%  median day={b_df.b_day_1r.median()}  "
              f"| %reach 2R={b_df.b_day_2r.notna().mean()*100:.1f}%  median day={b_df.b_day_2r.median()}")

        print(f"\nDistribution of b_days_after_a (how many days after A does B fire):")
        print(b_df.b_days_after_a.value_counts().sort_index())
