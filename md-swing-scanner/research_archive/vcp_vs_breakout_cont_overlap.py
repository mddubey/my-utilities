"""Isolated research only (2026-09-12). Two questions in one pass:
1. Of real VCP (coiled_spring) bases this project's own base_pivot() detects, how many
   actually resolve into a genuine breakout (Close crosses the VCP pivot) within a real
   horizon -- and of those, how many ALSO get caught by the reactive breakout_cont trigger
   (Close > high10_prior*1.005 with vol_zscore confirmation) on the same day, vs resolve
   with breakout_cont never firing at all -- a real blind spot in the live dashboard, since
   this week's actual trades all came from breakout_cont, not coiled_spring.
2. How far ahead of the eventual breakout_cont-confirmed day the VCP base was first flagged
   (the lag distribution), and how mature/tight the base was at that point.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from vcp import base_pivot

HORIZON_DAYS = 20
TRIGGER_CLEARANCE = 1.005


def run():
    fo_tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()
    results = []
    for t in fo_tickers:
        try:
            df = backtest.load(t, daily_pivots)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        for i in range(len(rows) - 1):
            row = rows.iloc[i]
            if row.corp_action_day:
                continue
            base = base_pivot(rows, i)
            if base is None:
                continue
            pivot, structural_low = base

            resolved_day = None
            caught_by_breakout_cont = False
            for j in range(i + 1, min(i + 1 + HORIZON_DAYS, len(rows))):
                r = rows.iloc[j]
                if r.corp_action_day:
                    break
                if r.Close > pivot:
                    resolved_day = j - i
                    trigger_price = r.high10_prior * TRIGGER_CLEARANCE if pd.notna(r.high10_prior) else None
                    if (trigger_price is not None and r.Close >= trigger_price
                            and pd.notna(r.vol_zscore) and r.vol_zscore >= 1.5):
                        caught_by_breakout_cont = True
                    break

            results.append(dict(ticker=t, flag_date=row.Date, pivot=pivot,
                               resolved=resolved_day is not None, resolved_day=resolved_day,
                               caught_by_breakout_cont=caught_by_breakout_cont))

    out = pd.DataFrame(results)
    out.to_csv("runs/vcp_vs_breakout_cont_overlap.csv", index=False)

    print(f"n VCP base flags = {len(out)}")
    resolved = out[out.resolved]
    print(f"resolved (Close crossed the VCP pivot) within {HORIZON_DAYS} days: {len(resolved)} ({len(resolved)/len(out)*100:.1f}%)")
    caught = resolved[resolved.caught_by_breakout_cont]
    missed = resolved[~resolved.caught_by_breakout_cont]
    print(f"\nof resolved bases:")
    print(f"  ALSO caught by breakout_cont same day: {len(caught)} ({len(caught)/len(resolved)*100:.1f}%)")
    print(f"  MISSED by breakout_cont entirely (real move, reactive filter never fired): {len(missed)} ({len(missed)/len(resolved)*100:.1f}%)")
    print(f"\nresolution-day lag distribution (days from VCP flag to resolution):")
    print(resolved.resolved_day.describe())


if __name__ == "__main__":
    run()
