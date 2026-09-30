"""RQ-QS-07A-P3 prerequisite -- Extend QS-A's envelope to D15 (2026-09-30,
critic-specified, user-authorized after a real discrepancy was caught).

`swing_qs/trajectory_replay/rq_qs_06_envelope.csv` only tracks D1-D5 --
RQ-QS-06's own deliberate scope, not an oversight ("EARLY (D1-D5), not a new
definition of the trade itself"). The critic's P3 design asks for D5/D10/
D15 close-R as PRIMARY measures, matching QS-A's real MAX_HOLD_DAYS=15
position management -- caught this gap by directly reading the file's
actual columns before building on an assumed premise, then confirmed with
the user before spending the extra build time.

REUSES, VERBATIM, NOT REIMPLEMENTED: `walk_ticker()` from
`swing_qs/trajectory_replay/rq_qs_01_opportunity_cost.py` (same dynamic-
import mechanism `rq_qs_06_early_monetization_envelope.py` itself uses) for
the entry/gate/stop DEFINITION -- entry price, initial_risk_pct, S1b stop,
frozen v0.1 gate, 10D/20D/40D lookbacks. NOTHING about entry/exit rules
changes here. This script only extends the MEASUREMENT layer already built
in `envelope()` (same corp-action truncation logic, same R-multiple
convention, same running-MFE/MAE-from-High/Low convention) from DAYS=[1..5]
to DAYS=[1..15] -- a longer observation window on the exact same already-
defined trade, not an intervention.

Written to `swing_qs_07a/` (this track's own directory), NOT overwriting or
modifying anything in `swing_qs/` -- QS-A's original D1-D5 envelope file
stays exactly as RQ-QS-06 left it. This is purely an extended re-measurement
for RQ-QS-07A-P3's own purposes.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

TRAJ_DIR = "swing_qs/trajectory_replay"
sys.path.insert(0, TRAJ_DIR)
from importlib.util import spec_from_file_location, module_from_spec
_spec = spec_from_file_location("rq_qs_01", os.path.join(TRAJ_DIR, "rq_qs_01_opportunity_cost.py"))
rq_qs_01 = module_from_spec(_spec)
_spec.loader.exec_module(rq_qs_01)
walk_ticker = rq_qs_01.walk_ticker

from backtest import load
from pivots import daily_pivots

OUT_DIR = "swing_qs_07a"
R_LEVELS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
DAYS = list(range(1, 16))  # extended from RQ-QS-06's [1,2,3,4,5]


def envelope(rows, a):
    """Identical logic to rq_qs_06_early_monetization_envelope.py's envelope(),
    generalized from DAYS=[1..5] to DAYS=[1..15]. Same corp-action truncation
    (25% threshold, this script's own stricter-than-production check, same
    Rule #22 catch already documented in the original), same R-multiple
    convention, same running-MFE/MAE tracking."""
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

    rec["stopped_by_D15"] = stopped_by_day
    for r in R_LEVELS:
        rec[f"first_hit_day_{r}R"] = first_hit_day[r]

    mfe_last = rec.get("mfe_D15")
    close_last = rec.get("close_r_D15")
    if first_hit_day[0.5] is not None and mfe_last is not None and close_last is not None and mfe_last > 0:
        rec["giveback_from_mfe_pct"] = (mfe_last - close_last) / mfe_last * 100
    else:
        rec["giveback_from_mfe_pct"] = None

    for d in DAYS:
        close_r = rec.get(f"close_r_D{d}")
        stopped_already = stopped_by_day is not None and stopped_by_day <= d
        hit_1r_by_d = first_hit_day[1.0] is not None and first_hit_day[1.0] <= d
        rec[f"unresolved_D{d}"] = bool(not stopped_already and not hit_1r_by_d)
    return rec


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    all_a = []
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
        for lb in (10, 20, 40):
            a_positions, _ = walk_ticker(t, lb)
            all_a.extend(a_positions)
    print(f"\n{len(all_a)} frozen QS-A positions (10D/20D/40D, S1b, gate v0.1) across {len(tickers)} tickers "
          f"-- should match the original envelope's 46,613 (verified below)")

    cache = {}
    recs = []
    for n, a in enumerate(all_a):
        if n % 5000 == 0:
            print(f"envelope {n}/{len(all_a)}", flush=True)
        rows = cache.setdefault(a["ticker"], load(a["ticker"], daily_pivots).reset_index())
        recs.append(envelope(rows, a))
    df = pd.DataFrame(recs)
    df.to_csv(f"{OUT_DIR}/qsa_envelope_d15.csv", index=False)
    print(f"\nSaved {OUT_DIR}/qsa_envelope_d15.csv ({len(df):,} rows)")

    original = pd.read_csv(f"{TRAJ_DIR}/rq_qs_06_envelope.csv")
    print(f"\nCross-check vs original D1-D5 envelope: original n={len(original):,}, this n={len(df):,} "
          f"({'MATCH' if len(original) == len(df) else 'MISMATCH -- investigate before trusting anything downstream'})")
    merged_check = df.merge(original[["ticker", "entry_definition", "entry_date", "close_r_D5"]],
                              on=["ticker", "entry_definition", "entry_date"], suffixes=("_new", "_orig"))
    diff = (merged_check.close_r_D5_new - merged_check.close_r_D5_orig).abs()
    print(f"D5 close_r reproduction check (this script's D5 vs original's D5, {len(merged_check):,} matched rows): "
          f"max abs diff = {diff.max():.6f} (should be ~0 -- same walk_ticker(), same envelope logic through D5)")
