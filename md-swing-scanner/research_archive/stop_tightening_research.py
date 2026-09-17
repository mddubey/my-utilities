"""Isolated research only (2026-09-12) -- NOT wired into backtest.py/option_backtest.py,
does not touch the frozen v30 production exit logic. Tests two independent fixes for the
"riding the wide stock-level 3xATR stop bleeds 58-91% of premium over a 21-day median hold"
finding (see FINDINGS.md, options-side stop-out numbers computed 2026-09-12):

  Variant 1 -- tighten the underlying stop itself (ATR_TRAIL_MULT 3.0 -> 1.5), matching the
  general "1.5xATR" dynamic-stop convention found in outside research, vs this project's own
  wider 3xATR. Re-runs the REAL stock backtest with the patched constant (monkeypatched on
  the backtest module, not edited in the file) over the same fo_universe population used for
  the existing opt_v28_*.csv comparisons, then re-uses option_backtest.run() unmodified.

  Variant 2 -- leave the stock-level stop untouched (still 3xATR, still the same v28 stock
  trades/exit dates), but add an INDEPENDENT hard stop on the option's own premium (-40% /
  -50% from entry), checked day-by-day, whichever hits first. This is the "50% of premium
  lost" convention from outside options-trading practice, tested here for the first time
  against this project's real option price data.

Both variants are backtest-only findings if/when this runs -- not adopted into any code.
"""
import backtest
import option_backtest
from pivots import daily_pivots

import pandas as pd


def variant1_tighter_atr_stop():
    fo_tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()

    backtest.ATR_TRAIL_MULT = 1.5
    trades = backtest.run(fo_tickers, True, daily_pivots, 0.0)
    backtest.ATR_TRAIL_MULT = 3.0  # restore -- this process is short-lived but be tidy anyway
    trades.to_csv("runs/trades_atr15_fo.csv", index=False)
    backtest.summarize(trades, "Variant 1: ATR_TRAIL_MULT=1.5 (fo universe, stock level)")

    combos = [("atm", "current", "ATM+current"), ("itm", "current", "ITM+current"),
              ("atm", "next", "ATM+next"), ("itm", "next", "ITM+next")]
    for moneyness, expiry_choice, name in combos:
        out = option_backtest.run("runs/trades_atr15_fo.csv", moneyness, expiry_choice)
        out.to_csv(f"runs/opt_atr15_{moneyness}_{expiry_choice}.csv", index=False)
        wins = out[out.pnl_pct > 0]
        win_rate = len(wins) / len(out) * 100 if len(out) else float("nan")
        stopped = out[out.stock_pnl_pct < 0]  # rough proxy: the stock leg lost money
        print(f"\n=== Variant 1, {name} (n={len(out)}) ===")
        print(f"win rate {win_rate:.1f}%  median {out.pnl_pct.median():.2f}%  mean {out.pnl_pct.mean():.2f}%")
        print(f"held to expiry: {(out.exit_reason == 'expired').sum()}/{len(out)}")


def simulate_option_trade_premium_stop(trade, moneyness, expiry_choice, stop_pct):
    """Same contract-selection as option_backtest.simulate_option_trade, but walks day by
    day from entry to the ORIGINAL stock-based exit date, exiting early the first day the
    option's own ClsPric closes <= stop_pct below entry -- independent of whatever the
    stock-level stop/target/climax logic says. Falls back to the normal signal/expiry exit
    if the premium stop is never breached first."""
    entry_spot = option_backtest._real_spot(trade.ticker, trade.entry_date, trade.entry_price)
    contract = option_backtest.pick_contract(trade.ticker, trade.entry_date, entry_spot, moneyness, expiry_choice)
    if contract is None:
        return None
    expiry, strike, lot_size = contract
    entry_row = option_backtest.option_row(trade.ticker, trade.entry_date, expiry, strike)
    if entry_row is None or not entry_row.ClsPric or not option_backtest.liquid(entry_row):
        return None
    entry_px = entry_row.ClsPric
    stop_price = entry_px * (1 - stop_pct)

    for d in option_backtest.days_after(trade.entry_date):
        if d > expiry:
            break
        row = option_backtest.option_row(trade.ticker, d, expiry, strike)
        if row is not None and row.ClsPric is not None and option_backtest.liquid(row):
            if row.ClsPric <= stop_price:
                return dict(
                    ticker=trade.ticker, entry_date=trade.entry_date, exit_date=d,
                    expiry=expiry, strike=strike, lot_size=int(lot_size),
                    entry_opt_price=entry_px, exit_opt_price=row.ClsPric,
                    pnl_pct=(row.ClsPric / entry_px - 1) * 100,
                    exit_reason="premium_stop", stock_pnl_pct=trade.pnl_pct,
                )
        if d >= trade.exit_date:
            break
    return option_backtest.simulate_option_trade(trade, moneyness, expiry_choice)


def variant2_premium_stop(stop_pct, moneyness, expiry_choice, label):
    trades = pd.read_csv("runs/trades_v28_fo.csv", parse_dates=["entry_date", "exit_date"])
    trades = trades[~trades.open_at_end]

    results, skipped = [], 0
    for _, trade in trades.iterrows():
        r = simulate_option_trade_premium_stop(trade, moneyness, expiry_choice, stop_pct)
        if r is None:
            skipped += 1
        else:
            results.append(r)
    out = pd.DataFrame(results)
    out.to_csv(f"runs/opt_premstop{int(stop_pct*100)}_{moneyness}_{expiry_choice}.csv", index=False)

    wins = out[out.pnl_pct > 0]
    win_rate = len(wins) / len(out) * 100 if len(out) else float("nan")
    n_premium_stop = (out.exit_reason == "premium_stop").sum()
    print(f"\n=== Variant 2, {label} (n={len(out)}, {skipped} skipped) ===")
    print(f"win rate {win_rate:.1f}%  median {out.pnl_pct.median():.2f}%  mean {out.pnl_pct.mean():.2f}%")
    print(f"exited via premium stop: {n_premium_stop}/{len(out)} ({n_premium_stop/len(out)*100:.1f}%)")
    print(f"held to expiry: {(out.exit_reason == 'expired').sum()}/{len(out)}  |  "
          f"normal signal exit: {(out.exit_reason == 'signal').sum()}/{len(out)}")


if __name__ == "__main__":
    print("########## VARIANT 1: tighter underlying stop (1.5x ATR) ##########")
    variant1_tighter_atr_stop()

    print("\n########## VARIANT 2: independent option premium stop ##########")
    for stop_pct in (0.40, 0.50):
        for moneyness, expiry_choice, name in [("itm", "next", "ITM+next"), ("atm", "next", "ATM+next")]:
            variant2_premium_stop(stop_pct, moneyness, expiry_choice, f"{name}, -{int(stop_pct*100)}% premium stop")
