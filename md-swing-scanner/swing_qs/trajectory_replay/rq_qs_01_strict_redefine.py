"""Critic's tighter A-stalls/B-blasts redefinition (2026-09-28) -- tiny tweak, not a
new RQ, per critic's own framing. Reuses replacement_analysis.csv's already-computed
blocked events, just re-derives the stall/blast check strictly against the QS product
definition instead of the looser 15-day-window version:

  A stalls  = never reaches +1R by day10 (from A's OWN entry) OR closes below +0.25R
              at day10 (or at the last available day, if A has fewer than 10 days left).
  B blasts  = >=2R by day5 specifically (not "eventually within 15 days"), matching
              the standard BLAST definition exactly.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

from backtest import load
from pivots import daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_DAYS = 15


def trajectory(rows, entry_i, entry_price, initial_risk_pct):
    """Returns dict day->(high_r, close_r) for up to MAX_DAYS forward, stopping early
    on corp action (not on stop -- we need the FULL day10 checkpoint even past a
    hypothetical -1R touch, since 'closes below 0.25R at day10' needs the real path)."""
    out = {}
    for k in range(entry_i + 1, min(entry_i + 1 + MAX_DAYS, len(rows))):
        row_k = rows.iloc[k]
        if row_k.corp_action_day:
            break
        day = k - entry_i
        high_r = (row_k.High / entry_price - 1) * 100 / initial_risk_pct
        close_r = (row_k.Close / entry_price - 1) * 100 / initial_risk_pct
        out[day] = (high_r, close_r)
    return out


def a_stalls(traj):
    days = sorted(traj.keys())
    if not days:
        return True
    reaches_1r_by_10 = any(h >= 1.0 for d, (h, c) in traj.items() if d <= 10)
    last_day_le_10 = max(d for d in days if d <= 10) if any(d <= 10 for d in days) else max(days)
    close_at_10_or_last = traj[last_day_le_10][1]
    return (not reaches_1r_by_10) or (close_at_10_or_last < 0.25)


def b_blasts(traj):
    return any(h >= 2.0 for d, (h, c) in traj.items() if d <= 5)


if __name__ == "__main__":
    df = pd.read_csv(f"{OUT_DIR}/replacement_analysis.csv", parse_dates=["blocker_entry_date", "b_entry_date"])
    cache = {}
    strict_outcomes = []
    for n, ev in enumerate(df.itertuples()):
        if n % 5000 == 0:
            print(f"{n}/{len(df)}", flush=True)
        t = ev.ticker
        if t not in cache:
            try:
                cache[t] = load(t, daily_pivots).reset_index()
            except FileNotFoundError:
                cache[t] = None
        rows = cache[t]
        if rows is None:
            strict_outcomes.append(None)
            continue
        a_traj = trajectory(rows, ev.blocker_entry_i, ev.blocker_entry_price, ev.blocker_initial_risk_pct)
        b_initial_risk_pct = (ev.b_entry_price - ev.b_initial_stop_price) / ev.b_entry_price * 100
        b_traj = trajectory(rows, ev.b_trigger_i, ev.b_entry_price, b_initial_risk_pct)

        a_bad = a_stalls(a_traj)
        b_good = b_blasts(b_traj)
        if a_bad and b_good:
            strict_outcomes.append("A_STALLS_B_BLASTS_STRICT")
        elif (not a_bad) and (not b_good):
            strict_outcomes.append("A_OK_B_NO")
        elif (not a_bad) and b_good:
            strict_outcomes.append("A_OK_B_BLASTS")
        else:
            strict_outcomes.append("A_STALLS_B_NO")

    df["strict_outcome"] = strict_outcomes
    df.to_csv(f"{OUT_DIR}/replacement_analysis.csv", index=False)

    print(f"\n=== Strict A-stalls/B-blasts redefinition, n={len(df)} ===")
    print(df.strict_outcome.value_counts())
    print()
    print("By blocker_state_at_block:")
    print(pd.crosstab(df.blocker_state_at_block, df.strict_outcome, normalize="index").mul(100).round(1).to_string())
