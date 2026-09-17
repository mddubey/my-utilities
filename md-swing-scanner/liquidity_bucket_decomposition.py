"""RQ-48 (Tier A, critic-specified after Update 47): liquidity floor bucket
decomposition. Checks for a Simpson's-Paradox confound in the earlier MIN_TRADED_VALUE
ablation (2026-09-16) -- was "removing the floor improves every metric" driven uniformly
across the whole 0-100cr range, or concentrated in one bucket?

Reuses runs/min_traded_value_0.csv (already built 2026-09-16: full nifty500 universe,
no liquidity floor, real swing_pnl_pct via the CURRENT production check_exit() mechanism,
freshness_score already computed) -- not re-scanned from scratch.

Adds one new dimension the original ablation didn't check: real options availability and
outcome per bucket (F&O eligibility + a real, liquid ATM/ITM current-month contract via
option_backtest.pick_contract()/liquid(), day1_pnl_pct via real premiums, not the day1_open
stock-proxy already in the file).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import option_backtest
from pivots import daily_pivots
from research.metrics import concentration_v2 as concentration, win_rate, expectancy

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def wstats(pnl):
    return win_rate(pnl), pnl.median(), expectancy(pnl), concentration(pnl)


def simulate_option_day1(ticker, entry_date, moneyness):
    df = load_daily(ticker)
    match = df.index[df.Date == entry_date]
    if len(match) == 0 or match[0] + 1 >= len(df):
        return None
    i = match[0]
    entry_price = df.iloc[i].high10_prior * 1.005
    contract = option_backtest.pick_contract(ticker, entry_date, entry_price, moneyness, "current")
    if contract is None:
        return None
    expiry, strike, lot_size = contract
    entry_row = option_backtest.option_row(ticker, entry_date, expiry, strike)
    if entry_row is None or not entry_row.ClsPric or not option_backtest.liquid(entry_row):
        return None
    entry_px = entry_row.ClsPric
    exit_date = df.iloc[match[0] + 1].Date
    exit_row = option_backtest.option_row(ticker, exit_date, expiry, strike)
    if exit_row is None or not exit_row.OpnPric or not option_backtest.liquid(exit_row):
        return None
    return (exit_row.OpnPric / entry_px - 1) * 100


def run():
    df = pd.read_csv("runs/min_traded_value_0.csv", parse_dates=["entry_date"])
    fo_tickers = set(pd.read_csv("fo_universe.csv", header=None)[0])
    fresh = df.dropna(subset=["freshness_score"])
    fresh = fresh[fresh.freshness_score <= 0.40].copy()
    fresh["traded_value_cr"] = fresh.traded_value_sma20 / 1e7

    buckets = [(0, 25), (25, 50), (50, 75), (75, 100), (100, float("inf"))]
    print(f"n (freshness<=0.40, full universe, no floor) = {len(fresh)}\n")

    for lo, hi in buckets:
        sub = fresh[(fresh.traded_value_cr >= lo) & (fresh.traded_value_cr < hi)]
        label = f"Rs.{lo}-{hi}cr" if hi != float("inf") else f"Rs.{lo}cr+"
        if len(sub) < 5:
            print(f"{label:<14} n={len(sub):<5} (too thin)")
            continue
        wr, med, exp, conc = wstats(sub.swing_pnl_pct)
        print(f"{label:<14} n={len(sub):<5} SWING  win={wr:5.1f}%  med={med:+.2f}%  exp={exp:+.3f}%  conc={conc:.1f}%")

        fo_sub = sub[sub.ticker.isin(fo_tickers)]
        fo_pct = len(fo_sub) / len(sub) * 100
        print(f"{'':<14} n={len(fo_sub):<5} F&O-eligible ({fo_pct:.0f}% of bucket)")

        if len(fo_sub) >= 5:
            atm_results = []
            n_available = 0
            for r in fo_sub.itertuples():
                res = simulate_option_day1(r.ticker, r.entry_date, "atm")
                if res is not None:
                    n_available += 1
                    atm_results.append(res)
            avail_pct = n_available / len(fo_sub) * 100
            print(f"{'':<14} real ATM contract available for {n_available}/{len(fo_sub)} ({avail_pct:.0f}%) of F&O-eligible entries")
            if len(atm_results) >= 5:
                atm_s = pd.Series(atm_results)
                wr2, med2, exp2, conc2 = wstats(atm_s)
                print(f"{'':<14} n={len(atm_s):<5} OPTIONS(ATM,day1) win={wr2:5.1f}%  med={med2:+.2f}%  exp={exp2:+.3f}%  conc={conc2:.1f}%")
        print()


if __name__ == "__main__":
    run()
