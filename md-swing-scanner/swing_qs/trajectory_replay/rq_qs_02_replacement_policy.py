"""RQ-QS-02 -- Replacement Policy (2026-09-28, critic-approved, bounded to exactly
three policies, no scoring, no proven/winner replacement).

Three policies, compared on portfolio expectancy (mean R per realized trade, and
aggregate R per ticker-lookback over the full history):
  never_replace      -- current baseline (A holds until its own natural stop/cap exit)
  replace_unresolved -- if a fresh, v0.1-gate-passing trigger B appears while A is
                        classified "unresolved" (A < 0.25R, not stopped), close A NOW
                        (realized at today's close) and open B in its place
  replace_underwater -- same, but only when A is specifically "underwater"

This is a genuine re-simulation (not a post-hoc reclassification of RQ-QS-01's
descriptive data) because replacing A with B changes the position sequence going
forward -- exactly what the "no overlapping positions" guardrail requires: at any
moment exactly one position is open per ticker, never both A and B simultaneously.

Reuses the same mechanics as rq_qs_01_opportunity_cost.py (raw N-day trigger, frozen
v0.1 gate, S1b stop, MAX_TRACK_DAYS cap) -- not reimplemented differently.
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

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LOOKBACKS = (10, 20, 40)
MIN_HISTORY = 61
POLICIES = ("never_replace", "replace_unresolved", "replace_underwater")


def passes_v01_gate(base_duration, gap_to_trigger_pct):
    return not (base_duration == 0 and gap_to_trigger_pct is not None and gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT)


def classify_state(max_r_so_far):
    if max_r_so_far is None or max_r_so_far == -float("inf"):
        return "unresolved"
    if max_r_so_far >= 1.0:
        return "winner"
    if max_r_so_far >= PROOF_R:
        return "proven"
    if max_r_so_far < 0:
        return "underwater"
    return "unresolved"


def walk_ticker_policy(ticker, lookback, policy):
    try:
        rows = load(ticker, daily_pivots).reset_index()
    except FileNotFoundError:
        return []
    n_rows = len(rows)
    high_prior_series = rows.High.shift(1).rolling(lookback).max()

    realized = []
    in_position = False
    cur = None

    for i in range(n_rows):
        row = rows.iloc[i]
        if row.corp_action_day:
            if in_position:
                cur["exit_i"], cur["exit_reason"] = i, "corp_action"
                realized.append(cur)
            in_position, cur = False, None
            continue

        if in_position:
            days_held = i - cur["entry_i"]
            high_r = (row.High / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            low_r = (row.Low / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            close_r = (row.Close / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            cur["max_r"] = max(cur["max_r"], high_r)
            stopped = low_r <= STOP_R
            capped = days_held >= MAX_TRACK_DAYS
            if stopped or capped:
                cur["exit_i"] = i
                cur["exit_reason"] = "stop" if stopped else "max_days"
                cur["exit_r"] = STOP_R if stopped else close_r
                realized.append(cur)
                in_position, cur = False, None
            # fall through: even if just closed, check today for a fresh/replacement trigger below

        if i < MIN_HISTORY:
            continue
        hp = high_prior_series.iloc[i]
        if pd.isna(hp):
            continue
        entry_price = hp * pe.TRIGGER_CLEARANCE
        if row.High < entry_price:
            continue

        base_duration = _base_duration(rows, high_prior_series, i)
        row_t1 = rows.iloc[i - 1]
        gap_to_trigger_pct = (entry_price / row_t1.Close - 1) * 100 if row_t1.Close else None
        if not passes_v01_gate(base_duration, gap_to_trigger_pct):
            continue

        if in_position:
            # candidate B: decide whether to replace, per policy
            state = classify_state(cur["max_r"])
            close_r_now = (row.Close / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            should_replace = (
                (policy == "replace_unresolved" and state == "unresolved") or
                (policy == "replace_underwater" and state == "underwater")
            )
            if not should_replace:
                continue  # blocked, A holds, policy says leave it alone
            # replace: close A now at today's close, open B in its place
            cur["exit_i"], cur["exit_reason"], cur["exit_r"] = i, f"replaced_by_B_({state})", close_r_now
            realized.append(cur)
            in_position = False
            cur = None
            # fall through to open B below

        initial_stop_price = row_t1.Low
        initial_risk_pct = (entry_price - initial_stop_price) / entry_price * 100
        if initial_risk_pct <= 0:
            continue
        in_position = True
        cur = dict(ticker=ticker, entry_definition=lookback, entry_i=i,
                    entry_date=str(row.Date.date()), entry_price=entry_price,
                    initial_stop_price=initial_stop_price, initial_risk_pct=initial_risk_pct,
                    max_r=-float("inf"))

    if in_position:
        # still open at data end -- unresolved, excluded from realized-trade stats
        pass

    return realized


def run_policy(tickers, policy):
    all_trades = []
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"  [{policy}] {n}/{len(tickers)}", flush=True)
        for lb in LOOKBACKS:
            all_trades.extend(walk_ticker_policy(t, lb, policy))
    return all_trades


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    summary_rows = []
    for policy in POLICIES:
        print(f"Running policy: {policy}")
        trades = run_policy(tickers, policy)
        df = pd.DataFrame(trades)
        df.to_csv(f"{OUT_DIR}/rq02_{policy}_trades.csv", index=False)
        n = len(df)
        mean_r = df.exit_r.mean()
        median_r = df.exit_r.median()
        win_pct = (df.exit_r > 0).mean() * 100
        total_r = df.exit_r.sum()
        n_replaced = (df.exit_reason.str.startswith("replaced_by_B")).sum() if n else 0
        summary_rows.append(dict(policy=policy, n_trades=n, mean_r=round(mean_r, 4),
                                  median_r=round(median_r, 4), win_pct=round(win_pct, 1),
                                  total_r=round(total_r, 1), n_replaced=n_replaced))
        print(f"  n={n}  mean_r={mean_r:.4f}  median_r={median_r:.4f}  win%={win_pct:.1f}  "
              f"total_r={total_r:.1f}  n_replaced={n_replaced}\n")

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(f"{OUT_DIR}/rq02_policy_summary.csv", index=False)
    print("\n=== RQ-QS-02 Policy Comparison ===")
    print(summary.to_string(index=False))
