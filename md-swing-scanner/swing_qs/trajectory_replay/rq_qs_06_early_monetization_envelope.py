"""RQ-QS-06 -- QS-A Early Monetization Envelope (2026-09-29, critic-specified).

Frozen inputs, per critic's exact spec: existing canonical QS-A population, existing
S1b risk unit, NO new entry filter, NO new pattern, NO parameter optimization. Reuses
`walk_ticker()` from `rq_qs_01_opportunity_cost.py` VERBATIM (imported, not
reimplemented) -- the exact same single-position, gate-passing, S1b-stopped A
sequence QS_V01_ENTRY_GATE.md's own population table describes. This script adds
ONLY a new measurement layer on top: how much of the eventual move is available
EARLY (D1-D5), not a new definition of the trade itself.

Question this answers (critic's exact framing): "Does QS-A contain a sufficiently
frequent, sufficiently early favorable excursion that could plausibly be monetized
within a few trading days?" NOT "what's the best stock exit" -- no returns-based
selection, no threshold selection, no exit rule chosen here. Report the full
distribution and stop.

Per critic: use HIGH-based excursion first (does the opportunity exist at all,
intraday-touch, matching this project's raw-trigger convention throughout), report
close-based/sustained outcomes separately, not conflated.

Measured per A position, day-by-day D1..D5:
  close_r, running MFE (High-based, cumulative), running MAE (Low-based, cumulative)
  first-hit day for R in [0.25, 0.5, 0.75, 1.0, 1.5, 2.0] (High-based, "did the
      opportunity exist", not "did we act on it")
  stopped_by_day (Low-based <=-1R, S1b) if it happens within D5
  giveback_from_first_0.5R: once 0.5R is first touched intraday, how much of that
      peak (measured from the true running MFE by D5, not just the first-touch day)
      is given back by D5's close -- this is the critic's "giveback after first
      meaningful excursion," 0.5R chosen as "meaningful" per this project's own
      Meaningful Win Rate convention (>=0.25R is meaningful; 0.5R is one step up,
      "quality" per the reporting-stack convention already adopted 2026-09-26)
  unresolved_by_day: has NOT reached >=1R (real win) AND has NOT stopped out, by
      that day -- for D1/D2/D3/D5
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from importlib.util import spec_from_file_location, module_from_spec
_spec = spec_from_file_location("rq_qs_01", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rq_qs_01_opportunity_cost.py"))
rq_qs_01 = module_from_spec(_spec)
_spec.loader.exec_module(rq_qs_01)
walk_ticker = rq_qs_01.walk_ticker

from backtest import load
from pivots import daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
R_LEVELS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
DAYS = [1, 2, 3, 4, 5]


def envelope(rows, a):
    entry_i = a["entry_i"]
    entry_price = a["entry_price"]
    risk_pct = a["initial_risk_pct"]
    n_rows = len(rows)

    rec = dict(ticker=a["ticker"], entry_definition=a["entry_definition"],
                entry_date=a["entry_date"], entry_price=entry_price, initial_risk_pct=risk_pct)

    running_mfe, running_mae = -float("inf"), float("inf")
    stopped_by_day = None
    first_hit_day = {r: None for r in R_LEVELS}
    truncated = False
    for d in DAYS:
        k = entry_i + d
        # Own, stricter corp-action check -- production's corp_action_day column uses a
        # 35% threshold; caught via Rule #22 hand-verification that a real bonus-issue
        # move (TRENT, 2026-01-01, -33.04%) slipped through it. 25% here, still well
        # above any plausible single-day organic move for this population, closes that
        # gap for THIS script without touching the shared production column.
        real_jump = False
        if k < n_rows and 0 < k - 1 < n_rows:
            prev_close = rows.iloc[k - 1].Close
            real_jump = bool(prev_close and abs(rows.iloc[k].Close / prev_close - 1) > 0.25)
        if k >= n_rows or rows.iloc[k].corp_action_day or real_jump or truncated:
            truncated = True
            rec[f"close_r_D{d}"] = None
            rec[f"mfe_D{d}"] = running_mfe if running_mfe != -float("inf") else None
            rec[f"mae_D{d}"] = running_mae if running_mae != float("inf") else None
            continue
        row = rows.iloc[k]
        close_r = (row.Close / entry_price - 1) * 100 / risk_pct
        high_r = (row.High / entry_price - 1) * 100 / risk_pct
        low_r = (row.Low / entry_price - 1) * 100 / risk_pct
        running_mfe = max(running_mfe, high_r)
        running_mae = min(running_mae, low_r)
        rec[f"close_r_D{d}"] = close_r
        rec[f"mfe_D{d}"] = running_mfe
        rec[f"mae_D{d}"] = running_mae
        if stopped_by_day is None and low_r <= -1.0:
            stopped_by_day = d
        for r in R_LEVELS:
            if first_hit_day[r] is None and running_mfe >= r:
                first_hit_day[r] = d

    rec["stopped_by_D5"] = stopped_by_day
    for r in R_LEVELS:
        rec[f"first_hit_day_{r}R"] = first_hit_day[r]

    mfe5 = rec.get("mfe_D5")
    close5 = rec.get("close_r_D5")
    if first_hit_day[0.5] is not None and mfe5 is not None and close5 is not None and mfe5 > 0:
        rec["giveback_from_mfe_pct"] = (mfe5 - close5) / mfe5 * 100
    else:
        rec["giveback_from_mfe_pct"] = None

    for d in DAYS:
        close_r = rec.get(f"close_r_D{d}")
        stopped_already = stopped_by_day is not None and stopped_by_day <= d
        hit_1r_by_d = first_hit_day[1.0] is not None and first_hit_day[1.0] <= d
        rec[f"unresolved_D{d}"] = bool(not stopped_already and not hit_1r_by_d)
    return rec


def pstack(s, fmt="{:.2f}", suffix=""):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return "  ".join(f"P{p}={fmt.format(np.percentile(s, p))}{suffix}" for p in [25, 50, 75, 90]) + f"  (n={len(s)})"


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    all_a = []
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
        for lb in (10, 20, 40):
            a_positions, _ = walk_ticker(t, lb)
            all_a.extend(a_positions)
    print(f"\n{len(all_a)} frozen QS-A positions (10D/20D/40D, S1b, gate v0.1) across {len(tickers)} tickers")

    cache = {}
    recs = []
    for n, a in enumerate(all_a):
        if n % 5000 == 0:
            print(f"envelope {n}/{len(all_a)}", flush=True)
        rows = cache.setdefault(a["ticker"], load(a["ticker"], daily_pivots).reset_index())
        recs.append(envelope(rows, a))
    df = pd.DataFrame(recs)
    df.to_csv(f"{OUT_DIR}/rq_qs_06_envelope.csv", index=False)

    print(f"\n=== RQ-QS-06: Early Monetization Envelope (n={len(df)}) ===\n")
    print("--- First-hit day (High-based MFE), among those that ever reach it within D5 ---")
    for r in R_LEVELS:
        col = f"first_hit_day_{r}R"
        reached = df[col].notna()
        print(f"  {r}R: reached by D5 = {reached.sum()} ({reached.mean()*100:.1f}%)  "
              f"median day = {df[col].median():.0f}" if reached.sum() else f"  {r}R: reached by D5 = 0")

    print("\n--- Close-R distribution by day ---")
    for d in DAYS:
        print(f"  D{d}: {pstack(df[f'close_r_D{d}'], '{:.2f}', 'R')}")

    print("\n--- MFE distribution by day (running max High-based R) ---")
    for d in DAYS:
        print(f"  D{d}: {pstack(df[f'mfe_D{d}'], '{:.2f}', 'R')}")

    print("\n--- MAE distribution by day (running min Low-based R) ---")
    for d in DAYS:
        print(f"  D{d}: {pstack(df[f'mae_D{d}'], '{:.2f}', 'R')}")

    print(f"\n--- Stopped out by D5 (S1b, -1R) ---")
    print(f"  {df.stopped_by_D5.notna().sum()} ({df.stopped_by_D5.notna().mean()*100:.1f}%)  "
          f"median day = {df.stopped_by_D5.median():.0f}")

    print(f"\n--- Giveback from D5 MFE (only where >=0.5R was touched at some point by D5) ---")
    print(f"  {pstack(df.giveback_from_mfe_pct, '{:.1f}', '%')}")
    gb = df.giveback_from_mfe_pct.dropna()
    print(f"  % giving back >=50% of their D5 peak: {(gb>=50).mean()*100:.1f}%   "
          f"% giving back >=80%: {(gb>=80).mean()*100:.1f}%   % giving back the WHOLE thing (>=100%, i.e. close<=0): {(gb>=100).mean()*100:.1f}%")

    print(f"\n--- Unresolved (no stop, no 1R yet) by day ---")
    for d in DAYS:
        print(f"  D{d}: {df[f'unresolved_D{d}'].mean()*100:.1f}%")
