"""Isolated research only (2026-09-12). Side question: of the real trigger-fires that go
LOW from day+1's open (the "flat" trades from floor_buffer_sweep.py with pnl_pct <= 0),
how many actually retrace all the way back down to the ORIGINAL raw pivot (high10_prior,
the pre-clearance base level the whole breakout was measured from) within a real horizon --
and when they do, is volume at that retracement still good enough to call it a genuine
re-entry, not just dead drift? Uses vol_zscore>=1.5, the same threshold this project
already uses for breakout_continuation's own entry confirmation (VOL_ZSCORE_MIN in
signals.py) -- consistent bar, not a new invented one.

Reuses the same 1600-trade real fireset (full history, fo_universe, breakout_cont
trigger-based) already built by floor_buffer_sweep.py.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from floor_buffer_sweep import find_trigger_fires

HORIZON_DAYS = 20  # trading days to look for a genuine pullback-to-pivot re-entry
VOL_ZSCORE_GOOD = 1.5  # same bar as signals.VOL_ZSCORE_MIN


def run():
    fo_tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()
    print("Finding real trigger-based breakout_cont fires (reusing floor_buffer_sweep's population)...")
    fires = find_trigger_fires(fo_tickers)
    print(f"n fires = {len(fires)}")

    results = []
    for f in fires:
        df = backtest.load(f["ticker"], daily_pivots)
        rows = df.reset_index()
        i = f["i"]
        if i + 1 >= len(rows):
            continue
        pivot_level = rows.iloc[i].high10_prior  # the RAW pre-clearance pivot
        day1_open = rows.iloc[i + 1].Open
        flat_pnl = (day1_open / f["entry_price"] - 1) * 100
        if flat_pnl > 0:
            continue  # only interested in "going low from open" trades

        pulled_back, good_volume, pullback_day, pullback_vz = False, False, None, None
        for j in range(i + 1, min(i + 1 + HORIZON_DAYS, len(rows))):
            row = rows.iloc[j]
            if row.corp_action_day:
                break
            if row.Low <= pivot_level:
                pulled_back = True
                pullback_day = j - i
                pullback_vz = row.vol_zscore
                good_volume = pd.notna(row.vol_zscore) and row.vol_zscore >= VOL_ZSCORE_GOOD
                break

        results.append(dict(
            ticker=f["ticker"], entry_date=f["entry_date"], flat_pnl_pct=flat_pnl,
            pivot_level=pivot_level, pulled_back_to_pivot=pulled_back,
            pullback_day=pullback_day, pullback_vol_zscore=pullback_vz, good_volume_at_pullback=good_volume,
        ))

    out = pd.DataFrame(results)
    out.to_csv("runs/pullback_to_pivot_reentry.csv", index=False)

    print(f"\n=== Trades going low from day+1 open, n={len(out)} ===")
    print(f"pulled back to raw pivot within {HORIZON_DAYS} days: {out.pulled_back_to_pivot.mean()*100:.1f}% ({out.pulled_back_to_pivot.sum()}/{len(out)})")
    pb = out[out.pulled_back_to_pivot]
    print(f"of those, showed good volume (vol_zscore>={VOL_ZSCORE_GOOD}) at the pullback: "
          f"{pb.good_volume_at_pullback.mean()*100:.1f}% ({pb.good_volume_at_pullback.sum()}/{len(pb)})")
    print(f"\nmedian day of pullback (from day+1): {pb.pullback_day.median()}")
    print(f"median vol_zscore at pullback moment: {pb.pullback_vol_zscore.median():.2f}")
    print(f"\n=> as a fraction of ALL 'going low' trades, genuine volume-confirmed re-entry: "
          f"{(pb.good_volume_at_pullback.sum() / len(out)) * 100:.1f}% ({pb.good_volume_at_pullback.sum()}/{len(out)})")


if __name__ == "__main__":
    run()
