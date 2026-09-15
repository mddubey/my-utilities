"""Run once/day (after refreshing data_cache), reads `open_positions.csv` (columns:
ticker,entry_date,entry_price,pattern — pattern is breakout_cont or coiled_spring) and,
for each position, replays the SAME exit logic backtest.py validated (check_exit) day by
day from entry to today. Reports the current stop/target level to update your real
broker orders to, flags if an exit condition has already fired (in case you missed it),
and reports how long it's been since the position last made a fresh high — informational
only, not a validated exit rule on its own, but a useful "is this stalling" data point."""
import pandas as pd

from backtest import load, check_exit, current_stop_level, resistance_target, MAX_INITIAL_RISK_PCT, STRUCTURAL_LOOKBACK_BC
from pivots import daily_pivots
from vcp import base_pivot

POSITIONS_FILE = "open_positions.csv"


def monitor(positions_df):
    for _, pos in positions_df.iterrows():
        ticker, entry_date, entry_price, pattern = pos.ticker, pos.entry_date, pos.entry_price, pos.pattern
        try:
            df = load(ticker, daily_pivots)
        except FileNotFoundError:
            print(f"{ticker}: no cached price data — run fetch_prices.py first")
            continue
        rows = df.reset_index()
        idx = rows.index[rows.Date == entry_date]
        if len(idx) == 0:
            print(f"{ticker}: entry_date {entry_date.date()} not found in cached data")
            continue
        entry_idx = idx[0]

        entry_row = rows.iloc[entry_idx]
        if pattern == "coiled_spring":
            base = base_pivot(rows, entry_idx)
            structural_low = base[1] if base else entry_price * (1 - MAX_INITIAL_RISK_PCT)
            structural_low = max(structural_low, entry_price * (1 - MAX_INITIAL_RISK_PCT))
        else:
            # (2026-09-15) breakout_cont's own structural low, same convention as
            # detect_entry() in backtest.py -- 20-day pre-entry lookback minimum.
            lo = max(0, entry_idx - STRUCTURAL_LOOKBACK_BC)
            structural_low = rows.iloc[lo:entry_idx].Low.min() if entry_idx > lo else entry_price * 0.9

        target = resistance_target(entry_price, entry_row)
        state = dict(entry_price=entry_price, peak_close=entry_price,
                      peak_high=entry_row.High, structural_low=structural_low, target=target,
                      days_held=0, atr_entry=entry_row.atr14)
        peak_high_date = entry_row.Date

        triggered = None
        for i in range(entry_idx + 1, len(rows)):
            row = rows.iloc[i]
            if row.corp_action_day:
                continue  # same right-censoring the backtest applies, informational here
            prev_peak_high = state["peak_high"]
            exit_reason, state = check_exit(pattern, state, row)
            if state["peak_high"] > prev_peak_high:
                peak_high_date = row.Date
            if exit_reason is not None:
                triggered = (row.Date, exit_reason, row.Close)
                break

        last_date = rows.iloc[-1].Date
        days_held = (last_date - entry_date).days
        days_since_new_high = (last_date - peak_high_date).days

        print(f"\n=== {ticker} ({pattern}) — entered {entry_date.date()} @ ₹{entry_price:.2f}, held {days_held}d ===")
        if triggered:
            t_date, t_reason, t_price = triggered
            print(f"  *** EXIT ALREADY TRIGGERED on {t_date.date()} via '{t_reason}' at ₹{t_price:.2f} — "
                  f"check you didn't miss this ***")
        else:
            stop = current_stop_level(pattern, state, rows.iloc[-1])
            print(f"  current stop   : ₹{stop:.2f}")
            print(f"  current target : {'₹' + format(state['target'], '.2f') if state['target'] is not None else 'n/a'}")
            print(f"  peak close so far: ₹{state['peak_close']:.2f}  |  days since last fresh high: {days_since_new_high}"
                  f"{'  (no progress in a while — worth a manual look, not a hard rule)' if days_since_new_high >= 15 else ''}")
            from backtest import MAX_HOLD_DAYS
            remaining = MAX_HOLD_DAYS - state["days_held"]
            print(f"  trading days held: {state['days_held']}/{MAX_HOLD_DAYS}"
                  f"{f'  ({remaining} left before the hard cap forces an exit)' if remaining > 0 else '  (cap should have fired — check exit logic)'}")
    return


if __name__ == "__main__":
    try:
        positions = pd.read_csv(POSITIONS_FILE, parse_dates=["entry_date"])
    except FileNotFoundError:
        print(f"{POSITIONS_FILE} not found — create it with columns: ticker,entry_date,entry_price,pattern")
    else:
        monitor(positions)
