"""Isolated research only (2026-09-12). The ACTIONABLE version of one_clean_test.py:
instead of using "did it reach 1% past the trigger" as a hindsight label on a trade already
bought at the raw trigger, this only enters ONCE that 1%-further level has actually been
confirmed intraday -- a real, executable "wait for confirmation" rule, not lookahead. Entry
price becomes trigger*1.01 (IOC-style fill at the confirmation level), not the raw trigger.

Compares, for the SAME population (stocks that did eventually confirm 1% further that same
day): day+1 outcome from the confirmed/delayed entry vs. from the raw trigger entry -- does
waiting for confirmation (a worse average price) still leave a good expected value, or does
the cost of waiting eat the edge that showed up in the hindsight version?
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from signals import base_filters_pass

TRIGGER_CLEARANCE = 1.005
CONFIRM_THRESHOLD = 1.01  # confirmed entry level: trigger * (1 + 1%)


def run():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    results = []
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

            confirm_price = trigger_price * CONFIRM_THRESHOLD
            if row.High < confirm_price:
                continue  # never actually confirmed same day -- this delayed rule never fires here

            day1_open = rows.iloc[i + 1].Open
            raw_entry_pnl = (day1_open / trigger_price - 1) * 100
            confirmed_entry_pnl = (day1_open / confirm_price - 1) * 100
            results.append(dict(ticker=t, entry_date=row.Date,
                               raw_entry_pnl=raw_entry_pnl, confirmed_entry_pnl=confirmed_entry_pnl))

    out = pd.DataFrame(results)
    out.to_csv("runs/confirmed_delayed_entry.csv", index=False)

    print(f"n = {len(out)} (only stocks that DID confirm {int((CONFIRM_THRESHOLD-1)*100)}% further intraday)")
    print(f"\n--- If bought at the RAW trigger (no wait) ---")
    print(f"win {(out.raw_entry_pnl>0).mean()*100:.1f}%  median {out.raw_entry_pnl.median():.2f}%  mean {out.raw_entry_pnl.mean():.2f}%")
    print(f"\n--- If bought only after CONFIRMED (waited for the 1% follow-through) ---")
    print(f"win {(out.confirmed_entry_pnl>0).mean()*100:.1f}%  median {out.confirmed_entry_pnl.median():.2f}%  mean {out.confirmed_entry_pnl.mean():.2f}%")


if __name__ == "__main__":
    run()
