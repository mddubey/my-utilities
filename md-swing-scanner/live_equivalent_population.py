"""Isolated research only (2026-09-12). The REAL fix, not another blend: everything tested
today (find_trigger_fires, full_breach_population's near-miss addition) still required
checklist_pass -- an END-OF-DAY-only condition (close-near-high, full-day volume vs
yesterday) that live_checkpoint.py's actual live dashboard never evaluates, because it
can't: those numbers don't exist yet at the moment a real trigger-cross would fire. The
live system only gates on base_filters_pass (the multi-day setup) plus the intraday price
crossing the trigger band -- confirmed directly via grep, checklist_pass appears nowhere
in live_checkpoint.py or daily_scan.py.

This rebuilds the population to match that real gate exactly: base_filters_pass holds AND
the day's intraday High crosses the trigger, full stop -- no checklist_pass, no Close-based
confirmation requirement. Still pure daily bars (High is a standard OHLC field, available
for the full multi-year history) -- no intraday cache dependency.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from signals import base_filters_pass

TRIGGER_CLEARANCE = 1.005


def find_live_equivalent_breaches(tickers):
    fires = []
    for t in tickers:
        try:
            df = backtest.load(t, daily_pivots)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        for i in range(len(rows) - 1):
            row = rows.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger_price:
                continue
            if not base_filters_pass(row):
                continue
            confirmed_by_close = row.Close >= trigger_price  # informational only, not a gate
            fires.append(dict(ticker=t, i=i, entry_date=row.Date, entry_price=trigger_price,
                              confirmed_by_close=confirmed_by_close))
    return fires


def run():
    fo_tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()
    print("Scanning full history for the REAL live-equivalent population (base_filters_pass + intraday breach only)...")
    fires = find_live_equivalent_breaches(fo_tickers)
    n_conf = sum(f["confirmed_by_close"] for f in fires)
    print(f"n total = {len(fires)}  (closed above trigger: {n_conf}, closed below: {len(fires)-n_conf})")

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
                             pnl_pct=(day1_open / f["entry_price"] - 1) * 100,
                             confirmed_by_close=f["confirmed_by_close"]))
    out = pd.DataFrame(rows_out)
    out.to_csv("runs/live_equivalent_flat.csv", index=False)

    print(f"\n=== STOCK-level, exit at day+1 open, LIVE-EQUIVALENT population n={len(out)} ===")
    print(f"win {(out.pnl_pct>0).mean()*100:.1f}%  median {out.pnl_pct.median():.2f}%  mean {out.pnl_pct.mean():.2f}%")
    conf = out[out.confirmed_by_close]
    nc = out[~out.confirmed_by_close]
    print(f"\n  closed above trigger (n={len(conf)}, {len(conf)/len(out)*100:.1f}%): win {(conf.pnl_pct>0).mean()*100:.1f}%  median {conf.pnl_pct.median():.2f}%")
    print(f"  closed below trigger (n={len(nc)}, {len(nc)/len(out)*100:.1f}%): win {(nc.pnl_pct>0).mean()*100:.1f}%  median {nc.pnl_pct.median():.2f}%")


if __name__ == "__main__":
    run()
