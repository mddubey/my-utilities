"""Isolated research only (2026-09-12). ONE consolidated test, replacing the scattered
individual checks from today: for every real breach (base_filters_pass + intraday High
crossed the trigger -- the honest, live-dashboard-equivalent gate, no checklist_pass),
measure how far past the trigger price it actually got that same day (day0's own High vs
the trigger), split into "cleared by >=1% further" vs "barely touched it," and check both:
(a) does it close the day as a genuine breakout candidate (Close still above trigger), and
(b) how does day+1's open look, for each bucket.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from signals import base_filters_pass

TRIGGER_CLEARANCE = 1.005
FURTHER_THRESHOLD_PCT = 1.0  # "caught 1% further" past the trigger, intraday


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

            max_pct_further = (row.High / trigger_price - 1) * 100
            confirmed_by_close = row.Close >= trigger_price
            day1_open = rows.iloc[i + 1].Open
            day1_pnl_pct = (day1_open / trigger_price - 1) * 100

            results.append(dict(ticker=t, entry_date=row.Date, max_pct_further=max_pct_further,
                               confirmed_by_close=confirmed_by_close, day1_pnl_pct=day1_pnl_pct))

    out = pd.DataFrame(results)
    out.to_csv("runs/one_clean_test.csv", index=False)

    print(f"n = {len(out)}")
    caught_further = out[out.max_pct_further >= FURTHER_THRESHOLD_PCT]
    barely = out[out.max_pct_further < FURTHER_THRESHOLD_PCT]

    for label, sub in [(f"Caught >={FURTHER_THRESHOLD_PCT}% further intraday", caught_further),
                        ("Barely touched the trigger (<1% further)", barely)]:
        print(f"\n--- {label}, n={len(sub)} ({len(sub)/len(out)*100:.1f}%) ---")
        print(f"  closed as a real breakout candidate (Close still above trigger): {sub.confirmed_by_close.mean()*100:.1f}%")
        print(f"  day+1 open: win {(sub.day1_pnl_pct>0).mean()*100:.1f}%  median {sub.day1_pnl_pct.median():.2f}%  mean {sub.day1_pnl_pct.mean():.2f}%")


if __name__ == "__main__":
    run()
