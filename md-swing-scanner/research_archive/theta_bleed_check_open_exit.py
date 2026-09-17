"""Isolated research only (2026-09-14). Correction to theta_bleed_check.py: that script used
simulate_option_trade()'s built-in Close-to-Close exit, but the actual adopted day+1 recipe
(FINDINGS.md, 2026-09-06/07) exits near day+1's OPEN, not its close ("the open isn't the
ceiling, it's a safe floor; the real opportunity is intraday on day+1, not a multi-day hold"
-- and Close-based day+1 exit was documented as dramatically worse, 45.5% vs 82.0% win for
ATM). Rebuilds the exact same 500-trade sample (same random_state=42) with entry_px =
entry day's option ClsPric (the already-established, flagged approximation for a real
intraday fill) and exit_px = day+1's option OpnPric (the real, adopted exit point).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import option_backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
SAMPLE_N = 500


def run():
    df = pd.read_csv("runs/pop_fresh40_big.csv", parse_dates=["entry_date"])
    sample = df.sample(n=min(SAMPLE_N, len(df)), random_state=42)
    print(f"sampling {len(sample)} of {len(df)}")

    daily_cache = {}
    rows = []
    for idx, r in enumerate(sample.itertuples(), 1):
        if idx % 50 == 0:
            print(f"  {idx}/{len(sample)}", flush=True)
        if r.ticker not in daily_cache:
            daily_cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        daily = daily_cache[r.ticker]
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0 or match[0] + 1 >= len(daily):
            continue
        i = match[0]
        trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
        exit_date = daily.iloc[i + 1].Date

        contract = option_backtest.pick_contract(r.ticker, r.entry_date, trigger, "atm", "current")
        if contract is None:
            continue
        expiry, strike, lot_size = contract
        dte = option_backtest.trading_days_between(r.entry_date, expiry)

        entry_row = option_backtest.option_row(r.ticker, r.entry_date, expiry, strike)
        if entry_row is None or not entry_row.ClsPric or not option_backtest.liquid(entry_row):
            continue
        entry_px = entry_row.ClsPric

        exit_row = option_backtest.option_row(r.ticker, exit_date, expiry, strike)
        if exit_row is None or not exit_row.OpnPric or not option_backtest.liquid(exit_row):
            continue
        exit_px = exit_row.OpnPric

        pnl_pct = (exit_px / entry_px - 1) * 100
        rows.append(dict(ticker=r.ticker, entry_date=r.entry_date, dte=dte, opt_pnl_pct=pnl_pct))

    out = pd.DataFrame(rows)
    out.to_csv("runs/theta_bleed_check_open_exit.csv", index=False)
    print(f"n with real option data = {len(out)}")


if __name__ == "__main__":
    run()
