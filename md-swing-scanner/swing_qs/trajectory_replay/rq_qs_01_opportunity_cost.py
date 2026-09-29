"""RQ-QS-01 -- Opportunity Cost of Occupancy (2026-09-28, critic-approved).

Self-contained: does NOT reuse qs_raw_{N}d_full.csv, because that file's single-
position windows were built with population_builder's real primed_engine trailing-
stop exit mechanics -- a DIFFERENT convention from QS's own frozen product (S1b fixed
stop, the one everything else tonight -- the gate, the dashboard, the Feature Battle
labels -- actually uses). Using primed_engine's exit windows to decide "is this ticker
occupied" while measuring outcomes in S1b terms would silently mix two different
products. This script re-walks the single-position simulation itself, using ONLY QS's
real mechanics (raw N-day trigger, frozen v0.1 gate, S1b stop, MAX_TRACK_DAYS cap) --
consistent with qs_dashboard.py and qs_trajectory_replay.py, not reimplemented
differently.

Phase 1: raw trigger calendar (every day, ignoring occupancy) + the actual single-
         position A-sequence (S1b-based) run in parallel over the same walk.
Phase 2: classify A's state (winner/proven/unresolved/underwater) at each blocked B's
         trigger day.
Phase 3: compare A's outcome from B's day forward vs B's own trajectory from entry.

No new filters, no exit redesign, no threshold tuning -- per RQ-QS-01.md's bounded
deliverable.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

from backtest import load
from pivots import daily_pivots
import primed_engine as pe
from qs_dashboard import _base_duration, GAP_BAD_THRESHOLD_PCT, MAX_TRACK_DAYS, STOP_R, PROOF_R

SCRATCH_OUT = os.path.dirname(os.path.abspath(__file__))
LOOKBACKS = (10, 20, 40)
MIN_HISTORY = 61  # matches qs_dashboard.py's morning() minimum


def passes_v01_gate(base_duration, gap_to_trigger_pct):
    return not (base_duration == 0 and gap_to_trigger_pct is not None and gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT)


def max_r_through(rows, entry_i, entry_price, initial_risk_pct, through_i):
    """Max High-based R reached from entry_i+1 through through_i (inclusive), capped
    at MAX_TRACK_DAYS days and stopping early if S1b (-1R) is breached first."""
    max_r, days = -float("inf"), 0
    for k in range(entry_i + 1, min(through_i, entry_i + MAX_TRACK_DAYS) + 1):
        if k >= len(rows) or rows.iloc[k].corp_action_day:
            break
        days += 1
        row_k = rows.iloc[k]
        high_r = (row_k.High / entry_price - 1) * 100 / initial_risk_pct
        low_r = (row_k.Low / entry_price - 1) * 100 / initial_risk_pct
        if high_r > max_r:
            max_r = high_r
        if low_r <= STOP_R:
            return max_r, days, True  # stopped
    return (max_r if max_r != -float("inf") else None), days, False


def walk_ticker(ticker, lookback):
    """Returns (a_positions, blocked_events) for one ticker/lookback.
    a_positions: list of dicts, the actual single-position-blocked S1b sequence.
    blocked_events: list of dicts, raw v0.1-gate-passing triggers that fell inside
    an earlier A's open window."""
    try:
        rows = load(ticker, daily_pivots).reset_index()
    except FileNotFoundError:
        return [], []
    n_rows = len(rows)
    high_prior_series = rows.High.shift(1).rolling(lookback).max()

    a_positions = []
    blocked_events = []
    in_position = False
    cur = None  # dict: entry_i, entry_price, initial_risk_pct, exit_i

    for i in range(n_rows):
        row = rows.iloc[i]
        if row.corp_action_day:
            in_position = False
            cur = None
            continue

        if in_position:
            days_held = i - cur["entry_i"]
            high_r = (row.High / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            low_r = (row.Low / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            cur["max_r"] = max(cur["max_r"], high_r)
            stopped = low_r <= STOP_R
            capped = days_held >= MAX_TRACK_DAYS
            if stopped or capped:
                cur["exit_i"] = i
                cur["exit_reason"] = "stop" if stopped else "max_days"
                a_positions.append(cur)
                in_position = False
                cur = None
            # fall through to also check for a blocked trigger THIS SAME day below

        if i < MIN_HISTORY:
            continue
        hp = high_prior_series.iloc[i]
        if pd.isna(hp):
            continue
        entry_price = hp * pe.TRIGGER_CLEARANCE
        if row.High < entry_price:
            continue  # no raw trigger today

        base_duration = _base_duration(rows, high_prior_series, i)
        row_t1 = rows.iloc[i - 1]
        gap_to_trigger_pct = (entry_price / row_t1.Close - 1) * 100 if row_t1.Close else None

        if in_position:
            # blocked -- record if it independently passes the gate
            if passes_v01_gate(base_duration, gap_to_trigger_pct):
                blocked_events.append(dict(
                    ticker=ticker, entry_definition=lookback, blocker_entry_i=cur["entry_i"],
                    blocker_entry_date=str(rows.iloc[cur["entry_i"]].Date.date()),
                    blocker_entry_price=cur["entry_price"], blocker_initial_risk_pct=cur["initial_risk_pct"],
                    b_trigger_i=i, b_entry_date=str(row.Date.date()), b_entry_price=entry_price,
                    b_initial_stop_price=row_t1.Low,
                ))
            continue  # ticker occupied, can't open a fresh A here regardless

        # not in position and gate check for opening a FRESH A position
        if not passes_v01_gate(base_duration, gap_to_trigger_pct):
            continue
        initial_stop_price = row_t1.Low
        initial_risk_pct = (entry_price - initial_stop_price) / entry_price * 100
        if initial_risk_pct <= 0:
            continue
        in_position = True
        cur = dict(ticker=ticker, entry_definition=lookback, entry_i=i,
                    entry_date=str(row.Date.date()), entry_price=entry_price,
                    initial_stop_price=initial_stop_price, initial_risk_pct=initial_risk_pct,
                    max_r=-float("inf"))

    return a_positions, blocked_events


def classify_blocker_state(a_max_r_so_far):
    if a_max_r_so_far is None:
        return "unresolved"
    if a_max_r_so_far >= 1.0:
        return "winner"
    if a_max_r_so_far >= PROOF_R:
        return "proven"
    if a_max_r_so_far < 0:
        return "underwater"
    return "unresolved"


def run(tickers):
    all_a, all_blocked = [], []
    for n, t in enumerate(tickers):
        if n % 50 == 0:
            print(f"{n}/{len(tickers)} tickers, {len(all_blocked)} blocked events so far", flush=True)
        for lb in LOOKBACKS:
            a_pos, blocked = walk_ticker(t, lb)
            all_a.extend(a_pos)
            all_blocked.extend(blocked)
    return all_a, all_blocked


def phase3_compare(blocked_events):
    """For each blocked event, compute A's outcome from block-day forward and B's
    outcome from its own entry forward, both via the same S1b/MAX_TRACK_DAYS walk."""
    results = []
    cache = {}
    for ev in blocked_events:
        t = ev["ticker"]
        if t not in cache:
            try:
                cache[t] = load(t, daily_pivots).reset_index()
            except FileNotFoundError:
                cache[t] = None
        rows = cache[t]
        if rows is None:
            continue

        # classify A's state as of B's trigger day (day BEFORE b_trigger_i, i.e. up to and
        # including the day before B triggers -- B's own day belongs to B, not A's tally)
        a_max_r_so_far, _, a_already_stopped = max_r_through(
            rows, ev["blocker_entry_i"], ev["blocker_entry_price"], ev["blocker_initial_risk_pct"],
            through_i=ev["b_trigger_i"] - 1)
        blocker_state = classify_blocker_state(a_max_r_so_far)

        # A's outcome from B's block day forward (continuing to hold A)
        a_future_max_r, a_days, a_stopped = max_r_through(
            rows, ev["b_trigger_i"] - 1, ev["blocker_entry_price"], ev["blocker_initial_risk_pct"],
            through_i=ev["b_trigger_i"] - 1 + MAX_TRACK_DAYS)

        # B's own outcome from its own entry forward
        b_max_r, b_days, b_stopped = max_r_through(
            rows, ev["b_trigger_i"], ev["b_entry_price"],
            (ev["b_entry_price"] - ev["b_initial_stop_price"]) / ev["b_entry_price"] * 100,
            through_i=ev["b_trigger_i"] + MAX_TRACK_DAYS)

        def bucket(max_r):
            if max_r is None:
                return "unresolved"
            if max_r >= 2.0:
                return "blast"
            if max_r >= PROOF_R:
                return "drift"
            return "failure"

        a_bucket, b_bucket = bucket(a_future_max_r), bucket(b_max_r)
        a_blasts, b_blasts = a_bucket == "blast", b_bucket == "blast"
        # clean, exhaustive 4-way partition on "did A blast" x "did B blast" -- matches
        # critic's table exactly (a_bucket=="drift" counts as "A stalls" here, same as
        # "failure"/"unresolved" -- critic's "A stalls" means "A did NOT blast", any reason)
        if not a_blasts and b_blasts:
            outcome = "A_STALLS_B_BLASTS"
        elif a_blasts and not b_blasts:
            outcome = "A_WINS_B_LOSES"
        elif a_blasts and b_blasts:
            outcome = "A_WINS_B_WINS"
        else:
            outcome = "A_LOSES_B_LOSES"

        results.append(dict(
            **ev, blocker_state_at_block=blocker_state, a_max_r_at_block=a_max_r_so_far,
            a_future_max_r=a_future_max_r, b_max_r=b_max_r, outcome=outcome,
        ))
    return results


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print("Phase 1: walking single-position sequences + raw blocked triggers...")
    a_positions, blocked_events = run(tickers)
    print(f"\nDone. {len(a_positions)} A positions taken, {len(blocked_events)} v0.1-gate-passing blocked triggers.")

    tickers_with_blocks = len(set(e["ticker"] for e in blocked_events))
    print(f"\n=== Phase 1 frequency report (per guardrail 3) ===")
    print(f"Tickers with >=1 blocked trigger: {tickers_with_blocks} / {len(tickers)}")
    print(f"Total blocked triggers (already v0.1-gate-filtered): {len(blocked_events)}")

    print("\nPhase 2+3: classifying blocker state and comparing A vs B...")
    results = phase3_compare(blocked_events)
    df = pd.DataFrame(results)
    df.to_csv(f"{SCRATCH_OUT}/replacement_analysis.csv", index=False)
    pd.DataFrame(a_positions).to_csv(f"{SCRATCH_OUT}/blocked_trigger_calendar.csv", index=False)

    print(f"\n=== Phase 1 (continued): blocked-while-unresolved specifically ===")
    print(df.blocker_state_at_block.value_counts())

    print(f"\n=== Phase 3: outcome distribution (n={len(df)}) ===")
    print(df.outcome.value_counts())

    print(f"\n=== Top 25 'A stalls, B blasts' ===")
    gold = df[df.outcome == "A_STALLS_B_BLASTS"].sort_values("b_max_r", ascending=False).head(25)
    print(gold[["ticker", "entry_definition", "blocker_entry_date", "b_entry_date",
                "blocker_state_at_block", "a_future_max_r", "b_max_r"]].to_string(index=False))
