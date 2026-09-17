"""Isolated research only (2026-09-12). Fixes a real gap in floor_buffer_sweep.py's
fireset: that population only counted a trade if the day's CLOSE also confirmed above the
trigger (breakout_continuation's own condition). A real IOC order fills the MOMENT the
intraday High crosses the trigger, regardless of what the close later does -- so any day
that breached intraday and then reversed to close BELOW the trigger was silently excluded,
even though a real trader would have been filled and left holding a loser. This rebuilds
the population as the UNION of confirmed fires (Close > high10_prior, same as before) and
near-miss fires (signals.near_miss_high_breakout -- High > high10_prior but Close didn't
hold), which together are every real intraday breach the pattern's other filters allow,
confirmed or not.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from signals import near_miss_high_breakout

TRIGGER_CLEARANCE = 1.005


def find_all_real_breaches(tickers):
    fires = []
    for t in tickers:
        try:
            df = backtest.load(t, daily_pivots)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        for i in range(len(rows) - 1):
            row = rows.iloc[i]
            if row.corp_action_day:
                continue
            trigger_price = row.high10_prior * TRIGGER_CLEARANCE if pd.notna(row.high10_prior) else None
            if trigger_price is None:
                continue

            candidate = backtest.detect_entry(t, rows, i, require_regime=False)
            confirmed = candidate is not None and candidate[0] == "breakout_cont" and row.Close >= trigger_price
            near_miss = (not confirmed) and near_miss_high_breakout(row) and row.High >= trigger_price

            if not (confirmed or near_miss):
                continue
            fires.append(dict(ticker=t, i=i, entry_date=row.Date, entry_price=trigger_price,
                              confirmed=confirmed))
    return fires


def run():
    fo_tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()
    print("Scanning full history for every real intraday breach (confirmed + near-miss)...")
    fires = find_all_real_breaches(fo_tickers)
    n_confirmed = sum(f["confirmed"] for f in fires)
    n_near_miss = len(fires) - n_confirmed
    print(f"n total = {len(fires)}  (confirmed: {n_confirmed}, near-miss/false-start: {n_near_miss})")

    rows_out = []
    for f in fires:
        df = backtest.load(f["ticker"], daily_pivots)
        rows = df.reset_index()
        i = f["i"]
        if i + 1 >= len(rows):
            continue
        day1_row = rows.iloc[i + 1]
        day1_open = day1_row.Open
        rows_out.append(dict(ticker=f["ticker"], entry_date=f["entry_date"], exit_date=day1_row.Date,
                             entry_price=f["entry_price"], exit_price=day1_open,
                             pnl_pct=(day1_open / f["entry_price"] - 1) * 100, confirmed=f["confirmed"]))
    out = pd.DataFrame(rows_out)
    out.to_csv("runs/full_breach_flat.csv", index=False)

    print(f"\n=== STOCK-level, exit at day+1 open, FULL population n={len(out)} ===")
    print(f"win {(out.pnl_pct>0).mean()*100:.1f}%  median {out.pnl_pct.median():.2f}%  mean {out.pnl_pct.mean():.2f}%")
    conf = out[out.confirmed]
    nm = out[~out.confirmed]
    print(f"\n  confirmed-only (n={len(conf)}): win {(conf.pnl_pct>0).mean()*100:.1f}%  median {conf.pnl_pct.median():.2f}%")
    print(f"  near-miss/false-start (n={len(nm)}): win {(nm.pnl_pct>0).mean()*100:.1f}%  median {nm.pnl_pct.median():.2f}%")


if __name__ == "__main__":
    run()
