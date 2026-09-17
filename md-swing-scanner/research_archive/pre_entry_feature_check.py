"""Isolated research only (2026-09-12). Reverse-engineering what's DIFFERENT, using only
information knowable AT OR BEFORE the moment of the intraday trigger cross, between real
breakouts and false ones -- on the full, honest raw-trigger population (base_filters_pass +
intraday High crossed the trigger, no checklist_pass, no lookahead).

Candidate features, all knowable before/at entry (none use today's own Close or full-day
Volume, which was today's earlier mistake):
  - gap_at_open_pct: today's Open vs yesterday's Close (known at market open)
  - dist_to_trigger_pct: how far the trigger sits above yesterday's Close (known before
    today's session even starts -- how big a jump was needed)
  - yday_rsi14: yesterday's RSI (not today's -- today's isn't fully known until close)
  - yday_vol_zscore: yesterday's volume z-score (was the setup already building volume
    BEFORE today, as opposed to today's own volume which isn't fully known at breach time)
  - yday_momentum_20d: yesterday's Close vs 20-days-ago Close
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from signals import base_filters_pass

TRIGGER_CLEARANCE = 1.005


def run():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    results = []
    for t in tickers:
        try:
            df = backtest.load(t, daily_pivots)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        for i in range(1, len(rows) - 1):
            row = rows.iloc[i]
            yday = rows.iloc[i - 1]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger_price:
                continue
            if not base_filters_pass(row):
                continue

            day1_open = rows.iloc[i + 1].Open
            day1_pnl_pct = (day1_open / trigger_price - 1) * 100

            results.append(dict(
                ticker=t, entry_date=row.Date, day1_pnl_pct=day1_pnl_pct,
                gap_at_open_pct=(row.Open / yday.Close - 1) * 100,
                dist_to_trigger_pct=(trigger_price / yday.Close - 1) * 100,
                yday_rsi14=yday.rsi14,
                yday_vol_zscore=yday.vol_zscore,
                yday_momentum_20d=(yday.Close / yday.close_20ago - 1) * 100 if pd.notna(yday.close_20ago) else None,
            ))

    out = pd.DataFrame(results)
    out.to_csv("runs/pre_entry_feature_check.csv", index=False)
    print(f"n = {len(out)}")

    features = ["gap_at_open_pct", "dist_to_trigger_pct", "yday_rsi14", "yday_vol_zscore", "yday_momentum_20d"]
    for feat in features:
        sub = out.dropna(subset=[feat])
        if len(sub) < 100:
            continue
        sub = sub.copy()
        sub["q"] = pd.qcut(sub[feat].rank(method="first"), 4, labels=["Q1(low)", "Q2", "Q3", "Q4(high)"])
        print(f"\n=== {feat} (n={len(sub)}) ===")
        g = sub.groupby("q", observed=True).agg(
            n=("day1_pnl_pct", "count"),
            win_rate=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
            median=("day1_pnl_pct", "median"),
        )
        print(g)


if __name__ == "__main__":
    run()
