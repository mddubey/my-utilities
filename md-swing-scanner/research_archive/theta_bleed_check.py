"""Isolated research only (2026-09-14). Last item from critic_update_35.md's reconsideration
shortlist: is theta bleed even relevant to the CURRENT day+1-exit strategy? The old
premium/time-stop rejections (2026-09-02) were built on the OLD long-hold ITM+next strategy
(median 21-day hold) -- their mechanism was "real edge lives in convex winners that need
time to recover from a 30-50% drawdown; cutting early kills them." That doesn't obviously
apply to a position closed at day+1's open/close regardless of what happens after.

Direct test proposed instead of asserting it: does DTE-at-entry correlate with the REAL
day+1 option return? If theta bleed over a single day is a small, bounded cost (as
hypothesized) except when DTE is already critically low, we should see a flat relationship
except at the very low end.

Uses real option contracts (option_backtest.simulate_option_trade, ATM/current-month --
the established recipe for a same-day/day+1 capture trade per the 2026-09-06/07 findings),
not the stock-price day1_pnl_pct proxy used elsewhere in today's work (that proxy has no
concept of DTE at all -- no option contract is ever actually picked for it).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import option_backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
SAMPLE_N = 500


class Trade:
    def __init__(self, ticker, entry_date, entry_price, exit_date, pnl_pct=0.0):
        self.ticker = ticker
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.exit_date = exit_date
        self.pnl_pct = pnl_pct


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
        stock_pnl = (daily.iloc[i + 1].Close / trigger - 1) * 100

        trade = Trade(r.ticker, r.entry_date, trigger, exit_date, stock_pnl)
        try:
            contract = option_backtest.pick_contract(r.ticker, r.entry_date, trigger, "atm", "current")
        except Exception:
            continue
        if contract is None:
            continue
        expiry, strike, lot_size = contract
        dte = option_backtest.trading_days_between(r.entry_date, expiry)

        result = option_backtest.simulate_option_trade(trade, moneyness="atm", expiry_choice="current")
        if result is None:
            continue
        rows.append(dict(ticker=r.ticker, entry_date=r.entry_date, dte=dte,
                          opt_pnl_pct=result["pnl_pct"], exit_reason=result["exit_reason"]))

    out = pd.DataFrame(rows)
    out.to_csv("runs/theta_bleed_check.csv", index=False)
    print(f"n with real option data = {len(out)}")
    return out


if __name__ == "__main__":
    run()
