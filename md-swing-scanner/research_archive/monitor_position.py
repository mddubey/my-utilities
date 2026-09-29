"""Live position monitor (2026-09-03): reuses backtest.py's own check_exit /
current_stop_level / resistance_target so an already-open discretionary trade gets
the SAME daily-refreshed stop/target the backtest's edge numbers are measured
against, instead of a hand-recomputed one that can quietly drift from the model.

NOT a signal generator. You tell it what you're already holding (ticker, pattern,
entry_date, entry_price) and it walks the cached daily bars forward from entry to
today, updating peak_close/peak_high/target exactly like simulate_ticker does, and
reports where the model says stop/target sit right now. Run once per day after
data_cache is refreshed (`fetch_prices.py`) to get that day's numbers — this is a
close-to-close model, it has nothing new to say intraday.

Usage: python3 monitor_position.py TICKER PATTERN ENTRY_DATE ENTRY_PRICE
  PATTERN: breakout_cont | coiled_spring
  ENTRY_DATE: the day the pattern actually fired (YYYY-MM-DD), not necessarily the
    day you got filled — matches how the model's own state (peak_close/peak_high)
    is seeded in backtest.py/daily_scan.py.
"""
import sys

import pandas as pd

from backtest import load, current_stop_level, resistance_target, check_exit


def monitor(ticker, pattern, entry_date, entry_price):
    df = load(ticker)
    rows = df.reset_index()
    entry_date = pd.Timestamp(entry_date)
    matches = rows.index[rows.Date == entry_date]
    if len(matches) == 0:
        print(f"No cached daily bar for {ticker} on {entry_date.date()} — "
              f"run fetch_prices.py first.")
        return None
    i0 = matches[0]
    entry_row = rows.iloc[i0]

    # Seed state the same way simulate_ticker/_initial_stop do: peak_close/peak_high
    # both start at the entry day's own extremes, not the fill price alone, so a fill
    # below that day's close doesn't understate how extended the trade already is.
    state = dict(entry_price=entry_price, peak_close=max(entry_price, entry_row.Close),
                 peak_high=max(entry_price, entry_row.High), structural_low=entry_price,
                 target=resistance_target(entry_row.Close, entry_row))

    print(f"{ticker} ({pattern}) — entry {entry_date.date()} @ {entry_price:.2f}")
    for i in range(i0 + 1, len(rows)):
        row = rows.iloc[i]
        reason, state = check_exit(pattern, state, row)
        stop_that_day = current_stop_level(pattern, state, row)
        target_str = f"{state['target']:.2f}" if state["target"] else "n/a"
        flag = f"  <- MODEL EXIT: {reason}" if reason else ""
        print(f"  {row.Date.date()}: close={row.Close:.2f}  stop={stop_that_day:.2f}  "
              f"target={target_str}{flag}")

    last = rows.iloc[-1]
    final_stop = current_stop_level(pattern, state, last)
    final_target = f"{state['target']:.2f}" if state["target"] else "n/a"
    print(f"\nAs of {last.Date.date()} close ({last.Close:.2f}): "
          f"STOP={final_stop:.2f}  TARGET={final_target}")
    return state, final_stop


if __name__ == "__main__":
    monitor(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]))
