"""Isolated research only (2026-09-15+). Same-close entry-fill bias -- flagged from a
veteran-trader review on 2026-09-01 ("is the backtest's same-day-close entry actually
attainable live?"), never investigated since. Direct user challenge (2026-09-15): the
OPTIONS backtest (option_backtest.py's simulate_option_trade / theta_bleed_check_open_exit.py)
uses the option's own end-of-day ClsPric on the entry day as the cost basis -- but if the
stock keeps running through the session after the intraday breach (this project's own
"grind, not gap" finding says it usually does), that Close is priced well past the real
breach-time fill a live trader would get, in either direction (inflated cost basis on days
that keep running, deflated on days that reverse).

There's no historical intraday OPTIONS data anywhere in this project (options_cache/ is one
row per contract per DAY, not per tick), so the option's own entry-day mispricing can't be
measured directly. But the STOCK side can: intraday_cache.py has real 5-min bars (60-day
trailing window only) covering the exact same entries used throughout the SMA21/Family-C/
freshness thread (runs/pop_fresh40_small.csv / pop_fresh40_cutoff.csv, both of which already
carry a real breach_time). Since the option tracks the stock (just scaled by delta, unknown
here -- no IV column anywhere in this project, flagged repeatedly), the stock's own
Close-vs-trigger gap is a delta-agnostic, directionally honest proxy for how big this bias
actually is.

Two numbers computed per trade:
  - day1_from_trigger : (day1_open / trigger_price - 1) * 100 -- the HONEST reference, using
    the actual breach-time trigger price as cost basis (already the standing convention for
    every stock-side day1_pnl_pct in this project's research, e.g. arrival_order_check.py).
  - day1_from_close   : (day1_open / entry_day_close - 1) * 100 -- mimics the OPTIONS
    backtest's actual convention (cost basis = entry day's own Close, not the trigger).
Comparing these two directly quantifies how much the entry-price convention change moves
the reported edge, on a delta-agnostic proxy -- not a guess.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def concentration(s):
    s = s.abs()
    total = s.sum()
    return s.sort_values(ascending=False).head(10).sum() / total * 100 if total else float("nan")


def build(pop_path):
    df = pd.read_csv(pop_path, parse_dates=["entry_date", "breach_time"])
    rows = []
    for r in df.itertuples():
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0 or match[0] + 1 >= len(daily):
            continue
        i = match[0]
        row = daily.iloc[i]
        trigger_price = row.high10_prior * TRIGGER_CLEARANCE
        entry_close = row.Close
        day1_open = daily.iloc[i + 1].Open

        run_pct = (entry_close / trigger_price - 1) * 100
        day1_from_trigger = (day1_open / trigger_price - 1) * 100
        day1_from_close = (day1_open / entry_close - 1) * 100

        rows.append(dict(ticker=r.ticker, entry_date=r.entry_date, hour=r.hour,
                          freshness_score=r.freshness_score, swing_pnl_pct=r.swing_pnl_pct,
                          run_pct=run_pct, day1_from_trigger=day1_from_trigger,
                          day1_from_close=day1_from_close))
    return pd.DataFrame(rows)


def report(sub, label):
    print(f"\n{'=' * 90}\n{label} (n={len(sub)})\n{'=' * 90}")

    print(f"\n--- How far the stock runs from breach (trigger) to that day's own Close ---")
    print(f"  median run_pct = {sub.run_pct.median():+.3f}%   mean = {sub.run_pct.mean():+.3f}%")
    print(f"  % of days that ran FURTHER (Close beyond trigger, in the breakout direction): {(sub.run_pct > 0).mean()*100:.1f}%")
    print(f"  quartiles: {sub.run_pct.quantile([.1,.25,.5,.75,.9]).round(3).to_dict()}")
    print(f"  outlier check (top-10 |run_pct| concentration): {concentration(sub.run_pct):.1f}%")

    print(f"\n--- Same delta-agnostic day+1 return, TWO entry-price conventions ---")
    for col, desc in [("day1_from_trigger", "entry = trigger price (honest, breach-time proxy)"),
                       ("day1_from_close", "entry = entry-day CLOSE (mimics option_backtest.py's actual convention)")]:
        wins = sub[sub[col] > 0][col]
        wr = len(wins) / len(sub) * 100
        print(f"  {col:<20} ({desc})")
        print(f"      win={wr:5.1f}%  median={sub[col].median():+.3f}%  mean={sub[col].mean():+.3f}%")

    print(f"\n--- Split by whether the underlying swing trade eventually won or lost ---")
    for outcome, subset in [("swing WIN", sub[sub.swing_pnl_pct > 0]), ("swing LOSS", sub[sub.swing_pnl_pct <= 0])]:
        if len(subset) < 5:
            continue
        print(f"  {outcome:<10} n={len(subset):<5} median run_pct={subset.run_pct.median():+.3f}%   "
              f"day1_from_trigger median={subset.day1_from_trigger.median():+.3f}%   "
              f"day1_from_close median={subset.day1_from_close.median():+.3f}%")

    print(f"\n--- Split by breach hour (early session vs late — less room left to run) ---")
    for h, subset in sorted(sub.groupby("hour")):
        if len(subset) < 5:
            continue
        print(f"  hour={h:<3} n={len(subset):<5} median run_pct={subset.run_pct.median():+.3f}%")


def run():
    small = build("runs/pop_fresh40_small.csv")
    small.to_csv("runs/entry_fill_bias_small.csv", index=False)
    report(small, "intraday (n=365 source)")

    cutoff = build("runs/pop_fresh40_cutoff.csv")
    cutoff.to_csv("runs/entry_fill_bias_cutoff.csv", index=False)
    report(cutoff, "intraday+cutoff (n=298 source)")


if __name__ == "__main__":
    run()
