"""Isolated research only (2026-09-16). Checks, over the last real trading week, which
tickers would have been NEWLY primed under the actual LIVE mechanism (_passes_primed_checks
in daily_scan.py -- what shortlist_primed()/classify_candidates() actually use every day)
purely because of the MIN_TRADED_VALUE liquidity floor -- i.e. everything else about the
setup already qualifies, only liquidity blocks it under the current Rs.100cr floor.

Deliberately uses _passes_primed_checks(), NOT backtest.detect_entry()/entry_signal() --
the latter also requires checklist_pass()/reject_theta_trap(), which are NOT part of the
live primed-check gate at all (confirmed directly, 2026-09-16) -- so a "no floor" check
against entry_signal() answers a different, stricter question than what the live dashboard
would actually have shown.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import signals
import daily_scan
from pivots import daily_pivots

tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

START = pd.Timestamp("2026-09-08")
END = pd.Timestamp("2026-09-15")


def run():
    results = []
    for t in tickers:
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        mask = (df.Date >= START) & (df.Date <= END)
        for i in df.index[mask]:
            row = df.iloc[i]
            if row.corp_action_day:
                continue
            rows_upto = df.iloc[:i + 1]

            signals.MIN_TRADED_VALUE = 1_000_000_000
            primed_current = daily_scan._passes_primed_checks(t, rows_upto, row)

            signals.MIN_TRADED_VALUE = 0
            primed_no_floor = daily_scan._passes_primed_checks(t, rows_upto, row)

            if primed_no_floor and not primed_current:
                last_close = df.iloc[-1].Close
                move_since = (last_close / row.Close - 1) * 100
                results.append(dict(ticker=t, date=row.Date.date(), close=row.Close,
                                    traded_value_sma20_cr=row.traded_value_sma20 / 1e7,
                                    move_to_today_pct=move_since))

    out = pd.DataFrame(results)
    print(f"n newly primed (last week, liquidity-floor-only) = {len(out)}")
    if len(out):
        print(out.sort_values("date").to_string(index=False))


if __name__ == "__main__":
    run()
